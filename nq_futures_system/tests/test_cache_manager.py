"""
Unit tests for CacheManager class.

Tests basic cache operations including:
- Cache initialization
- Data storage and retrieval
- Cache hit/miss scenarios
- Statistics tracking
- File path generation
"""

import unittest
import tempfile
import shutil
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import os
import sys

from nq_futures_system.data.cache.cache_manager import CacheManager, IncrementalCacheManager


class TestCacheManager(unittest.TestCase):
    """Test basic CacheManager functionality."""
    
    def setUp(self):
        """Set up test environment with temporary cache directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_manager = CacheManager(self.temp_dir)
        
        # Create sample data for testing
        self.sample_data = pd.DataFrame({
            'ts_event': pd.date_range('2024-08-01 14:00:00', periods=100, freq='1min'),
            'symbol': ['NQU4'] * 100,
            'price': [25000 + i * 0.25 for i in range(100)],
            'size': [1 + (i % 10) for i in range(100)]
        }).set_index('ts_event')
        
        self.symbols = ['NQU4']
        self.start = datetime(2024, 8, 1, 14, 0)
        self.end = datetime(2024, 8, 1, 15, 0)
        self.schema = 'trades'
    
    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)
    
    def test_cache_manager_initialization(self):
        """Test that CacheManager initializes correctly."""
        # Check that cache manager was created
        self.assertIsInstance(self.cache_manager, CacheManager)
        
        # Check that directories were created
        self.assertTrue(self.cache_manager.data_dir.exists())
        self.assertTrue(self.cache_manager.daily_dir.exists())
        self.assertTrue(self.cache_manager.metadata_dir.exists())
        
        # Check that metadata was initialized
        self.assertIsInstance(self.cache_manager.metadata, dict)
        self.assertIn('cache_files', self.cache_manager.metadata)
        self.assertIn('daily_files', self.cache_manager.metadata)
    
    def test_cache_path_generation(self):
        """Test that cache file paths are generated correctly."""
        cache_path = self.cache_manager._get_cache_path(
            self.symbols, self.start, self.end, self.schema
        )
        
        # Check that path is a Path object
        self.assertIsInstance(cache_path, Path)
        
        # Check that path contains expected elements
        path_str = str(cache_path)
        self.assertIn('NQU4', path_str)
        self.assertIn('20240801', path_str)
        self.assertIn('trades', path_str)
        self.assertIn('.parquet', path_str)
    
    def test_cache_miss_scenario(self):
        """Test cache miss when data is not cached."""
        # Try to get data that doesn't exist in cache
        result = self.cache_manager.get(self.symbols, self.start, self.end, self.schema)
        
        # Should return None for cache miss
        self.assertIsNone(result)
        
        # Check that stats were updated
        stats = self.cache_manager.get_stats()
        self.assertEqual(stats['cache_misses'], 1)
        self.assertEqual(stats['cache_hits'], 0)
        self.assertEqual(stats['total_requests'], 1)
    
    def test_cache_set_and_get(self):
        """Test storing data in cache and retrieving it."""
        # Store data in cache
        self.cache_manager.set(
            self.sample_data, self.symbols, self.start, self.end, self.schema
        )
        
        # Retrieve data from cache
        retrieved_data = self.cache_manager.get(
            self.symbols, self.start, self.end, self.schema
        )
        
        # Check that data was retrieved successfully
        self.assertIsNotNone(retrieved_data)
        self.assertIsInstance(retrieved_data, pd.DataFrame)
        self.assertEqual(len(retrieved_data), len(self.sample_data))
        
        # Check that the data is the same
        pd.testing.assert_frame_equal(retrieved_data, self.sample_data)
    
    def test_cache_hit_scenario(self):
        """Test cache hit when data is already cached."""
        # Store data in cache first
        self.cache_manager.set(
            self.sample_data, self.symbols, self.start, self.end, self.schema
        )
        
        # Reset stats to test cache hit
        self.cache_manager.stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "total_requests": 0,
            "bytes_cached": 0,
            "api_calls_saved": 0
        }
        
        # Retrieve data (should be cache hit)
        result = self.cache_manager.get(self.symbols, self.start, self.end, self.schema)
        
        # Check that data was retrieved
        self.assertIsNotNone(result)
        
        # Check that stats show cache hit
        stats = self.cache_manager.get_stats()
        self.assertEqual(stats['cache_hits'], 1)
        self.assertEqual(stats['cache_misses'], 0)
        self.assertEqual(stats['api_calls_saved'], 1)
    
    def test_cache_statistics(self):
        """Test that cache statistics are tracked correctly."""
        # Initially, stats should be zero
        stats = self.cache_manager.get_stats()
        self.assertEqual(stats['total_requests'], 0)
        self.assertEqual(stats['cache_hits'], 0)
        
        # Make a cache miss
        self.cache_manager.get(self.symbols, self.start, self.end, self.schema)
        stats = self.cache_manager.get_stats()
        self.assertEqual(stats['total_requests'], 1)
        self.assertEqual(stats['cache_misses'], 1)
        
        # Store some data
        self.cache_manager.set(
            self.sample_data, self.symbols, self.start, self.end, self.schema
        )
        
        # Make a cache hit
        self.cache_manager.get(self.symbols, self.start, self.end, self.schema)
        stats = self.cache_manager.get_stats()
        self.assertEqual(stats['total_requests'], 2)
        self.assertEqual(stats['cache_hits'], 1)
        self.assertEqual(stats['cache_misses'], 1)
        self.assertEqual(stats['hit_rate_percent'], 50.0)
    
    def test_empty_dataframe_handling(self):
        """Test that empty DataFrames are handled correctly."""
        empty_df = pd.DataFrame()
        
        # Should not store empty DataFrame
        self.cache_manager.set(empty_df, self.symbols, self.start, self.end, self.schema)
        
        # Should still return None for cache miss
        result = self.cache_manager.get(self.symbols, self.start, self.end, self.schema)
        self.assertIsNone(result)
    
    def test_multiple_symbols(self):
        """Test caching with multiple symbols."""
        symbols = ['NQU4', 'NQZ4']
        multi_symbol_data = pd.DataFrame({
            'ts_event': pd.date_range('2024-08-01 14:00:00', periods=50, freq='1min'),
            'symbol': ['NQU4'] * 25 + ['NQZ4'] * 25,
            'price': [25000 + i * 0.25 for i in range(50)],
            'size': [1] * 50
        }).set_index('ts_event')
        
        # Store multi-symbol data
        self.cache_manager.set(multi_symbol_data, symbols, self.start, self.end, self.schema)
        
        # Retrieve it
        result = self.cache_manager.get(symbols, self.start, self.end, self.schema)
        
        self.assertIsNotNone(result)
        pd.testing.assert_frame_equal(result, multi_symbol_data)


class TestIncrementalCacheManager(unittest.TestCase):
    """Test IncrementalCacheManager functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_manager = IncrementalCacheManager(self.temp_dir)
        
        self.symbol = 'NQU4'
        self.schema = 'trades'
        self.test_date = datetime(2024, 8, 1).date()
    
    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)
    
    def test_missing_dates_detection(self):
        """Test detection of missing dates."""
        start_date = datetime(2024, 8, 1).date()
        end_date = datetime(2024, 8, 5).date()  # 5 days
        
        # All dates should be missing initially
        missing = self.cache_manager.find_missing_dates(
            self.symbol, self.schema, start_date, end_date
        )
        
        # Should find 4 trading days (skip weekend)
        self.assertGreater(len(missing), 0)
        self.assertLessEqual(len(missing), 5)  # At most 5 days
    
    def test_has_cached_date(self):
        """Test checking if a specific date is cached."""
        # Initially, no dates should be cached
        self.assertFalse(
            self.cache_manager.has_cached_date(self.symbol, self.schema, self.test_date)
        )
        
        # Cache some data for this date
        sample_data = pd.DataFrame({
            'ts_event': pd.date_range('2024-08-01 14:00:00', periods=10, freq='1min'),
            'symbol': [self.symbol] * 10,
            'price': [25000] * 10,
            'size': [1] * 10
        }).set_index('ts_event')
        
        self.cache_manager.cache_daily_data(sample_data, self.symbol, self.test_date, self.schema)
        
        # Now it should be cached
        self.assertTrue(
            self.cache_manager.has_cached_date(self.symbol, self.schema, self.test_date)
        )
    
    def test_latest_cached_date(self):
        """Test finding the latest cached date."""
        # Initially, no latest date
        latest = self.cache_manager.get_latest_cached_date(self.symbol, self.schema)
        self.assertIsNone(latest)
        
        # Cache data for a specific date
        sample_data = pd.DataFrame({
            'symbol': [self.symbol] * 5,
            'price': [25000] * 5
        })
        
        self.cache_manager.cache_daily_data(sample_data, self.symbol, self.test_date, self.schema)
        
        # Should find that date as latest
        latest = self.cache_manager.get_latest_cached_date(self.symbol, self.schema)
        self.assertEqual(latest, self.test_date)


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)