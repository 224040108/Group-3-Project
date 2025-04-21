// 全局变量
let performanceChart = null;
const refreshInterval = 5000; // 刷新间隔（毫秒）

// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // 加载策略配置
    loadStrategyConfig();
    
    // 加载执行系统状态
    loadExecutionStatus();
    
    // 加载持仓信息
    loadPositions();
    
    // 加载交易记录
    loadTrades();
    
    // 加载策略表现
    loadPerformance();
    
    // 设置定时刷新
    setInterval(function() {
        loadExecutionStatus();
        loadPositions();
        loadTrades();
        loadPerformance();
    }, refreshInterval);
    
    // 绑定按钮事件
    document.getElementById('update-config').addEventListener('click', updateStrategyConfig);
    document.getElementById('start-execution').addEventListener('click', startExecution);
    document.getElementById('stop-execution').addEventListener('click', stopExecution);
});

// 加载策略配置
function loadStrategyConfig() {
    fetch('/api/strategy/config')
        .then(response => response.json())
        .then(data => {
            document.getElementById('lookback-period').value = data.lookback_period;
            document.getElementById('entry-threshold').value = data.entry_threshold;
            document.getElementById('exit-threshold').value = data.exit_threshold;
            document.getElementById('stop-loss').value = data.stop_loss;
            document.getElementById('position-size').value = data.position_size;
        })
        .catch(error => console.error('加载策略配置失败:', error));
}

// 更新策略配置
function updateStrategyConfig() {
    const config = {
        lookback_period: parseInt(document.getElementById('lookback-period').value),
        entry_threshold: parseFloat(document.getElementById('entry-threshold').value),
        exit_threshold: parseFloat(document.getElementById('exit-threshold').value),
        stop_loss: parseFloat(document.getElementById('stop-loss').value),
        position_size: parseFloat(document.getElementById('position-size').value)
    };
    
    fetch('/api/strategy/config', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(config)
    })
        .then(response => response.json())
        .then(data => {
            alert('策略配置已更新');
        })
        .catch(error => console.error('更新策略配置失败:', error));
}

// 加载执行系统状态
function loadExecutionStatus() {
    fetch('/api/execution/status')
        .then(response => response.json())
        .then(data => {
            const statusElement = document.getElementById('execution-status');
            if (data.running) {
                statusElement.className = 'alert alert-success';
                statusElement.textContent = `执行系统状态: 运行中 (最后更新: ${data.last_update || '未知'})`;
                document.getElementById('start-execution').disabled = true;
                document.getElementById('stop-execution').disabled = false;
            } else {
                statusElement.className = 'alert alert-warning';
                statusElement.textContent = '执行系统状态: 未运行';
                document.getElementById('start-execution').disabled = false;
                document.getElementById('stop-execution').disabled = true;
            }
        })
        .catch(error => console.error('加载执行系统状态失败:', error));
}

// 启动执行系统
function startExecution() {
    fetch('/api/execution/start', {
        method: 'POST'
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                alert(data.message);
                loadExecutionStatus();
            } else {
                alert(`错误: ${data.message}`);
            }
        })
        .catch(error => console.error('启动执行系统失败:', error));
}

// 停止执行系统
function stopExecution() {
    fetch('/api/execution/stop', {
        method: 'POST'
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                alert(data.message);
                loadExecutionStatus();
            } else {
                alert(`错误: ${data.message}`);
            }
        })
        .catch(error => console.error('停止执行系统失败:', error));
}

// 加载持仓信息
function loadPositions() {
    fetch('/api/positions')
        .then(response => response.json())
        .then(data => {
            const container = document.getElementById('positions-container');
            
            if (data.length === 0) {
                container.innerHTML = '<p>当前没有持仓</p>';
                return;
            }
            
            let html = '<div class="table-responsive"><table class="table table-sm">';
            html += '<thead><tr><th>配对</th><th>类型</th><th>数量</th><th>开仓时间</th></tr></thead>';
            html += '<tbody>';
            
            data.forEach(position => {
                const positionType = position.type === 'long_short' ? 
                    `做多${position.stock1_code}/做空${position.stock2_code}` : 
                    `做空${position.stock1_code}/做多${position.stock2_code}`;
                
                html += `<tr>
                    <td>${position.pair_id}</td>
                    <td>${positionType}</td>
                    <td>${position.quantity.toFixed(2)}</td>
                    <td>${position.open_time}</td>
                </tr>`;
            });
            
            html += '</tbody></table></div>';
            container.innerHTML = html;
        })
        .catch(error => console.error('加载持仓信息失败:', error));
}

// 加载交易记录
function loadTrades() {
    // 获取最近30天的交易记录
    const endDate = new Date().toISOString().split('T')[0];
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - 30);
    const startDateStr = startDate.toISOString().split('T')[0];
    
    fetch(`/api/trades?start_date=${startDateStr}&end_date=${endDate}`)
        .then(response => response.json())
        .then(data => {
            const container = document.getElementById('trades-container');
            
            if (data.length === 0) {
                container.innerHTML = '<tr><td colspan="8" class="text-center">没有交易记录</td></tr>';
                return;
            }
            
            let html = '';
            
            // 只显示最近10条交易记录
            const recentTrades = data.slice(0, 10);
            
            recentTrades.forEach(trade => {
                const pnlClass = trade.pnl > 0 ? 'text-success' : (trade.pnl < 0 ? 'text-danger' : '');
                
                html += `<tr>
                    <td>${trade.timestamp}</td>
                    <td>${trade.pair_id}</td>
                    <td>${trade.action === 'open' ? '开仓' : (trade.action === 'close' ? '平仓' : '止损')}</td>
                    <td>${trade.long_code}</td>
                    <td>${trade.short_code}</td>
                    <td>${trade.quantity.toFixed(2)}</td>
                    <td class="${pnlClass}">${trade.pnl ? trade.pnl.toFixed(2) : '-'}</td>
                    <td>${trade.status === 'open' ? '持仓中' : '已平仓'}</td>
                </tr>`;
            });
            
            container.innerHTML = html;
        })
        .catch(error => console.error('加载交易记录失败:', error));
}

// 加载策略表现
function loadPerformance() {
    // 获取最近30天的表现数据
    const endDate = new Date().toISOString().split('T')[0];
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - 30);
    const startDateStr = startDate.toISOString().split('T')[0];
    
    fetch(`/api/performance?start_date=${startDateStr}&end_date=${endDate}`)
        .then(response => response.json())
        .then(data => {
            if (data.length === 0) {
                return;
            }
            
            // 准备图表数据
            const dates = data.map(item => item.date);
            const equity = data.map(item => item.equity);
            
            // 如果图表已存在，则销毁
            if (performanceChart) {
                performanceChart.destroy();
            }
            
            // 创建新图表
            const ctx = document.getElementById('performance-chart').getContext('2d');
            performanceChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: dates,
                    datasets: [{
                        label: '权益曲线',
                        data: equity,
                        borderColor: 'rgba(75, 192, 192, 1)',
                        backgroundColor: 'rgba(75, 192, 192, 0.2)',
                        tension: 0.1,
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        title: {
                            display: true,
                            text: '策略权益曲线'
                        }
                    },
                    scales: {
                        x: {
                            display: true,
                            title: {
                                display: true,
                                text: '日期'
                            }
                        },
                        y: {
                            display: true,
                            title: {
                                display: true,
                                text: '权益'
                            }
                        }
                    }
                }
            });
        })
        .catch(error => console.error('加载策略表现失败:', error));
}

// 在处理回测结果的函数中，确保使用后端返回的实际指标

function updateBacktestResults(data) {
    // 更新回测指标
    if (data.metrics) {
        console.log("收到的回测指标数据:", data.metrics); // 添加调试信息
        
        document.getElementById('total-return').textContent = data.metrics.total_return;
        document.getElementById('annual-return').textContent = data.metrics.annual_return;
        document.getElementById('sharpe-ratio').textContent = data.metrics.sharpe_ratio;
        document.getElementById('max-drawdown').textContent = data.metrics.max_drawdown;
        document.getElementById('win-rate').textContent = data.metrics.win_rate;
        document.getElementById('profit-loss-ratio').textContent = data.metrics.profit_loss_ratio;
        document.getElementById('total-trades').textContent = data.metrics.total_trades;
    }
    
    // 更新回测图表
    if (data.chart_url) {
        const chartImg = document.getElementById('backtest-chart');
        // 添加时间戳参数避免浏览器缓存
        chartImg.src = data.chart_url + '?t=' + new Date().getTime();
    }
    
    // 显示回测结果区域
    document.getElementById('backtest-results').style.display = 'block';
}