#!/usr/bin/env python3
"""
Centralized Logging for InvestIQ
Provides rotating file handlers and stdout logging
"""
import logging
import os
from logging.handlers import RotatingFileHandler
import sys

# Import LOG_DIR from config
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import LOG_DIR

def get_logger(name: str, level=logging.INFO) -> logging.Logger:
    """
    Get or create a logger with both file and console handlers.
    
    Args:
        name: Logger name (will be used as filename: logs/{name}.log)
        level: Logging level (default: INFO)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # Format: "2026-02-28 14:30:45 [INFO] Message here"
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    
    # File Handler (Rotating: 5MB max, 3 backups)
    log_file = os.path.join(LOG_DIR, f"{name}.log")
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Console Handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

if __name__ == "__main__":
    # Test the logger
    test_log = get_logger("test")
    test_log.info("Logger initialized successfully!")
    test_log.debug("This is a debug message")
    test_log.warning("This is a warning")
    test_log.error("This is an error")
    print(f"Log file created at: {os.path.join(LOG_DIR, 'test.log')}")
