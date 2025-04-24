对冲策略交易系统 (Hedge Trading System)

一、项目概述
对冲策略交易系统是一个基于配对交易策略的量化交易平台，集成了策略开发、回测、执行和交易成本分析等功能。该系统采用Python和Flask框架开发，提供了Web界面进行交互操作，支持历史数据回测和实时交易执行。

二、项目架构
hedge_trading_system/
├── config/                  # 配置文件目录
│   ├── __init__.py          # 包初始化文件
│   └── config.py            # 系统配置参数
├── data/                    # 数据存储目录
│   └── database.db          # SQLite数据库文件
│   └── hedge_trading.db     # 交易数据库文件
├── static/                  # 静态资源目录
│   ├── css/                 # CSS样式文件
│   │   └── style.css        # 主样式文件
│   └── js/                  # JavaScript文件
│       ├── dashboard.js     # 仪表盘页面脚本
│       ├── backtest.js      # 回测页面脚本
│       └── tca.js           # 交易成本分析页面脚本
├── templates/               # HTML模板目录
│   ├── index.html           # 主页/仪表盘模板
│   ├── backtest.html        # 回测页面模板
│   ├── dashboard.html       # 仪表盘详细页面模板
│   └── tca.html             # 交易成本分析页面模板
├── app.py                   # 应用主入口，Flask服务器
├── database.py              # 数据库操作模块
├── strategy.py              # 交易策略实现模块
├── backtest.py              # 回测系统模块
├── execution.py             # 交易执行系统模块
├── tca.py                   # 交易成本分析模块
└── readme.txt               # 项目说明文件

三、核心模块详解（后端）

1. 配置模块 (config/config.py)
该模块定义了系统的各项配置参数，包括：
数据库配置：数据库路径
回测配置：初始资金、回测日期范围、佣金率、滑点等
执行系统配置：更新间隔、最大订单大小等
前端配置：刷新间隔等
策略配置：股票对列表、回溯期、入场/出场阈值、止损比例等

2. 策略模块 (strategy.py)：配对交易对冲策略
配对交易策略原理：
配对交易是一种统计套利策略，主要基于两只相关性较高的股票之间价格关系的均值回归特性。该策略的核心假设是：虽然两只股票的价格可能暂时偏离其历史关系，但最终会回归到历史均值水平。
主要思路如下：
	配对选择：基于相关性高的股票对进行交易
	价格比率计算：计算两只股票的价格比率
	Z-Score计算：使用滚动窗口计算价格比率的均值和标准差，然后计算Z-Score：Z-Score = (当前比率 - 均值) / 标准差
	信号生成：
	当Z-Score > entry_threshold时，做空股票1，做多股票2
	当Z-Score < -entry_threshold时，做多股票1，做空股票2
	当Z-Score回归到exit_threshold附近时，平仓获利
	当亏损超过stop_loss阈值时，触发止损
	数据获取：使用yfinance API获取股票数据，并缓存到本地数据库
	主要函数：
	fetch_data：获取股票历史数据
	calculate_pair_stats：计算股票对的统计数据
	generate_signals：生成交易信号
	run：运行策略并返回交易信号
	check_stop_loss：检查是否触发止损

3. 回测模块 (backtest.py)
实现了策略回测的功能，主要逻辑：
数据加载：加载历史数据
信号生成：基于历史数据生成交易信号
交易执行：模拟执行交易并计算收益
绩效评估：计算各项绩效指标
主要指标计算公式：
收益率：returns = (final_equity - initial_capital) / initial_capital
年化收益率：annual_return = (1 + returns) ^ (252 / trading_days) - 1
夏普比率：sharpe_ratio = (annual_return - risk_free_rate) / volatility
最大回撤：max_drawdown = max((peak_value - current_value) / peak_value)
主要函数：
run：运行回测
load_data：加载历史数据
generate_signals_for_date：生成特定日期的交易信号
execute_trade：执行交易
update_portfolio_value：更新投资组合价值
calculate_returns_and_drawdowns：计算收益和回撤
calculate_performance_metrics：计算绩效指标

4. 数据库模块 (database.py)
负责数据的存储和检索，包括股票数据、交易记录和绩效数据。
主要表结构：
stock_data：存储股票历史数据
trades：存储交易记录
performance：存储绩效数据
backtest_info：存储回测配置信息
主要函数：
ensure_db_exists：确保数据库存在
get_db_connection：获取数据库连接
save_stock_data：保存股票数据
get_stock_data：获取股票数据
save_trade：保存交易记录
get_trades：获取交易记录
save_performance：保存绩效数据
get_performance：获取绩效数据
reset_database：重置数据库
数据来源：
股票数据：通过yfinance API获取
交易数据：由回测系统和执行系统生成
绩效数据：由回测系统计算

5. 执行系统模块 (execution.py)
负责实时交易执行，将策略生成的信号转化为实际交易。
主要功能：
定时运行策略生成信号
检查交易时间
执行交易并记录
管理持仓和资金
主要函数：
start：启动执行系统
stop：停止执行系统
_run_loop：执行系统主循环
_is_trading_time：检查是否是交易时间
_execute_trade：执行交易

6. 交易成本分析模块 (tca.py)
分析交易成本并提供可视化，帮助评估交易执行效率。
主要指标计算：
佣金：commission = volume * commission_rate
滑点：slippage = volume * slippage_rate
市场冲击：market_impact = 0.1 * sqrt(volume / 10000)
时机成本：基于执行价格与决策价格的差异
总交易成本：total_cost = commission + slippage + market_impact + timing_cost
成本比例：cost_ratio = total_cost / volume * 100%
主要函数：
run：运行交易成本分析
load_trades：加载交易数据
analyze_trades：分析交易成本
plot_cost_analysis：绘制成本分析图表
get_cost_metrics：获取成本指标

7. Web应用模块 (app.py)
使用Flask框架实现Web界面，提供用户交互功能。
主要路由：
/：主页/仪表盘
/backtest：回测页面
/tca：交易成本分析页面
/api/strategy/config：获取/更新策略配置
/api/backtest/latest：获取最近一次回测信息
/run_backtest：运行回测
/run_tca：运行交易成本分析

四、前端文件详解

1.HTML文件
index.html：主页/仪表盘，显示策略概览、当前持仓和最近交易
backtest.html：回测页面，提供回测参数配置和结果展示
dashboard.html：详细仪表盘页面，展示更多策略和市场数据
tca.html：交易成本分析页面，展示交易成本指标和图表

2.JavaScript文件
dashboard.js：处理仪表盘页面的交互和数据更新
backtest.js：处理回测页面的参数提交和结果展示
tca.js：处理交易成本分析页面的参数提交和结果展示，包括：
设置默认日期范围
提交分析请求
显示分析结果和图表
处理交易明细展示

3.CSS文件
style.css：定义系统的样式，包括布局、颜色、字体等

五、数据库文件
database.db：主数据库，存储股票数据、交易记录和绩效数据
hedge_trading.db：交易数据库，存储交易执行相关数据

六、使用流程
1.在配置文件中设置参数
2.运行app.py启动系统
3.访问Web界面进行操作：
	在仪表盘调整策略参数
	在回测页面进行历史回测
	在交易成本分析页面评估交易效率
	
七、策略特点
该配对交易策略具有以下特点：
1.市场中性：同时做多和做空，降低系统性风险
2.统计套利：基于价格关系的均值回归特性
3.风险控制：包含止损机制，控制单次交易最大亏损
4.适应性：可通过参数调整适应不同市场环境
