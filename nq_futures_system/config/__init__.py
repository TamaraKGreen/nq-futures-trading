"""
Configuration Module

Central configuration management with validation and fail-fast support.

Components:
- settings: Configuration dataclasses and validation functions
"""

from .settings import get_config, ConfigManager

__all__ = [
    "get_config",
    "ConfigManager",
]