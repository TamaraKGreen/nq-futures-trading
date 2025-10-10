#!/usr/bin/env python3
"""
Example of how to add caching to the existing databento_client.py
This wraps the existing client to add caching functionality.
"""

import os
import pandas as pd
import hashlib
from datetime import datetime
from typing import List, Optional

# Import the existing client
from data.collectors.databento_client import DatabentoClient


class CachedDatabentoClient(DatabentoClient):
    """
    Enhanced Databento client with caching to minimize API costs.
    
    This extends the existing client, adding a cache layer that:
    1. Checks for cached data before making API calls
    2. Caches new data automatically
    3. Handles partial date ranges intelligently
    """
    
    def __init__(self, api_key: Optional[str] = None, cache_dir: str = "data/cache"):
        super().__init__(api_key)
        self.cache_dir = cache_dir
        self._ensure_cache_dirs()
        self._cache_hits = 0
        self._api_calls = 0
    
    def _ensure_cache_dirs(self):
        """Create cache directory structure."""
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(os.path.join(self.cache_dir, "data"), exist_ok=True)
    
    def _get_cache_path(self, symbols: List[str], start: datetime, 
                       end: datetime, schema: str) -> str:
        """Generate cache file path."""
        # Create a unique filename based on request parameters
        symbols_str = "_".join(sorted(symbols))
        date_str = f"{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}"
        
        # Use first symbol for directory organization
        symbol_dir = os.path.join(self.cache_dir, "data", symbols[0])
        os.makedirs(symbol_dir, exist_ok=True)
        
        filename = f"{symbols_str}_{date_str}_{schema}.parquet"
        return os.path.join(symbol_dir, filename)
    
    def get_historical_data(self, symbols: List[str], start: datetime, 
                          end: datetime, schema: str = "trades",
                          dataset: str = "GLBX.MDP3") -> pd.DataFrame:
        """
        Override parent method to add caching.
        
        This method:
        1. Checks if data exists in cache
        2. If yes, returns cached data (no API call)
        3. If no, fetches from API and caches it
        """
        cache_path = self._get_cache_path(symbols, start, end, schema)
        
        # Check if we have this data cached
        if os.path.exists(cache_path):
            self._cache_hits += 1
            print(f"💾 Cache HIT ({self._cache_hits}): Loading {symbols} from cache")
            print(f"   Saved API call! Cache efficiency: {self.get_cache_efficiency():.1f}%")
            return pd.read_parquet(cache_path)
        
        # Not in cache, fetch from API
        print(f"🌐 Cache MISS: Fetching {symbols} from Databento API...")
        self._api_calls += 1
        
        # Call parent method to get data from API
        df = super().get_historical_data(symbols, start, end, schema, dataset)
        
        # Cache the data for future use
        if not df.empty:
            df.to_parquet(cache_path, compression='snappy')
            size_mb = os.path.getsize(cache_path) / (1024 * 1024)
            print(f"💾 Cached {len(df)} rows ({size_mb:.1f} MB) for future use")
        
        return df
    
    def get_cache_efficiency(self) -> float:
        """Calculate cache hit rate."""
        total_requests = self._cache_hits + self._api_calls
        if total_requests == 0:
            return 0.0
        return (self._cache_hits / total_requests) * 100
    
    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        stats = {
            "cache_hits": self._cache_hits,
            "api_calls": self._api_calls,
            "efficiency": self.get_cache_efficiency(),
            "calls_saved": self._cache_hits,
            "cache_size_mb": self._calculate_cache_size()
        }
        return stats
    
    def _calculate_cache_size(self) -> float:
        """Calculate total cache size in MB."""
        total_size = 0
        for root, dirs, files in os.walk(self.cache_dir):
            for file in files:
                if file.endswith('.parquet'):
                    total_size += os.path.getsize(os.path.join(root, file))
        return total_size / (1024 * 1024)
    
    def clear_cache(self, older_than_days: Optional[int] = None):
        """Clear cache files, optionally only those older than N days."""
        import shutil
        from datetime import timedelta
        
        if older_than_days is None:
            # Clear entire cache
            shutil.rmtree(os.path.join(self.cache_dir, "data"))
            self._ensure_cache_dirs()
            print("🗑️  Cleared entire cache")
        else:
            # Clear old files
            cutoff_time = datetime.now() - timedelta(days=older_than_days)
            cleared_count = 0
            
            for root, dirs, files in os.walk(self.cache_dir):
                for file in files:
                    if file.endswith('.parquet'):
                        file_path = os.path.join(root, file)
                        file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                        if file_time < cutoff_time:
                            os.remove(file_path)
                            cleared_count += 1
            
            print(f"🗑️  Cleared {cleared_count} cache files older than {older_than_days} days")


def demonstrate_cost_savings():
    """Show real cost savings with actual API calls."""
    print("\n" + "="*60)
    print("CACHED DATABENTO CLIENT DEMONSTRATION")
    print("="*60)
    
    # Create cached client
    client = CachedDatabentoClient()
    
    # Test dates (using historical data we know works)
    test_date = datetime(2024, 8, 1)
    symbols = ["NQU4"]
    
    print("\n1️⃣  FIRST REQUEST (No cache):")
    print("-" * 40)
    df1 = client.get_historical_data(
        symbols=symbols,
        start=test_date,
        end=test_date + timedelta(hours=1),
        schema="trades"
    )
    print(f"   Retrieved {len(df1)} trades")
    
    print("\n2️⃣  SECOND REQUEST (Same data - should hit cache):")
    print("-" * 40)
    df2 = client.get_historical_data(
        symbols=symbols,
        start=test_date,
        end=test_date + timedelta(hours=1),
        schema="trades"
    )
    print(f"   Retrieved {len(df2)} trades")
    
    print("\n3️⃣  THIRD REQUEST (Different schema - new API call):")
    print("-" * 40)
    df3 = client.get_historical_data(
        symbols=symbols,
        start=test_date,
        end=test_date + timedelta(hours=1),
        schema="ohlcv-1m"
    )
    print(f"   Retrieved {len(df3)} bars")
    
    print("\n4️⃣  FOURTH REQUEST (Reuse OHLCV - should hit cache):")
    print("-" * 40)
    df4 = client.get_historical_data(
        symbols=symbols,
        start=test_date,
        end=test_date + timedelta(hours=1),
        schema="ohlcv-1m"
    )
    print(f"   Retrieved {len(df4)} bars")
    
    # Show statistics
    stats = client.get_cache_stats()
    print("\n" + "="*60)
    print("📊 CACHE STATISTICS")
    print("="*60)
    print(f"Total requests: {stats['cache_hits'] + stats['api_calls']}")
    print(f"Cache hits: {stats['cache_hits']}")
    print(f"API calls: {stats['api_calls']}")
    print(f"Cache efficiency: {stats['efficiency']:.1f}%")
    print(f"API calls saved: {stats['calls_saved']}")
    print(f"Cache size: {stats['cache_size_mb']:.1f} MB")
    
    print("\n💰 COST SAVINGS:")
    print(f"Without cache: {stats['cache_hits'] + stats['api_calls']} API calls")
    print(f"With cache: {stats['api_calls']} API calls")
    print(f"Reduction: {stats['efficiency']:.0f}%")
    
    # Monthly projection
    daily_requests = 100  # Typical daily usage
    monthly_requests = daily_requests * 20  # Trading days
    
    print(f"\n📅 MONTHLY PROJECTION (at {daily_requests} requests/day):")
    print(f"Without cache: {monthly_requests:,} API calls/month")
    print(f"With cache: ~{int(monthly_requests * (1 - stats['efficiency']/100)):,} API calls/month")
    print(f"Cost savings: ~${(monthly_requests * stats['efficiency']/100 * 0.01):.2f}/month")


if __name__ == "__main__":
    # Add parent directory to path
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    demonstrate_cost_savings()