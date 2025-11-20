"""
AsyncDatabaseManager - 统一异步PostgreSQL连接池管理器
Phase 3: 迁移所有数据库操作到asyncpg，替代psycopg2

Author: SelfLearningTrader Team
Version: Phase 3.0 (2025-11-20)
"""

import os
import logging
from typing import Optional, List, Any, Dict
from contextlib import asynccontextmanager
import asyncpg
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


class AsyncDatabaseManager:
    """
    异步PostgreSQL连接池管理器（基于asyncpg）
    
    特性：
    - 异步连接池自动管理
    - 连接健康检查
    - 事务支持
    - 批量操作优化
    - 统一错误处理
    - 优雅关闭
    
    设计目标：
    1. 100%异步操作（无阻塞）
    2. 统一数据库访问层
    3. 替代psycopg2 DatabaseManager
    4. 与PositionController共享架构
    """
    
    def __init__(
        self,
        min_connections: int = 1,
        max_connections: int = 20,
        connection_timeout: int = 30,
        command_timeout: int = 10
    ):
        """
        初始化异步数据库管理器
        
        Args:
            min_connections: 最小连接数
            max_connections: 最大连接数
            connection_timeout: 连接超时（秒）
            command_timeout: 命令超时（秒）
        """
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self.command_timeout = command_timeout
        
        self.pool: Optional[asyncpg.Pool] = None
        self._is_initialized = False
    
    def _get_database_url(self) -> str:
        """
        获取数据库URL（优先使用 DATABASE_URL）
        
        Returns:
            数据库连接URL
        """
        database_url = os.environ.get('DATABASE_URL')
        
        if not database_url:
            database_url = os.environ.get('DATABASE_PUBLIC_URL')
            logger.warning("⚠️ DATABASE_URL 未设置，使用 DATABASE_PUBLIC_URL")
        
        if not database_url:
            raise ValueError(
                "未找到数据库连接URL。请设置 DATABASE_URL 或 DATABASE_PUBLIC_URL 环境变量"
            )
        
        return database_url
    
    def _prepare_connection_url(self, database_url: str) -> str:
        """
        准备连接URL（智能SSL检测）
        
        Args:
            database_url: 原始数据库URL
            
        Returns:
            处理后的连接URL
        """
        parsed = urlparse(database_url)
        
        # 检查URL是否已包含 sslmode 参数
        query_params = parse_qs(parsed.query)
        has_sslmode = 'sslmode' in query_params or 'ssl' in query_params
        
        if has_sslmode:
            logger.info(f"🔑 URL已包含SSL参数，保持不变")
            return database_url
        
        # 智能SSL检测
        if 'railway.internal' in parsed.netloc:
            logger.info("🔓 Railway内部连接：禁用SSL")
            return database_url
        elif 'railway.app' in parsed.netloc or 'neon' in parsed.netloc:
            logger.info("🔒 公开连接：启用SSL")
            separator = '&' if '?' in database_url else '?'
            return f"{database_url}{separator}sslmode=require"
        else:
            logger.info("🔓 默认连接：禁用SSL")
            return database_url
    
    async def initialize(self) -> None:
        """
        初始化异步连接池
        
        必须在使用前调用此方法
        """
        if self._is_initialized and self.pool:
            logger.debug("连接池已初始化，跳过")
            return
        
        try:
            database_url = self._get_database_url()
            connection_url = self._prepare_connection_url(database_url)
            
            logger.info("📡 初始化PostgreSQL异步连接池...")
            logger.debug(f"   最小连接数: {self.min_connections}")
            logger.debug(f"   最大连接数: {self.max_connections}")
            
            self.pool = await asyncpg.create_pool(
                connection_url,
                min_size=self.min_connections,
                max_size=self.max_connections,
                timeout=self.connection_timeout,
                command_timeout=self.command_timeout
            )
            
            self._is_initialized = True
            logger.info("✅ PostgreSQL异步连接池初始化成功")
            
        except Exception as e:
            logger.error(f"❌ 连接池初始化失败: {e}")
            logger.exception("详细错误信息:")
            self._is_initialized = False
            raise
    
    async def close(self) -> None:
        """
        关闭连接池（优雅关闭）
        """
        if self.pool:
            try:
                await self.pool.close()
                logger.info("✅ PostgreSQL异步连接池已关闭")
            except Exception as e:
                logger.error(f"❌ 关闭连接池失败: {e}")
            finally:
                self.pool = None
                self._is_initialized = False
    
    @asynccontextmanager
    async def acquire(self):
        """
        获取数据库连接（异步上下文管理器）
        
        使用示例:
            async with db_manager.acquire() as conn:
                result = await conn.fetch("SELECT 1")
        
        Yields:
            asyncpg连接对象
        """
        if not self._is_initialized or not self.pool:
            raise RuntimeError("连接池未初始化，请先调用 await initialize()")
        
        async with self.pool.acquire() as connection:
            yield connection
    
    async def execute(self, query: str, *params) -> str:
        """
        执行SQL（无返回值）
        
        Args:
            query: SQL查询语句
            *params: 查询参数
            
        Returns:
            执行状态字符串
            
        示例:
            await db_manager.execute(
                "INSERT INTO trades (symbol, price) VALUES ($1, $2)",
                'BTCUSDT', 50000.0
            )
        """
        if not self._is_initialized or not self.pool:
            raise RuntimeError("连接池未初始化")
        
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *params)
    
    async def fetch(self, query: str, *params) -> List[asyncpg.Record]:
        """
        查询SQL（返回多行）
        
        Args:
            query: SQL查询语句
            *params: 查询参数
            
        Returns:
            查询结果列表
            
        示例:
            rows = await db_manager.fetch(
                "SELECT * FROM trades WHERE symbol = $1",
                'BTCUSDT'
            )
        """
        if not self._is_initialized or not self.pool:
            raise RuntimeError("连接池未初始化")
        
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *params)
    
    async def fetchrow(self, query: str, *params) -> Optional[asyncpg.Record]:
        """
        查询SQL（返回单行）
        
        Args:
            query: SQL查询语句
            *params: 查询参数
            
        Returns:
            查询结果（单行）或None
            
        示例:
            row = await db_manager.fetchrow(
                "SELECT * FROM trades WHERE id = $1",
                123
            )
        """
        if not self._is_initialized or not self.pool:
            raise RuntimeError("连接池未初始化")
        
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *params)
    
    async def fetchval(self, query: str, *params) -> Any:
        """
        查询SQL（返回单个值）
        
        Args:
            query: SQL查询语句
            *params: 查询参数
            
        Returns:
            查询结果（单个值）
            
        示例:
            count = await db_manager.fetchval(
                "SELECT COUNT(*) FROM trades"
            )
        """
        if not self._is_initialized or not self.pool:
            raise RuntimeError("连接池未初始化")
        
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *params)
    
    async def execute_many(self, query: str, params_list: List[tuple]) -> None:
        """
        批量执行SQL
        
        Args:
            query: SQL查询语句
            params_list: 参数列表
            
        示例:
            await db_manager.execute_many(
                "INSERT INTO trades (symbol, price) VALUES ($1, $2)",
                [
                    ('BTCUSDT', 50000),
                    ('ETHUSDT', 3000)
                ]
            )
        """
        if not self._is_initialized or not self.pool:
            raise RuntimeError("连接池未初始化")
        
        async with self.pool.acquire() as conn:
            await conn.executemany(query, params_list)
    
    async def check_health(self) -> bool:
        """
        检查数据库连接健康状态
        
        Returns:
            True if healthy, False otherwise
        """
        if not self._is_initialized or not self.pool:
            return False
        
        try:
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"数据库健康检查失败: {e}")
            return False
    
    async def get_pool_stats(self) -> Dict[str, Any]:
        """
        获取连接池统计信息
        
        Returns:
            连接池统计字典
        """
        if not self._is_initialized or not self.pool:
            return {
                'initialized': False,
                'size': 0,
                'free_size': 0,
                'min_size': self.min_connections,
                'max_size': self.max_connections
            }
        
        return {
            'initialized': True,
            'size': self.pool.get_size(),
            'free_size': self.pool.get_idle_size(),
            'min_size': self.pool.get_min_size(),
            'max_size': self.pool.get_max_size()
        }
    
    def _convert_placeholders(self, query: str) -> str:
        """
        将psycopg2风格参数（%s）转换为asyncpg风格（$1, $2, $3...）
        
        此方法处理多参数SQL语句，确保所有%s占位符正确转换。
        
        Args:
            query: 包含%s占位符的SQL查询语句
            
        Returns:
            转换后的SQL查询（使用$1, $2, $3...占位符）
            
        示例:
            输入: "INSERT INTO trades (a, b, c) VALUES (%s, %s, %s)"
            输出: "INSERT INTO trades (a, b, c) VALUES ($1, $2, $3)"
        
        实现细节:
            - 使用re.sub()和计数器逐个替换
            - 每个%s按顺序转换为$1, $2, $3...
            - 确保多参数SQL语句正确转换
        """
        import re
        
        param_count = 0
        def replace_placeholder(match):
            nonlocal param_count
            param_count += 1
            return f"${param_count}"
        
        converted_query = re.sub(r'%s', replace_placeholder, query)
        return converted_query
    
    async def execute_query(self, query: str, params: tuple = (), fetch: bool = False):
        """
        向后兼容方法：兼容DatabaseManager的execute_query接口
        
        Phase 3: 改为async def，支持TradingDataService的await调用。
        自动转换%s→$1, $2...并返回dict（兼容psycopg2）。
        
        Args:
            query: SQL查询语句（使用%s参数化，会自动转换为$1, $2...）
            params: 查询参数元组
            fetch: 是否返回查询结果
            
        Returns:
            如果fetch=True，返回dict列表（兼容psycopg2）
            如果fetch=False，返回None
        """
        # 使用_convert_placeholders()转换所有%s参数为$1, $2, $3...
        converted_query = self._convert_placeholders(query)
        
        # 直接使用async方法
        if fetch:
            result = await self.fetch(converted_query, *params)
            # 将asyncpg.Record转换为dict列表（兼容psycopg2）
            return [dict(row) for row in result] if result else []
        else:
            await self.execute(converted_query, *params)
            return None
    
    @asynccontextmanager
    async def transaction(self):
        """
        事务上下文管理器
        
        使用示例:
            async with db_manager.transaction():
                await db_manager.execute("INSERT INTO ...")
                await db_manager.execute("UPDATE ...")
                # 自动commit，异常时自动rollback
        """
        if not self._is_initialized or not self.pool:
            raise RuntimeError("连接池未初始化")
        
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                yield conn


# 全局实例（可选，用于简化导入）
_global_instance: Optional[AsyncDatabaseManager] = None


async def get_global_instance() -> AsyncDatabaseManager:
    """
    获取全局AsyncDatabaseManager实例（单例模式）
    
    Returns:
        全局AsyncDatabaseManager实例
        
    注意: 使用前必须先调用 initialize_global_instance()
    """
    global _global_instance
    
    if _global_instance is None:
        raise RuntimeError(
            "全局AsyncDatabaseManager未初始化。"
            "请先调用 await initialize_global_instance()"
        )
    
    return _global_instance


async def initialize_global_instance(
    min_connections: int = 1,
    max_connections: int = 20
) -> AsyncDatabaseManager:
    """
    初始化全局AsyncDatabaseManager实例
    
    Args:
        min_connections: 最小连接数
        max_connections: 最大连接数
        
    Returns:
        全局AsyncDatabaseManager实例
    """
    global _global_instance
    
    if _global_instance is not None:
        logger.debug("全局AsyncDatabaseManager已存在")
        return _global_instance
    
    _global_instance = AsyncDatabaseManager(
        min_connections=min_connections,
        max_connections=max_connections
    )
    
    await _global_instance.initialize()
    return _global_instance


async def close_global_instance() -> None:
    """
    关闭全局AsyncDatabaseManager实例
    """
    global _global_instance
    
    if _global_instance:
        await _global_instance.close()
        _global_instance = None
