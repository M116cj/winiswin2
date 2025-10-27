#!/usr/bin/env python3
"""
交易对诊断工具 - 检查交易对是否可交易及参数要求

用法：
python -m scripts.check_symbol BLUAIUSDT
"""

import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.clients.binance_client import BinanceClient
from src.config import Config
from src.utils.logger import logger


async def check_symbol(symbol: str):
    """检查交易对的可交易性和规则"""
    client = BinanceClient(
        Config.BINANCE_API_KEY,
        Config.BINANCE_API_SECRET,
        testnet=Config.BINANCE_TESTNET
    )
    
    try:
        logger.info(f"\n{'='*60}")
        logger.info(f"检查交易对: {symbol}")
        logger.info(f"{'='*60}\n")
        
        # 1. 检查交易所信息
        logger.info("1️⃣ 获取交易所信息...")
        exchange_info = await client.get_exchange_info()
        
        # 查找交易对
        symbol_info = None
        for s in exchange_info.get('symbols', []):
            if s.get('symbol') == symbol:
                symbol_info = s
                break
        
        if not symbol_info:
            logger.error(f"❌ 交易对 {symbol} 不存在或已下架")
            return
        
        # 2. 显示基本信息
        logger.info(f"✅ 找到交易对: {symbol}")
        logger.info(f"   状态: {symbol_info.get('status')}")
        logger.info(f"   合约类型: {symbol_info.get('contractType')}")
        logger.info(f"   报价资产: {symbol_info.get('quoteAsset')}")
        logger.info(f"   基础资产: {symbol_info.get('baseAsset')}")
        
        # 检查状态
        if symbol_info.get('status') != 'TRADING':
            logger.warning(f"⚠️  交易对状态异常: {symbol_info.get('status')}")
            logger.warning(f"   该交易对可能暂停交易")
        
        # 3. 显示过滤器规则
        logger.info(f"\n2️⃣ 交易规则:")
        filters = symbol_info.get('filters', [])
        
        for f in filters:
            filter_type = f.get('filterType')
            
            if filter_type == 'PRICE_FILTER':
                logger.info(f"\n   📊 价格过滤器 (PRICE_FILTER):")
                logger.info(f"      最小价格: {f.get('minPrice')}")
                logger.info(f"      最大价格: {f.get('maxPrice')}")
                logger.info(f"      价格步长: {f.get('tickSize')}")
            
            elif filter_type == 'LOT_SIZE':
                logger.info(f"\n   📏 数量过滤器 (LOT_SIZE):")
                logger.info(f"      最小数量: {f.get('minQty')}")
                logger.info(f"      最大数量: {f.get('maxQty')}")
                logger.info(f"      数量步长: {f.get('stepSize')}")
            
            elif filter_type == 'MIN_NOTIONAL':
                logger.info(f"\n   💰 最小名义价值 (MIN_NOTIONAL):")
                logger.info(f"      最小名义价值: {f.get('notional')} USDT")
            
            elif filter_type == 'MARKET_LOT_SIZE':
                logger.info(f"\n   🛒 市价单数量过滤器 (MARKET_LOT_SIZE):")
                logger.info(f"      最小数量: {f.get('minQty')}")
                logger.info(f"      最大数量: {f.get('maxQty')}")
                logger.info(f"      数量步长: {f.get('stepSize')}")
        
        # 4. 获取当前价格
        logger.info(f"\n3️⃣ 当前市场价格:")
        try:
            ticker = await client.get_ticker_price(symbol)
            price = float(ticker.get('price', 0))
            logger.info(f"   当前价格: {price} USDT")
            
            # 计算建议的最小订单
            min_notional = 0
            for f in filters:
                if f.get('filterType') == 'MIN_NOTIONAL':
                    min_notional = float(f.get('notional', 0))
                    break
            
            if min_notional > 0 and price > 0:
                min_qty_required = min_notional / price
                logger.info(f"\n   💡 建议最小数量: {min_qty_required:.8f} (满足最小名义价值)")
            
        except Exception as e:
            logger.error(f"   ❌ 获取价格失败: {e}")
        
        # 5. 检查24小时交易量
        logger.info(f"\n4️⃣ 24小时统计:")
        try:
            ticker_24h = await client.get_24h_ticker(symbol)
            logger.info(f"   24小时成交量: {ticker_24h.get('volume')}")
            logger.info(f"   24小时成交额: {ticker_24h.get('quoteVolume')} USDT")
            logger.info(f"   价格变化: {ticker_24h.get('priceChangePercent')}%")
            
            volume = float(ticker_24h.get('volume', 0))
            if volume < 1000:
                logger.warning(f"   ⚠️  24小时成交量较低，可能流动性不足")
        
        except Exception as e:
            logger.error(f"   ❌ 获取24小时统计失败: {e}")
        
        logger.info(f"\n{'='*60}\n")
        
    except Exception as e:
        logger.error(f"❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await client.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python -m scripts.check_symbol <SYMBOL>")
        print("示例: python -m scripts.check_symbol BLUAIUSDT")
        sys.exit(1)
    
    symbol = sys.argv[1].upper()
    asyncio.run(check_symbol(symbol))
