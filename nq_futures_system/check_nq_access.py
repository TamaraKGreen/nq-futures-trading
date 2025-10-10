#!/usr/bin/env python3
"""Check specific NQ access and find the correct symbol format."""

import databento as db
from datetime import datetime, timedelta
import os
import sys

from nq_futures_system.data.collectors.databento_client import DatabentoClient

def check_nq_symbols():
    """Try different NQ symbol formats."""
    client = DatabentoClient()
    
    print("Checking NQ symbol formats and data access...")
    print("="*60)
    
    # Different symbol formats to try
    nq_symbols = [
        "NQ",          # Base symbol
        "NQZ4",        # December 2024
        "NQH5",        # March 2025
        "NQM5",        # June 2025
        "NQ.c.0",      # Continuous front month
        "ESZ4",        # Try ES for comparison
        "ES",          # ES base symbol
    ]
    
    # Try different time periods
    time_periods = [
        ("2 months ago", datetime(2024, 8, 1), datetime(2024, 8, 2)),
        ("3 months ago", datetime(2024, 7, 1), datetime(2024, 7, 2)),
        ("6 months ago", datetime(2024, 4, 1), datetime(2024, 4, 2)),
    ]
    
    for start_date, end_date in [(tp[1], tp[2]) for tp in time_periods]:
        print(f"\nTrying period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        print("-" * 50)
        
        for symbol in nq_symbols:
            try:
                print(f"  Testing {symbol}...", end="")
                
                # Try to get definition data
                data = client.historical.timeseries.get_range(
                    dataset="GLBX.MDP3",
                    symbols=[symbol],
                    schema="definition",
                    start=start_date,
                    end=end_date,
                    stype_in="raw_symbol",
                    limit=1
                )
                
                df = data.to_df()
                if not df.empty:
                    print(f" ✓ SUCCESS - Found data!")
                    
                    # Try to get some trades
                    trades = client.historical.timeseries.get_range(
                        dataset="GLBX.MDP3",
                        symbols=[symbol],
                        schema="trades",
                        start=start_date,
                        end=end_date,
                        stype_in="raw_symbol",
                        limit=10
                    )
                    
                    trades_df = trades.to_df()
                    if not trades_df.empty:
                        print(f"     - Retrieved {len(trades_df)} trades")
                        if 'price' in trades_df.columns:
                            avg_price = trades_df['price'].mean()
                            print(f"     - Average price: ${avg_price:,.2f}")
                else:
                    print(" ⚠️  No data found")
                    
            except Exception as e:
                error_msg = str(e)
                if "dataset_unavailable" in error_msg:
                    print(" ✗ Subscription required")
                elif "symbology_invalid" in error_msg:
                    print(" ✗ Invalid symbol")
                else:
                    print(f" ✗ Error: {error_msg[:40]}...")

def check_metadata_access():
    """Check if we can access metadata/catalog."""
    client = DatabentoClient()
    
    print("\n\nChecking metadata access...")
    print("="*60)
    
    try:
        # Try to list available datasets
        print("Checking available data for this API key...")
        
        # Use a date we know has data (older date)
        test_date = datetime(2024, 1, 1)
        
        # Try different approaches
        print("\nTrying symbology resolution for NQ...")
        data = client.historical.metadata.get_symbology(
            dataset="GLBX.MDP3",
            symbols=["NQ"],
            start=test_date,
            end=test_date + timedelta(days=1),
            stype_in="raw_symbol"
        )
        
        print("✓ Symbology request successful")
        
    except AttributeError:
        print("✗ Metadata API not available in this version")
    except Exception as e:
        print(f"✗ Error: {e}")

if __name__ == "__main__":
    check_nq_symbols()
    check_metadata_access()
    
    print("\n" + "="*60)
    print("RECOMMENDATIONS:")
    print("="*60)
    print("1. This API key appears to have limited access to CME futures")
    print("2. You may need to:")
    print("   - Upgrade your Databento subscription for real-time CME data")
    print("   - Use delayed data (if available with your plan)")
    print("   - Contact Databento support to confirm your access level")
    print("\nAPI Key being used:", os.getenv('DATABENTO_API_KEY')[:15], "...")