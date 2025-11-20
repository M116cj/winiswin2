"""
Smart Startup Manager v1.0
Handles crash loops, exponential backoff, and Railway-specific recovery

Features:
- Crash tracking (.restart_count file)
- Exponential backoff (prevent API bans)
- Automatic recovery after cooling period
- Integration with LifecycleManager
"""

import asyncio
import logging
import json
import time
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class StartupManager:
    """
    Smart Startup Manager
    
    Features:
    1. Crash tracking in .restart_count file
    2. Exponential backoff if >3 crashes in 5 minutes
    3. Auto-recovery after cooling period
    4. Integration with LifecycleManager
    
    Usage:
        startup = StartupManager()
        await startup.safe_start(main_coroutine())
    """
    
    RESTART_FILE = ".restart_count"
    CRASH_WINDOW = 300  # 5 minutes in seconds
    MAX_CRASHES = 3  # Max crashes before backoff
    BACKOFF_DELAY = 60  # Wait 60 seconds if too many crashes
    
    def __init__(self, restart_file: str = RESTART_FILE):
        """Initialize startup manager"""
        self.restart_file = Path(restart_file)
        self.crash_history: list = []
        self.total_crashes = 0
        self.total_restarts = 0
        
        logger.info("=" * 80)
        logger.info("🔄 StartupManager v1.0 初始化完成")
        logger.info(f"   📁 崩溃追踪文件: {self.restart_file}")
        logger.info(f"   ⏱️  崩溃窗口: {self.CRASH_WINDOW}秒 ({self.CRASH_WINDOW/60}分钟)")
        logger.info(f"   🚨 最大崩溃次数: {self.MAX_CRASHES}")
        logger.info(f"   ⏳ 退避延迟: {self.BACKOFF_DELAY}秒")
        logger.info("=" * 80)
    
    def _load_crash_history(self) -> Dict[str, Any]:
        """Load crash history from file"""
        if not self.restart_file.exists():
            return {
                'crashes': [],
                'total_crashes': 0,
                'total_restarts': 0,
                'last_crash_time': None
            }
        
        try:
            with open(self.restart_file, 'r') as f:
                data = json.load(f)
                logger.info(f"📖 已加载崩溃历史: {data.get('total_crashes', 0)}次崩溃")
                return data
        except Exception as e:
            logger.warning(f"⚠️ 加载崩溃历史失败: {e}，使用默认值")
            return {
                'crashes': [],
                'total_crashes': 0,
                'total_restarts': 0,
                'last_crash_time': None
            }
    
    def _save_crash_history(self, data: Dict[str, Any]):
        """Save crash history to file"""
        try:
            with open(self.restart_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"💾 崩溃历史已保存: {data.get('total_crashes', 0)}次崩溃")
        except Exception as e:
            logger.error(f"❌ 保存崩溃历史失败: {e}")
    
    def _clean_old_crashes(self, crashes: list) -> list:
        """Remove crashes older than CRASH_WINDOW"""
        current_time = time.time()
        cutoff_time = current_time - self.CRASH_WINDOW
        
        recent_crashes = [
            crash_time for crash_time in crashes
            if crash_time > cutoff_time
        ]
        
        if len(recent_crashes) < len(crashes):
            removed = len(crashes) - len(recent_crashes)
            logger.info(f"🧹 已清理 {removed} 个旧崩溃记录 (>{self.CRASH_WINDOW}秒)")
        
        return recent_crashes
    
    def _should_backoff(self, recent_crashes: int) -> bool:
        """Determine if we should apply exponential backoff"""
        return recent_crashes >= self.MAX_CRASHES
    
    async def record_crash(self):
        """Record a crash event"""
        current_time = time.time()
        
        # Load existing history
        data = self._load_crash_history()
        
        # Add new crash
        data['crashes'].append(current_time)
        data['total_crashes'] = data.get('total_crashes', 0) + 1
        data['last_crash_time'] = datetime.now().isoformat()
        
        # Clean old crashes
        data['crashes'] = self._clean_old_crashes(data['crashes'])
        
        # Save updated history
        self._save_crash_history(data)
        
        recent_crashes = len(data['crashes'])
        
        logger.warning("=" * 80)
        logger.warning("⚠️ 崩溃已记录")
        logger.warning(f"   最近崩溃次数: {recent_crashes} (过去{self.CRASH_WINDOW/60:.0f}分钟)")
        logger.warning(f"   总崩溃次数: {data['total_crashes']}")
        logger.warning("=" * 80)
        
        # Check if backoff needed
        if self._should_backoff(recent_crashes):
            logger.critical("=" * 80)
            logger.critical("🚨 检测到崩溃循环!")
            logger.critical(f"   {recent_crashes} 次崩溃在 {self.CRASH_WINDOW/60:.0f} 分钟内")
            logger.critical(f"   应用指数退避: 等待 {self.BACKOFF_DELAY} 秒")
            logger.critical("   (防止 API 禁令和资源耗尽)")
            logger.critical("=" * 80)
            
            # Wait before retry
            await asyncio.sleep(self.BACKOFF_DELAY)
            
            logger.info("✅ 退避完成，继续重启...")
    
    async def record_successful_start(self):
        """Record a successful startup (reset crash counter)"""
        data = self._load_crash_history()
        
        # Update restart count
        data['total_restarts'] = data.get('total_restarts', 0) + 1
        data['last_successful_start'] = datetime.now().isoformat()
        
        # Keep crash history but note successful start
        self._save_crash_history(data)
        
        recent_crashes = len(self._clean_old_crashes(data.get('crashes', [])))
        
        logger.info("=" * 80)
        logger.info("✅ 启动成功已记录")
        logger.info(f"   总重启次数: {data['total_restarts']}")
        logger.info(f"   总崩溃次数: {data['total_crashes']}")
        logger.info(f"   最近崩溃次数: {recent_crashes}")
        logger.info("=" * 80)
    
    def get_crash_stats(self) -> Dict[str, Any]:
        """Get crash statistics"""
        data = self._load_crash_history()
        recent_crashes = self._clean_old_crashes(data.get('crashes', []))
        
        return {
            'total_crashes': data.get('total_crashes', 0),
            'total_restarts': data.get('total_restarts', 0),
            'recent_crashes': len(recent_crashes),
            'last_crash_time': data.get('last_crash_time'),
            'last_successful_start': data.get('last_successful_start'),
            'in_backoff_mode': self._should_backoff(len(recent_crashes))
        }
    
    async def safe_start(self, main_coroutine):
        """
        Safe startup with crash tracking and backoff
        
        Args:
            main_coroutine: Main application coroutine
        
        Returns:
            Exit code (0 = success, 1 = error)
        """
        from src.core.lifecycle_manager import get_lifecycle_manager
        
        try:
            # Check for recent crashes and apply backoff if needed
            data = self._load_crash_history()
            recent_crashes = self._clean_old_crashes(data.get('crashes', []))
            
            if self._should_backoff(len(recent_crashes)):
                logger.critical("=" * 80)
                logger.critical("🚨 启动时检测到崩溃循环")
                logger.critical(f"   {len(recent_crashes)} 次崩溃在过去 {self.CRASH_WINDOW/60:.0f} 分钟")
                logger.critical(f"   应用指数退避: 等待 {self.BACKOFF_DELAY} 秒...")
                logger.critical("=" * 80)
                
                await asyncio.sleep(self.BACKOFF_DELAY)
                logger.info("✅ 退避完成，继续启动...")
            
            # Get lifecycle manager
            lifecycle = get_lifecycle_manager()
            
            # Run application with lifecycle management
            await lifecycle.run(main_coroutine)
            
            # 🔧 FIX: Only record successful start AFTER coroutine completes
            await self.record_successful_start()
            
            return 0  # Graceful exit
            
        except KeyboardInterrupt:
            logger.info("⌨️ 键盘中断")
            # Don't record as crash for keyboard interrupt
            return 0
            
        except Exception as e:
            logger.error(f"❌ 启动失败: {e}")
            logger.exception("详细错误:")
            
            # 🔧 FIX: Record crash before returning error code
            await self.record_crash()
            
            return 1  # Error exit
    
    def clear_crash_history(self):
        """Clear crash history (for manual recovery)"""
        if self.restart_file.exists():
            os.remove(self.restart_file)
            logger.info("🗑️ 崩溃历史已清除")
        else:
            logger.info("ℹ️ 没有崩溃历史需要清除")


# Convenience function
def get_startup_manager() -> StartupManager:
    """Get startup manager instance"""
    return StartupManager()
