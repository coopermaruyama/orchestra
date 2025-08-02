"""
Subagent Runner for Orchestra Extensions

Provides git-aware subagent invocation with automatic context creation and branch management.
"""

import subprocess
import os
import json
from typing import Dict, Any, Optional, List
from pathlib import Path

from .git_task_manager import GitTaskManager
from .task_state import GitTaskState


class SubagentRunner:
    """Manages subagent invocation with git context integration"""
    
    def __init__(self, git_manager: GitTaskManager):
        """Initialize subagent runner
        
        Args:
            git_manager: GitTaskManager instance for git operations
        """
        self.git_manager = git_manager
        self.subagent_types = {
            'scope-creep-detector': 'Identifies when commands introduce unnecessary complexity, abstractions, or architectural patterns before basic functionality is complete',
            'over-engineering-detector': 'Identifies when commands are unrelated to the current task objectives and requirements',
            'off-topic-detector': 'Detects when commands deviate from core task requirements by adding enhancements, improvements, or features before completing primary objectives'
        }
    
    def is_claude_code_environment(self) -> bool:
        """Check if running inside Claude Code environment"""
        return os.environ.get('CLAUDECODE') == '1'
    
    def invoke_subagent(self, subagent_type: str, 
                       task_state: GitTaskState,
                       analysis_context: str,
                       create_branch: bool = True) -> Dict[str, Any]:
        """Invoke a subagent with git context
        
        Args:
            subagent_type: Type of subagent to invoke
            task_state: Current task state with git information
            analysis_context: Context for subagent analysis
            create_branch: Whether to create a dedicated branch for subagent
            
        Returns:
            Subagent response or error information
        """
        if subagent_type not in self.subagent_types:
            return {
                'error': f'Unknown subagent type: {subagent_type}',
                'available_types': list(self.subagent_types.keys())
            }
        
        try:
            # Create subagent branch if requested
            if create_branch:
                subagent_branch = self.git_manager.create_subagent_branch(task_state, subagent_type)
            else:
                subagent_branch = task_state.branch_name
            
            # Get git diff for context
            diff_output = self.git_manager.get_task_diff(task_state)
            changed_files = self.git_manager.get_task_file_changes(task_state)
            
            # Build analysis prompt with git context
            prompt = self._build_analysis_prompt(
                subagent_type=subagent_type,
                task_description=task_state.task_description,
                diff_output=diff_output,
                changed_files=changed_files,
                analysis_context=analysis_context,
                branch_name=subagent_branch
            )
            
            if self.is_claude_code_environment():
                # Running inside Claude Code - return structured response
                return self._invoke_claude_code_subagent(subagent_type, prompt)
            else:
                # Running externally - call external Claude instance
                return self._invoke_external_claude(prompt, subagent_type)
                
        except Exception as e:
            return {
                'error': f'Failed to invoke subagent: {str(e)}',
                'subagent_type': subagent_type
            }
    
    def _build_analysis_prompt(self, subagent_type: str, 
                              task_description: str,
                              diff_output: str,
                              changed_files: List[str],
                              analysis_context: str,
                              branch_name: str) -> str:
        """Build comprehensive analysis prompt with git context"""
        
        # Get subagent description
        description = self.subagent_types.get(subagent_type, subagent_type)
        
        prompt = f"""You are a {subagent_type} subagent analyzing a development session.

**Your Role**: {description}

**Current Task**: {task_description}

**Git Context**:
- Analysis Branch: {branch_name}
- Files Changed: {len(changed_files)} files
- Changed Files: {', '.join(changed_files) if changed_files else 'None'}

**Session Context**:
{analysis_context}

**Git Diff of Changes**:
```diff
{diff_output if diff_output.strip() else 'No changes detected'}
```

**Analysis Instructions**:
1. Review the task description and current changes
2. Identify any deviations from the core task requirements
3. Consider whether the work is progressing toward the stated goal
4. Flag any concerning patterns or unnecessary complexity

**Response Format**:
Provide a clear assessment with specific recommendations. If you detect issues, explain:
- What specific deviation you identified
- Why it's problematic for the current task
- What should be done instead

If the work appears aligned with the task, confirm this and suggest next steps.
"""
        
        return prompt
    
    def _invoke_claude_code_subagent(self, subagent_type: str, prompt: str) -> Dict[str, Any]:
        """Invoke subagent within Claude Code using Task tool"""
        # This would be called from within Claude Code's hook system
        # The actual Task tool invocation would be handled by the calling code
        return {
            'method': 'task_tool',
            'subagent_type': subagent_type,
            'prompt': prompt,
            'message': 'Use Task tool with this prompt and subagent_type'
        }
    
    def _invoke_external_claude(self, prompt: str, subagent_type: str) -> Dict[str, Any]:
        """Invoke external Claude instance via subprocess"""
        try:
            # Use claude CLI with the prompt
            result = subprocess.run([
                'claude', '-p', prompt
            ], capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'response': result.stdout.strip(),
                    'subagent_type': subagent_type,
                    'method': 'external_claude'
                }
            else:
                return {
                    'error': f'Claude CLI failed with return code {result.returncode}',
                    'stderr': result.stderr,
                    'subagent_type': subagent_type
                }
                
        except subprocess.TimeoutExpired:
            return {
                'error': 'Claude CLI call timed out',
                'subagent_type': subagent_type
            }
        except FileNotFoundError:
            return {
                'error': 'Claude CLI not found. Please ensure claude is installed and in PATH.',
                'subagent_type': subagent_type
            }
        except Exception as e:
            return {
                'error': f'Unexpected error calling Claude CLI: {str(e)}',
                'subagent_type': subagent_type
            }
    
    def invoke_multiple_subagents(self, subagent_types: List[str],
                                 task_state: GitTaskState,
                                 analysis_context: str) -> Dict[str, Any]:
        """Invoke multiple subagents and combine their responses
        
        Args:
            subagent_types: List of subagent types to invoke
            task_state: Current task state
            analysis_context: Context for analysis
            
        Returns:
            Combined responses from all subagents
        """
        results = {}
        
        for subagent_type in subagent_types:
            result = self.invoke_subagent(
                subagent_type=subagent_type,
                task_state=task_state,
                analysis_context=analysis_context,
                create_branch=True
            )
            results[subagent_type] = result
        
        # Analyze combined results
        has_errors = any('error' in result for result in results.values())
        successful_analyses = [
            result['response'] for result in results.values() 
            if 'response' in result
        ]
        
        return {
            'individual_results': results,
            'has_errors': has_errors,
            'successful_count': len(successful_analyses),
            'total_count': len(subagent_types),
            'combined_analysis': self._combine_analyses(successful_analyses) if successful_analyses else None
        }
    
    def _combine_analyses(self, analyses: List[str]) -> str:
        """Combine multiple subagent analyses into a coherent summary"""
        if not analyses:
            return "No successful analyses to combine."
        
        if len(analyses) == 1:
            return analyses[0]
        
        combined = "**Combined Subagent Analysis**:\n\n"
        
        for i, analysis in enumerate(analyses, 1):
            combined += f"**Analysis {i}**:\n{analysis}\n\n"
        
        combined += "**Summary**: Multiple subagents have provided analysis above. Review each perspective to understand the full context."
        
        return combined
    
    def get_available_subagents(self) -> Dict[str, str]:
        """Get list of available subagent types and their descriptions"""
        return self.subagent_types.copy()
    
    def validate_subagent_environment(self) -> Dict[str, Any]:
        """Validate that the environment is properly set up for subagent invocation"""
        validation = {
            'claude_code_detected': self.is_claude_code_environment(),
            'git_repo': self.git_manager._is_git_repo(),
            'claude_cli_available': False,
            'working_directory': self.git_manager.working_dir,
            'issues': []
        }
        
        # Check if Claude CLI is available for external invocation
        try:
            result = subprocess.run(['claude', '--version'], 
                                  capture_output=True, timeout=5)
            validation['claude_cli_available'] = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            validation['claude_cli_available'] = False
        
        # Identify issues
        if not validation['git_repo']:
            validation['issues'].append('Not in a git repository')
        
        if not validation['claude_code_detected'] and not validation['claude_cli_available']:
            validation['issues'].append('Neither Claude Code environment nor Claude CLI available')
        
        return validation