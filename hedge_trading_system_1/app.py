# 修改导入语句，添加Response
from flask import Flask, render_template, request, jsonify, Response
import pandas as pd
import json
from datetime import datetime, timedelta
import os
import time

from strategy import PairTradingStrategy
from backtest import Backtest
from execution import ExecutionSystem
from tca import TCA
import database as db
import yfinance as yf
from config.config import STRATEGY_CONFIG, BACKTEST_CONFIG, FRONTEND_CONFIG

app = Flask(__name__)

# 在app.py中，初始化组件后调用display_pairs_info方法

# 初始化组件
strategy = PairTradingStrategy()
# 显示股票对信息
strategy.display_pairs_info()
backtest = Backtest(strategy_class=PairTradingStrategy)
execution_system = ExecutionSystem(strategy=strategy)
tca = TCA()

# 确保数据库存在
db.ensure_db_exists()

@app.route('/')
def index():
    """主页"""
    return render_template('index.html', config=FRONTEND_CONFIG)

@app.route('/backtest')
def backtest_page():
    """回测页面"""
    return render_template('backtest.html', config=FRONTEND_CONFIG)

@app.route('/tca')
def tca_page():
    """交易成本分析页面"""
    return render_template('tca.html', config=FRONTEND_CONFIG)

@app.route('/api/strategy/config', methods=['GET'])
def get_strategy_config():
    """获取策略配置"""
    return jsonify(STRATEGY_CONFIG)

@app.route('/api/strategy/config', methods=['POST'])
def update_strategy_config():
    """更新策略配置"""
    data = request.json
    
    # 更新策略配置
    for key, value in data.items():
        if key in STRATEGY_CONFIG:
            STRATEGY_CONFIG[key] = value
    
    # 重新初始化策略
    strategy = PairTradingStrategy(config=STRATEGY_CONFIG)
    
    return jsonify({'status': 'success', 'config': STRATEGY_CONFIG})

@app.route('/api/backtest/run', methods=['POST'])
# 在app.py中找到处理回测结果的路由函数，确保它正确传递计算的指标

@app.route('/run_backtest', methods=['POST'])
def run_backtest():
    """运行回测"""
    data = request.json
    
    # 更新回测配置
    config = BACKTEST_CONFIG.copy()
    for key, value in data.items():
        if key in config:
            config[key] = value
    
    try:
        # 运行回测
        backtest = Backtest(strategy_class=PairTradingStrategy, config=config)
        results = backtest.run()
        
        # 确保将实际计算的指标传递给前端
        metrics = results['metrics']
        
        # 确保指标是字符串格式，避免前端处理问题
        metrics = results.get('metrics', {})
        formatted_metrics = {
            'total_return': f"{metrics.get('total_return', 0):.2%}",
            'annual_return': f"{metrics.get('annual_return', 0):.2f}",
            'sharpe_ratio': f"{metrics.get('sharpe_ratio', 0):.2f}",
            'max_drawdown': f"{metrics.get('max_drawdown', 0):.2%}",
            'win_rate': f"{metrics.get('win_rate', 0):.2%}",
            'profit_loss_ratio': f"{metrics.get('profit_loss_ratio', 0):.2f}",
            'total_trades': f"{metrics.get('total_trades', 0)}"
        }
        
        # 添加交易记录到响应
        trades = results.get('trades', [])
        
        # 调试信息
        print(f"回测完成，总交易次数: {formatted_metrics['total_trades']}")
        print(f"交易记录数量: {len(trades)}")

        return jsonify({
            'status': 'success',
            'message': '回测完成',
            'metrics': formatted_metrics,
            'trades': trades,
            'chart_url': 'static/backtest_results.png'
        })
        
    except Exception as e:
        import traceback
        print(f"回测过程中发生错误: {str(e)}")
        print(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': f'回测过程中发生错误: {str(e)}'
        })

@app.route('/api/backtest/metrics', methods=['GET'])
def get_backtest_metrics():
    """获取回测指标"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # 获取绩效数据
    performance = db.get_performance_data(start_date, end_date)
    
    if performance.empty:
        return jsonify({
            'status': 'error',
            'message': '没有回测数据'
        })
    
    # 计算指标
    initial_equity = performance.iloc[0]['equity']
    final_equity = performance.iloc[-1]['equity']
    total_return = (final_equity / initial_equity) - 1
    
    # 计算年化收益率
    days = len(performance)
    annual_return = (1 + total_return) ** (365 / days) - 1 if days > 0 else 0
    
    # 计算最大回撤
    max_drawdown = performance['drawdown'].max()
    
    # 计算夏普比率
    sharpe_ratio = performance.iloc[-1]['sharpe']
    
    # 获取交易记录
    trades = db.get_trades(start_date, end_date)
    
    # 计算胜率
    profitable_trades = trades[trades['pnl'] > 0]
    win_rate = len(profitable_trades) / len(trades) if len(trades) > 0 else 0
    
    # 计算盈亏比
    avg_profit = profitable_trades['pnl'].mean() if len(profitable_trades) > 0 else 0
    losing_trades = trades[trades['pnl'] < 0]
    avg_loss = abs(losing_trades['pnl'].mean()) if len(losing_trades) > 0 else 1
    profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else float('inf')
    
    return jsonify({
        'status': 'success',
        'metrics': {
            'total_return': total_return,
            'annual_return': annual_return,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'profit_loss_ratio': profit_loss_ratio,
            'total_trades': len(trades)
        }
    })

# 在app.py中添加以下路由

@app.route('/api/execution/start', methods=['POST'])
def start_execution():
    """启动执行系统"""
    def update_callback(progress, date_str, metrics, trades):
        # 将更新推送到全局变量，供SSE接口使用
        global execution_progress, execution_date, execution_metrics, execution_trades
        execution_progress = progress
        execution_date = date_str
        execution_metrics = metrics
        execution_trades = trades[-10:] if len(trades) > 10 else trades  # 只保留最近10条交易记录

    # 获取当前日期和3个月前的日期作为默认范围
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')

    # 启动执行系统
    result = execution_system.start(update_callback=update_callback)

    # 添加日期范围到结果中
    if result.get('status') == 'success':
        result['start_date'] = start_date
        result['end_date'] = end_date
        
    return jsonify(result)

@app.route('/api/execution/stop', methods=['POST'])
def stop_execution():
    """停止执行系统"""
    result = execution_system.stop()
    return jsonify(result)

@app.route('/api/execution/status', methods=['GET'])
def get_execution_status():
    """获取执行系统状态"""
    status = execution_system.get_status()
    
    # 添加图表URL
    if status.get('running', False):
        # 添加时间戳参数以避免浏览器缓存
        status['chart_url'] = f"static/execution_results.png?t={int(time.time())}"
    
    return jsonify(status)

# 添加SSE接口，用于实时更新
@app.route('/api/execution/progress')
def execution_progress_stream():
    """执行系统进度流"""
    def generate():
        global execution_progress, execution_date, execution_metrics, execution_trades
        
        # 确保static目录存在
        static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
        chart_path = os.path.join(static_dir, 'execution_results.png')
        
        # 如果图表不存在，创建一个空白图表
        if not os.path.exists(chart_path):
            try:
                import matplotlib.pyplot as plt
                plt.figure(figsize=(10, 6))
                plt.title('策略权益曲线 (等待数据...)')
                plt.xlabel('交易日')
                plt.ylabel('权益')
                plt.grid(True)
                plt.savefig(chart_path)
                plt.close()
                print(f"初始空白图表已创建: {chart_path}")
            except Exception as e:
                print(f"创建初始空白图表失败: {e}")
        
        while True:
            # 构建事件数据
            data = {
                'progress': execution_progress,
                'date': execution_date,
                'metrics': execution_metrics,
                'trades': execution_trades,
                'chart_url': f"static/execution_results.png?t={int(time.time())}"  # 添加时间戳避免缓存
            }
            
            # 发送事件
            yield f"data: {json.dumps(data)}\n\n"
            
            # 暂停一下，避免过多请求
            time.sleep(0.5)
    
    return Response(generate(), mimetype='text/event-stream')

# 初始化全局变量
execution_progress = 0
execution_date = None
execution_metrics = None
execution_trades = []

@app.route('/api/positions', methods=['GET'])
def get_positions():
    """获取当前持仓"""
    positions = []
    
    for pair_id, position in strategy.positions.items():
        positions.append({
            'pair_id': pair_id,
            'type': position['type'],
            'stock1_code': position['stock1_code'],
            'stock2_code': position['stock2_code'],
            'stock1_price': position['stock1_price'],
            'stock2_price': position['stock2_price'],
            'quantity': position['quantity'],
            'open_time': position['open_time']
        })
    
    return jsonify(positions)

@app.route('/api/trades', methods=['GET'])
def get_trades():
    """获取交易记录"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    status = request.args.get('status')
    
    # 获取交易记录
    trades = db.get_trades(start_date, end_date, status)
    
    # 确保返回的是列表
    if trades is None or trades.empty:
        return jsonify([])
    
    # 将DataFrame转换为字典列表
    trades_list = trades.to_dict('records')
    
    # 确保每个交易记录都有pnl字段，并且是数值类型
    for trade in trades_list:
        if 'pnl' not in trade or trade['pnl'] is None:
            trade['pnl'] = 0.0
        else:
            try:
                trade['pnl'] = float(trade['pnl'])
            except:
                trade['pnl'] = 0.0
    
    return jsonify(trades_list)

@app.route('/api/performance', methods=['GET'])
def get_performance():
    """获取策略表现"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    performance = db.get_performance_data(start_date, end_date)
    
    return jsonify(performance.to_dict('records'))

@app.route('/run_tca', methods=['POST'])
def run_tca():
    """运行交易成本分析"""
    data = request.json
    
    # 获取日期范围
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    
    try:
        # 运行交易成本分析
        tca_instance = TCA(start_date=start_date, end_date=end_date)
        
        # 设置进度回调函数
        def progress_callback(progress, message, status=None):
            print(f"TCA进度: {progress}% - {message}")
        
        tca_instance.progress_callback = progress_callback
        
        # 运行分析
        results = tca_instance.run()
        
        # 确保指标是字符串格式，避免前端处理问题
        metrics = results.get('metrics', {})
        formatted_metrics = {
            'total_trades': f"{metrics.get('total_trades', 0)}",
            'total_volume': f"{metrics.get('total_volume', 0):.2f}",
            'total_commission': f"{metrics.get('total_commission', 0):.2f}",
            'avg_slippage': f"{metrics.get('avg_slippage', 0):.4f}",
            'implementation_shortfall': f"{metrics.get('implementation_shortfall', 0):.2f}",
            'market_impact': f"{metrics.get('market_impact', 0):.2f}",
            'timing_cost': f"{metrics.get('timing_cost', 0):.2f}",
            'avg_cost_ratio': f"{metrics.get('avg_cost_ratio', 0):.2f}%",
            'commission_pct': f"{metrics.get('commission_pct', 0):.2f}%",
            'slippage_pct': f"{metrics.get('slippage_pct', 0):.2f}%",
            'market_impact_pct': f"{metrics.get('market_impact_pct', 0):.2f}%",
            'timing_cost_pct': f"{metrics.get('timing_cost_pct', 0):.2f}%"
        }
        
        return jsonify({
            'status': results.get('status', 'success'),
            'message': results.get('message', '交易成本分析完成'),
            'metrics': formatted_metrics,
            'trade_details': results.get('trade_details', []),
            'chart_url': results.get('chart_url', 'static/tca_analysis.png')
        })
        
    except Exception as e:
        import traceback
        print(f"交易成本分析过程中发生错误: {str(e)}")
        print(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': f'交易成本分析过程中发生错误: {str(e)}'
        })

@app.route('/api/backtest/latest', methods=['GET'])
def get_latest_backtest():
    """获取最近一次回测的日期范围"""
    try:
        # 从数据库获取最近一次回测信息
        conn = db.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT start_date, end_date FROM backtest_info 
            ORDER BY timestamp DESC LIMIT 1
        """)
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            # 将日期格式化为前端需要的格式
            start_date = result['start_date']
            end_date = result['end_date']
            
            # 如果日期格式是YYYYMMDD，转换为YYYY-MM-DD
            if len(start_date) == 8 and start_date.isdigit():
                start_date = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
            
            if len(end_date) == 8 and end_date.isdigit():
                end_date = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"
            
            return jsonify({
                'status': 'success',
                'start_date': start_date,
                'end_date': end_date
            })
        else:
            # 如果没有回测记录，返回空值
            return jsonify({
                'status': 'error',
                'message': '没有找到回测记录',
                'start_date': None,
                'end_date': None
            })
    
    except Exception as e:
        print(f"获取最近回测日期时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'获取最近回测日期时出错: {str(e)}',
            'start_date': None,
            'end_date': None
        })
        
# 在导入部分添加
from strategy import PairTradingStrategy
import database as db
import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd

# 添加初始化数据的函数
def initialize_stock_data():
    """在应用启动时加载历史股票数据到数据库"""
    print("正在初始化股票数据...")
    
    # 创建策略实例以获取股票对
    strategy = PairTradingStrategy()
    
    # 获取所有股票代码
    stock_codes = []
    for pair in strategy.pairs:
        stock_codes.extend(pair)
    
    # 去重
    stock_codes = list(set(stock_codes))
    
    # 设置日期范围（获取3年数据）
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*3 + 30)  # 多获取一个月的数据以防万一
    
    start_date_str = start_date.strftime('%Y%m%d')
    end_date_str = end_date.strftime('%Y%m%d')
    
    print(f"加载历史数据: {start_date_str} 至 {end_date_str}")
    
    # 加载每只股票的数据并保存到数据库
    for code in stock_codes:
        print(f"正在加载 {code} 的历史数据...")
        
        # 检查数据库中是否已有该股票的数据
        existing_data = db.get_stock_data(code, start_date_str, end_date_str)
        
        if not existing_data.empty:
            # 获取最新的数据日期
            latest_date = existing_data['date'].max()
            latest_date_dt = datetime.strptime(latest_date, '%Y%m%d')
            
            # 如果数据已经是最新的，则跳过
            if (end_date - latest_date_dt).days < 5:  # 允许5天的延迟
                print(f"{code} 数据已是最新，跳过更新")
                continue
            
            # 否则只更新缺失的部分
            new_start_date = (latest_date_dt + timedelta(days=1)).strftime('%Y%m%d')
            print(f"更新 {code} 从 {new_start_date} 至 {end_date_str} 的数据")
            start_date_str = new_start_date
        
        try:
            # 转换为yfinance格式的代码
            if '.SH' in code:
                yf_code = code.replace('.SH', '.SS')
            elif '.SZ' in code:
                yf_code = code
            else:
                yf_code = code
            
            # 使用更简单的方式获取数据 - 一次只获取一只股票
            ticker = yf.Ticker(yf_code)
            df = ticker.history(start=start_date, end=end_date)
            
            if df.empty:
                print(f"警告: 无法获取 {code} 的数据")
                continue
            
            # 处理数据格式
            df = df.reset_index()
            df['date'] = df['Date'].dt.strftime('%Y%m%d')
            
            # 批量保存到数据库
            conn = db.get_connection()
            cursor = conn.cursor()
            
            for _, row in df.iterrows():
                try:
                    # 检查是否已存在该记录
                    cursor.execute(
                        "SELECT id FROM stock_data WHERE code = ? AND date = ?",
                        (code, row['date'])
                    )
                    result = cursor.fetchone()
                    
                    if result:
                        # 更新现有记录
                        cursor.execute(
                            """
                            UPDATE stock_data 
                            SET open = ?, high = ?, low = ?, close = ?, volume = ?
                            WHERE code = ? AND date = ?
                            """,
                            (float(row['Open']), float(row['High']), float(row['Low']), 
                             float(row['Close']), float(row['Volume']) if not pd.isna(row['Volume']) else 0,
                             code, row['date'])
                        )
                    else:
                        # 插入新记录
                        cursor.execute(
                            """
                            INSERT INTO stock_data (code, date, open, high, low, close, volume)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (code, row['date'], float(row['Open']), float(row['High']), 
                             float(row['Low']), float(row['Close']), 
                             float(row['Volume']) if not pd.isna(row['Volume']) else 0)
                        )
                except Exception as e:
                    print(f"保存行数据时出错: {e}")
            
            conn.commit()
            conn.close()
            
            print(f"成功加载 {code} 的 {len(df)} 条历史数据")
            
        except Exception as e:
            print(f"加载 {code} 数据时出错: {e}")
    
    print("股票数据初始化完成")

# 在app.py的主函数中调用初始化函数
if __name__ == '__main__':
    # 初始化股票数据
    initialize_stock_data()
    
    # 启动Flask应用
    app.run(debug=True)
    
    # 不再需要登出baostock
    # import baostock as bs
    # bs.logout()
