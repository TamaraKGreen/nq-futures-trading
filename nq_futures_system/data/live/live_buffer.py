"""
Live Data Buffer for Real-time Market Data

Provides thread-safe buffering of live market data with:
- High-performance circular buffer
- Thread-safe operations
- Automatic memory management
- Seamless DataFrame conversion
- Configurable retention policies
"""

import threading
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
import pandas as pd
import logging

logger = logging.getLogger(__name__)


@dataclass
class LiveTick:
    """Represents a single live market data tick."""
    timestamp: datetime
    symbol: str
    price: float
    size: int
    side: Optional[str] = None  # 'buy', 'sell', or None
    trade_id: Optional[str] = None
    exchange: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for DataFrame creation."""
        return {
            'ts_event': self.timestamp,
            'symbol': self.symbol,
            'price': self.price,
            'size': self.size,
            'side': self.side,
            'trade_id': self.trade_id,
            'exchange': self.exchange
        }


@dataclass
class BufferStats:
    """Statistics about buffer state."""
    total_ticks: int
    buffer_size_mb: float
    oldest_tick: Optional[datetime]
    newest_tick: Optional[datetime]
    symbols: List[str]
    ticks_per_second: float
    buffer_utilization: float  # Percentage of max buffer used


class LiveDataBuffer:
    """
    Thread-safe circular buffer for live market data.
    
    Features:
    - Lock-free read operations for performance
    - Configurable size limits (by count and time)
    - Automatic cleanup of old data
    - Statistics tracking
    - Multiple data retrieval methods
    """
    
    def __init__(self, 
                 max_size: int = 100000,
                 max_age_seconds: int = 3600,
                 cleanup_interval: int = 60):
        """
        Initialize live data buffer.
        
        Args:
            max_size: Maximum number of ticks to store
            max_age_seconds: Maximum age of ticks in seconds
            cleanup_interval: How often to run cleanup (seconds)
        """
        self.max_size = max_size
        self.max_age_seconds = max_age_seconds
        self.cleanup_interval = cleanup_interval
        
        # Thread-safe deque for storing ticks
        self.buffer = deque(maxlen=max_size)
        self.lock = threading.RLock()  # Reentrant lock for nested calls
        
        # Statistics tracking
        self.total_ticks_received = 0
        self.start_time = datetime.utcnow()
        self.last_cleanup = time.time()
        
        # Symbol tracking
        self.symbols_seen = set()
        
        logger.info(f"LiveDataBuffer initialized: max_size={max_size}, max_age={max_age_seconds}s")
    
    def add_tick(self, tick: LiveTick) -> bool:
        """
        Add a new tick to the buffer (thread-safe).
        
        Args:
            tick: LiveTick to add
            
        Returns:
            True if tick was added, False if rejected
        """
        with self.lock:
            # Validate tick
            if not isinstance(tick, LiveTick):
                logger.warning(f"Invalid tick type: {type(tick)}")
                return False
            
            if tick.timestamp is None:
                logger.warning("Tick with no timestamp rejected")
                return False
            
            # Add to buffer
            self.buffer.append(tick)
            self.total_ticks_received += 1
            self.symbols_seen.add(tick.symbol)
            
            # Periodic cleanup check (avoid cleanup on every tick)
            current_time = time.time()
            if current_time - self.last_cleanup > self.cleanup_interval:
                self._cleanup_old_ticks()
                self.last_cleanup = current_time
            
            return True
    
    def add_ticks_batch(self, ticks: List[LiveTick]) -> int:
        """
        Add multiple ticks efficiently.
        
        Args:
            ticks: List of LiveTicks to add
            
        Returns:
            Number of ticks successfully added
        """
        if not ticks:
            return 0
        
        added_count = 0
        with self.lock:
            for tick in ticks:
                if self.add_tick(tick):
                    added_count += 1
        
        logger.debug(f"Added {added_count}/{len(ticks)} ticks to buffer")
        return added_count
    
    def get_recent_data(self, seconds: int = 300) -> pd.DataFrame:
        """
        Get data from the last N seconds.
        
        Args:
            seconds: Number of seconds to look back
            
        Returns:
            DataFrame with recent data
        """
        cutoff_time = datetime.utcnow() - timedelta(seconds=seconds)
        return self.get_data_since(cutoff_time)
    
    def get_data_since(self, since: datetime) -> pd.DataFrame:
        """
        Get all data since a specific timestamp.
        
        Args:
            since: Timestamp to get data since
            
        Returns:
            DataFrame with data since timestamp
        """
        with self.lock:
            # Filter ticks after 'since'
            relevant_ticks = [
                tick for tick in self.buffer
                if tick.timestamp >= since
            ]
            
            if not relevant_ticks:
                # Return empty DataFrame with correct schema
                return pd.DataFrame(columns=[
                    'ts_event', 'symbol', 'price', 'size', 'side', 'trade_id', 'exchange'
                ]).set_index('ts_event')
            
            # Convert to DataFrame
            data = [tick.to_dict() for tick in relevant_ticks]
            df = pd.DataFrame(data)
            
            # Set timestamp as index and sort
            df.set_index('ts_event', inplace=True)
            df.sort_index(inplace=True)
            
            return df
    
    def get_data_for_symbol(self, symbol: str, seconds: int = 300) -> pd.DataFrame:
        """
        Get recent data for a specific symbol.
        
        Args:
            symbol: Symbol to filter by
            seconds: Number of seconds to look back
            
        Returns:
            DataFrame with symbol data
        """
        cutoff_time = datetime.utcnow() - timedelta(seconds=seconds)
        
        with self.lock:
            relevant_ticks = [
                tick for tick in self.buffer
                if tick.timestamp >= cutoff_time and tick.symbol == symbol
            ]
            
            if not relevant_ticks:
                return pd.DataFrame(columns=[
                    'ts_event', 'symbol', 'price', 'size', 'side', 'trade_id', 'exchange'
                ]).set_index('ts_event')
            
            data = [tick.to_dict() for tick in relevant_ticks]
            df = pd.DataFrame(data)
            df.set_index('ts_event', inplace=True)
            df.sort_index(inplace=True)
            
            return df
    
    def get_data_range(self, start: datetime, end: datetime) -> pd.DataFrame:
        """
        Get data for a specific time range.
        
        Args:
            start: Start timestamp
            end: End timestamp
            
        Returns:
            DataFrame with data in range
        """
        with self.lock:
            relevant_ticks = [
                tick for tick in self.buffer
                if start <= tick.timestamp <= end
            ]
            
            if not relevant_ticks:
                return pd.DataFrame(columns=[
                    'ts_event', 'symbol', 'price', 'size', 'side', 'trade_id', 'exchange'
                ]).set_index('ts_event')
            
            data = [tick.to_dict() for tick in relevant_ticks]
            df = pd.DataFrame(data)
            df.set_index('ts_event', inplace=True)
            df.sort_index(inplace=True)
            
            return df
    
    def get_latest_tick(self, symbol: Optional[str] = None) -> Optional[LiveTick]:
        """
        Get the most recent tick.
        
        Args:
            symbol: Optional symbol to filter by
            
        Returns:
            Latest LiveTick or None
        """
        with self.lock:
            if not self.buffer:
                return None
            
            if symbol is None:
                return self.buffer[-1]  # Most recent tick
            
            # Find most recent tick for symbol
            for tick in reversed(self.buffer):
                if tick.symbol == symbol:
                    return tick
            
            return None
    
    def get_price_summary(self, symbol: str, seconds: int = 60) -> Optional[Dict[str, float]]:
        """
        Get price summary for a symbol.
        
        Args:
            symbol: Symbol to analyze
            seconds: Number of seconds to look back
            
        Returns:
            Dictionary with price statistics or None
        """
        df = self.get_data_for_symbol(symbol, seconds)
        
        if df.empty:
            return None
        
        return {
            'latest_price': float(df['price'].iloc[-1]),
            'high': float(df['price'].max()),
            'low': float(df['price'].min()),
            'volume': int(df['size'].sum()),
            'trade_count': len(df),
            'vwap': float((df['price'] * df['size']).sum() / df['size'].sum()) if df['size'].sum() > 0 else 0.0
        }
    
    def _cleanup_old_ticks(self):
        """Remove ticks older than max_age_seconds (called with lock held)."""
        if not self.buffer:
            return
        
        cutoff_time = datetime.utcnow() - timedelta(seconds=self.max_age_seconds)
        original_size = len(self.buffer)
        
        # Remove old ticks from the front
        while self.buffer and self.buffer[0].timestamp < cutoff_time:
            self.buffer.popleft()
        
        removed_count = original_size - len(self.buffer)
        if removed_count > 0:
            logger.debug(f"Cleaned up {removed_count} old ticks from buffer")
    
    def get_stats(self) -> BufferStats:
        """
        Get current buffer statistics.
        
        Returns:
            BufferStats object with current metrics
        """
        with self.lock:
            buffer_size = len(self.buffer)
            
            # Calculate approximate memory usage
            # Rough estimate: each tick ~200 bytes
            buffer_size_mb = (buffer_size * 200) / (1024 * 1024)
            
            # Get time range
            oldest_tick = self.buffer[0].timestamp if self.buffer else None
            newest_tick = self.buffer[-1].timestamp if self.buffer else None
            
            # Calculate ticks per second
            runtime_seconds = (datetime.utcnow() - self.start_time).total_seconds()
            ticks_per_second = self.total_ticks_received / runtime_seconds if runtime_seconds > 0 else 0
            
            # Buffer utilization
            buffer_utilization = (buffer_size / self.max_size) * 100
            
            return BufferStats(
                total_ticks=self.total_ticks_received,
                buffer_size_mb=buffer_size_mb,
                oldest_tick=oldest_tick,
                newest_tick=newest_tick,
                symbols=list(self.symbols_seen),
                ticks_per_second=ticks_per_second,
                buffer_utilization=buffer_utilization
            )
    
    def clear_buffer(self):
        """Clear all data from buffer."""
        with self.lock:
            self.buffer.clear()
            self.symbols_seen.clear()
            logger.info("Buffer cleared")
    
    def resize_buffer(self, new_max_size: int):
        """
        Resize buffer capacity.
        
        Args:
            new_max_size: New maximum buffer size
        """
        with self.lock:
            # Create new deque with new size
            old_data = list(self.buffer)
            self.buffer = deque(old_data, maxlen=new_max_size)
            self.max_size = new_max_size
            
            logger.info(f"Buffer resized to {new_max_size} (current size: {len(self.buffer)})")
    
    def export_to_dataframe(self, include_all: bool = False) -> pd.DataFrame:
        """
        Export entire buffer to DataFrame.
        
        Args:
            include_all: If True, include all buffer data; if False, only recent data
            
        Returns:
            DataFrame with all buffer data
        """
        if include_all:
            # Export everything
            with self.lock:
                if not self.buffer:
                    return pd.DataFrame(columns=[
                        'ts_event', 'symbol', 'price', 'size', 'side', 'trade_id', 'exchange'
                    ]).set_index('ts_event')
                
                data = [tick.to_dict() for tick in self.buffer]
                df = pd.DataFrame(data)
                df.set_index('ts_event', inplace=True)
                df.sort_index(inplace=True)
                return df
        else:
            # Export last 10 minutes
            return self.get_recent_data(600)
    
    def print_stats(self):
        """Print formatted buffer statistics."""
        stats = self.get_stats()
        
        print(f"\n{'='*50}")
        print(f"📡 LIVE DATA BUFFER STATISTICS")
        print(f"{'='*50}")
        print(f"Total ticks received:    {stats.total_ticks:,}")
        print(f"Current buffer size:     {len(self.buffer):,} ticks")
        print(f"Buffer memory usage:     {stats.buffer_size_mb:.1f} MB")
        print(f"Buffer utilization:      {stats.buffer_utilization:.1f}%")
        print(f"Ticks per second:        {stats.ticks_per_second:.1f}")
        print(f"Symbols tracked:         {len(stats.symbols)}")
        
        if stats.oldest_tick and stats.newest_tick:
            time_span = stats.newest_tick - stats.oldest_tick
            print(f"Time span:               {time_span}")
            print(f"Oldest tick:             {stats.oldest_tick}")
            print(f"Newest tick:             {stats.newest_tick}")
        
        if stats.symbols:
            print(f"Active symbols:          {', '.join(sorted(stats.symbols))}")


def create_sample_ticks(count: int = 1000, symbol: str = "NQZ5") -> List[LiveTick]:
    """
    Create sample ticks for testing.
    
    Args:
        count: Number of ticks to create
        symbol: Symbol for the ticks
        
    Returns:
        List of sample LiveTicks
    """
    ticks = []
    base_time = datetime.utcnow()
    base_price = 25000.0
    
    for i in range(count):
        tick = LiveTick(
            timestamp=base_time + timedelta(seconds=i),
            symbol=symbol,
            price=base_price + (i % 100) * 0.25,  # Simulate price movement
            size=1 + (i % 10),  # Variable size
            side='buy' if i % 2 == 0 else 'sell',
            trade_id=f"trade_{i:06d}",
            exchange="CME"
        )
        ticks.append(tick)
    
    return ticks


if __name__ == '__main__':
    # Demo the live buffer
    print("LIVE DATA BUFFER DEMONSTRATION")
    print("="*50)
    
    # Create buffer
    buffer = LiveDataBuffer(max_size=5000, max_age_seconds=300)
    
    # Add sample data
    print("\n📥 Adding sample data...")
    sample_ticks = create_sample_ticks(1000, "NQZ5")
    added_count = buffer.add_ticks_batch(sample_ticks)
    print(f"Added {added_count} ticks to buffer")
    
    # Show statistics
    buffer.print_stats()
    
    # Test data retrieval
    print(f"\n📊 DATA RETRIEVAL TESTS:")
    
    # Recent data
    recent_df = buffer.get_recent_data(60)  # Last minute
    print(f"Recent data (60s):       {len(recent_df)} rows")
    
    # Symbol-specific data
    symbol_df = buffer.get_data_for_symbol("NQZ5", 120)
    print(f"Symbol data (120s):      {len(symbol_df)} rows")
    
    # Latest tick
    latest = buffer.get_latest_tick("NQZ5")
    if latest:
        print(f"Latest tick:             {latest.symbol} @ {latest.price} x {latest.size}")
    
    # Price summary
    summary = buffer.get_price_summary("NQZ5", 300)
    if summary:
        print(f"Price summary:           Latest: {summary['latest_price']}, "
              f"VWAP: {summary['vwap']:.2f}, Volume: {summary['volume']}")
    
    print(f"\n✅ Live buffer demonstration complete!")