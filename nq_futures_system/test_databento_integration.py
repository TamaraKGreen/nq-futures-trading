#!/usr/bin/env python3
"""
Test the Databento integration for NQ futures.
Tests both live and historical data access.
"""

import asyncio
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


async def test_historical_data(client):
    """Test historical data retrieval."""
    print("\n" + "="*60)
    print("TESTING HISTORICAL DATA ACCESS")
    print("="*60)
    
    try:
        # Get the current front-month contract
        front_month = client.get_continuous_contract("NQ")
        print(f"✓ Current front-month NQ contract: {front_month}")
        
        # Get available symbols
        print("\nChecking available NQ symbols...")
        symbols = client.get_available_symbols("NQ")
        futures_only = [s for s in symbols if s['instrument_class'] == 'FUTURE']
        print(f"✓ Found {len(futures_only)} NQ futures contracts")
        for future in futures_only[:3]:  # Show first 3
            print(f"  - {future['symbol']} (expires: {future['expiration']})")
        
        # Get 1-minute OHLCV data for the last day
        print(f"\nFetching 1-minute OHLCV data for {front_month}...")
        end = datetime.utcnow() - timedelta(hours=1)  # Ensure data is available
        start = end - timedelta(days=1)
        
        ohlcv_df = client.get_historical_data(
            symbols=[front_month],
            start=start,
            end=end,
            schema="ohlcv-1m"
        )
        
        if not ohlcv_df.empty:
            print(f"✓ Retrieved {len(ohlcv_df)} 1-minute bars")
            print("\nLatest 5 bars:")
            print(ohlcv_df.tail())
            print(f"\nPrice range: ${ohlcv_df['low'].min():,.2f} - ${ohlcv_df['high'].max():,.2f}")
            print(f"Total volume: {ohlcv_df['volume'].sum():,}")
        
        # Get trade data for the last hour
        print(f"\nFetching trade data for {front_month}...")
        trade_end = datetime.utcnow() - timedelta(hours=1)  # Ensure data is available
        trade_start = trade_end - timedelta(hours=1)
        
        trades_df = client.get_historical_data(
            symbols=[front_month],
            start=trade_start,
            end=trade_end,
            schema="trades"
        )
        
        if not trades_df.empty:
            print(f"✓ Retrieved {len(trades_df)} trades")
            print("\nLatest 5 trades:")
            print(trades_df.tail())
            
            # Calculate some statistics
            print("\nTrade Statistics:")
            print(f"Average trade size: {trades_df['size'].mean():.2f} contracts")
            print(f"Largest trade: {trades_df['size'].max()} contracts")
            print(f"Price range: ${trades_df['price'].min():,.2f} - ${trades_df['price'].max():,.2f}")
        
        return True
        
    except Exception as e:
        logger.error(f"Historical data test failed: {e}")
        return False


async def test_live_data(client):
    """Test live data subscription (runs for 10 seconds)."""
    print("\n" + "="*60)
    print("TESTING LIVE DATA ACCESS")
    print("="*60)
    
    try:
        # Get front-month contract
        front_month = client.get_continuous_contract("NQ")
        print(f"✓ Subscribing to live trades for {front_month}")
        
        # Counter for received messages
        message_count = 0
        
        async def count_trades(record):
            nonlocal message_count
            message_count += 1
            if message_count <= 5:  # Print first 5 trades
                if hasattr(record, 'price') and hasattr(record, 'size'):
                    print(f"  Trade #{message_count}: {record.symbol} @ ${record.price/1e9:,.2f} x {record.size}")
        
        # Subscribe to live trades
        sub_id = await client.subscribe_live(
            symbols=[front_month],
            schema="trades",
            callback=count_trades
        )
        
        print("✓ Subscription active. Listening for 10 seconds...")
        print("  (Note: Markets must be open to receive live data)")
        
        # Start live feed in background
        feed_task = asyncio.create_task(client.start_live_feed())
        
        # Wait for 10 seconds
        await asyncio.sleep(10)
        
        # Stop the feed
        client.stop_live_feed()
        feed_task.cancel()
        
        print(f"\n✓ Received {message_count} messages in 10 seconds")
        
        if message_count == 0:
            print("  ℹ️  No messages received. This is normal if markets are closed.")
            print("     CME trading hours: Sunday 6pm - Friday 5pm ET (with breaks)")
        
        return True
        
    except Exception as e:
        logger.error(f"Live data test failed: {e}")
        return False


async def main():
    """Run all tests."""
    print("NQ FUTURES DATABENTO INTEGRATION TEST")
    print(f"Timestamp: {datetime.now()}")
    
    # Initialize client
    try:
        client = DatabentoClient()
        print("✓ Databento client initialized successfully")
    except Exception as e:
        print(f"✗ Failed to initialize client: {e}")
        print("  Make sure DATABENTO_API_KEY is set in config/.env")
        return
    
    # Test historical data
    hist_success = await test_historical_data(client)
    
    # Test live data
    live_success = await test_live_data(client)
    
    # Clean up
    client.close()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Historical Data: {'✓ PASSED' if hist_success else '✗ FAILED'}")
    print(f"Live Data: {'✓ PASSED' if live_success else '✗ FAILED'}")
    
    if hist_success and live_success:
        print("\n✅ All tests passed! Databento integration is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Check the logs above for details.")


if __name__ == "__main__":
    asyncio.run(main())