// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // 设置默认日期
    setDefaultDates();
    
    // 设置默认回测参数
    setDefaultBacktestParams();
    
    // 绑定按钮事件
    document.getElementById('run-backtest').addEventListener('click', runBacktest);
});

// 设置默认日期
function setDefaultDates() {
    const endDate = new Date();
    const startDate = new Date();
    startDate.setFullYear(startDate.getFullYear() - 1); // 默认回测一年
    
    document.getElementById('start-date').value = formatDate(startDate);
    document.getElementById('end-date').value = formatDate(endDate);
}

// 设置默认回测参数
function setDefaultBacktestParams() {
    document.getElementById('initial-capital').value = 1000000;
    document.getElementById('commission-rate').value = 0.0003;
    document.getElementById('slippage').value = 0.0001;
}

// 格式化日期为YYYY-MM-DD
function formatDate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

// 运行回测
function runBacktest() {
    // 获取回测参数
    const initialCapital = parseFloat(document.getElementById('initial-capital').value);
    const startDate = document.getElementById('start-date').value.replace(/-/g, '');
    const endDate = document.getElementById('end-date').value.replace(/-/g, '');
    const commissionRate = parseFloat(document.getElementById('commission-rate').value);
    const slippage = parseFloat(document.getElementById('slippage').value);
    
    // 验证参数
    if (isNaN(initialCapital) || initialCapital <= 0) {
        alert('请输入有效的初始资金');
        return;
    }
    
    if (!startDate || !endDate) {
        alert('请选择开始和结束日期');
        return;
    }
    
    if (startDate > endDate) {
        alert('开始日期不能晚于结束日期');
        return;
    }
    
    if (isNaN(commissionRate) || commissionRate < 0) {
        alert('请输入有效的佣金率');
        return;
    }
    
    if (isNaN(slippage) || slippage < 0) {
        alert('请输入有效的滑点');
        return;
    }
    
    // 更新状态
    const statusElement = document.getElementById('backtest-status');
    statusElement.className = 'alert alert-info';
    statusElement.textContent = '正在运行回测，请稍候...';
    
    // 发送回测请求
    fetch('/api/backtest/run', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            initial_capital: initialCapital,
            start_date: startDate,
            end_date: endDate,
            commission_rate: commissionRate,
            slippage: slippage
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                // 更新状态
                statusElement.className = 'alert alert-success';
                statusElement.textContent = '回测完成';
                
                // 显示回测指标
                displayBacktestMetrics(data.metrics);
                
                // 显示回测图表
                displayBacktestChart(data.chart_url);
                
                // 加载交易记录
                loadBacktestTrades(startDate, endDate);
            } else {
                statusElement.className = 'alert alert-danger';
                statusElement.textContent = `回测失败: ${data.message}`;
            }
        })
        .catch(error => {
            console.error('运行回测失败:', error);
            statusElement.className = 'alert alert-danger';
            statusElement.textContent = '回测失败，请检查控制台获取详细错误信息';
        });
}

// 显示回测指标
function displayBacktestMetrics(metrics) {
    const container = document.getElementById('metrics-container');
    
    container.innerHTML = `
        <tr>
            <td>总收益率</td>
            <td>${(metrics.total_return * 100).toFixed(2)}%</td>
        </tr>
        <tr>
            <td>年化收益率</td>
            <td>${(metrics.annual_return * 100).toFixed(2)}%</td>
        </tr>
        <tr>
            <td>夏普比率</td>
            <td>${metrics.sharpe_ratio.toFixed(2)}</td>
        </tr>
        <tr>
            <td>最大回撤</td>
            <td>${(metrics.max_drawdown * 100).toFixed(2)}%</td>
        </tr>
        <tr>
            <td>胜率</td>
            <td>${(metrics.win_rate * 100).toFixed(2)}%</td>
        </tr>
        <tr>
            <td>盈亏比</td>
            <td>${metrics.profit_factor.toFixed(2)}</td>
        </tr>
        <tr>
            <td>总交易次数</td>
            <td>${metrics.total_trades}</td>
        </tr>
    `;
}

// 显示回测图表
function displayBacktestChart(chartUrl) {
    const container = document.getElementById('backtest-chart-container');
    
    // 添加时间戳以避免缓存
    const timestamp = new Date().getTime();
    container.innerHTML = `<img src="${chartUrl}?t=${timestamp}" class="img-fluid" alt="回测结果图表">`;
}

// 加载回测交易记录
function loadBacktestTrades(startDate, endDate) {
    fetch(`/api/trades?start_date=${startDate}&end_date=${endDate}`)
        .then(response => response.json())
        .then(data => {
            const container = document.getElementById('backtest-trades-container');
            
            if (data.length === 0) {
                container.innerHTML = '<tr><td colspan="7" class="text-center">没有交易记录</td></tr>';
                return;
            }
            
            let html = '';
            
            data.forEach(trade => {
                const pnlClass = trade.pnl > 0 ? 'text-success' : (trade.pnl < 0 ? 'text-danger' : '');
                
                html += `<tr>
                    <td>${trade.timestamp}</td>
                    <td>${trade.pair_id}</td>
                    <td>${trade.action === 'open' ? '开仓' : (trade.action === 'close' ? '平仓' : '止损')}</td>
                    <td>${trade.long_code}</td>
                    <td>${trade.short_code}</td>
                    <td>${trade.quantity.toFixed(2)}</td>
                    <td class="${pnlClass}">${trade.pnl ? trade.pnl.toFixed(2) : '-'}</td>
                </tr>`;
            });
            
            container.innerHTML = html;
        })
        .catch(error => console.error('加载交易记录失败:', error));
}