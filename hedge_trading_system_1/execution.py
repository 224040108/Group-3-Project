import time
import threading
import numpy as np
import pandas as pd
import database as db
from datetime import datetime, timedelta
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from strategy import PairTradingStrategy
from config.config import EXECUTION_CONFIG
import database as db
import yfinance as yf
import os

# 添加DataLoader类
class DataLoader:
    def __init__(self, start_date=None, end_date=None):
        """初始化数据加载器"""
        self.start_date = start_date
        self.end_date = end_date
        self.data = {}
        
    def load_data(self, stock_codes):
        """加载股票数据"""
        for code in stock_codes:
            # 尝试从数据库获取数据
            df = db.get_stock_data(code, self.start_date, self.end_date)
            
            if df is None or len(df) == 0:
                # 如果数据库中没有数据，从yfinance获取
                print(f"从yfinance获取股票 {code} 的数据")
                df = self._fetch_data_from_yfinance(code)
                
                # 保存到数据库
                if df is not None and len(df) > 0:
                    for index, row in df.iterrows():
                        # 修复：确保获取单个值而不是Series
                        data = {
                            'code': code,
                            'date': index.strftime('%Y%m%d') if hasattr(index, 'strftime') else str(index),
                            'open': float(row['Open']) if not pd.isna(row['Open']) else 0.0,
                            'high': float(row['High']) if not pd.isna(row['High']) else 0.0,
                            'low': float(row['Low']) if not pd.isna(row['Low']) else 0.0,
                            'close': float(row['Close']) if not pd.isna(row['Close']) else 0.0,
                            'volume': float(row['Volume']) if not pd.isna(row['Volume']) else 0,
                            'amount': float(row['Volume'] * row['Close']) if not pd.isna(row['Volume']) and not pd.isna(row['Close']) else 0.0
                        }
                        try:
                            db.save_stock_data(data)
                        except Exception as e:
                            print(f"保存股票数据时出错: {e}")
                            print(f"数据: {data}")
            else:
                # 统一列名为大写格式，与yfinance保持一致
                df.rename(columns={
                    'open': 'Open',
                    'high': 'High',
                    'low': 'Low',
                    'close': 'Close',
                    'volume': 'Volume'
                }, inplace=True)
            
            # 将数据添加到字典中
            if df is not None and len(df) > 0:
                self.data[code] = df
                print(f"成功加载 {code} 的 {len(df)} 条数据")
            else:
                print(f"警告: 无法获取 {code} 的数据")
    
    def load_recent_data_from_db(self, stock_codes, months=3):
        """直接从数据库加载最近几个月的数据"""
        # 计算开始日期（当前日期减去指定的月数）
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30 * months)
        
        start_date_str = start_date.strftime('%Y%m%d')
        end_date_str = end_date.strftime('%Y%m%d')
        
        print(f"从数据库加载最近{months}个月的数据: {start_date_str} 至 {end_date_str}")
        
        for code in stock_codes:
            # 从数据库获取数据
            df = db.get_stock_data(code, start_date_str, end_date_str)
            
            if df is not None and len(df) > 0:
                # 将日期列转换为datetime索引
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')
                    df.set_index('date', inplace=True)
                
                self.data[code] = df
                print(f"成功从数据库加载 {code} 的 {len(df)} 条数据")
            else:
                print(f"警告: 数据库中没有 {code} 在指定时间范围内的数据")
        
        return len(self.data) > 0
    
    def get_trading_dates(self):
        """获取交易日期列表"""
        # 如果没有数据，返回空列表
        if not self.data:
            return []
        
        # 获取第一只股票的日期
        first_code = list(self.data.keys())[0]
        dates = self.data[first_code].index.tolist()
        
        # 转换为字符串格式
        date_strs = [date.strftime('%Y%m%d') if hasattr(date, 'strftime') else str(date) for date in dates]
        
        return date_strs
    
    def get_price(self, code, date):
        """获取指定日期的收盘价"""
        if code not in self.data:
            return None
        
        # 确定收盘价列名
        close_column = None
        if 'Close' in self.data[code].columns:
            close_column = 'Close'
        elif 'close' in self.data[code].columns:
            close_column = 'close'
        else:
            print(f"警告: 数据中没有收盘价列 (Close/close)，可用列: {self.data[code].columns.tolist()}")
            return None
        
        # 如果日期是字符串格式，转换为datetime
        if isinstance(date, str):
            try:
                date_obj = datetime.strptime(date, '%Y%m%d')
                # 查找最接近的日期
                for idx, row_date in enumerate(self.data[code].index):
                    if row_date >= date_obj:
                        return self.data[code].iloc[idx][close_column]
                return None
            except:
                # 如果转换失败，尝试直接查找
                if date in self.data[code].index:
                    return self.data[code].loc[date][close_column]
                return None
        
        # 如果日期是datetime格式
        if date in self.data[code].index:
            return self.data[code].loc[date][close_column]
        
        return None
    
    def _fetch_data_from_yfinance(self, code):
        """从yfinance获取股票数据"""
        try:
            # 转换股票代码格式
            if '.SH' in code:
                yf_code = code.replace('.SH', '.SS')
            elif '.SZ' in code:
                yf_code = code.replace('.SZ', '.SZ')
            else:
                yf_code = code
            
            # 获取数据
            df = yf.download(yf_code, start=self.start_date, end=self.end_date)
            
            return df
        except Exception as e:
            print(f"获取股票 {code} 数据失败: {e}")
            return None

class ExecutionSystem:
    def __init__(self, strategy, initial_capital=1000000, commission_rate=0.0003):
        """初始化执行系统"""
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.equity = initial_capital
        self.commission_rate = commission_rate
        
        # 初始化状态变量
        self.running = False
        self.thread = None
        self.current_date_index = 0
        self.equity_curve = [initial_capital]
        self.trades = []
        self.positions = {}
        self.update_callback = None
        self.trading_days = []
        self.returns = []
        self.drawdowns = []
        self.data = {}
        
        # 设置日期范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)
        self.start_date = start_date.strftime('%Y-%m-%d')
        self.end_date = end_date.strftime('%Y-%m-%d')
        
        # 初始化数据加载器
        self.data_loader = DataLoader(start_date=self.start_date, end_date=self.end_date)
        
        # 加载数据
        self._load_data()
    
    def _load_data(self):
        """加载历史数据"""
        # 获取所有股票代码
        stock_codes = []
        for pair in self.strategy.pairs:
            stock_codes.extend(pair)
        stock_codes = list(set(stock_codes))  # 去重
        
        # 首先尝试从数据库加载最近3个月的数据
        success = self.data_loader.load_recent_data_from_db(stock_codes, months=3)
        
        # 如果数据库中没有足够的数据，则尝试从yfinance获取
        if not success:
            print("数据库中没有足够的数据，尝试从yfinance获取...")
            self.data_loader.load_data(stock_codes)
        
        # 将数据加载器中的数据复制到执行系统中
        self.data = self.data_loader.data

    def start(self, update_callback=None):
        """启动执行系统"""
        if self.running:
            return {'status': 'error', 'message': '执行系统已经在运行'}
        
        # 设置回调函数
        self.update_callback = update_callback
        
        # 重置状态
        self.running = True
        self.current_date_index = 0
        self.equity_curve = [self.initial_capital]  # 初始化权益曲线
        
        # 创建初始图表
        static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
        if not os.path.exists(static_dir):
            os.makedirs(static_dir)
        
        chart_path = os.path.join(static_dir, 'execution_results.png')
        try:
            import matplotlib.pyplot as plt
            plt.figure(figsize=(10, 6))
            plt.title('策略权益曲线 (等待数据...)')
            plt.xlabel('交易日')
            plt.ylabel('权益')
            plt.grid(True)
            plt.ylim([self.initial_capital * 0.9, self.initial_capital * 1.1])  # 设置一个合理的范围
            plt.savefig(chart_path)
            plt.close()
            print(f"初始空白图表已创建: {chart_path}")
            
            # 立即调用回调函数，更新初始状态
            if self.update_callback:
                # 计算初始指标
                metrics = {
                    'total_return': '0.00%',
                    'annual_return': '0.00%',
                    'sharpe_ratio': '0.00',
                    'max_drawdown': '0.00%',
                    'win_rate': '0.00%',
                    'profit_loss_ratio': '0.00',
                    'total_trades': '0'
                }
                self.update_callback(0, '等待数据...', metrics, [])
        except Exception as e:
            print(f"创建初始空白图表失败: {e}")
        
        # 启动执行线程
        self.thread = threading.Thread(target=self._run_loop)
        self.thread.daemon = True
        self.thread.start()
        
        print("执行系统已启动")
        
        return {'status': 'success', 'message': '执行系统已启动'}
    
    def stop(self):
        """停止执行系统"""
        self.running = False
        if self.thread:
            self.thread.join()
        print("执行系统已停止")
        
        return {
            'status': 'success',
            'message': '执行系统已停止'
        }
    
    def _initialize_backtest(self):
        """初始化回测数据"""
        print(f"初始化回测数据: {self.start_date} 至 {self.end_date}")
        
        # 重置状态
        self.equity = self.initial_capital
        self.positions = {}
        self.trades = []
        self.daily_returns = []
        self.daily_equity = []
        self.equity_curve = [self.initial_capital]
        self.returns = []
        self.drawdowns = []
        self.current_date_index = 0
        
        # 加载历史数据
        self._load_data()
        
        # 计算股票对的统计数据
        self.strategy.calculate_pair_stats(self.data)
        
        # 获取所有交易日
        self.trading_days = sorted(self.data.keys())
        
        # 保存回测配置信息
        backtest_info = {
            'start_date': self.start_date,
            'end_date': self.end_date,
            'initial_capital': self.initial_capital,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        db.save_backtest_info(backtest_info)
        
        print(f"初始化完成，共 {len(self.trading_days)} 个交易日")
    
    def _run_loop(self):
        """执行系统主循环"""
        try:
            # 获取交易日期列表
            trading_dates = self.data_loader.get_trading_dates()
            
            # 如果没有交易日期，直接返回
            if not trading_dates or len(trading_dates) == 0:
                print("没有可用的交易日期")
                return
            
            # 从最近90天开始模拟
            start_index = max(0, len(trading_dates) - 90)
            trading_dates = trading_dates[start_index:]
            
            total_days = len(trading_dates)
            
            for i, date in enumerate(trading_dates):
                if not self.running:
                    break
                
                # 更新当前日期索引
                self.current_date_index = i
                
                # 计算进度
                progress = int((i / total_days) * 100)
                
                # 执行当天的交易逻辑
                self._process_trading_day(date)
                
                # 更新权益曲线
                self.equity_curve.append(self.calculate_equity())
                
                # 计算指标
                metrics = self._calculate_metrics()
                
                # 生成图表
                self._generate_charts()
                
                # 调用回调函数
                if self.update_callback:
                    self.update_callback(progress, date, metrics, self.trades)
                
                # 暂停一下，模拟实时执行
                time.sleep(1)
            
            # 执行完成后，设置进度为100%
            if self.running and self.update_callback:
                self.update_callback(100, trading_dates[-1], self._calculate_metrics(), self.trades)
            
            print("执行系统运行完成")
        except Exception as e:
            print(f"执行系统运行出错: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.running = False
    
    def _process_trading_day(self, date):
        """处理单个交易日"""
        try:
            # 获取所有股票对的价格
            pair_prices = {}
            for i, pair in enumerate(self.strategy.pairs):
                stock1_code, stock2_code = pair
                
                # 获取价格
                stock1_price = self.data_loader.get_price(stock1_code, date)
                stock2_price = self.data_loader.get_price(stock2_code, date)
                
                if stock1_price is None or stock2_price is None:
                    print(f"警告: 无法获取股票对 {stock1_code}/{stock2_code} 在 {date} 的价格")
                    continue
                
                pair_prices[i] = {
                    'stock1_code': stock1_code,
                    'stock2_code': stock2_code,
                    'stock1_price': stock1_price,
                    'stock2_price': stock2_price
                }
            
            # 检查是否有持仓需要平仓
            for pair_id in list(self.positions.keys()):
                position = self.positions[pair_id]
                
                # 获取当前价格
                stock1_code = position['stock1_code']
                stock2_code = position['stock2_code']
                current_stock1_price = self.data_loader.get_price(stock1_code, date)
                current_stock2_price = self.data_loader.get_price(stock2_code, date)
                
                if current_stock1_price is None or current_stock2_price is None:
                    print(f"警告: 无法获取持仓股票 {stock1_code}/{stock2_code} 在 {date} 的价格")
                    continue
                
                # 计算当前价差
                if position['type'] == 'long_short':
                    # 做多stock1，做空stock2
                    entry_ratio = position['stock1_price'] / position['stock2_price']
                    current_ratio = current_stock1_price / current_stock2_price
                    
                    # 计算收益
                    pnl = (current_stock1_price - position['stock1_price']) - (current_stock2_price - position['stock2_price']) * entry_ratio
                    pnl_pct = pnl / (position['stock1_price'] + position['stock2_price'] * entry_ratio)
                    
                else:
                    # 做空stock1，做多stock2
                    entry_ratio = position['stock2_price'] / position['stock1_price']
                    current_ratio = current_stock2_price / current_stock1_price
                    
                    # 计算收益
                    pnl = (current_stock2_price - position['stock2_price']) - (current_stock1_price - position['stock1_price']) * entry_ratio
                    pnl_pct = pnl / (position['stock2_price'] + position['stock1_price'] * entry_ratio)
                
                # 检查是否需要平仓
                close_signal = False
                close_reason = ''
                
                # 止损
                if pnl_pct < -0.05:  # 5%止损
                    close_signal = True
                    close_reason = '止损'
                
                # 止盈
                elif pnl_pct > 0.1:  # 10%止盈
                    close_signal = True
                    close_reason = '止盈'
                
                # 均值回归
                elif (position['type'] == 'long_short' and current_ratio < entry_ratio * 0.95) or \
                     (position['type'] == 'short_long' and current_ratio > entry_ratio * 1.05):
                    close_signal = True
                    close_reason = '均值回归'
                
                # 如果需要平仓
                if close_signal:
                    # 创建平仓信号
                    close_signal = {
                        'action': 'close',
                        'pair_id': pair_id,
                        'stock1_code': stock1_code,
                        'stock2_code': stock2_code,
                        'stock1_price': current_stock1_price,
                        'stock2_price': current_stock2_price,
                        'reason': close_reason
                    }
                    
                    # 执行平仓
                    self._execute_trade(close_signal, date)
            
            # 检查是否有新的交易信号
            for pair_id, prices in pair_prices.items():
                # 如果已经有持仓，跳过
                if pair_id in self.positions:
                    continue
                
                # 获取价格
                stock1_code = prices['stock1_code']
                stock2_code = prices['stock2_code']
                stock1_price = prices['stock1_price']
                stock2_price = prices['stock2_price']
                
                # 计算价格比率
                price_ratio = stock1_price / stock2_price
                
                # 简单策略：如果比率偏离均值，开仓
                # 这里使用固定的阈值，实际应该基于历史数据计算
                if price_ratio > 1.1:  # 比率过高，做空stock1，做多stock2
                    signal = {
                        'action': 'open',
                        'pair_id': pair_id,
                        'stock1_code': stock1_code,
                        'stock2_code': stock2_code,
                        'stock1_price': stock1_price,
                        'stock2_price': stock2_price,
                        'position_type': 'short_long'
                    }
                    self._execute_trade(signal, date)
                    
                elif price_ratio < 0.9:  # 比率过低，做多stock1，做空stock2
                    signal = {
                        'action': 'open',
                        'pair_id': pair_id,
                        'stock1_code': stock1_code,
                        'stock2_code': stock2_code,
                        'stock1_price': stock1_price,
                        'stock2_price': stock2_price,
                        'position_type': 'long_short'
                    }
                    self._execute_trade(signal, date)
        
        except Exception as e:
            print(f"处理交易日 {date} 时出错: {e}")
            import traceback
            traceback.print_exc()
    
    def _execute_trade(self, signal, date_str):
        """执行交易"""
        # 获取信号中的股票代码和价格
        stock1_code = signal['stock1_code']
        stock2_code = signal['stock2_code']
        stock1_price = signal['stock1_price']
        stock2_price = signal['stock2_price']
        pair_id = signal['pair_id']
        
        # 根据信号类型执行交易
        if signal['action'] == 'open':
            # 开仓交易
            position_type = signal['position_type']
            
            # 计算交易数量
            position_size = self.equity * 0.1  # 使用10%的资金开仓
            quantity = position_size / (stock1_price + stock2_price)
            
            # 计算交易成本
            commission = (stock1_price + stock2_price) * quantity * self.commission_rate
            
            # 更新资金
            self.equity -= commission
            
            # 记录持仓
            self.positions[pair_id] = {
                'stock1_code': stock1_code,
                'stock2_code': stock2_code,
                'stock1_price': stock1_price,
                'stock2_price': stock2_price,
                'quantity': quantity,
                'type': position_type,
                'open_time': date_str
            }
            
            # 记录交易
            trade = {
                'timestamp': date_str,
                'pair_id': pair_id,
                'action': 'open',
                'position_type': position_type,
                'long_code': stock1_code if position_type == 'long_short' else stock2_code,
                'short_code': stock2_code if position_type == 'long_short' else stock1_code,
                'open_price_long': stock1_price if position_type == 'long_short' else stock2_price,
                'open_price_short': stock2_price if position_type == 'long_short' else stock1_price,
                'close_price_long': 0.0,
                'close_price_short': 0.0,
                'quantity': quantity,
                'pnl': 0.0,
                'commission': commission,
                'status': 'open'
            }
            
            self.trades.append(trade)
            
            # 保存交易记录到数据库
            try:
                db.save_trade(trade)
            except Exception as e:
                print(f"保存交易记录到数据库时出错: {e}")
            
            print(f"开仓: {position_type} 对 {pair_id}, 数量: {quantity:.2f}, 成本: {commission:.2f}")
            
        elif signal['action'] == 'close':
            # 平仓交易
            if pair_id not in self.positions:
                print(f"警告: 尝试平仓不存在的持仓 {pair_id}")
                return
                
            position = self.positions[pair_id]
            position_type = position['type']
            quantity = position['quantity']
            
            # 计算盈亏
            if position_type == 'long_short':
                # 做多stock1，做空stock2
                entry_value = position['stock1_price'] - position['stock2_price']
                exit_value = stock1_price - stock2_price
                pnl = (exit_value - entry_value) * quantity
            else:
                # 做空stock1，做多stock2
                entry_value = position['stock2_price'] - position['stock1_price']
                exit_value = stock2_price - stock1_price
                pnl = (exit_value - entry_value) * quantity
            
            # 计算交易成本
            commission = (stock1_price + stock2_price) * quantity * self.commission_rate
            
            # 更新资金
            self.equity += pnl - commission
            
            # 更新交易记录
            for i, trade in enumerate(self.trades):
                if trade['pair_id'] == pair_id and trade['status'] == 'open':
                    self.trades[i]['close_price_long'] = stock1_price if position_type == 'long_short' else stock2_price
                    self.trades[i]['close_price_short'] = stock2_price if position_type == 'long_short' else stock1_price
                    self.trades[i]['pnl'] = pnl
                    self.trades[i]['commission'] += commission
                    self.trades[i]['status'] = 'closed'
                    self.trades[i]['close_time'] = date_str
                    
                    # 尝试更新数据库
                    try:
                        # 检查数据库模块是否有update_trade函数
                        if hasattr(db, 'update_trade'):
                            db.update_trade(self.trades[i])
                        else:
                            # 如果没有update_trade函数，使用save_trade函数
                            print("警告: 数据库模块没有update_trade函数，使用save_trade函数")
                            # 确保trade记录有id字段
                            if 'id' not in self.trades[i]:
                                # 查询数据库获取id
                                conn = db.get_db_connection()
                                cursor = conn.cursor()
                                cursor.execute(
                                    "SELECT id FROM trades WHERE pair_id = ? AND timestamp = ? AND action = ?",
                                    (pair_id, self.trades[i]['timestamp'], 'open')
                                )
                                result = cursor.fetchone()
                                if result:
                                    self.trades[i]['id'] = result[0]
                                conn.close()
                            
                            # 保存更新后的交易记录
                            db.save_trade(self.trades[i])
                    except Exception as e:
                        print(f"更新交易记录到数据库时出错: {e}")
                    break
            
            # 移除持仓
            del self.positions[pair_id]
            
            reason = signal.get('reason', '未知原因')
            print(f"平仓: 对 {pair_id}, 盈亏: {pnl:.2f}, 成本: {commission:.2f}, 原因: {reason}")
    
    def calculate_equity(self):
        """计算当前权益"""
        # 基础权益
        total_equity = self.equity
        
        # 加上未平仓的持仓价值
        for pair_id, position in self.positions.items():
            # 这里简化处理，实际应该考虑当前市场价格
            # 假设持仓价值不变
            pass
        
        return total_equity
    
    def _calculate_metrics(self):
        """计算绩效指标"""
        # 计算总收益率
        if len(self.equity_curve) > 1:
            total_return = (self.equity_curve[-1] - self.equity_curve[0]) / self.equity_curve[0]
        else:
            total_return = 0
        
        # 计算年化收益率（假设252个交易日）
        if len(self.equity_curve) > 1:
            days = len(self.equity_curve) - 1
            annual_return = total_return * (252 / days) if days > 0 else 0
        else:
            annual_return = 0
        
        # 计算最大回撤
        max_drawdown = 0
        peak = self.equity_curve[0]
        for equity in self.equity_curve:
            if equity > peak:
                peak = equity
            drawdown = (peak - equity) / peak if peak > 0 else 0
            max_drawdown = max(max_drawdown, drawdown)
        
        # 计算夏普比率
        if len(self.equity_curve) > 1:
            returns = [(self.equity_curve[i] - self.equity_curve[i-1]) / self.equity_curve[i-1] for i in range(1, len(self.equity_curve))]
            avg_return = sum(returns) / len(returns) if returns else 0
            std_return = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5 if returns else 0
            sharpe_ratio = (avg_return / std_return) * (252 ** 0.5) if std_return > 0 else 0
        else:
            sharpe_ratio = 0
        
        # 计算胜率和盈亏比
        closed_trades = [t for t in self.trades if t['status'] == 'closed']
        winning_trades = [t for t in closed_trades if t['pnl'] > 0]
        losing_trades = [t for t in closed_trades if t['pnl'] <= 0]
        
        win_rate = len(winning_trades) / len(closed_trades) if closed_trades else 0
        
        avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t['pnl'] for t in losing_trades) / len(losing_trades) if losing_trades else 0
        profit_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
        
        return {
            'total_return': total_return,
            'annual_return': annual_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'win_rate': win_rate,
            'profit_loss_ratio': profit_loss_ratio,
            'total_trades': len(closed_trades)
        }
    
    def _generate_charts(self):
        """生成图表"""
        try:
            # 创建图表目录
            static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
            if not os.path.exists(static_dir):
                os.makedirs(static_dir)
            
            # 生成权益曲线图
            plt.figure(figsize=(10, 6))
            plt.plot(self.equity_curve)
            plt.title('策略权益曲线')
            plt.xlabel('交易日')
            plt.ylabel('权益')
            plt.grid(True)
            plt.savefig(os.path.join(static_dir, 'execution_results.png'))
            plt.close()
            
        except Exception as e:
            print(f"生成图表时出错: {e}")
    
    def _calculate_performance_metrics(self):
        """计算绩效指标"""
        metrics = self._calculate_metrics()
        
        # 添加当前日期和进度
        if self.current_date_index < len(self.trading_days):
            current_date = self.trading_days[self.current_date_index] if self.trading_days else "未知"
        else:
            current_date = self.trading_days[-1] if self.trading_days else "未知"
        
        progress = int((self.current_date_index / len(self.trading_days) * 100)) if self.trading_days else 0
        
        metrics['current_date'] = current_date
        metrics['progress'] = progress
        
        return metrics
    
    def get_status(self):
        """获取执行系统状态"""
        metrics = self._calculate_performance_metrics()
        
        return {
            'running': self.running,
            'current_date': metrics['current_date'],
            'progress': metrics['progress'],
            'metrics': {
                'total_return': f"{metrics['total_return']:.2%}",
                'annual_return': f"{metrics['annual_return']:.2%}",
                'max_drawdown': f"{metrics['max_drawdown']:.2%}",
                'sharpe_ratio': f"{metrics['sharpe_ratio']:.2f}",
                'win_rate': f"{metrics['win_rate']:.2%}",
                'profit_loss_ratio': f"{metrics['profit_loss_ratio']:.2f}",
                'total_trades': metrics['total_trades']
            },
            'chart_url': '/static/execution_results.png',
            'positions': len(self.positions),
            'equity': self.equity_curve[-1] if len(self.equity_curve) > 0 else self.initial_capital
        }