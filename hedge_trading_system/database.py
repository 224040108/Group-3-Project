import sqlite3
import os
import pandas as pd
from config.config import DATABASE_PATH
import numpy as np

def reset_database():
    """重置数据库，删除所有表并重新创建"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 获取所有表名
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    # 删除所有表
    for table in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {table[0]}")
    
    conn.commit()
    conn.close()
    
    print("数据库已重置")
    
    # 重新创建必要的表
    ensure_db_exists()

# 添加数据库连接函数
def get_db_connection():
    """获取数据库连接"""
    # 确保数据库目录存在
    db_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)
    
    # 连接到数据库文件
    db_path = os.path.join(db_dir, 'hedge_trading.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # 使查询结果可以通过列名访问
    return conn
    
def ensure_db_exists():
    """确保数据库文件存在，如果不存在则创建"""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # 创建股票数据表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS stock_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL,
        date TEXT NOT NULL,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume REAL,
        amount REAL,
        UNIQUE(code, date)
    )
    ''')
    
    # 创建交易记录表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        pair_id TEXT,
        action TEXT,
        position_type TEXT,
        long_code TEXT,
        short_code TEXT,
        open_price_long REAL,
        open_price_short REAL,
        close_price_long REAL,
        close_price_short REAL,
        quantity REAL,
        pnl REAL,
        commission REAL,
        net_pnl REAL,
        volume REAL,
        slippage REAL,
        market_impact REAL,
        timing_cost REAL,
        total_cost REAL,
        status TEXT
    )
    ''')
    
    # 创建策略表现表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS performance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        equity REAL NOT NULL,
        returns REAL,
        drawdown REAL,
        sharpe REAL,
        UNIQUE(date)
    )
    ''')
    
    conn.commit()
    conn.close()

def save_stock_data(data):
    """保存股票数据到数据库"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 检查是否已存在该记录
    cursor.execute(
        "SELECT id FROM stock_data WHERE code = ? AND date = ?",
        (data['code'], data['date'])
    )
    result = cursor.fetchone()
    
    try:
        if result:
            # 更新现有记录
            cursor.execute(
                """
                UPDATE stock_data 
                SET open = ?, high = ?, low = ?, close = ?, volume = ?
                WHERE code = ? AND date = ?
                """,
                (data['open'], data['high'], data['low'], data['close'], data['volume'], 
                 data['code'], data['date'])
            )
        else:
            # 插入新记录
            cursor.execute(
                """
                INSERT INTO stock_data (code, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (data['code'], data['date'], data['open'], data['high'], data['low'], 
                 data['close'], data['volume'])
            )
        
        conn.commit()
    except Exception as e:
        print(f"保存股票数据时出错: {e}")
        print(f"数据: {data}")
    finally:
        conn.close()

def get_stock_data(code, start_date, end_date):
    """从数据库获取股票数据"""
    conn = get_connection()
    
    query = """
    SELECT code, date, open, high, low, close, volume
    FROM stock_data
    WHERE code = ? AND date >= ? AND date <= ?
    ORDER BY date
    """
    
    df = pd.read_sql_query(query, conn, params=(code, start_date, end_date))
    
    conn.close()
    return df

def save_trade(trade_data):
    """保存交易记录到数据库"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 检查trades表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
    table_exists = cursor.fetchone()
    
    if table_exists:
        # 检查表结构
        cursor.execute("PRAGMA table_info(trades)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # 如果表结构不匹配，则删除旧表
        required_columns = ['position_type', 'long_code', 'short_code', 'open_price_long', 
                           'open_price_short', 'close_price_long', 'close_price_short']
        if not all(col in columns for col in required_columns):
            print("trades表结构不匹配，重新创建表...")
            cursor.execute("DROP TABLE trades")
            table_exists = None
    
    # 创建或重新创建trades表
    if not table_exists:
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            pair_id TEXT,
            action TEXT,
            position_type TEXT,
            long_code TEXT,
            short_code TEXT,
            open_price_long REAL,
            open_price_short REAL,
            close_price_long REAL,
            close_price_short REAL,
            quantity REAL,
            pnl REAL,
            commission REAL,
            net_pnl REAL,
            volume REAL,
            slippage REAL,
            market_impact REAL,
            timing_cost REAL,
            total_cost REAL,
            status TEXT
        )
        ''')
    
    # 计算交易量
    if 'volume' not in trade_data:
        if trade_data['action'] == 'open':
            trade_data['volume'] = trade_data['quantity'] * (trade_data['open_price_long'] + trade_data['open_price_short'])
        else:
            trade_data['volume'] = trade_data['quantity'] * (trade_data['close_price_long'] + trade_data['close_price_short'])
    
    # 计算滑点成本 (假设为交易量的0.01%)
    if 'slippage' not in trade_data:
        trade_data['slippage'] = trade_data['volume'] * 0.0001
    
    # 计算市场冲击成本 (假设为交易量的平方根乘以系数)
    if 'market_impact' not in trade_data:
        trade_data['market_impact'] = 0.1 * np.sqrt(trade_data['volume'] / 10000)
    
    # 计算时机成本 (假设为随机值)
    if 'timing_cost' not in trade_data:
        np.random.seed(42)
        trade_data['timing_cost'] = np.random.normal(0, 0.0005) * trade_data['volume']
    
    # 计算总成本
    if 'total_cost' not in trade_data:
        trade_data['total_cost'] = trade_data['commission'] + trade_data['slippage'] + trade_data['market_impact'] + trade_data['timing_cost']
    
    # 准备SQL语句
    sql = '''
    INSERT INTO trades (
        timestamp, pair_id, action, position_type, long_code, short_code,
        open_price_long, open_price_short, close_price_long, close_price_short,
        quantity, pnl, commission, net_pnl, volume, slippage, market_impact, timing_cost, total_cost
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    '''
    
    # 准备数据
    data = (
        trade_data.get('timestamp', ''),
        trade_data.get('pair_id', ''),
        trade_data.get('action', ''),
        trade_data.get('position_type', ''),
        trade_data.get('long_code', ''),
        trade_data.get('short_code', ''),
        trade_data.get('open_price_long', 0.0),
        trade_data.get('open_price_short', 0.0),
        trade_data.get('close_price_long', 0.0),
        trade_data.get('close_price_short', 0.0),
        trade_data.get('quantity', 0.0),
        trade_data.get('pnl', 0.0),
        trade_data.get('commission', 0.0),
        trade_data.get('net_pnl', 0.0),
        trade_data.get('volume', 0.0),
        trade_data.get('slippage', 0.0),
        trade_data.get('market_impact', 0.0),
        trade_data.get('timing_cost', 0.0),
        trade_data.get('total_cost', 0.0)
    )
    
    # 执行SQL
    cursor.execute(sql, data)
    conn.commit()
    conn.close()

def save_backtest_info(backtest_info):
    """保存回测信息到数据库"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 确保backtest_info表存在
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS backtest_info (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        start_date TEXT,
        end_date TEXT,
        initial_capital REAL,
        timestamp TEXT
    )
    ''')
    
    # 准备SQL语句
    sql = '''
    INSERT INTO backtest_info (start_date, end_date, initial_capital, timestamp)
    VALUES (?, ?, ?, ?)
    '''
    
    # 准备数据
    data = (
        backtest_info.get('start_date', ''),
        backtest_info.get('end_date', ''),
        backtest_info.get('initial_capital', 0.0),
        backtest_info.get('timestamp', '')
    )
    
    # 执行SQL
    cursor.execute(sql, data)
    conn.commit()
    conn.close()

def get_trades(start_date=None, end_date=None):
    """从数据库获取交易记录"""
    conn = get_db_connection()
    
    # 转换日期格式
    if start_date and isinstance(start_date, str) and '-' in start_date:
        start_date = start_date.replace('-', '')
    if end_date and isinstance(end_date, str) and '-' in end_date:
        end_date = end_date.replace('-', '')
    
    # 构建查询
    query = "SELECT * FROM trades"
    params = []
    
    if start_date or end_date:
        query += " WHERE "
        if start_date:
            query += "timestamp >= ?"
            params.append(start_date)
        if start_date and end_date:
            query += " AND "
        if end_date:
            query += "timestamp <= ?"
            params.append(end_date)
    
    # 执行查询
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    return df

def get_latest_backtest_info():
    """获取最新的回测信息"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 查询最新的回测信息
    cursor.execute("SELECT * FROM backtest_info ORDER BY id DESC LIMIT 1")
    result = cursor.fetchone()
    conn.close()
    
    if result:
        # 将结果转换为字典
        columns = [desc[0] for desc in cursor.description]
        backtest_info = dict(zip(columns, result))
        return backtest_info
    
    return None

def update_trade_status(trade_id, status, pnl=None):
    """更新交易状态"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    if pnl is not None:
        cursor.execute("UPDATE trades SET status = ?, pnl = ? WHERE id = ?", (status, pnl, trade_id))
    else:
        cursor.execute("UPDATE trades SET status = ? WHERE id = ?", (status, trade_id))
    
    conn.commit()
    conn.close()

def save_performance(performance_data):
    """保存策略表现数据"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT OR REPLACE INTO performance (date, equity, returns, drawdown, sharpe)
    VALUES (?, ?, ?, ?, ?)
    ''', (
        performance_data['date'],
        performance_data['equity'],
        performance_data['returns'],
        performance_data['drawdown'],
        performance_data['sharpe']
    ))
    
    conn.commit()
    conn.close()

def get_performance_data(start_date=None, end_date=None):
    """获取绩效数据
    
    Args:
        start_date: 开始日期，格式为YYYYMMDD
        end_date: 结束日期，格式为YYYYMMDD
        
    Returns:
        pandas.DataFrame: 绩效数据
    """
    conn = get_connection()
    
    query = "SELECT * FROM performance"
    params = []
    
    if start_date or end_date:
        query += " WHERE"
        
        if start_date:
            query += " date >= ?"
            params.append(start_date)
            
        if end_date:
            if start_date:
                query += " AND"
            query += " date <= ?"
            params.append(end_date)
    
    query += " ORDER BY date"
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    return df

def get_trades(start_date=None, end_date=None, status=None):
    """获取交易记录"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 检查trades表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
    if not cursor.fetchone():
        print("警告: trades表不存在")
        return pd.DataFrame()
    
    # 检查表结构
    cursor.execute("PRAGMA table_info(trades)")
    columns = [column[1] for column in cursor.fetchall()]
    
    # 构建查询
    query = "SELECT * FROM trades"
    conditions = []
    params = []
    
    if start_date:
        conditions.append("timestamp >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("timestamp <= ?")
        params.append(end_date)
    if status:
        conditions.append("status = ?")
        params.append(status)
    
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    query += " ORDER BY timestamp DESC"
    
    # 执行查询
    df = pd.read_sql_query(query, conn, params=params)
    
    # 检查是否需要添加缺失的列
    required_columns = ['open_price_long', 'open_price_short', 'close_price_long', 'close_price_short']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns and 'long_price' in df.columns and 'short_price' in df.columns:
        print(f"添加缺失的列: {missing_columns}")
        # 根据action列创建开盘价和收盘价
        if 'open_price_long' not in df.columns:
            df['open_price_long'] = df['long_price']
        if 'open_price_short' not in df.columns:
            df['open_price_short'] = df['short_price']
        if 'close_price_long' not in df.columns:
            df['close_price_long'] = df['long_price']
        if 'close_price_short' not in df.columns:
            df['close_price_short'] = df['short_price']
    
    conn.close()
    return df


import sqlite3
import os

def get_connection():
    """获取数据库连接"""
    # 使用与get_db_connection相同的数据库路径
    db_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)
    
    # 连接到数据库文件
    db_path = os.path.join(db_dir, 'hedge_trading.db')
    conn = sqlite3.connect(db_path)
    
    # 创建必要的表
    create_tables(conn)
    
    return conn

def create_tables(conn):
    """创建必要的数据库表"""
    cursor = conn.cursor()
    
    # 创建股票数据表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS stock_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL,
        date TEXT NOT NULL,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume REAL,
        UNIQUE(code, date)
    )
    ''')
    
    # 创建交易记录表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        pair_id TEXT,
        action TEXT,
        position_type TEXT,
        long_code TEXT,
        short_code TEXT,
        open_price_long REAL,
        open_price_short REAL,
        close_price_long REAL,
        close_price_short REAL,
        quantity REAL,
        pnl REAL,
        commission REAL,
        net_pnl REAL,
        volume REAL,
        slippage REAL,
        market_impact REAL,
        timing_cost REAL,
        total_cost REAL,
        status TEXT
    )
    ''')
    
    # 创建绩效表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS performance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        equity REAL,
        returns REAL,
        drawdown REAL,
        sharpe REAL,
        UNIQUE(date)
    )
    ''')
    
    conn.commit()

def save_performance_data(data):
    """保存绩效数据到数据库
    
    Args:
        data: 包含绩效数据的字典，包括date, equity, return, drawdown, sharpe等字段
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # 确保performance表存在
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS performance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        equity REAL,
        returns REAL,
        drawdown REAL,
        sharpe REAL
    )
    ''')
    
    # 检查是否已存在该日期的记录
    cursor.execute(
        "SELECT id FROM performance WHERE date = ?",
        (data['date'],)
    )
    result = cursor.fetchone()
    
    if result:
        # 更新现有记录
        cursor.execute(
            """
            UPDATE performance 
            SET equity = ?, returns = ?, drawdown = ?, sharpe = ?
            WHERE date = ?
            """,
            (data['equity'], data['return'], data['drawdown'], data['sharpe'], data['date'])
        )
    else:
        # 插入新记录
        cursor.execute(
            """
            INSERT INTO performance (date, equity, returns, drawdown, sharpe)
            VALUES (?, ?, ?, ?, ?)
            """,
            (data['date'], data['equity'], data['return'], data['drawdown'], data['sharpe'])
        )
    
    conn.commit()
    conn.close()

# 确保在导入模块时创建数据库和表
if __name__ == "__main__":
    conn = get_connection()
    conn.close()