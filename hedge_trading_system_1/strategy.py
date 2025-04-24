import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import time
from config.config import STRATEGY_CONFIG
import database as db

# 使用yfinance获取数据
import yfinance as yf

class PairTradingStrategy:
    def __init__(self, config=None):
        self.config = config or STRATEGY_CONFIG
        self.pairs = self.config['pairs']
        self.lookback_period = self.config['lookback_period']
        self.entry_threshold = self.config['entry_threshold']
        self.exit_threshold = self.config['exit_threshold']
        self.stop_loss = self.config['stop_loss']
        self.position_size = self.config['position_size']
        self.positions = {}  # 当前持仓
        self.pair_stats = {}  # 添加pair_stats属性
        
        # 确保数据库存在
        db.ensure_db_exists()
    
    def fetch_data(self, code, days=None):
        """从yfinance获取股票数据"""
        days = days or self.lookback_period + 10  # 多获取一些数据以防万一
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        try:
            # 先尝试从数据库获取
            db_code = code.replace('.', '_')  # 转换代码格式以匹配数据库
            db_start = start_date.strftime('%Y%m%d')
            db_end = end_date.strftime('%Y%m%d')
            df = db.get_stock_data(db_code, db_start, db_end)
            
            # 如果数据库中数据不足，则从yfinance获取
            if len(df) < days:
                # 转换为yfinance格式的代码
                yf_code = self.convert_to_yf_code(code)
                
                # 获取数据
                df_new = yf.download(
                    yf_code,
                    start=start_date,
                    end=end_date,
                    progress=False
                )
                
                if not df_new.empty:
                    # 重置索引，将日期列从索引转为普通列
                    df_new = df_new.reset_index()
                    
                    # 重命名列以匹配数据库结构
                    df_new = df_new.rename(columns={
                        'Date': 'date',
                        'Open': 'open',
                        'High': 'high',
                        'Low': 'low',
                        'Close': 'close',
                        'Volume': 'volume'
                    })
                    
                    # 添加代码列
                    df_new['code'] = db_code
                    
                    # 转换日期格式
                    df_new['date'] = df_new['date'].dt.strftime('%Y%m%d')
                    
                    # 保存到数据库
                    db.save_stock_data(df_new)
                    
                    # 合并数据
                    if not df.empty:
                        df = pd.concat([df, df_new])
                    else:
                        df = df_new
            
            return df.sort_values('date')
        except Exception as e:
            print(f"获取{code}数据失败: {e}")
            return pd.DataFrame()
    
    def convert_to_yf_code(self, code):
        """将标准代码转换为yfinance格式的代码"""
        if '.SZ' in code:
            return code.split('.')[0] + '.SZ'
        elif '.SH' in code:
            return code.split('.')[0] + '.SS'
        return code
    
    def display_pairs_info(self):
        """显示选取的股票对及其共同有数据的连续3年时间范围"""
        print("选取的股票对:")
        for pair in self.pairs:
            stock1_code, stock2_code = pair
            print(f"- {stock1_code} 和 {stock2_code}")
        
        print("\n检查是否有最近3年的数据:")
        three_years_ago = datetime.now() - timedelta(days=365*3)
        today = datetime.now()
        
        for pair in self.pairs:
            stock1_code, stock2_code = pair
            
            try:
                # 获取两只股票的数据
                yf_code1 = self.convert_to_yf_code(stock1_code)
                yf_code2 = self.convert_to_yf_code(stock2_code)
                
                # 获取第一只股票的数据
                df1 = yf.download(
                    yf_code1,
                    start=three_years_ago,
                    end=today,
                    progress=False
                )
                
                # 获取第二只股票的数据
                df2 = yf.download(
                    yf_code2,
                    start=three_years_ago,
                    end=today,
                    progress=False
                )
                
                # 检查数据量
                if df1.empty or df2.empty:
                    print(f"- {stock1_code} 和 {stock2_code}: 无法获取足够数据")
                    continue
                
                # 重置索引，将日期列从索引转为普通列
                df1 = df1.reset_index()
                df2 = df2.reset_index()
                
                # 检查最新数据日期
                latest_date1 = df1['Date'].max() if not df1.empty else None
                latest_date2 = df2['Date'].max() if not df2.empty else None
                
                # 检查数据量是否足够3年
                days_count1 = len(df1)
                days_count2 = len(df2)
                
                # 找出共同的交易日
                common_dates = set(df1['Date']).intersection(set(df2['Date']))
                common_days_count = len(common_dates)
                
                # 检查最早的共同日期
                earliest_common_date = min(common_dates) if common_dates else None
                
                print(f"- {stock1_code}:")
                print(f"  - 数据量: {days_count1}个交易日")
                print(f"  - 最新数据日期: {latest_date1}")
                
                print(f"- {stock2_code}:")
                print(f"  - 数据量: {days_count2}个交易日")
                print(f"  - 最新数据日期: {latest_date2}")
                
                print(f"- 共同数据:")
                print(f"  - 共同交易日数量: {common_days_count}个交易日")
                print(f"  - 最早共同日期: {earliest_common_date}")
                print(f"  - 最新共同日期: {max(common_dates) if common_dates else None}")
                
                # 判断是否满足要求
                three_years_days = 252 * 3  # 假设每年约252个交易日
                if common_days_count >= three_years_days:
                    print(f"  - 状态: ✅ 满足3年数据要求")
                else:
                    print(f"  - 状态: ❌ 不满足3年数据要求，仅有{common_days_count}个交易日")
                
                # 检查是否有最新的数据
                latest_date = datetime.now() - timedelta(days=7)  # 允许最多7天的滞后
                
                if max(common_dates) if common_dates else None >= latest_date:
                    print(f"  - 最新数据: ✅ 有最新数据")
                else:
                    print(f"  - 最新数据: ❌ 缺少最新数据，最新日期为{max(common_dates) if common_dates else None}")
                
                print("")
                
            except Exception as e:
                print(f"- {stock1_code} 和 {stock2_code}: 获取数据失败 - {e}")
                print("")
    
    def calculate_spread(self, stock1_data, stock2_data):
        """计算两只股票的价差"""
        # 确保日期匹配
        merged_data = pd.merge(
            stock1_data[['date', 'close']], 
            stock2_data[['date', 'close']], 
            on='date', 
            suffixes=('_1', '_2')
        )
        
        if merged_data.empty:
            return None, None, None
        
        # 计算价格比率
        merged_data['ratio'] = merged_data['close_1'] / merged_data['close_2']
        
        # 计算z-score
        merged_data['ratio_mean'] = merged_data['ratio'].rolling(window=self.lookback_period).mean()
        merged_data['ratio_std'] = merged_data['ratio'].rolling(window=self.lookback_period).std()
        merged_data['z_score'] = (merged_data['ratio'] - merged_data['ratio_mean']) / merged_data['ratio_std']
        
        # 去除NaN值
        merged_data = merged_data.dropna()
        
        if merged_data.empty:
            return None, None, None
        
        # 获取最新的z-score和价格
        latest = merged_data.iloc[-1]
        return latest['z_score'], latest['close_1'], latest['close_2']
    
    def generate_signals(self, date_str=None, data=None):
        """生成交易信号"""
        signals = []
        
        # 如果没有提供日期和数据，则返回空列表
        if date_str is None or data is None:
            return signals
        
        # 调试信息
        print(f"处理日期: {date_str}, 可用股票数量: {len(data)}")
        
        # 遍历所有股票对
        for pair_id, pair in enumerate(self.pairs):
            stock1_code, stock2_code = pair
            
            # 检查两只股票的数据是否都存在
            if stock1_code not in data or stock2_code not in data:
                continue
            
            stock1_data = data[stock1_code]
            stock2_data = data[stock2_code]
            
            # 获取当前价格
            stock1_price = stock1_data['close']
            stock2_price = stock2_data['close']
            
            # 计算价格比率
            price_ratio = stock1_price / stock2_price
            
            # 检查是否有足够的历史数据来计算均值和标准差
            if pair_id not in self.pair_stats:
                print(f"警告: 股票对 {pair_id} 没有统计数据")
                continue
            
            mean = self.pair_stats[pair_id]['mean']
            std = self.pair_stats[pair_id]['std']
            
            # 确保标准差不为零
            if std <= 0.0001:
                std = 0.0001
            
            # 计算z-score
            z_score = (price_ratio - mean) / std
            
            # 调试信息
            if abs(z_score) > 0.5:
                print(f"股票对 {stock1_code}-{stock2_code} 的z-score: {z_score:.4f}")
            
            # 根据z-score生成交易信号
            if z_score > self.entry_threshold:
                # 价格比率高于阈值，做空stock1，做多stock2
                print(f"生成做空信号: {stock1_code}-{stock2_code}, z-score={z_score:.4f}")
                signals.append({
                    'pair_id': pair_id,
                    'stock1_code': stock1_code,
                    'stock2_code': stock2_code,
                    'stock1_price': stock1_price,
                    'stock2_price': stock2_price,
                    'z_score': z_score,
                    'action': 'open',
                    'position_type': 'short',
                    'timestamp': date_str
                })
            elif z_score < -self.entry_threshold:
                # 价格比率低于阈值，做多stock1，做空stock2
                print(f"生成做多信号: {stock1_code}-{stock2_code}, z-score={z_score:.4f}")
                signals.append({
                    'pair_id': pair_id,
                    'stock1_code': stock1_code,
                    'stock2_code': stock2_code,
                    'stock1_price': stock1_price,
                    'stock2_price': stock2_price,
                    'z_score': z_score,
                    'action': 'open',
                    'position_type': 'long',
                    'timestamp': date_str
                })
            elif pair_id in self.positions:
                # 检查是否需要平仓
                position = self.positions[pair_id]
                
                if position['type'] == 'long' and z_score >= -self.exit_threshold:
                    # 做多仓位，z-score回归，平仓
                    print(f"生成平仓信号(多头): {stock1_code}-{stock2_code}, z-score={z_score:.4f}")
                    signals.append({
                        'pair_id': pair_id,
                        'stock1_code': stock1_code,
                        'stock2_code': stock2_code,
                        'stock1_price': stock1_price,
                        'stock2_price': stock2_price,
                        'z_score': z_score,
                        'action': 'close',
                        'position_type': 'long',
                        'timestamp': date_str
                    })
                elif position['type'] == 'short' and z_score <= self.exit_threshold:
                    # 做空仓位，z-score回归，平仓
                    print(f"生成平仓信号(空头): {stock1_code}-{stock2_code}, z-score={z_score:.4f}")
                    signals.append({
                        'pair_id': pair_id,
                        'stock1_code': stock1_code,
                        'stock2_code': stock2_code,
                        'stock1_price': stock1_price,
                        'stock2_price': stock2_price,
                        'z_score': z_score,
                        'action': 'close',
                        'position_type': 'short',
                        'timestamp': date_str
                    })
        
        if signals:
            print(f"日期 {date_str} 生成了 {len(signals)} 个交易信号")
        
        return signals
    
    def check_stop_loss(self, position, current_price1, current_price2):
        """检查是否触发止损"""
        if position['type'] == 'long_short':
            # 做多stock1，做空stock2
            long_return = current_price1 / position['stock1_price'] - 1
            short_return = 1 - current_price2 / position['stock2_price']
            total_return = long_return + short_return
        else:
            # 做空stock1，做多stock2
            short_return = 1 - current_price1 / position['stock1_price']
            long_return = current_price2 / position['stock2_price'] - 1
            total_return = short_return + long_return
        
        return total_return < -self.stop_loss
    
    def update_positions(self, trade_data):
        """更新持仓信息"""
        pair_id = trade_data['pair_id']
        
        if trade_data['action'] in ['close', 'stop_loss']:
            if pair_id in self.positions:
                del self.positions[pair_id]
        
        elif trade_data['action'] == 'open':
            self.positions[pair_id] = {
                'type': trade_data['position_type'],
                'stock1_code': trade_data['long_code'],
                'stock2_code': trade_data['short_code'],
                'stock1_price': trade_data['long_price'],
                'stock2_price': trade_data['short_price'],
                'quantity': trade_data['quantity'],
                'open_time': trade_data['timestamp']
            }
    
    def run(self):
        """运行策略，生成交易信号"""
        return self.generate_signals()
    
    def calculate_pair_stats(self, historical_data=None):
        """计算每个股票对的统计数据
        
        Args:
            historical_data: 历史数据字典，如果为None则从数据库获取
            
        Returns:
            dict: 每个股票对的统计数据
        """
        self.pair_stats = {}
        
        print("计算股票对统计数据...")
        
        # 打印历史数据的第一个日期的所有股票代码，用于调试
        if historical_data is not None and len(historical_data) > 0:
            first_date = sorted(historical_data.keys())[0]
            print(f"历史数据中第一个日期 {first_date} 的股票代码:")
            for code in historical_data[first_date].keys():
                print(f"  - {code}")
        
        for pair_id, pair in enumerate(self.pairs):
            stock1_code, stock2_code = pair
            
            # 标准化股票代码格式
            stock1_code_std = self.standardize_stock_code(stock1_code)
            stock2_code_std = self.standardize_stock_code(stock2_code)
            
            print(f"处理股票对: {stock1_code}({stock1_code_std}) 和 {stock2_code}({stock2_code_std})")
            
            # 如果提供了历史数据，则使用提供的数据
            if historical_data is not None:
                # 检查历史数据中是否包含这两只股票（使用标准化后的代码）
                if stock1_code_std not in historical_data[first_date] or stock2_code_std not in historical_data[first_date]:
                    # 尝试使用原始代码
                    if stock1_code not in historical_data[first_date] or stock2_code not in historical_data[first_date]:
                        print(f"警告: 历史数据中缺少 {stock1_code} 或 {stock2_code} 的数据")
                        continue
                    else:
                        # 使用原始代码
                        stock1_code_use = stock1_code
                        stock2_code_use = stock2_code
                else:
                    # 使用标准化后的代码
                    stock1_code_use = stock1_code_std
                    stock2_code_use = stock2_code_std
                
                # 获取共同的日期
                common_dates = set(historical_data.keys())
                
                if not common_dates:
                    print(f"警告: {stock1_code} 和 {stock2_code} 没有共同的交易日")
                    continue
                
                # 构建价格序列
                dates = sorted(common_dates)
                stock1_prices = []
                stock2_prices = []
                
                for date in dates:
                    if stock1_code_use in historical_data[date] and stock2_code_use in historical_data[date]:
                        stock1_prices.append(historical_data[date][stock1_code_use]['close'])
                        stock2_prices.append(historical_data[date][stock2_code_use]['close'])
                
                if len(stock1_prices) < self.lookback_period:
                    print(f"警告: {stock1_code} 和 {stock2_code} 的数据不足 {self.lookback_period} 天")
                    continue
                
                # 计算价格比率
                price_ratios = [p1 / p2 for p1, p2 in zip(stock1_prices, stock2_prices)]
                
                # 计算均值和标准差
                mean = sum(price_ratios) / len(price_ratios)
                std = (sum((r - mean) ** 2 for r in price_ratios) / len(price_ratios)) ** 0.5
            else:
                # 从数据库获取数据
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=self.lookback_period * 2)).strftime('%Y%m%d')
                
                stock1_data = db.get_stock_data(stock1_code_std, start_date, end_date)
                stock2_data = db.get_stock_data(stock2_code_std, start_date, end_date)
                
                if stock1_data.empty or stock2_data.empty:
                    print(f"警告: 无法获取 {stock1_code} 或 {stock2_code} 的数据")
                    continue
                
                # 合并数据
                merged_data = pd.merge(
                    stock1_data[['date', 'close']], 
                    stock2_data[['date', 'close']], 
                    on='date', 
                    suffixes=('_1', '_2')
                )
                
                if len(merged_data) < self.lookback_period:
                    print(f"警告: {stock1_code} 和 {stock2_code} 的共同数据不足 {self.lookback_period} 天")
                    continue
                
                # 计算价格比率
                merged_data['ratio'] = merged_data['close_1'] / merged_data['close_2']
                
                # 计算均值和标准差
                mean = merged_data['ratio'].mean()
                std = merged_data['ratio'].std()
            
            # 存储统计数据
            self.pair_stats[pair_id] = {
                'mean': mean,
                'std': std
            }
            
            print(f"股票对 {stock1_code}-{stock2_code} 的统计数据: 均值={mean:.4f}, 标准差={std:.4f}")
        
        print(f"计算完成，共有 {len(self.pair_stats)} 个股票对的统计数据")
        return self.pair_stats
    
    def standardize_stock_code(self, code):
        """标准化股票代码格式，确保在数据库和回测系统中使用一致的格式"""
        
        # 处理上交所股票
        if 'SH' in code or 'SS' in code:
            code = code.replace('SH', 'SS')  # 统一使用SS表示上交所
        
        return code


    def calculate_zscore(self, price_ratio, pair_id):
        """
        计算给定价格比率的Z分数
        
        Args:
            price_ratio: 两只股票的价格比率
            pair_id: 股票对ID
            
        Returns:
            float: Z分数，如果无法计算则返回None
        """
        # 检查是否有该股票对的统计数据
        if pair_id not in self.pair_stats:
            print(f"警告: 股票对 {pair_id} 没有统计数据")
            return None
        
        # 获取均值和标准差
        mean = self.pair_stats[pair_id]['mean']
        std = self.pair_stats[pair_id]['std']
        
        # 确保标准差不为零
        if std <= 0.0001:
            std = 0.0001
        
        # 计算z-score
        z_score = (price_ratio - mean) / std
        
        return z_score