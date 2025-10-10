#!/usr/bin/env python3
"""
Real-world example of intraday calculations using unified live + historical data.

Shows how the unified data manager makes complex intraday analysis simple.
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List
import numpy as np


class IntradayAnalyzer:
    """
    Example of intraday calculations that seamlessly use both historical and live data.
    
    This demonstrates the power of the unified data manager - your analysis code
    doesn't need to know or care where the data comes from!
    """
    
    def __init__(self, unified_manager):
        self.data_manager = unified_manager
    
    def calculate_volume_profile(self, symbol: str, lookback_hours: int = 24) -> Dict:
        """
        Calculate volume profile for the last N hours.
        
        This is a perfect example of why unified data is powerful:
        - Might need historical data (if it's early in the day)
        - Might need live data (for current session)
        - Often needs BOTH (for full 24-hour profile)
        """
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=lookback_hours)
        
        print(f"\n📊 Volume Profile Analysis: {symbol}")
        print(f"   Period: {start_time} to {end_time} ({lookback_hours}h)")
        
        # Get data - unified manager handles historical vs live automatically!
        trades = self.data_manager.get_data(
            symbols=[symbol],
            start=start_time,
            end=end_time,
            schema="trades"
        )
        
        if trades.empty:
            return {"error": "No data available"}
        
        print(f"   Data points: {len(trades)} trades")
        print(f"   Price range: ${trades['price'].min():.2f} - ${trades['price'].max():.2f}")
        
        # Calculate volume at each price level
        price_levels = np.arange(
            trades['price'].min(),
            trades['price'].max() + 0.25,
            0.25  # NQ moves in 0.25 increments
        )
        
        volume_by_price = {}
        for price in price_levels:
            # Volume within 0.125 of this price level
            volume = trades[
                (trades['price'] >= price - 0.125) & 
                (trades['price'] < price + 0.125)
            ]['size'].sum()
            
            if volume > 0:
                volume_by_price[price] = volume
        
        # Find value area (70% of volume)
        total_volume = sum(volume_by_price.values())
        value_area_volume = total_volume * 0.7
        
        # Sort by volume to find high-volume prices
        sorted_prices = sorted(volume_by_price.items(), key=lambda x: x[1], reverse=True)
        
        value_area_prices = []
        cumulative_volume = 0
        
        for price, volume in sorted_prices:
            value_area_prices.append(price)
            cumulative_volume += volume
            if cumulative_volume >= value_area_volume:
                break
        
        # Find the price range of value area
        vah = max(value_area_prices)  # Value Area High
        val = min(value_area_prices)  # Value Area Low
        poc = max(volume_by_price.items(), key=lambda x: x[1])[0]  # Point of Control
        
        return {
            "total_volume": total_volume,
            "total_trades": len(trades),
            "point_of_control": poc,
            "value_area_high": vah,
            "value_area_low": val,
            "value_area_range": vah - val,
            "current_price": trades['price'].iloc[-1],
            "profile": volume_by_price,
            "data_sources": self._identify_data_sources(trades, start_time)
        }
    
    def detect_buyer_aggression(self, symbol: str, lookback_minutes: int = 30) -> Dict:
        """
        Detect large buyer aggression in recent trading.
        
        Another great example - needs very recent data that might be:
        - Partially in cache (older minutes)
        - Partially in live buffer (latest minutes)
        """
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=lookback_minutes)
        
        print(f"\n⚡ Buyer Aggression Analysis: {symbol}")
        print(f"   Period: Last {lookback_minutes} minutes")
        
        # Get recent trades - seamlessly combines sources
        trades = self.data_manager.get_data(
            symbols=[symbol],
            start=start_time,
            end=end_time,
            schema="trades"
        )
        
        if trades.empty:
            return {"error": "No recent trades"}
        
        # Define "large" trades (customize based on symbol)
        large_trade_threshold = 10  # contracts for NQ
        
        # Find large trades
        large_trades = trades[trades['size'] >= large_trade_threshold]
        
        if large_trades.empty:
            return {"no_large_trades": True}
        
        # Analyze the large trades
        total_large_volume = large_trades['size'].sum()
        avg_trade_size = large_trades['size'].mean()
        largest_trade = large_trades['size'].max()
        
        # Recent activity (last 5 minutes)
        recent_cutoff = end_time - timedelta(minutes=5)
        recent_large = large_trades[large_trades.index >= recent_cutoff]
        
        # Price impact analysis
        price_before_large = trades['price'].iloc[0] if len(trades) > 0 else 0
        price_after_large = trades['price'].iloc[-1] if len(trades) > 0 else 0
        price_impact = price_after_large - price_before_large
        
        return {
            "period_minutes": lookback_minutes,
            "total_trades": len(trades),
            "large_trades_count": len(large_trades),
            "large_trade_threshold": large_trade_threshold,
            "total_large_volume": total_large_volume,
            "avg_large_trade_size": avg_trade_size,
            "largest_single_trade": largest_trade,
            "recent_large_trades": len(recent_large),
            "price_impact": price_impact,
            "latest_price": price_after_large,
            "aggression_score": self._calculate_aggression_score(large_trades),
            "data_sources": self._identify_data_sources(trades, start_time)
        }
    
    def calculate_real_time_vwap(self, symbol: str, hours_back: int = 4) -> Dict:
        """
        Calculate Volume Weighted Average Price with live updates.
        
        Perfect for intraday trading - needs historical session data plus
        real-time updates as new trades come in.
        """
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)
        
        print(f"\n📈 Real-time VWAP: {symbol}")
        print(f"   Session period: {hours_back} hours")
        
        # Get all trades for the period
        trades = self.data_manager.get_data(
            symbols=[symbol],
            start=start_time,
            end=end_time,
            schema="trades"
        )
        
        if trades.empty:
            return {"error": "No trades for VWAP calculation"}
        
        # Calculate VWAP
        trades['value'] = trades['price'] * trades['size']
        total_value = trades['value'].sum()
        total_volume = trades['size'].sum()
        vwap = total_value / total_volume if total_volume > 0 else 0
        
        # Current price vs VWAP
        current_price = trades['price'].iloc[-1]
        vwap_deviation = current_price - vwap
        vwap_deviation_pct = (vwap_deviation / vwap) * 100 if vwap > 0 else 0
        
        # Intraday high/low
        session_high = trades['price'].max()
        session_low = trades['price'].min()
        
        return {
            "vwap": vwap,
            "current_price": current_price,
            "deviation_points": vwap_deviation,
            "deviation_percent": vwap_deviation_pct,
            "session_high": session_high,
            "session_low": session_low,
            "total_volume": total_volume,
            "total_trades": len(trades),
            "above_vwap": current_price > vwap,
            "data_span_hours": hours_back,
            "data_sources": self._identify_data_sources(trades, start_time)
        }
    
    def _calculate_aggression_score(self, large_trades: pd.DataFrame) -> float:
        """Simple aggression scoring based on trade size and frequency."""
        if large_trades.empty:
            return 0.0
        
        # Score based on:
        # 1. Average trade size (bigger = more aggressive)
        # 2. Frequency (more frequent = more aggressive)
        # 3. Recent activity (recent trades weighted higher)
        
        avg_size = large_trades['size'].mean()
        trade_count = len(large_trades)
        
        # Simple scoring formula (customize as needed)
        base_score = (avg_size / 10) + (trade_count / 5)
        
        # Cap at 10
        return min(base_score, 10.0)
    
    def _identify_data_sources(self, trades: pd.DataFrame, start_time: datetime) -> Dict:
        """Identify what data came from cache vs live feed."""
        if trades.empty:
            return {"historical": 0, "live": 0}
        
        live_cutoff = self.data_manager.get_live_cutoff()
        
        historical_trades = trades[trades.index < live_cutoff]
        live_trades = trades[trades.index >= live_cutoff]
        
        return {
            "historical": len(historical_trades),
            "live": len(live_trades),
            "live_cutoff": live_cutoff,
            "seamless": True
        }


def demonstrate_intraday_calculations():
    """Show how intraday calculations work with unified data."""
    
    print("INTRADAY CALCULATIONS WITH UNIFIED DATA")
    print("=" * 60)
    
    print("\n🎯 THE POWER: Your analysis code stays simple!")
    print("-" * 50)
    
    # Simulate the analyzer (can't run real calculations without live data)
    example_results = {
        "volume_profile": {
            "point_of_control": 25275.0,
            "value_area_high": 25285.0,
            "value_area_low": 25265.0,
            "total_volume": 15420,
            "data_sources": {"historical": 8230, "live": 7190}
        },
        "buyer_aggression": {
            "large_trades_count": 12,
            "total_large_volume": 156,
            "aggression_score": 7.2,
            "data_sources": {"historical": 45, "live": 89}
        },
        "real_time_vwap": {
            "vwap": 25272.50,
            "current_price": 25275.25,
            "deviation_points": 2.75,
            "above_vwap": True,
            "data_sources": {"historical": 1205, "live": 340}
        }
    }
    
    print("\n📊 Example Analysis Results:")
    print("-" * 40)
    
    for analysis, results in example_results.items():
        print(f"\n{analysis.upper()}:")
        
        # Show key metrics
        for key, value in results.items():
            if key != "data_sources":
                print(f"   {key}: {value}")
        
        # Show data source breakdown
        sources = results["data_sources"]
        total = sources["historical"] + sources["live"]
        hist_pct = (sources["historical"] / total * 100) if total > 0 else 0
        live_pct = (sources["live"] / total * 100) if total > 0 else 0
        
        print(f"   📊 Data: {sources['historical']} historical ({hist_pct:.0f}%) + {sources['live']} live ({live_pct:.0f}%)")
        print(f"   ✨ Seamlessly combined from multiple sources!")
    
    print(f"\n💡 KEY INSIGHTS:")
    print(f"   - Same analysis code works for any time period")
    print(f"   - Data source switching is completely transparent")
    print(f"   - Real-time updates without code changes")
    print(f"   - Historical context + live precision")
    
    print(f"\n🔄 TYPICAL INTRADAY WORKFLOW:")
    print(f"   Morning: Analyze overnight levels (historical)")
    print(f"   Trading: Monitor live aggression (live + historical)")
    print(f"   Intraday: VWAP calculations (seamless combination)")
    print(f"   All day: Same simple code, automatic data management!")


def show_code_simplicity():
    """Show how simple the code becomes with unified data."""
    
    print("\n" + "=" * 60)
    print("CODE SIMPLICITY COMPARISON")
    print("=" * 60)
    
    print("\n❌ WITHOUT UNIFIED DATA (Complex):")
    print("-" * 40)
    print("""
    # User has to manage data sources manually
    if requested_time < live_cutoff:
        data = cached_client.get_historical_data(...)
    elif requested_time > live_cutoff:
        data = live_buffer.get_recent_data(...)
    else:
        # Complex: combine both sources
        hist_data = cached_client.get_historical_data(...)
        live_data = live_buffer.get_recent_data(...)
        data = merge_and_sort(hist_data, live_data)
    
    # Calculate volume profile
    volume_profile = analyze_volume(data)
    """)
    
    print("\n✅ WITH UNIFIED DATA (Simple):")
    print("-" * 40)
    print("""
    # User doesn't think about data sources
    data = manager.get_data(symbols, start, end)
    
    # Calculate volume profile
    volume_profile = analyze_volume(data)
    """)
    
    print(f"\n🎯 RESULT:")
    print(f"   - 90% less code")
    print(f"   - No data source management")
    print(f"   - No complex merging logic")
    print(f"   - Focus on analysis, not plumbing!")


if __name__ == "__main__":
    demonstrate_intraday_calculations()
    show_code_simplicity()