"""
🔥 UnifiedDatabaseManager v1.0 - 统一数据库管理器
职责：单一入口管理asyncpg连接 + Redis缓存

这个类解决了原有的"多个真理"问题：
- 之前: AsyncDatabaseManager + RedisManager （两个独立的连接管理）
- 现在: UnifiedDatabaseManager （统一数据库和缓存层）

设计：
1. PostgreSQL是真理来源（asyncpg连接池）
2. Redis是L2缓存层（可选）
3. 所有查询通过此类进行
"""

import os
import logging
import asyncpg
from typing import Optional, Any, Dict, List
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)

# 尝试导入Redis（可选）
try:
    import redis.asyncio as aioredis
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False
    aioredis = None


class UnifiedDatabaseManager:
    """
    🔥 统一数据库管理器 v1.0
    
    统一管理：
    1. AsyncPG PostgreSQL连接池
    2. Redis缓存层（可选）
    
    特性：
    - 单一真理来源：所有数据库访问通过此类
    - 异步优先：100%异步操作
    - 智能缓存：Redis L2缓存 + PostgreSQL L3持久化
    - 优雅降级：Redis不可用时自动切换到PostgreSQL
    - 统一错误处理
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        min_db_connections: int = 2,
        max_db_connections: int = 10,
        db_connection_timeout: int = 30,
        db_command_timeout: int = 10
    ):
        """初始化统一数据库管理器"""
        if UnifiedDatabaseManager._initialized:
            return
        
        logger.info("=" * 80)
        logger.info("✅ UnifiedDatabaseManager 初始化中...")
        logger.info("=" * 80)
        
        # ===== PostgreSQL配置 =====
        self.min_db_connections = min_db_connections
        self.max_db_connections = max_db_connections
        self.db_connection_timeout = db_connection_timeout
        self.db_command_timeout = db_command_timeout
        
        self.pg_pool: Optional[asyncpg.Pool] = None
        self._db_initialized = False
        
        # ===== Redis配置 =====
        self.redis_url: Optional[str] = os.environ.get('REDIS_URL')
        self.redis_client: Optional[aioredis.Redis] = None
        self._redis_initialized = False
        self.redis_enabled = False
        
        # 统计信息
        self.stats = {
            'pg_queries': 0,
            'pg_errors': 0,
            'redis_hits': 0,
            'redis_misses': 0,
            'redis_errors': 0
        }
        
        UnifiedDatabaseManager._initialized = True
        logger.info("✅ UnifiedDatabaseManager 初始化完成")
    
    # ==================== PostgreSQL 管理 ====================
    
    def _get_database_url(self) -> str:
        """获取数据库URL（优先使用DATABASE_URL）"""
        database_url = os.environ.get('DATABASE_URL')
        
        if not database_url:
            database_url = os.environ.get('DATABASE_PUBLIC_URL')
        
        if not database_url:
            raise ValueError(
                "❌ 未找到数据库URL。请设置 DATABASE_URL 或 DATABASE_PUBLIC_URL 环境变量"
            )
        
        return database_url
    
    def _prepare_connection_url(self, database_url: str) -> str:
        """准备连接URL（智能SSL检测）"""
        parsed = urlparse(database_url)
        query_params = parse_qs(parsed.query)
        has_sslmode = 'sslmode' in query_params or 'ssl' in query_params
        
        if has_sslmode:
            return database_url
        
        # 智能SSL检测
        if 'railway.internal' in parsed.netloc:
            return database_url
        elif 'railway.app' in parsed.netloc or 'neon' in parsed.netloc:
            separator = '&' if '?' in database_url else '?'
            return f"{database_url}{separator}sslmode=require"
        else:
            return database_url
    
    async def initialize_postgres(self) -> None:
        """初始化PostgreSQL连接池"""
        if self._db_initialized and self.pg_pool:
            return
        
        try:
            database_url = self._get_database_url()
            connection_url = self._prepare_connection_url(database_url)
            
            logger.info(f"📡 连接PostgreSQL连接池...")
            
            self.pg_pool = await asyncpg.create_pool(
                connection_url,
                min_size=self.min_db_connections,
                max_size=self.max_db_connections,
                command_timeout=self.db_command_timeout
            )
            
            self._db_initialized = True
            logger.info("✅ PostgreSQL连接池已初始化")
        
        except Exception as e:
            logger.error(f"❌ PostgreSQL连接失败: {e}")
            raise
    
    # ==================== Redis 管理 ====================
    
    async def initialize_redis(self) -> None:
        """初始化Redis连接（如果配置）"""
        if self._redis_initialized or not self.redis_url:
            return
        
        if not _REDIS_AVAILABLE:
            logger.info("ℹ️  Redis未安装（可选功能）")
            return
        
        try:
            logger.info("📡 连接Redis...")
            
            self.redis_client = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=3.0,
                socket_connect_timeout=3.0,
                max_connections=10
            )
            
            # 测试连接
            await self.redis_client.ping()
            self.redis_enabled = True
            self._redis_initialized = True
            
            logger.info("✅ Redis连接成功")
        
        except Exception as e:
            logger.warning(f"⚠️  Redis连接失败: {e} - 将使用纯PostgreSQL模式")
            self.redis_enabled = False
    
    # ==================== 初始化总入口 ====================
    
    async def initialize(self) -> None:
        """初始化所有数据库连接（PostgreSQL + Redis）"""
        await self.initialize_postgres()
        await self.initialize_redis()
        logger.info("=" * 80)
        logger.info("✅ UnifiedDatabaseManager 所有连接已初始化")
        logger.info("=" * 80)
    
    # ==================== 关闭方法 ====================
    
    async def close(self) -> None:
        """优雅关闭所有连接"""
        if self.pg_pool:
            await self.pg_pool.close()
            self._db_initialized = False
            logger.info("✅ PostgreSQL连接池已关闭")
        
        if self.redis_client:
            await self.redis_client.close()
            self._redis_initialized = False
            logger.info("✅ Redis连接已关闭")
    
    # ==================== 数据库查询方法 ====================
    
    async def execute(self, query: str, *args) -> Any:
        """
        执行单条SQL语句
        
        Args:
            query: SQL查询语句
            *args: 查询参数
        
        Returns:
            查询结果
        """
        if not self.pg_pool:
            raise RuntimeError("PostgreSQL连接池未初始化")
        
        try:
            async with self.pg_pool.acquire() as connection:
                result = await connection.execute(query, *args)
                self.stats['pg_queries'] += 1
                return result
        except Exception as e:
            self.stats['pg_errors'] += 1
            logger.error(f"❌ 数据库查询失败: {e}")
            raise
    
    async def fetch(self, query: str, *args) -> List[tuple]:
        """执行查询并获取所有行"""
        if not self.pg_pool:
            raise RuntimeError("PostgreSQL连接池未初始化")
        
        try:
            async with self.pg_pool.acquire() as connection:
                rows = await connection.fetch(query, *args)
                self.stats['pg_queries'] += 1
                return rows
        except Exception as e:
            self.stats['pg_errors'] += 1
            logger.error(f"❌ 数据库查询失败: {e}")
            raise
    
    async def fetchval(self, query: str, *args) -> Any:
        """执行查询并获取单个值"""
        if not self.pg_pool:
            raise RuntimeError("PostgreSQL连接池未初始化")
        
        try:
            async with self.pg_pool.acquire() as connection:
                value = await connection.fetchval(query, *args)
                self.stats['pg_queries'] += 1
                return value
        except Exception as e:
            self.stats['pg_errors'] += 1
            logger.error(f"❌ 数据库查询失败: {e}")
            raise
    
    # ==================== Redis缓存方法 ====================
    
    async def cache_get(self, key: str) -> Optional[str]:
        """从Redis获取缓存"""
        if not self.redis_enabled or not self.redis_client:
            return None
        
        try:
            value = await self.redis_client.get(key)
            if value:
                self.stats['redis_hits'] += 1
            else:
                self.stats['redis_misses'] += 1
            return value
        except Exception as e:
            self.stats['redis_errors'] += 1
            logger.debug(f"⚠️  Redis缓存读取失败: {e}")
            return None
    
    async def cache_set(self, key: str, value: str, ttl: int = 300) -> bool:
        """设置Redis缓存"""
        if not self.redis_enabled or not self.redis_client:
            return False
        
        try:
            await self.redis_client.setex(key, ttl, value)
            return True
        except Exception as e:
            self.stats['redis_errors'] += 1
            logger.debug(f"⚠️  Redis缓存写入失败: {e}")
            return False
    
    # ==================== 单例访问 ====================
    
    @staticmethod
    def get_instance() -> 'UnifiedDatabaseManager':
        """获取单例实例"""
        return UnifiedDatabaseManager()


# 全局单例实例
database_manager = UnifiedDatabaseManager()
