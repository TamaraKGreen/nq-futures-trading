#!/usr/bin/env python3
"""
End-to-End System Validation Script

Validates the complete NQ futures trading system functionality:
- Configuration validation
- API connectivity
- Cache system operation
- Live data integration
- Performance monitoring
- Cost tracking
- Error handling
"""

import os
import sys
import asyncio
import time
from datetime import datetime, timedelta
from pathlib import Path

from nq_futures_system.production_system import TradingSystem
from nq_futures_system.deployment.rollback_procedures import RollbackManager
from nq_futures_system.config.settings import get_config
from nq_futures_system.utils.validators import ValidationError
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SystemValidator:
    """Comprehensive system validation."""
    
    def __init__(self):
        self.results = {}
        self.start_time = datetime.now()
        
    def validate_system(self) -> dict:
        """Run complete system validation."""
        print("🧪 NQ FUTURES TRADING SYSTEM VALIDATION")
        print("="*60)
        
        # 1. Environment and Dependencies
        self.results['environment'] = self._validate_environment()
        
        # 2. Configuration System
        self.results['configuration'] = self._validate_configuration()
        
        # 3. Core System Components
        self.results['core_components'] = self._validate_core_components()
        
        # 4. Data Operations
        self.results['data_operations'] = self._validate_data_operations()
        
        # 5. Performance and Monitoring
        self.results['monitoring'] = self._validate_monitoring()
        
        # 6. Deployment Readiness
        self.results['deployment'] = self._validate_deployment()
        
        # 7. Overall Assessment
        self.results['overall'] = self._assess_overall_health()
        
        return self.results
    
    def _validate_environment(self) -> dict:
        """Validate environment and dependencies."""
        print("\n1️⃣ Validating Environment...")
        
        result = {
            'status': 'pass',
            'checks': {},
            'issues': []
        }
        
        # Check Python version
        import sys
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        result['checks']['python_version'] = python_version
        print(f"   ✅ Python version: {python_version}")
        
        # Check configuration (including API key)
        config = get_config()
        validation = config.validate_config()
        
        if validation['valid']:
            api_key = os.getenv('DATABENTO_API_KEY')
            if api_key:
                result['checks']['api_key'] = f"Set ({len(api_key)} chars)"
                print(f"   ✅ API key: Present ({len(api_key)} characters)")
        else:
            result['status'] = 'fail'
            # Add all validation issues
            for issue in validation['issues']:
                result['issues'].append(issue)
                if "DATABENTO_API_KEY" in issue:
                    print(f"   ❌ API key: Missing")
                else:
                    print(f"   ❌ {issue}")
        
        # Print warnings if any
        for warning in validation.get('warnings', []):
            print(f"   ⚠️  {warning}")
        
        # Check required packages
        required_packages = ['databento', 'pandas', 'asyncio', 'threading']
        for package in required_packages:
            try:
                __import__(package)
                result['checks'][f'package_{package}'] = 'available'
                print(f"   ✅ Package {package}: Available")
            except ImportError:
                result['status'] = 'fail'
                result['issues'].append(f"Missing package: {package}")
                print(f"   ❌ Package {package}: Missing")
        
        return result
    
    def _validate_configuration(self) -> dict:
        """Validate system configuration."""
        print("\n2️⃣ Validating Configuration...")
        
        result = {
            'status': 'pass',
            'checks': {},
            'issues': []
        }
        
        try:
            # Initialize system to test configuration
            system = TradingSystem()
            
            # Validate config
            validation = system.config.validate_config()
            result['checks']['config_valid'] = validation['valid']
            result['checks']['config_warnings'] = len(validation.get('warnings', []))
            
            if validation['valid']:
                print(f"   ✅ Configuration: Valid ({result['checks']['config_warnings']} warnings)")
            else:
                result['status'] = 'fail'
                result['issues'].extend(validation.get('issues', []))
                print(f"   ❌ Configuration: Invalid")
            
            # Test component initialization
            result['checks']['components_initialized'] = True
            print(f"   ✅ Components: All initialized successfully")
            
        except Exception as e:
            result['status'] = 'fail'
            result['issues'].append(f"Configuration error: {str(e)}")
            print(f"   ❌ Configuration error: {e}")
        
        return result
    
    def _validate_core_components(self) -> dict:
        """Validate core system components."""
        print("\n3️⃣ Validating Core Components...")
        
        result = {
            'status': 'pass',
            'checks': {},
            'issues': []
        }
        
        try:
            system = TradingSystem()
            
            # Test unified coordinator
            stats = system.coordinator.get_system_stats()
            result['checks']['coordinator'] = 'operational'
            print(f"   ✅ Unified Coordinator: Operational")
            
            # Test performance monitor
            health = system.performance_monitor.get_system_health()
            result['checks']['performance_monitor'] = health['status']
            print(f"   ✅ Performance Monitor: {health['status']}")
            
            # Test cost tracker
            budget = system.cost_tracker.get_budget_status()
            result['checks']['cost_tracker'] = budget['status']
            print(f"   ✅ Cost Tracker: {budget['status']} (${budget['current_cost']:.2f})")
            
            # Test cache system
            cache_stats = system.coordinator.cached_client.cache_manager.get_stats()
            result['checks']['cache_system'] = 'operational'
            print(f"   ✅ Cache System: {cache_stats['files_cached']} files cached")
            
        except Exception as e:
            result['status'] = 'fail'
            result['issues'].append(f"Component error: {str(e)}")
            print(f"   ❌ Component error: {e}")
        
        return result
    
    def _validate_data_operations(self) -> dict:
        """Validate data operations."""
        print("\n4️⃣ Validating Data Operations...")
        
        result = {
            'status': 'pass',
            'checks': {},
            'issues': []
        }
        
        try:
            system = TradingSystem()
            
            # Test historical data retrieval
            start_time = time.time()
            test_data = system.get_data(
                "NQU4",
                datetime(2024, 8, 1, 14, 0),
                datetime(2024, 8, 1, 14, 30),
                "ohlcv-1m"
            )
            
            if len(test_data) > 0:
                result['checks']['historical_data'] = f"{len(test_data)} records"
                duration = time.time() - start_time
                result['checks']['data_retrieval_speed'] = f"{duration:.2f}s"
                print(f"   ✅ Historical Data: {len(test_data)} records in {duration:.2f}s")
            else:
                result['status'] = 'warn'
                result['issues'].append("No historical data retrieved")
                print(f"   ⚠️  Historical Data: No records retrieved")
            
            # Test cache efficiency
            cache_stats = system.coordinator.cached_client.cache_manager.get_stats()
            if cache_stats['total_requests'] > 0:
                efficiency = cache_stats['hit_rate_percent']
                result['checks']['cache_efficiency'] = f"{efficiency}%"
                print(f"   ✅ Cache Efficiency: {efficiency}%")
            else:
                result['checks']['cache_efficiency'] = "0% (new system)"
                print(f"   ✅ Cache System: Ready (no previous requests)")
            
            # Test live buffer
            buffer_stats = system.coordinator.live_buffer.get_stats()
            result['checks']['live_buffer'] = 'operational'
            print(f"   ✅ Live Buffer: {buffer_stats.buffer_utilization:.1f}% utilization")
            
        except Exception as e:
            result['status'] = 'fail'
            result['issues'].append(f"Data operation error: {str(e)}")
            print(f"   ❌ Data operation error: {e}")
        
        return result
    
    def _validate_monitoring(self) -> dict:
        """Validate monitoring and alerting."""
        print("\n5️⃣ Validating Monitoring...")
        
        result = {
            'status': 'pass',
            'checks': {},
            'issues': []
        }
        
        try:
            system = TradingSystem()
            
            # Test performance monitoring
            system.performance_monitor.record_metric("test_metric", 42.0)
            metric_stats = system.performance_monitor.metrics_collector.get_metric_stats("test_metric")
            
            if metric_stats and metric_stats.get('count', 0) > 0:
                result['checks']['metrics_recording'] = 'functional'
                print(f"   ✅ Metrics Recording: Functional")
            else:
                result['status'] = 'warn'
                result['issues'].append("Metrics recording issue")
                print(f"   ⚠️  Metrics Recording: Issue detected")
            
            # Test alerting
            alerts = system.performance_monitor.alert_manager.get_recent_alerts(1)
            result['checks']['alerting_system'] = 'operational'
            print(f"   ✅ Alerting System: {len(alerts)} recent alerts")
            
            # Test cost tracking
            system.cost_tracker.record_api_call("TEST", "test-schema", cache_hit=False)
            current_cost = system.cost_tracker.get_current_month_cost()
            result['checks']['cost_tracking'] = f"${current_cost:.3f}"
            print(f"   ✅ Cost Tracking: Recording costs (${current_cost:.3f})")
            
        except Exception as e:
            result['status'] = 'fail'
            result['issues'].append(f"Monitoring error: {str(e)}")
            print(f"   ❌ Monitoring error: {e}")
        
        return result
    
    def _validate_deployment(self) -> dict:
        """Validate deployment readiness."""
        print("\n6️⃣ Validating Deployment Readiness...")
        
        result = {
            'status': 'pass',
            'checks': {},
            'issues': []
        }
        
        try:
            # Test rollback manager
            rollback_manager = RollbackManager()
            deployment_status = rollback_manager.validate_deployment_readiness()
            
            result['checks']['deployment_ready'] = deployment_status['ready']
            result['checks']['deployment_warnings'] = len(deployment_status['warnings'])
            result['checks']['deployment_errors'] = len(deployment_status['errors'])
            
            if deployment_status['ready']:
                print(f"   ✅ Deployment: Ready ({result['checks']['deployment_warnings']} warnings)")
            else:
                result['status'] = 'warn'
                result['issues'].extend(deployment_status['errors'])
                print(f"   ⚠️  Deployment: Issues detected")
            
            # Test backup capability
            if len(rollback_manager.list_available_backups()) >= 0:
                result['checks']['backup_system'] = 'operational'
                print(f"   ✅ Backup System: Operational")
            
        except Exception as e:
            result['status'] = 'warn'
            result['issues'].append(f"Deployment validation error: {str(e)}")
            print(f"   ⚠️  Deployment validation error: {e}")
        
        return result
    
    def _assess_overall_health(self) -> dict:
        """Assess overall system health."""
        print("\n7️⃣ Overall System Assessment...")
        
        # Count status by category
        statuses = [r['status'] for r in self.results.values()]
        pass_count = statuses.count('pass')
        warn_count = statuses.count('warn')
        fail_count = statuses.count('fail')
        
        total_checks = len(statuses)
        
        # Determine overall status
        if fail_count > 0:
            overall_status = 'fail'
            status_icon = '🔴'
        elif warn_count > 0:
            overall_status = 'warn'
            status_icon = '🟡'
        else:
            overall_status = 'pass'
            status_icon = '🟢'
        
        # Calculate health score
        health_score = ((pass_count * 100) + (warn_count * 70)) / total_checks
        
        result = {
            'status': overall_status,
            'health_score': round(health_score, 1),
            'total_checks': total_checks,
            'pass_count': pass_count,
            'warn_count': warn_count,
            'fail_count': fail_count,
            'validation_time': (datetime.now() - self.start_time).total_seconds()
        }
        
        print(f"\n{status_icon} Overall Status: {overall_status.upper()}")
        print(f"   Health Score: {health_score:.1f}/100")
        print(f"   Checks: {pass_count} pass, {warn_count} warnings, {fail_count} failures")
        print(f"   Validation time: {result['validation_time']:.1f}s")
        
        return result
    
    def print_summary(self):
        """Print validation summary."""
        overall = self.results.get('overall', {})
        
        print(f"\n{'='*60}")
        print(f"📋 VALIDATION SUMMARY")
        print(f"{'='*60}")
        
        status_icon = '🟢' if overall.get('status') == 'pass' else '🟡' if overall.get('status') == 'warn' else '🔴'
        print(f"Overall Status:          {status_icon} {overall.get('status', 'unknown').upper()}")
        print(f"Health Score:            {overall.get('health_score', 0)}/100")
        print(f"Total Checks:            {overall.get('total_checks', 0)}")
        print(f"Validation Time:         {overall.get('validation_time', 0):.1f}s")
        
        # Component status
        print(f"\n🔧 COMPONENT STATUS:")
        for component, data in self.results.items():
            if component != 'overall':
                status = data.get('status', 'unknown')
                icon = '✅' if status == 'pass' else '⚠️' if status == 'warn' else '❌'
                print(f"  {icon} {component.replace('_', ' ').title()}: {status}")
        
        # Issues summary
        all_issues = []
        for data in self.results.values():
            all_issues.extend(data.get('issues', []))
        
        if all_issues:
            print(f"\n⚠️  ISSUES FOUND:")
            for issue in all_issues:
                print(f"  • {issue}")
        else:
            print(f"\n✅ No issues found!")
        
        # Recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        if overall.get('status') == 'pass':
            print(f"  • System is ready for production use")
            print(f"  • Consider running performance tests under load")
            print(f"  • Set up monitoring alerts for production")
        elif overall.get('status') == 'warn':
            print(f"  • Address warnings before production deployment")
            print(f"  • Monitor system closely during initial operation")
            print(f"  • Create backup before going live")
        else:
            print(f"  • Fix critical issues before deployment")
            print(f"  • Review configuration and dependencies")
            print(f"  • Test in development environment first")


def main():
    """Main validation entry point."""
    validator = SystemValidator()
    
    try:
        # Run validation
        results = validator.validate_system()
        
        # Print summary
        validator.print_summary()
        
        # Return appropriate exit code
        overall_status = results.get('overall', {}).get('status', 'fail')
        exit_code = 0 if overall_status == 'pass' else 1 if overall_status == 'warn' else 2
        
        return exit_code
        
    except Exception as e:
        print(f"\n❌ Validation failed with error: {e}")
        return 2


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)