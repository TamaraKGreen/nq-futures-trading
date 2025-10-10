"""
Performance Monitoring and Metrics System

Provides comprehensive monitoring of the trading system with:
- Real-time performance metrics
- Cost tracking and optimization
- System health monitoring  
- Alert generation
- Historical performance analysis
"""

import time
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from collections import deque, defaultdict
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Single performance measurement."""
    timestamp: datetime
    metric_name: str
    value: float
    tags: Dict[str, str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = {}


@dataclass
class SystemAlert:
    """System alert for monitoring."""
    timestamp: datetime
    severity: str  # 'info', 'warning', 'error', 'critical'
    component: str
    message: str
    metric_value: Optional[float] = None
    threshold: Optional[float] = None


class MetricsCollector:
    """Collects and aggregates performance metrics."""
    
    def __init__(self, max_history: int = 10000):
        """
        Initialize metrics collector.
        
        Args:
            max_history: Maximum number of metrics to store in memory
        """
        self.max_history = max_history
        self.metrics: deque = deque(maxlen=max_history)
        self.aggregated_stats: Dict[str, Dict] = defaultdict(dict)
        self.lock = threading.RLock()
        
        # Performance counters
        self.counters: Dict[str, int] = defaultdict(int)
        self.timers: Dict[str, List[float]] = defaultdict(list)
        
        logger.info(f"MetricsCollector initialized with max_history={max_history}")
    
    def record_metric(self, name: str, value: float, tags: Dict[str, str] = None):
        """
        Record a performance metric.
        
        Args:
            name: Metric name
            value: Metric value
            tags: Optional tags for categorization
        """
        with self.lock:
            metric = PerformanceMetric(
                timestamp=datetime.utcnow(),
                metric_name=name,
                value=value,
                tags=tags or {}
            )
            self.metrics.append(metric)
            
            # Update aggregated stats
            self._update_aggregated_stats(metric)
    
    def increment_counter(self, name: str, amount: int = 1, tags: Dict[str, str] = None):
        """Increment a counter metric."""
        with self.lock:
            self.counters[name] += amount
            self.record_metric(f"{name}_count", self.counters[name], tags)
    
    def record_timing(self, name: str, duration: float, tags: Dict[str, str] = None):
        """Record a timing metric."""
        with self.lock:
            self.timers[name].append(duration)
            # Keep only recent timings
            if len(self.timers[name]) > 1000:
                self.timers[name] = self.timers[name][-1000:]
            
            self.record_metric(f"{name}_duration", duration, tags)
            
            # Record aggregated timing stats
            timings = self.timers[name]
            if len(timings) >= 10:  # Need at least 10 samples
                avg_duration = sum(timings) / len(timings)
                self.record_metric(f"{name}_avg_duration", avg_duration, tags)
    
    def _update_aggregated_stats(self, metric: PerformanceMetric):
        """Update aggregated statistics for a metric."""
        name = metric.metric_name
        value = metric.value
        
        if name not in self.aggregated_stats:
            self.aggregated_stats[name] = {
                'count': 0,
                'sum': 0.0,
                'min': float('inf'),
                'max': float('-inf'),
                'last_value': 0.0,
                'last_updated': None
            }
        
        stats = self.aggregated_stats[name]
        stats['count'] += 1
        stats['sum'] += value
        stats['min'] = min(stats['min'], value)
        stats['max'] = max(stats['max'], value)
        stats['last_value'] = value
        stats['last_updated'] = metric.timestamp
        stats['avg'] = stats['sum'] / stats['count']
    
    def get_metric_stats(self, name: str) -> Optional[Dict]:
        """Get aggregated statistics for a metric."""
        with self.lock:
            return self.aggregated_stats.get(name, {}).copy()
    
    def get_recent_metrics(self, name: str, minutes: int = 5) -> List[PerformanceMetric]:
        """Get recent metrics for a specific name."""
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        
        with self.lock:
            return [
                metric for metric in self.metrics
                if metric.metric_name == name and metric.timestamp >= cutoff
            ]
    
    def get_all_metrics_summary(self) -> Dict[str, Dict]:
        """Get summary of all tracked metrics."""
        with self.lock:
            return {name: stats.copy() for name, stats in self.aggregated_stats.items()}


class AlertManager:
    """Manages system alerts and notifications."""
    
    def __init__(self, max_alerts: int = 1000):
        """
        Initialize alert manager.
        
        Args:
            max_alerts: Maximum number of alerts to store
        """
        self.max_alerts = max_alerts
        self.alerts: deque = deque(maxlen=max_alerts)
        self.alert_rules: Dict[str, Dict] = {}
        self.alert_callbacks: List[Callable[[SystemAlert], None]] = []
        self.lock = threading.RLock()
        
        # Default alert rules
        self._setup_default_rules()
        
        logger.info(f"AlertManager initialized with max_alerts={max_alerts}")
    
    def _setup_default_rules(self):
        """Setup default alerting rules."""
        self.alert_rules = {
            'cache_efficiency': {
                'warning_threshold': 70.0,
                'critical_threshold': 50.0,
                'comparison': 'less_than'
            },
            'api_response_time': {
                'warning_threshold': 2.0,
                'critical_threshold': 5.0,
                'comparison': 'greater_than'
            },
            'buffer_utilization': {
                'warning_threshold': 80.0,
                'critical_threshold': 95.0,
                'comparison': 'greater_than'
            },
            'error_rate': {
                'warning_threshold': 5.0,
                'critical_threshold': 10.0,
                'comparison': 'greater_than'
            }
        }
    
    def add_alert_rule(self, metric_name: str, warning_threshold: float, 
                      critical_threshold: float, comparison: str = 'greater_than'):
        """
        Add a custom alert rule.
        
        Args:
            metric_name: Name of metric to monitor
            warning_threshold: Warning level threshold
            critical_threshold: Critical level threshold
            comparison: 'greater_than' or 'less_than'
        """
        with self.lock:
            self.alert_rules[metric_name] = {
                'warning_threshold': warning_threshold,
                'critical_threshold': critical_threshold,
                'comparison': comparison
            }
        
        logger.info(f"Added alert rule for {metric_name}")
    
    def check_metric_for_alerts(self, metric: PerformanceMetric):
        """Check if a metric triggers any alerts."""
        metric_name = metric.metric_name
        
        if metric_name not in self.alert_rules:
            return
        
        rule = self.alert_rules[metric_name]
        value = metric.value
        
        # Determine alert level
        alert_level = None
        threshold = None
        
        if rule['comparison'] == 'greater_than':
            if value >= rule['critical_threshold']:
                alert_level = 'critical'
                threshold = rule['critical_threshold']
            elif value >= rule['warning_threshold']:
                alert_level = 'warning'
                threshold = rule['warning_threshold']
        else:  # less_than
            if value <= rule['critical_threshold']:
                alert_level = 'critical'
                threshold = rule['critical_threshold']
            elif value <= rule['warning_threshold']:
                alert_level = 'warning'
                threshold = rule['warning_threshold']
        
        if alert_level:
            self._create_alert(
                severity=alert_level,
                component=metric_name,
                message=f"{metric_name} is {value:.2f} (threshold: {threshold:.2f})",
                metric_value=value,
                threshold=threshold
            )
    
    def _create_alert(self, severity: str, component: str, message: str,
                     metric_value: Optional[float] = None, threshold: Optional[float] = None):
        """Create and store an alert."""
        alert = SystemAlert(
            timestamp=datetime.utcnow(),
            severity=severity,
            component=component,
            message=message,
            metric_value=metric_value,
            threshold=threshold
        )
        
        with self.lock:
            self.alerts.append(alert)
        
        # Notify callbacks
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.warning(f"Alert callback error: {e}")
        
        logger.log(
            logging.WARNING if severity in ['warning', 'critical'] else logging.INFO,
            f"ALERT [{severity.upper()}] {component}: {message}"
        )
    
    def add_alert_callback(self, callback: Callable[[SystemAlert], None]):
        """Add a callback for alert notifications."""
        self.alert_callbacks.append(callback)
    
    def get_recent_alerts(self, hours: int = 1) -> List[SystemAlert]:
        """Get alerts from the last N hours."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        with self.lock:
            return [alert for alert in self.alerts if alert.timestamp >= cutoff]
    
    def get_alert_summary(self) -> Dict[str, int]:
        """Get summary of alert counts by severity."""
        recent_alerts = self.get_recent_alerts(24)  # Last 24 hours
        
        summary = {'info': 0, 'warning': 0, 'error': 0, 'critical': 0}
        for alert in recent_alerts:
            summary[alert.severity] += 1
        
        return summary


class PerformanceMonitor:
    """Main performance monitoring system."""
    
    def __init__(self, metrics_dir: str = "monitoring/metrics"):
        """
        Initialize performance monitor.
        
        Args:
            metrics_dir: Directory to store metrics data
        """
        self.metrics_dir = Path(metrics_dir)
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.metrics_collector = MetricsCollector()
        self.alert_manager = AlertManager()
        
        # Monitoring state
        self.is_monitoring = False
        self.monitoring_thread: Optional[threading.Thread] = None
        
        # Tracked components
        self.tracked_components = set()
        
        logger.info(f"PerformanceMonitor initialized: {metrics_dir}")
    
    def start_monitoring(self, interval_seconds: int = 30):
        """
        Start continuous monitoring.
        
        Args:
            interval_seconds: How often to collect system metrics
        """
        if self.is_monitoring:
            logger.warning("Monitoring is already running")
            return
        
        self.is_monitoring = True
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(interval_seconds,),
            daemon=True
        )
        self.monitoring_thread.start()
        
        logger.info(f"Performance monitoring started (interval: {interval_seconds}s)")
    
    def stop_monitoring(self):
        """Stop continuous monitoring."""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        
        logger.info("Performance monitoring stopped")
    
    def _monitoring_loop(self, interval_seconds: int):
        """Main monitoring loop."""
        while self.is_monitoring:
            try:
                self._collect_system_metrics()
                time.sleep(interval_seconds)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(interval_seconds)
    
    def _collect_system_metrics(self):
        """Collect system-wide performance metrics."""
        import psutil
        
        try:
            # CPU and memory metrics
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            
            self.record_metric("system_cpu_percent", cpu_percent)
            self.record_metric("system_memory_percent", memory.percent)
            self.record_metric("system_memory_mb", memory.used / 1024 / 1024)
            
            # Check for alerts
            self.alert_manager.check_metric_for_alerts(
                PerformanceMetric(datetime.utcnow(), "system_cpu_percent", cpu_percent)
            )
            self.alert_manager.check_metric_for_alerts(
                PerformanceMetric(datetime.utcnow(), "system_memory_percent", memory.percent)
            )
            
        except ImportError:
            # psutil not available, skip system metrics
            pass
        except Exception as e:
            logger.warning(f"Error collecting system metrics: {e}")
    
    def record_metric(self, name: str, value: float, tags: Dict[str, str] = None):
        """Record a performance metric."""
        self.metrics_collector.record_metric(name, value, tags)
        
        # Check for alerts
        metric = PerformanceMetric(datetime.utcnow(), name, value, tags)
        self.alert_manager.check_metric_for_alerts(metric)
    
    def record_timing(self, name: str, duration: float, tags: Dict[str, str] = None):
        """Record a timing metric."""
        self.metrics_collector.record_timing(name, duration, tags)
        
        # Check for alerts on timing metrics
        metric = PerformanceMetric(datetime.utcnow(), f"{name}_duration", duration, tags)
        self.alert_manager.check_metric_for_alerts(metric)
    
    def increment_counter(self, name: str, amount: int = 1, tags: Dict[str, str] = None):
        """Increment a counter metric."""
        self.metrics_collector.increment_counter(name, amount, tags)
    
    def time_operation(self, operation_name: str, tags: Dict[str, str] = None):
        """Context manager for timing operations."""
        return TimingContext(self, operation_name, tags)
    
    def track_component(self, component_name: str):
        """Start tracking a component."""
        self.tracked_components.add(component_name)
        logger.info(f"Now tracking component: {component_name}")
    
    def get_component_stats(self, component_name: str) -> Dict[str, Any]:
        """Get statistics for a tracked component."""
        # Get all metrics related to this component
        all_stats = self.metrics_collector.get_all_metrics_summary()
        
        component_stats = {}
        for metric_name, stats in all_stats.items():
            if component_name in metric_name:
                component_stats[metric_name] = stats
        
        return component_stats
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health assessment."""
        alert_summary = self.alert_manager.get_alert_summary()
        recent_alerts = self.alert_manager.get_recent_alerts(1)  # Last hour
        
        # Calculate health score (0-100)
        health_score = 100
        health_score -= alert_summary['critical'] * 20
        health_score -= alert_summary['warning'] * 5
        health_score -= alert_summary['error'] * 10
        health_score = max(0, health_score)
        
        # Determine health status
        if health_score >= 90:
            status = "excellent"
        elif health_score >= 75:
            status = "good"
        elif health_score >= 50:
            status = "fair"
        else:
            status = "poor"
        
        return {
            'health_score': health_score,
            'status': status,
            'alert_summary': alert_summary,
            'recent_alerts_count': len(recent_alerts),
            'tracked_components': list(self.tracked_components),
            'monitoring_active': self.is_monitoring
        }
    
    def export_metrics(self, filename: Optional[str] = None) -> str:
        """
        Export metrics to JSON file.
        
        Args:
            filename: Optional filename (auto-generated if None)
            
        Returns:
            Path to exported file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"metrics_export_{timestamp}.json"
        
        export_path = self.metrics_dir / filename
        
        # Prepare export data
        export_data = {
            'export_timestamp': datetime.utcnow().isoformat(),
            'metrics_summary': self.metrics_collector.get_all_metrics_summary(),
            'recent_alerts': [asdict(alert) for alert in self.alert_manager.get_recent_alerts(24)],
            'system_health': self.get_system_health(),
            'tracked_components': list(self.tracked_components)
        }
        
        # Write to file
        with open(export_path, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        logger.info(f"Metrics exported to {export_path}")
        return str(export_path)
    
    def print_dashboard(self):
        """Print a formatted monitoring dashboard."""
        health = self.get_system_health()
        alerts = self.alert_manager.get_alert_summary()
        
        print(f"\n{'='*60}")
        print(f"📊 PERFORMANCE MONITORING DASHBOARD")
        print(f"{'='*60}")
        
        # System health
        status_icons = {
            'excellent': '🟢',
            'good': '🟡', 
            'fair': '🟠',
            'poor': '🔴'
        }
        status_icon = status_icons.get(health['status'], '❓')
        
        print(f"System Health:           {status_icon} {health['status'].upper()} ({health['health_score']}/100)")
        print(f"Monitoring Active:       {'🟢 Yes' if health['monitoring_active'] else '🔴 No'}")
        print(f"Tracked Components:      {len(health['tracked_components'])}")
        
        # Alerts summary
        print(f"\n🚨 ALERTS (24h):")
        print(f"Critical:                🔴 {alerts['critical']}")
        print(f"Warning:                 🟡 {alerts['warning']}")
        print(f"Error:                   🟠 {alerts['error']}")
        print(f"Info:                    🔵 {alerts['info']}")
        
        # Recent metrics summary
        all_stats = self.metrics_collector.get_all_metrics_summary()
        if all_stats:
            print(f"\n📈 KEY METRICS:")
            for metric_name, stats in list(all_stats.items())[:5]:  # Show top 5
                print(f"{metric_name:>25}: {stats.get('last_value', 0):>8.2f} "
                      f"(avg: {stats.get('avg', 0):>6.2f})")
        
        # Component status
        if health['tracked_components']:
            print(f"\n🔧 TRACKED COMPONENTS:")
            for component in health['tracked_components']:
                print(f"  • {component}")


class TimingContext:
    """Context manager for timing operations."""
    
    def __init__(self, monitor: PerformanceMonitor, operation_name: str, tags: Dict[str, str] = None):
        self.monitor = monitor
        self.operation_name = operation_name
        self.tags = tags
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            duration = time.time() - self.start_time
            self.monitor.record_timing(self.operation_name, duration, self.tags)


# Global performance monitor instance
_performance_monitor = None

def get_performance_monitor() -> PerformanceMonitor:
    """Get global performance monitor instance."""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor


if __name__ == '__main__':
    # Demo the performance monitoring system
    print("PERFORMANCE MONITORING SYSTEM DEMONSTRATION")
    print("="*60)
    
    # Create monitor
    monitor = PerformanceMonitor()
    
    # Record some sample metrics
    monitor.record_metric("cache_efficiency", 85.5, {"component": "cache"})
    monitor.record_metric("api_response_time", 1.2, {"endpoint": "historical"})
    monitor.record_metric("buffer_utilization", 45.0, {"component": "live_buffer"})
    
    # Test timing
    with monitor.time_operation("data_processing", {"symbol": "NQZ5"}):
        time.sleep(0.1)  # Simulate work
    
    # Increment counters
    monitor.increment_counter("api_requests", 5)
    monitor.increment_counter("cache_hits", 4)
    
    # Track components
    monitor.track_component("unified_coordinator")
    monitor.track_component("cache_manager")
    
    # Show dashboard
    monitor.print_dashboard()
    
    # Export metrics
    export_file = monitor.export_metrics()
    print(f"\n✅ Metrics exported to: {export_file}")
    
    print(f"\n✅ Performance monitoring demonstration complete!")