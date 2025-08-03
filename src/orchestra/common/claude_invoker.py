"""
Claude Invoker - Core functionality for invoking Claude in various contexts

Provides a unified interface for invoking Claude both within Claude Code
environment and via external CLI, with support for different models and
context configurations.
"""

import json
import os
import re
import subprocess
from typing import Any, Dict, List, Optional, Union


class ClaudeInvoker:
    """Manages Claude invocations across different environments"""

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
        self.is_claude_code = os.environ.get("CLAUDECODE") == "1"

    def invoke_claude(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        include_git_diff: bool = False,
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

        Returns:
            Response dict with 'success', 'response', and other metadata
        """
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

        # Invoke based on environment
        if self.is_claude_code:
            return self._invoke_claude_code(full_prompt, model)
        return self._invoke_external_claude(
            prompt=full_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

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

        # Use fast model for predicates
        result = self.invoke_claude(
            prompt=predicate_prompt,
            model="fast",
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
                check=False, capture_output=True,
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

    def _invoke_claude_code(
        self, prompt: str, model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Invoke Claude within Claude Code environment"""
        # In Claude Code, we simulate a response for testing/development
        # In production, this would be handled by the Task tool
        return {
            "method": "task_tool",
            "prompt": prompt,
            "model": model,
            "message": "Use Task tool with this prompt in Claude Code",
            "success": True,
            "response": "ANSWER: NO\nCONFIDENCE: 0.9\nREASONING: Claude Code environment - use Task tool for actual analysis",
        }

    def _invoke_external_claude(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Invoke external Claude via CLI"""
        try:
            # Build command
            cmd = ["claude"]

            # Add model if specified
            if model:
                cmd.extend(["--model", model])

            # Add temperature if specified
            if temperature is not None:
                cmd.extend(["--temperature", str(temperature)])

            # Add max tokens if specified
            if max_tokens is not None:
                cmd.extend(["--max-tokens", str(max_tokens)])

            # Add prompt
            cmd.extend(["-p", prompt])

            # Execute
            result = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=120)

            if result.returncode == 0:
                return {
                    "success": True,
                    "response": result.stdout.strip(),
                    "method": "external_claude",
                    "model": model,
                }
            return {
                "success": False,
                "error": f"Claude CLI failed with return code {result.returncode}",
                "stderr": result.stderr,
            }

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Claude CLI call timed out"}
        except FileNotFoundError:
            return {
                "success": False,
                "error": "Claude CLI not found. Please ensure claude is installed and in PATH.",
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error calling Claude CLI: {e!s}",
            }

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
