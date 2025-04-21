import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib
# 设置Matplotlib使用非交互式后端，避免线程问题
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import database as db
# 添加中文字体支持
from matplotlib import font_manager
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

class TCA:
    def __init__(self, start_date=None, end_date=None):
        """初始化交易成本分析"""
        self.start_date = start_date
        self.end_date = end_date
        self.trades = None
        self.progress_callback = None
    
    def run(self):
        """运行交易成本分析"""
        print("开始交易成本分析...")
        
        # 报告进度：开始加载数据
        if hasattr(self, 'progress_callback') and self.progress_callback:
            self.progress_callback(10, "加载交易数据...")
        
        # 加载交易数据
        self.load_trades()
        
        if self.trades is None or len(self.trades) == 0:
            print("没有找到交易数据")
            return {
                'status': 'error',
                'message': '没有找到交易数据',
                'metrics': {
                    'total_trades': 0,
                    'total_volume': 0,
                    'total_commission': 0,
                    'avg_slippage': 0,
                    'implementation_shortfall': 0,
                    'market_impact': 0,
                    'timing_cost': 0
                },
                'trade_details': []
            }
        
        # 报告进度：开始分析
        if hasattr(self, 'progress_callback') and self.progress_callback:
            self.progress_callback(30, "分析交易成本...")
        
        # 分析交易成本
        metrics = self.analyze_trades()
        
        # 报告进度：生成图表
        if hasattr(self, 'progress_callback') and self.progress_callback:
            self.progress_callback(70, "生成图表...")
        
        # 生成图表
        chart_path = self.plot_cost_analysis()
        
        # 获取成本指标
        cost_metrics = self.get_cost_metrics()
        
        # 合并所有指标
        all_metrics = {**metrics, **cost_metrics}

        # 处理NaN值，将其转换为0
        for key, value in all_metrics.items():
            if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
                all_metrics[key] = 0
        
        # 处理交易详情中的NaN值
        if not self.trades.empty:
            trade_details = self.trades.replace({np.nan: 0, np.inf: 0, -np.inf: 0}).to_dict('records')
        else:
            trade_details = []

        # 报告进度：完成
        if hasattr(self, 'progress_callback') and self.progress_callback:
            self.progress_callback(100, "分析完成", "completed")
        
        print("交易成本分析完成")
        return {
            'status': 'success',
            'message': '交易成本分析完成',
            'metrics': all_metrics,
            'trade_details': self.trades.to_dict('records') if not self.trades.empty else [],
            'chart_url': chart_path
        }
    
    def load_trades(self):
        """加载交易数据"""
        print(f"加载交易数据: {self.start_date} 至 {self.end_date}")
        
        # 从数据库获取交易记录
        trades_df = db.get_trades(self.start_date, self.end_date)
        
        if trades_df.empty:
            print("警告: 没有找到交易数据")
            self.trades = pd.DataFrame()
            return
        
        # 确保时间戳列是日期时间格式
        if 'timestamp' in trades_df.columns:
            trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'])
        
        # 打印前几行数据用于调试
        print(f"加载了 {len(trades_df)} 条交易记录")
        print("交易记录前3行:")
        print(trades_df.head(3))
        
        self.trades = trades_df
    
    def analyze_trades(self):
        """分析交易成本"""
        if self.trades.empty:
            return {
                'total_trades': 0,
                'total_volume': 0,
                'total_commission': 0,
                'avg_slippage': 0,
                'implementation_shortfall': 0,
                'market_impact': 0,
                'timing_cost': 0
            }
        
        # 检查并转换列名
        # 如果有long_price和short_price列，但没有open_price_long等列，进行映射
        if ('long_price' in self.trades.columns and 'short_price' in self.trades.columns and 
            not all(col in self.trades.columns for col in ['open_price_long', 'open_price_short', 'close_price_long', 'close_price_short'])):
            
            print("检测到旧格式交易数据，进行列映射转换...")
            
            # 根据action列创建开盘价和收盘价
            self.trades['open_price_long'] = self.trades['long_price']
            self.trades['open_price_short'] = self.trades['short_price']
            self.trades['close_price_long'] = self.trades['long_price']
            self.trades['close_price_short'] = self.trades['short_price']
        
        # 确保必要的列存在
        required_columns = ['quantity', 'open_price_long', 'open_price_short', 'close_price_long', 'close_price_short']
        for col in required_columns:
            if col not in self.trades.columns:
                print(f"警告: 交易数据缺少必要的列 '{col}'")
                # 创建默认列
                if col.startswith('open_price') or col.startswith('close_price'):
                    self.trades[col] = 0.0
                elif col == 'quantity':
                    self.trades[col] = 1.0
        
        # 如果数据库中已有计算好的成本数据，直接使用
        if all(col in self.trades.columns for col in ['volume', 'commission', 'slippage', 'market_impact', 'timing_cost', 'total_cost']):
            print("使用数据库中已有的成本数据")
        else:
            print("计算交易成本数据")
            # 计算交易量 - 使用开盘价和收盘价的平均值
            self.trades['long_price'] = (self.trades['open_price_long'] + self.trades['close_price_long']) / 2
            self.trades['short_price'] = (self.trades['open_price_short'] + self.trades['close_price_short']) / 2
            self.trades['volume'] = self.trades['quantity'] * (self.trades['long_price'] + self.trades['short_price'])
            
            # 计算佣金（假设为交易量的0.03%）
            if 'commission' not in self.trades.columns:
                self.trades['commission'] = self.trades['volume'] * 0.0003
            
            # 计算滑点（假设为交易价格的0.01%）
            if 'slippage' not in self.trades.columns:
                self.trades['slippage'] = self.trades['volume'] * 0.0001
            
            # 计算市场冲击（假设为交易量的平方根乘以一个系数）
            if 'market_impact' not in self.trades.columns:
                self.trades['market_impact'] = 0.1 * np.sqrt(self.trades['volume'] / 10000)
            
            # 计算时机成本（假设为随机值，实际应该比较执行价格与决策价格的差异）
            if 'timing_cost' not in self.trades.columns:
                np.random.seed(42)  # 设置随机种子以确保结果可重现
                self.trades['timing_cost'] = np.random.normal(0, 0.0005, len(self.trades)) * self.trades['volume']
            
            # 计算总交易成本
            if 'total_cost' not in self.trades.columns:
                self.trades['total_cost'] = self.trades['commission'] + self.trades['slippage'] + self.trades['market_impact'] + self.trades['timing_cost']
        
        # 计算交易成本占交易量的比例
        self.trades['cost_ratio'] = self.trades['total_cost'] / self.trades['volume'] * 100  # 转换为百分比
        
        # 计算实施缺口（总成本）
        self.trades['implementation_shortfall'] = self.trades['total_cost']
        
        # 汇总结果
        result = {
            'total_trades': len(self.trades),
            'total_volume': self.trades['volume'].sum(),
            'total_commission': self.trades['commission'].sum(),
            'avg_slippage': self.trades['slippage'].mean(),
            'implementation_shortfall': self.trades['implementation_shortfall'].sum(),
            'market_impact': self.trades['market_impact'].sum(),
            'timing_cost': self.trades['timing_cost'].sum()
        }
        
        return result
    
    def plot_cost_analysis(self, save_path='static/tca_analysis.png'):
        """绘制交易成本分析图表"""
        if self.trades.empty:
            print("没有交易数据可供分析")
            return save_path
        
        # 确保时间戳列是日期时间格式
        if 'timestamp' not in self.trades.columns:
            print("警告: 交易数据缺少时间戳列")
            self.trades['timestamp'] = pd.to_datetime('today')
        elif not pd.api.types.is_datetime64_any_dtype(self.trades['timestamp']):
            self.trades['timestamp'] = pd.to_datetime(self.trades['timestamp'])
        
        # 按日期汇总
        daily_costs = self.trades.groupby(self.trades['timestamp'].dt.date).agg({
            'volume': 'sum',
            'commission': 'sum',
            'slippage': 'sum',
            'market_impact': 'sum',
            'timing_cost': 'sum',
            'total_cost': 'sum'
        }).reset_index()
        
        # 确保有数据可以绘图
        if len(daily_costs) == 0:
            print("警告: 没有足够的数据生成每日成本图表")
            # 创建一个简单的图表，显示没有数据
            plt.figure(figsize=(10, 6))
            plt.text(0.5, 0.5, '没有足够的数据生成图表', 
                     horizontalalignment='center', verticalalignment='center',
                     fontsize=14)
            plt.tight_layout()
            plt.savefig(save_path)
            plt.close()
            return save_path
        
        daily_costs['cost_ratio'] = daily_costs['total_cost'] / daily_costs['volume'] * 100
        
        # 创建图表
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 15))
        
        # 绘制交易量和总成本
        ax1.bar(daily_costs['timestamp'], daily_costs['volume'], alpha=0.7, label='交易量')
        ax1_twin = ax1.twinx()
        ax1_twin.plot(daily_costs['timestamp'], daily_costs['total_cost'], 'r-', label='总成本')
        
        # 设置标题和标签
        ax1.set_title('每日交易量和总成本')
        ax1.set_ylabel('交易量')
        ax1_twin.set_ylabel('成本')
        ax1.legend(loc='upper left')
        ax1_twin.legend(loc='upper right')
        
        # 绘制成本比例
        ax2.plot(daily_costs['timestamp'], daily_costs['cost_ratio'], 'g-', label='成本比例 (%)')
        ax2.set_title('每日交易成本比例')
        ax2.set_ylabel('成本比例 (%)')
        ax2.legend()
        
        # 绘制成本构成
        cost_components = daily_costs[['commission', 'slippage', 'market_impact', 'timing_cost']].copy()
        cost_components.index = daily_costs['timestamp']

        ax3.stackplot(cost_components.index, 
                    cost_components['commission'], 
                    cost_components['slippage'],
                    cost_components['market_impact'],
                    cost_components['timing_cost'],
                    labels=['佣金', '滑点', '市场冲击', '时机成本'])
        ax3.set_title('成本构成')
        ax3.set_ylabel('成本')
        ax3.legend()
        
        plt.tight_layout()
        plt.savefig(save_path)
        plt.close()
        
        return save_path
    
    def get_cost_metrics(self):
        """获取成本指标"""
        if self.trades.empty:
            return {
                'avg_cost_ratio': 0,
                'commission_pct': 0,
                'slippage_pct': 0,
                'market_impact_pct': 0,
                'timing_cost_pct': 0
            }
        
        # 计算总交易量
        total_volume = self.trades['volume'].sum()
        
        if total_volume == 0:
            return {
                'avg_cost_ratio': 0,
                'commission_pct': 0,
                'slippage_pct': 0,
                'market_impact_pct': 0,
                'timing_cost_pct': 0
            }
        
        # 计算各项成本占比
        total_cost = self.trades['total_cost'].sum()
        commission_sum = self.trades['commission'].sum()
        slippage_sum = self.trades['slippage'].sum()
        market_impact_sum = self.trades['market_impact'].sum()
        timing_cost_sum = self.trades['timing_cost'].sum()
        
        # 计算成本比例
        avg_cost_ratio = total_cost / total_volume * 100
        
        # 计算各项成本占总成本的比例
        commission_pct = commission_sum / total_cost * 100 if total_cost > 0 else 0
        slippage_pct = slippage_sum / total_cost * 100 if total_cost > 0 else 0
        market_impact_pct = market_impact_sum / total_cost * 100 if total_cost > 0 else 0
        timing_cost_pct = timing_cost_sum / total_cost * 100 if total_cost > 0 else 0
        
        # 处理可能的NaN或无穷大值
        metrics = {
            'avg_cost_ratio': avg_cost_ratio,
            'commission_pct': commission_pct,
            'slippage_pct': slippage_pct,
            'market_impact_pct': market_impact_pct,
            'timing_cost_pct': timing_cost_pct
        }
        
        # 将NaN或无穷大值替换为0
        for key, value in metrics.items():
            if np.isnan(value) or np.isinf(value):
                metrics[key] = 0

        return {
            'avg_cost_ratio': avg_cost_ratio,
            'commission_pct': commission_pct,
            'slippage_pct': slippage_pct,
            'market_impact_pct': market_impact_pct,
            'timing_cost_pct': timing_cost_pct
        }