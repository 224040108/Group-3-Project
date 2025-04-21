import time
import threading
import pandas as pd
from datetime import datetime, timedelta
from strategy import PairTradingStrategy
from config.config import EXECUTION_CONFIG
import database as db
import yfinance as yf

class ExecutionSystem:
    def __init__(self, strategy=None, config=None):
        self.strategy = strategy or PairTradingStrategy()
        self.config = config or EXECUTION_CONFIG
        self.update_interval = self.config['update_interval']
        self.max_order_size = self.config['max_order_size']
        self.running = False
        self.thread = None
        self.last_update_time = None
    
    def start(self):
        """启动执行系统"""
        if self.running:
            print("执行系统已经在运行")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_loop)
        self.thread.daemon = True
        self.thread.start()
        print("执行系统已启动")
    
    def stop(self):
        """停止执行系统"""
        self.running = False
        if self.thread:
            self.thread.join()
        print("执行系统已停止")
    
    def _run_loop(self):
        """执行系统主循环"""
        while self.running:
            try:
                # 检查是否是交易时间
                now = datetime.now()
                if self._is_trading_time(now):
                    # 生成交易信号
                    signals = self.strategy.run()
                    
                    # 执行交易
                    for signal in signals:
                        if signal['action'] in ['open', 'close', 'stop_loss']:
                            self._execute_trade(signal)
                    
                    self.last_update_time = now
                
                # 等待下一次更新
                time.sleep(self.update_interval)
            
            except Exception as e:
                print(f"执行系统错误: {e}")
                time.sleep(self.update_interval)
    
    def _is_trading_time(self, now):
        """检查是否是交易时间"""
        # 检查是否是工作日
        if now.weekday() >= 5:  # 周六和周日
            return False
        
        # 检查是否是交易时段
        hour = now.hour
        minute = now.minute
        
        # 上午交易时段: 9:30 - 11:30
        if (hour == 9 and minute >= 30) or (hour == 10) or (hour == 11 and minute <= 30):
            return True
        
        # 下午交易时段: 13:00 - 15:00
        if (hour >= 13 and hour < 15):
            return True
        
        return False
    
    def _execute_trade(self, signal):
        """执行交易"""
        try:
            pair_id = signal['pair_id']
            
            if signal['action'] in ['close', 'stop_loss']:
                # 平仓交易
                position_type = signal['position_type']
                
                # 获取当前价格
                stock1_price = self._get_real_time_price(signal['stock1_code'])
                stock2_price = self._get_real_time_price(signal['stock2_code'])
                
                if stock1_price is None or stock2_price is None:
                    print(f"无法获取实时价格，取消交易: {pair_id}")
                    return
                
                # 确定做多和做空的股票
                if position_type == 'long_short':
                    long_code = signal['stock1_code']
                    short_code = signal['stock2_code']
                    long_price = stock1_price
                    short_price = stock2_price
                else:
                    long_code = signal['stock2_code']
                    short_code = signal['stock1_code']
                    long_price = stock2_price
                    short_price = stock1_price
                
                # 获取持仓信息
                position = self.strategy.positions.get(pair_id)
                if not position:
                    print(f"找不到持仓信息，取消交易: {pair_id}")
                    return
                
                # 计算盈亏
                if position_type == 'long_short':
                    long_pnl = (long_price - position['stock1_price']) * position['quantity']
                    short_pnl = (position['stock2_price'] - short_price) * position['quantity']
                else:
                    long_pnl = (long_price - position['stock2_price']) * position['quantity']
                    short_pnl = (position['stock1_price'] - short_price) * position['quantity']
                
                total_pnl = long_pnl + short_pnl
                
                # 记录交易
                trade_data = {
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'pair_id': pair_id,
                    'long_code': long_code,
                    'short_code': short_code,
                    'long_price': long_price,
                    'short_price': short_price,
                    'quantity': position['quantity'],
                    'action': signal['action'],
                    'pnl': total_pnl,
                    'status': 'closed'
                }
                
                # 保存到数据库
                db.save_trade(trade_data)
                
                # 更新策略持仓
                self.strategy.update_positions(trade_data)
                
                print(f"执行平仓交易: {pair_id}, PnL: {total_pnl:.2f}")
            
            elif signal['action'] == 'open':
                # 开仓交易
                position_type = signal['position_type']
                
                # 获取当前价格
                stock1_price = self._get_real_time_price(signal['stock1_code'])
                stock2_price = self._get_real_time_price(signal['stock2_code'])
                
                if stock1_price is None or stock2_price is None:
                    print(f"无法获取实时价格，取消交易: {pair_id}")
                    return
                
                # 确定做多和做空的股票
                if position_type == 'long_short':
                    long_code = signal['stock1_code']
                    short_code = signal['stock2_code']
                    long_price = stock1_price
                    short_price = stock2_price
                else:
                    long_code = signal['stock2_code']
                    short_code = signal['stock1_code']
                    long_price = stock2_price
                    short_price = stock1_price
                
                # 计算仓位大小
                total_value = long_price + short_price
                quantity = min(self.max_order_size / total_value, self.strategy.position_size * 1000000 / total_value)
                
                # 记录交易
                trade_data = {
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'pair_id': pair_id,
                    'long_code': long_code,
                    'short_code': short_code,
                    'long_price': long_price,
                    'short_price': short_price,
                    'quantity': quantity,
                    'action': 'open',
                    'pnl': 0,
                    'status': 'open'
                }
                
                # 保存到数据库
                db.save_trade(trade_data)
                
                # 更新策略持仓
                self.strategy.update_positions(trade_data)
                
                print(f"执行开仓交易: {pair_id}, 数量: {quantity:.2f}")
        
        except Exception as e:
            print(f"执行交易错误: {e}")
    
    def _get_real_time_price(self, code):
        """获取实时价格"""
        try:
            # 使用yfinance获取实时行情
            # 转换为yfinance格式的代码
            if '.SH' in code:
                yf_code = code.replace('.SH', '.SS')
            elif '.SZ' in code:
                yf_code = code  # 深圳代码保持不变
            else:
                yf_code = code
                
            # 获取最近1分钟的数据
            end_time = datetime.now()
            start_time = end_time - timedelta(minutes=5)  # 获取最近5分钟的数据，以防最新的1分钟数据还未更新
            
            df = yf.download(
                yf_code,
                start=start_time,
                end=end_time,
                interval='1m',
                progress=False
            )
            
            if df is not None and not df.empty:
                # 返回最新的收盘价
                return float(df['Close'].iloc[-1])
            
            # 如果无法获取分钟数据，尝试获取日线数据的最新价格
            df_daily = yf.download(
                yf_code,
                period='1d',
                progress=False
            )
            
            if df_daily is not None and not df_daily.empty:
                return float(df_daily['Close'].iloc[-1])
                
            return None
        except Exception as e:
            print(f"获取实时价格错误: {e}")
            return None