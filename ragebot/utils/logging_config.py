# ragebot/utils/logging_config.py
"""
Logging Configuration - Suppress noisy HuggingFace and model loading logs.
Enhanced with background task handling and progress state management.
"""
from __future__ import annotations

import logging
import warnings
import sys
from typing import Optional


# Store original log levels for restoration
_ORIGINAL_LEVELS = {}


def suppress_noisy_logs() -> None:
    """
    Suppress verbose logging from heavy libraries.
    Call once at application startup.
    Suppresses:
    - HuggingFace transformers & hub logging
    - sentence-transformers model loading
    - BertModel initialization
    - CUDA/device warnings
    - urllib3 connection pool logs
    """
    # Store original levels in case we need to restore
    loggers_to_suppress = {
        "transformers": logging.ERROR,
        "transformers.modeling_utils": logging.ERROR,
        "transformers.configuration_utils": logging.ERROR,
        "transformers.tokenization_utils": logging.ERROR,
        "sentence_transformers": logging.ERROR,
        "sentence_transformers.cross_encoders": logging.ERROR,
        "sentence_transformers.models": logging.ERROR,
        "huggingface_hub": logging.ERROR,
        "huggingface_hub.file_download": logging.ERROR,
        "huggingface_hub.repository": logging.ERROR,
        "huggingface_hub.utils._authentication": logging.ERROR,
        "torch": logging.ERROR,
        "torch.distributed": logging.ERROR,
        "pytorch_lightning": logging.ERROR,
        "filelock": logging.WARNING,
        "urllib3.connectionpool": logging.WARNING,
        "urllib3.util.retry": logging.WARNING,
        "h11._connection": logging.WARNING,
        "httpx": logging.WARNING,
        "httpcore": logging.WARNING,
        "openai": logging.WARNING,
        "requests": logging.WARNING,
        "chardet": logging.WARNING,
    }
    
    for logger_name, level in loggers_to_suppress.items():
        logger = logging.getLogger(logger_name)
        _ORIGINAL_LEVELS[logger_name] = logger.level
        logger.setLevel(level)
    
    # Suppress warnings from specific modules
    warnings.filterwarnings("ignore", category=UserWarning, module=".*transformers.*")
    warnings.filterwarnings("ignore", category=FutureWarning, module=".*transformers.*")
    warnings.filterwarnings("ignore", category=UserWarning, module=".*huggingface.*")
    warnings.filterwarnings("ignore", category=FutureWarning, module=".*huggingface.*")
    warnings.filterwarnings("ignore", category=DeprecationWarning, module=".*torch.*")
    
    # Suppress specific common warnings
    warnings.filterwarnings("ignore", message=".*Avoid calling deprecated DeprecationWarning.*")
    warnings.filterwarnings("ignore", message=".*Some weights.*not initialized.*")


def restore_original_logging() -> None:
    """Restore original logging levels (useful for debugging)."""
    for logger_name, level in _ORIGINAL_LEVELS.items():
        logging.getLogger(logger_name).setLevel(level)


def setup_debug_logging(enable: bool = True) -> None:
    """
    Setup debug logging. Set to False to suppress, True to enable.
    Only affects specified modules.
    """
    debug_loggers = [
        "ragebot",
        "ragebot.core",
        "ragebot.llm",
        "ragebot.storage",
        "ragebot.search",
    ]
    
    level = logging.DEBUG if enable else logging.WARNING
    for logger_name in debug_loggers:
        logging.getLogger(logger_name).setLevel(level)


class BackgroundTaskLogger:
    """Log background tasks without cluttering main output."""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"ragebot.background.{name}")
        self.logger.setLevel(logging.DEBUG)
    
    def info(self, message: str) -> None:
        """Log info message for background task."""
        self.logger.info(f"[{self.name}] {message}")
    
    def debug(self, message: str) -> None:
        """Log debug message for background task."""
        self.logger.debug(f"[{self.name}] {message}")
    
    def warning(self, message: str) -> None:
        """Log warning message for background task."""
        self.logger.warning(f"[{self.name}] {message}")
    
    def error(self, message: str) -> None:
        """Log error message for background task."""
        self.logger.error(f"[{self.name}] {message}")


class ProgressState:
    """Track progress state for background operations."""
    
    def __init__(self, operation: str, total_items: int = 0):
        self.operation = operation
        self.total_items = total_items
        self.current_item = 0
        self.status = "initializing"
        self.errors = []
        self.logger = BackgroundTaskLogger(operation)
    
    def update(self, current: int, status: str = "") -> None:
        """Update progress state."""
        self.current_item = current
        if status:
            self.status = status
        self.logger.debug(f"Progress: {current}/{self.total_items} ({status})")
    
    def add_error(self, error: str) -> None:
        """Record an error during operation."""
        self.errors.append(error)
        self.logger.warning(f"Error during operation: {error}")
    
    def complete(self) -> None:
        """Mark operation as complete."""
        self.status = "complete"
        self.logger.info(f"Operation complete: {self.total_items} items processed, "
                        f"{len(self.errors)} errors")
    
    def get_summary(self) -> dict:
        """Get operation summary."""
        return {
            "operation": self.operation,
            "total_items": self.total_items,
            "processed": self.current_item,
            "errors": len(self.errors),
            "status": self.status,
            "error_list": self.errors[:10],  # First 10 errors
        }


def setup_clean_progress() -> None:
    """
    Configure progress indicators instead of raw logs.
    Integrates with Rich for clean terminal output.
    """
    suppress_noisy_logs()
    # Additional progress-specific setup can go here


def suppress_transformer_warnings() -> None:
    """Suppress only transformer-related warnings."""
    warnings.filterwarnings("ignore", category=UserWarning, module=".*transformers.*")
    warnings.filterwarnings("ignore", category=FutureWarning, module=".*transformers.*")


def suppress_pytorch_warnings() -> None:
    """Suppress only PyTorch-related warnings."""
    warnings.filterwarnings("ignore", category=DeprecationWarning, module=".*torch.*")
    warnings.filterwarnings("ignore", message=".*Avoid calling deprecated.*")


def configure_rich_logging() -> None:
    """
    Configure logging with Rich formatting for better terminal display.
    """
    suppress_noisy_logs()
    
    # This can be extended to use Rich's logging handler
    # For now, just suppress the noisy libraries


# Initialize on module import
suppress_noisy_logs()


if __name__ == "__main__":
    # Test the logging setup
    suppress_noisy_logs()
    
    # Test background logger
    bg_logger = BackgroundTaskLogger("test_task")
    bg_logger.info("Test message")
    bg_logger.debug("Debug message")
    
    # Test progress state
    progress = ProgressState("indexing", total_items=100)
    progress.update(50, "processing files")
    progress.add_error("Failed to parse file.py")
    progress.complete()
    
    summary = progress.get_summary()
    print(f"Progress summary: {summary}")
