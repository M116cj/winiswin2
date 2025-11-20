#!/usr/bin/env python3
"""
Phase 1 Migration Script: Create position_entry_times Table
用于修复 "relation position_entry_times does not exist" 错误
"""

import asyncio
import asyncpg
import os
import sys
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def create_position_entry_times_table():
    """创建 position_entry_times 表"""
    
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("❌ 错误: DATABASE_URL 环境变量未设置")
        return False
    
    print("=" * 80)
    print("Phase 1 Migration: Creating position_entry_times Table")
    print("=" * 80)
    
    try:
        # 连接数据库
        print(f"\n📡 连接数据库...")
        conn = await asyncpg.connect(database_url)
        print("✅ 数据库连接成功")
        
        # 检查表是否已存在
        print(f"\n🔍 检查 position_entry_times 表是否存在...")
        table_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'position_entry_times'
            );
            """
        )
        
        if table_exists:
            print("⚠️  position_entry_times 表已存在，跳过创建")
            
            # 显示表结构
            print(f"\n📋 当前表结构:")
            columns = await conn.fetch(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'position_entry_times'
                ORDER BY ordinal_position;
                """
            )
            
            for col in columns:
                nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                print(f"   - {col['column_name']}: {col['data_type']} {nullable}")
            
            # 显示现有数据
            count = await conn.fetchval("SELECT COUNT(*) FROM position_entry_times;")
            print(f"\n📊 现有记录数: {count}")
            
        else:
            print("📝 创建 position_entry_times 表...")
            
            # 创建表
            create_table_sql = """
            CREATE TABLE position_entry_times (
                symbol VARCHAR(20) PRIMARY KEY,
                entry_time TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            """
            
            await conn.execute(create_table_sql)
            print("✅ 表创建成功")
            
            # 创建索引
            print("📝 创建索引...")
            index_sql = """
            CREATE INDEX IF NOT EXISTS idx_position_entry_times_entry_time 
            ON position_entry_times(entry_time DESC);
            """
            await conn.execute(index_sql)
            print("✅ 索引创建成功")
        
        # 验证表创建成功
        print(f"\n🧪 验证表结构...")
        verification_query = """
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'position_entry_times'
        ORDER BY ordinal_position;
        """
        
        columns = await conn.fetch(verification_query)
        
        expected_columns = {'symbol', 'entry_time', 'updated_at'}
        actual_columns = {col['column_name'] for col in columns}
        
        if expected_columns == actual_columns:
            print("✅ 表结构验证通过")
            print(f"   列: {', '.join(actual_columns)}")
        else:
            print("⚠️  表结构验证失败")
            print(f"   预期: {expected_columns}")
            print(f"   实际: {actual_columns}")
        
        # 测试插入和查询
        print(f"\n🧪 测试插入和查询...")
        test_symbol = "TEST_MIGRATION"
        test_time = datetime.now()
        
        # 插入测试数据
        await conn.execute(
            """
            INSERT INTO position_entry_times (symbol, entry_time, updated_at)
            VALUES ($1, $2, $3)
            ON CONFLICT (symbol) DO UPDATE 
            SET entry_time = $2, updated_at = $3;
            """,
            test_symbol,
            test_time,
            test_time
        )
        
        # 查询测试数据
        result = await conn.fetchrow(
            "SELECT * FROM position_entry_times WHERE symbol = $1",
            test_symbol
        )
        
        if result:
            print("✅ 插入/查询测试通过")
            print(f"   Symbol: {result['symbol']}")
            print(f"   Entry Time: {result['entry_time']}")
        else:
            print("❌ 插入/查询测试失败")
        
        # 清理测试数据
        await conn.execute(
            "DELETE FROM position_entry_times WHERE symbol = $1",
            test_symbol
        )
        print("🗑️  测试数据已清理")
        
        # 关闭连接
        await conn.close()
        print("\n✅ 数据库连接已关闭")
        
        print("\n" + "=" * 80)
        print("✅ Phase 1 Migration 完成!")
        print("=" * 80)
        print("\n✅ position_entry_times 表已就绪")
        print("✅ PositionController 现在可以正常启动（无 relation not exist 错误）")
        print("\n下一步: 重启应用程序以验证修复")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Migration 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    success = await create_position_entry_times_table()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
