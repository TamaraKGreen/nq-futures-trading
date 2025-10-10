#!/usr/bin/env python3
"""
Cache Cleanup Utilities

Provides intelligent cache management and cleanup strategies:
- Remove old/stale cache files
- Optimize disk usage
- Maintain cache performance
- Handle cache corruption recovery
- Smart retention policies
"""

import os
import sys
import shutil
import time
import argparse
import logging
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import json

from nq_futures_system.data.cache.cache_manager import CacheManager, IncrementalCacheManager


class CacheCleanupManager:
    """Manages cache cleanup operations with intelligent policies."""
    
    def __init__(self, cache_dir: str = "data/cache"):
        """
        Initialize cache cleanup manager.
        
        Args:
            cache_dir: Path to cache directory
        """
        self.cache_dir = Path(cache_dir)
        self.data_dir = self.cache_dir / "data"
        self.daily_dir = self.cache_dir / "daily"
        self.metadata_dir = self.cache_dir / "metadata"
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Cleanup statistics
        self.cleanup_stats = {
            'files_removed': 0,
            'bytes_freed': 0,
            'corrupt_files_found': 0,
            'metadata_updated': 0
        }
    
    def analyze_cache_usage(self) -> Dict:
        """
        Analyze current cache usage and provide insights.
        
        Returns:
            Dictionary with cache analysis
        """
        self.logger.info("Analyzing cache usage...")
        
        analysis = {
            'total_size_mb': 0,
            'total_files': 0,
            'by_directory': {},
            'by_file_age': {'< 1 day': 0, '1-7 days': 0, '1-4 weeks': 0, '> 1 month': 0},
            'by_file_size': {'< 1MB': 0, '1-10MB': 0, '10-100MB': 0, '> 100MB': 0},
            'oldest_file': None,
            'newest_file': None,
            'largest_file': None,
            'corruption_suspects': []
        }
        
        now = datetime.now()
        oldest_time = None
        newest_time = None
        largest_size = 0
        largest_file = None
        
        # Analyze each cache directory
        for cache_subdir in [self.data_dir, self.daily_dir]:
            if not cache_subdir.exists():
                continue
                
            dir_name = cache_subdir.name
            dir_stats = {'size_mb': 0, 'files': 0}
            
            for file_path in cache_subdir.rglob("*.parquet"):
                try:
                    stat = file_path.stat()
                    file_size = stat.st_size
                    file_time = datetime.fromtimestamp(stat.st_mtime)
                    
                    # Update totals
                    analysis['total_size_mb'] += file_size / (1024 * 1024)
                    analysis['total_files'] += 1
                    dir_stats['size_mb'] += file_size / (1024 * 1024)
                    dir_stats['files'] += 1
                    
                    # Track age distribution
                    age = now - file_time
                    if age.days < 1:
                        analysis['by_file_age']['< 1 day'] += 1
                    elif age.days <= 7:
                        analysis['by_file_age']['1-7 days'] += 1
                    elif age.days <= 30:
                        analysis['by_file_age']['1-4 weeks'] += 1
                    else:
                        analysis['by_file_age']['> 1 month'] += 1
                    
                    # Track size distribution
                    size_mb = file_size / (1024 * 1024)
                    if size_mb < 1:
                        analysis['by_file_size']['< 1MB'] += 1
                    elif size_mb <= 10:
                        analysis['by_file_size']['1-10MB'] += 1
                    elif size_mb <= 100:
                        analysis['by_file_size']['10-100MB'] += 1
                    else:
                        analysis['by_file_size']['> 100MB'] += 1
                    
                    # Track oldest/newest/largest
                    if oldest_time is None or file_time < oldest_time:
                        oldest_time = file_time
                        analysis['oldest_file'] = {'path': str(file_path), 'date': file_time}
                    
                    if newest_time is None or file_time > newest_time:
                        newest_time = file_time
                        analysis['newest_file'] = {'path': str(file_path), 'date': file_time}
                    
                    if file_size > largest_size:
                        largest_size = file_size
                        analysis['largest_file'] = {'path': str(file_path), 'size_mb': size_mb}
                    
                    # Check for potential corruption (very small files)
                    if file_size < 1024:  # Less than 1KB
                        analysis['corruption_suspects'].append({
                            'path': str(file_path),
                            'size': file_size,
                            'modified': file_time
                        })
                
                except (OSError, IOError) as e:
                    self.logger.warning(f"Failed to analyze {file_path}: {e}")
            
            analysis['by_directory'][dir_name] = dir_stats
        
        # Round the total size
        analysis['total_size_mb'] = round(analysis['total_size_mb'], 1)
        for dir_data in analysis['by_directory'].values():
            dir_data['size_mb'] = round(dir_data['size_mb'], 1)
        
        return analysis
    
    def cleanup_by_age(self, max_age_days: int, dry_run: bool = False) -> Dict:
        """
        Remove cache files older than specified age.
        
        Args:
            max_age_days: Maximum age in days to keep
            dry_run: If True, only simulate cleanup
            
        Returns:
            Cleanup statistics
        """
        cutoff_time = datetime.now() - timedelta(days=max_age_days)
        self.logger.info(f"Cleaning up files older than {max_age_days} days (before {cutoff_time})")
        
        if dry_run:
            self.logger.info("🔍 DRY RUN MODE - No files will be deleted")
        
        cleanup_stats = {
            'files_checked': 0,
            'files_to_remove': 0,
            'bytes_to_free': 0,
            'removed_files': []
        }
        
        for cache_subdir in [self.data_dir, self.daily_dir]:
            if not cache_subdir.exists():
                continue
            
            for file_path in cache_subdir.rglob("*.parquet"):
                try:
                    cleanup_stats['files_checked'] += 1
                    
                    file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_time < cutoff_time:
                        file_size = file_path.stat().st_size
                        cleanup_stats['files_to_remove'] += 1
                        cleanup_stats['bytes_to_free'] += file_size
                        
                        cleanup_stats['removed_files'].append({
                            'path': str(file_path),
                            'size_mb': round(file_size / (1024 * 1024), 2),
                            'age_days': (datetime.now() - file_time).days
                        })
                        
                        if not dry_run:
                            file_path.unlink()
                            self.logger.debug(f"Removed: {file_path}")
                
                except (OSError, IOError) as e:
                    self.logger.warning(f"Failed to process {file_path}: {e}")
        
        # Convert bytes to MB
        cleanup_stats['mb_to_free'] = round(cleanup_stats['bytes_to_free'] / (1024 * 1024), 1)
        
        if not dry_run and cleanup_stats['files_to_remove'] > 0:
            self.logger.info(f"✅ Removed {cleanup_stats['files_to_remove']} files, "
                           f"freed {cleanup_stats['mb_to_free']} MB")
        
        return cleanup_stats
    
    def cleanup_by_size(self, max_size_mb: float, dry_run: bool = False) -> Dict:
        """
        Remove oldest cache files to stay under size limit.
        
        Args:
            max_size_mb: Maximum cache size in MB
            dry_run: If True, only simulate cleanup
            
        Returns:
            Cleanup statistics
        """
        self.logger.info(f"Cleaning up cache to stay under {max_size_mb} MB")
        
        if dry_run:
            self.logger.info("🔍 DRY RUN MODE - No files will be deleted")
        
        # Get all cache files with metadata
        all_files = []
        current_size_mb = 0
        
        for cache_subdir in [self.data_dir, self.daily_dir]:
            if not cache_subdir.exists():
                continue
            
            for file_path in cache_subdir.rglob("*.parquet"):
                try:
                    stat = file_path.stat()
                    size_mb = stat.st_size / (1024 * 1024)
                    modified_time = datetime.fromtimestamp(stat.st_mtime)
                    
                    all_files.append({
                        'path': file_path,
                        'size_mb': size_mb,
                        'modified': modified_time
                    })
                    current_size_mb += size_mb
                
                except (OSError, IOError) as e:
                    self.logger.warning(f"Failed to process {file_path}: {e}")
        
        cleanup_stats = {
            'current_size_mb': round(current_size_mb, 1),
            'target_size_mb': max_size_mb,
            'files_to_remove': 0,
            'mb_to_free': 0,
            'removed_files': []
        }
        
        if current_size_mb <= max_size_mb:
            self.logger.info(f"✅ Cache size ({current_size_mb:.1f} MB) is already under limit")
            return cleanup_stats
        
        # Sort files by modification time (oldest first)
        all_files.sort(key=lambda x: x['modified'])
        
        # Remove oldest files until under size limit
        size_to_free = current_size_mb - max_size_mb
        freed_size = 0
        
        for file_info in all_files:
            if freed_size >= size_to_free:
                break
            
            cleanup_stats['files_to_remove'] += 1
            cleanup_stats['mb_to_free'] += file_info['size_mb']
            freed_size += file_info['size_mb']
            
            cleanup_stats['removed_files'].append({
                'path': str(file_info['path']),
                'size_mb': round(file_info['size_mb'], 2),
                'modified': file_info['modified']
            })
            
            if not dry_run:
                try:
                    file_info['path'].unlink()
                    self.logger.debug(f"Removed: {file_info['path']}")
                except (OSError, IOError) as e:
                    self.logger.warning(f"Failed to remove {file_info['path']}: {e}")
        
        cleanup_stats['mb_to_free'] = round(cleanup_stats['mb_to_free'], 1)
        
        if not dry_run and cleanup_stats['files_to_remove'] > 0:
            self.logger.info(f"✅ Removed {cleanup_stats['files_to_remove']} files, "
                           f"freed {cleanup_stats['mb_to_free']} MB")
        
        return cleanup_stats
    
    def remove_corrupt_files(self, dry_run: bool = False) -> Dict:
        """
        Remove potentially corrupt cache files.
        
        Args:
            dry_run: If True, only simulate cleanup
            
        Returns:
            Cleanup statistics
        """
        self.logger.info("Scanning for corrupt cache files...")
        
        if dry_run:
            self.logger.info("🔍 DRY RUN MODE - No files will be deleted")
        
        cleanup_stats = {
            'files_checked': 0,
            'corrupt_files': 0,
            'removed_files': []
        }
        
        for cache_subdir in [self.data_dir, self.daily_dir]:
            if not cache_subdir.exists():
                continue
            
            for file_path in cache_subdir.rglob("*.parquet"):
                cleanup_stats['files_checked'] += 1
                
                is_corrupt = False
                try:
                    # Check file size (very small files are likely corrupt)
                    file_size = file_path.stat().st_size
                    if file_size < 1024:  # Less than 1KB
                        is_corrupt = True
                        reason = f"too small ({file_size} bytes)"
                    
                    # Try to read the file header
                    if not is_corrupt:
                        try:
                            import pandas as pd
                            # Just read metadata, don't load full file
                            df = pd.read_parquet(file_path, nrows=0)
                            if len(df.columns) == 0:
                                is_corrupt = True
                                reason = "no columns"
                        except Exception as e:
                            is_corrupt = True
                            reason = f"read error: {str(e)[:50]}"
                    
                    if is_corrupt:
                        cleanup_stats['corrupt_files'] += 1
                        cleanup_stats['removed_files'].append({
                            'path': str(file_path),
                            'size_mb': round(file_size / (1024 * 1024), 3),
                            'reason': reason
                        })
                        
                        if not dry_run:
                            file_path.unlink()
                            self.logger.warning(f"Removed corrupt file: {file_path} ({reason})")
                
                except (OSError, IOError) as e:
                    self.logger.warning(f"Failed to check {file_path}: {e}")
        
        if not dry_run and cleanup_stats['corrupt_files'] > 0:
            self.logger.info(f"✅ Removed {cleanup_stats['corrupt_files']} corrupt files")
        
        return cleanup_stats
    
    def optimize_cache_structure(self, dry_run: bool = False) -> Dict:
        """
        Optimize cache directory structure and remove empty directories.
        
        Args:
            dry_run: If True, only simulate optimization
            
        Returns:
            Optimization statistics
        """
        self.logger.info("Optimizing cache directory structure...")
        
        if dry_run:
            self.logger.info("🔍 DRY RUN MODE - No changes will be made")
        
        stats = {
            'empty_dirs_removed': 0,
            'dirs_optimized': 0
        }
        
        # Remove empty directories
        for cache_subdir in [self.data_dir, self.daily_dir]:
            if not cache_subdir.exists():
                continue
            
            # Walk directory tree bottom-up to remove empty dirs
            for root, dirs, files in os.walk(cache_subdir, topdown=False):
                for dir_name in dirs:
                    dir_path = Path(root) / dir_name
                    try:
                        if not any(dir_path.iterdir()):  # Empty directory
                            if not dry_run:
                                dir_path.rmdir()
                            stats['empty_dirs_removed'] += 1
                            self.logger.debug(f"Removed empty directory: {dir_path}")
                    except (OSError, IOError):
                        pass  # Directory not empty or permission issue
        
        if not dry_run and stats['empty_dirs_removed'] > 0:
            self.logger.info(f"✅ Removed {stats['empty_dirs_removed']} empty directories")
        
        return stats
    
    def print_cleanup_report(self, analysis: Dict, age_cleanup: Dict = None,
                           size_cleanup: Dict = None, corrupt_cleanup: Dict = None):
        """Print a formatted cleanup report."""
        print("\n" + "="*60)
        print("🧹 CACHE CLEANUP REPORT")
        print("="*60)
        
        # Current state
        print(f"📊 CURRENT CACHE STATE:")
        print(f"   Total size:          {analysis['total_size_mb']:.1f} MB")
        print(f"   Total files:         {analysis['total_files']:,}")
        print(f"   Oldest file:         {analysis['oldest_file']['date'].strftime('%Y-%m-%d') if analysis['oldest_file'] else 'N/A'}")
        print(f"   Corruption suspects: {len(analysis['corruption_suspects'])}")
        
        print(f"\n📁 BY DIRECTORY:")
        for dir_name, stats in analysis['by_directory'].items():
            print(f"   {dir_name:>10}: {stats['files']:>4} files, {stats['size_mb']:>6.1f} MB")
        
        print(f"\n⏰ BY FILE AGE:")
        for age_range, count in analysis['by_file_age'].items():
            print(f"   {age_range:>10}: {count:>4} files")
        
        # Cleanup results
        if age_cleanup:
            print(f"\n🗓️  AGE-BASED CLEANUP:")
            print(f"   Files removed:       {age_cleanup['files_to_remove']}")
            print(f"   Space freed:         {age_cleanup['mb_to_free']:.1f} MB")
        
        if size_cleanup:
            print(f"\n📦 SIZE-BASED CLEANUP:")
            print(f"   Current size:        {size_cleanup['current_size_mb']:.1f} MB")
            print(f"   Target size:         {size_cleanup['target_size_mb']:.1f} MB")
            print(f"   Files removed:       {size_cleanup['files_to_remove']}")
            print(f"   Space freed:         {size_cleanup['mb_to_free']:.1f} MB")
        
        if corrupt_cleanup:
            print(f"\n🚨 CORRUPTION CLEANUP:")
            print(f"   Files checked:       {corrupt_cleanup['files_checked']}")
            print(f"   Corrupt files:       {corrupt_cleanup['corrupt_files']}")


def main():
    """CLI interface for cache cleanup."""
    parser = argparse.ArgumentParser(description="Clean up and optimize cache storage")
    parser.add_argument(
        '--cache-dir',
        default='data/cache',
        help='Cache directory path (default: data/cache)'
    )
    parser.add_argument(
        '--max-age-days',
        type=int,
        help='Remove files older than N days'
    )
    parser.add_argument(
        '--max-size-mb',
        type=float,
        help='Keep cache under N megabytes'
    )
    parser.add_argument(
        '--remove-corrupt',
        action='store_true',
        help='Remove potentially corrupt files'
    )
    parser.add_argument(
        '--optimize',
        action='store_true',
        help='Optimize directory structure'
    )
    parser.add_argument(
        '--analyze-only',
        action='store_true',
        help='Only analyze cache, do not clean'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be cleaned without doing it'
    )
    
    args = parser.parse_args()
    
    # Initialize cleanup manager
    cleanup_manager = CacheCleanupManager(args.cache_dir)
    
    # Always analyze first
    print("🔍 Analyzing cache usage...")
    analysis = cleanup_manager.analyze_cache_usage()
    
    # Initialize cleanup results
    age_cleanup = None
    size_cleanup = None
    corrupt_cleanup = None
    
    if not args.analyze_only:
        # Perform requested cleanup operations
        if args.max_age_days:
            age_cleanup = cleanup_manager.cleanup_by_age(args.max_age_days, args.dry_run)
        
        if args.max_size_mb:
            size_cleanup = cleanup_manager.cleanup_by_size(args.max_size_mb, args.dry_run)
        
        if args.remove_corrupt:
            corrupt_cleanup = cleanup_manager.remove_corrupt_files(args.dry_run)
        
        if args.optimize:
            optimize_stats = cleanup_manager.optimize_cache_structure(args.dry_run)
            print(f"✅ Directory optimization: {optimize_stats['empty_dirs_removed']} empty dirs removed")
    
    # Print comprehensive report
    cleanup_manager.print_cleanup_report(analysis, age_cleanup, size_cleanup, corrupt_cleanup)


if __name__ == '__main__':
    main()