import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib
# 设置Matplotlib使用非交互式后端，避免线程问题
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from strategy import PairTradingStrategy
from config.config import BACKTEST_CONFIG
import database as db

class Backtest:
    def __init__(self, strategy_class=PairTradingStrategy, config=None):
        self.config = config or BACKTEST_CONFIG
        self.initial_capital = self.config['initial_capital']
        self.start_date = self.config['start_date']
        self.end_date = self.config['end_date']
        self.commission_rate = self.config['commission_rate']
        self.slippage = self.config['slippage']
        
        self.strategy = strategy_class()
        self.equity = self.initial_capital
        self.positions = {}
        self.trades = []
        self.daily_returns = []
        self.daily_equity = []
        
        # 添加进度回调函数
        self.progress_callback = None
    
    def run(self):
        """运行回测"""
        
        print("开始回测...")
        
        # 报告进度：开始加载数据
        if hasattr(self, 'progress_callback') and self.progress_callback:
            self.progress_callback(5, "加载历史数据...")
        
        # 加载历史数据
        self.load_data()
        
        # 报告进度：开始计算股票对统计数据
        if hasattr(self, 'progress_callback') and self.progress_callback:
            self.progress_callback(20, "计算股票对统计数据...")
        
        # 计算股票对的统计数据
        self.strategy.calculate_pair_stats(self.data)
        
        # 初始化回测结果
        self.equity_curve = [self.initial_capital]
        self.returns = []
        self.drawdowns = []
        self.positions = {} 
        self.trades = []

        # 保存回测配置信息
        backtest_info = {
            'start_date': self.start_date,
            'end_date': self.end_date,
            'initial_capital': self.initial_capital,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        db.save_backtest_info(backtest_info)
                
        # 报告进度：开始回测
        if hasattr(self, 'progress_callback') and self.progress_callback:
            self.progress_callback(30, "开始回测交易...")
        
        # 获取所有交易日
        trading_days = sorted(self.data.keys())
        total_days = len(trading_days)
        
        # 遍历每个交易日
        for i, date_str in enumerate(trading_days):
            # 生成交易信号 - 使用我们自己的方法而不是策略的方法
            signals = self.generate_signals_for_date(date_str)
            
            # 调试信息：打印生成的信号
            if signals:
                print(f"日期 {date_str} 生成了 {len(signals)} 个交易信号")
                for signal in signals:
                    print(f"  信号详情: {signal}")
            
            # 执行交易
            for signal in signals:
                # 确保信号包含必要的字段
                if 'action' not in signal or 'pair_id' not in signal:
                    print(f"警告: 信号缺少必要字段: {signal}")
                    continue
                    
                # 执行交易
                self.execute_trade(signal, date_str)
            
            # 更新持仓价值
            self.update_portfolio_value(date_str)
            
            # 计算回报和回撤
            self.calculate_returns_and_drawdowns()
            
            # 保存每日绩效
            self.save_daily_performance(date_str)
            
            # 更新进度
            if hasattr(self, 'progress_callback') and self.progress_callback and total_days > 0:
                progress = 30 + int(60 * (i + 1) / total_days)  # 30%-90%的进度用于回测
                self.progress_callback(progress, f"回测进度: {i+1}/{total_days} 天")
        
        # 报告进度：计算回测指标
        if hasattr(self, 'progress_callback') and self.progress_callback:
            self.progress_callback(90, "计算回测指标...")
        
        # 计算回测指标
        self.calculate_metrics()
        
        # 报告进度：回测完成
        if hasattr(self, 'progress_callback') and self.progress_callback:
            self.progress_callback(95, "生成回测图表...")
        
        # 绘制回测结果图表
        self.plot_results()
        
        # 报告进度：全部完成
        if hasattr(self, 'progress_callback') and self.progress_callback:
            self.progress_callback(100, "回测完成", "completed")
        
        print("回测完成")
        return {
            'equity_curve': self.equity_curve,
            'returns': self.returns,
            'drawdowns': self.drawdowns,
            'trades': self.trades,
            'metrics': self.metrics
        }
    
    def generate_signals_for_date(self, date_str):
        """为特定日期生成交易信号"""
        signals = []
        
        # 首先检查是否需要平仓现有持仓
        for pair_id, position in list(self.positions.items()):
            stock1_code = position['stock1_code']
            stock2_code = position['stock2_code']
            
            # 获取当前价格
            if date_str not in self.data or stock1_code not in self.data[date_str] or stock2_code not in self.data[date_str]:
                continue
                
            stock1_price = self.data[date_str][stock1_code]['close']
            stock2_price = self.data[date_str][stock2_code]['close']
            
            # 计算当前z-score
            # 获取历史数据
            lookback_start = (datetime.strptime(date_str, '%Y%m%d') - timedelta(days=self.strategy.lookback_period * 2)).strftime('%Y%m%d')
            stock1_data = db.get_stock_data(stock1_code, lookback_start, date_str)
            stock2_data = db.get_stock_data(stock2_code, lookback_start, date_str)
            
            if stock1_data.empty or stock2_data.empty or len(stock1_data) < self.strategy.lookback_period or len(stock2_data) < self.strategy.lookback_period:
                continue
                
            # 计算z-score
            z_score, _, _ = self.strategy.calculate_spread(stock1_data, stock2_data)
            
            if z_score is None:
                continue
                
            # 检查是否应该平仓
            # 添加强制平仓条件：持仓超过一定天数
            days_held = (datetime.strptime(date_str, '%Y%m%d') - datetime.strptime(position['open_time'], '%Y%m%d')).days
            max_hold_days = 20  # 设置最大持仓天数
            
            if days_held >= max_hold_days:
                # 强制平仓
                signals.append({
                    'pair_id': pair_id,
                    'stock1_code': stock1_code,
                    'stock2_code': stock2_code,
                    'stock1_price': stock1_price,
                    'stock2_price': stock2_price,
                    'z_score': z_score,
                    'action': 'close',
                    'position_type': position['type'],
                    'timestamp': date_str
                })
                print(f"生成强制平仓信号 - 对: {pair_id}, 持仓天数: {days_held}")
                continue
                
            # 根据z-score平仓
            if position['type'] == 'long_short' and z_score > -0.5:  # 修改平仓阈值，使其更容易触发
                # 做多stock1/做空stock2的仓位，当z-score回归到阈值以上时平仓
                signals.append({
                    'pair_id': pair_id,
                    'stock1_code': stock1_code,
                    'stock2_code': stock2_code,
                    'stock1_price': stock1_price,
                    'stock2_price': stock2_price,
                    'z_score': z_score,
                    'action': 'close',
                    'position_type': position['type'],
                    'timestamp': date_str
                })
                print(f"生成平仓信号 - 对: {pair_id}, z-score={z_score:.4f}")
            
            elif position['type'] == 'short_long' and z_score < 0.5:  # 修改平仓阈值，使其更容易触发
                # 做空stock1/做多stock2的仓位，当z-score回归到阈值以下时平仓
                signals.append({
                    'pair_id': pair_id,
                    'stock1_code': stock1_code,
                    'stock2_code': stock2_code,
                    'stock1_price': stock1_price,
                    'stock2_price': stock2_price,
                    'z_score': z_score,
                    'action': 'close',
                    'position_type': position['type'],
                    'timestamp': date_str
                })
                print(f"生成平仓信号 - 对: {pair_id}, z-score={z_score:.4f}")
        
        # 然后检查是否有新的开仓机会
        for pair in self.strategy.pairs:
            stock1_code, stock2_code = pair
            pair_id = f"{stock1_code}_{stock2_code}"
            
            # 如果已经有持仓，跳过
            if pair_id in self.positions:
                continue
                
            # 获取历史数据
            lookback_start = (datetime.strptime(date_str, '%Y%m%d') - timedelta(days=self.strategy.lookback_period * 2)).strftime('%Y%m%d')
            stock1_data = db.get_stock_data(stock1_code, lookback_start, date_str)
            stock2_data = db.get_stock_data(stock2_code, lookback_start, date_str)
            
            if stock1_data.empty or stock2_data.empty or len(stock1_data) < self.strategy.lookback_period or len(stock2_data) < self.strategy.lookback_period:
                continue
            
            # 计算价差
            z_score, price1, price2 = self.strategy.calculate_spread(stock1_data, stock2_data)
            
            if z_score is None:
                continue
            
            # 生成信号
            signal = {
                'pair_id': pair_id,
                'stock1_code': stock1_code,
                'stock2_code': stock2_code,
                'stock1_price': price1,
                'stock2_price': price2,
                'z_score': z_score,
                'timestamp': date_str
            }
            
            # 检查是否应该开仓
            if z_score > self.strategy.entry_threshold:
                # 做空stock1，做多stock2
                signal['action'] = 'open'
                signal['position_type'] = 'short_long'
                signals.append(signal)
                print(f"生成开仓信号 - 对: {pair_id}, 类型: short_long, z-score={z_score:.4f}")
            
            elif z_score < -self.strategy.entry_threshold:
                # 做多stock1，做空stock2
                signal['action'] = 'open'
                signal['position_type'] = 'long_short'
                signals.append(signal)
                print(f"生成开仓信号 - 对: {pair_id}, 类型: long_short, z-score={z_score:.4f}")
        
        return signals
    
    def execute_trade(self, signal, date_str):
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
                'long_price': stock1_price if position_type == 'long_short' else stock2_price,
                'short_price': stock2_price if position_type == 'long_short' else stock1_price,
                'quantity': quantity,
                'commission': commission,
                'status': 'open',
                # 添加TCA所需的字段
                'open_price_long': stock1_price if position_type == 'long_short' else stock2_price,
                'open_price_short': stock2_price if position_type == 'long_short' else stock1_price,
                'close_price_long': 0.0,  # 开仓时收盘价为0
                'close_price_short': 0.0  # 开仓时收盘价为0
            }
            
            self.trades.append(trade)
            
            # 保存交易记录到数据库
            db.save_trade(trade)
            
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
            
            # 记录交易
            trade = {
                'timestamp': date_str,
                'pair_id': pair_id,
                'action': 'close',
                'position_type': position_type,
                'long_code': position['stock1_code'] if position_type == 'long_short' else position['stock2_code'],
                'short_code': position['stock2_code'] if position_type == 'long_short' else position['stock1_code'],
                'long_price': stock1_price if position_type == 'long_short' else stock2_price,
                'short_price': stock2_price if position_type == 'long_short' else stock1_price,
                'quantity': quantity,
                'pnl': pnl,
                'commission': commission,
                'net_pnl': pnl - commission,
                'status': 'closed',
                # 添加TCA所需的字段
                'open_price_long': position['stock1_price'] if position_type == 'long_short' else position['stock2_price'],
                'open_price_short': position['stock2_price'] if position_type == 'long_short' else position['stock1_price'],
                'close_price_long': stock1_price if position_type == 'long_short' else stock2_price,
                'close_price_short': stock2_price if position_type == 'long_short' else stock1_price
            }
            
            self.trades.append(trade)
            
            # 保存交易记录到数据库
            db.save_trade(trade)
            
            # 删除持仓
            del self.positions[pair_id]
            
            print(f"平仓: {position_type} 对 {pair_id}, 数量: {quantity:.2f}, 盈亏: {pnl:.2f}, 成本: {commission:.2f}")
    
    def update_portfolio_value(self, date_str):
        """更新投资组合价值"""
        # 获取当前日期的市场数据
        current_data = self.data[date_str]
        
        # 计算持仓价值
        portfolio_value = self.equity
        
        # 遍历所有持仓
        for pair_id, position in self.positions.items():
            stock1_code = position['stock1_code']
            stock2_code = position['stock2_code']
            
            # 检查股票数据是否存在
            if stock1_code not in current_data or stock2_code not in current_data:
                continue
            
            # 获取当前价格
            stock1_price = current_data[stock1_code]['close']
            stock2_price = current_data[stock2_code]['close']
            
            # 计算持仓价值变化
            if position['type'] == 'long_short':  # 修正：使用正确的持仓类型
                # 做多stock1，做空stock2
                stock1_value = position['quantity'] * stock1_price
                stock2_value = position['quantity'] * stock2_price
                position_value = stock1_value - stock2_value
                
                # 计算初始价值
                initial_stock1_value = position['quantity'] * position['stock1_price']
                initial_stock2_value = position['quantity'] * position['stock2_price']
                initial_position_value = initial_stock1_value - initial_stock2_value
                
                # 计算盈亏
                pnl = position_value - initial_position_value
                
            else:  # position['type'] == 'short_long'
                # 做空stock1，做多stock2
                stock1_value = position['quantity'] * stock1_price
                stock2_value = position['quantity'] * stock2_price
                position_value = stock2_value - stock1_value
                
                # 计算初始价值
                initial_stock1_value = position['quantity'] * position['stock1_price']
                initial_stock2_value = position['quantity'] * position['stock2_price']
                initial_position_value = initial_stock2_value - initial_stock1_value
                
                # 计算盈亏
                pnl = position_value - initial_position_value
            
            # 更新持仓的当前价值
            position['current_value'] = position_value
            position['pnl'] = pnl
            
            # 更新总资产
            portfolio_value += pnl
        
        # 更新权益曲线
        self.equity = portfolio_value
        self.equity_curve.append(portfolio_value)
    
    def calculate_returns_and_drawdowns(self):
        """计算回报和回撤"""
        """计算回报和回撤"""
        # 计算每日回报
        if len(self.equity_curve) > 1:
            daily_return = (self.equity_curve[-1] / self.equity_curve[-2]) - 1
            self.returns.append(daily_return)
            
            # 计算累计回报
            cumulative_return = (self.equity_curve[-1] / self.initial_capital) - 1
            
            # 计算最大回撤
            peak = max(self.equity_curve)
            drawdown = (peak - self.equity_curve[-1]) / peak if peak > 0 else 0
            self.drawdowns.append(drawdown)
    
    def save_daily_performance(self, date_str):
        """保存每日绩效数据"""
        # 计算夏普比率
        if len(self.returns) > 0:
            avg_return = sum(self.returns) / len(self.returns)
            std_return = np.std(self.returns) if len(self.returns) > 1 else 0
            sharpe = avg_return / std_return if std_return > 0 else 0
        else:
            sharpe = 0
        
        # 计算最大回撤
        max_drawdown = max(self.drawdowns) if self.drawdowns else 0
        
        # 保存到数据库
        performance_data = {
            'date': date_str,
            'equity': self.equity,
            'return': self.returns[-1] if self.returns else 0,  # 这里使用'return'作为键
            'drawdown': max_drawdown,
            'sharpe': sharpe
        }
        
        db.save_performance_data(performance_data)

    def calculate_metrics(self):
        """计算回测指标"""
        # 计算总回报率
        if len(self.equity_curve) > 1:
            total_return = self.equity_curve[-1] / self.equity_curve[0] - 1
        else:
            total_return = 0
        
        # 计算年化回报率
        days = len(self.equity_curve)
        if days > 1:
            # 使用abs确保不会出现负数的情况，然后根据原始值的符号添加符号
            annual_return_value = (self.equity_curve[-1] / self.equity_curve[0]) ** (252 / days) - 1
            if isinstance(annual_return_value, complex):
                # 如果结果是复数，则取实部
                annual_return = annual_return_value.real
            else:
                annual_return = annual_return_value
        else:
            annual_return = 0
        
        # 计算夏普比率
        if len(self.returns) > 1:
            daily_returns = np.array(self.returns)
            sharpe_ratio = np.mean(daily_returns) / np.std(daily_returns) * np.sqrt(252) if np.std(daily_returns) > 0 else 0
        else:
            sharpe_ratio = 0
        
        # 计算最大回撤
        max_drawdown = max(self.drawdowns) if self.drawdowns else 0
        
        # 计算胜率和盈亏比
        win_trades = [t for t in self.trades if t.get('pnl', 0) > 0]
        loss_trades = [t for t in self.trades if t.get('pnl', 0) < 0]
        
        # 修复：总交易次数应该是self.trades的长度，而不是胜利和亏损交易的总和
        # 因为可能有pnl为0的交易
        total_trades = len(self.trades)
        win_rate = len(win_trades) / total_trades if total_trades > 0 else 0
        
        avg_win = sum(t.get('pnl', 0) for t in win_trades) / len(win_trades) if win_trades else 0
        avg_loss = sum(t.get('pnl', 0) for t in loss_trades) / len(loss_trades) if loss_trades else 0
        
        profit_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
        
        # 打印指标
        print(f"总回报率: {total_return:.2%}")
        print(f"年化回报率: {annual_return:.2f}") 
        print(f"夏普比率: {sharpe_ratio:.2f}")
        print(f"最大回撤: {max_drawdown:.2%}")
        print(f"胜率: {win_rate:.2%}")
        print(f"盈亏比: {profit_loss_ratio:.2f}")
        print(f"总交易次数: {total_trades}")
        
        # 存储指标
        self.metrics = {
            'total_return': total_return,
            'annual_return': annual_return,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'profit_loss_ratio': profit_loss_ratio,
            'total_trades': total_trades
        }
        
        return self.metrics

    def load_data(self):
        """加载回测数据"""
        self.data = {}
        
        # 获取回测日期范围
        start_date = self.start_date
        end_date = self.end_date
        
        print(f"加载回测数据: {start_date} 至 {end_date}")
        
        # 获取所有股票代码
        stock_codes = []
        for pair in self.strategy.pairs:
            stock_codes.extend(pair)
        
        # 去重
        stock_codes = list(set(stock_codes))
        
        # 加载每只股票的数据
        stock_data = {}
        for code in stock_codes:
            # 标准化股票代码
            std_code = self.strategy.standardize_stock_code(code)
            print(f"加载股票 {code} (标准化为 {std_code}) 的数据")
            
            # 尝试使用标准化的代码获取数据
            data = db.get_stock_data(std_code, start_date, end_date)
            
            # 如果获取不到，尝试使用原始代码
            if data.empty:
                print(f"使用标准化代码 {std_code} 未找到数据，尝试使用原始代码 {code}")
                data = db.get_stock_data(code, start_date, end_date)
            
            if data.empty:
                print(f"警告: 无法获取股票 {code} 的数据")
                continue
            
            # 打印前几行数据用于调试
            print(f"股票 {code} 的前3行数据:")
            print(data.head(3))
            
            stock_data[code] = data
        
        # 确定共同的交易日
        common_dates = None
        for code, data in stock_data.items():
            dates = set(data['date'].unique())
            if common_dates is None:
                common_dates = dates
            else:
                common_dates = common_dates.intersection(dates)
        
        if not common_dates or len(common_dates) == 0:
            print("错误: 没有找到共同的交易日")
            return
        
        # 即使数据不足3年，也继续进行回测
        print(f"找到 {len(common_dates)} 个共同交易日")
        
        # 按日期组织数据
        for date in common_dates:
            date_data = {}
            for code, data in stock_data.items():
                date_df = data[data['date'] == date]
                if not date_df.empty:
                    date_data[code] = date_df.iloc[0].to_dict()
            
            if date_data:
                self.data[date] = date_data
        
        # 打印第一个日期的数据结构用于调试
        if self.data:
            first_date = sorted(self.data.keys())[0]
            print(f"第一个日期 {first_date} 的数据结构:")
            for code in self.data[first_date]:
                print(f"  - {code}")
    
    def plot_results(self):
        """绘制回测结果图表"""
        if not hasattr(self, 'equity_curve') or len(self.equity_curve) == 0:
            print("没有回测数据可供绘图")
            return
        
        # 设置中文字体
        import matplotlib.font_manager as fm
        # 尝试使用系统中常见的中文字体
        try:
            # 尝试使用微软雅黑
            plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS', 'sans-serif']
            plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
        except:
            print("警告: 无法设置中文字体，图表中的中文可能无法正确显示")
        
        # 创建图表
        fig, axes = plt.subplots(3, 1, figsize=(12, 18), gridspec_kw={'height_ratios': [3, 1, 1]})
        
        # 绘制权益曲线
        dates = list(sorted(self.data.keys()))
        
        # 确保日期和权益曲线长度一致
        print(f"日期数量: {len(dates)}, 权益曲线数据点: {len(self.equity_curve)}")
        
        # 如果权益曲线比日期多一个点（初始资金），则去掉第一个点
        equity_curve_plot = self.equity_curve
        if len(self.equity_curve) == len(dates) + 1:
            print("权益曲线比日期多一个点，去掉第一个点（初始资金）")
            equity_curve_plot = self.equity_curve[1:]
        
        # 如果权益曲线比日期少，则截取日期
        if len(equity_curve_plot) < len(dates):
            print(f"权益曲线比日期少，截取日期列表 ({len(dates)} -> {len(equity_curve_plot)})")
            dates = dates[:len(equity_curve_plot)]
        
        # 转换日期格式
        formatted_dates = [datetime.strptime(date, '%Y%m%d') for date in dates]
        
        # 确保长度一致
        if len(formatted_dates) != len(equity_curve_plot):
            print(f"警告: 日期和权益曲线长度不一致: {len(formatted_dates)} vs {len(equity_curve_plot)}")
            # 取两者中较短的长度
            min_len = min(len(formatted_dates), len(equity_curve_plot))
            formatted_dates = formatted_dates[:min_len]
            equity_curve_plot = equity_curve_plot[:min_len]
        
        # 绘制权益曲线
        axes[0].plot(formatted_dates, equity_curve_plot, label='权益曲线')
        axes[0].set_title('回测权益曲线')
        axes[0].set_ylabel('资金')
        axes[0].legend()
        axes[0].grid(True)
        
        # 绘制每日回报
        if self.returns and len(formatted_dates) == len(self.returns):
            axes[1].plot(formatted_dates, self.returns, label='每日回报', color='green')
            axes[1].axhline(y=0, color='r', linestyle='-', alpha=0.3)
            axes[1].set_title('每日回报')
            axes[1].set_ylabel('回报率')
            axes[1].legend()
            axes[1].grid(True)
        elif self.returns:
            # 如果长度不一致，截取较短的部分
            min_len = min(len(formatted_dates), len(self.returns))
            axes[1].plot(formatted_dates[:min_len], self.returns[:min_len], label='每日回报', color='green')
            axes[1].axhline(y=0, color='r', linestyle='-', alpha=0.3)
            axes[1].set_title('每日回报')
            axes[1].set_ylabel('回报率')
            axes[1].legend()
            axes[1].grid(True)
        
        # 绘制回撤
        if self.drawdowns and len(formatted_dates) == len(self.drawdowns):
            axes[2].fill_between(formatted_dates, self.drawdowns, 0, color='red', alpha=0.3, label='回撤')
            axes[2].set_title('回撤')
            axes[2].set_ylabel('回撤率')
            axes[2].set_xlabel('日期')
            axes[2].legend()
            axes[2].grid(True)
        elif self.drawdowns:
            # 如果长度不一致，截取较短的部分
            min_len = min(len(formatted_dates), len(self.drawdowns))
            axes[2].fill_between(formatted_dates[:min_len], self.drawdowns[:min_len], 0, color='red', alpha=0.3, label='回撤')
            axes[2].set_title('回撤')
            axes[2].set_ylabel('回撤率')
            axes[2].set_xlabel('日期')
            axes[2].legend()
            axes[2].grid(True)
        
        # 调整布局
        plt.tight_layout()
        
        # 保存图表
        plt.savefig('d:\\硕士\\MFE5210 Algorithmic Trading Basics\\hedge_trading_system\\static\\backtest_results.png')
        
        # 关闭图表
        plt.close()
        
        return 'static/backtest_results.png'