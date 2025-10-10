#!/usr/bin/env python3
"""
Check how far back tick data goes and verify NQ price levels.
"""

import os
from datetime import datetime, timedelta

from nq_futures_system.data.collectors.databento_client import DatabentoClient
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_historical_availability():
    """Check how far back we can access tick data."""
    print("\n" + "="*60)
    print("CHECKING HISTORICAL DATA AVAILABILITY")
    print("="*60)
    
    client = DatabentoClient()
    
    # Test different time periods going back
    test_periods = [
        ("1 month ago", datetime.now() - timedelta(days=30)),
        ("2 months ago", datetime.now() - timedelta(days=60)),
        ("3 months ago", datetime.now() - timedelta(days=90)),
        ("6 months ago", datetime.now() - timedelta(days=180)),
        ("1 year ago", datetime.now() - timedelta(days=365)),
        ("2 years ago", datetime.now() - timedelta(days=730)),
    ]
    
    # Find the appropriate contract for each period
    print("\nTesting tick data availability:")
    
    for period_name, test_date in test_periods:
        # Determine the likely active contract for that date
        month_code = {1: 'H', 3: 'M', 6: 'U', 9: 'Z', 12: 'Z'}
        
        # Find the next quarterly expiration
        test_month = test_date.month
        for exp_month in [3, 6, 9, 12]:
            if test_month <= exp_month:
                code = month_code[exp_month]
                break
        else:
            # Next year March
            code = 'H'
            year = test_date.year + 1
        
        if code in ['H', 'M', 'U'] and test_month <= {'H': 3, 'M': 6, 'U': 9}[code]:
            year = test_date.year
        else:
            year = test_date.year if code == 'Z' and test_month <= 12 else test_date.year + 1
            
        year_code = str(year)[-1]  # Last digit of year
        symbol = f"NQ{code}{year_code}"
        
        print(f"\n{period_name} ({test_date.strftime('%Y-%m-%d')}) - Testing {symbol}:")
        
        try:
            # Try to get one hour of tick data
            start = test_date.replace(hour=14, minute=0, second=0, microsecond=0)
            end = start + timedelta(minutes=5)  # Just 5 minutes to test
            
            trades_df = client.get_historical_data(
                symbols=[symbol],
                start=start,
                end=end,
                schema="trades"
            )
            
            if not trades_df.empty:
                print(f"  ✓ SUCCESS - {len(trades_df)} trades available")
                print(f"    Price range: ${trades_df['price'].min():,.2f} - ${trades_df['price'].max():,.2f}")
                print(f"    Avg price: ${trades_df['price'].mean():,.2f}")
            else:
                print(f"  ⚠️  No data found")
                
        except Exception as e:
            if "dataset_unavailable" in str(e):
                print(f"  ✗ Data not available (subscription required)")
            else:
                print(f"  ✗ Error: {str(e)[:60]}...")


def check_price_accuracy():
    """Verify NQ price levels are correct."""
    print("\n" + "="*60)
    print("VERIFYING NQ PRICE DATA ACCURACY")
    print("="*60)
    
    client = DatabentoClient()
    
    # Check NQU4 prices on specific date
    symbol = "NQU4"
    test_date = datetime(2024, 8, 1, 14, 0)  # Aug 1, 2024, 2PM UTC
    
    print(f"\nChecking {symbol} prices on {test_date.strftime('%Y-%m-%d %H:%M')} UTC:")
    
    try:
        # Get 1 hour of trades
        trades_df = client.get_historical_data(
            symbols=[symbol],
            start=test_date,
            end=test_date + timedelta(hours=1),
            schema="trades"
        )
        
        if not trades_df.empty:
            print(f"\nRaw price data analysis:")
            print(f"  Total trades: {len(trades_df)}")
            print(f"  Price column min: {trades_df['price'].min()}")
            print(f"  Price column max: {trades_df['price'].max()}")
            print(f"  Price column mean: {trades_df['price'].mean()}")
            
            # Check if prices need scaling
            # Databento often provides prices in fixed-point format
            if trades_df['price'].max() < 100000:  # Seems like prices might need scaling
                print(f"\n⚠️  Prices appear to be in scaled format!")
                print(f"  If divided by 100: ${trades_df['price'].min()/100:,.2f} - ${trades_df['price'].max()/100:,.2f}")
                print(f"  If divided by 1000: ${trades_df['price'].min()/1000:,.2f} - ${trades_df['price'].max()/1000:,.2f}")
            
            # Show sample trades
            print(f"\nSample trades (first 10):")
            print(trades_df[['price', 'size']].head(10))
            
            # Get OHLCV to compare
            print(f"\nComparing with OHLCV data:")
            ohlcv_df = client.get_historical_data(
                symbols=[symbol],
                start=test_date,
                end=test_date + timedelta(hours=1),
                schema="ohlcv-1m"
            )
            
            if not ohlcv_df.empty:
                print(f"  OHLCV High column: {ohlcv_df['high'].max()}")
                print(f"  OHLCV Low column: {ohlcv_df['low'].min()}")
                print(f"  OHLCV sample:")
                print(ohlcv_df[['open', 'high', 'low', 'close']].head())
                
    except Exception as e:
        print(f"Error: {e}")


def check_known_dates():
    """Check some known market dates to understand pricing."""
    print("\n" + "="*60)
    print("CHECKING KNOWN MARKET EVENTS")  
    print("="*60)
    
    client = DatabentoClient()
    
    # August 5, 2024 was a major market selloff day
    print("\nChecking August 5, 2024 (known market volatility day):")
    
    vol_date = datetime(2024, 8, 5, 14, 0)  # 2PM UTC
    
    try:
        ohlcv_df = client.get_historical_data(
            symbols=["NQU4"],
            start=vol_date,
            end=vol_date + timedelta(hours=4),
            schema="ohlcv-1m"
        )
        
        if not ohlcv_df.empty:
            print(f"  Data points: {len(ohlcv_df)}")
            print(f"  High: {ohlcv_df['high'].max()}")
            print(f"  Low: {ohlcv_df['low'].min()}")
            print(f"  Volatility: {ohlcv_df['high'].max() - ohlcv_df['low'].min()} points")
            
            # Historical context: NQ was trading around 17,000-18,000 in early August 2024
            if ohlcv_df['high'].max() < 100000:
                print(f"\n  Scaled prices detected!")
                print(f"  Actual High: ${ohlcv_df['high'].max()/100:,.2f}")
                print(f"  Actual Low: ${ohlcv_df['low'].min()/100:,.2f}")
                
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    print("DATABENTO DATA INVESTIGATION")
    print(f"API Key: {os.getenv('DATABENTO_API_KEY')[:15]}...")
    
    # Check how far back data goes
    check_historical_availability()
    
    # Verify price accuracy
    check_price_accuracy()
    
    # Check known dates
    check_known_dates()
    
    print("\n" + "="*60)
    print("INVESTIGATION COMPLETE")
    print("="*60)