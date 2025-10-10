"""
Integration tests for CachedDatabentoClient with real Databento API.

These tests verify:
- Real API connectivity and authentication
- Cache functionality with actual data
- Cost savings measurement
- Performance improvements
"""

import unittest
import tempfile
import shutil
import pandas as pd
from datetime import datetime, timedelta
import os
import sys
import time

from nq_futures_system.data.collectors.cached_databento_client import CachedDatabentoClient, create_cached_client
from nq_futures_system.data.collectors.databento_client import DatabentoClient
from nq_futures_system.config.settings import get_config
from nq_futures_system.utils.validators import ValidationError


class TestCachedDatabentoClientIntegration(unittest.TestCase):
    """Integration tests with real Databento API."""
    
    @classmethod
    def setUpClass(cls):
        """Set up class-level test environment."""
        # Validate configuration
        config = get_config()
        validation = config.validate_config()
        
        if not validation['valid']:
            # In test context, skip tests if validation fails
            error_msg = "Configuration validation failed: "
            error_msg += ", ".join(validation['issues'])
            raise unittest.SkipTest(error_msg)
        
        cls.api_key = os.getenv('DATABENTO_API_KEY')
        
        # Test dates (using historical data we know works)
        cls.test_symbols = ['NQU4']
        cls.test_start = datetime(2024, 8, 1, 14, 0)  # 2 PM UTC
        cls.test_end = cls.test_start + timedelta(hours=1)  # 1 hour of data
        cls.test_schema = 'ohlcv-1m'  # 1-minute bars (cheaper than trades)
    
    def setUp(self):
        """Set up test environment for each test."""
        # Create temporary cache directory
        self.temp_cache_dir = tempfile.mkdtemp()
        
        # Create cached client
        self.cached_client = CachedDatabentoClient(
            api_key=self.api_key,
            cache_dir=self.temp_cache_dir
        )
        
        # Create regular client for comparison
        self.regular_client = DatabentoClient(api_key=self.api_key)
    
    def tearDown(self):
        """Clean up after each test."""
        shutil.rmtree(self.temp_cache_dir)
    
    def test_api_connectivity(self):
        """Test that the cached client can connect to Databento API."""
        try:
            # Make a small API request
            df = self.cached_client.get_historical_data(
                symbols=self.test_symbols,
                start=self.test_start,
                end=self.test_start + timedelta(minutes=5),  # Just 5 minutes
                schema=self.test_schema
            )
            
            # Verify we got data
            self.assertIsInstance(df, pd.DataFrame)
            self.assertGreater(len(df), 0)
            print(f"✅ API connectivity test passed: Retrieved {len(df)} records")
            
        except Exception as e:
            self.fail(f"API connectivity test failed: {e}")
    
    def test_cache_miss_then_hit(self):
        """Test cache miss on first request, hit on second."""
        print("\n🧪 Testing cache miss then hit scenario...")
        
        # First request should be cache miss (API call)
        start_time = time.time()
        df1 = self.cached_client.get_historical_data(
            symbols=self.test_symbols,
            start=self.test_start,
            end=self.test_end,
            schema=self.test_schema
        )
        first_call_time = time.time() - start_time
        
        # Verify we got data
        self.assertIsInstance(df1, pd.DataFrame)
        self.assertGreater(len(df1), 0)
        
        # Check stats after first call
        stats = self.cached_client.get_performance_stats()
        self.assertEqual(stats['total_requests'], 1)
        self.assertEqual(stats['api_calls'], 1)
        self.assertEqual(stats['cache_hits'], 0)
        
        print(f"   First call (API): {first_call_time:.2f}s, {len(df1)} records")
        
        # Second request should be cache hit (no API call)
        start_time = time.time()
        df2 = self.cached_client.get_historical_data(
            symbols=self.test_symbols,
            start=self.test_start,
            end=self.test_end,
            schema=self.test_schema
        )
        second_call_time = time.time() - start_time
        
        # Verify data is identical
        pd.testing.assert_frame_equal(df1, df2)
        
        # Check stats after second call
        stats = self.cached_client.get_performance_stats()
        self.assertEqual(stats['total_requests'], 2)
        self.assertEqual(stats['api_calls'], 1)  # Still only 1 API call
        self.assertEqual(stats['cache_hits'], 1)
        self.assertEqual(stats['cache_efficiency_percent'], 50.0)
        
        print(f"   Second call (cache): {second_call_time:.2f}s, {len(df2)} records")
        print(f"   Speed improvement: {first_call_time/second_call_time:.1f}x faster")
        
        # Cache should be significantly faster
        self.assertLess(second_call_time, first_call_time * 0.5)  # At least 2x faster
    
    def test_multiple_requests_performance(self):
        """Test performance with multiple repeated requests."""
        print("\n🚀 Testing multiple requests performance...")
        
        # Make 5 identical requests
        request_times = []
        
        for i in range(5):
            start_time = time.time()
            df = self.cached_client.get_historical_data(
                symbols=self.test_symbols,
                start=self.test_start,
                end=self.test_end,
                schema=self.test_schema
            )
            request_time = time.time() - start_time
            request_times.append(request_time)
            
            self.assertIsInstance(df, pd.DataFrame)
            self.assertGreater(len(df), 0)
        
        # Check final stats
        stats = self.cached_client.get_performance_stats()
        self.assertEqual(stats['total_requests'], 5)
        self.assertEqual(stats['api_calls'], 1)  # Only 1 API call for all 5 requests
        self.assertEqual(stats['cache_hits'], 4)  # 4 cache hits
        self.assertEqual(stats['cache_efficiency_percent'], 80.0)
        
        print(f"   Total requests: {stats['total_requests']}")
        print(f"   API calls: {stats['api_calls']}")
        print(f"   Cache hits: {stats['cache_hits']}")
        print(f"   Cache efficiency: {stats['cache_efficiency_percent']:.1f}%")
        print(f"   Request times: {[f'{t:.2f}s' for t in request_times]}")
        
        # First request should be slowest (API call)
        self.assertGreater(request_times[0], max(request_times[1:]))
    
    def test_data_consistency(self):
        """Test that cached data is identical to API data."""
        print("\n🔍 Testing data consistency...")
        
        # Get data using cached client
        cached_df = self.cached_client.get_historical_data(
            symbols=self.test_symbols,
            start=self.test_start,
            end=self.test_start + timedelta(minutes=30),  # 30 minutes
            schema=self.test_schema
        )
        
        # Get same data using regular client
        regular_df = self.regular_client.get_historical_data(
            symbols=self.test_symbols,
            start=self.test_start,
            end=self.test_start + timedelta(minutes=30),
            schema=self.test_schema
        )
        
        # Data should be identical
        pd.testing.assert_frame_equal(cached_df, regular_df)
        print(f"   ✅ Data consistency verified: {len(cached_df)} records match exactly")
    
    def test_cost_savings_estimation(self):
        """Test cost savings calculation."""
        print("\n💰 Testing cost savings estimation...")
        
        # Make several requests to build up savings
        for i in range(3):
            self.cached_client.get_historical_data(
                symbols=self.test_symbols,
                start=self.test_start,
                end=self.test_end,
                schema=self.test_schema
            )
        
        stats = self.cached_client.get_performance_stats()
        
        # Should have saved some API calls
        self.assertGreater(stats['api_calls_saved'], 0)
        self.assertGreater(stats['estimated_cost_saved'], 0)
        
        print(f"   API calls saved: {stats['api_calls_saved']}")
        print(f"   Estimated cost saved: ${stats['estimated_cost_saved']:.2f}")
        print(f"   Monthly projection: ${stats['monthly_savings_estimate']:.2f}")
        
        # Print full performance summary
        self.cached_client.print_performance_summary()
    
    def test_different_schemas(self):
        """Test caching works with different data schemas."""
        print("\n📊 Testing different data schemas...")
        
        schemas_to_test = ['ohlcv-1m']  # Start with just one to avoid too many API calls
        
        for schema in schemas_to_test:
            # First call - cache miss
            df1 = self.cached_client.get_historical_data(
                symbols=self.test_symbols,
                start=self.test_start,
                end=self.test_start + timedelta(minutes=10),
                schema=schema
            )
            
            # Second call - cache hit
            df2 = self.cached_client.get_historical_data(
                symbols=self.test_symbols,
                start=self.test_start,
                end=self.test_start + timedelta(minutes=10),
                schema=schema
            )
            
            # Data should be identical
            pd.testing.assert_frame_equal(df1, df2)
            print(f"   ✅ Schema {schema}: {len(df1)} records cached and retrieved correctly")
    
    def test_cache_file_creation(self):
        """Test that cache files are created on disk."""
        # Make a request to create cache
        self.cached_client.get_historical_data(
            symbols=self.test_symbols,
            start=self.test_start,
            end=self.test_start + timedelta(minutes=15),
            schema=self.test_schema
        )
        
        # Check that cache files were created
        cache_files = list(self.cached_client.cache_manager.data_dir.rglob("*.parquet"))
        self.assertGreater(len(cache_files), 0)
        
        # Check file size
        total_size = sum(f.stat().st_size for f in cache_files)
        self.assertGreater(total_size, 0)
        
        print(f"   ✅ Cache files created: {len(cache_files)} files, {total_size/1024:.1f} KB total")


def run_integration_tests():
    """Run integration tests with proper setup."""
    print("CACHED DATABENTO CLIENT INTEGRATION TESTS")
    print("=" * 60)
    
    # Validate configuration
    config = get_config()
    validation = config.validate_config()
    
    if not validation['valid']:
        print("❌ Configuration validation failed:")
        for issue in validation['issues']:
            print(f"   - {issue}")
        return False
    
    if validation['warnings']:
        print("⚠️  Configuration warnings:")
        for warning in validation['warnings']:
            print(f"   - {warning}")
    
    # Run the tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCachedDatabentoClientIntegration)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_integration_tests()
    if not success:
        sys.exit(1)