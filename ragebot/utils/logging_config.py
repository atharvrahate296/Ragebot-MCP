"""
Logging Configuration - Suppress noisy HuggingFace and model loading logs.

This module sets up logging filters to hide verbose output from:
- HuggingFace transformers library
- sentence-transformers model loading
- BertModel initialization reports
- CUDA/device warnings

Instead, we show clean progress indicators and friendly messages.
"""
from __future__ import annotations

import logging
import warnings


def suppress_noisy_logs() -> None:
    """
    Suppress verbose logging from heavy libraries.
    Call once at application startup.
    """
    # Suppress HuggingFace warnings
    warnings.filterwarnings("ignore", category=UserWarning, module=".*transformers.*")
    warnings.filterwarnings("ignore", category=FutureWarning, module=".*transformers.*")
    warnings.filterwarnings("ignore", category=UserWarning, module=".*huggingface.*")
    
    # Set logging levels for noisy modules
    logging.getLogger("transformers").setLevel(logging.ERROR)
    logging.getLogger("transformers.modeling_utils").setLevel(logging.ERROR)
    logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
    logging.getLogger("sentence_transformers.cross_encoders").setLevel(logging.ERROR)
    logging.getLogger("sentence_transformers.models").setLevel(logging.ERROR)
    logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
    logging.getLogger("huggingface_hub.file_download").setLevel(logging.ERROR)
    logging.getLogger("torch").setLevel(logging.ERROR)
    logging.getLogger("pytorch_lightning").setLevel(logging.ERROR)
    
    # Suppress specific noisy loggers
    for logger_name in [
        "filelock",
        "urllib3.connectionpool",
        "h11._connection",
        "httpx",
    ]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def setup_clean_progress() -> None:
    """
    Configure progress indicators instead of raw logs.
    Integrates with Rich for clean terminal output.
    """
    # Rich handles progress bar setup, so this is mostly for logging config
    suppress_noisy_logs()


if __name__ == "__main__":
    suppress_noisy_logs()
    print("Logging filters applied.")
