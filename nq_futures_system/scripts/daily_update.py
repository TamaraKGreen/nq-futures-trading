#!/usr/bin/env python3
"""
Daily Data Update Script

Efficiently fetches and caches new daily data from Databento API.
This script is designed to run once per day to keep the cache current
while minimizing API costs.

Key Features:
- Only fetches data that's not already cached
- Automatically detects missing dates
- Handles market holidays and weekends
- Provides detailed cost and time reporting
- Safe error handling and recovery
"""

import os
import sys
import argparse
import logging
from datetime import datetime, date, timedelta
from typing import List, Optional

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.collectors.cached_databento_client import CachedDatabentoClient
from data.cache.cache_manager import IncrementalCacheManager


class DailyDataUpdater:
    """Manages daily incremental data updates."""
    
    def __init__(self, api_key: Optional[str] = None, cache_dir: str = "data/cache"):
        """
        Initialize daily data updater.
        
        Args:
            api_key: Databento API key (uses env var if not provided)
            cache_dir: Cache directory path
        """
        self.client = CachedDatabentoClient(api_key, cache_dir)
        self.cache_manager = IncrementalCacheManager(cache_dir)
        
        # Default symbols to update
        self.default_symbols = ['NQZ4', 'NQH5']  # Current and next quarter
        self.default_schemas = ['trades', 'ohlcv-1m']
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('daily_update.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def get_update_date_range(self, days_back: int = 5) -> tuple[date, date]:
        """
        Get the date range for updates.
        
        Args:
            days_back: How many days back to check for missing data
            
        Returns:
            (start_date, end_date) tuple
        """
        today = date.today()
        start_date = today - timedelta(days=days_back)
        
        # Don't try to fetch future data
        end_date = today - timedelta(days=1)  # Yesterday
        
        return start_date, end_date
    
    def update_symbol_data(self, symbol: str, schema: str, 
                          start_date: date, end_date: date) -> dict:
        """
        Update data for a specific symbol and schema.
        
        Args:
            symbol: Symbol to update
            schema: Data schema
            start_date: Start date for update range
            end_date: End date for update range
            
        Returns:
            Dictionary with update statistics
        """
        self.logger.info(f"Updating {symbol} {schema} data from {start_date} to {end_date}")
        
        # Find missing dates
        missing_dates = self.cache_manager.find_missing_dates(
            symbol, schema, start_date, end_date
        )
        
        if not missing_dates:
            self.logger.info(f"  ✅ All dates already cached for {symbol} {schema}")
            return {
                'symbol': symbol,
                'schema': schema,
                'missing_dates': 0,
                'api_calls': 0,
                'records_cached': 0,
                'cost_estimate': 0.0
            }
        
        self.logger.info(f"  📅 Need to fetch {len(missing_dates)} missing dates:")
        for missing_date in missing_dates:
            self.logger.info(f"    - {missing_date}")
        
        total_records = 0
        api_calls = 0
        
        # Fetch data for each missing date
        for missing_date in missing_dates:
            try:
                # Convert date to datetime range (full trading day)
                start_datetime = datetime.combine(missing_date, datetime.min.time())
                end_datetime = start_datetime + timedelta(days=1)
                
                # Fetch data from API
                data = self.client.get_historical_data(
                    symbols=[symbol],
                    start=start_datetime,
                    end=end_datetime,
                    schema=schema
                )
                
                if not data.empty:
                    # Cache the daily data
                    self.cache_manager.cache_daily_data(data, symbol, missing_date, schema)
                    total_records += len(data)
                    self.logger.info(f"    ✅ Cached {len(data)} records for {missing_date}")
                else:
                    self.logger.warning(f"    ⚠️  No data returned for {missing_date}")
                
                api_calls += 1
                
            except Exception as e:
                self.logger.error(f"    ❌ Failed to fetch data for {missing_date}: {e}")
        
        # Estimate cost
        cost_per_call = 0.20 if schema == 'trades' else 0.02
        total_cost = api_calls * cost_per_call
        
        self.logger.info(f"  📊 Update complete: {api_calls} API calls, {total_records} records, ~${total_cost:.2f}")
        
        return {
            'symbol': symbol,
            'schema': schema,
            'missing_dates': len(missing_dates),
            'api_calls': api_calls,
            'records_cached': total_records,
            'cost_estimate': total_cost
        }
    
    def run_daily_update(self, symbols: Optional[List[str]] = None,
                        schemas: Optional[List[str]] = None,
                        days_back: int = 5) -> dict:
        """
        Run the complete daily update process.
        
        Args:
            symbols: List of symbols to update (uses defaults if None)
            schemas: List of schemas to update (uses defaults if None)  
            days_back: How many days back to check
            
        Returns:
            Dictionary with complete update statistics
        """
        symbols = symbols or self.default_symbols
        schemas = schemas or self.default_schemas
        
        start_date, end_date = self.get_update_date_range(days_back)
        
        self.logger.info("=" * 60)
        self.logger.info("STARTING DAILY DATA UPDATE")
        self.logger.info("=" * 60)
        self.logger.info(f"Update period: {start_date} to {end_date}")
        self.logger.info(f"Symbols: {symbols}")
        self.logger.info(f"Schemas: {schemas}")
        
        update_start_time = datetime.now()
        all_results = []
        
        # Update each symbol/schema combination
        for symbol in symbols:
            for schema in schemas:
                result = self.update_symbol_data(symbol, schema, start_date, end_date)
                all_results.append(result)
        
        update_end_time = datetime.now()
        update_duration = (update_end_time - update_start_time).total_seconds()
        
        # Calculate totals
        total_api_calls = sum(r['api_calls'] for r in all_results)
        total_records = sum(r['records_cached'] for r in all_results)
        total_cost = sum(r['cost_estimate'] for r in all_results)
        
        # Log summary
        self.logger.info("=" * 60)
        self.logger.info("DAILY UPDATE SUMMARY")
        self.logger.info("=" * 60)
        self.logger.info(f"Update duration:     {update_duration:.1f} seconds")
        self.logger.info(f"Total API calls:     {total_api_calls}")
        self.logger.info(f"Total records:       {total_records:,}")
        self.logger.info(f"Estimated cost:      ${total_cost:.2f}")
        
        if total_api_calls == 0:
            self.logger.info("🎉 All data was already cached - no API calls needed!")
        else:
            if total_records > 0:
                self.logger.info(f"💰 Cost per record:     ${total_cost/total_records:.6f}")
                self.logger.info(f"⚡ Records per second: {total_records/update_duration:.0f}")
            else:
                self.logger.info("⚠️  No records retrieved (possibly market holiday or no trading activity)")
        
        # Cache performance stats
        cache_stats = self.client.get_performance_stats()
        self.logger.info(f"\n📊 Cache Performance:")
        self.logger.info(f"Cache efficiency:    {cache_stats['cache_efficiency_percent']:.1f}%")
        self.logger.info(f"Total cache hits:    {cache_stats['cache_hits']}")
        self.logger.info(f"Cache size:          {cache_stats['cache_size_mb']:.1f} MB")
        
        return {
            'update_duration': update_duration,
            'total_api_calls': total_api_calls,
            'total_records': total_records,
            'total_cost': total_cost,
            'results': all_results,
            'cache_stats': cache_stats
        }
    
    def cleanup_old_cache(self, days_to_keep: int = 30):
        """
        Clean up old cache files to save disk space.
        
        Args:
            days_to_keep: Number of days of cache to keep
        """
        self.logger.info(f"🧹 Cleaning up cache files older than {days_to_keep} days")
        
        self.client.clear_cache(older_than_days=days_to_keep)
        
        self.logger.info("Cache cleanup completed")


def main():
    """Main entry point for daily update script."""
    parser = argparse.ArgumentParser(description="Daily Databento data update script")
    parser.add_argument(
        '--symbols', 
        nargs='+', 
        help='Symbols to update (default: NQZ4 NQH5)'
    )
    parser.add_argument(
        '--schemas',
        nargs='+',
        choices=['trades', 'ohlcv-1m', 'ohlcv-1h', 'bbo'],
        help='Data schemas to update (default: trades ohlcv-1m)'
    )
    parser.add_argument(
        '--days-back',
        type=int,
        default=5,
        help='Number of days back to check for missing data (default: 5)'
    )
    parser.add_argument(
        '--cache-dir',
        default='data/cache',
        help='Cache directory path (default: data/cache)'
    )
    parser.add_argument(
        '--cleanup',
        action='store_true',
        help='Clean up old cache files after update'
    )
    parser.add_argument(
        '--cleanup-days',
        type=int,
        default=30,
        help='Days of cache to keep during cleanup (default: 30)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be updated without making API calls'
    )
    
    args = parser.parse_args()
    
    # Check for API key
    if not os.getenv('DATABENTO_API_KEY'):
        print("❌ Error: DATABENTO_API_KEY environment variable not set")
        print("   Please set your Databento API key in the environment")
        sys.exit(1)
    
    try:
        # Create updater
        updater = DailyDataUpdater(cache_dir=args.cache_dir)
        
        if args.dry_run:
            print("🔍 DRY RUN MODE - No API calls will be made")
            start_date, end_date = updater.get_update_date_range(args.days_back)
            symbols = args.symbols or updater.default_symbols
            schemas = args.schemas or updater.default_schemas
            
            print(f"\nWould update:")
            print(f"  Date range: {start_date} to {end_date}")
            print(f"  Symbols: {symbols}")
            print(f"  Schemas: {schemas}")
            
            for symbol in symbols:
                for schema in schemas:
                    missing = updater.cache_manager.find_missing_dates(
                        symbol, schema, start_date, end_date
                    )
                    print(f"  {symbol} {schema}: {len(missing)} missing dates")
        else:
            # Run the update
            results = updater.run_daily_update(
                symbols=args.symbols,
                schemas=args.schemas,
                days_back=args.days_back
            )
            
            # Cleanup if requested
            if args.cleanup:
                updater.cleanup_old_cache(args.cleanup_days)
            
            # Exit with appropriate code
            if results['total_api_calls'] > 0:
                print(f"\n✅ Daily update completed successfully")
                print(f"   API calls: {results['total_api_calls']}")
                print(f"   Cost: ${results['total_cost']:.2f}")
            else:
                print(f"\n✅ No updates needed - all data already cached")
    
    except KeyboardInterrupt:
        print("\n🛑 Update cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Update failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()