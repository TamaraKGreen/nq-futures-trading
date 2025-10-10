"""
Test cache efficiency with realistic backtesting workflow.

This demonstrates how caching dramatically reduces costs during:
- Strategy development and optimization
- Parameter tuning
- Multiple backtest runs
- Different time periods analysis
"""

import os
import sys
import time
import tempfile
import shutil
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.collectors.cached_databento_client import CachedDatabentoClient
from data.collectors.databento_client import DatabentoClient


class MockTradingStrategy:
    """Simple trading strategy for demonstration purposes."""
    
    def __init__(self, name: str, params: Dict[str, Any]):
        self.name = name
        self.params = params
    
    def backtest(self, data: pd.DataFrame) -> Dict[str, float]:
        """
        Run backtest on data and return performance metrics.
        
        This is a mock implementation - real strategies would be more complex.
        """
        if data.empty:
            return {"total_return": 0.0, "sharpe_ratio": 0.0, "max_drawdown": 0.0}
        
        # Simulate some calculations on the data
        price_changes = data['close'].pct_change().dropna()
        
        # Mock performance metrics
        total_return = price_changes.sum() * 100  # Convert to percentage
        volatility = price_changes.std() * 100
        sharpe_ratio = total_return / volatility if volatility > 0 else 0
        
        return {
            "total_return": round(total_return, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "max_drawdown": round(abs(price_changes.min()) * 100, 2),
            "data_points": len(data)
        }


class BacktestingWorkflowTester:
    """Tests cache efficiency with realistic backtesting workflows."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.temp_cache_dir = tempfile.mkdtemp()
        
        # Create cached and regular clients for comparison
        self.cached_client = CachedDatabentoClient(
            api_key=api_key,
            cache_dir=self.temp_cache_dir
        )
        self.regular_client = DatabentoClient(api_key=api_key)
        
        # Test parameters
        self.symbols = ['NQU4']
        self.base_start = datetime(2024, 8, 1, 14, 0)
        self.schema = 'ohlcv-1m'
        
        # Mock strategies for testing
        self.strategies = [
            MockTradingStrategy("Moving Average", {"fast": 10, "slow": 20}),
            MockTradingStrategy("RSI", {"period": 14, "overbought": 70}),
            MockTradingStrategy("Bollinger Bands", {"period": 20, "std": 2}),
        ]
        
        # Track performance
        self.workflow_results = []
    
    def cleanup(self):
        """Clean up temporary cache directory."""
        shutil.rmtree(self.temp_cache_dir)
    
    def test_strategy_development_workflow(self):
        """
        Simulate typical strategy development workflow:
        1. Load data for testing period
        2. Run multiple strategies
        3. Tweak parameters and re-run
        4. Test on different time periods
        """
        print("\n🧪 STRATEGY DEVELOPMENT WORKFLOW TEST")
        print("="*60)
        
        # Phase 1: Initial strategy testing
        print("\n📊 Phase 1: Initial strategy testing")
        test_period_hours = 6  # 6 hours of data
        end_time = self.base_start + timedelta(hours=test_period_hours)
        
        total_start_time = time.time()
        strategy_results = []
        
        for strategy in self.strategies:
            print(f"\n   Testing strategy: {strategy.name}")
            
            start_time = time.time()
            data = self.cached_client.get_historical_data(
                symbols=self.symbols,
                start=self.base_start,
                end=end_time,
                schema=self.schema
            )
            data_load_time = time.time() - start_time
            
            # Run backtest
            results = strategy.backtest(data)
            results['data_load_time'] = data_load_time
            results['strategy'] = strategy.name
            strategy_results.append(results)
            
            print(f"      Data load: {data_load_time:.2f}s | Data points: {results['data_points']}")
            print(f"      Performance: {results['total_return']:.2f}% return, {results['sharpe_ratio']:.2f} Sharpe")
        
        phase1_time = time.time() - total_start_time
        
        # Phase 2: Parameter optimization (multiple runs on same data)
        print(f"\n🔧 Phase 2: Parameter optimization (10 iterations)")
        
        optimization_start = time.time()
        optimization_results = []
        
        # Simulate 10 parameter optimization runs
        for i in range(10):
            data = self.cached_client.get_historical_data(
                symbols=self.symbols,
                start=self.base_start,
                end=end_time,
                schema=self.schema
            )
            
            # Simulate parameter changes and re-run
            mock_strategy = MockTradingStrategy(f"Optimized_v{i+1}", {"param": i})
            results = mock_strategy.backtest(data)
            optimization_results.append(results)
        
        phase2_time = time.time() - optimization_start
        
        # Phase 3: Different time periods testing
        print(f"\n📅 Phase 3: Different time periods testing")
        
        time_periods_start = time.time()
        period_results = []
        
        # Test on 3 different time periods
        for i, hours in enumerate([2, 4, 8]):
            period_end = self.base_start + timedelta(hours=hours)
            
            data = self.cached_client.get_historical_data(
                symbols=self.symbols,
                start=self.base_start,
                end=period_end,
                schema=self.schema
            )
            
            results = self.strategies[0].backtest(data)  # Use first strategy
            results['period_hours'] = hours
            period_results.append(results)
            
            print(f"      {hours}h period: {results['data_points']} data points, {results['total_return']:.2f}% return")
        
        phase3_time = time.time() - time_periods_start
        
        # Get final performance stats
        stats = self.cached_client.get_performance_stats()
        
        print(f"\n📈 WORKFLOW PERFORMANCE SUMMARY")
        print("="*60)
        print(f"Phase 1 (Initial testing):    {phase1_time:.2f}s")
        print(f"Phase 2 (Optimization):       {phase2_time:.2f}s")
        print(f"Phase 3 (Time periods):       {phase3_time:.2f}s")
        print(f"Total workflow time:          {phase1_time + phase2_time + phase3_time:.2f}s")
        
        print(f"\n💾 CACHE PERFORMANCE:")
        print(f"Total requests:               {stats['total_requests']}")
        print(f"Cache hits:                   {stats['cache_hits']}")
        print(f"API calls:                    {stats['api_calls']}")
        print(f"Cache efficiency:             {stats['cache_efficiency_percent']:.1f}%")
        print(f"API calls saved:              {stats['api_calls_saved']}")
        print(f"Estimated cost saved:         ${stats['estimated_cost_saved']:.2f}")
        
        return {
            'phase_times': [phase1_time, phase2_time, phase3_time],
            'cache_stats': stats,
            'strategy_results': strategy_results,
            'optimization_results': optimization_results,
            'period_results': period_results
        }
    
    def test_without_cache_comparison(self):
        """
        Run the same workflow without caching to show the difference.
        
        Note: This makes real API calls, so use sparingly!
        """
        print("\n⚠️  COMPARISON: Same workflow WITHOUT caching")
        print("="*60)
        print("   (Making real API calls - this will be slower and more expensive)")
        
        start_time = time.time()
        api_call_count = 0
        
        # Simulate just the parameter optimization phase without cache
        test_end = self.base_start + timedelta(hours=2)  # Smaller test to avoid too many API calls
        
        for i in range(3):  # Only 3 iterations to limit API calls
            data = self.regular_client.get_historical_data(
                symbols=self.symbols,
                start=self.base_start,
                end=test_end,
                schema=self.schema
            )
            api_call_count += 1
            
            # Quick calculation
            mock_strategy = MockTradingStrategy(f"NoCache_v{i+1}", {"param": i})
            results = mock_strategy.backtest(data)
        
        no_cache_time = time.time() - start_time
        
        print(f"   Time without cache:           {no_cache_time:.2f}s")
        print(f"   API calls made:               {api_call_count}")
        print(f"   Estimated cost:               ${api_call_count * 0.20:.2f}")
        
        return {
            'time_without_cache': no_cache_time,
            'api_calls': api_call_count
        }
    
    def demonstrate_monthly_savings(self):
        """Demonstrate potential monthly savings."""
        stats = self.cached_client.get_performance_stats()
        
        print(f"\n💰 MONTHLY COST PROJECTION")
        print("="*60)
        
        # Typical development workflow assumptions
        daily_requests = 50  # Requests per development day
        development_days = 20  # Days per month
        monthly_requests = daily_requests * development_days
        
        # Without cache
        without_cache_calls = monthly_requests
        without_cache_cost = without_cache_calls * 0.20  # $0.20 per API call
        
        # With cache (using current efficiency)
        efficiency = stats['cache_efficiency_percent'] / 100
        with_cache_calls = int(monthly_requests * (1 - efficiency))
        with_cache_cost = with_cache_calls * 0.20
        
        savings = without_cache_cost - with_cache_cost
        savings_percent = (savings / without_cache_cost) * 100
        
        print(f"Monthly development scenario:")
        print(f"  - {daily_requests} requests/day × {development_days} days = {monthly_requests:,} total requests")
        print(f"")
        print(f"Without cache:")
        print(f"  - API calls:                  {without_cache_calls:,}")
        print(f"  - Cost:                       ${without_cache_cost:.2f}")
        print(f"")
        print(f"With cache ({efficiency*100:.0f}% efficiency):")
        print(f"  - API calls:                  {with_cache_calls:,}")
        print(f"  - Cost:                       ${with_cache_cost:.2f}")
        print(f"")
        print(f"💡 MONTHLY SAVINGS:")
        print(f"  - API calls saved:            {without_cache_calls - with_cache_calls:,}")
        print(f"  - Cost savings:               ${savings:.2f}")
        print(f"  - Savings percentage:         {savings_percent:.1f}%")
        
        return {
            'monthly_requests': monthly_requests,
            'without_cache_cost': without_cache_cost,
            'with_cache_cost': with_cache_cost,
            'savings': savings,
            'savings_percent': savings_percent
        }


def run_backtesting_workflow_test():
    """Run the complete backtesting workflow test."""
    print("BACKTESTING WORKFLOW CACHE EFFICIENCY TEST")
    print("="*60)
    
    # Check for API key
    api_key = os.getenv('DATABENTO_API_KEY')
    if not api_key:
        print("❌ DATABENTO_API_KEY environment variable not set")
        return False
    
    print("🚀 Testing cache efficiency with realistic trading strategy development workflow...")
    
    tester = BacktestingWorkflowTester(api_key)
    
    try:
        # Run the main workflow test
        workflow_results = tester.test_strategy_development_workflow()
        
        # Show monthly projections
        monthly_results = tester.demonstrate_monthly_savings()
        
        # Optional: Compare with no-cache workflow (commented out to avoid excessive API calls)
        # no_cache_results = tester.test_without_cache_comparison()
        
        print(f"\n✅ BACKTESTING WORKFLOW TEST COMPLETED")
        print(f"   Cache efficiency demonstrated: {workflow_results['cache_stats']['cache_efficiency_percent']:.1f}%")
        print(f"   Potential monthly savings: ${monthly_results['savings']:.2f}")
        
        return True
        
    finally:
        tester.cleanup()


if __name__ == '__main__':
    success = run_backtesting_workflow_test()
    if not success:
        sys.exit(1)