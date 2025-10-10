"""
Gap Detection Utility for Missing Cache Data

Provides intelligent gap detection and filling for market data cache.
Key features:
- Detects missing data ranges in cache
- Accounts for market holidays and trading hours
- Provides cost-optimized batch filling strategies
- Handles different data schemas and symbols
"""

import os
import sys
from datetime import datetime, date, timedelta
from typing import List, Dict, Tuple, Optional, Set
import pandas as pd
import logging
from dataclasses import dataclass

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.cache.cache_manager import IncrementalCacheManager

logger = logging.getLogger(__name__)


@dataclass
class DataGap:
    """Represents a gap in cached data."""
    symbol: str
    schema: str
    start_date: date
    end_date: date
    trading_days_missing: int
    estimated_cost: float
    priority: str  # 'high', 'medium', 'low'


@dataclass
class GapFillStrategy:
    """Strategy for filling data gaps efficiently."""
    batch_size_days: int
    max_concurrent_requests: int
    cost_threshold: float
    prioritize_recent: bool


class MarketCalendar:
    """Simple market calendar for US equity markets."""
    
    @staticmethod
    def is_trading_day(date_obj: date) -> bool:
        """
        Check if a date is a trading day.
        
        Note: This is a simplified implementation.
        Production systems should use a proper market calendar library.
        """
        # Skip weekends
        if date_obj.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Common US holidays (simplified)
        holidays_2024_2025 = {
            # 2024
            date(2024, 1, 1),   # New Year's Day
            date(2024, 1, 15),  # MLK Day
            date(2024, 2, 19),  # Presidents Day
            date(2024, 3, 29),  # Good Friday
            date(2024, 5, 27),  # Memorial Day
            date(2024, 6, 19),  # Juneteenth
            date(2024, 7, 4),   # Independence Day
            date(2024, 9, 2),   # Labor Day
            date(2024, 11, 28), # Thanksgiving
            date(2024, 12, 25), # Christmas
            
            # 2025
            date(2025, 1, 1),   # New Year's Day
            date(2025, 1, 20),  # MLK Day
            date(2025, 2, 17),  # Presidents Day
            date(2025, 4, 18),  # Good Friday
            date(2025, 5, 26),  # Memorial Day
            date(2025, 6, 19),  # Juneteenth
            date(2025, 7, 4),   # Independence Day
            date(2025, 9, 1),   # Labor Day
            date(2025, 11, 27), # Thanksgiving
            date(2025, 12, 25), # Christmas
        }
        
        return date_obj not in holidays_2024_2025
    
    @staticmethod
    def get_trading_days(start_date: date, end_date: date) -> List[date]:
        """Get list of trading days between start and end dates."""
        trading_days = []
        current = start_date
        
        while current <= end_date:
            if MarketCalendar.is_trading_day(current):
                trading_days.append(current)
            current += timedelta(days=1)
        
        return trading_days


class GapDetector:
    """Detects and analyzes gaps in cached market data."""
    
    def __init__(self, cache_manager: IncrementalCacheManager):
        """
        Initialize gap detector.
        
        Args:
            cache_manager: Cache manager instance to analyze
        """
        self.cache_manager = cache_manager
        self.market_calendar = MarketCalendar()
        
        # Cost estimates per schema (approximate)
        self.schema_costs = {
            'trades': 0.20,      # $0.20 per day
            'ohlcv-1m': 0.02,    # $0.02 per day
            'ohlcv-1h': 0.01,    # $0.01 per day
            'bbo': 0.15,         # $0.15 per day
        }
    
    def detect_gaps(self, symbols: List[str], schemas: List[str],
                   analysis_period_days: int = 30) -> List[DataGap]:
        """
        Detect gaps in cached data for given symbols and schemas.
        
        Args:
            symbols: List of symbols to analyze
            schemas: List of data schemas to check
            analysis_period_days: How many days back to analyze
            
        Returns:
            List of detected data gaps
        """
        logger.info(f"Detecting gaps for {len(symbols)} symbols, {len(schemas)} schemas")
        logger.info(f"Analysis period: {analysis_period_days} days")
        
        end_date = date.today() - timedelta(days=1)  # Yesterday
        start_date = end_date - timedelta(days=analysis_period_days)
        
        gaps = []
        
        for symbol in symbols:
            for schema in schemas:
                symbol_gaps = self._detect_symbol_gaps(
                    symbol, schema, start_date, end_date
                )
                gaps.extend(symbol_gaps)
        
        # Sort gaps by priority and cost
        gaps.sort(key=lambda g: (g.priority, -g.estimated_cost))
        
        logger.info(f"Detected {len(gaps)} data gaps")
        return gaps
    
    def _detect_symbol_gaps(self, symbol: str, schema: str,
                           start_date: date, end_date: date) -> List[DataGap]:
        """Detect gaps for a specific symbol and schema."""
        
        # Get all trading days in the period
        trading_days = self.market_calendar.get_trading_days(start_date, end_date)
        
        # Find which days are missing from cache
        missing_days = []
        for trading_day in trading_days:
            if not self.cache_manager.has_cached_date(symbol, schema, trading_day):
                missing_days.append(trading_day)
        
        if not missing_days:
            return []  # No gaps
        
        # Group consecutive missing days into gaps
        gaps = self._group_consecutive_dates(missing_days)
        
        # Convert to DataGap objects
        data_gaps = []
        for gap_start, gap_end in gaps:
            gap_trading_days = len([d for d in missing_days if gap_start <= d <= gap_end])
            estimated_cost = gap_trading_days * self.schema_costs.get(schema, 0.10)
            
            # Determine priority based on recency and size
            days_ago = (date.today() - gap_end).days
            if days_ago <= 7:
                priority = 'high'
            elif days_ago <= 30:
                priority = 'medium'
            else:
                priority = 'low'
            
            data_gap = DataGap(
                symbol=symbol,
                schema=schema,
                start_date=gap_start,
                end_date=gap_end,
                trading_days_missing=gap_trading_days,
                estimated_cost=estimated_cost,
                priority=priority
            )
            data_gaps.append(data_gap)
        
        return data_gaps
    
    def _group_consecutive_dates(self, dates: List[date]) -> List[Tuple[date, date]]:
        """Group consecutive dates into ranges."""
        if not dates:
            return []
        
        sorted_dates = sorted(dates)
        groups = []
        current_start = sorted_dates[0]
        current_end = sorted_dates[0]
        
        for i in range(1, len(sorted_dates)):
            if sorted_dates[i] == current_end + timedelta(days=1):
                # Consecutive date, extend current group
                current_end = sorted_dates[i]
            else:
                # Gap found, start new group
                groups.append((current_start, current_end))
                current_start = sorted_dates[i]
                current_end = sorted_dates[i]
        
        # Add the last group
        groups.append((current_start, current_end))
        return groups
    
    def analyze_gaps(self, gaps: List[DataGap]) -> Dict:
        """
        Analyze detected gaps and provide summary statistics.
        
        Args:
            gaps: List of detected gaps
            
        Returns:
            Dictionary with gap analysis
        """
        if not gaps:
            return {
                'total_gaps': 0,
                'total_cost': 0.0,
                'by_priority': {},
                'by_symbol': {},
                'by_schema': {},
                'recommendations': []
            }
        
        total_cost = sum(gap.estimated_cost for gap in gaps)
        total_trading_days = sum(gap.trading_days_missing for gap in gaps)
        
        # Group by priority
        by_priority = {}
        for gap in gaps:
            if gap.priority not in by_priority:
                by_priority[gap.priority] = {'count': 0, 'cost': 0.0, 'days': 0}
            by_priority[gap.priority]['count'] += 1
            by_priority[gap.priority]['cost'] += gap.estimated_cost
            by_priority[gap.priority]['days'] += gap.trading_days_missing
        
        # Group by symbol
        by_symbol = {}
        for gap in gaps:
            if gap.symbol not in by_symbol:
                by_symbol[gap.symbol] = {'count': 0, 'cost': 0.0, 'days': 0}
            by_symbol[gap.symbol]['count'] += 1
            by_symbol[gap.symbol]['cost'] += gap.estimated_cost
            by_symbol[gap.symbol]['days'] += gap.trading_days_missing
        
        # Group by schema
        by_schema = {}
        for gap in gaps:
            if gap.schema not in by_schema:
                by_schema[gap.schema] = {'count': 0, 'cost': 0.0, 'days': 0}
            by_schema[gap.schema]['count'] += 1
            by_schema[gap.schema]['cost'] += gap.estimated_cost
            by_schema[gap.schema]['days'] += gap.trading_days_missing
        
        # Generate recommendations
        recommendations = self._generate_recommendations(gaps, by_priority, by_schema)
        
        return {
            'total_gaps': len(gaps),
            'total_cost': total_cost,
            'total_trading_days': total_trading_days,
            'by_priority': by_priority,
            'by_symbol': by_symbol,
            'by_schema': by_schema,
            'recommendations': recommendations
        }
    
    def _generate_recommendations(self, gaps: List[DataGap], 
                                by_priority: Dict, by_schema: Dict) -> List[str]:
        """Generate actionable recommendations based on gap analysis."""
        recommendations = []
        
        # Priority-based recommendations
        if 'high' in by_priority and by_priority['high']['count'] > 0:
            high_priority_cost = by_priority['high']['cost']
            recommendations.append(
                f"🔥 High Priority: {by_priority['high']['count']} gaps need immediate attention "
                f"(${high_priority_cost:.2f})"
            )
        
        # Cost optimization recommendations
        expensive_schemas = [(schema, data['cost']) for schema, data in by_schema.items() 
                           if data['cost'] > 5.0]
        if expensive_schemas:
            expensive_schemas.sort(key=lambda x: x[1], reverse=True)
            schema_name, cost = expensive_schemas[0]
            recommendations.append(
                f"💰 Cost Focus: {schema_name} data gaps cost ${cost:.2f} - prioritize filling these"
            )
        
        # Batch filling recommendations
        total_gaps = len(gaps)
        if total_gaps > 10:
            recommendations.append(
                f"📦 Batch Strategy: {total_gaps} gaps detected - consider batch filling "
                f"to optimize API usage"
            )
        
        # Schema-specific recommendations
        if 'trades' in by_schema and by_schema['trades']['cost'] > 10.0:
            recommendations.append(
                "⚡ Consider using ohlcv-1m instead of trades for backtesting to reduce costs"
            )
        
        return recommendations
    
    def create_fill_strategy(self, gaps: List[DataGap], 
                           max_daily_cost: float = 10.0) -> GapFillStrategy:
        """
        Create an optimal strategy for filling gaps within budget constraints.
        
        Args:
            gaps: List of gaps to fill
            max_daily_cost: Maximum daily cost budget
            
        Returns:
            Optimized gap fill strategy
        """
        total_cost = sum(gap.estimated_cost for gap in gaps)
        
        if total_cost <= max_daily_cost:
            # Can fill all gaps in one go
            return GapFillStrategy(
                batch_size_days=30,
                max_concurrent_requests=5,
                cost_threshold=max_daily_cost,
                prioritize_recent=True
            )
        else:
            # Need to spread over multiple days
            return GapFillStrategy(
                batch_size_days=10,
                max_concurrent_requests=3,
                cost_threshold=max_daily_cost,
                prioritize_recent=True
            )
    
    def print_gap_report(self, gaps: List[DataGap], analysis: Dict):
        """Print a formatted gap analysis report."""
        print("\n" + "="*60)
        print("📊 DATA GAP ANALYSIS REPORT")
        print("="*60)
        
        if not gaps:
            print("✅ No data gaps detected - cache is complete!")
            return
        
        print(f"Total gaps detected:      {analysis['total_gaps']}")
        print(f"Total cost to fill:       ${analysis['total_cost']:.2f}")
        print(f"Total trading days:       {analysis['total_trading_days']}")
        
        print(f"\n📈 BY PRIORITY:")
        for priority, data in analysis['by_priority'].items():
            print(f"  {priority.upper():>6}: {data['count']:>3} gaps, "
                  f"{data['days']:>3} days, ${data['cost']:>6.2f}")
        
        print(f"\n📊 BY SCHEMA:")
        for schema, data in analysis['by_schema'].items():
            print(f"  {schema:>10}: {data['count']:>3} gaps, "
                  f"{data['days']:>3} days, ${data['cost']:>6.2f}")
        
        print(f"\n💡 RECOMMENDATIONS:")
        for i, rec in enumerate(analysis['recommendations'], 1):
            print(f"  {i}. {rec}")
        
        if analysis['total_cost'] > 20.0:
            print(f"\n⚠️  WARNING: High fill cost (${analysis['total_cost']:.2f})")
            print(f"   Consider filling gaps incrementally over multiple days")


def main():
    """CLI interface for gap detection."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Detect gaps in cached market data")
    parser.add_argument(
        '--symbols',
        nargs='+',
        default=['NQZ4', 'NQH5'],
        help='Symbols to analyze (default: NQZ4 NQH5)'
    )
    parser.add_argument(
        '--schemas',
        nargs='+',
        default=['trades', 'ohlcv-1m'],
        help='Schemas to analyze (default: trades ohlcv-1m)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Number of days back to analyze (default: 30)'
    )
    parser.add_argument(
        '--cache-dir',
        default='data/cache',
        help='Cache directory path (default: data/cache)'
    )
    
    args = parser.parse_args()
    
    # Initialize components
    cache_manager = IncrementalCacheManager(args.cache_dir)
    gap_detector = GapDetector(cache_manager)
    
    # Detect gaps
    print(f"🔍 Analyzing cache gaps...")
    print(f"   Symbols: {args.symbols}")
    print(f"   Schemas: {args.schemas}")
    print(f"   Period: {args.days} days")
    
    gaps = gap_detector.detect_gaps(args.symbols, args.schemas, args.days)
    analysis = gap_detector.analyze_gaps(gaps)
    
    # Print report
    gap_detector.print_gap_report(gaps, analysis)
    
    # Show strategy recommendation
    if gaps:
        strategy = gap_detector.create_fill_strategy(gaps)
        print(f"\n🎯 RECOMMENDED FILL STRATEGY:")
        print(f"   Batch size: {strategy.batch_size_days} days")
        print(f"   Max concurrent: {strategy.max_concurrent_requests}")
        print(f"   Cost threshold: ${strategy.cost_threshold:.2f}")
        print(f"   Prioritize recent: {strategy.prioritize_recent}")


if __name__ == '__main__':
    main()