"""
Comprehensive System Integration Tests

Tests end-to-end functionality of the complete trading system:
- Unified data coordinator integration
- Performance monitoring integration
- Cost tracking integration
- Cache management workflow
- Configuration system validation
- Error handling and recovery
"""

import unittest
import tempfile
import shutil
import asyncio
import time
from datetime import datetime, timedelta
import sys
import os

from nq_futures_system.data.unified_data_coordinator import UnifiedDataCoordinator, create_coordinator
from nq_futures_system.monitoring.performance_monitor import PerformanceMonitor, get_performance_monitor
from nq_futures_system.monitoring.cost_tracker import CostTracker, create_cost_tracker
from nq_futures_system.config.settings import ConfigManager, get_config
from nq_futures_system.data.live.live_buffer import LiveDataBuffer, LiveTick, create_sample_ticks
from nq_futures_system.utils.gap_detector import GapDetector
from nq_futures_system.utils.validators import ValidationError
from nq_futures_system.utils.cache_cleanup import CacheCleanupManager


class TestSystemIntegration(unittest.TestCase):
    """Comprehensive system integration tests."""
    
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
    
    def setUp(self):
        """Set up test environment for each test."""
        # Create temporary directories
        self.temp_cache_dir = tempfile.mkdtemp()
        self.temp_monitoring_dir = tempfile.mkdtemp()
        
        # Initialize system components
        self.coordinator = create_coordinator(
            cache_dir=self.temp_cache_dir,
            live_buffer_size=10000
        )
        
        self.performance_monitor = PerformanceMonitor(
            metrics_dir=os.path.join(self.temp_monitoring_dir, "metrics")
        )
        
        self.cost_tracker = CostTracker(
            storage_dir=os.path.join(self.temp_monitoring_dir, "costs")
        )
        
        # Test data parameters
        self.test_symbols = ["NQU4"]
        self.test_start = datetime(2024, 8, 1, 14, 0)
        self.test_end = self.test_start + timedelta(hours=1)
    
    def tearDown(self):
        """Clean up after each test."""
        # Stop any running monitors
        try:
            self.performance_monitor.stop_monitoring()
        except:
            pass
        
        # Clean up temporary directories
        shutil.rmtree(self.temp_cache_dir, ignore_errors=True)
        shutil.rmtree(self.temp_monitoring_dir, ignore_errors=True)
    
    def test_unified_data_access_with_monitoring(self):
        """Test unified data access with performance monitoring."""
        print("\n🧪 Testing unified data access with monitoring...")
        
        # Start performance monitoring
        self.performance_monitor.start_monitoring(interval_seconds=1)
        
        # Track the coordinator
        self.performance_monitor.track_component("unified_coordinator")
        
        try:
            # Make data requests with timing
            with self.performance_monitor.time_operation("historical_data_request"):
                data = self.coordinator.get_data(
                    self.test_symbols, 
                    self.test_start, 
                    self.test_end, 
                    "ohlcv-1m"
                )
            
            # Verify data was retrieved
            self.assertIsNotNone(data)
            print(f"   ✅ Retrieved {len(data)} records")
            
            # Record metrics
            self.performance_monitor.record_metric("data_records_retrieved", len(data))
            self.performance_monitor.increment_counter("api_requests")
            
            # Wait briefly for monitoring
            time.sleep(2)
            
            # Check that metrics were recorded
            stats = self.performance_monitor.get_component_stats("unified_coordinator")
            self.assertGreater(len(stats), 0)
            print(f"   ✅ Performance metrics recorded: {len(stats)} metrics")
            
            # Check system health
            health = self.performance_monitor.get_system_health()
            self.assertEqual(health['status'], 'excellent')
            print(f"   ✅ System health: {health['status']} ({health['health_score']}/100)")
            
        finally:
            self.performance_monitor.stop_monitoring()
    
    def test_cost_tracking_integration(self):
        """Test cost tracking integration with data requests."""
        print("\n💰 Testing cost tracking integration...")
        
        # Make a data request
        data = self.coordinator.get_data(
            self.test_symbols,
            self.test_start,
            self.test_end,
            "ohlcv-1m"
        )
        
        # Record the cost
        self.cost_tracker.record_api_call(
            symbol=self.test_symbols[0],
            schema="ohlcv-1m",
            data_size_mb=len(data) * 0.001,  # Rough estimate
            cache_hit=False
        )
        
        # Make the same request again (should be cache hit)
        data2 = self.coordinator.get_data(
            self.test_symbols,
            self.test_start,
            self.test_end,
            "ohlcv-1m"
        )
        
        # Record cache hit
        self.cost_tracker.record_api_call(
            symbol=self.test_symbols[0],
            schema="ohlcv-1m",
            data_size_mb=len(data2) * 0.001,
            cache_hit=True
        )
        
        # Verify cost tracking
        budget_status = self.cost_tracker.get_budget_status()
        self.assertGreater(budget_status['current_cost'], 0)
        print(f"   ✅ Current cost: ${budget_status['current_cost']:.3f}")
        
        # Check cache ROI
        cache_roi = self.cost_tracker.calculate_cache_roi(1)
        self.assertGreater(cache_roi['total_savings'], 0)
        print(f"   ✅ Cache savings: ${cache_roi['total_savings']:.3f} ({cache_roi['roi_percent']:.1f}% ROI)")
        
        # Get optimization recommendations
        recommendations = self.cost_tracker.get_optimization_recommendations()
        print(f"   ✅ Generated {len(recommendations)} optimization recommendations")
    
    def test_live_buffer_integration(self):
        """Test live buffer integration with the system."""
        print("\n📡 Testing live buffer integration...")
        
        # Create sample live data
        sample_ticks = create_sample_ticks(100, "NQU4")
        
        # Add to live buffer
        added_count = self.coordinator.live_buffer.add_ticks_batch(sample_ticks)
        self.assertEqual(added_count, 100)
        print(f"   ✅ Added {added_count} ticks to live buffer")
        
        # Test live data retrieval
        live_data = self.coordinator.live_buffer.get_recent_data(60)
        self.assertGreater(len(live_data), 0)
        print(f"   ✅ Retrieved {len(live_data)} records from live buffer")
        
        # Test price summary
        price_summary = self.coordinator.get_price_summary("NQU4", 60)
        self.assertIsNotNone(price_summary)
        print(f"   ✅ Price summary: Latest ${price_summary['latest_price']:.2f}, "
              f"Volume {price_summary['volume']}")
        
        # Test buffer statistics
        buffer_stats = self.coordinator.live_buffer.get_stats()
        self.assertEqual(buffer_stats.total_ticks, 100)
        print(f"   ✅ Buffer utilization: {buffer_stats.buffer_utilization:.1f}%")
    
    def test_configuration_system(self):
        """Test configuration system integration."""
        print("\n⚙️ Testing configuration system...")
        
        # Get configuration
        config = get_config()
        self.assertIsNotNone(config)
        
        # Validate configuration
        validation = config.validate_config()
        self.assertTrue(validation['valid'])
        print(f"   ✅ Configuration valid: {len(validation['warnings'])} warnings")
        
        # Test configuration access
        cache_config = config.get_cache_config()
        self.assertIn('cache_dir', cache_config)
        print(f"   ✅ Cache configuration: {cache_config['cache_dir']}")
        
        # Test dynamic updates
        original_size = config.cache.max_cache_size_mb
        config.update_cache_settings(max_cache_size_mb=1000.0)
        self.assertEqual(config.cache.max_cache_size_mb, 1000.0)
        
        # Restore original
        config.update_cache_settings(max_cache_size_mb=original_size)
        print(f"   ✅ Dynamic configuration updates working")
    
    def test_gap_detection_workflow(self):
        """Test gap detection and analysis workflow."""
        print("\n🔍 Testing gap detection workflow...")
        
        # Create gap detector
        gap_detector = GapDetector(self.coordinator.cached_client.cache_manager)
        
        # Detect gaps
        gaps = gap_detector.detect_gaps(
            symbols=["NQU4"],
            schemas=["ohlcv-1m"],
            analysis_period_days=10
        )
        
        print(f"   ✅ Detected {len(gaps)} data gaps")
        
        # Analyze gaps
        analysis = gap_detector.analyze_gaps(gaps)
        self.assertIn('total_gaps', analysis)
        print(f"   ✅ Gap analysis: ${analysis['total_cost']:.2f} to fill")
        
        # Generate recommendations
        if gaps:
            strategy = gap_detector.create_fill_strategy(gaps)
            print(f"   ✅ Fill strategy: {strategy.batch_size_days} day batches")
    
    def test_cache_cleanup_workflow(self):
        """Test cache cleanup and maintenance workflow."""
        print("\n🧹 Testing cache cleanup workflow...")
        
        # Create cleanup manager
        cleanup_manager = CacheCleanupManager(self.temp_cache_dir)
        
        # Analyze cache (should be empty initially)
        analysis = cleanup_manager.analyze_cache_usage()
        initial_size = analysis['total_size_mb']
        print(f"   ✅ Initial cache size: {initial_size:.1f} MB")
        
        # Add some data to cache first
        self.coordinator.get_data(
            self.test_symbols,
            self.test_start,
            self.test_end,
            "ohlcv-1m"
        )
        
        # Re-analyze
        analysis = cleanup_manager.analyze_cache_usage()
        new_size = analysis['total_size_mb']
        self.assertGreater(new_size, initial_size)
        print(f"   ✅ Cache size after data: {new_size:.1f} MB")
        
        # Test cleanup (dry run)
        cleanup_stats = cleanup_manager.cleanup_by_age(max_age_days=0, dry_run=True)
        print(f"   ✅ Cleanup simulation: {cleanup_stats['files_to_remove']} files to remove")
    
    def test_system_status_reporting(self):
        """Test comprehensive system status reporting."""
        print("\n📊 Testing system status reporting...")
        
        # Get coordinator status
        coordinator_stats = self.coordinator.get_system_stats()
        self.assertIn('coordinator', coordinator_stats)
        self.assertIn('cache_performance', coordinator_stats)
        print(f"   ✅ Coordinator stats: {len(coordinator_stats)} sections")
        
        # Get performance monitor health
        health = self.performance_monitor.get_system_health()
        self.assertIn('health_score', health)
        print(f"   ✅ System health: {health['status']} ({health['health_score']}/100)")
        
        # Get cost tracking status
        budget_status = self.cost_tracker.get_budget_status()
        self.assertIn('current_cost', budget_status)
        print(f"   ✅ Budget status: {budget_status['status']} "
              f"(${budget_status['current_cost']:.2f})")
        
        # Test integrated dashboard
        try:
            self.coordinator.print_system_status()
            self.performance_monitor.print_dashboard()
            self.cost_tracker.print_cost_report()
            print(f"   ✅ All status dashboards printed successfully")
        except Exception as e:
            self.fail(f"Dashboard printing failed: {e}")
    
    def test_error_handling_and_recovery(self):
        """Test system error handling and recovery."""
        print("\n🛡️ Testing error handling and recovery...")
        
        # Test invalid symbol handling
        try:
            data = self.coordinator.get_data(
                ["INVALID_SYMBOL"],
                self.test_start,
                self.test_end,
                "ohlcv-1m"
            )
            # Should handle gracefully
            print(f"   ✅ Invalid symbol handled gracefully: {len(data)} records")
        except Exception as e:
            print(f"   ✅ Invalid symbol error handled: {type(e).__name__}")
        
        # Test invalid date range
        try:
            future_start = datetime(2030, 1, 1)
            future_end = future_start + timedelta(hours=1)
            data = self.coordinator.get_data(
                self.test_symbols,
                future_start,
                future_end,
                "ohlcv-1m"
            )
            print(f"   ✅ Future date handled: {len(data)} records")
        except Exception as e:
            print(f"   ✅ Future date error handled: {type(e).__name__}")
        
        # Test system recovery after errors
        try:
            # Make a valid request after errors
            data = self.coordinator.get_data(
                self.test_symbols,
                self.test_start,
                self.test_end,
                "ohlcv-1m"
            )
            self.assertIsNotNone(data)
            print(f"   ✅ System recovery confirmed: {len(data)} records")
        except Exception as e:
            self.fail(f"System recovery failed: {e}")
    
    def test_performance_under_load(self):
        """Test system performance under load."""
        print("\n⚡ Testing system performance under load...")
        
        # Start performance monitoring
        self.performance_monitor.start_monitoring(interval_seconds=1)
        
        try:
            # Make multiple concurrent requests
            start_time = time.time()
            
            for i in range(5):
                # Vary the time ranges slightly
                test_start = self.test_start + timedelta(minutes=i*10)
                test_end = test_start + timedelta(minutes=30)
                
                with self.performance_monitor.time_operation(f"load_test_request_{i}"):
                    data = self.coordinator.get_data(
                        self.test_symbols,
                        test_start,
                        test_end,
                        "ohlcv-1m"
                    )
                
                # Record metrics
                self.performance_monitor.record_metric(f"request_{i}_records", len(data))
            
            total_time = time.time() - start_time
            print(f"   ✅ Completed 5 requests in {total_time:.2f}s")
            
            # Wait for monitoring to collect data
            time.sleep(2)
            
            # Check performance metrics
            all_stats = self.performance_monitor.metrics_collector.get_all_metrics_summary()
            timing_metrics = [name for name in all_stats.keys() if 'duration' in name]
            print(f"   ✅ Collected {len(timing_metrics)} timing metrics")
            
            # Verify system is still healthy
            health = self.performance_monitor.get_system_health()
            self.assertGreaterEqual(health['health_score'], 50)  # Should still be reasonable
            print(f"   ✅ System health after load: {health['status']} ({health['health_score']}/100)")
            
        finally:
            self.performance_monitor.stop_monitoring()


def run_comprehensive_tests():
    """Run all comprehensive system tests."""
    print("COMPREHENSIVE SYSTEM INTEGRATION TESTS")
    print("="*70)
    
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
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSystemIntegration)
    runner = unittest.TextTestRunner(verbosity=0)  # Reduce verbosity for cleaner output
    result = runner.run(suite)
    
    # Print summary
    print(f"\n{'='*70}")
    print(f"📊 TEST SUMMARY")
    print(f"{'='*70}")
    print(f"Tests run:               {result.testsRun}")
    print(f"Failures:                {len(result.failures)}")
    print(f"Errors:                  {len(result.errors)}")
    print(f"Success rate:            {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print(f"\n❌ FAILURES:")
        for test, traceback in result.failures:
            print(f"   - {test}: {traceback.split('AssertionError:')[-1].strip()}")
    
    if result.errors:
        print(f"\n🚨 ERRORS:")
        for test, traceback in result.errors:
            print(f"   - {test}: {traceback.split('Exception:')[-1].strip()}")
    
    if result.wasSuccessful():
        print(f"\n✅ ALL SYSTEM TESTS PASSED!")
        print(f"   The complete trading system is working correctly.")
    else:
        print(f"\n⚠️  Some tests failed. Please review the issues above.")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_comprehensive_tests()
    if not success:
        sys.exit(1)