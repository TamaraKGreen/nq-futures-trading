"""
Cost Tracking and Reporting System

Provides detailed cost analysis and optimization recommendations:
- Real-time API cost tracking
- Monthly budget monitoring
- Cost optimization suggestions
- ROI analysis for caching
- Detailed cost breakdowns
"""

import json
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import threading

logger = logging.getLogger(__name__)


@dataclass
class CostEntry:
    """Single cost tracking entry."""
    timestamp: datetime
    operation_type: str  # 'api_call', 'cache_hit', 'cache_miss'
    symbol: str
    schema: str
    cost_usd: float
    api_calls_count: int = 1
    data_volume_mb: float = 0.0
    cache_hit: bool = False


@dataclass
class MonthlyCostSummary:
    """Monthly cost summary."""
    month: str  # YYYY-MM format
    total_cost: float
    api_calls: int
    cache_hits: int
    cache_misses: int
    cache_savings: float
    data_volume_gb: float
    top_expensive_symbols: List[Tuple[str, float]]


class CostTracker:
    """Tracks and analyzes API costs and cache savings."""
    
    def __init__(self, storage_dir: str = "monitoring/costs", config=None):
        """
        Initialize cost tracker.
        
        Args:
            storage_dir: Directory to store cost data
            config: Configuration object (uses default if None)
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Get configuration
        if config is None:
            from nq_futures_system.config.settings import get_config
            config = get_config()
        self.config = config
        
        # Cost tracking
        self.cost_entries: List[CostEntry] = []
        self.monthly_summaries: Dict[str, MonthlyCostSummary] = {}
        self.lock = threading.RLock()
        
        # Get cost rates from canonical configuration
        # Combine API base costs with schema multipliers
        self.cost_rates = {}
        for schema, multiplier in self.config.trading.get_schema_cost_rates.items():
            # Use base cost from API settings, applied with schema multiplier
            base_cost = getattr(self.config.api, f"cost_per_{schema.replace('-', '_')}_day", 
                              self.config.api.cost_per_trade_day)  # Default to trade cost
            self.cost_rates[schema] = base_cost * multiplier
        
        # Budget settings from configuration
        self.monthly_budget = self.config.api.monthly_budget_usd
        self.warning_threshold = 0.8  # 80% of budget
        
        # Load existing data
        self._load_historical_data()
        
        logger.info(f"CostTracker initialized: {storage_dir}")
    
    def record_api_call(self, symbol: str, schema: str, data_size_mb: float = 0.0,
                       cache_hit: bool = False):
        """
        Record an API call for cost tracking.
        
        Args:
            symbol: Symbol that was requested
            schema: Data schema
            data_size_mb: Size of data returned in MB
            cache_hit: Whether this was a cache hit (no actual API cost)
        """
        with self.lock:
            # Calculate cost
            cost = 0.0 if cache_hit else self.cost_rates.get(schema, 0.10)
            
            entry = CostEntry(
                timestamp=datetime.utcnow(),
                operation_type='cache_hit' if cache_hit else 'api_call',
                symbol=symbol,
                schema=schema,
                cost_usd=cost,
                api_calls_count=0 if cache_hit else 1,
                data_volume_mb=data_size_mb,
                cache_hit=cache_hit
            )
            
            self.cost_entries.append(entry)
            
            # Update monthly summary
            self._update_monthly_summary(entry)
            
            logger.debug(f"Recorded {'cache hit' if cache_hit else 'API call'}: "
                        f"{symbol} {schema} ${cost:.3f}")
    
    def record_batch_api_calls(self, symbol: str, schema: str, days_count: int,
                              data_size_mb: float = 0.0):
        """
        Record multiple days of API calls (for batch operations).
        
        Args:
            symbol: Symbol that was requested
            schema: Data schema
            days_count: Number of days of data requested
            data_size_mb: Total size of data returned in MB
        """
        cost_per_day = self.cost_rates.get(schema, 0.10)
        total_cost = cost_per_day * days_count
        
        with self.lock:
            entry = CostEntry(
                timestamp=datetime.utcnow(),
                operation_type='batch_api_call',
                symbol=symbol,
                schema=schema,
                cost_usd=total_cost,
                api_calls_count=days_count,
                data_volume_mb=data_size_mb,
                cache_hit=False
            )
            
            self.cost_entries.append(entry)
            self._update_monthly_summary(entry)
            
            logger.info(f"Recorded batch API call: {symbol} {schema} "
                       f"{days_count} days ${total_cost:.2f}")
    
    def _update_monthly_summary(self, entry: CostEntry):
        """Update monthly cost summary with new entry."""
        month_key = entry.timestamp.strftime("%Y-%m")
        
        if month_key not in self.monthly_summaries:
            self.monthly_summaries[month_key] = MonthlyCostSummary(
                month=month_key,
                total_cost=0.0,
                api_calls=0,
                cache_hits=0,
                cache_misses=0,
                cache_savings=0.0,
                data_volume_gb=0.0,
                top_expensive_symbols=[]
            )
        
        summary = self.monthly_summaries[month_key]
        summary.total_cost += entry.cost_usd
        summary.data_volume_gb += entry.data_volume_mb / 1024
        
        if entry.cache_hit:
            summary.cache_hits += 1
            # Calculate theoretical cost if it wasn't cached
            theoretical_cost = self.cost_rates.get(entry.schema, 0.10)
            summary.cache_savings += theoretical_cost
        else:
            summary.api_calls += entry.api_calls_count
            if entry.api_calls_count > 0:
                summary.cache_misses += 1
    
    def get_current_month_cost(self) -> float:
        """Get current month's total cost."""
        current_month = datetime.now().strftime("%Y-%m")
        summary = self.monthly_summaries.get(current_month)
        return summary.total_cost if summary else 0.0
    
    def get_budget_status(self) -> Dict[str, any]:
        """Get current budget status and warnings."""
        current_cost = self.get_current_month_cost()
        remaining_budget = self.monthly_budget - current_cost
        usage_percent = (current_cost / self.monthly_budget) * 100
        
        # Determine status
        if usage_percent >= 100:
            status = "exceeded"
            color = "🔴"
        elif usage_percent >= self.warning_threshold * 100:
            status = "warning"
            color = "🟡"
        else:
            status = "good"
            color = "🟢"
        
        return {
            'current_cost': current_cost,
            'monthly_budget': self.monthly_budget,
            'remaining_budget': remaining_budget,
            'usage_percent': usage_percent,
            'status': status,
            'status_color': color,
            'days_remaining': (datetime.now().replace(day=28) + timedelta(days=4) - 
                             datetime.now().replace(day=28)).days - datetime.now().day + 1
        }
    
    def get_cost_breakdown_by_symbol(self, days: int = 30) -> Dict[str, Dict]:
        """Get cost breakdown by symbol for recent period."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        symbol_costs = {}
        with self.lock:
            for entry in self.cost_entries:
                if entry.timestamp >= cutoff:
                    symbol = entry.symbol
                    if symbol not in symbol_costs:
                        symbol_costs[symbol] = {
                            'total_cost': 0.0,
                            'api_calls': 0,
                            'cache_hits': 0,
                            'cache_savings': 0.0,
                            'schemas': set()
                        }
                    
                    symbol_costs[symbol]['total_cost'] += entry.cost_usd
                    symbol_costs[symbol]['schemas'].add(entry.schema)
                    
                    if entry.cache_hit:
                        symbol_costs[symbol]['cache_hits'] += 1
                        theoretical_cost = self.cost_rates.get(entry.schema, 0.10)
                        symbol_costs[symbol]['cache_savings'] += theoretical_cost
                    else:
                        symbol_costs[symbol]['api_calls'] += entry.api_calls_count
        
        # Convert sets to lists for JSON serialization
        for symbol_data in symbol_costs.values():
            symbol_data['schemas'] = list(symbol_data['schemas'])
        
        return symbol_costs
    
    def get_cost_breakdown_by_schema(self, days: int = 30) -> Dict[str, Dict]:
        """Get cost breakdown by schema for recent period."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        schema_costs = {}
        with self.lock:
            for entry in self.cost_entries:
                if entry.timestamp >= cutoff:
                    schema = entry.schema
                    if schema not in schema_costs:
                        schema_costs[schema] = {
                            'total_cost': 0.0,
                            'api_calls': 0,
                            'cache_hits': 0,
                            'cache_savings': 0.0,
                            'data_volume_mb': 0.0
                        }
                    
                    schema_costs[schema]['total_cost'] += entry.cost_usd
                    schema_costs[schema]['data_volume_mb'] += entry.data_volume_mb
                    
                    if entry.cache_hit:
                        schema_costs[schema]['cache_hits'] += 1
                        theoretical_cost = self.cost_rates.get(entry.schema, 0.10)
                        schema_costs[schema]['cache_savings'] += theoretical_cost
                    else:
                        schema_costs[schema]['api_calls'] += entry.api_calls_count
        
        return schema_costs
    
    def calculate_cache_roi(self, days: int = 30) -> Dict[str, float]:
        """Calculate ROI from caching over recent period."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        actual_cost = 0.0
        theoretical_cost_without_cache = 0.0
        
        with self.lock:
            for entry in self.cost_entries:
                if entry.timestamp >= cutoff:
                    actual_cost += entry.cost_usd
                    
                    if entry.cache_hit:
                        # Add theoretical cost if this wasn't cached
                        theoretical_cost_without_cache += self.cost_rates.get(entry.schema, 0.10)
                    else:
                        theoretical_cost_without_cache += entry.cost_usd
        
        cache_savings = theoretical_cost_without_cache - actual_cost
        roi_percent = (cache_savings / theoretical_cost_without_cache * 100) if theoretical_cost_without_cache > 0 else 0
        
        return {
            'actual_cost': actual_cost,
            'theoretical_cost_without_cache': theoretical_cost_without_cache,
            'total_savings': cache_savings,
            'roi_percent': roi_percent,
            'period_days': days
        }
    
    def get_optimization_recommendations(self) -> List[str]:
        """Generate cost optimization recommendations."""
        recommendations = []
        
        # Check budget status
        budget_status = self.get_budget_status()
        if budget_status['status'] == 'exceeded':
            recommendations.append(
                f"🔴 URGENT: Monthly budget exceeded by ${budget_status['current_cost'] - budget_status['monthly_budget']:.2f}"
            )
        elif budget_status['status'] == 'warning':
            recommendations.append(
                f"🟡 WARNING: {budget_status['usage_percent']:.1f}% of monthly budget used"
            )
        
        # Analyze symbol costs
        symbol_costs = self.get_cost_breakdown_by_symbol(30)
        if symbol_costs:
            most_expensive = max(symbol_costs.items(), key=lambda x: x[1]['total_cost'])
            if most_expensive[1]['total_cost'] > 10.0:
                recommendations.append(
                    f"💰 Consider optimizing requests for {most_expensive[0]} "
                    f"(${most_expensive[1]['total_cost']:.2f} in 30 days)"
                )
        
        # Analyze cache efficiency
        cache_roi = self.calculate_cache_roi(30)
        if cache_roi['roi_percent'] < 50:
            recommendations.append(
                f"📦 Cache efficiency is low ({cache_roi['roi_percent']:.1f}%) - "
                f"consider pre-warming cache for frequently accessed data"
            )
        
        # Schema cost analysis
        schema_costs = self.get_cost_breakdown_by_schema(30)
        expensive_schemas = [(schema, data) for schema, data in schema_costs.items() 
                           if data['total_cost'] > 5.0]
        if expensive_schemas:
            expensive_schemas.sort(key=lambda x: x[1]['total_cost'], reverse=True)
            top_schema = expensive_schemas[0]
            recommendations.append(
                f"📊 {top_schema[0]} data is expensive (${top_schema[1]['total_cost']:.2f}) - "
                f"consider using lower-resolution data for backtesting"
            )
        
        # Data volume recommendations
        total_volume = sum(data['data_volume_mb'] for data in schema_costs.values())
        if total_volume > 1000:  # > 1GB
            recommendations.append(
                f"💾 High data volume ({total_volume/1024:.1f} GB) - "
                f"implement data compression and cleanup strategies"
            )
        
        return recommendations
    
    def _load_historical_data(self):
        """Load historical cost data from storage."""
        cost_file = self.storage_dir / "cost_history.json"
        if cost_file.exists():
            try:
                with open(cost_file, 'r') as f:
                    data = json.load(f)
                
                # Load cost entries
                for entry_data in data.get('cost_entries', []):
                    entry_data['timestamp'] = datetime.fromisoformat(entry_data['timestamp'])
                    entry = CostEntry(**entry_data)
                    self.cost_entries.append(entry)
                
                # Rebuild monthly summaries
                self._rebuild_monthly_summaries()
                
                logger.info(f"Loaded {len(self.cost_entries)} historical cost entries")
                
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(f"Failed to load historical cost data: {e}")
    
    def _rebuild_monthly_summaries(self):
        """Rebuild monthly summaries from cost entries."""
        self.monthly_summaries.clear()
        
        for entry in self.cost_entries:
            self._update_monthly_summary(entry)
    
    def save_data(self):
        """Save cost data to storage."""
        cost_file = self.storage_dir / "cost_history.json"
        
        # Prepare data for serialization
        data = {
            'cost_entries': [asdict(entry) for entry in self.cost_entries[-1000:]],  # Keep last 1000
            'monthly_summaries': {k: asdict(v) for k, v in self.monthly_summaries.items()},
            'last_updated': datetime.utcnow().isoformat()
        }
        
        try:
            with open(cost_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            logger.info(f"Cost data saved to {cost_file}")
            
        except IOError as e:
            logger.error(f"Failed to save cost data: {e}")
    
    def print_cost_report(self):
        """Print a formatted cost report."""
        budget_status = self.get_budget_status()
        cache_roi = self.calculate_cache_roi(30)
        symbol_costs = self.get_cost_breakdown_by_symbol(30)
        recommendations = self.get_optimization_recommendations()
        
        print(f"\n{'='*60}")
        print(f"💰 COST TRACKING REPORT")
        print(f"{'='*60}")
        
        # Budget status
        print(f"Monthly Budget:          ${budget_status['monthly_budget']:.2f}")
        print(f"Current Usage:           {budget_status['status_color']} ${budget_status['current_cost']:.2f} "
              f"({budget_status['usage_percent']:.1f}%)")
        print(f"Remaining Budget:        ${budget_status['remaining_budget']:.2f}")
        print(f"Days Remaining:          {budget_status['days_remaining']}")
        
        # Cache ROI
        print(f"\n📦 CACHE ROI (30 days):")
        print(f"Actual Cost:             ${cache_roi['actual_cost']:.2f}")
        print(f"Cost Without Cache:      ${cache_roi['theoretical_cost_without_cache']:.2f}")
        print(f"Total Savings:           ${cache_roi['total_savings']:.2f}")
        print(f"ROI:                     {cache_roi['roi_percent']:.1f}%")
        
        # Top expensive symbols
        if symbol_costs:
            print(f"\n💸 TOP EXPENSIVE SYMBOLS (30 days):")
            sorted_symbols = sorted(symbol_costs.items(), 
                                   key=lambda x: x[1]['total_cost'], reverse=True)
            for symbol, data in sorted_symbols[:5]:
                cache_efficiency = (data['cache_hits'] / 
                                  max(data['cache_hits'] + data['api_calls'], 1) * 100)
                print(f"  {symbol:>8}: ${data['total_cost']:>6.2f} "
                      f"(cache: {cache_efficiency:>5.1f}%)")
        
        # Recommendations
        if recommendations:
            print(f"\n💡 OPTIMIZATION RECOMMENDATIONS:")
            for i, rec in enumerate(recommendations, 1):
                print(f"  {i}. {rec}")
        else:
            print(f"\n✅ No optimization recommendations - costs are well managed!")


def create_cost_tracker() -> CostTracker:
    """Factory function to create a cost tracker."""
    return CostTracker()


if __name__ == '__main__':
    # Demo the cost tracking system
    print("COST TRACKING SYSTEM DEMONSTRATION")
    print("="*60)
    
    # Create tracker
    tracker = CostTracker()
    
    # Simulate some API calls and cache hits
    tracker.record_api_call("NQZ5", "trades", 15.5, cache_hit=False)
    tracker.record_api_call("NQZ5", "trades", 15.5, cache_hit=True)  # Cache hit
    tracker.record_api_call("NQH6", "ohlcv-1m", 2.1, cache_hit=False)
    tracker.record_batch_api_calls("ESZ5", "trades", 5, 75.0)  # 5 days of data
    
    # Simulate more cache hits to show efficiency
    for _ in range(10):
        tracker.record_api_call("NQZ5", "ohlcv-1m", 1.0, cache_hit=True)
    
    # Print cost report
    tracker.print_cost_report()
    
    # Save data
    tracker.save_data()
    
    print(f"\n✅ Cost tracking demonstration complete!")
    print(f"   Cost data saved for persistent tracking across sessions")