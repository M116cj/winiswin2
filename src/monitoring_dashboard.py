"""
📊 Real-time Monitoring Dashboard - Track Signals, Trades, ML Performance
"""

import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


class MonitoringDashboard:
    """Real-time system monitoring and performance tracking"""
    
    def __init__(self):
        self.signals_generated = 0
        self.trades_completed = 0
        self.trades_won = 0
        self.total_pnl = 0.0
        self.total_return_pct = 0.0
        self.predictions_data = []
        self.ml_training_triggered = False
    
    async def collect_statistics(self):
        """Collect real-time statistics from system"""
        try:
            from src.capital_tracker import get_capital_tracker, get_account_status
            from src.experience_buffer import get_experience_buffer
            from src.ml_model import get_ml_model
            
            # Get account status
            status = get_account_status()
            
            # Get experience buffer
            exp_buf = get_experience_buffer()
            
            # Get ML model
            ml_model = get_ml_model()
            
            return {
                'account_status': status,
                'experiences_count': len(exp_buf.experiences) if exp_buf else 0,
                'ml_trained': ml_model.is_trained if ml_model else False,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.warning(f"⚠️ Error collecting statistics: {e}")
            return None
    
    async def query_trading_data(self):
        """Query trading results from database"""
        try:
            import asyncpg
            from src.config import get_database_url
            
            db_url = get_database_url()
            conn = await asyncpg.connect(db_url)
            
            # Count signals
            signals = await conn.fetch("SELECT COUNT(*) as count FROM signals")
            signal_count = signals[0]['count'] if signals else 0
            
            # Get recent signals with details
            recent_signals = await conn.fetch("""
                SELECT id, symbol, confidence, position_size, timestamp 
                FROM signals 
                ORDER BY timestamp DESC 
                LIMIT 20
            """)
            
            # Get market data count
            market_data = await conn.fetch("SELECT COUNT(*) as count FROM market_data")
            market_count = market_data[0]['count'] if market_data else 0
            
            await conn.close()
            
            return {
                'total_signals': signal_count,
                'recent_signals': recent_signals,
                'market_data_records': market_count
            }
        except Exception as e:
            logger.warning(f"⚠️ Error querying database: {e}")
            return None
    
    async def print_dashboard(self):
        """Print real-time dashboard"""
        stats = await self.collect_statistics()
        db_data = await self.query_trading_data()
        
        print("\n" + "=" * 80)
        print("📊 REAL-TIME MONITORING DASHBOARD")
        print("=" * 80)
        
        if stats:
            print(f"\n💼 ACCOUNT STATUS:")
            if 'account_status' in stats and stats['account_status']:
                s = stats['account_status']
                print(f"  Total Equity: ${s.get('total_equity', 0):,.2f}")
                print(f"  Available Balance: ${s.get('available_balance', 0):,.2f}")
                print(f"  Realized PnL: ${s.get('realized_pnl', 0):,.2f}")
                print(f"  Unrealized PnL: ${s.get('unrealized_pnl', 0):,.2f}")
                print(f"  Total Return: {s.get('total_return_pct', 0):.2f}%")
                print(f"  Win Rate: {s.get('win_rate', 0):.1%}")
                print(f"  Trades Completed: {s.get('trade_count', 0)}")
                print(f"  Open Positions: {s.get('open_positions', 0)}")
        
        if db_data:
            print(f"\n📈 TRADING SIGNALS:")
            print(f"  Total Signals Generated: {db_data['total_signals']}")
            print(f"  Market Data Records: {db_data['market_data_records']}")
            
            if db_data['recent_signals']:
                print(f"\n  Recent Signals (Last 5):")
                for sig in db_data['recent_signals'][:5]:
                    print(f"    • {sig['symbol']:10} | Conf: {sig['confidence']:.1%} | Size: ${sig['position_size']:.0f}")
        
        if stats and 'experiences_count' in stats:
            print(f"\n🧠 ML TRAINING STATUS:")
            print(f"  Experience Buffer: {stats['experiences_count']} records")
            print(f"  ML Model Trained: {'✅ Yes' if stats['ml_trained'] else '❌ No'}")
            print(f"  Ready for Training: {'✅ Yes (10+ trades)' if stats['experiences_count'] >= 10 else f'❌ No ({stats['experiences_count']}/10)'}")
        
        print("\n" + "=" * 80 + "\n")


async def start_monitoring():
    """Start continuous monitoring"""
    dashboard = MonitoringDashboard()
    
    # Print initial dashboard
    await dashboard.print_dashboard()
    
    # Return dashboard for periodic updates
    return dashboard


# Convenience function
async def update_dashboard():
    """Update and print dashboard"""
    dashboard = MonitoringDashboard()
    await dashboard.print_dashboard()
    return dashboard
