"""
Configuration Management for NQ Futures Trading System

Provides centralized configuration with:
- Environment-specific settings
- Cache configuration
- API limits and costs
- Trading parameters
- Performance tuning
"""

import os
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import logging

# Import typed exceptions for fail-fast support
from nq_futures_system.utils.validators import ValidationError, ConfigurationError

logger = logging.getLogger(__name__)


@dataclass
class CacheSettings:
    """Cache-related configuration."""
    cache_dir: str = "data/cache"
    default_compression: str = "snappy"
    max_cache_size_mb: float = 5000.0  # 5GB default
    cleanup_age_days: int = 90
    enable_daily_cleanup: bool = True
    buffer_size: int = 100000
    batch_size_days: int = 30


@dataclass 
class APISettings:
    """Databento API configuration."""
    base_url: str = "https://hist.databento.com"
    timeout_seconds: int = 120
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    rate_limit_calls_per_minute: int = 100
    
    # Cost estimates (USD)
    cost_per_trade_day: float = 0.20
    cost_per_ohlcv_day: float = 0.02
    cost_per_bbo_day: float = 0.15
    monthly_budget_usd: float = 100.0


@dataclass
class TradingSettings:
    """Trading-specific configuration."""
    default_symbols: list = None
    default_schemas: list = None
    trading_hours_start: str = "09:30"  # EST
    trading_hours_end: str = "16:00"    # EST
    timezone: str = "America/New_York"
    
    # Live data settings
    live_buffer_seconds: int = 3600     # 1 hour
    live_cutoff_hours: int = 1          # Switch to live data after 1 hour
    heartbeat_interval_seconds: int = 30
    
    # Schema definitions for centralized access
    schema_definitions: dict = None
    valid_schemas: list = None
    
    def __post_init__(self):
        if self.default_symbols is None:
            self.default_symbols = ["NQZ4", "NQH5"]
        if self.default_schemas is None:
            self.default_schemas = ["trades", "ohlcv-1m"]
        
        # Central schema definitions with metadata
        if self.schema_definitions is None:
            self.schema_definitions = {
                "trades": {
                    "description": "Individual trade records",
                    "required_columns": ["ts_event", "ts_recv", "price", "size"],
                    "cost_multiplier": 1.0,
                    "typical_size": "large",
                    "frequency": "tick-by-tick"
                },
                "ohlcv-1m": {
                    "description": "1-minute OHLCV candlestick bars",
                    "required_columns": ["ts_event", "open", "high", "low", "close", "volume"],
                    "cost_multiplier": 0.1,
                    "typical_size": "small",
                    "frequency": "1-minute"
                },
                "ohlcv-1h": {
                    "description": "1-hour OHLCV candlestick bars",
                    "required_columns": ["ts_event", "open", "high", "low", "close", "volume"],
                    "cost_multiplier": 0.02,
                    "typical_size": "very_small",
                    "frequency": "1-hour"
                },
                "tbbo": {
                    "description": "Top of book bid-offer quotes",
                    "required_columns": ["ts_event", "bid_px", "ask_px", "bid_sz", "ask_sz"],
                    "cost_multiplier": 0.8,
                    "typical_size": "medium",
                    "frequency": "tick-by-tick"
                },
                "mbp-1": {
                    "description": "Market by price (Level 1)",
                    "required_columns": ["ts_event", "price", "size", "side"],
                    "cost_multiplier": 0.6,
                    "typical_size": "medium",
                    "frequency": "tick-by-tick"
                }
            }
            
        # Valid schemas list for validation
        if self.valid_schemas is None:
            self.valid_schemas = list(self.schema_definitions.keys())


@dataclass
class LoggingSettings:
    """Logging configuration."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: str = "logs/trading_system.log"
    max_file_size_mb: int = 50
    backup_count: int = 5
    enable_console: bool = True


@dataclass
class PerformanceSettings:
    """Performance tuning configuration."""
    max_concurrent_requests: int = 5
    chunk_size_rows: int = 50000
    memory_limit_mb: int = 2000
    enable_multiprocessing: bool = True
    worker_processes: int = 4


@dataclass
class FailFastSettings:
    """
    Fail-fast behavior configuration for robust trading system operation.
    
    When enabled, the system will fail immediately and loudly on any issues
    rather than falling back to potentially stale data or continuing with
    degraded functionality. This ensures trading decisions are made only
    with reliable, real-time data.
    """
    enable_fail_fast: bool = False           # Main fail-fast mode toggle
    disable_auto_reconnect: bool = False     # Disable automatic reconnection
    strict_error_handling: bool = False      # Replace warnings with errors
    immediate_failure_timeout: int = 5       # Seconds before considering failure
    max_retry_attempts: int = 0              # No retries in strict fail-fast mode
    fail_on_stale_data: bool = False         # Fail if data is older than threshold
    stale_data_threshold_seconds: int = 60   # Data freshness threshold
    require_live_feed_validation: bool = False  # Validate live feeds before trading


class ConfigManager:
    """Manages system configuration with environment overrides."""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_file: Path to JSON config file (optional)
        """
        self.config_file = config_file
        self.config = self._load_config()
        
        # Initialize component settings
        self.cache = CacheSettings(**self.config.get('cache', {}))
        self.api = APISettings(**self.config.get('api', {}))
        self.trading = TradingSettings(**self.config.get('trading', {}))
        self.logging = LoggingSettings(**self.config.get('logging', {}))
        self.performance = PerformanceSettings(**self.config.get('performance', {}))
        self.fail_fast = FailFastSettings(**self.config.get('fail_fast', {}))
        
        # Apply environment overrides
        self._apply_env_overrides()
        
        logger.info("Configuration loaded successfully")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or use defaults."""
        if self.config_file and Path(self.config_file).exists():
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                logger.info(f"Loaded configuration from {self.config_file}")
                return config
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load config file {self.config_file}: {e}")
        
        # Return empty dict to use defaults
        return {}
    
    def _apply_env_overrides(self):
        """Apply environment variable overrides."""
        
        # API settings from environment
        if os.getenv('DATABENTO_API_KEY'):
            self.api.api_key = os.getenv('DATABENTO_API_KEY')
        
        if os.getenv('DATABENTO_TIMEOUT'):
            try:
                self.api.timeout_seconds = int(os.getenv('DATABENTO_TIMEOUT'))
            except ValueError:
                pass
        
        # Cache settings from environment
        if os.getenv('CACHE_DIR'):
            self.cache.cache_dir = os.getenv('CACHE_DIR')
        
        if os.getenv('CACHE_SIZE_MB'):
            try:
                self.cache.max_cache_size_mb = float(os.getenv('CACHE_SIZE_MB'))
            except ValueError:
                pass
        
        # Trading settings from environment
        if os.getenv('DEFAULT_SYMBOLS'):
            self.trading.default_symbols = os.getenv('DEFAULT_SYMBOLS').split(',')
        
        if os.getenv('DEFAULT_SCHEMAS'):
            self.trading.default_schemas = os.getenv('DEFAULT_SCHEMAS').split(',')
        
        # Logging settings from environment
        if os.getenv('LOG_LEVEL'):
            self.logging.level = os.getenv('LOG_LEVEL').upper()
        
        if os.getenv('LOG_FILE'):
            self.logging.file_path = os.getenv('LOG_FILE')
        
        # Fail-fast settings from environment
        if os.getenv('ENABLE_FAIL_FAST'):
            self.fail_fast.enable_fail_fast = os.getenv('ENABLE_FAIL_FAST').lower() == 'true'
        
        if os.getenv('DISABLE_AUTO_RECONNECT'):
            self.fail_fast.disable_auto_reconnect = os.getenv('DISABLE_AUTO_RECONNECT').lower() == 'true'
        
        if os.getenv('STRICT_ERROR_HANDLING'):
            self.fail_fast.strict_error_handling = os.getenv('STRICT_ERROR_HANDLING').lower() == 'true'
        
        if os.getenv('IMMEDIATE_FAILURE_TIMEOUT'):
            try:
                self.fail_fast.immediate_failure_timeout = int(os.getenv('IMMEDIATE_FAILURE_TIMEOUT'))
            except ValueError:
                pass
    
    def save_config(self, output_file: str):
        """
        Save current configuration to file.
        
        Args:
            output_file: Path to save configuration
        """
        config_dict = {
            'cache': asdict(self.cache),
            'api': asdict(self.api),
            'trading': asdict(self.trading),
            'logging': asdict(self.logging),
            'performance': asdict(self.performance),
            'fail_fast': asdict(self.fail_fast)
        }
        
        # Remove sensitive data
        if 'api_key' in config_dict['api']:
            config_dict['api']['api_key'] = '***REDACTED***'
        
        try:
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, 'w') as f:
                json.dump(config_dict, f, indent=2)
            logger.info(f"Configuration saved to {output_file}")
        except IOError as e:
            logger.error(f"Failed to save configuration: {e}")
    
    def get_cache_config(self) -> Dict[str, Any]:
        """Get cache configuration as dictionary."""
        return asdict(self.cache)
    
    def get_api_config(self) -> Dict[str, Any]:
        """Get API configuration as dictionary."""
        config = asdict(self.api)
        # Add API key from environment
        config['api_key'] = os.getenv('DATABENTO_API_KEY')
        return config
    
    def get_trading_config(self) -> Dict[str, Any]:
        """Get trading configuration as dictionary."""
        return asdict(self.trading)
    
    def update_cache_settings(self, **kwargs):
        """Update cache settings dynamically."""
        for key, value in kwargs.items():
            if hasattr(self.cache, key):
                setattr(self.cache, key, value)
                logger.info(f"Updated cache.{key} = {value}")
    
    def update_api_settings(self, **kwargs):
        """Update API settings dynamically."""
        for key, value in kwargs.items():
            if hasattr(self.api, key):
                setattr(self.api, key, value)
                logger.info(f"Updated api.{key} = {value}")
    
    def validate_config(self) -> Dict[str, Any]:
        """
        Validate configuration and return any issues.
        
        Returns:
            Dictionary with validation results
        """
        issues = []
        warnings = []
        
        # Check required environment variables
        if not os.getenv('DATABENTO_API_KEY'):
            error_msg = "DATABENTO_API_KEY environment variable not set"
            if self.fail_fast.enable_fail_fast:
                raise ConfigurationError(f"FAIL-FAST: {error_msg}")
            else:
                issues.append(error_msg)
        
        # Validate cache directory
        cache_dir = Path(self.cache.cache_dir)
        if not cache_dir.exists():
            try:
                cache_dir.mkdir(parents=True, exist_ok=True)
                warnings.append(f"Created cache directory: {cache_dir}")
            except OSError:
                issues.append(f"Cannot create cache directory: {cache_dir}")
        
        # Validate cache size
        if self.cache.max_cache_size_mb < 100:
            warnings.append("Cache size is very small (< 100MB)")
        elif self.cache.max_cache_size_mb > 10000:
            warnings.append("Cache size is very large (> 10GB)")
        
        # Validate API settings
        if self.api.timeout_seconds < 30:
            warnings.append("API timeout is very short (< 30s)")
        
        if self.api.monthly_budget_usd < 10:
            warnings.append("Monthly budget is very low (< $10)")
        
        # Validate trading settings
        if len(self.trading.default_symbols) == 0:
            issues.append("No default symbols configured")
        
        if len(self.trading.default_schemas) == 0:
            issues.append("No default schemas configured")
        
        # Validate logging settings
        log_dir = Path(self.logging.file_path).parent
        if not log_dir.exists():
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
                warnings.append(f"Created log directory: {log_dir}")
            except OSError:
                issues.append(f"Cannot create log directory: {log_dir}")
        
        # Validate fail-fast settings consistency
        if self.fail_fast.enable_fail_fast:
            if not self.fail_fast.strict_error_handling:
                warnings.append("Fail-fast mode enabled but strict error handling is disabled")
            
            if not self.fail_fast.disable_auto_reconnect:
                warnings.append("Fail-fast mode enabled but auto-reconnect is still enabled")
            
            if self.fail_fast.max_retry_attempts > 0:
                warnings.append("Fail-fast mode enabled but retry attempts > 0")
            
            if self.api.max_retries > 0:
                warnings.append("Fail-fast mode enabled but API max_retries > 0")
            
            if self.fail_fast.immediate_failure_timeout > 30:
                warnings.append("Immediate failure timeout is very high (> 30s)")
            
            if self.fail_fast.require_live_feed_validation:
                warnings.append("Live feed validation required - ensure live data license is active")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings
        }
    
    def print_config_summary(self):
        """Print a formatted configuration summary."""
        print("\n" + "="*60)
        print("⚙️  SYSTEM CONFIGURATION SUMMARY")
        print("="*60)
        
        print(f"\n📁 CACHE SETTINGS:")
        print(f"   Directory:           {self.cache.cache_dir}")
        print(f"   Max size:            {self.cache.max_cache_size_mb:.0f} MB")
        print(f"   Cleanup age:         {self.cache.cleanup_age_days} days")
        print(f"   Compression:         {self.cache.default_compression}")
        
        print(f"\n🌐 API SETTINGS:")
        print(f"   Base URL:            {self.api.base_url}")
        print(f"   Timeout:             {self.api.timeout_seconds}s")
        print(f"   Rate limit:          {self.api.rate_limit_calls_per_minute}/min")
        print(f"   Monthly budget:      ${self.api.monthly_budget_usd:.2f}")
        
        print(f"\n📈 TRADING SETTINGS:")
        print(f"   Default symbols:     {', '.join(self.trading.default_symbols)}")
        print(f"   Default schemas:     {', '.join(self.trading.default_schemas)}")
        print(f"   Trading hours:       {self.trading.trading_hours_start} - {self.trading.trading_hours_end}")
        print(f"   Live buffer:         {self.trading.live_buffer_seconds}s")
        
        print(f"\n📝 LOGGING SETTINGS:")
        print(f"   Level:               {self.logging.level}")
        print(f"   File:                {self.logging.file_path}")
        print(f"   Console enabled:     {self.logging.enable_console}")
        
        print(f"\n⚡ PERFORMANCE SETTINGS:")
        print(f"   Max concurrent:      {self.performance.max_concurrent_requests}")
        print(f"   Memory limit:        {self.performance.memory_limit_mb} MB")
        print(f"   Multiprocessing:     {self.performance.enable_multiprocessing}")
        
        print(f"\n🛡️  FAIL-FAST SETTINGS:")
        status_icon = "🟢" if self.fail_fast.enable_fail_fast else "🔴"
        print(f"   Fail-fast mode:      {status_icon} {'Enabled' if self.fail_fast.enable_fail_fast else 'Disabled'}")
        print(f"   Strict errors:       {'Yes' if self.fail_fast.strict_error_handling else 'No'}")
        print(f"   Auto-reconnect:      {'Disabled' if self.fail_fast.disable_auto_reconnect else 'Enabled'}")
        print(f"   Failure timeout:     {self.fail_fast.immediate_failure_timeout}s")
        print(f"   Max retries:         {self.fail_fast.max_retry_attempts}")
        print(f"   Live feed validation: {'Required' if self.fail_fast.require_live_feed_validation else 'Optional'}")


# Global configuration instance
_config_manager = None

def get_config(config_file: Optional[str] = None) -> ConfigManager:
    """
    Get global configuration manager instance.
    
    Args:
        config_file: Path to config file (only used on first call)
        
    Returns:
        ConfigManager instance
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_file)
    return _config_manager


def load_config_from_file(config_file: str) -> ConfigManager:
    """
    Load configuration from specific file.
    
    Args:
        config_file: Path to configuration file
        
    Returns:
        ConfigManager instance
    """
    return ConfigManager(config_file)


if __name__ == '__main__':
    # Demo configuration usage
    config = get_config()
    
    # Print summary
    config.print_config_summary()
    
    # Validate configuration
    validation = config.validate_config()
    
    print(f"\n✅ CONFIGURATION VALIDATION:")
    print(f"   Valid: {validation['valid']}")
    if validation['issues']:
        print(f"   Issues: {len(validation['issues'])}")
        for issue in validation['issues']:
            print(f"     - {issue}")
    if validation['warnings']:
        print(f"   Warnings: {len(validation['warnings'])}")
        for warning in validation['warnings']:
            print(f"     - {warning}")