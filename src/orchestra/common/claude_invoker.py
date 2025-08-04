"""
Claude Invoker - Core functionality for invoking Claude in various contexts

Provides a unified interface for invoking Claude using the Python SDK
with support for different models and context configurations.
"""

import asyncio
import json
import os
import re
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Union

from claude_code_sdk import ClaudeSDKClient, ClaudeCodeOptions, AssistantMessage, TextBlock, ResultMessage


class ClaudeInvoker:
    """Manages Claude invocations using the Python SDK"""

    # Model aliases for different use cases
    MODELS = {
        "default": None,  # Use Claude's default
        "fast": "claude-3-haiku-20240307",  # Fast, cost-effective for simple tasks
        "balanced": "sonnet",  # Good balance of speed/quality
        "powerful": "opus",  # High quality responses
        "small": "claude-3-haiku-20240307",  # Alias for fast
    }

    def __init__(self) -> None:
        """Initialize Claude invoker"""
        pass

    def invoke_claude(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        include_git_diff: bool = False,
        allowed_tools: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Invoke Claude with the given prompt and configuration

        Args:
            prompt: The user prompt to send to Claude
            model: Model to use (can be alias like 'fast', 'balanced', or actual model name)
            system_prompt: System prompt to prepend
            context: Additional context to include
            temperature: Temperature for response generation
            max_tokens: Maximum tokens in response
            include_git_diff: Whether to include current git diff in context
            allowed_tools: Space-separated list of allowed tools (e.g., "Bash(git:*) Edit")

        Returns:
            Response dict with 'success', 'response', and other metadata
        """
        try:
            # Resolve model alias
            if model and model in self.MODELS:
                model = self.MODELS[model]

            # Build the full prompt with context
            full_prompt = self._build_full_prompt(
                prompt=prompt,
                system_prompt=system_prompt,
                context=context,
                include_git_diff=include_git_diff,
            )

            # Create temporary settings file with hooks disabled
            temp_settings = {
                "hooks": {
                    "pre_command": [],
                    "post_command": [],
                    "prompt": [],
                    "file_change": []
                }
            }
            
            # Write to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(temp_settings, f)
                temp_settings_path = f.name
            
            # Configure options
            options = ClaudeCodeOptions()
            if model:
                options.model = model
            if system_prompt:
                options.system_prompt = system_prompt
            
            # Override settings to disable all hooks for external Claude instances
            # This prevents the external Claude from also having tidy extensions applied
            options.settings = temp_settings_path

            # Set environment variable to prevent recursive calls
            original_env = os.environ.get("ORCHESTRA_CLAUDE_INVOCATION")
            os.environ["ORCHESTRA_CLAUDE_INVOCATION"] = "1"
            
            try:
                # Use the ClaudeSDKClient for better control
                import asyncio
                
                async def run_query():
                response_text = ""
                messages = []
                cost_info = {}

                async with ClaudeSDKClient(options) as client:
                    # Send the query
                    await client.query(full_prompt)
                    
                    # Receive all messages in the response
                    async for message in client.receive_response():
                        messages.append(message)
                        if isinstance(message, AssistantMessage):
                            for block in message.content:
                                if isinstance(block, TextBlock):
                                    response_text += block.text
                        elif isinstance(message, ResultMessage):
                            cost_info = {
                                "duration_ms": message.duration_ms,
                                "duration_api_ms": message.duration_api_ms,
                                "total_cost_usd": message.total_cost_usd,
                            }

                return {
                    "success": True,
                    "response": response_text.strip(),
                    "method": "python_sdk_client",
                    "model": model,
                    "messages": messages,
                    "cost_info": cost_info,
                }

                # Try to run in new loop
                try:
                    return asyncio.run(run_query())
                except RuntimeError as e:
                    if "cannot be called from a running event loop" in str(e):
                        # We're in an async context, run in thread
                        with ThreadPoolExecutor() as executor:
                            future = executor.submit(lambda: asyncio.run(run_query()))
                            return future.result()
                    else:
                        raise
            
            finally:
                # Clean up environment variable
                if original_env is None:
                    os.environ.pop("ORCHESTRA_CLAUDE_INVOCATION", None)
                else:
                    os.environ["ORCHESTRA_CLAUDE_INVOCATION"] = original_env
                
                # Clean up temporary settings file
                try:
                    os.unlink(temp_settings_path)
                except OSError:
                    pass

        except Exception as e:
            import traceback
            return {
                "success": False,
                "error": f"SDK invocation failed: {e!s}",
                "traceback": traceback.format_exc(),
                "method": "python_sdk",
            }


    def check_predicate(
        self,
        question: str,
        context: Optional[Union[str, Dict[str, Any]]] = None,
        include_git_diff: bool = False,
        confidence_threshold: float = 0.8,
    ) -> Dict[str, Any]:
        """Ask Claude a yes/no question and get a boolean response

        Args:
            question: A yes/no question to ask
            context: Additional context (string or dict)
            include_git_diff: Whether to include current git diff
            confidence_threshold: Minimum confidence for a definitive answer

        Returns:
            Dict with 'answer' (bool), 'confidence' (float), 'reasoning' (str)
        """
        # Format context if provided as string
        if isinstance(context, str):
            context = {"additional_context": context}

        # Build predicate prompt
        predicate_prompt = f"""Answer the following yes/no question based on the provided context.

Question: {question}

Instructions:
1. Answer with YES or NO
2. Provide a confidence level (0.0 to 1.0)
3. Give brief reasoning (1-2 sentences)

Response format:
ANSWER: [YES/NO]
CONFIDENCE: [0.0-1.0]
REASONING: [Brief explanation]
"""

        system_prompt = """You are a precise evaluation assistant. You answer yes/no questions based on provided context. Be decisive but accurate."""

        # Use default model for predicates (fast model has token limit issues)
        result = self.invoke_claude(
            prompt=predicate_prompt,
            model=None,  # Use default model to avoid token limits
            system_prompt=system_prompt,
            context=context,
            include_git_diff=include_git_diff,
            temperature=0.1,  # Low temperature for consistency
            max_tokens=150,  # Short responses expected
        )

        if result.get("success"):
            return self._parse_predicate_response(
                result["response"], confidence_threshold
            )
        return {
            "answer": None,
            "confidence": 0.0,
            "reasoning": f"Failed to get response: {result.get('error', 'Unknown error')}",
            "error": result.get("error"),
        }

    def _build_full_prompt(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        include_git_diff: bool = False,
    ) -> str:
        """Build complete prompt with all context"""
        parts = []

        # Add system prompt if provided
        if system_prompt:
            parts.append(f"System: {system_prompt}\n")

        # Add context if provided
        if context:
            parts.append("Context:")
            for key, value in context.items():
                if isinstance(value, (list, dict)):
                    value = json.dumps(value, indent=2)
                parts.append(f"- {key}: {value}")
            parts.append("")  # Empty line

        # Add git diff if requested
        if include_git_diff:
            diff = self._get_git_diff()
            if diff:
                parts.append("Current Git Diff:")
                parts.append("```diff")
                parts.append(diff)
                parts.append("```")
                parts.append("")

        # Add main prompt
        parts.append(prompt)

        return "\n".join(parts)

    def _get_git_diff(self) -> Optional[str]:
        """Get current git diff"""
        try:
            result = subprocess.run(
                ["git", "diff", "--staged", "HEAD"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                staged_diff = result.stdout.strip()
            else:
                staged_diff = ""

            # Also get unstaged changes
            result = subprocess.run(
                ["git", "diff"], check=False, capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                unstaged_diff = result.stdout.strip()
            else:
                unstaged_diff = ""

            # Combine diffs
            diff_parts = []
            if staged_diff:
                diff_parts.append("=== Staged Changes ===")
                diff_parts.append(staged_diff)
            if unstaged_diff:
                if diff_parts:
                    diff_parts.append("\n=== Unstaged Changes ===")
                else:
                    diff_parts.append("=== Unstaged Changes ===")
                diff_parts.append(unstaged_diff)

            return "\n".join(diff_parts) if diff_parts else None

        except Exception:
            return None

    def _parse_predicate_response(
        self, response: str, confidence_threshold: float
    ) -> Dict[str, Any]:
        """Parse predicate response from Claude"""
        # Default values
        result = {
            "answer": None,
            "confidence": 0.0,
            "reasoning": "",
            "raw_response": response,
        }

        # Parse response
        lines = response.strip().split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("ANSWER:"):
                answer_text = line.replace("ANSWER:", "").strip().upper()
                result["answer"] = answer_text == "YES"
            elif line.startswith("CONFIDENCE:"):
                try:
                    conf_text = line.replace("CONFIDENCE:", "").strip()
                    result["confidence"] = float(conf_text)
                except ValueError:
                    pass
            elif line.startswith("REASONING:"):
                result["reasoning"] = line.replace("REASONING:", "").strip()

        # Handle cases where parsing failed
        if result["answer"] is None:
            # Try to find YES/NO in response as whole words
            response_upper = response.upper()
            yes_matches = len(re.findall(r"\bYES\b", response_upper))
            no_matches = len(re.findall(r"\bNO\b", response_upper))

            if yes_matches > 0 and no_matches == 0:
                result["answer"] = True
                result["confidence"] = 0.5  # Low confidence due to parsing issue
            elif no_matches > 0 and yes_matches == 0:
                result["answer"] = False
                result["confidence"] = 0.5
            elif yes_matches > no_matches:
                # More YES than NO
                result["answer"] = True
                result["confidence"] = 0.3
            elif no_matches > yes_matches:
                # More NO than YES
                result["answer"] = False
                result["confidence"] = 0.3
            else:
                # Equal or both zero, cannot determine
                result["answer"] = None
                result["confidence"] = 0.0

        # Apply confidence threshold
        if result["confidence"] < confidence_threshold:
            result["definitive"] = False
            # Keep the answer but mark as not definitive
        else:
            result["definitive"] = True

        return result

    def batch_check_predicates(
        self,
        predicates: List[Dict[str, Any]],
        shared_context: Optional[Dict[str, Any]] = None,
        include_git_diff: bool = False,
    ) -> List[Dict[str, Any]]:
        """Check multiple predicates efficiently

        Args:
            predicates: List of dicts with 'question' and optional 'context'
            shared_context: Context shared by all predicates
            include_git_diff: Whether to include git diff for all predicates

        Returns:
            List of predicate results
        """
        results = []

        for pred in predicates:
            # Merge contexts
            context = {}
            if shared_context:
                context.update(shared_context)
            if pred.get("context"):
                context.update(pred["context"])

            # Check predicate
            result = self.check_predicate(
                question=pred["question"],
                context=context if context else None,
                include_git_diff=include_git_diff,
                confidence_threshold=pred.get("confidence_threshold", 0.8),
            )

            # Add question to result for reference
            result["question"] = pred["question"]
            results.append(result)

        return results


# Convenience functions
_default_invoker = None


def get_invoker() -> ClaudeInvoker:
    """Get default Claude invoker instance"""
    global _default_invoker
    if _default_invoker is None:
        _default_invoker = ClaudeInvoker()
    return _default_invoker


def invoke_claude(**kwargs) -> Dict[str, Any]:
    """Convenience function to invoke Claude"""
    return get_invoker().invoke_claude(**kwargs)


def check_predicate(**kwargs) -> Dict[str, Any]:
    """Convenience function to check a predicate"""
    return get_invoker().check_predicate(**kwargs)
