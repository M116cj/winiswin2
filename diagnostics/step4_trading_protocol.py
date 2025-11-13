#!/usr/bin/env python3
"""
STEP 4: 交易協議與訂單規範檢測
檢測合約規格、訂單參數問題、驗證邏輯、錯誤處理
"""

import os
import sys
import asyncio
import aiohttp
from decimal import Decimal

sys.path.insert(0, '/home/runner/workspace')

class TradingProtocolTester:
    def __init__(self):
        self.base_url = 'https://fapi.binance.com'
        
    async def get_symbol_info(self, session, symbol):
        """獲取交易對詳細信息"""
        try:
            url = f'{self.base_url}/fapi/v1/exchangeInfo'
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    symbol_info = next((s for s in data.get('symbols', []) if s['symbol'] == symbol), None)
                    return symbol_info
                else:
                    return None
        except Exception as e:
            print(f"❌ 獲取{symbol}信息失敗: {e}")
            return None
    
    def analyze_filters(self, symbol_info):
        """分析過濾器規則"""
        if not symbol_info:
            return None
        
        filters = {f['filterType']: f for f in symbol_info.get('filters', [])}
        
        analysis = {
            'symbol': symbol_info['symbol'],
            'status': symbol_info['status'],
            'price_filter': filters.get('PRICE_FILTER', {}),
            'lot_size': filters.get('LOT_SIZE', {}),
            'min_notional': filters.get('MIN_NOTIONAL', {}),
            'market_lot_size': filters.get('MARKET_LOT_SIZE', {}),
        }
        
        return analysis
    
    def check_order_validity(self, analysis, price, quantity):
        """檢查訂單有效性"""
        issues = []
        
        if not analysis:
            return False, ["無法獲取交易對信息"]
        
        # 1. 價格過濾器檢查
        price_filter = analysis.get('price_filter', {})
        if price_filter:
            min_price = Decimal(price_filter.get('minPrice', '0'))
            max_price = Decimal(price_filter.get('maxPrice', '0'))
            tick_size = Decimal(price_filter.get('tickSize', '0'))
            
            price_dec = Decimal(str(price))
            
            if price_dec < min_price:
                issues.append(f"價格過低: {price} < {min_price}")
            if max_price > 0 and price_dec > max_price:
                issues.append(f"價格過高: {price} > {max_price}")
            if tick_size > 0 and (price_dec % tick_size) != 0:
                issues.append(f"價格步長不符: {price} % {tick_size} != 0")
        
        # 2. 數量過濾器檢查
        lot_size = analysis.get('lot_size', {})
        if lot_size:
            min_qty = Decimal(lot_size.get('minQty', '0'))
            max_qty = Decimal(lot_size.get('maxQty', '0'))
            step_size = Decimal(lot_size.get('stepSize', '0'))
            
            qty_dec = Decimal(str(quantity))
            
            if qty_dec < min_qty:
                issues.append(f"數量過小: {quantity} < {min_qty}")
            if max_qty > 0 and qty_dec > max_qty:
                issues.append(f"數量過大: {quantity} > {max_qty}")
            if step_size > 0 and (qty_dec % step_size) != 0:
                issues.append(f"數量步長不符: {quantity} % {step_size} != 0")
        
        # 3. 最小名義價值檢查
        min_notional = analysis.get('min_notional', {})
        if min_notional:
            min_notional_value = Decimal(min_notional.get('notional', '0'))
            notional_value = Decimal(str(price)) * Decimal(str(quantity))
            
            if notional_value < min_notional_value:
                issues.append(f"名義價值不符: {notional_value:.2f} < {min_notional_value} USDT")
                # 計算建議最小數量
                suggested_qty = float(min_notional_value / Decimal(str(price)))
                issues.append(f"💡 建議最小數量: {suggested_qty:.2f} (基於價格 {price})")
        
        return len(issues) == 0, issues
    
    async def run_tests(self):
        """執行所有測試"""
        print("=" * 60)
        print("💰 STEP 4: 交易協議與訂單規範檢測")
        print("=" * 60)
        print()
        
        results = []
        
        async with aiohttp.ClientSession() as session:
            # 測試關鍵交易對
            test_cases = [
                ('BTCUSDT', 50000.0, 0.001),  # 正常訂單
                ('ETHUSDT', 3000.0, 0.01),    # 正常訂單
                ('SKLUSDT', 0.01693, 294.0),  # 可能的問題訂單
            ]
            
            for symbol, price, quantity in test_cases:
                print(f"📌 檢測 {symbol}")
                print(f"   價格: {price}, 數量: {quantity}")
                
                # 獲取交易對信息
                symbol_info = await self.get_symbol_info(session, symbol)
                
                if symbol_info:
                    # 分析過濾器
                    analysis = self.analyze_filters(symbol_info)
                    
                    if analysis:
                        # 顯示規格
                        print(f"\n✅ {symbol}合約規格:")
                        
                        pf = analysis['price_filter']
                        print(f"   價格過濾器: 最小={pf.get('minPrice')}, 步長={pf.get('tickSize')}")
                        
                        ls = analysis['lot_size']
                        print(f"   數量過濾器: 最小={ls.get('minQty')}, 步長={ls.get('stepSize')}")
                        
                        mn = analysis['min_notional']
                        if mn:
                            print(f"   名義價值過濾器: 最小={mn.get('notional')} USDT")
                        
                        # 檢查訂單有效性
                        valid, issues = self.check_order_validity(analysis, price, quantity)
                        
                        if valid:
                            print(f"\n✅ 訂單參數驗證通過")
                            results.append(True)
                        else:
                            print(f"\n❌ 訂單參數驗證失敗:")
                            for issue in issues:
                                print(f"   • {issue}")
                            results.append(False)
                    else:
                        print(f"❌ 無法分析{symbol}過濾器")
                        results.append(False)
                else:
                    print(f"❌ 無法獲取{symbol}信息（可能因HTTP 451限制）")
                    results.append(False)
                
                print()
        
        # 檢查系統訂單驗證邏輯
        print("📌 檢查系統OrderValidator邏輯")
        try:
            from src.clients.order_validator import OrderValidator
            validator = OrderValidator()
            print(f"✅ OrderValidator已加載")
            print(f"   最小名義價值閾值: {validator.min_notional_value} USDT")
            results.append(True)
        except Exception as e:
            print(f"❌ OrderValidator加載失敗: {e}")
            results.append(False)
        print()
        
        # 總評分
        success_count = sum(results)
        total_count = len(results)
        score = (success_count / total_count * 100) if total_count > 0 else 0
        
        print("=" * 60)
        print(f"📊 STEP 4 總體評分: {score:.1f}% ({success_count}/{total_count}項通過)")
        print("=" * 60)
        
        return score

async def main():
    tester = TradingProtocolTester()
    score = await tester.run_tests()
    return score

if __name__ == "__main__":
    score = asyncio.run(main())
    sys.exit(0 if score >= 80 else 1)
