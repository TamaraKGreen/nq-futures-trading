#!/usr/bin/env python3
"""
Example of how incremental daily updates work with caching system.
Shows how adding new data is simple and efficient.
"""

import os
import pandas as pd
from datetime import datetime, timedelta, date
from typing import List, Tuple
import json


class IncrementalCacheManager:
    """
    Demonstrates how daily data updates work with the caching system.
    Key insight: You only pay for each day's data ONCE.
    """
    
    def __init__(self, cache_dir="data/cache"):
        self.cache_dir = cache_dir
        self.metadata_file = os.path.join(cache_dir, "cache_index.json")
        self.ensure_dirs()
        self.metadata = self.load_metadata()
    
    def ensure_dirs(self):
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(os.path.join(self.cache_dir, "daily"), exist_ok=True)
    
    def load_metadata(self):
        if os.path.exists(self.metadata_file):
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        return {"daily_files": {}, "last_update": None}
    
    def save_metadata(self):
        with open(self.metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)
    
    def get_latest_cached_date(self, symbol: str, schema: str) -> date:
        """Find the latest date we have cached for this symbol/schema."""
        key = f"{symbol}_{schema}"
        if key not in self.metadata["daily_files"]:
            return date(2020, 1, 1)  # Very old date if no cache
        
        dates = [datetime.fromisoformat(d).date() 
                for d in self.metadata["daily_files"][key].keys()]
        return max(dates) if dates else date(2020, 1, 1)
    
    def find_missing_dates(self, symbol: str, schema: str, 
                          start: date, end: date) -> List[date]:
        """Find which dates we need to fetch from API."""
        missing = []
        current = start
        
        while current <= end:
            # Skip weekends (simplified - real version would check market calendar)
            if current.weekday() < 5:  # Monday=0, Friday=4
                if not self.has_cached_date(symbol, schema, current):
                    missing.append(current)
            current += timedelta(days=1)
        
        return missing
    
    def has_cached_date(self, symbol: str, schema: str, date_obj: date) -> bool:
        """Check if we have this specific date cached."""
        key = f"{symbol}_{schema}"
        if key not in self.metadata["daily_files"]:
            return False
        
        date_str = date_obj.isoformat()
        return date_str in self.metadata["daily_files"][key]
    
    def simulate_api_fetch(self, symbol: str, date_obj: date, schema: str) -> pd.DataFrame:
        """Simulate fetching data from Databento API."""
        print(f"  🌐 API CALL: Fetching {symbol} {schema} for {date_obj}")
        
        # Simulate realistic data sizes
        if schema == "trades":
            rows = 50000  # ~50K trades per day
            cost = 0.20   # ~$0.20 per day
        else:  # ohlcv-1m
            rows = 390    # ~390 minutes per trading day
            cost = 0.02   # ~$0.02 per day
        
        # Create dummy data
        timestamps = pd.date_range(
            start=datetime.combine(date_obj, datetime.min.time()),
            periods=rows,
            freq='1min' if schema == 'ohlcv-1m' else '1s'
        )
        
        df = pd.DataFrame({
            'timestamp': timestamps,
            'symbol': symbol,
            'price': 25000 + (pd.Series(range(rows)) % 100) * 0.25,
            'size': 1 + (pd.Series(range(rows)) % 10)
        })
        
        print(f"     💰 Cost: ${cost:.2f}")
        return df, cost
    
    def cache_daily_data(self, df: pd.DataFrame, symbol: str, 
                        date_obj: date, schema: str):
        """Cache a single day's data."""
        filename = f"{symbol}_{date_obj.isoformat()}_{schema}.parquet"
        filepath = os.path.join(self.cache_dir, "daily", filename)
        
        df.to_parquet(filepath, compression='snappy')
        
        # Update metadata
        key = f"{symbol}_{schema}"
        if key not in self.metadata["daily_files"]:
            self.metadata["daily_files"][key] = {}
        
        self.metadata["daily_files"][key][date_obj.isoformat()] = {
            "file": filepath,
            "rows": len(df),
            "cached_at": datetime.now().isoformat()
        }
        
        self.save_metadata()
    
    def get_data_with_smart_caching(self, symbol: str, start: date, 
                                   end: date, schema: str) -> Tuple[pd.DataFrame, float]:
        """
        Main method: Get data using smart incremental caching.
        Returns (data, api_cost)
        """
        print(f"\n📊 REQUEST: {symbol} {schema} from {start} to {end}")
        print("=" * 50)
        
        # Find what dates we need to fetch
        missing_dates = self.find_missing_dates(symbol, schema, start, end)
        
        if not missing_dates:
            print("✅ ALL DATA CACHED - No API calls needed!")
            total_cost = 0.0
        else:
            print(f"📅 Need to fetch {len(missing_dates)} missing days:")
            for d in missing_dates:
                print(f"   - {d}")
            
            # Fetch missing data
            total_cost = 0.0
            for missing_date in missing_dates:
                df, cost = self.simulate_api_fetch(symbol, missing_date, schema)
                self.cache_daily_data(df, symbol, missing_date, schema)
                total_cost += cost
        
        # Load all requested data from cache
        all_data = []
        current = start
        cache_hits = 0
        
        while current <= end:
            if current.weekday() < 5:  # Trading days only
                if self.has_cached_date(symbol, schema, current):
                    # Load from cache
                    cache_hits += 1
                    # In real implementation, would load actual data
            current += timedelta(days=1)
        
        print(f"\n📈 RESULT:")
        print(f"   Cache hits: {cache_hits}")
        print(f"   API calls: {len(missing_dates)}")
        print(f"   Total cost: ${total_cost:.2f}")
        
        # Return dummy combined data for demo
        combined_df = pd.DataFrame({
            'symbol': [symbol] * 100,
            'price': [25000] * 100
        })
        
        return combined_df, total_cost


def demonstrate_daily_updates():
    """Show how daily updates work in practice."""
    print("INCREMENTAL DATA UPDATE DEMONSTRATION")
    print("=" * 60)
    
    cache = IncrementalCacheManager()
    
    # Scenario 1: Initial data load (first time)
    print("\n🏁 SCENARIO 1: Initial data load (building cache)")
    print("-" * 50)
    
    start_date = date(2024, 8, 1)
    end_date = date(2024, 8, 5)  # 5 days
    
    data1, cost1 = cache.get_data_with_smart_caching(
        "NQZ5", start_date, end_date, "trades"
    )
    
    # Scenario 2: Same request (should be all cached)
    print("\n🔄 SCENARIO 2: Repeat same request (should be cached)")
    print("-" * 50)
    
    data2, cost2 = cache.get_data_with_smart_caching(
        "NQZ5", start_date, end_date, "trades"
    )
    
    # Scenario 3: Add one new day
    print("\n📅 SCENARIO 3: Add one new day (daily update)")
    print("-" * 50)
    
    new_end = date(2024, 8, 6)  # Add one more day
    
    data3, cost3 = cache.get_data_with_smart_caching(
        "NQZ5", start_date, new_end, "trades"
    )
    
    # Scenario 4: Rolling window (last 5 days)
    print("\n🪟 SCENARIO 4: Rolling window - last 5 days")
    print("-" * 50)
    
    today = date(2024, 8, 10)
    rolling_start = today - timedelta(days=4)
    
    data4, cost4 = cache.get_data_with_smart_caching(
        "NQZ5", rolling_start, today, "trades"
    )
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 DAILY UPDATE COST ANALYSIS")
    print("=" * 60)
    
    total_api_cost = cost1 + cost2 + cost3 + cost4
    
    print(f"Initial load (5 days):     ${cost1:.2f}")
    print(f"Repeat request:           ${cost2:.2f}")
    print(f"Add 1 new day:            ${cost3:.2f}")
    print(f"Rolling window (5 days):  ${cost4:.2f}")
    print(f"Total API costs:          ${total_api_cost:.2f}")
    
    print(f"\n💡 KEY INSIGHTS:")
    print(f"   - Initial data load: Pay once for historical data")
    print(f"   - Daily updates: Only pay for new days (~$0.20/day)")
    print(f"   - Repeated analysis: FREE (uses cache)")
    print(f"   - Cost scales linearly with time, not usage!")
    
    # Monthly projection
    print(f"\n📅 MONTHLY PROJECTION:")
    daily_cost = 0.20
    trading_days = 20
    monthly_new_data = daily_cost * trading_days
    
    print(f"   Daily new data: ${daily_cost:.2f}/day")
    print(f"   Monthly cost: ${monthly_new_data:.2f}")
    print(f"   Unlimited backtests: $0 (cached)")
    print(f"   \n   VS without caching: $100+ (re-downloading same data)")


def show_simple_daily_workflow():
    """Show what your daily workflow looks like."""
    print("\n" + "=" * 60)
    print("🔄 YOUR SIMPLE DAILY WORKFLOW")
    print("=" * 60)
    
    print("\n1️⃣  Morning: Check for new data")
    print("   cache.update_daily_data()  # 30 seconds, $0.20")
    
    print("\n2️⃣  Trading day: Run analysis (multiple times)")
    print("   for strategy in strategies:")
    print("       data = cache.get_data(last_30_days)  # FREE (cached)")
    print("       backtest(strategy, data)")
    
    print("\n3️⃣  End of day: You're done!")
    print("   Tomorrow's data will be auto-fetched when needed")
    
    print(f"\n💰 Daily cost: $0.20 for new data")
    print(f"   Unlimited analysis: FREE")
    print(f"   Time overhead: 30 seconds")


if __name__ == "__main__":
    demonstrate_daily_updates()
    show_simple_daily_workflow()