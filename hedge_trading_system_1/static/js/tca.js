// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // 设置默认日期
    setDefaultDates();
    
    // 绑定按钮事件
    document.getElementById('run-tca').addEventListener('click', runTCA);
});

// 设置默认日期
function setDefaultDates() {
    // 先尝试获取最近一次回测的日期范围
    fetch('/api/backtest/latest')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success' && data.start_date && data.end_date) {
                // 直接使用API返回的格式化日期
                document.getElementById('tca-start-date').value = data.start_date;
                document.getElementById('tca-end-date').value = data.end_date;
                console.log(`设置TCA日期范围为最近回测日期: ${data.start_date} 至 ${data.end_date}`);
            } else {
                // 如果没有回测记录或获取失败，使用默认的一个月范围
                setDefaultOneMonthRange();
                console.log('未找到回测记录，使用默认日期范围');
            }
        })
        .catch(error => {
            console.error('获取最近回测日期失败:', error);
            setDefaultOneMonthRange();
        });
}

// 设置默认一个月范围
function setDefaultOneMonthRange() {
    const endDate = new Date();
    const startDate = new Date();
    startDate.setMonth(startDate.getMonth() - 1); // 默认分析一个月
    
    document.getElementById('tca-start-date').value = formatDate(startDate);
    document.getElementById('tca-end-date').value = formatDate(endDate);
}

// 格式化日期为YYYY-MM-DD
function formatDate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

// 运行交易成本分析
function runTCA() {
    // 获取分析参数
    const startDate = document.getElementById('tca-start-date').value;
    const endDate = document.getElementById('tca-end-date').value;
    
    // 验证参数
    if (!startDate || !endDate) {
        alert('请选择开始和结束日期');
        return;
    }
    
    if (startDate > endDate) {
        alert('开始日期不能晚于结束日期');
        return;
    }
    
    // 显示加载状态
    showLoading("正在进行交易成本分析...");
    
    // 发送分析请求 - 修改为使用POST方法和正确的端点
    fetch('/run_tca', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            start_date: startDate,
            end_date: endDate
        }),
    })
        .then(response => response.json())
        .then(data => {
            // 隐藏加载状态
            hideLoading();
            
            if (data.status === 'error') {
                showError(data.message);
                return;
            }
            
            // 显示成本指标
            displayTCAMetrics(data.metrics);
            
            // 显示分析图表
            displayTCAChart(data.chart_url);
            
            // 显示交易明细 - 修改为使用正确的数据结构
            displayTCATrades(data.trade_details);
        })
        .catch(error => {
            hideLoading();
            showError('请求失败: ' + error);
            console.error('运行交易成本分析失败:', error);
        });
}

// 显示成本指标
function displayTCAMetrics(metrics) {
    const container = document.getElementById('tca-metrics-container');
    
    // 处理字符串格式的指标值
    container.innerHTML = `
        <tr>
            <td>平均成本比例</td>
            <td>${metrics.avg_cost_ratio}</td>
        </tr>
        <tr>
            <td>佣金占比</td>
            <td>${metrics.commission_pct}</td>
        </tr>
        <tr>
            <td>滑点占比</td>
            <td>${metrics.slippage_pct}</td>
        </tr>
        <tr>
            <td>市场冲击占比</td>
            <td>${metrics.market_impact_pct}</td>
        </tr>
        <tr>
            <td>时机成本占比</td>
            <td>${metrics.timing_cost_pct}</td>
        </tr>
        <tr>
            <td>总交易次数</td>
            <td>${metrics.total_trades}</td>
        </tr>
        <tr>
            <td>总交易量</td>
            <td>${metrics.total_volume}</td>
        </tr>
        <tr>
            <td>总佣金</td>
            <td>${metrics.total_commission}</td>
        </tr>
        <tr>
            <td>平均滑点</td>
            <td>${metrics.avg_slippage}</td>
        </tr>
        <tr>
            <td>实施缺口</td>
            <td>${metrics.implementation_shortfall}</td>
        </tr>
    `;
}

// 显示分析图表
function displayTCAChart(chartUrl) {
    const container = document.getElementById('tca-chart-container');
    
    if (!chartUrl) {
        container.innerHTML = '<p class="text-center">没有足够的数据生成图表</p>';
        return;
    }
    
    // 添加时间戳以避免缓存
    const timestamp = new Date().getTime();
    container.innerHTML = `<img src="${chartUrl}?t=${timestamp}" class="img-fluid" alt="交易成本分析图表">`;
}

// 显示交易明细
function displayTCATrades(trades) {
    const container = document.getElementById('tca-trades-container');
    
    if (!trades || trades.length === 0) {
        container.innerHTML = '<tr><td colspan="10" class="text-center">没有交易记录</td></tr>';
        return;
    }
    
    let html = '';
    
    trades.forEach(trade => {
        // 格式化时间戳
        let timestamp = trade.timestamp;
        if (timestamp && typeof timestamp === 'string' && timestamp.includes('T')) {
            timestamp = timestamp.split('T')[0];
        }
        
        // 安全地访问属性，避免undefined错误
        const volume = trade.volume !== undefined ? parseFloat(trade.volume) : 0;
        const commission = trade.commission !== undefined ? parseFloat(trade.commission) : 0;
        const slippage = trade.slippage !== undefined ? parseFloat(trade.slippage) : 0;
        const marketImpact = trade.market_impact !== undefined ? parseFloat(trade.market_impact) : 0;
        const timingCost = trade.timing_cost !== undefined ? parseFloat(trade.timing_cost) : 0;
        const totalCost = trade.total_cost !== undefined ? parseFloat(trade.total_cost) : 0;
        const costRatio = trade.cost_ratio !== undefined ? parseFloat(trade.cost_ratio) : 0;
        
        html += `<tr>
            <td>${timestamp || '-'}</td>
            <td>${trade.pair_id || '-'}</td>
            <td>${trade.action === 'open' ? '开仓' : (trade.action === 'close' ? '平仓' : '止损')}</td>
            <td>${volume.toFixed(2)}</td>
            <td>${commission.toFixed(4)}</td>
            <td>${slippage.toFixed(4)}</td>
            <td>${marketImpact.toFixed(4)}</td>
            <td>${timingCost.toFixed(4)}</td>
            <td>${totalCost.toFixed(4)}</td>
            <td>${costRatio.toFixed(2)}%</td>
        </tr>`;
    });
    
    container.innerHTML = html;
}

// 显示加载状态
function showLoading(message) {
    // 检查是否已存在加载提示
    let loadingElement = document.getElementById('loading-indicator');
    
    if (!loadingElement) {
        // 创建加载提示
        loadingElement = document.createElement('div');
        loadingElement.id = 'loading-indicator';
        loadingElement.className = 'loading-indicator';
        loadingElement.style.position = 'fixed';
        loadingElement.style.top = '0';
        loadingElement.style.left = '0';
        loadingElement.style.width = '100%';
        loadingElement.style.height = '100%';
        loadingElement.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
        loadingElement.style.display = 'flex';
        loadingElement.style.flexDirection = 'column';
        loadingElement.style.justifyContent = 'center';
        loadingElement.style.alignItems = 'center';
        loadingElement.style.zIndex = '9999';
        loadingElement.style.color = 'white';
        
        const spinner = document.createElement('div');
        spinner.className = 'spinner-border text-primary';
        spinner.setAttribute('role', 'status');
        
        const spinnerText = document.createElement('span');
        spinnerText.className = 'visually-hidden';
        spinnerText.textContent = '加载中...';
        
        spinner.appendChild(spinnerText);
        
        const messageElement = document.createElement('div');
        messageElement.id = 'loading-message';
        messageElement.className = 'loading-message';
        messageElement.style.marginTop = '10px';
        messageElement.style.fontSize = '18px';
        messageElement.textContent = message || '加载中...';
        
        loadingElement.appendChild(spinner);
        loadingElement.appendChild(messageElement);
        
        document.body.appendChild(loadingElement);
    } else {
        // 更新现有加载提示的消息
        document.getElementById('loading-message').textContent = message || '加载中...';
        loadingElement.style.display = 'flex';
    }
}

// 隐藏加载状态
function hideLoading() {
    const loadingElement = document.getElementById('loading-indicator');
    if (loadingElement) {
        loadingElement.style.display = 'none';
    }
}

// 显示错误消息
function showError(message) {
    // 创建错误提示
    const errorElement = document.createElement('div');
    errorElement.className = 'alert alert-danger alert-dismissible fade show';
    errorElement.setAttribute('role', 'alert');
    errorElement.style.position = 'fixed';
    errorElement.style.top = '20px';
    errorElement.style.right = '20px';
    errorElement.style.zIndex = '9999';
    
    errorElement.textContent = message;
    
    const closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.className = 'btn-close';
    closeButton.setAttribute('data-bs-dismiss', 'alert');
    closeButton.setAttribute('aria-label', '关闭');
    
    errorElement.appendChild(closeButton);
    document.body.appendChild(errorElement);
    
    // 5秒后自动关闭
    setTimeout(() => {
        errorElement.remove();
    }, 5000);
}