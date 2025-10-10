#!/usr/bin/env python3
"""
Test Databento integration with historical data that we have access to.
This version uses data from 2-3 months ago which is accessible with the current API key.
"""

import sys
import os
from datetime import datetime, timedelta

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data.collectors.databento_client import DatabentoClient
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_historical_data():
    """Test historical data retrieval with accessible date ranges."""
    print("\n" + "="*60)
    print("DATABENTO HISTORICAL DATA TEST")
    print("="*60)
    
    client = DatabentoClient()
    
    try:
        # Use dates from 2-3 months ago (August 2024)
        end_date = datetime(2024, 8, 15)
        start_date = datetime(2024, 8, 1)
        
        print(f"\nTesting period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        print("(Using historical data that's accessible with current API key)")
        
        # Test 1: Get available NQ contracts
        print("\n1. Finding available NQ contracts...")
        
        # We know NQU4 (September 2024) was active in August
        test_symbols = ["NQU4", "NQZ4", "NQH5"]
        
        for symbol in test_symbols:
            try:
                # Get some trades to verify the symbol
                trades = client.get_historical_data(
                    symbols=[symbol],
                    start=start_date,
                    end=start_date + timedelta(hours=1),
                    schema="trades"
                )
                
                if not trades.empty:
                    print(f"   ✓ {symbol} - Active contract ({len(trades)} trades found)")
                else:
                    print(f"   ⚠️  {symbol} - No trades found")
                    
            except Exception as e:
                print(f"   ✗ {symbol} - Error: {str(e)[:50]}...")
        
        # Test 2: Get OHLCV data
        active_symbol = "NQU4"  # September 2024 contract
        print(f"\n2. Fetching 1-minute OHLCV data for {active_symbol}...")
        
        ohlcv_df = client.get_historical_data(
            symbols=[active_symbol],
            start=start_date,
            end=start_date + timedelta(days=1),
            schema="ohlcv-1m"
        )
        
        if not ohlcv_df.empty:
            print(f"   ✓ Retrieved {len(ohlcv_df)} 1-minute bars")
            print(f"\n   Sample data (first 5 bars):")
            print(ohlcv_df.head())
            print(f"\n   Summary statistics:")
            print(f"   - Date range: {ohlcv_df.index.min()} to {ohlcv_df.index.max()}")
            print(f"   - Price range: ${ohlcv_df['low'].min():,.2f} - ${ohlcv_df['high'].max():,.2f}")
            print(f"   - Total volume: {ohlcv_df['volume'].sum():,} contracts")
            print(f"   - Average bar volume: {ohlcv_df['volume'].mean():,.0f} contracts")
        
        # Test 3: Get trade tick data
        print(f"\n3. Fetching trade tick data for {active_symbol}...")
        
        # Get one hour of trades
        trade_start = datetime(2024, 8, 1, 14, 0)  # 2 PM UTC
        trade_end = datetime(2024, 8, 1, 15, 0)    # 3 PM UTC
        
        trades_df = client.get_historical_data(
            symbols=[active_symbol],
            start=trade_start,
            end=trade_end,
            schema="trades"
        )
        
        if not trades_df.empty:
            print(f"   ✓ Retrieved {len(trades_df)} trades")
            print(f"\n   Trade statistics:")
            print(f"   - Time range: {trades_df.index.min()} to {trades_df.index.max()}")
            print(f"   - Price range: ${trades_df['price'].min():,.2f} - ${trades_df['price'].max():,.2f}")
            print(f"   - Average trade size: {trades_df['size'].mean():.1f} contracts")
            print(f"   - Largest trade: {trades_df['size'].max()} contracts")
            
            # Show some large trades
            large_trades = trades_df[trades_df['size'] >= 10].head()
            if not large_trades.empty:
                print(f"\n   Sample large trades (>= 10 contracts):")
                for idx, trade in large_trades.iterrows():
                    print(f"   - {idx}: {trade['size']} contracts @ ${trade['price']:,.2f}")
        
        # Test 4: Multiple symbols
        print(f"\n4. Testing multiple symbols simultaneously...")
        
        multi_symbols = ["NQU4", "ESU4"]  # NQ and ES September 2024
        
        multi_df = client.get_historical_data(
            symbols=multi_symbols,
            start=start_date,
            end=start_date + timedelta(hours=1),
            schema="ohlcv-1m"
        )
        
        if not multi_df.empty:
            print(f"   ✓ Retrieved {len(multi_df)} total bars")
            
            # Check data for each symbol
            for symbol in multi_symbols:
                symbol_data = multi_df[multi_df['symbol'] == symbol]
                if not symbol_data.empty:
                    avg_price = (symbol_data['high'] + symbol_data['low']) / 2
                    print(f"   - {symbol}: {len(symbol_data)} bars, avg price: ${avg_price.mean():,.2f}")
        
        return True
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_data_schemas():
    """Test different data schemas available."""
    print("\n" + "="*60)
    print("TESTING DIFFERENT DATA SCHEMAS")
    print("="*60)
    
    client = DatabentoClient()
    
    # Test date
    test_date = datetime(2024, 8, 1, 14, 0)
    symbol = "NQU4"
    
    schemas = {
        "trades": "Individual trades",
        "ohlcv-1m": "1-minute OHLCV bars",
        "ohlcv-1h": "1-hour OHLCV bars",
        "bbo": "Best bid/offer quotes"
    }
    
    for schema, description in schemas.items():
        print(f"\nTesting {schema} ({description})...")
        
        try:
            df = client.get_historical_data(
                symbols=[symbol],
                start=test_date,
                end=test_date + timedelta(minutes=10),
                schema=schema
            )
            
            if not df.empty:
                print(f"  ✓ SUCCESS - Retrieved {len(df)} records")
                print(f"    Columns: {', '.join(df.columns[:5])}...")
            else:
                print(f"  ⚠️  No data returned")
                
        except Exception as e:
            print(f"  ✗ Error: {str(e)[:60]}...")


def main():
    """Run all tests."""
    print("NQ FUTURES DATABENTO INTEGRATION TEST")
    print("Using historical data (2-3 months old)")
    print(f"API Key: {os.getenv('DATABENTO_API_KEY')[:15]}...")
    
    # Test basic historical data
    hist_success = test_historical_data()
    
    # Test different schemas
    test_data_schemas()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    if hist_success:
        print("✅ Historical data access is working!")
        print("\nNOTE: This API key has access to historical data (2+ months old)")
        print("For real-time or recent data, you'll need to upgrade your Databento subscription.")
    else:
        print("❌ Tests failed. Check the errors above.")
    
    print("\nNext steps:")
    print("1. You can develop and test strategies using historical data")
    print("2. Once ready for live trading, upgrade to a real-time data subscription")
    print("3. The same code will work with real-time data - just change the dates!")


if __name__ == "__main__":
    main()