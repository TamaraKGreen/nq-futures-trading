#!/usr/bin/env python3
"""
Example design for Databento cache system to minimize API costs.
This shows the concept - not for production use yet.
"""

import os
import pandas as pd
from datetime import datetime, timedelta
import hashlib
import json

class DatabentoCache:
    """
    Simple cache system for Databento data to minimize API calls.
    
    Key Features:
    1. Check local cache before making API calls
    2. Store data in Parquet format (efficient compression)
    3. Track what data we have to avoid redundant requests
    """
    
    def __init__(self, cache_dir="data/cache"):
        self.cache_dir = cache_dir
        self.metadata_file = os.path.join(cache_dir, "metadata.json")
        self.ensure_cache_dir()
        self.metadata = self.load_metadata()
    
    def ensure_cache_dir(self):
        """Create cache directory structure."""
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(os.path.join(self.cache_dir, "data"), exist_ok=True)
    
    def load_metadata(self):
        """Load cache metadata."""
        if os.path.exists(self.metadata_file):
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        return {"cache_entries": {}}
    
    def save_metadata(self):
        """Save cache metadata."""
        with open(self.metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)
    
    def get_cache_key(self, symbol, start_date, end_date, schema):
        """Generate unique cache key."""
        key_string = f"{symbol}_{start_date}_{end_date}_{schema}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get_cached_data(self, symbol, start_date, end_date, schema):
        """
        Check if we have this exact data cached.
        Returns DataFrame if found, None otherwise.
        """
        cache_key = self.get_cache_key(symbol, start_date, end_date, schema)
        
        if cache_key in self.metadata["cache_entries"]:
            cache_path = self.metadata["cache_entries"][cache_key]["path"]
            if os.path.exists(cache_path):
                print(f"  💾 CACHE HIT: Loading {symbol} data from cache")
                return pd.read_parquet(cache_path)
            else:
                print(f"  ⚠️  Cache file missing, will re-fetch")
                del self.metadata["cache_entries"][cache_key]
        
        return None
    
    def save_to_cache(self, df, symbol, start_date, end_date, schema):
        """Save DataFrame to cache."""
        cache_key = self.get_cache_key(symbol, start_date, end_date, schema)
        
        # Create symbol directory
        symbol_dir = os.path.join(self.cache_dir, "data", symbol)
        os.makedirs(symbol_dir, exist_ok=True)
        
        # Save as Parquet (efficient compression)
        filename = f"{start_date}_{end_date}_{schema}.parquet"
        cache_path = os.path.join(symbol_dir, filename)
        df.to_parquet(cache_path, compression='snappy')
        
        # Update metadata
        self.metadata["cache_entries"][cache_key] = {
            "symbol": symbol,
            "start": start_date,
            "end": end_date,
            "schema": schema,
            "path": cache_path,
            "rows": len(df),
            "cached_at": datetime.now().isoformat(),
            "size_mb": os.path.getsize(cache_path) / (1024 * 1024)
        }
        self.save_metadata()
        
        print(f"  💾 CACHED: Saved {len(df)} rows ({self.metadata['cache_entries'][cache_key]['size_mb']:.2f} MB)")
    
    def find_partial_data(self, symbol, start_date, end_date, schema):
        """
        Find any cached data that partially overlaps our request.
        This helps reduce the amount of new data we need to fetch.
        """
        overlapping = []
        
        for key, entry in self.metadata["cache_entries"].items():
            if (entry["symbol"] == symbol and 
                entry["schema"] == schema):
                
                # Check for date overlap
                cached_start = datetime.fromisoformat(entry["start"])
                cached_end = datetime.fromisoformat(entry["end"])
                req_start = datetime.fromisoformat(start_date)
                req_end = datetime.fromisoformat(end_date)
                
                if cached_start <= req_end and cached_end >= req_start:
                    overlapping.append(entry)
        
        return overlapping
    
    def get_missing_ranges(self, symbol, start_date, end_date, schema):
        """
        Determine what date ranges we need to fetch from API.
        Returns list of (start, end) tuples for missing data.
        """
        overlapping = self.find_partial_data(symbol, start_date, end_date, schema)
        
        if not overlapping:
            # No cached data, need everything
            return [(start_date, end_date)]
        
        # TODO: Implement smart range detection
        # For now, simplified version
        return []
    
    def get_cache_stats(self):
        """Get cache statistics."""
        stats = {
            "total_entries": len(self.metadata["cache_entries"]),
            "total_size_mb": 0,
            "symbols": set(),
            "date_range": {"min": None, "max": None}
        }
        
        for entry in self.metadata["cache_entries"].values():
            stats["total_size_mb"] += entry.get("size_mb", 0)
            stats["symbols"].add(entry["symbol"])
            
            if not stats["date_range"]["min"] or entry["start"] < stats["date_range"]["min"]:
                stats["date_range"]["min"] = entry["start"]
            if not stats["date_range"]["max"] or entry["end"] > stats["date_range"]["max"]:
                stats["date_range"]["max"] = entry["end"]
        
        return stats


# Example usage showing cost savings
def demonstrate_cache_savings():
    """Show how caching reduces API calls."""
    
    print("DATABENTO CACHE DEMONSTRATION")
    print("="*50)
    
    # Simulate a typical backtest scenario
    cache = DatabentoCache()
    
    # First run - everything needs to be fetched
    print("\n📊 FIRST BACKTEST RUN (No cache):")
    print("-" * 40)
    
    api_calls_scenario_1 = 0
    for month in range(1, 4):  # 3 months of data
        for symbol in ["NQH5", "NQM5", "NQU5", "NQZ5"]:
            start = f"2025-0{month}-01"
            end = f"2025-0{month}-28"
            
            cached = cache.get_cached_data(symbol, start, end, "ohlcv-1m")
            if cached is None:
                print(f"  🌐 API CALL: Fetching {symbol} for month {month}")
                api_calls_scenario_1 += 1
                # In real implementation, would fetch and cache here
    
    print(f"\nTotal API calls: {api_calls_scenario_1}")
    
    # Second run - most data is cached
    print("\n\n📊 SECOND BACKTEST RUN (With cache):")
    print("-" * 40)
    
    api_calls_scenario_2 = 0
    cache_hits = 0
    for month in range(1, 4):
        for symbol in ["NQH5", "NQM5", "NQU5", "NQZ5"]:
            start = f"2025-0{month}-01"
            end = f"2025-0{month}-28"
            
            # Simulate some data being cached
            if month < 3:  # Assume first 2 months are cached
                print(f"  💾 CACHE HIT: Loading {symbol} for month {month}")
                cache_hits += 1
            else:
                print(f"  🌐 API CALL: Fetching {symbol} for month {month} (new data)")
                api_calls_scenario_2 += 1
    
    print(f"\nCache hits: {cache_hits}")
    print(f"API calls: {api_calls_scenario_2}")
    print(f"API calls saved: {api_calls_scenario_1 - api_calls_scenario_2}")
    print(f"Cost reduction: {((api_calls_scenario_1 - api_calls_scenario_2) / api_calls_scenario_1 * 100):.0f}%")
    
    # Smart batching example
    print("\n\n📊 SMART BATCHING EXAMPLE:")
    print("-" * 40)
    
    print("Without batching (5 separate requests):")
    for i in range(5):
        print(f"  🌐 API CALL: Get day {i+1} data")
    
    print("\nWith batching (1 combined request):")
    print("  🌐 API CALL: Get days 1-5 data (single request)")
    print("  💾 Cache individual days for future use")
    
    print("\nBatching saves: 4 API calls (80% reduction)")
    
    # Show typical monthly savings
    print("\n\n💰 TYPICAL MONTHLY COST SAVINGS:")
    print("-" * 40)
    
    daily_symbols = 4
    trading_days = 20
    backtests_per_day = 10
    
    without_cache = daily_symbols * trading_days * backtests_per_day
    with_cache = daily_symbols * trading_days * 1  # Only first run hits API
    
    print(f"Without cache: {without_cache:,} API calls/month")
    print(f"With cache: {with_cache:,} API calls/month")
    print(f"Reduction: {((without_cache - with_cache) / without_cache * 100):.0f}%")
    print(f"\nEstimated cost savings: ${(without_cache - with_cache) * 0.01:.2f}/month")
    print("(Assuming $0.01 per API call)")


if __name__ == "__main__":
    demonstrate_cache_savings()