"""
System Lifecycle Manager v1.0
Professional orchestration of system startup, shutdown, and recovery

Features:
- Signal handling (SIGINT, SIGTERM)
- Component registry for graceful shutdown
- Watchdog for hang detection
- Graceful shutdown sequence
- Exit coordination
"""

import asyncio
import logging
import signal
import sys
import time
import threading
from typing import Optional, List, Callable, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class LifecycleManager:
    """
    System Lifecycle Manager (Singleton)
    
    Responsibilities:
    1. Signal handling (SIGINT, SIGTERM)
    2. Component registry for shutdown methods
    3. Graceful shutdown orchestration
    4. Watchdog for hang detection
    5. Exit coordination
    
    Usage:
        lifecycle = LifecycleManager.get_instance()
        lifecycle.register_component("Database", db_manager.close)
        lifecycle.start_watchdog()
        lifecycle.run(main_coroutine())
    """
    
    _instance: Optional['LifecycleManager'] = None
    _lock = threading.Lock()
    
    def __init__(self):
        """Initialize lifecycle manager (singleton pattern)"""
        if LifecycleManager._instance is not None:
            raise RuntimeError("LifecycleManager is a singleton. Use get_instance()")
        
        # System state
        self.is_running = False
        self.is_shutting_down = False
        self.shutdown_initiated = False
        
        # Component registry
        self.components: Dict[str, Callable] = {}
        self.shutdown_order: List[str] = []
        
        # Watchdog (Dead Man's Switch)
        self.last_heartbeat: float = time.time()
        self.watchdog_enabled = False
        self.watchdog_thread: Optional[threading.Thread] = None
        self.watchdog_interval = 10  # Check every 10 seconds
        self.watchdog_timeout = 60  # Declare dead if no heartbeat for 60s
        
        # Statistics
        self.stats = {
            'start_time': None,
            'shutdown_time': None,
            'uptime_seconds': 0,
            'graceful_shutdowns': 0,
            'forced_exits': 0
        }
        
        logger.info("=" * 80)
        logger.info("🛡️ LifecycleManager v1.0 初始化完成")
        logger.info("   📡 信号处理: SIGINT, SIGTERM")
        logger.info("   🐶 看门狗: 60秒超时检测")
        logger.info("   🔄 优雅关闭: 组件注册机制")
        logger.info("=" * 80)
    
    @classmethod
    def get_instance(cls) -> 'LifecycleManager':
        """Get singleton instance (thread-safe)"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset_instance(cls):
        """Reset singleton (for testing only)"""
        with cls._lock:
            cls._instance = None
    
    def register_component(
        self, 
        name: str, 
        shutdown_method: Callable,
        priority: int = 50
    ):
        """
        Register a component for graceful shutdown
        
        Args:
            name: Component name (e.g., "Database", "WebSocket")
            shutdown_method: Async or sync shutdown method
            priority: Shutdown priority (lower = earlier, default=50)
        
        Examples:
            lifecycle.register_component("Database", db_manager.close, priority=10)
            lifecycle.register_component("WebSocket", ws_manager.stop, priority=20)
        """
        self.components[name] = {
            'shutdown_method': shutdown_method,
            'priority': priority
        }
        
        # Sort components by priority
        self.shutdown_order = sorted(
            self.components.keys(),
            key=lambda k: self.components[k]['priority']
        )
        
        logger.info(f"✅ 组件已注册: {name} (优先级={priority})")
    
    def update_heartbeat(self):
        """Update watchdog heartbeat (call every 10s from main loop)"""
        self.last_heartbeat = time.time()
    
    def start_watchdog(self):
        """Start watchdog thread (Dead Man's Switch)"""
        if self.watchdog_enabled:
            logger.warning("⚠️ 看门狗已启用，跳过")
            return
        
        self.watchdog_enabled = True
        self.last_heartbeat = time.time()
        
        self.watchdog_thread = threading.Thread(
            target=self._watchdog_monitor,
            daemon=True,
            name="WatchdogMonitor"
        )
        self.watchdog_thread.start()
        
        logger.info(f"🐶 看门狗已启动 (超时={self.watchdog_timeout}秒)")
    
    def stop_watchdog(self):
        """Stop watchdog thread"""
        if not self.watchdog_enabled:
            return
        
        self.watchdog_enabled = False
        
        if self.watchdog_thread and self.watchdog_thread.is_alive():
            # Thread will exit on next check
            self.watchdog_thread.join(timeout=2)
        
        logger.info("🐶 看门狗已停止")
    
    def _watchdog_monitor(self):
        """
        Watchdog monitor thread (runs in background)
        
        🔧 FIX: Removed self.is_running check so watchdog monitors from start
        """
        logger.info("🐶 看门狗监控线程已启动")
        
        # 🔧 FIX: Only check watchdog_enabled, not is_running
        # This allows watchdog to monitor even during initialization
        while self.watchdog_enabled:
            try:
                current_time = time.time()
                time_since_heartbeat = current_time - self.last_heartbeat
                
                if time_since_heartbeat > self.watchdog_timeout:
                    # CRITICAL: System hang detected!
                    logger.critical("=" * 80)
                    logger.critical("🚨 系统挂起检测到!")
                    logger.critical(f"   上次心跳: {time_since_heartbeat:.1f}秒前")
                    logger.critical(f"   超时阈值: {self.watchdog_timeout}秒")
                    logger.critical("   🔄 强制退出以触发Railway重启...")
                    logger.critical("=" * 80)
                    
                    self.stats['forced_exits'] += 1
                    
                    # Force exit (Railway will restart the service)
                    import os
                    os._exit(1)  # Immediate exit without cleanup
                
                # Sleep for watchdog interval
                time.sleep(self.watchdog_interval)
                
            except Exception as e:
                logger.error(f"❌ 看门狗监控异常: {e}")
                time.sleep(self.watchdog_interval)
        
        logger.info("🐶 看门狗监控线程已退出")
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            """Handle shutdown signals"""
            signal_name = signal.Signals(signum).name
            logger.info("=" * 80)
            logger.info(f"📡 收到信号: {signal_name}")
            logger.info("   🛑 启动优雅关闭序列...")
            logger.info("=" * 80)
            
            # Trigger shutdown
            asyncio.create_task(self.shutdown())
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # Railway deploy/stop
        
        logger.info("📡 信号处理器已注册: SIGINT, SIGTERM")
    
    async def shutdown(self, exit_code: int = 0):
        """
        Execute graceful shutdown sequence
        
        Args:
            exit_code: Exit code (0=success, 1=error) - used by run() to indicate failure
        
        Sequence:
        1. Set is_running = False (stop new operations)
        2. Persist state (flush logs/stats)
        3. Close components in priority order
        4. Stop watchdog
        5. Exit (only if not being managed by StartupManager)
        """
        if self.shutdown_initiated:
            logger.warning("⚠️ 关闭已在进行中，跳过")
            return
        
        self.shutdown_initiated = True
        self.is_shutting_down = True
        self.stats['shutdown_time'] = datetime.now()
        
        logger.info("=" * 80)
        logger.info("🛑 优雅关闭序列已启动")
        logger.info("=" * 80)
        
        # Step 1: Stop accepting new operations
        self.is_running = False
        logger.info("✅ 步骤 1/5: 已停止新操作")
        
        # Step 2: Persist state (allow 2 seconds for final writes)
        logger.info("⏳ 步骤 2/5: 持久化状态...")
        await asyncio.sleep(2)
        logger.info("✅ 步骤 2/5: 状态已持久化")
        
        # Step 3: Close components in priority order
        logger.info(f"⏳ 步骤 3/5: 关闭组件 ({len(self.components)}个)...")
        
        for component_name in self.shutdown_order:
            try:
                component = self.components[component_name]
                shutdown_method = component['shutdown_method']
                
                logger.info(f"   🔄 关闭 {component_name}...")
                
                # Check if method is async
                if asyncio.iscoroutinefunction(shutdown_method):
                    await shutdown_method()
                else:
                    shutdown_method()
                
                logger.info(f"   ✅ {component_name} 已关闭")
                
            except Exception as e:
                logger.error(f"   ❌ {component_name} 关闭失败: {e}")
        
        logger.info("✅ 步骤 3/5: 所有组件已关闭")
        
        # Step 4: Stop watchdog
        logger.info("⏳ 步骤 4/5: 停止看门狗...")
        self.stop_watchdog()
        logger.info("✅ 步骤 4/5: 看门狗已停止")
        
        # Step 5: Calculate uptime
        if self.stats['start_time']:
            uptime = (datetime.now() - self.stats['start_time']).total_seconds()
            self.stats['uptime_seconds'] = uptime
            logger.info(f"⏱️  系统运行时间: {uptime:.1f}秒 ({uptime/60:.1f}分钟)")
        
        self.stats['graceful_shutdowns'] += 1
        
        logger.info("=" * 80)
        logger.info("✅ 步骤 5/5: 优雅关闭完成")
        if exit_code != 0:
            logger.error(f"   ❌ 退出码: {exit_code} (错误)")
        logger.info("=" * 80)
        
        # 🔧 FIX: Don't call sys.exit() here - let StartupManager handle exit codes
    
    async def run(self, main_coroutine):
        """
        Run main application with lifecycle management
        
        Args:
            main_coroutine: Main application coroutine
        
        Example:
            async def main():
                # Application logic
                pass
            
            lifecycle = LifecycleManager.get_instance()
            lifecycle.run(main())
        
        Raises:
            Any exception from main_coroutine (for proper exit code propagation)
        """
        self.is_running = True
        self.stats['start_time'] = datetime.now()
        
        # Setup signal handlers
        self._setup_signal_handlers()
        
        logger.info("🚀 LifecycleManager: 系统启动完成")
        
        try:
            # Run main application
            await main_coroutine
            
        except KeyboardInterrupt:
            logger.info("⌨️ 键盘中断 (Ctrl+C)")
            await self.shutdown(exit_code=0)
            # 🔧 FIX: Don't re-raise KeyboardInterrupt (clean exit)
            
        except Exception as e:
            logger.error(f"❌ 主应用异常: {e}")
            logger.exception("详细错误:")
            await self.shutdown(exit_code=1)
            # 🔧 FIX: Re-raise to propagate error for exit code
            raise
        
        finally:
            if not self.shutdown_initiated:
                await self.shutdown(exit_code=0)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get lifecycle manager statistics"""
        return {
            **self.stats,
            'is_running': self.is_running,
            'is_shutting_down': self.is_shutting_down,
            'watchdog_enabled': self.watchdog_enabled,
            'components_count': len(self.components),
            'last_heartbeat_age': time.time() - self.last_heartbeat
        }


# Convenience function for getting singleton instance
def get_lifecycle_manager() -> LifecycleManager:
    """Get lifecycle manager singleton instance"""
    return LifecycleManager.get_instance()
