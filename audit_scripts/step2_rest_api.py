#!/usr/bin/env python3
"""
STEP 2: Binance REST API 深度檢測
驗證API密鑰、測試所有關鍵端點、檢查權限和交易規則
"""

import os
import sys
import asyncio
import aiohttp
import hmac
import hashlib
from datetime import datetime
from urllib.parse import urlencode

# 添加項目路徑
sys.path.insert(0, '/home/runner/workspace')

class BinanceAPITester:
    def __init__(self):
        self.api_key = os.getenv('BINANCE_API_KEY', '')
        self.api_secret = os.getenv('BINANCE_API_SECRET', '')
        self.base_url = 'https://fapi.binance.com'
        self.spot_url = 'https://api.binance.com'
        
    def _generate_signature(self, params):
        """生成API簽名"""
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    async def test_endpoint(self, session, name, url, method='GET', signed=False, params=None):
        """測試單個端點"""
        if params is None:
            params = {}
        
        headers = {'X-MBX-APIKEY': self.api_key} if self.api_key else {}
        
        if signed:
            params['timestamp'] = int(datetime.now().timestamp() * 1000)
            params['signature'] = self._generate_signature(params)
        
        try:
            start_time = datetime.now()
            async with session.request(method, url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                latency = (datetime.now() - start_time).total_seconds() * 1000
                
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ {name}: 正常 ({latency:.0f}ms)")
                    return True, data
                elif response.status == 451:
                    print(f"🚫 {name}: HTTP 451 地理限制")
                    return False, None
                else:
                    error_text = await response.text()
                    print(f"❌ {name}: HTTP {response.status} - {error_text[:100]}")
                    return False, None
                    
        except asyncio.TimeoutError:
            print(f"⏱️ {name}: 超時")
            return False, None
        except Exception as e:
            print(f"❌ {name}: 異常 - {str(e)[:100]}")
            return False, None
    
    async def run_tests(self):
        """執行所有測試"""
        print("=" * 60)
        print("🔌 STEP 2: Binance REST API 深度檢測")
        print("=" * 60)
        print()
        
        # 1. API密鑰檢查
        print("📌 2.1 API密鑰配置檢查")
        if self.api_key and self.api_secret:
            print(f"✅ API Key: 已配置 ({self.api_key[:8]}...)")
            print(f"✅ API Secret: 已配置 ({len(self.api_secret)}字符)")
        else:
            print("❌ API Key/Secret: 未配置")
        print()
        
        results = []
        
        async with aiohttp.ClientSession() as session:
            # 2. 現貨行情API測試
            print("📌 2.2 現貨行情API測試")
            spot_tests = [
                ('現貨Ping', f'{self.spot_url}/api/v3/ping'),
                ('現貨服務器時間', f'{self.spot_url}/api/v3/time'),
                ('現貨交易規則', f'{self.spot_url}/api/v3/exchangeInfo'),
            ]
            
            for name, url in spot_tests:
                result, _ = await self.test_endpoint(session, name, url)
                results.append(result)
            print()
            
            # 3. 合約行情API測試
            print("📌 2.3 合約行情API測試")
            futures_tests = [
                ('合約Ping', f'{self.base_url}/fapi/v1/ping'),
                ('合約服務器時間', f'{self.base_url}/fapi/v1/time'),
                ('合約交易規則', f'{self.base_url}/fapi/v1/exchangeInfo'),
                ('合約深度', f'{self.base_url}/fapi/v1/depth', {'symbol': 'BTCUSDT', 'limit': 5}),
            ]
            
            for name, url, *params in futures_tests:
                param_dict = params[0] if params else None
                result, _ = await self.test_endpoint(session, name, url, params=param_dict)
                results.append(result)
            print()
            
            # 4. API權限檢查（需要簽名）
            print("📌 2.4 API權限檢查")
            if self.api_key and self.api_secret:
                auth_tests = [
                    ('賬戶信息', f'{self.base_url}/fapi/v2/account', True),
                    ('持倉信息', f'{self.base_url}/fapi/v2/positionRisk', True),
                ]
                
                for name, url, signed in auth_tests:
                    result, _ = await self.test_endpoint(session, name, url, signed=signed)
                    results.append(result)
            else:
                print("⚠️  跳過（API密鑰未配置）")
            print()
            
            # 5. 交易對檢查
            print("📌 2.5 關鍵交易對檢查")
            result, data = await self.test_endpoint(session, '獲取交易規則', f'{self.base_url}/fapi/v1/exchangeInfo')
            if result and data:
                symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
                for symbol in symbols:
                    symbol_info = next((s for s in data.get('symbols', []) if s['symbol'] == symbol), None)
                    if symbol_info:
                        filters = {f['filterType']: f for f in symbol_info.get('filters', [])}
                        min_qty = filters.get('LOT_SIZE', {}).get('minQty', 'N/A')
                        print(f"✅ {symbol}: 可交易 (最小數量: {min_qty})")
                        results.append(True)
                    else:
                        print(f"❌ {symbol}: 未找到")
                        results.append(False)
            print()
        
        # 總評分
        success_count = sum(results)
        total_count = len(results)
        score = (success_count / total_count * 100) if total_count > 0 else 0
        
        print("=" * 60)
        print(f"📊 STEP 2 總體評分: {score:.1f}% ({success_count}/{total_count}端點正常)")
        print("=" * 60)
        
        return score

async def main():
    tester = BinanceAPITester()
    score = await tester.run_tests()
    return score

if __name__ == "__main__":
    score = asyncio.run(main())
    sys.exit(0 if score >= 80 else 1)
