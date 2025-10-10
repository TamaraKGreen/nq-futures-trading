"""
Cache Manager for Databento historical data.

Provides intelligent caching to minimize API calls and costs.
Key features:
- Automatic cache hit/miss tracking
- Parquet compression for efficient storage
- Daily incremental updates
- Gap detection and filling
"""

import os
import json
import hashlib
import pandas as pd
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Manages local cache for Databento historical data.
    
    Features:
    - Stores data as compressed Parquet files
    - Tracks cache metadata and statistics
    - Handles incremental daily updates
    - Provides gap detection for missing data
    """
    
    def __init__(self, cache_dir: str = "data/cache"):
        """
        Initialize cache manager.
        
        Args:
            cache_dir: Root directory for cache storage
        """
        self.cache_dir = Path(cache_dir)
        self.data_dir = self.cache_dir / "data"
        self.daily_dir = self.cache_dir / "daily" 
        self.metadata_dir = self.cache_dir / "metadata"
        
        # Ensure directories exist
        self._ensure_directories()
        
        # Load cache metadata
        self.metadata_file = self.metadata_dir / "cache_index.json"
        self.metadata = self._load_metadata()
        
        # Statistics tracking
        self.stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "total_requests": 0,
            "bytes_cached": 0,
            "api_calls_saved": 0
        }
    
    def _ensure_directories(self):
        """Create cache directory structure if it doesn't exist."""
        for directory in [self.data_dir, self.daily_dir, self.metadata_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"Cache directories ready: {self.cache_dir}")
    
    def _load_metadata(self) -> Dict[str, Any]:
        """Load cache metadata from disk."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load metadata: {e}, starting fresh")
        
        # Return default metadata structure
        return {
            "cache_files": {},
            "daily_files": {},
            "last_update": None,
            "version": "1.0"
        }
    
    def _save_metadata(self):
        """Save cache metadata to disk."""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2, default=str)
        except IOError as e:
            logger.error(f"Failed to save metadata: {e}")
    
    def _get_cache_path(self, symbols: List[str], start: datetime, 
                       end: datetime, schema: str) -> Path:
        """
        Generate cache file path for given parameters.
        
        Args:
            symbols: List of symbols
            start: Start datetime
            end: End datetime
            schema: Data schema
            
        Returns:
            Path to cache file
        """
        # Create hash of request parameters for unique filename
        symbols_str = "_".join(sorted(symbols))
        date_str = f"{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}"
        
        # Create subdirectory for symbol organization
        symbol_dir = self.data_dir / symbols[0]
        symbol_dir.mkdir(exist_ok=True)
        
        # Generate filename
        filename = f"{symbols_str}_{date_str}_{schema}.parquet"
        return symbol_dir / filename
    
    def get(self, symbols: List[str], start: datetime, end: datetime, 
           schema: str = "trades") -> Optional[pd.DataFrame]:
        """
        Retrieve data from cache if available.
        
        Args:
            symbols: List of symbols to retrieve
            start: Start datetime
            end: End datetime
            schema: Data schema
            
        Returns:
            DataFrame if cached, None if not found
        """
        cache_path = self._get_cache_path(symbols, start, end, schema)
        
        self.stats["total_requests"] += 1
        
        if cache_path.exists():
            try:
                df = pd.read_parquet(cache_path)
                self.stats["cache_hits"] += 1
                self.stats["api_calls_saved"] += 1
                
                logger.info(f"Cache HIT: {symbols} {schema} ({len(df)} records)")
                return df
                
            except Exception as e:
                logger.warning(f"Failed to read cache file {cache_path}: {e}")
                
        self.stats["cache_misses"] += 1
        logger.info(f"Cache MISS: {symbols} {schema}")
        return None
    
    def set(self, data: pd.DataFrame, symbols: List[str], start: datetime, 
           end: datetime, schema: str = "trades"):
        """
        Store data in cache.
        
        Args:
            data: DataFrame to cache
            symbols: List of symbols
            start: Start datetime
            end: End datetime
            schema: Data schema
        """
        if data.empty:
            logger.warning("Attempted to cache empty DataFrame")
            return
            
        cache_path = self._get_cache_path(symbols, start, end, schema)
        
        try:
            # Save data with compression
            data.to_parquet(cache_path, compression='snappy')
            
            # Update metadata
            cache_key = str(cache_path.relative_to(self.cache_dir))
            self.metadata["cache_files"][cache_key] = {
                "symbols": symbols,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "schema": schema,
                "rows": len(data),
                "cached_at": datetime.now().isoformat(),
                "file_size": cache_path.stat().st_size
            }
            
            # Update statistics
            file_size = cache_path.stat().st_size
            self.stats["bytes_cached"] += file_size
            
            self._save_metadata()
            
            logger.info(f"Cached {len(data)} records ({file_size/1024/1024:.1f} MB): {symbols} {schema}")
            
        except Exception as e:
            logger.error(f"Failed to cache data: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache performance metrics
        """
        total_requests = self.stats["total_requests"]
        hit_rate = (self.stats["cache_hits"] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "cache_hits": self.stats["cache_hits"],
            "cache_misses": self.stats["cache_misses"],
            "total_requests": total_requests,
            "hit_rate_percent": round(hit_rate, 1),
            "api_calls_saved": self.stats["api_calls_saved"],
            "cache_size_mb": round(self.stats["bytes_cached"] / 1024 / 1024, 1),
            "files_cached": len(self.metadata["cache_files"]),
            "last_update": self.metadata.get("last_update")
        }


class IncrementalCacheManager(CacheManager):
    """
    Extended cache manager with daily incremental update capabilities.
    
    This handles the common pattern of adding new daily data while
    reusing existing cached historical data.
    """
    
    def get_latest_cached_date(self, symbol: str, schema: str) -> Optional[date]:
        """Find the latest date we have cached for this symbol/schema."""
        key = f"{symbol}_{schema}"
        if key not in self.metadata.get("daily_files", {}):
            return None
        
        dates = [
            datetime.fromisoformat(d).date() 
            for d in self.metadata["daily_files"][key].keys()
        ]
        return max(dates) if dates else None
    
    def find_missing_dates(self, symbol: str, schema: str, 
                          start: date, end: date) -> List[date]:
        """Find which dates we need to fetch from API."""
        missing = []
        current = start
        
        while current <= end:
            # Skip weekends (simplified - real version would check market calendar)
            if current.weekday() < 5:  # Monday=0, Friday=4
                if not self.has_cached_date(symbol, schema, current):
                    missing.append(current)
            current += timedelta(days=1)
        
        return missing
    
    def has_cached_date(self, symbol: str, schema: str, date_obj: date) -> bool:
        """Check if we have this specific date cached."""
        key = f"{symbol}_{schema}"
        daily_files = self.metadata.get("daily_files", {})
        
        if key not in daily_files:
            return False
        
        date_str = date_obj.isoformat()
        return date_str in daily_files[key]
    
    def cache_daily_data(self, data: pd.DataFrame, symbol: str, 
                        date_obj: date, schema: str):
        """Cache a single day's data."""
        if data.empty:
            return
            
        filename = f"{symbol}_{date_obj.isoformat()}_{schema}.parquet"
        filepath = self.daily_dir / filename
        
        # Save the data
        data.to_parquet(filepath, compression='snappy')
        
        # Update metadata
        key = f"{symbol}_{schema}"
        if "daily_files" not in self.metadata:
            self.metadata["daily_files"] = {}
        if key not in self.metadata["daily_files"]:
            self.metadata["daily_files"][key] = {}
        
        self.metadata["daily_files"][key][date_obj.isoformat()] = {
            "file": str(filepath),
            "rows": len(data),
            "cached_at": datetime.now().isoformat(),
            "file_size": filepath.stat().st_size
        }
        
        self._save_metadata()
        logger.info(f"Cached daily data: {symbol} {date_obj} ({len(data)} records)")