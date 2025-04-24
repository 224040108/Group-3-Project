// 全局变量
let performanceChart = null;
const refreshInterval = 5000; // 刷新间隔（毫秒）
let executionInProgress = false;

// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // 设置默认日期（最近3个月）
    setDefaultDates();
    
    // 加载策略配置
    loadStrategyConfig();
    
    // 加载执行系统状态
    loadExecutionStatus();
    
    // 加载持仓信息
    loadPositions();
    
    // 加载交易记录
    loadTrades();
    
    // 绑定按钮事件
    document.getElementById('update-config').addEventListener('click', updateStrategyConfig);
    document.getElementById('start-execution').addEventListener('click', startExecution);
    document.getElementById('stop-execution').addEventListener('click', stopExecution);
    
    // 初始化图表容器但不显示数据
    initializePerformanceChart();
});

// 设置默认日期（最近3个月）
function setDefaultDates() {
    const endDate = new Date();
    const startDate = new Date();
    startDate.setMonth(startDate.getMonth() - 3); // 默认回测最近3个月
    
    // 如果页面上有日期选择器，则设置默认值
    const startDateInput = document.getElementById('start-date');
    const endDateInput = document.getElementById('end-date');
    
    if (startDateInput) {
        startDateInput.value = formatDate(startDate);
    }
    
    if (endDateInput) {
        endDateInput.value = formatDate(endDate);
    }
}

// 格式化日期为YYYY-MM-DD
function formatDate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

// 初始化性能图表（但不显示数据）
function initializePerformanceChart() {
    const ctx = document.getElementById('performance-chart');
    if (!ctx) return;
    
    // 获取最近3个月的日期范围
    const endDate = new Date();
    const startDate = new Date();
    startDate.setMonth(startDate.getMonth() - 3);
    
    // 生成空的日期标签（3个月的每一天）
    const dateLabels = [];
    const currentDate = new Date(startDate);
    while (currentDate <= endDate) {
        dateLabels.push(formatDate(currentDate));
        currentDate.setDate(currentDate.getDate() + 1);
    }
    
    // 创建空的数据集
    const emptyData = Array(dateLabels.length).fill(null);
    
    // 创建图表
    performanceChart = new Chart(ctx.getContext('2d'), {
        type: 'line',
        data: {
            labels: dateLabels,
            datasets: [{
                label: '权益曲线',
                data: emptyData,
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
                    },
                    beginAtZero: false
                }
            }
        }
    });
    
    // 隐藏执行结果区域
    const resultsElement = document.getElementById('execution-results');
    if (resultsElement) {
        resultsElement.style.display = 'none';
    }
}

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
    
    // 显示加载状态
    showLoading("正在更新策略配置...");
    
    fetch('/api/strategy/config', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(config)
    })
        .then(response => response.json())
        .then(data => {
            // 隐藏加载状态
            hideLoading();
            
            if (data.status === 'success') {
                showAlert('success', '策略配置已更新');
            } else {
                showAlert('danger', `更新失败: ${data.message}`);
            }
        })
        .catch(error => {
            // 隐藏加载状态
            hideLoading();
            console.error('更新策略配置失败:', error);
            showAlert('danger', '更新策略配置失败，请查看控制台获取详细错误信息');
        });
}

// 加载执行系统状态
function loadExecutionStatus() {
    fetch('/api/execution/status')
        .then(response => response.json())
        .then(data => {
            // 更新执行系统状态
            const statusElement = document.getElementById('execution-status');
            if (statusElement) {
                statusElement.textContent = data.running ? '运行中' : '已停止';
                statusElement.className = data.running ? 'badge bg-success' : 'badge bg-danger';
            }
            
            // 更新按钮状态
            const startButton = document.getElementById('start-execution');
            const stopButton = document.getElementById('stop-execution');
            
            if (startButton && stopButton) {
                startButton.disabled = data.running;
                stopButton.disabled = !data.running;
            }
            
            // 更新全局执行状态
            executionInProgress = data.running;
            
            // 如果系统正在运行，显示执行结果区域
            const resultsElement = document.getElementById('execution-results');
            
            if (resultsElement) {
                resultsElement.style.display = data.running ? 'block' : 'none';
            }
            
            // 更新进度条
            if (data.running && data.progress !== undefined) {
                updateExecutionProgress(data.progress, data.current_date);
            }
        })
        .catch(error => console.error('加载执行系统状态失败:', error));
}

// 加载持仓信息
// 修改loadPositions函数，确保只在执行系统运行时显示持仓信息
function loadPositions() {
    // 如果执行系统未运行，不加载持仓
    if (!executionInProgress) return;
    
    // 显示持仓卡片
    document.getElementById('positions-card').style.display = 'block';
    
    fetch('/api/positions')
        .then(response => response.json())
        .then(data => {
            const container = document.getElementById('positions-container');
            
            if (!container) return;
            
            if (data.length === 0) {
                container.innerHTML = '<p>暂无持仓</p>';
                return;
            }
            
            let html = '<table class="table table-striped">';
            html += `<thead>
                <tr>
                    <th>股票对</th>
                    <th>多头</th>
                    <th>空头</th>
                    <th>数量</th>
                    <th>开仓时间</th>
                </tr>
            </thead><tbody>`;
            
            data.forEach(position => {
                html += `<tr>
                    <td>${position.pair_id}</td>
                    <td>${position.stock1_code}</td>
                    <td>${position.stock2_code}</td>
                    <td>${parseFloat(position.quantity).toFixed(2)}</td>
                    <td>${position.open_time}</td>
                </tr>`;
            });
            
            html += '</tbody></table>';
            
            container.innerHTML = html;
        })
        .catch(error => console.error('加载持仓信息失败:', error));
}

// 修改startExecution函数，确保启动执行系统时显示相关卡片并隐藏系统说明
// 启动执行系统
function startExecution() {
    showLoading("正在启动执行系统...");
    
    fetch('/api/execution/start', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        hideLoading();
        
        if (data.status === 'success') {
            // 更新UI
            document.getElementById('start-execution').disabled = true;
            document.getElementById('stop-execution').disabled = false;
            
            // 显示执行相关卡片
            document.getElementById('execution-results').style.display = 'block';
            document.getElementById('execution-trades').style.display = 'block';
            document.getElementById('positions-card').style.display = 'block';
            
            // 隐藏系统说明和股票对信息
            document.getElementById('system-info').style.display = 'none';
            document.getElementById('pairs-info').style.display = 'none';
            
            // 显示日期范围（如果有）
            const startDate = data.start_date || '未指定';
            const endDate = data.end_date || '未指定';
            document.getElementById('execution-progress-message').textContent = `开始执行: ${startDate} 至 ${endDate}`;
            
            // 设置执行状态
            executionInProgress = true;
            
            // 启动SSE连接
            startExecutionEventSource();
            
            // 显示初始图表
            const chartUrl = `static/execution_results.png?t=${new Date().getTime()}`;
            updateExecutionChart(chartUrl);
        } else {
            alert(`启动失败: ${data.message}`);
        }
    })
    .catch(error => {
        hideLoading();
        console.error('启动执行系统失败:', error);
        alert('启动执行系统失败，请查看控制台获取详细信息。');
    });
}

// 修改stopExecution函数，确保停止执行系统时显示系统说明
function stopExecution() {
    showLoading("正在停止执行系统...");
    
    fetch('/api/execution/stop', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        hideLoading();
        
        if (data.status === 'success') {
            // 更新UI
            document.getElementById('start-execution').disabled = false;
            document.getElementById('stop-execution').disabled = true;
            document.getElementById('execution-progress-message').textContent = '执行已停止';
            
            // 修改：不隐藏执行相关卡片，而是更新其内容
            document.getElementById('execution-results').style.display = 'block';
            document.getElementById('execution-trades').style.display = 'block';
            document.getElementById('positions-card').style.display = 'block';
            
            // 显示系统说明和股票对信息
            document.getElementById('system-info').style.display = 'block';
            document.getElementById('pairs-info').style.display = 'block';
            
            // 设置执行状态
            executionInProgress = false;
            
            // 停止SSE连接
            if (window.executionEventSource) {
                window.executionEventSource.close();
            }
            
            // 修改：执行结束后加载最终的交易记录和持仓信息
            loadFinalTrades();
            
            // 清空持仓显示
            const positionsContainer = document.getElementById('positions-container');
            if (positionsContainer) {
                positionsContainer.innerHTML = '<p>暂无持仓</p>';
            }
        } else {
            alert(`停止失败: ${data.message}`);
        }
    })
    .catch(error => {
        hideLoading();
        console.error('停止执行系统失败:', error);
        alert('停止执行系统失败，请查看控制台获取详细信息。');
    });
}

// 添加新函数：加载最终的交易记录
function loadFinalTrades() {
    fetch('/api/trades?status=closed')
        .then(response => response.json())
        .then(trades => {
            // 按时间戳排序，最新的在前面
            trades.sort((a, b) => {
                return b.timestamp.localeCompare(a.timestamp);
            });
            
            // 更新交易记录显示
            updateExecutionTrades(trades);
        })
        .catch(error => {
            console.error('加载最终交易记录失败:', error);
        });
}

// 修改checkExecutionStatus函数，确保页面加载时检查执行系统状态
function checkExecutionStatus() {
    fetch('/api/execution/status')
        .then(response => response.json())
        .then(data => {
            if (data.running) {
                // 如果系统正在运行，更新UI
                document.getElementById('start-execution').disabled = true;
                document.getElementById('stop-execution').disabled = false;
                
                // 显示执行相关卡片
                document.getElementById('execution-results').style.display = 'block';
                document.getElementById('execution-trades').style.display = 'block';
                document.getElementById('positions-card').style.display = 'block';
                
                // 隐藏系统说明和股票对信息
                document.getElementById('system-info').style.display = 'none';
                document.getElementById('pairs-info').style.display = 'none';
                
                // 设置执行状态
                executionInProgress = true;
                
                // 更新进度
                updateExecutionProgress(data.progress, data.current_date);
                
                // 更新指标
                updateExecutionMetrics(data.metrics);
                
                // 更新图表
                updateExecutionChart(data.chart_url);
                
                // 启动SSE连接
                startExecutionEventSource();
            } else {
                // 如果系统未运行，隐藏相关卡片
                document.getElementById('execution-results').style.display = 'none';
                document.getElementById('execution-trades').style.display = 'none';
                document.getElementById('positions-card').style.display = 'none';
                
                // 显示系统说明和股票对信息
                document.getElementById('system-info').style.display = 'block';
                document.getElementById('pairs-info').style.display = 'block';
                
                // 设置执行状态
                executionInProgress = false;
            }
        })
        .catch(error => {
            console.error('获取执行系统状态失败:', error);
        });
}

// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // 设置默认日期（最近3个月）
    setDefaultDates();
    
    // 加载策略配置
    loadStrategyConfig();
    
    // 绑定按钮事件
    document.getElementById('start-execution').addEventListener('click', startExecution);
    document.getElementById('stop-execution').addEventListener('click', stopExecution);
    document.getElementById('update-config').addEventListener('click', updateStrategyConfig);
    
    // 检查执行系统状态
    checkExecutionStatus();
});

// 启动SSE连接
function startExecutionEventSource() {
    // 如果已经存在连接，先关闭
    if (window.executionEventSource) {
        window.executionEventSource.close();
    }
    
    // 创建新连接
    window.executionEventSource = new EventSource('/api/execution/progress');
    
    // 监听消息
    window.executionEventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            console.log("收到SSE更新:", data);  // 添加日志
            
            // 更新进度
            if (data.progress !== undefined) {
                updateExecutionProgress(data.progress, data.date);
            }
            
            // 更新指标
            if (data.metrics) {
                updateExecutionMetrics(data.metrics);
            }
            
            // 更新交易记录
            if (data.trades && data.trades.length > 0) {
                updateExecutionTrades(data.trades);
            }
            
            // 更新图表
            if (data.chart_url) {
                updateExecutionChart(data.chart_url);
            }
        } catch (error) {
            console.error("处理SSE消息时出错:", error, "原始数据:", event.data);
        }
    };
    
    // 监听错误
    window.executionEventSource.onerror = function(error) {
        console.error('SSE连接错误:', error);
        // 尝试重新连接
        setTimeout(startExecutionEventSource, 5000);
    };
    
    // 监听连接打开
    window.executionEventSource.onopen = function() {
        console.log("SSE连接已建立");
    };
}

// 更新进度
function updateExecutionProgress(progress, date) {
    const progressBar = document.getElementById('execution-progress-bar');
    if (!progressBar) return;
    
    progressBar.style.width = `${progress}%`;
    progressBar.textContent = `${Math.round(progress)}%`;
    progressBar.setAttribute('aria-valuenow', progress);
    
    if (date) {
        // 格式化日期 (从YYYYMMDD转为YYYY-MM-DD)
        const formattedDate = date.substring(0, 4) + '-' + date.substring(4, 6) + '-' + date.substring(6, 8);
        const progressMessage = document.getElementById('execution-progress-message');
        if (progressMessage) {
            progressMessage.textContent = `当前日期: ${formattedDate}`;
        }
    }
}

// 更新指标
function updateExecutionMetrics(metrics) {
    document.getElementById('execution-total-return').textContent = metrics.total_return;
    document.getElementById('execution-annual-return').textContent = metrics.annual_return;
    document.getElementById('execution-sharpe-ratio').textContent = metrics.sharpe_ratio;
    document.getElementById('execution-max-drawdown').textContent = metrics.max_drawdown;
    document.getElementById('execution-win-rate').textContent = metrics.win_rate;
    document.getElementById('execution-profit-loss-ratio').textContent = metrics.profit_loss_ratio;
    document.getElementById('execution-total-trades').textContent = metrics.total_trades;
}

// 更新交易记录
function updateExecutionTrades(trades) {
    const tradesContainer = document.getElementById('execution-trades-container');
    if (!tradesContainer) return;
    
    tradesContainer.innerHTML = '';
    
    if (trades.length > 0) {
        trades.forEach(trade => {
            // 格式化日期
            const date = trade.timestamp.substring(0, 4) + '-' + 
                        trade.timestamp.substring(4, 6) + '-' + 
                        trade.timestamp.substring(6, 8);
            
            // 创建行
            const row = document.createElement('tr');
            
            // 设置行内容，修改盈亏显示逻辑
            let pnlDisplay = '-';
            if (trade.action === 'close' || trade.status === 'closed') {
                // 确保pnl是数字
                const pnl = parseFloat(trade.pnl);
                if (!isNaN(pnl)) {
                    pnlDisplay = pnl.toFixed(2);
                }
            }
            
            row.innerHTML = `
                <td>${date}</td>
                <td>${trade.pair_id}</td>
                <td>${trade.action === 'open' ? '开仓' : '平仓'}</td>
                <td>${trade.long_code}</td>
                <td>${trade.short_code}</td>
                <td>${parseFloat(trade.quantity || 0).toFixed(2)}</td>
                <td>${pnlDisplay}</td>
            `;
            
            // 添加到容器
            tradesContainer.appendChild(row);
        });
    } else {
        const row = document.createElement('tr');
        row.innerHTML = '<td colspan="7" class="text-center">没有交易记录</td>';
        tradesContainer.appendChild(row);
    }
}

// 显示提示信息
function showAlert(type, message) {
    // 创建提示元素
    const alertElement = document.createElement('div');
    alertElement.className = `alert alert-${type} alert-dismissible fade show`;
    alertElement.role = 'alert';
    alertElement.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // 添加到页面
    const container = document.querySelector('.container-fluid');
    container.insertBefore(alertElement, container.firstChild);
    
    // 3秒后自动关闭
    setTimeout(() => {
        alertElement.classList.remove('show');
        setTimeout(() => alertElement.remove(), 150);
    }, 3000);
}

// 显示/隐藏加载指示器
function showLoading(message) {
    // 检查是否已存在加载指示器
    let loadingIndicator = document.getElementById('loading-indicator');
    
    if (!loadingIndicator) {
        // 创建加载指示器
        loadingIndicator = document.createElement('div');
        loadingIndicator.id = 'loading-indicator';
        loadingIndicator.className = 'loading-overlay';
        loadingIndicator.innerHTML = `
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">加载中...</span>
            </div>
            <p id="loading-message">${message}</p>
        `;
        
        // 添加样式
        const style = document.createElement('style');
        style.textContent = `
            .loading-overlay {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0, 0, 0, 0.5);
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                z-index: 9999;
                color: white;
            }
        `;
        document.head.appendChild(style);
        
        // 添加到页面
        document.body.appendChild(loadingIndicator);
    } else {
        // 更新消息
        document.getElementById('loading-message').textContent = message;
        loadingIndicator.style.display = 'flex';
    }
}

function hideLoading() {
    const loadingIndicator = document.getElementById('loading-indicator');
    if (loadingIndicator) {
        loadingIndicator.style.display = 'none';
    }
}

// 确保updateExecutionChart函数正确实现
function updateExecutionChart(chartUrl) {
    console.log("更新图表:", chartUrl);  // 添加日志
    
    const chartImg = document.getElementById('execution-chart');
    if (chartImg) {
        // 添加错误处理
        chartImg.onerror = function() {
            console.log('图表加载失败，可能尚未生成或正在生成中');
            // 5秒后重试
            setTimeout(() => {
                // 添加时间戳避免缓存
                const newUrl = chartUrl + (chartUrl.includes('?') ? '&' : '?') + 't=' + new Date().getTime();
                console.log("重试加载图表:", newUrl);
                chartImg.src = newUrl;
            }, 5000);
        };
        
        // 添加加载成功处理
        chartImg.onload = function() {
            console.log('图表加载成功');
        };
        
        // 确保URL包含时间戳以避免缓存
        const finalUrl = chartUrl.includes('t=') ? chartUrl : 
                         (chartUrl + (chartUrl.includes('?') ? '&' : '?') + 't=' + new Date().getTime());
        chartImg.src = finalUrl;
    } else {
        console.error("找不到图表元素");
    }
}