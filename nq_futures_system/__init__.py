"""
NQ Futures Trading System

A comprehensive, production-ready trading system for NQ futures with
automated data management, caching, monitoring, and fail-fast validation.

Key Features:
- Centralized configuration management
- Intelligent caching with automatic refresh
- Real-time and historical data integration
- Comprehensive validation and error handling
- Performance monitoring and cost tracking
- Fail-fast operational safety

Usage:
    from nq_futures_system import TradingSystem
    from nq_futures_system.config.settings import get_config
    
    # Initialize system
    system = TradingSystem()
    
    # Get data
    data = system.get_data("NQZ4", start_date, end_date, "ohlcv-1m")
"""

__version__ = "1.0.0"
__author__ = "NQ Futures Trading Team"

# Core exports for easy access
from .production_system import TradingSystem
from .config.settings import get_config

__all__ = [
    "TradingSystem",
    "get_config",
    "__version__",
    "__author__",
]