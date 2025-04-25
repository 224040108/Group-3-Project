# 数据库配置
DATABASE_PATH = "data/database.db"

# 回测配置
BACKTEST_CONFIG = {
    "initial_capital": 1000000,  # 初始资金
    "start_date": "20220101",    # 回测开始日期
    "end_date": "20221231",      # 回测结束日期
    "commission_rate": 0.0003,   # 佣金率
    "slippage": 0.0001,          # 滑点
}

# 执行系统配置
EXECUTION_CONFIG = {
    "update_interval": 60,  # 更新间隔（秒）
    "max_order_size": 100000,  # 最大订单大小
}

# 前端配置
FRONTEND_CONFIG = {
    "refresh_interval": 5000,  # 刷新间隔（毫秒）
}

# 修改策略配置
STRATEGY_CONFIG = {
    'pairs': [
        ('601318.SH', '601601.SH'),  # 中国平安和中国太保
        ('600036.SH', '601328.SH'),  # 招商银行和交通银行
        ('600276.SH', '600196.SH'),  # 恒瑞医药和复星医药
        ('600887.SH', '600298.SH'),  # 伊利股份和青岛啤酒
        # 添加更多的股票对以增加交易机会
        ('601988.SH', '601398.SH'),  # 中国银行和工商银行
        ('600028.SH', '601857.SH'),  # 中国石化和中国石油
        ('600050.SH', '600000.SH'),  # 中国联通和浦发银行
    ],
    'lookback_period': 60,           # 回溯期
    'entry_threshold': 1.0,          # 降低入场阈值
    'exit_threshold': 0.3,           # 降低出场阈值
    'stop_loss': 0.1,                # 止损比例
    'position_size': 0.1,            # 仓位大小
    'use_dynamic_threshold': False,   # 启用动态阈值
    'min_threshold': 0.8,            # 最小阈值
    'max_threshold': 2.0,            # 最大阈值
    'volatility_lookback': 20        # 波动性计算回溯期
}