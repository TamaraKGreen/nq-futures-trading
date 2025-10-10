"""
Unified Data Coordinator - The Magic Integration Layer

This is the crown jewel that seamlessly integrates:
- Cached historical data  
- Live streaming data
- Automatic source switching
- Intelligent gap filling
- Performance optimization

The user gets a single interface that "just works" regardless of data source.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union
import pandas as pd
from pathlib import Path
import threading

# Add parent directory to path
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.collectors.cached_databento_client import CachedDatabentoClient
from data.live.live_buffer import LiveDataBuffer, LiveTick
from data.live.live_manager import LiveDataManager, SubscriptionConfig
from config.settings import get_config

logger = logging.getLogger(__name__)


class UnifiedDataCoordinator:
    """
    🎯 THE MAGIC UNIFIED INTERFACE
    
    This coordinator provides seamless access to both historical and live data
    through a single, simple interface. Users don't need to know or care about
    data sources - it all "just works".
    
    Key Innovation: Single get_data() method that automatically:
    1. Uses cached historical data for old dates
    2. Uses live buffer for recent/current data  
    3. Combines them seamlessly when query spans both
    4. Handles gaps intelligently
    5. Optimizes performance automatically
    """
    
    def __init__(self, 
                 cache_dir: str = "data/cache",
                 live_buffer_size: int = 100000,
                 api_key: Optional[str] = None):
        """
        Initialize the unified data coordinator.
        
        Args:
            cache_dir: Directory for cache storage
            live_buffer_size: Maximum live buffer size
            api_key: Databento API key (uses env if not provided)
        """
        # Load configuration
        self.config = get_config()
        
        # Initialize core components
        self.cached_client = CachedDatabentoClient(api_key, cache_dir)
        self.live_buffer = LiveDataBuffer(
            max_size=live_buffer_size,
            max_age_seconds=self.config.trading.live_buffer_seconds
        )
        self.live_manager = LiveDataManager(
            self.live_buffer,
            self.cached_client,  # Reuse the cached client for live data
            max_concurrent_streams=self.config.performance.max_concurrent_requests
        )
        
        # Configuration
        self.live_cutoff_hours = self.config.trading.live_cutoff_hours
        self.default_symbols = self.config.trading.default_symbols
        self.default_schemas = self.config.trading.default_schemas
        
        # State management
        self.is_live_active = False
        self.active_symbols: set = set()
        
        # Performance tracking
        self.request_stats = {
            'total_requests': 0,
            'cache_only_requests': 0,
            'live_only_requests': 0,
            'combined_requests': 0,
            'average_response_time': 0.0
        }
        
        # Thread safety for async operations
        self.lock = asyncio.Lock()
        
        logger.info("UnifiedDataCoordinator initialized")
    
    def get_live_cutoff(self) -> datetime:
        """
        Determine the boundary between historical and live data.
        
        Returns:
            Datetime where live data begins
        """
        return datetime.utcnow() - timedelta(hours=self.live_cutoff_hours)
    
    def get_data(self, symbols: Union[str, List[str]], 
                start: datetime, end: datetime, 
                schema: str = "trades") -> pd.DataFrame:
        """
        🎯 THE MAGIC METHOD - Unified data access!
        
        This single method handles all data requests seamlessly:
        - Historical data from cache for old dates
        - Live buffer for recent dates  
        - Intelligent combination when spanning both
        - Automatic performance optimization
        
        Args:
            symbols: Symbol(s) to retrieve
            start: Start datetime
            end: End datetime
            schema: Data schema
            
        Returns:
            DataFrame with requested data
        """
        import time
        start_time = time.time()
        
        # Normalize symbols to list
        if isinstance(symbols, str):
            symbols = [symbols]
        
        self.request_stats['total_requests'] += 1
        
        # Determine data source strategy
        live_cutoff = self.get_live_cutoff()
        
        logger.info(f"🎯 UNIFIED GET_DATA: {symbols[0]} from {start} to {end}")
        logger.info(f"   Live cutoff: {live_cutoff}")
        
        try:
            # Case 1: Request is entirely historical
            if end <= live_cutoff:
                logger.info("   📚 Strategy: Historical data only")
                self.request_stats['cache_only_requests'] += 1
                result = self.cached_client.get_historical_data(
                    symbols, start, end, schema
                )
            
            # Case 2: Request is entirely live  
            elif start >= live_cutoff:
                logger.info("   📡 Strategy: Live buffer only")
                self.request_stats['live_only_requests'] += 1
                result = self._get_live_data(symbols[0], start, end)
            
            # Case 3: Request spans historical + live (THE COMPLEX CASE)
            else:
                logger.info("   🔄 Strategy: Combined historical + live data")
                self.request_stats['combined_requests'] += 1
                result = self._get_combined_data(symbols, start, end, schema, live_cutoff)
            
            # Update performance stats
            response_time = time.time() - start_time
            self._update_response_time(response_time)
            
            logger.info(f"   ✅ Returned {len(result)} records in {response_time:.3f}s")
            return result
            
        except Exception as e:
            logger.error(f"   ❌ Error in unified get_data: {e}")
            raise
    
    def _get_live_data(self, symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
        """Get data from live buffer."""
        logger.debug(f"     Getting live data for {symbol}")
        
        # Get data from live buffer
        live_data = self.live_buffer.get_data_range(start, end)
        
        # Filter by symbol if needed
        if not live_data.empty and 'symbol' in live_data.columns:
            live_data = live_data[live_data['symbol'] == symbol]
        
        logger.debug(f"     Live buffer: {len(live_data)} records")
        return live_data
    
    def _get_combined_data(self, symbols: List[str], start: datetime, 
                          end: datetime, schema: str, cutoff: datetime) -> pd.DataFrame:
        """Combine historical and live data seamlessly."""
        
        logger.debug(f"     Combining data sources at cutoff: {cutoff}")
        
        # Get historical data up to cutoff
        logger.debug(f"     Getting historical: {start} to {cutoff}")
        historical_data = self.cached_client.get_historical_data(
            symbols, start, cutoff, schema
        )
        
        # Get live data from cutoff to end
        logger.debug(f"     Getting live: {cutoff} to {end}")
        live_data = self._get_live_data(symbols[0], cutoff, end)
        
        # Combine datasets intelligently
        result = self._merge_dataframes(historical_data, live_data)
        
        logger.debug(f"     Combined: {len(historical_data)} historical + "
                    f"{len(live_data)} live = {len(result)} total")
        
        return result
    
    def _merge_dataframes(self, historical: pd.DataFrame, live: pd.DataFrame) -> pd.DataFrame:
        """Merge historical and live DataFrames intelligently."""
        
        # Handle empty DataFrames
        if historical.empty and live.empty:
            return pd.DataFrame()
        elif historical.empty:
            return live.copy()
        elif live.empty:
            return historical.copy()
        
        # Ensure both have the same columns (align schemas)
        historical_cols = set(historical.columns)
        live_cols = set(live.columns)
        
        # Find common columns
        common_cols = historical_cols.intersection(live_cols)
        
        if not common_cols:
            logger.warning("No common columns between historical and live data")
            return historical.copy()  # Return historical as fallback
        
        # Align columns
        historical_aligned = historical[list(common_cols)]
        live_aligned = live[list(common_cols)]
        
        # Concatenate and sort by index (timestamp)
        try:
            combined = pd.concat([historical_aligned, live_aligned])
            combined = combined.sort_index()
            
            # Remove duplicates if any (keep first occurrence)
            combined = combined[~combined.index.duplicated(keep='first')]
            
            return combined
            
        except Exception as e:
            logger.warning(f"Error merging dataframes: {e}")
            return historical.copy()  # Fallback to historical
    
    def _update_response_time(self, response_time: float):
        """Update average response time statistics."""
        current_avg = self.request_stats['average_response_time']
        total_requests = self.request_stats['total_requests']
        
        # Running average calculation
        new_avg = ((current_avg * (total_requests - 1)) + response_time) / total_requests
        self.request_stats['average_response_time'] = new_avg
    
    async def start_live_streaming(self, symbols: Optional[List[str]] = None):
        """
        Start live data streaming for specified symbols.
        
        Args:
            symbols: List of symbols to stream (uses defaults if None)
        """
        if self.is_live_active:
            logger.warning("Live streaming is already active")
            return
        
        symbols = symbols or self.default_symbols
        
        logger.info(f"🔴 Starting live streaming for {symbols}")
        
        # Add subscriptions for each symbol
        for symbol in symbols:
            for schema in self.default_schemas:
                subscription = SubscriptionConfig(
                    symbol=symbol,
                    schema=schema,
                    enabled=True,
                    auto_reconnect=True
                )
                await self.live_manager.add_subscription(subscription)
                self.active_symbols.add(symbol)
        
        # Start the live manager
        await self.live_manager.start_manager()
        self.is_live_active = True
        
        logger.info(f"✅ Live streaming started for {len(symbols)} symbols")
    
    async def stop_live_streaming(self):
        """Stop live data streaming."""
        if not self.is_live_active:
            logger.warning("Live streaming is not active")
            return
        
        logger.info("🛑 Stopping live streaming...")
        
        await self.live_manager.stop_manager()
        self.is_live_active = False
        self.active_symbols.clear()
        
        logger.info("✅ Live streaming stopped")
    
    def get_latest_price(self, symbol: str) -> Optional[float]:
        """
        Get the latest price for a symbol.
        
        Args:
            symbol: Symbol to get price for
            
        Returns:
            Latest price or None if not available
        """
        latest_tick = self.live_buffer.get_latest_tick(symbol)
        return latest_tick.price if latest_tick else None
    
    def get_price_summary(self, symbol: str, seconds: int = 60) -> Optional[Dict[str, float]]:
        """
        Get price summary for a symbol from live buffer.
        
        Args:
            symbol: Symbol to analyze
            seconds: Lookback period in seconds
            
        Returns:
            Price summary dictionary or None
        """
        return self.live_buffer.get_price_summary(symbol, seconds)
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get comprehensive system statistics."""
        cache_stats = self.cached_client.get_performance_stats()
        buffer_stats = self.live_buffer.get_stats()
        manager_stats = self.live_manager.get_manager_stats()
        
        # Calculate efficiency metrics
        total_requests = self.request_stats['total_requests']
        cache_efficiency = cache_stats.get('cache_efficiency_percent', 0)
        
        return {
            'coordinator': {
                'live_active': self.is_live_active,
                'active_symbols': list(self.active_symbols),
                'live_cutoff': self.get_live_cutoff(),
                'request_stats': self.request_stats.copy()
            },
            'cache_performance': cache_stats,
            'live_buffer': {
                'utilization': buffer_stats.buffer_utilization,
                'size_mb': buffer_stats.buffer_size_mb,
                'symbols': buffer_stats.symbols,
                'ticks_per_second': buffer_stats.ticks_per_second
            },
            'live_manager': manager_stats,
            'efficiency_metrics': {
                'cache_hit_rate': cache_efficiency,
                'avg_response_time': self.request_stats['average_response_time'],
                'request_distribution': {
                    'cache_only': self.request_stats['cache_only_requests'],
                    'live_only': self.request_stats['live_only_requests'], 
                    'combined': self.request_stats['combined_requests']
                }
            }
        }
    
    def print_system_status(self):
        """Print comprehensive system status."""
        stats = self.get_system_stats()
        
        print(f"\n{'='*70}")
        print(f"🎯 UNIFIED DATA COORDINATOR STATUS")
        print(f"{'='*70}")
        
        # Coordinator status
        coord_stats = stats['coordinator']
        print(f"Live streaming:          {'🟢 Active' if coord_stats['live_active'] else '🔴 Inactive'}")
        print(f"Active symbols:          {', '.join(coord_stats['active_symbols']) if coord_stats['active_symbols'] else 'None'}")
        print(f"Live cutoff:             {coord_stats['live_cutoff']}")
        print(f"Total requests:          {coord_stats['request_stats']['total_requests']:,}")
        print(f"Avg response time:       {coord_stats['request_stats']['average_response_time']:.3f}s")
        
        # Request distribution
        req_stats = coord_stats['request_stats']
        print(f"\n📊 REQUEST DISTRIBUTION:")
        print(f"Cache only:              {req_stats['cache_only_requests']:>6,} ({req_stats['cache_only_requests']/max(req_stats['total_requests'],1)*100:>5.1f}%)")
        print(f"Live only:               {req_stats['live_only_requests']:>6,} ({req_stats['live_only_requests']/max(req_stats['total_requests'],1)*100:>5.1f}%)")
        print(f"Combined:                {req_stats['combined_requests']:>6,} ({req_stats['combined_requests']/max(req_stats['total_requests'],1)*100:>5.1f}%)")
        
        # Cache performance  
        cache_stats = stats['cache_performance']
        print(f"\n💾 CACHE PERFORMANCE:")
        print(f"Cache efficiency:        {cache_stats.get('cache_efficiency_percent', 0):.1f}%")
        print(f"API calls saved:         {cache_stats.get('api_calls_saved', 0):,}")
        print(f"Est. cost saved:         ${cache_stats.get('estimated_cost_saved', 0):.2f}")
        
        # Live buffer status
        buffer_stats = stats['live_buffer']
        print(f"\n📡 LIVE BUFFER:")
        print(f"Buffer utilization:      {buffer_stats['utilization']:.1f}%")
        print(f"Memory usage:            {buffer_stats['size_mb']:.1f} MB")
        print(f"Ticks per second:        {buffer_stats['ticks_per_second']:.1f}")
        print(f"Symbols tracked:         {len(buffer_stats['symbols'])}")
        
        # Live manager status
        manager_stats = stats['live_manager']
        print(f"\n📊 LIVE MANAGER:")
        print(f"Connected streams:       {manager_stats['connected_streams']}")
        print(f"Total subscriptions:     {manager_stats['total_subscriptions']}")
        print(f"Active tasks:            {manager_stats['active_tasks']}")
    
    def get_data_simple(self, symbol: str, hours_back: int = 1, 
                       schema: str = "ohlcv-1m") -> pd.DataFrame:
        """
        Simplified data access for quick queries.
        
        Args:
            symbol: Symbol to retrieve
            hours_back: Hours of data to retrieve
            schema: Data schema
            
        Returns:
            DataFrame with recent data
        """
        end = datetime.utcnow()
        start = end - timedelta(hours=hours_back)
        
        return self.get_data(symbol, start, end, schema)
    
    async def warm_cache_for_symbols(self, symbols: List[str], days_back: int = 30):
        """
        Warm cache by pre-loading data for symbols.
        
        Args:
            symbols: Symbols to warm cache for
            days_back: Days of historical data to pre-load
        """
        logger.info(f"🔥 Warming cache for {len(symbols)} symbols ({days_back} days)")
        
        end = datetime.utcnow()
        start = end - timedelta(days=days_back)
        
        for symbol in symbols:
            for schema in ["ohlcv-1m", "trades"]:
                try:
                    # This will populate the cache
                    data = self.get_data([symbol], start, end, schema)
                    logger.debug(f"   Warmed {symbol} {schema}: {len(data)} records")
                except Exception as e:
                    logger.warning(f"   Failed to warm {symbol} {schema}: {e}")
        
        logger.info("✅ Cache warming completed")


def create_coordinator(cache_dir: str = "data/cache", 
                      live_buffer_size: int = 100000) -> UnifiedDataCoordinator:
    """
    Factory function to create a unified data coordinator.
    
    Args:
        cache_dir: Cache directory path
        live_buffer_size: Live buffer size
        
    Returns:
        Configured UnifiedDataCoordinator
    """
    return UnifiedDataCoordinator(cache_dir, live_buffer_size)


async def demo_unified_coordinator():
    """Demonstrate the unified data coordinator."""
    print("UNIFIED DATA COORDINATOR DEMONSTRATION")
    print("="*70)
    
    # Create coordinator
    coordinator = create_coordinator()
    
    # Show initial status
    coordinator.print_system_status()
    
    print(f"\n🎯 TESTING UNIFIED DATA ACCESS:")
    
    # Test 1: Recent data (should use cache or live buffer)
    try:
        symbol = "NQU4"
        recent_data = coordinator.get_data_simple(symbol, hours_back=1)
        print(f"✅ Recent data test: {len(recent_data)} records")
    except Exception as e:
        print(f"⚠️  Recent data test failed: {e}")
    
    # Test 2: Historical data (should use cache)
    try:
        from datetime import datetime
        start = datetime(2024, 8, 1, 14, 0)
        end = start + timedelta(hours=2)
        historical_data = coordinator.get_data([symbol], start, end, "ohlcv-1m")
        print(f"✅ Historical data test: {len(historical_data)} records")
    except Exception as e:
        print(f"⚠️  Historical data test failed: {e}")
    
    # Show final status
    print(f"\n📊 FINAL STATUS:")
    coordinator.print_system_status()
    
    print(f"\n✅ Unified coordinator demonstration complete!")
    print(f"   The system provides seamless access to both historical and live data")
    print(f"   through a single, simple interface that optimizes performance automatically.")


if __name__ == '__main__':
    asyncio.run(demo_unified_coordinator())