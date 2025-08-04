"""
Logging utilities for Orchestra extensions

Provides consistent log formatting and truncation capabilities.
"""

import json
import logging
from typing import Any, Dict, List, Tuple


class TruncatingFormatter(logging.Formatter):
    """Custom formatter that truncates long values in log messages"""

    def __init__(
        self,
        *args: Any,
        max_length: int = 200,
        truncate_enabled: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.max_length = max_length
        self.truncate_enabled = truncate_enabled

    def format(self, record: logging.LogRecord) -> str:
        # Format the message first
        msg = super().format(record)

        if self.truncate_enabled:
            # Truncate long lines
            if len(msg) > self.max_length:
                # Keep important parts (timestamp, level, function) and truncate the message part
                parts = msg.split(" - ", 4)  # Split on our standard delimiter
                if len(parts) >= 5:
                    # Reconstruct with truncated message
                    prefix = " - ".join(parts[:4])
                    message = parts[4]
                    if len(message) > self.max_length:
                        truncated_msg = message[: self.max_length] + "... [truncated]"
                        msg = f"{prefix} - {truncated_msg}"

        return msg


def truncate_value(value: Any, max_length: int = 100) -> str:
    """Truncate a value for logging purposes

    Args:
        value: Value to truncate
        max_length: Maximum length before truncation

    Returns:
        String representation of value, truncated if necessary
    """
    if value is None:
        return "None"

    # Handle different types
    if isinstance(value, str):
        if len(value) > max_length:
            return f"{value[:max_length]}... [{len(value)} chars total]"
        return value

    if isinstance(value, (dict, list)):
        # Convert to JSON string with nice formatting
        try:
            json_str = json.dumps(value, indent=2)
            if len(json_str) > max_length:
                # For dicts/lists, show the beginning and indicate size
                if isinstance(value, dict):
                    return f"{json_str[:max_length]}... [{len(value)} keys total]"
                return f"{json_str[:max_length]}... [{len(value)} items total]"
            return json_str
        except (TypeError, ValueError):
            # Fallback to str representation
            str_val = str(value)
            if len(str_val) > max_length:
                return f"{str_val[:max_length]}... [{len(str_val)} chars total]"
            return str_val

    else:
        # For other types, use string representation
        str_val = str(value)
        if len(str_val) > max_length:
            return f"{str_val[:max_length]}... [{len(str_val)} chars total]"
        return str_val


def format_hook_context(context: Dict[str, Any], max_value_length: int = 100) -> str:
    """Format hook context for logging with truncation

    Args:
        context: Hook context dictionary
        max_value_length: Maximum length for each value

    Returns:
        Formatted string representation
    """
    formatted_parts = []

    # Important keys to always show (in order)
    priority_keys = ["hook_type", "tool_name", "tool_input", "decision", "reason"]

    # Show priority keys first
    for key in priority_keys:
        if key in context:
            value = truncate_value(context[key], max_value_length)
            formatted_parts.append(f"{key}: {value}")

    # Show remaining keys
    for key, value in context.items():
        if key not in priority_keys:
            value_str = truncate_value(value, max_value_length)
            formatted_parts.append(f"{key}: {value_str}")

    return "{ " + ", ".join(formatted_parts) + " }"


def setup_logger(
    name: str,
    log_file: str,
    level: int = logging.DEBUG,
    truncate: bool = True,
    max_length: int = 200,
) -> logging.Logger:
    """Set up a logger with consistent formatting and truncation

    Args:
        name: Logger name
        log_file: Path to log file
        level: Logging level
        truncate: Whether to enable truncation
        max_length: Maximum line length before truncation

    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Only add handler if logger doesn't already have handlers
    if not logger.handlers:
        # File handler
        file_handler = logging.FileHandler(log_file, mode="a")
        file_handler.setLevel(level)

        # Create formatter with truncation
        formatter = TruncatingFormatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
            max_length=max_length,
            truncate_enabled=truncate,
        )
        file_handler.setFormatter(formatter)

        # Add handler to logger
        logger.addHandler(file_handler)

    return logger


class LogContext:
    """Context manager for temporarily disabling truncation"""

    def __init__(self, logger: logging.Logger, truncate: bool = False) -> None:
        self.logger = logger
        self.truncate = truncate
        self.original_formatters: List[Tuple[logging.Handler, bool]] = []

    def __enter__(self) -> "LogContext":
        # Save original formatters and update truncation setting
        for handler in self.logger.handlers:
            formatter = handler.formatter
            if isinstance(formatter, TruncatingFormatter):
                self.original_formatters.append((handler, formatter.truncate_enabled))
                formatter.truncate_enabled = self.truncate
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        # Restore original truncation settings
        for handler, original_setting in self.original_formatters:
            if isinstance(handler.formatter, TruncatingFormatter):
                handler.formatter.truncate_enabled = original_setting
