#!/usr/bin/env python3
"""Check what data is accessible with the current Databento API key."""

import databento as db
from datetime import datetime, timedelta
import os

from nq_futures_system.data.collectors.databento_client import DatabentoClient

def check_datasets():
    """Check which datasets we have access to."""
    client = DatabentoClient()
    
    print("Checking Databento API access...")
    print("="*60)
    
    # Common datasets to check
    datasets = [
        ("GLBX.MDP3", "CME Globex MDP 3.0"),
        ("XNAS.ITCH", "Nasdaq TotalView-ITCH"),  
        ("OPRA.PILLAR", "OPRA"),
        ("DBEQ.BASIC", "Databento Equities Basic"),
    ]
    
    # Test different time ranges
    time_ranges = [
        ("Recent (1 hour ago)", timedelta(hours=1)),
        ("Yesterday", timedelta(days=1)),
        ("Last week", timedelta(days=7)),
        ("Last month", timedelta(days=30)),
    ]
    
    for dataset_id, dataset_name in datasets:
        print(f"\nTesting {dataset_name} ({dataset_id}):")
        print("-" * 40)
        
        for range_name, delta in time_ranges:
            try:
                end = datetime.utcnow() - delta
                start = end - timedelta(minutes=1)
                
                # Try to get a small amount of data
                data = client.historical.timeseries.get_range(
                    dataset=dataset_id,
                    symbols=["NQ" if "GLBX" in dataset_id else "AAPL"],
                    schema="trades",
                    start=start,
                    end=end,
                    stype_in="raw_symbol",
                    limit=1
                )
                
                df = data.to_df()
                if not df.empty:
                    print(f"  ✓ {range_name}: SUCCESS - Retrieved {len(df)} records")
                else:
                    print(f"  ⚠️  {range_name}: No data found")
                    
            except Exception as e:
                error_msg = str(e)
                if "dataset_unavailable" in error_msg:
                    print(f"  ✗ {range_name}: Subscription required")
                elif "auth" in error_msg:
                    print(f"  ✗ {range_name}: Authentication failed")
                else:
                    print(f"  ✗ {range_name}: {error_msg[:60]}...")

def check_delayed_data():
    """Check if we have access to delayed data."""
    client = DatabentoClient()
    
    print("\n\nChecking for delayed/free tier data access...")
    print("="*60)
    
    # Try data from various delays
    delays = [
        ("15 minutes", timedelta(minutes=15)),
        ("1 hour", timedelta(hours=1)),
        ("1 day", timedelta(days=1)),
        ("1 week", timedelta(days=7)),
        ("1 month", timedelta(days=30)),
    ]
    
    for delay_name, delay_time in delays:
        try:
            end = datetime.utcnow() - delay_time
            start = end - timedelta(hours=1)
            
            print(f"\nTrying GLBX.MDP3 data from {delay_name} ago...")
            
            # Get available symbols first
            symbols = client.get_available_symbols("NQ", date=start)
            if symbols:
                print(f"  ✓ Found {len(symbols)} NQ symbols")
                
                # Try to get trade data
                futures = [s for s in symbols if s['instrument_class'] == 'FUTURE']
                if futures:
                    symbol = futures[0]['symbol']
                    print(f"  Trying to fetch data for {symbol}...")
                    
                    df = client.get_historical_data(
                        symbols=[symbol],
                        start=start,
                        end=end,
                        schema="ohlcv-1m"
                    )
                    
                    if not df.empty:
                        print(f"  ✓ SUCCESS: Retrieved {len(df)} bars")
                        print(f"    Price range: ${df['low'].min():,.2f} - ${df['high'].max():,.2f}")
                        return True  # Found working delay
                        
        except Exception as e:
            error_msg = str(e)
            if "dataset_unavailable" in error_msg:
                print(f"  ✗ Subscription required for this time range")
            else:
                print(f"  ✗ Error: {error_msg[:80]}...")
    
    return False

if __name__ == "__main__":
    check_datasets()
    success = check_delayed_data()
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    if success:
        print("✓ Found accessible data! Adjust your queries to use appropriate delays.")
    else:
        print("✗ No accessible data found. You may need a subscription for real-time data.")
        print("\nPossible solutions:")
        print("1. Check if your API key has the correct permissions")
        print("2. Use a different dataset that you have access to")
        print("3. Contact Databento support about your subscription level")