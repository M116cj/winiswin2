"""
DatabaseManager - 生产级PostgreSQL连接池管理器
支持健康检查、自动重连、错误处理
"""

import os
import logging
import time
from typing import Optional
from contextlib import contextmanager
import psycopg2
from psycopg2 import pool, OperationalError, InterfaceError
from urllib.parse import urlparse, parse_qs

from src.config import Config

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    PostgreSQL连接池管理器
    
    特性：
    - 连接池自动管理
    - 连接健康检查
    - 自动重连机制
    - 线程安全操作
    - 详细错误日志
    """
    
    def __init__(
        self,
        min_connections: int = 1,
        max_connections: int = 20,
        connection_timeout: int = 30,
        auto_retry: bool = True,
        max_retries: int = 3
    ):
        """
        初始化数据库管理器
        
        Args:
            min_connections: 最小连接数
            max_connections: 最大连接数
            connection_timeout: 连接超时（秒）
            auto_retry: 是否自动重试
            max_retries: 最大重试次数
        """
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self.auto_retry = auto_retry
        self.max_retries = max_retries
        
        self.connection_pool: Optional[pool.SimpleConnectionPool] = None
        self._is_initialized = False
        
        # 初始化连接池
        self._initialize_pool()
    
    def _get_database_url(self) -> str:
        """
        获取数据库URL（优先使用内部URL）
        
        Returns:
            数据库连接URL
        """
        # 优先使用内部URL（在Railway上更快）
        database_url = os.environ.get('DATABASE_URL')
        
        if not database_url:
            # 备用公开URL
            database_url = os.environ.get('DATABASE_PUBLIC_URL')
        
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
        
        # 🔥 v4.0+ 智能SSL检测
        # 1. Railway内部连接（*.railway.internal）-> 无需SSL
        # 2. Railway公开连接（*.railway.app等）-> 需要SSL
        # 3. Replit内部数据库 -> 无需SSL（默认）
        # 4. 其他云平台（Neon/Supabase等）-> 需要SSL
        
        if 'railway.internal' in parsed.netloc:
            logger.info("🔓 Railway内部连接：禁用SSL")
            return database_url
        elif 'railway.app' in parsed.netloc or Config.DATABASE_PUBLIC_URL:
            # Railway公开连接需要SSL
            logger.info("🔒 Railway公开连接：启用SSL")
            if '?' in database_url:
                return f"{database_url}&sslmode=require"
            else:
                return f"{database_url}?sslmode=require"
        else:
            # Replit内部数据库或其他默认不需要SSL
            logger.info("🔓 Replit内部连接：禁用SSL")
            return database_url
    
    def _initialize_pool(self) -> None:
        """初始化连接池"""
        try:
            database_url = self._get_database_url()
            connection_url = self._prepare_connection_url(database_url)
            
            logger.info("=" * 70)
            logger.info("🔌 正在初始化PostgreSQL连接池...")
            logger.info(f"   最小连接数: {self.min_connections}")
            logger.info(f"   最大连接数: {self.max_connections}")
            logger.info(f"   连接超时: {self.connection_timeout}秒")
            
            self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                self.min_connections,
                self.max_connections,
                connection_url,
                connect_timeout=self.connection_timeout
            )
            
            self._is_initialized = True
            
            logger.info("✅ PostgreSQL连接池初始化成功")
            logger.info("=" * 70)
            
        except Exception as e:
            logger.error(f"❌ 连接池初始化失败: {e}")
            logger.exception("详细错误信息:")
            self._is_initialized = False
            raise
    
    @contextmanager
    def get_connection(self):
        """
        获取数据库连接（上下文管理器）
        
        使用示例:
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
        
        Yields:
            数据库连接对象
        """
        if not self._is_initialized or not self.connection_pool:
            raise RuntimeError("连接池未初始化")
        
        conn = None
        try:
            conn = self.connection_pool.getconn()
            
            if conn is None:
                raise RuntimeError("无法从连接池获取连接")
            
            # 检查连接是否有效
            if conn.closed:
                logger.warning("⚠️ 连接已关闭，重新获取...")
                self.connection_pool.putconn(conn)
                conn = self.connection_pool.getconn()
            
            yield conn
            
        except (OperationalError, InterfaceError) as e:
            logger.error(f"❌ 数据库连接错误: {e}")
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            raise
            
        finally:
            if conn:
                try:
                    self.connection_pool.putconn(conn)
                except Exception as e:
                    logger.error(f"⚠️ 归还连接时出错: {e}")
    
    def execute_query(
        self,
        query: str,
        params: Optional[tuple] = None,
        fetch: bool = True
    ):
        """
        执行SQL查询（带自动重试）
        
        Args:
            query: SQL查询语句
            params: 查询参数
            fetch: 是否返回结果
            
        Returns:
            查询结果（如果fetch=True）
        """
        retries = 0
        last_error = None
        
        while retries <= self.max_retries:
            try:
                with self.get_connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute(query, params)
                        
                        if fetch and query.strip().upper().startswith('SELECT'):
                            result = cursor.fetchall()
                        else:
                            conn.commit()
                            result = None
                        
                        return result
                        
            except (OperationalError, InterfaceError) as e:
                last_error = e
                retries += 1
                
                if retries <= self.max_retries and self.auto_retry:
                    logger.warning(
                        f"⚠️ 查询失败，重试 {retries}/{self.max_retries}: {e}"
                    )
                    time.sleep(min(2 ** retries, 10))  # 指数退避
                else:
                    break
                    
            except Exception as e:
                logger.error(f"❌ 查询执行失败: {e}")
                logger.exception("详细错误:")
                raise
        
        # 所有重试都失败
        logger.error(f"❌ 查询在 {self.max_retries} 次重试后仍然失败")
        if last_error:
            raise last_error
        else:
            raise RuntimeError("查询失败但未捕获到具体错误")
    
    def check_health(self) -> bool:
        """
        检查数据库连接健康状态
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    result = cursor.fetchone()
                    
                    if result and result[0] == 1:
                        logger.debug("✅ 数据库连接健康")
                        return True
                    else:
                        logger.warning("⚠️ 数据库连接响应异常")
                        return False
                        
        except Exception as e:
            logger.error(f"❌ 数据库健康检查失败: {e}")
            return False
    
    def close_all_connections(self) -> None:
        """关闭所有连接"""
        if self.connection_pool:
            try:
                self.connection_pool.closeall()
                logger.info("✅ 所有数据库连接已关闭")
                self._is_initialized = False
            except Exception as e:
                logger.error(f"❌ 关闭连接时出错: {e}")
    
    def __del__(self):
        """析构函数：确保连接被关闭"""
        self.close_all_connections()
