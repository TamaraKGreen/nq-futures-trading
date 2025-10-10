"""
Validation Utilities for Fail-Fast Trading System

Provides comprehensive validation functions and strict mode enforcement
to ensure the trading system fails fast, loud, and safe on any data
quality issues, API problems, or configuration errors.

Key Features:
- API response validation
- DataFrame structure validation  
- Input parameter validation
- StrictModeEnforcer for runtime checks
- Immediate failure on validation errors
"""

import re
import os
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
import logging

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when validation fails in strict mode."""
    pass


class DataQualityError(ValidationError):
    """Raised when data quality validation fails."""
    pass


class APIValidationError(ValidationError):
    """Raised when API response validation fails."""
    pass


class InputValidationError(ValidationError):
    """Raised when input parameter validation fails."""
    pass


class ConfigurationError(ValidationError):
    """
    Raised when configuration validation fails.
    
    This exception indicates problems with system configuration such as:
    - Invalid configuration values
    - Missing required configuration settings
    - Configuration conflicts or incompatibilities
    - Environment variable issues
    """
    pass


class ConnectionError(ValidationError):
    """
    Raised when connection or network-related operations fail.
    
    This exception indicates problems with external connections such as:
    - API connectivity issues
    - Network timeouts
    - Authentication failures with external services
    - Service unavailability
    """
    pass


class CacheError(ValidationError):
    """
    Raised when cache operations fail.
    
    This exception indicates problems with caching operations such as:
    - Cache storage/retrieval failures
    - Cache corruption or integrity issues
    - Disk space or permission problems
    - Cache format or serialization errors
    """
    pass


def validate_api_response(response_data: Any, expected_type: type = pd.DataFrame) -> bool:
    """
    Validate API response data structure and content.
    
    Args:
        response_data: Data returned from API
        expected_type: Expected type of the response
        
    Returns:
        True if valid
        
    Raises:
        APIValidationError: If validation fails
    """
    if response_data is None:
        raise APIValidationError("API response is None")
    
    if not isinstance(response_data, expected_type):
        raise APIValidationError(
            f"API response type {type(response_data)} does not match expected type {expected_type}"
        )
    
    if isinstance(response_data, pd.DataFrame):
        if response_data.empty:
            raise APIValidationError("API response DataFrame is empty")
        
        # Check for required columns in market data
        required_columns = {'ts_event', 'ts_recv'}  # Basic timestamp columns
        missing_columns = required_columns - set(response_data.columns)
        if missing_columns:
            raise APIValidationError(
                f"API response missing required columns: {missing_columns}"
            )
        
        # Check for NaN values in critical columns
        critical_columns = ['ts_event', 'ts_recv']
        for col in critical_columns:
            if col in response_data.columns and response_data[col].isna().any():
                raise APIValidationError(f"API response has NaN values in critical column: {col}")
    
    logger.debug(f"API response validation passed: {type(response_data)}")
    return True


def validate_dataframe_structure(df: pd.DataFrame, schema: str = "trades") -> bool:
    """
    Validate DataFrame structure matches expected schema.
    
    Args:
        df: DataFrame to validate
        schema: Expected data schema
        
    Returns:
        True if valid
        
    Raises:
        DataQualityError: If validation fails
    """
    if df is None or df.empty:
        raise DataQualityError("DataFrame is None or empty")
    
    # Get schema requirements from canonical configuration
    from nq_futures_system.config.settings import get_config
    config = get_config()
    schema_requirements = config.trading.get_schema_validator_rules
    
    if schema in schema_requirements:
        required_columns = schema_requirements[schema]
        missing_columns = set(required_columns) - set(df.columns)
        if missing_columns:
            raise DataQualityError(
                f"DataFrame missing required columns for {schema}: {missing_columns}"
            )
    
    # Data quality checks
    if df.index.duplicated().any():
        raise DataQualityError("DataFrame has duplicate index values")
    
    # Check for completely empty rows
    if (df.isna().all(axis=1)).any():
        raise DataQualityError("DataFrame contains completely empty rows")
    
    # Validate timestamp columns
    timestamp_columns = ['ts_event', 'ts_recv']
    for col in timestamp_columns:
        if col in df.columns:
            if not pd.api.types.is_datetime64_any_dtype(df[col]):
                try:
                    pd.to_datetime(df[col])
                except:
                    raise DataQualityError(f"Column {col} is not a valid timestamp")
    
    # Validate numeric columns
    numeric_columns = ['price', 'open', 'high', 'low', 'close', 'volume', 'size']
    for col in numeric_columns:
        if col in df.columns:
            if not pd.api.types.is_numeric_dtype(df[col]):
                raise DataQualityError(f"Column {col} is not numeric")
            
            # Check for negative prices (should not exist)
            if col in ['price', 'open', 'high', 'low', 'close'] and (df[col] < 0).any():
                raise DataQualityError(f"Negative values found in price column: {col}")
    
    logger.debug(f"DataFrame structure validation passed: {schema}, {len(df)} rows")
    return True


def validate_symbol_format(symbol: str) -> bool:
    """
    Validate trading symbol format.
    
    Args:
        symbol: Trading symbol to validate
        
    Returns:
        True if valid
        
    Raises:
        InputValidationError: If validation fails
    """
    if not symbol or not isinstance(symbol, str):
        raise InputValidationError("Symbol must be a non-empty string")
    
    symbol = symbol.strip().upper()
    
    # Basic symbol format validation
    if len(symbol) < 2 or len(symbol) > 10:
        raise InputValidationError(f"Symbol length must be 2-10 characters: {symbol}")
    
    # Check for valid characters (letters and numbers only)
    if not re.match(r'^[A-Z0-9]+$', symbol):
        raise InputValidationError(f"Symbol contains invalid characters: {symbol}")
    
    # NQ futures specific validation
    if symbol.startswith('NQ'):
        if len(symbol) < 3:
            raise InputValidationError(f"NQ symbol too short: {symbol}")
        
        # Check for valid NQ contract format (e.g., NQZ4, NQH5)
        if len(symbol) >= 4:
            month_code = symbol[2]
            if month_code not in 'FGHJKMNQUVXZ':
                raise InputValidationError(f"Invalid futures month code: {month_code}")
    
    logger.debug(f"Symbol validation passed: {symbol}")
    return True


def validate_datetime_range(start: datetime, end: datetime, max_range_days: int = 365) -> bool:
    """
    Validate datetime range for data requests.
    
    Args:
        start: Start datetime
        end: End datetime
        max_range_days: Maximum allowed range in days
        
    Returns:
        True if valid
        
    Raises:
        InputValidationError: If validation fails
    """
    if not isinstance(start, datetime) or not isinstance(end, datetime):
        raise InputValidationError("Start and end must be datetime objects")
    
    if start >= end:
        raise InputValidationError(f"Start time {start} must be before end time {end}")
    
    # Check range is not too large
    range_days = (end - start).days
    if range_days > max_range_days:
        raise InputValidationError(
            f"Date range too large: {range_days} days (max: {max_range_days})"
        )
    
    # Check dates are not too far in the future
    now = datetime.now()
    if start > now + timedelta(days=1):
        raise InputValidationError(f"Start time is too far in the future: {start}")
    
    # Check dates are not too far in the past (basic sanity check)
    min_date = datetime(2020, 1, 1)  # Reasonable minimum for market data
    if start < min_date:
        raise InputValidationError(f"Start time is too far in the past: {start}")
    
    logger.debug(f"Datetime range validation passed: {start} to {end}")
    return True


def validate_schema_format(schema: str) -> bool:
    """
    Validate data schema format.
    
    Args:
        schema: Data schema to validate
        
    Returns:
        True if valid
        
    Raises:
        InputValidationError: If validation fails
    """
    if not schema or not isinstance(schema, str):
        raise InputValidationError("Schema must be a non-empty string")
    
    schema = schema.strip().lower()
    
    # Get valid schemas from canonical configuration
    from nq_futures_system.config.settings import get_config
    config = get_config()
    valid_schemas = set(config.trading.valid_schemas)
    
    if schema not in valid_schemas:
        raise InputValidationError(f"Invalid schema: {schema}. Valid schemas: {valid_schemas}")
    
    logger.debug(f"Schema validation passed: {schema}")
    return True


class StrictModeEnforcer:
    """
    Enforces strict validation and fail-fast behavior throughout the system.
    
    This class provides centralized enforcement of fail-fast policies,
    ensuring that any data quality issues, API problems, or configuration
    errors cause immediate system failure rather than silent degradation.
    """
    
    def __init__(self, config):
        """
        Initialize strict mode enforcer.
        
        Args:
            config: Configuration manager with fail_fast settings
        """
        self.config = config
        self.strict_mode = config.fail_fast.enable_fail_fast
        self.strict_errors = config.fail_fast.strict_error_handling
        self.fail_timeout = config.fail_fast.immediate_failure_timeout
        
        logger.info(f"StrictModeEnforcer initialized: strict_mode={self.strict_mode}")
    
    def enforce_data_quality(self, data: pd.DataFrame, schema: str, 
                           source: str = "unknown") -> pd.DataFrame:
        """
        Enforce data quality standards.
        
        Args:
            data: DataFrame to validate
            schema: Expected data schema
            source: Data source for error reporting
            
        Returns:
            Validated DataFrame
            
        Raises:
            DataQualityError: If validation fails in strict mode
        """
        if not self.strict_mode:
            return data  # Pass through in non-strict mode
        
        try:
            # Validate DataFrame structure
            validate_dataframe_structure(data, schema)
            
            # Additional strict checks
            if len(data) == 0:
                raise DataQualityError(f"Empty dataset from {source}")
            
            # Check data freshness for real-time schemas
            if schema in ['trades', 'bbo', 'mbp-1'] and 'ts_event' in data.columns:
                latest_timestamp = pd.to_datetime(data['ts_event']).max()
                age_seconds = (datetime.now() - latest_timestamp.to_pydatetime()).total_seconds()
                
                if age_seconds > self.config.fail_fast.stale_data_threshold_seconds:
                    if self.config.fail_fast.fail_on_stale_data:
                        raise DataQualityError(
                            f"Stale data detected: {age_seconds:.1f}s old (max: {self.config.fail_fast.stale_data_threshold_seconds}s)"
                        )
            
            logger.debug(f"Data quality enforcement passed: {source}, {len(data)} rows")
            return data
            
        except Exception as e:
            if self.strict_errors:
                logger.error(f"STRICT MODE: Data quality failure from {source}: {e}")
                raise DataQualityError(f"Data quality failure from {source}: {e}")
            else:
                logger.warning(f"Data quality warning from {source}: {e}")
                return data
    
    def enforce_api_validation(self, response: Any, endpoint: str = "unknown") -> Any:
        """
        Enforce API response validation.
        
        Args:
            response: API response to validate
            endpoint: API endpoint for error reporting
            
        Returns:
            Validated response
            
        Raises:
            APIValidationError: If validation fails in strict mode
        """
        if not self.strict_mode:
            return response  # Pass through in non-strict mode
        
        try:
            validate_api_response(response)
            
            logger.debug(f"API validation enforcement passed: {endpoint}")
            return response
            
        except Exception as e:
            if self.strict_errors:
                logger.error(f"STRICT MODE: API validation failure from {endpoint}: {e}")
                raise APIValidationError(f"API validation failure from {endpoint}: {e}")
            else:
                logger.warning(f"API validation warning from {endpoint}: {e}")
                return response
    
    def enforce_input_validation(self, **kwargs) -> Dict[str, Any]:
        """
        Enforce input parameter validation.
        
        Args:
            **kwargs: Input parameters to validate
            
        Returns:
            Validated parameters
            
        Raises:
            InputValidationError: If validation fails in strict mode
        """
        if not self.strict_mode:
            return kwargs  # Pass through in non-strict mode
        
        try:
            validated_params = {}
            
            # Validate each parameter type
            for key, value in kwargs.items():
                if key == 'symbol' and value is not None:
                    if isinstance(value, list):
                        for symbol in value:
                            validate_symbol_format(symbol)
                    else:
                        validate_symbol_format(value)
                
                elif key == 'schema' and value is not None:
                    validate_schema_format(value)
                
                elif key in ['start', 'end'] and value is not None:
                    if not isinstance(value, datetime):
                        raise InputValidationError(f"{key} must be a datetime object")
                
                # Additional parameter validation can be added here
                validated_params[key] = value
            
            # Cross-parameter validation
            if 'start' in validated_params and 'end' in validated_params:
                if validated_params['start'] and validated_params['end']:
                    validate_datetime_range(validated_params['start'], validated_params['end'])
            
            logger.debug(f"Input validation enforcement passed: {list(kwargs.keys())}")
            return validated_params
            
        except Exception as e:
            if self.strict_errors:
                logger.error(f"STRICT MODE: Input validation failure: {e}")
                raise InputValidationError(f"Input validation failure: {e}")
            else:
                logger.warning(f"Input validation warning: {e}")
                return kwargs
    
    def should_fail_fast(self, error: Exception) -> bool:
        """
        Determine if an error should trigger immediate system failure.
        
        Args:
            error: Exception to evaluate
            
        Returns:
            True if system should fail immediately
        """
        if not self.strict_mode:
            return False
        
        # Critical errors that should always trigger fail-fast
        critical_error_types = [
            ConnectionError,
            AuthenticationError,
            DataQualityError,
            APIValidationError,
            ConfigurationError,
            CacheError
        ]
        
        return any(isinstance(error, error_type) for error_type in critical_error_types)
    
    def validate_system_preconditions(self) -> bool:
        """
        Validate system preconditions for fail-fast operation.
        
        Returns:
            True if all preconditions are met
            
        Raises:
            ValidationError: If preconditions are not met in strict mode
        """
        issues = []
        
        # Check required environment variables
        required_env_vars = ['DATABENTO_API_KEY']
        for var in required_env_vars:
            if not os.getenv(var):
                issues.append(f"Required environment variable not set: {var}")
        
        # Check configuration consistency
        if self.config.fail_fast.enable_fail_fast:
            if not self.config.fail_fast.disable_auto_reconnect:
                issues.append("Fail-fast enabled but auto-reconnect is not disabled")
            
            if self.config.api.max_retries > 0:
                issues.append("Fail-fast enabled but API max_retries > 0")
        
        if issues:
            error_msg = "System precondition failures: " + "; ".join(issues)
            if self.strict_mode:
                raise ValidationError(error_msg)
            else:
                logger.warning(error_msg)
                return False
        
        logger.info("System preconditions validated successfully")
        return True


# Authentication error class for clarity
class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


def validate_trading_session() -> bool:
    """
    Validate that we're in a valid trading session.
    
    Returns:
        True if valid trading session
        
    Raises:
        ValidationError: If outside trading hours in strict mode
    """
    # This is a simplified check - real implementation would check market calendar
    now = datetime.now()
    
    # Basic trading hours check (9:30 AM to 4:00 PM ET, Monday-Friday)
    if now.weekday() >= 5:  # Weekend
        raise ValidationError("Trading attempted outside market hours (weekend)")
    
    # Additional trading hours validation could be added here
    return True


def validate_environment() -> Dict[str, Any]:
    """
    Validate complete environment setup and dependencies.
    
    Returns:
        Dictionary with validation results including:
        - valid: bool - Overall validation status
        - issues: list - List of critical issues
        - warnings: list - List of warnings
        - checks: dict - Detailed check results
        
    Raises:
        ValidationError: If environment is invalid and fail-fast mode enabled
    """
    from nq_futures_system.config.settings import get_config
    
    config = get_config()
    
    # Use the central config validation which now includes API key check
    validation_result = config.validate_config()
    
    issues = list(validation_result.get('issues', []))
    warnings = list(validation_result.get('warnings', []))
    checks = {}
    
    # Add additional environment checks
    import sys
    import platform
    
    # Python version check
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    checks['python_version'] = python_version
    
    if sys.version_info < (3, 8):
        issues.append(f"Python version {python_version} < 3.8 (minimum required)")
    
    # Platform check
    checks['platform'] = platform.system()
    checks['architecture'] = platform.machine()
    
    # Required packages check
    required_packages = ['pandas', 'numpy', 'asyncio', 'logging']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            checks[f'package_{package}'] = 'available'
        except ImportError:
            missing_packages.append(package)
            checks[f'package_{package}'] = 'missing'
    
    if missing_packages:
        issues.append(f"Missing required packages: {', '.join(missing_packages)}")
    
    # Check disk space (basic check)
    try:
        import shutil
        cache_dir = config.cache.cache_dir
        _, _, free_bytes = shutil.disk_usage(cache_dir if os.path.exists(cache_dir) else '.')
        free_gb = free_bytes / (1024 ** 3)
        checks['free_disk_space_gb'] = round(free_gb, 2)
        
        if free_gb < 1.0:  # Less than 1GB free
            warnings.append(f"Low disk space: {free_gb:.2f}GB available")
    except Exception as e:
        warnings.append(f"Could not check disk space: {e}")
    
    # Memory check
    try:
        import psutil
        memory = psutil.virtual_memory()
        checks['total_memory_gb'] = round(memory.total / (1024 ** 3), 2)
        checks['available_memory_gb'] = round(memory.available / (1024 ** 3), 2)
        
        if memory.available < config.performance.memory_limit_mb * 1024 * 1024:
            warnings.append(f"Available memory ({memory.available / (1024**3):.2f}GB) less than configured limit ({config.performance.memory_limit_mb}MB)")
    except ImportError:
        warnings.append("psutil not available - cannot check memory usage")
    except Exception as e:
        warnings.append(f"Could not check memory: {e}")
    
    final_result = {
        'valid': len(issues) == 0,
        'issues': issues,
        'warnings': warnings,
        'checks': checks
    }
    
    # If fail-fast is enabled and we have issues, raise an error
    if config.fail_fast.enable_fail_fast and issues:
        error_msg = "Environment validation failed: " + "; ".join(issues)
        raise ValidationError(error_msg)
    
    logger.debug(f"Environment validation completed: {len(issues)} issues, {len(warnings)} warnings")
    return final_result


def validate_data_freshness(data: pd.DataFrame, max_age_seconds: int = 60, 
                            timestamp_column: str = 'ts_event') -> bool:
    """
    Validate that data is fresh enough for trading decisions.
    
    Args:
        data: DataFrame containing timestamped data
        max_age_seconds: Maximum allowed age in seconds
        timestamp_column: Name of the timestamp column to check
        
    Returns:
        True if data is fresh enough
        
    Raises:
        DataQualityError: If data is too stale or invalid
    """
    if data is None or data.empty:
        raise DataQualityError("Cannot validate freshness: data is None or empty")
    
    if timestamp_column not in data.columns:
        raise DataQualityError(f"Timestamp column '{timestamp_column}' not found in data")
    
    try:
        # Convert to datetime if not already
        timestamps = pd.to_datetime(data[timestamp_column])
        
        # Find the latest timestamp
        latest_timestamp = timestamps.max()
        
        # Check if latest_timestamp is NaT (Not a Time)
        if pd.isna(latest_timestamp):
            raise DataQualityError("Latest timestamp is NaT (Not a Time)")
        
        # Calculate age
        current_time = datetime.now()
        
        # Handle timezone-aware timestamps
        if latest_timestamp.tz is not None:
            current_time = current_time.replace(tzinfo=latest_timestamp.tz)
        elif hasattr(latest_timestamp, 'to_pydatetime'):
            latest_timestamp = latest_timestamp.to_pydatetime()
        
        age_seconds = (current_time - latest_timestamp).total_seconds()
        
        # Check if data is too old
        if age_seconds > max_age_seconds:
            raise DataQualityError(
                f"Data is too stale: {age_seconds:.1f}s old (max allowed: {max_age_seconds}s). "
                f"Latest timestamp: {latest_timestamp}"
            )
        
        # Check if data is too far in the future (more than 5 minutes)
        if age_seconds < -300:  # 5 minutes in the future
            raise DataQualityError(
                f"Data timestamp is too far in the future: {-age_seconds:.1f}s ahead. "
                f"Latest timestamp: {latest_timestamp}"
            )
        
        logger.debug(f"Data freshness validation passed: {age_seconds:.1f}s old")
        return True
        
    except Exception as e:
        if isinstance(e, DataQualityError):
            raise
        else:
            raise DataQualityError(f"Error validating data freshness: {e}")


def validate_connection_health(client=None, timeout_seconds: int = 10) -> Dict[str, Any]:
    """
    Validate connection health to external services (specifically Databento API).
    
    Args:
        client: Client object to test (optional, will create if None)
        timeout_seconds: Maximum time to wait for connection test
        
    Returns:
        Dictionary with connection health results:
        - healthy: bool - Overall connection health
        - response_time_ms: float - Connection response time
        - api_accessible: bool - Whether API is accessible
        - auth_valid: bool - Whether authentication is valid
        - issues: list - List of connection issues
        
    Raises:
        ConnectionError: If connection is critically unhealthy and fail-fast enabled
    """
    from nq_futures_system.config.settings import get_config
    import time
    import asyncio
    
    config = get_config()
    result = {
        'healthy': True,
        'response_time_ms': 0.0,
        'api_accessible': False,
        'auth_valid': False,
        'issues': [],
        'checks': {}
    }
    
    try:
        # If no client provided, try to create one for testing
        if client is None:
            try:
                from data.collectors.databento_client import DatabentoClient
                api_key = os.getenv('DATABENTO_API_KEY')
                if not api_key:
                    result['healthy'] = False
                    result['issues'].append("No API key available for connection test")
                    if config.fail_fast.enable_fail_fast:
                        raise ConnectionError("Cannot test connection: No API key available")
                    return result
                
                client = DatabentoClient(api_key)
            except ImportError as e:
                result['healthy'] = False
                result['issues'].append(f"Cannot import Databento client: {e}")
                result['checks']['client_import'] = 'failed'
                if config.fail_fast.enable_fail_fast:
                    raise ConnectionError(f"Cannot test connection: {e}")
                return result
            except Exception as e:
                result['healthy'] = False
                result['issues'].append(f"Cannot create Databento client: {e}")
                result['checks']['client_creation'] = 'failed'
                if config.fail_fast.enable_fail_fast:
                    raise ConnectionError(f"Cannot create client: {e}")
                return result
        
        # Test basic connectivity
        start_time = time.time()
        
        try:
            # Try to make a simple API call to test connectivity and auth
            # This is a minimal call that should work if everything is set up correctly
            if hasattr(client, 'get_schema'):
                # Test getting schema information (lightweight call)
                schema_info = client.get_schema()
                result['api_accessible'] = True
                result['auth_valid'] = True
                result['checks']['schema_access'] = 'success'
            elif hasattr(client, 'list_symbols'):
                # Alternative: try to list symbols
                symbols = client.list_symbols(limit=1)
                result['api_accessible'] = True
                result['auth_valid'] = True
                result['checks']['symbols_access'] = 'success'
            elif hasattr(client, '_client'):
                # For wrapped clients, test the underlying client
                # This is a basic connectivity test
                result['api_accessible'] = True
                result['auth_valid'] = True
                result['checks']['client_available'] = 'success'
            else:
                # Basic check - just verify client object exists
                result['api_accessible'] = True
                result['checks']['client_exists'] = 'success'
                
        except Exception as api_error:
            result['api_accessible'] = False
            result['healthy'] = False
            
            # Try to determine the type of error
            error_str = str(api_error).lower()
            if 'auth' in error_str or 'unauthorized' in error_str or 'invalid key' in error_str:
                result['issues'].append(f"Authentication failed: {api_error}")
                result['checks']['authentication'] = 'failed'
            elif 'timeout' in error_str or 'connection' in error_str:
                result['issues'].append(f"Connection timeout or network issue: {api_error}")
                result['checks']['network'] = 'failed'
            elif 'rate limit' in error_str:
                result['issues'].append(f"API rate limit exceeded: {api_error}")
                result['checks']['rate_limit'] = 'exceeded'
            else:
                result['issues'].append(f"API call failed: {api_error}")
                result['checks']['api_call'] = 'failed'
        
        # Calculate response time
        end_time = time.time()
        result['response_time_ms'] = (end_time - start_time) * 1000
        
        # Check if response time is reasonable
        max_response_time_ms = getattr(config.api, 'max_response_time_ms', 5000)
        if result['response_time_ms'] > max_response_time_ms:
            result['healthy'] = False
            result['issues'].append(f"Slow response time: {result['response_time_ms']:.1f}ms (max: {max_response_time_ms}ms)")
            result['checks']['response_time'] = 'slow'
        else:
            result['checks']['response_time'] = 'acceptable'
        
        # Additional health checks
        if hasattr(client, 'get_stats'):
            try:
                stats = client.get_stats()
                result['checks']['client_stats'] = 'available'
            except:
                result['checks']['client_stats'] = 'unavailable'
        
        # Final health determination
        if result['api_accessible'] and len(result['issues']) == 0:
            result['healthy'] = True
            logger.debug(f"Connection health check passed: {result['response_time_ms']:.1f}ms")
        else:
            result['healthy'] = False
            
        # If fail-fast is enabled and connection is unhealthy, raise error
        if config.fail_fast.enable_fail_fast and not result['healthy']:
            error_msg = f"Connection health check failed: {'; '.join(result['issues'])}"
            raise ConnectionError(error_msg)
        
        return result
        
    except ConnectionError:
        # Re-raise ConnectionError as-is
        raise
    except Exception as e:
        result['healthy'] = False
        result['issues'].append(f"Connection health check error: {e}")
        result['checks']['general_error'] = str(e)
        
        if config.fail_fast.enable_fail_fast:
            raise ConnectionError(f"Connection health check failed: {e}")
        
        logger.warning(f"Connection health check failed: {e}")
        return result


if __name__ == '__main__':
    # Demo validation utilities
    print("VALIDATION UTILITIES DEMONSTRATION")
    print("="*50)
    
    # Test symbol validation
    try:
        validate_symbol_format("NQZ4")
        print("✅ Symbol validation: NQZ4 is valid")
    except InputValidationError as e:
        print(f"❌ Symbol validation failed: {e}")
    
    # Test datetime validation
    try:
        start = datetime(2024, 8, 1, 14, 0)
        end = datetime(2024, 8, 1, 15, 0)
        validate_datetime_range(start, end)
        print("✅ Datetime validation: Range is valid")
    except InputValidationError as e:
        print(f"❌ Datetime validation failed: {e}")
    
    # Test schema validation
    try:
        validate_schema_format("ohlcv-1m")
        print("✅ Schema validation: ohlcv-1m is valid")
    except InputValidationError as e:
        print(f"❌ Schema validation failed: {e}")
    
    print("\n✅ Validation utilities demonstration complete!")