"""
Live Data Manager for Streaming Coordination

Manages live market data streams with:
- Multiple symbol subscription management
- Automatic reconnection and error handling
- Rate limiting and flow control
- Integration with live data buffer
- Health monitoring and diagnostics
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Callable, Any
from dataclasses import dataclass
import threading
from enum import Enum

# Add parent directory to path
import sys
import os
from nq_futures_system.data.live.live_buffer import LiveDataBuffer, LiveTick
from nq_futures_system.data.collectors.databento_client import DatabentoClient
from nq_futures_system.config.settings import get_config

logger = logging.getLogger(__name__)


class StreamState(Enum):
    """States for live data streams."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass
class StreamStats:
    """Statistics for a live data stream."""
    symbol: str
    state: StreamState
    connected_since: Optional[datetime]
    total_ticks: int
    ticks_per_second: float
    last_tick_time: Optional[datetime]
    error_count: int
    reconnect_count: int


@dataclass
class SubscriptionConfig:
    """Configuration for a symbol subscription."""
    symbol: str
    schema: str = "trades"
    dataset: str = "GLBX.MDP3"
    enabled: bool = True
    auto_reconnect: bool = True
    max_reconnects: int = 10
    reconnect_delay: float = 5.0


class LiveDataManager:
    """
    Manages live market data streaming and coordination.
    
    Features:
    - Multi-symbol subscription management
    - Automatic reconnection with exponential backoff
    - Rate limiting and flow control
    - Health monitoring
    - Integration with live buffer
    """
    
    def __init__(self, 
                 buffer: LiveDataBuffer,
                 client: DatabentoClient,
                 max_concurrent_streams: int = 10):
        """
        Initialize live data manager.
        
        Args:
            buffer: LiveDataBuffer instance for storing data
            client: DatabentoClient for API access
            max_concurrent_streams: Maximum concurrent subscriptions
        """
        self.buffer = buffer
        self.client = client
        self.max_concurrent_streams = max_concurrent_streams
        
        # Subscription management
        self.subscriptions: Dict[str, SubscriptionConfig] = {}
        self.stream_stats: Dict[str, StreamStats] = {}
        self.active_tasks: Dict[str, asyncio.Task] = {}
        
        # State management
        self.is_running = False
        self.manager_task: Optional[asyncio.Task] = None
        self.health_check_task: Optional[asyncio.Task] = None
        
        # Callbacks and event handlers
        self.tick_callbacks: List[Callable[[LiveTick], None]] = []
        self.connection_callbacks: List[Callable[[str, StreamState], None]] = []
        self.error_callbacks: List[Callable[[str, Exception], None]] = []
        
        # Configuration
        config = get_config()
        self.heartbeat_interval = config.trading.heartbeat_interval_seconds
        self.health_check_interval = 30  # seconds
        
        # Thread safety
        self.lock = asyncio.Lock()
        
        logger.info(f"LiveDataManager initialized: max_streams={max_concurrent_streams}")
    
    async def add_subscription(self, config: SubscriptionConfig) -> bool:
        """
        Add a new symbol subscription.
        
        Args:
            config: Subscription configuration
            
        Returns:
            True if subscription added successfully
        """
        async with self.lock:
            if len(self.subscriptions) >= self.max_concurrent_streams:
                logger.warning(f"Maximum concurrent streams ({self.max_concurrent_streams}) reached")
                return False
            
            symbol = config.symbol
            if symbol in self.subscriptions:
                logger.warning(f"Subscription for {symbol} already exists")
                return False
            
            self.subscriptions[symbol] = config
            self.stream_stats[symbol] = StreamStats(
                symbol=symbol,
                state=StreamState.DISCONNECTED,
                connected_since=None,
                total_ticks=0,
                ticks_per_second=0.0,
                last_tick_time=None,
                error_count=0,
                reconnect_count=0
            )
            
            # Start the stream if manager is running
            if self.is_running and config.enabled:
                await self._start_stream(symbol)
            
            logger.info(f"Added subscription for {symbol} ({config.schema})")
            return True
    
    async def remove_subscription(self, symbol: str) -> bool:
        """
        Remove a symbol subscription.
        
        Args:
            symbol: Symbol to remove
            
        Returns:
            True if subscription removed successfully
        """
        async with self.lock:
            if symbol not in self.subscriptions:
                logger.warning(f"No subscription found for {symbol}")
                return False
            
            # Stop the stream if running
            await self._stop_stream(symbol)
            
            # Remove from tracking
            del self.subscriptions[symbol]
            del self.stream_stats[symbol]
            
            logger.info(f"Removed subscription for {symbol}")
            return True
    
    async def start_manager(self):
        """Start the live data manager."""
        if self.is_running:
            logger.warning("LiveDataManager is already running")
            return
        
        self.is_running = True
        
        # Start enabled subscriptions
        enabled_symbols = [
            symbol for symbol, config in self.subscriptions.items()
            if config.enabled
        ]
        
        logger.info(f"Starting LiveDataManager with {len(enabled_symbols)} subscriptions")
        
        # Start all enabled streams
        for symbol in enabled_symbols:
            await self._start_stream(symbol)
        
        # Start health monitoring
        self.health_check_task = asyncio.create_task(self._health_check_loop())
        
        logger.info("LiveDataManager started successfully")
    
    async def stop_manager(self):
        """Stop the live data manager."""
        if not self.is_running:
            return
        
        logger.info("Stopping LiveDataManager...")
        self.is_running = False
        
        # Stop all active streams
        async with self.lock:
            stop_tasks = []
            for symbol in list(self.active_tasks.keys()):
                stop_tasks.append(self._stop_stream(symbol))
            
            if stop_tasks:
                await asyncio.gather(*stop_tasks, return_exceptions=True)
        
        # Stop health monitoring
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass
        
        logger.info("LiveDataManager stopped")
    
    async def _start_stream(self, symbol: str):
        """Start streaming for a specific symbol."""
        if symbol in self.active_tasks:
            logger.debug(f"Stream for {symbol} already active")
            return
        
        config = self.subscriptions[symbol]
        stats = self.stream_stats[symbol]
        
        stats.state = StreamState.CONNECTING
        await self._notify_connection_state(symbol, StreamState.CONNECTING)
        
        # Create streaming task
        task = asyncio.create_task(self._stream_worker(symbol))
        self.active_tasks[symbol] = task
        
        logger.info(f"Started stream for {symbol}")
    
    async def _stop_stream(self, symbol: str):
        """Stop streaming for a specific symbol."""
        if symbol not in self.active_tasks:
            return
        
        task = self.active_tasks[symbol]
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        del self.active_tasks[symbol]
        
        stats = self.stream_stats[symbol]
        stats.state = StreamState.STOPPED
        stats.connected_since = None
        
        await self._notify_connection_state(symbol, StreamState.STOPPED)
        logger.info(f"Stopped stream for {symbol}")
    
    async def _stream_worker(self, symbol: str):
        """Worker coroutine for a single symbol stream."""
        config = self.subscriptions[symbol]
        stats = self.stream_stats[symbol]
        
        reconnect_count = 0
        start_time = time.time()
        
        while self.is_running and reconnect_count < config.max_reconnects:
            try:
                # Subscribe to live data
                await self.client.subscribe_live(
                    symbols=[symbol],
                    schema=config.schema,
                    callback=self._create_tick_handler(symbol),
                    dataset=config.dataset
                )
                
                # Update state
                stats.state = StreamState.CONNECTED
                stats.connected_since = datetime.utcnow()
                stats.reconnect_count = reconnect_count
                await self._notify_connection_state(symbol, StreamState.CONNECTED)
                
                # Start live feed processing
                await self.client.start_live_feed()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                stats.error_count += 1
                stats.state = StreamState.ERROR
                await self._notify_error(symbol, e)
                
                if config.auto_reconnect and reconnect_count < config.max_reconnects:
                    # Exponential backoff for reconnection
                    delay = config.reconnect_delay * (2 ** min(reconnect_count, 5))
                    logger.warning(f"Stream {symbol} error: {e}. Reconnecting in {delay:.1f}s")
                    
                    stats.state = StreamState.RECONNECTING
                    await self._notify_connection_state(symbol, StreamState.RECONNECTING)
                    
                    await asyncio.sleep(delay)
                    reconnect_count += 1
                else:
                    logger.error(f"Stream {symbol} failed permanently: {e}")
                    break
        
        # Final state update
        stats.state = StreamState.DISCONNECTED
        stats.connected_since = None
        await self._notify_connection_state(symbol, StreamState.DISCONNECTED)
    
    def _create_tick_handler(self, symbol: str) -> Callable:
        """Create a tick handler for a specific symbol."""
        
        async def handle_tick(record):
            """Handle incoming tick data."""
            try:
                # Convert Databento record to LiveTick
                tick = LiveTick(
                    timestamp=getattr(record, 'ts_event', datetime.utcnow()),
                    symbol=symbol,
                    price=getattr(record, 'price', 0) / 1e9 if hasattr(record, 'price') else 0,
                    size=getattr(record, 'size', 0),
                    side=None,  # Would need order flow data to determine
                    trade_id=getattr(record, 'trade_id', None),
                    exchange=getattr(record, 'exchange', None)
                )
                
                # Add to buffer
                self.buffer.add_tick(tick)
                
                # Update statistics
                stats = self.stream_stats[symbol]
                stats.total_ticks += 1
                stats.last_tick_time = tick.timestamp
                
                # Calculate ticks per second
                if stats.connected_since:
                    elapsed = (datetime.utcnow() - stats.connected_since).total_seconds()
                    if elapsed > 0:
                        stats.ticks_per_second = stats.total_ticks / elapsed
                
                # Notify callbacks
                for callback in self.tick_callbacks:
                    try:
                        callback(tick)
                    except Exception as e:
                        logger.warning(f"Tick callback error: {e}")
                
            except Exception as e:
                logger.error(f"Error handling tick for {symbol}: {e}")
                stats = self.stream_stats[symbol]
                stats.error_count += 1
        
        return handle_tick
    
    async def _health_check_loop(self):
        """Periodic health check for all streams."""
        while self.is_running:
            try:
                await self._perform_health_check()
                await asyncio.sleep(self.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
                await asyncio.sleep(self.health_check_interval)
    
    async def _perform_health_check(self):
        """Perform health check on all active streams."""
        current_time = datetime.utcnow()
        stale_threshold = timedelta(seconds=60)  # Consider stale after 1 minute
        
        for symbol, stats in self.stream_stats.items():
            if stats.state == StreamState.CONNECTED:
                # Check for stale data
                if stats.last_tick_time:
                    time_since_last_tick = current_time - stats.last_tick_time
                    if time_since_last_tick > stale_threshold:
                        logger.warning(f"Stream {symbol} appears stale: {time_since_last_tick}")
                
                # Check tick rate
                if stats.ticks_per_second < 0.1:  # Less than 1 tick per 10 seconds
                    logger.warning(f"Stream {symbol} has low tick rate: {stats.ticks_per_second:.2f}/s")
    
    async def _notify_connection_state(self, symbol: str, state: StreamState):
        """Notify connection state callbacks."""
        for callback in self.connection_callbacks:
            try:
                callback(symbol, state)
            except Exception as e:
                logger.warning(f"Connection callback error: {e}")
    
    async def _notify_error(self, symbol: str, error: Exception):
        """Notify error callbacks."""
        for callback in self.error_callbacks:
            try:
                callback(symbol, error)
            except Exception as e:
                logger.warning(f"Error callback error: {e}")
    
    def add_tick_callback(self, callback: Callable[[LiveTick], None]):
        """Add a callback for tick events."""
        self.tick_callbacks.append(callback)
    
    def add_connection_callback(self, callback: Callable[[str, StreamState], None]):
        """Add a callback for connection state changes."""
        self.connection_callbacks.append(callback)
    
    def add_error_callback(self, callback: Callable[[str, Exception], None]):
        """Add a callback for error events."""
        self.error_callbacks.append(callback)
    
    def get_stream_stats(self) -> Dict[str, StreamStats]:
        """Get statistics for all streams."""
        return self.stream_stats.copy()
    
    def get_manager_stats(self) -> Dict[str, Any]:
        """Get overall manager statistics."""
        total_ticks = sum(stats.total_ticks for stats in self.stream_stats.values())
        connected_streams = sum(1 for stats in self.stream_stats.values() 
                              if stats.state == StreamState.CONNECTED)
        
        return {
            'is_running': self.is_running,
            'total_subscriptions': len(self.subscriptions),
            'connected_streams': connected_streams,
            'active_tasks': len(self.active_tasks),
            'total_ticks_received': total_ticks,
            'buffer_stats': self.buffer.get_stats()
        }
    
    def print_status(self):
        """Print formatted manager status."""
        manager_stats = self.get_manager_stats()
        
        print(f"\n{'='*60}")
        print(f"📡 LIVE DATA MANAGER STATUS")
        print(f"{'='*60}")
        print(f"Manager running:         {manager_stats['is_running']}")
        print(f"Total subscriptions:     {manager_stats['total_subscriptions']}")
        print(f"Connected streams:       {manager_stats['connected_streams']}")
        print(f"Active tasks:            {manager_stats['active_tasks']}")
        print(f"Total ticks received:    {manager_stats['total_ticks_received']:,}")
        
        print(f"\n📊 STREAM DETAILS:")
        for symbol, stats in self.stream_stats.items():
            status_icon = {
                StreamState.CONNECTED: "🟢",
                StreamState.CONNECTING: "🟡",
                StreamState.RECONNECTING: "🟠",
                StreamState.ERROR: "🔴",
                StreamState.DISCONNECTED: "⚫",
                StreamState.STOPPED: "⚪"
            }.get(stats.state, "❓")
            
            print(f"  {status_icon} {symbol:>8}: {stats.state.value:>12} | "
                  f"Ticks: {stats.total_ticks:>6,} | "
                  f"Rate: {stats.ticks_per_second:>6.1f}/s | "
                  f"Errors: {stats.error_count}")
        
        # Buffer stats
        buffer_stats = manager_stats['buffer_stats']
        print(f"\n📦 BUFFER STATUS:")
        print(f"  Buffer utilization:      {buffer_stats.buffer_utilization:.1f}%")
        print(f"  Memory usage:            {buffer_stats.buffer_size_mb:.1f} MB")
        print(f"  Symbols in buffer:       {len(buffer_stats.symbols)}")


async def demo_live_manager():
    """Demonstrate the live data manager."""
    print("LIVE DATA MANAGER DEMONSTRATION")
    print("="*60)
    
    # Note: This is a simplified demo since we can't actually connect to live feeds
    # without proper subscription access
    
    from data.collectors.databento_client import DatabentoClient
    
    # Create components
    buffer = LiveDataBuffer(max_size=10000)
    client = DatabentoClient()  # Will use env API key
    manager = LiveDataManager(buffer, client, max_concurrent_streams=5)
    
    # Add some subscriptions
    subscriptions = [
        SubscriptionConfig("NQZ5", "trades"),
        SubscriptionConfig("NQH6", "trades"),
        SubscriptionConfig("ESZ5", "trades")
    ]
    
    for sub_config in subscriptions:
        await manager.add_subscription(sub_config)
    
    # Show initial status
    manager.print_status()
    
    print(f"\n📝 CONFIGURATION:")
    print(f"  Max concurrent streams:  {manager.max_concurrent_streams}")
    print(f"  Heartbeat interval:      {manager.heartbeat_interval}s")
    print(f"  Health check interval:   {manager.health_check_interval}s")
    
    print(f"\n✅ Live manager demonstration complete!")
    print(f"   Note: Use start_manager() to begin actual streaming")


if __name__ == '__main__':
    asyncio.run(demo_live_manager())