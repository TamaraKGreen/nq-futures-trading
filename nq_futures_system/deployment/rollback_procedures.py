#!/usr/bin/env python3
"""
Safe Deployment and Rollback Procedures

Provides automated rollback capabilities for the trading system:
- Configuration backup and restore
- Cache state preservation
- Service state management
- Database rollback procedures
- Safety checks and validation
"""

import os
import json
import shutil
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import subprocess
import threading
import time

logger = logging.getLogger(__name__)


class RollbackManager:
    """Manages safe deployment and rollback procedures."""
    
    def __init__(self, base_dir: str = "/Users/Mike/trading/input/nq_futures_system"):
        """
        Initialize rollback manager.
        
        Args:
            base_dir: Base directory of the trading system
        """
        self.base_dir = Path(base_dir)
        self.backup_dir = self.base_dir / "deployment" / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Critical directories to backup
        self.critical_dirs = [
            "config",
            "data/cache",
            "monitoring/metrics",
            "monitoring/costs"
        ]
        
        # Critical files to backup
        self.critical_files = [
            "production_system.py",
            ".env",
            "requirements.txt"
        ]
        
        # Service state
        self.service_state = {}
        
        logger.info(f"RollbackManager initialized: {base_dir}")
    
    def create_deployment_backup(self, deployment_name: str = None) -> str:
        """
        Create a complete backup before deployment.
        
        Args:
            deployment_name: Optional deployment identifier
            
        Returns:
            Backup identifier for rollback
        """
        if deployment_name is None:
            deployment_name = f"auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        backup_id = f"backup_{deployment_name}"
        backup_path = self.backup_dir / backup_id
        backup_path.mkdir(exist_ok=True)
        
        logger.info(f"🔄 Creating deployment backup: {backup_id}")
        
        try:
            # Create backup manifest
            manifest = {
                "backup_id": backup_id,
                "timestamp": datetime.now().isoformat(),
                "system_state": self._capture_system_state(),
                "backed_up_dirs": [],
                "backed_up_files": [],
                "git_commit": self._get_git_commit(),
                "environment": dict(os.environ)
            }
            
            # Backup critical directories
            for dir_name in self.critical_dirs:
                src_dir = self.base_dir / dir_name
                if src_dir.exists():
                    dst_dir = backup_path / dir_name
                    dst_dir.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
                    manifest["backed_up_dirs"].append(dir_name)
                    logger.info(f"   ✅ Backed up directory: {dir_name}")
            
            # Backup critical files
            for file_name in self.critical_files:
                src_file = self.base_dir / file_name
                if src_file.exists():
                    dst_file = backup_path / file_name
                    dst_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_file, dst_file)
                    manifest["backed_up_files"].append(file_name)
                    logger.info(f"   ✅ Backed up file: {file_name}")
            
            # Backup running services state
            manifest["running_services"] = self._get_running_services()
            
            # Save manifest
            with open(backup_path / "manifest.json", "w") as f:
                json.dump(manifest, f, indent=2, default=str)
            
            logger.info(f"✅ Deployment backup created: {backup_id}")
            return backup_id
            
        except Exception as e:
            logger.error(f"❌ Failed to create deployment backup: {e}")
            # Cleanup partial backup
            if backup_path.exists():
                shutil.rmtree(backup_path, ignore_errors=True)
            raise
    
    def rollback_deployment(self, backup_id: str, 
                          confirm_rollback: bool = False,
                          preserve_cache: bool = True) -> bool:
        """
        Rollback to a previous deployment state.
        
        Args:
            backup_id: Backup identifier to rollback to
            confirm_rollback: Must be True to proceed (safety check)
            preserve_cache: Whether to preserve cache data during rollback
            
        Returns:
            True if rollback successful
        """
        if not confirm_rollback:
            logger.error("❌ Rollback not confirmed. Set confirm_rollback=True to proceed.")
            return False
        
        backup_path = self.backup_dir / backup_id
        if not backup_path.exists():
            logger.error(f"❌ Backup not found: {backup_id}")
            return False
        
        logger.info(f"🔄 Starting rollback to: {backup_id}")
        
        try:
            # Load backup manifest
            with open(backup_path / "manifest.json", "r") as f:
                manifest = json.load(f)
            
            # Validate backup
            if not self._validate_backup(backup_path, manifest):
                logger.error("❌ Backup validation failed")
                return False
            
            # Stop running services first
            logger.info("🛑 Stopping running services...")
            self._stop_trading_system()
            
            # Create emergency backup of current state
            emergency_backup = self.create_deployment_backup("emergency_before_rollback")
            logger.info(f"🚨 Created emergency backup: {emergency_backup}")
            
            # Restore directories
            for dir_name in manifest["backed_up_dirs"]:
                if preserve_cache and "cache" in dir_name:
                    logger.info(f"   ⏭️ Skipping cache directory: {dir_name}")
                    continue
                
                src_dir = backup_path / dir_name
                dst_dir = self.base_dir / dir_name
                
                # Remove current directory
                if dst_dir.exists():
                    shutil.rmtree(dst_dir)
                
                # Restore from backup
                shutil.copytree(src_dir, dst_dir)
                logger.info(f"   ✅ Restored directory: {dir_name}")
            
            # Restore files
            for file_name in manifest["backed_up_files"]:
                src_file = backup_path / file_name
                dst_file = self.base_dir / file_name
                
                # Backup current file
                if dst_file.exists():
                    shutil.copy2(dst_file, f"{dst_file}.rollback_backup")
                
                # Restore from backup
                shutil.copy2(src_file, dst_file)
                logger.info(f"   ✅ Restored file: {file_name}")
            
            # Restore environment variables (critical ones only)
            self._restore_environment(manifest.get("environment", {}))
            
            # Validate system after rollback
            if self._validate_system_state():
                logger.info("✅ Rollback completed successfully")
                logger.info("⚠️  Please restart the trading system manually")
                return True
            else:
                logger.error("❌ System validation failed after rollback")
                return False
                
        except Exception as e:
            logger.error(f"❌ Rollback failed: {e}")
            return False
    
    def list_available_backups(self) -> List[Dict]:
        """List all available backups."""
        backups = []
        
        for backup_dir in self.backup_dir.iterdir():
            if backup_dir.is_dir():
                manifest_file = backup_dir / "manifest.json"
                if manifest_file.exists():
                    try:
                        with open(manifest_file, "r") as f:
                            manifest = json.load(f)
                        
                        backups.append({
                            "backup_id": manifest["backup_id"],
                            "timestamp": manifest["timestamp"],
                            "git_commit": manifest.get("git_commit", "unknown"),
                            "size_mb": self._get_backup_size(backup_dir),
                            "dirs_count": len(manifest.get("backed_up_dirs", [])),
                            "files_count": len(manifest.get("backed_up_files", []))
                        })
                    except (json.JSONDecodeError, KeyError):
                        logger.warning(f"Invalid backup manifest: {backup_dir}")
        
        # Sort by timestamp (newest first)
        backups.sort(key=lambda x: x["timestamp"], reverse=True)
        return backups
    
    def cleanup_old_backups(self, keep_count: int = 10) -> int:
        """
        Clean up old backups, keeping only the most recent ones.
        
        Args:
            keep_count: Number of backups to keep
            
        Returns:
            Number of backups removed
        """
        backups = self.list_available_backups()
        
        if len(backups) <= keep_count:
            logger.info(f"No cleanup needed: {len(backups)} backups (keeping {keep_count})")
            return 0
        
        backups_to_remove = backups[keep_count:]
        removed_count = 0
        
        for backup in backups_to_remove:
            backup_path = self.backup_dir / backup["backup_id"]
            try:
                shutil.rmtree(backup_path)
                removed_count += 1
                logger.info(f"🗑️ Removed old backup: {backup['backup_id']}")
            except Exception as e:
                logger.warning(f"Failed to remove backup {backup['backup_id']}: {e}")
        
        logger.info(f"✅ Cleanup complete: removed {removed_count} old backups")
        return removed_count
    
    def validate_deployment_readiness(self) -> Dict[str, any]:
        """
        Validate system readiness for deployment.
        
        Returns:
            Validation results with recommendations
        """
        results = {
            "ready": True,
            "checks": {},
            "warnings": [],
            "errors": [],
            "recommendations": []
        }
        
        # Check system state
        try:
            results["checks"]["system_running"] = self._is_trading_system_running()
            results["checks"]["disk_space"] = self._check_disk_space()
            results["checks"]["backup_space"] = self._check_backup_space()
            results["checks"]["git_status"] = self._get_git_status()
            results["checks"]["environment"] = self._check_environment()
            results["checks"]["dependencies"] = self._check_dependencies()
            
            # Analyze results
            if results["checks"]["system_running"]:
                results["warnings"].append("Trading system is currently running")
                results["recommendations"].append("Stop trading system before deployment")
            
            if results["checks"]["disk_space"] < 1000:  # Less than 1GB
                results["errors"].append(f"Low disk space: {results['checks']['disk_space']:.1f} MB")
                results["ready"] = False
            
            if results["checks"]["backup_space"] < 500:  # Less than 500MB for backups
                results["warnings"].append(f"Low backup space: {results['checks']['backup_space']:.1f} MB")
                results["recommendations"].append("Clean up old backups")
            
            if results["checks"]["git_status"]["uncommitted_changes"]:
                results["warnings"].append("Uncommitted changes detected")
                results["recommendations"].append("Commit or stash changes before deployment")
            
            # Check for recent backups
            backups = self.list_available_backups()
            if not backups:
                results["warnings"].append("No existing backups found")
                results["recommendations"].append("Create initial backup before first deployment")
            elif len(backups) == 1:
                results["recommendations"].append("Consider keeping more backup versions")
            
        except Exception as e:
            results["errors"].append(f"Validation error: {e}")
            results["ready"] = False
        
        return results
    
    def _capture_system_state(self) -> Dict:
        """Capture current system state."""
        return {
            "trading_system_running": self._is_trading_system_running(),
            "disk_usage": self._get_disk_usage(),
            "python_version": self._get_python_version(),
            "installed_packages": self._get_installed_packages(),
            "environment_vars": {
                k: v for k, v in os.environ.items() 
                if k.startswith(('DATABENTO_', 'TRADING_', 'CACHE_'))
            }
        }
    
    def _validate_backup(self, backup_path: Path, manifest: Dict) -> bool:
        """Validate backup integrity."""
        try:
            # Check all expected directories exist
            for dir_name in manifest["backed_up_dirs"]:
                if not (backup_path / dir_name).exists():
                    logger.error(f"Missing backup directory: {dir_name}")
                    return False
            
            # Check all expected files exist
            for file_name in manifest["backed_up_files"]:
                if not (backup_path / file_name).exists():
                    logger.error(f"Missing backup file: {file_name}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Backup validation error: {e}")
            return False
    
    def _stop_trading_system(self):
        """Stop the trading system safely."""
        try:
            # Check if system is running by looking for the process
            result = subprocess.run(
                ["pgrep", "-f", "production_system.py"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    if pid:
                        logger.info(f"🛑 Stopping trading system process: {pid}")
                        subprocess.run(["kill", "-TERM", pid])
                        time.sleep(5)  # Wait for graceful shutdown
                        
                        # Force kill if still running
                        result = subprocess.run(["kill", "-0", pid], capture_output=True)
                        if result.returncode == 0:
                            logger.warning(f"Force killing process: {pid}")
                            subprocess.run(["kill", "-KILL", pid])
            
        except Exception as e:
            logger.warning(f"Error stopping trading system: {e}")
    
    def _restore_environment(self, backup_env: Dict):
        """Restore critical environment variables."""
        critical_vars = [
            'DATABENTO_API_KEY',
            'TRADING_CONFIG_FILE',
            'CACHE_DIR'
        ]
        
        for var in critical_vars:
            if var in backup_env:
                os.environ[var] = backup_env[var]
                logger.info(f"   ✅ Restored environment variable: {var}")
    
    def _validate_system_state(self) -> bool:
        """Validate system state after rollback."""
        try:
            # Check critical files exist
            critical_files = [
                self.base_dir / "production_system.py",
                self.base_dir / "config" / "settings.py"
            ]
            
            for file_path in critical_files:
                if not file_path.exists():
                    logger.error(f"Missing critical file: {file_path}")
                    return False
            
            # Check Python syntax of main file
            result = subprocess.run([
                "python3", "-m", "py_compile", 
                str(self.base_dir / "production_system.py")
            ], capture_output=True)
            
            if result.returncode != 0:
                logger.error("Python syntax error in production_system.py")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"System validation error: {e}")
            return False
    
    def _get_git_commit(self) -> str:
        """Get current git commit hash."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.base_dir,
                capture_output=True,
                text=True
            )
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except:
            return "unknown"
    
    def _get_git_status(self) -> Dict:
        """Get git status information."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.base_dir,
                capture_output=True,
                text=True
            )
            
            uncommitted = bool(result.stdout.strip()) if result.returncode == 0 else False
            
            return {
                "uncommitted_changes": uncommitted,
                "current_commit": self._get_git_commit(),
                "current_branch": self._get_git_branch()
            }
        except:
            return {"uncommitted_changes": False, "current_commit": "unknown", "current_branch": "unknown"}
    
    def _get_git_branch(self) -> str:
        """Get current git branch."""
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.base_dir,
                capture_output=True,
                text=True
            )
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except:
            return "unknown"
    
    def _get_running_services(self) -> List[str]:
        """Get list of running services."""
        services = []
        try:
            # Check for trading system
            result = subprocess.run(
                ["pgrep", "-f", "production_system.py"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                services.append("trading_system")
        except:
            pass
        
        return services
    
    def _is_trading_system_running(self) -> bool:
        """Check if trading system is running."""
        return "trading_system" in self._get_running_services()
    
    def _check_disk_space(self) -> float:
        """Check available disk space in MB."""
        try:
            usage = shutil.disk_usage(self.base_dir)
            return usage.free / (1024 * 1024)  # Convert to MB
        except:
            return 0.0
    
    def _check_backup_space(self) -> float:
        """Check available space for backups in MB."""
        try:
            usage = shutil.disk_usage(self.backup_dir)
            return usage.free / (1024 * 1024)  # Convert to MB
        except:
            return 0.0
    
    def _check_environment(self) -> bool:
        """Check critical environment variables."""
        required_vars = ['DATABENTO_API_KEY']
        return all(os.getenv(var) for var in required_vars)
    
    def _check_dependencies(self) -> bool:
        """Check if dependencies are satisfied."""
        try:
            # Check if we can import critical modules
            import databento
            import pandas
            import asyncio
            return True
        except ImportError:
            return False
    
    def _get_disk_usage(self) -> Dict:
        """Get disk usage information."""
        try:
            usage = shutil.disk_usage(self.base_dir)
            return {
                "total_gb": usage.total / (1024**3),
                "used_gb": usage.used / (1024**3),
                "free_gb": usage.free / (1024**3),
                "usage_percent": (usage.used / usage.total) * 100
            }
        except:
            return {}
    
    def _get_python_version(self) -> str:
        """Get Python version."""
        import sys
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    
    def _get_installed_packages(self) -> Dict:
        """Get list of installed packages."""
        try:
            result = subprocess.run(
                ["pip", "list", "--format=json"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                packages = json.loads(result.stdout)
                return {pkg["name"]: pkg["version"] for pkg in packages}
        except:
            pass
        
        return {}
    
    def _get_backup_size(self, backup_path: Path) -> float:
        """Get backup size in MB."""
        try:
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(backup_path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    total_size += os.path.getsize(filepath)
            return total_size / (1024 * 1024)  # Convert to MB
        except:
            return 0.0
    
    def print_deployment_status(self):
        """Print deployment readiness status."""
        validation = self.validate_deployment_readiness()
        
        print(f"\n{'='*60}")
        print(f"🚀 DEPLOYMENT READINESS STATUS")
        print(f"{'='*60}")
        
        status_icon = "🟢" if validation["ready"] else "🔴"
        print(f"Deployment Ready:        {status_icon} {'Yes' if validation['ready'] else 'No'}")
        
        # System checks
        checks = validation["checks"]
        print(f"\n🔍 SYSTEM CHECKS:")
        print(f"Trading System:          {'🔴 Running' if checks.get('system_running') else '🟢 Stopped'}")
        print(f"Disk Space:              {checks.get('disk_space', 0):.1f} MB available")
        print(f"Backup Space:            {checks.get('backup_space', 0):.1f} MB available")
        print(f"Environment:             {'🟢 Valid' if checks.get('environment') else '🔴 Invalid'}")
        print(f"Dependencies:            {'🟢 Satisfied' if checks.get('dependencies') else '🔴 Missing'}")
        
        # Git status
        git_status = checks.get('git_status', {})
        git_icon = "🟡" if git_status.get('uncommitted_changes') else "🟢"
        print(f"Git Status:              {git_icon} {'Uncommitted changes' if git_status.get('uncommitted_changes') else 'Clean'}")
        print(f"Current Branch:          {git_status.get('current_branch', 'unknown')}")
        print(f"Current Commit:          {git_status.get('current_commit', 'unknown')[:8]}")
        
        # Warnings and errors
        if validation["warnings"]:
            print(f"\n⚠️  WARNINGS:")
            for warning in validation["warnings"]:
                print(f"  • {warning}")
        
        if validation["errors"]:
            print(f"\n❌ ERRORS:")
            for error in validation["errors"]:
                print(f"  • {error}")
        
        # Recommendations
        if validation["recommendations"]:
            print(f"\n💡 RECOMMENDATIONS:")
            for rec in validation["recommendations"]:
                print(f"  • {rec}")
        
        # Available backups
        backups = self.list_available_backups()
        if backups:
            print(f"\n📦 AVAILABLE BACKUPS ({len(backups)}):")
            for backup in backups[:3]:  # Show latest 3
                backup_time = datetime.fromisoformat(backup["timestamp"]).strftime("%Y-%m-%d %H:%M")
                print(f"  • {backup['backup_id']} ({backup_time}) - {backup['size_mb']:.1f} MB")
            
            if len(backups) > 3:
                print(f"  ... and {len(backups) - 3} more")
        else:
            print(f"\n📦 AVAILABLE BACKUPS: None")


def create_rollback_manager() -> RollbackManager:
    """Factory function to create rollback manager."""
    return RollbackManager()


if __name__ == '__main__':
    # Demo the rollback system
    print("DEPLOYMENT ROLLBACK SYSTEM DEMONSTRATION")
    print("="*60)
    
    # Create rollback manager
    manager = RollbackManager()
    
    # Show deployment status
    manager.print_deployment_status()
    
    # Create a demo backup
    backup_id = manager.create_deployment_backup("demo_backup")
    print(f"\n✅ Created demo backup: {backup_id}")
    
    # List backups
    backups = manager.list_available_backups()
    print(f"\n📦 Available backups: {len(backups)}")
    for backup in backups:
        print(f"  • {backup['backup_id']} - {backup['size_mb']:.1f} MB")
    
    print(f"\n✅ Rollback system demonstration complete!")
    print(f"   Use rollback_deployment(backup_id, confirm_rollback=True) to rollback")