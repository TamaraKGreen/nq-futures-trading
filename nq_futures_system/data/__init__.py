"""
Data Management Module

Comprehensive data collection, caching, and coordination for NQ futures trading.

Components:
- collectors: Data retrieval from external APIs (Databento)  
- cache: Intelligent caching system with incremental updates
- live: Real-time data streaming and buffering
- unified_data_coordinator: Central coordination between historical and live data

Key Features:
- Automatic cache management
- Seamless live/historical data integration
- Cost-optimized API usage
- Performance monitoring
"""

from .unified_data_coordinator import UnifiedDataCoordinator, create_coordinator
from .collectors.databento_client import DatabentoClient
from .collectors.cached_databento_client import CachedDatabentoClient, create_cached_client

__all__ = [
    "UnifiedDataCoordinator",
    "create_coordinator", 
    "DatabentoClient",
    "CachedDatabentoClient",
    "create_cached_client",
]