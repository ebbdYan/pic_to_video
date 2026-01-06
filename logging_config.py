import logging
import os
from logging.handlers import RotatingFileHandler

# --- Configuration ---
LOG_FILE_NAME = "app.log"
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
LOG_BACKUP_COUNT = 3

# --- Setup Logger ---
def setup_logging():
    """Initializes and configures the root logger."""
    log_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s'
    )

    # Use the directory of this script as the base for the log file
    log_dir = os.path.dirname(os.path.abspath(__file__))
    log_file_path = os.path.join(log_dir, LOG_FILE_NAME)

    # Rotating file handler
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.INFO)

    # Get the root logger and add the handler
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Avoid adding duplicate handlers if this function is called multiple times
    if not root_logger.handlers:
        root_logger.addHandler(file_handler)

    return root_logger

# --- Initialize and get logger ---
# This will be imported by other modules
logger = setup_logging()

