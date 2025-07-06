"""
Logging configuration and utilities for the AI agents system.
"""

import logging
import sys
from datetime import datetime
from typing import Optional


def setup_logging(
    level: str = "INFO",
    format_string: Optional[str] = None,
    include_timestamp: bool = True
) -> None:
    """
    Set up logging configuration for the AI agents system.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Custom format string for log messages
        include_timestamp: Whether to include timestamp in log messages
    """
    if format_string is None:
        if include_timestamp:
            format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        else:
            format_string = '%(name)s - %(levelname)s - %(message)s'
    
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=format_string,
        stream=sys.stdout
    )
    
    # Set third-party library log levels to reduce noise
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('googleapiclient').setLevel(logging.WARNING)
    logging.getLogger('google.auth').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class AgentLogger:
    """Logger wrapper with agent-specific functionality."""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.logger = logging.getLogger(f"agents.{agent_name}")
    
    def info(self, message: str, task_id: Optional[str] = None):
        """Log info message with optional task ID."""
        if task_id:
            self.logger.info(f"[{self.agent_name}] Task {task_id}: {message}")
        else:
            self.logger.info(f"[{self.agent_name}] {message}")
    
    def error(self, message: str, task_id: Optional[str] = None, exc_info: bool = False):
        """Log error message with optional task ID."""
        if task_id:
            self.logger.error(f"[{self.agent_name}] Task {task_id}: {message}", exc_info=exc_info)
        else:
            self.logger.error(f"[{self.agent_name}] {message}", exc_info=exc_info)
    
    def warning(self, message: str, task_id: Optional[str] = None):
        """Log warning message with optional task ID."""
        if task_id:
            self.logger.warning(f"[{self.agent_name}] Task {task_id}: {message}")
        else:
            self.logger.warning(f"[{self.agent_name}] {message}")
    
    def debug(self, message: str, task_id: Optional[str] = None):
        """Log debug message with optional task ID."""
        if task_id:
            self.logger.debug(f"[{self.agent_name}] Task {task_id}: {message}")
        else:
            self.logger.debug(f"[{self.agent_name}] {message}")