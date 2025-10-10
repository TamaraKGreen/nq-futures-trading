"""
Utilities Module

Common utilities, validators, and helper functions.

Components:
- validators: Central validation functions with fail-fast support
- gap_detector: Data gap detection and analysis
- cache_cleanup: Cache maintenance and cleanup utilities
"""

from .validators import (
    ValidationError, DataQualityError, APIValidationError, InputValidationError,
    validate_api_response, validate_dataframe_structure, validate_symbol_format,
    validate_datetime_range, validate_schema_format, validate_environment,
    validate_data_freshness, validate_connection_health, StrictModeEnforcer
)
from .gap_detector import GapDetector
from .cache_cleanup import CacheCleanupManager

__all__ = [
    # Validation exceptions
    "ValidationError",
    "DataQualityError", 
    "APIValidationError",
    "InputValidationError",
    
    # Validation functions
    "validate_api_response",
    "validate_dataframe_structure",
    "validate_symbol_format", 
    "validate_datetime_range",
    "validate_schema_format",
    "validate_environment",
    "validate_data_freshness",
    "validate_connection_health",
    "StrictModeEnforcer",
    
    # Other utilities
    "GapDetector",
    "CacheCleanupManager",
]