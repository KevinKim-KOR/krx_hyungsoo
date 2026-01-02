// KRX Alertor Dashboard JavaScript

const API_BASE = '';

// Navigation
document.addEventListener('DOMContentLoaded', () => {
    // Navigation click handlers
    const navLinks = document.querySelectorAll('.nav-link:not(.api-link)');
    const sections = document.querySelectorAll('.section');
    
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = link.getAttribute('href').substring(1);
            
            // Update active nav link
            navLinks.forEach(l => l.classList.remove('active'));
            link.classList.add('active');
            
            // Update active section
            sections.forEach(s => s.classList.remove('active'));
            document.getElementById(targetId).classList.add('active');
            
            // Load data for the section
            loadSectionData(targetId);
        });
    });
    
    // Load initial data
    loadSectionData('home');
});

// Load data for specific section
async function loadSectionData(sectionId) {
    switch(sectionId) {
        case 'home':
            await loadDashboardData();
            break;
        case 'backtest':
            await loadBacktestData();
            break;
        case 'stop-loss':
            await loadStopLossData();
            break;
        case 'market':
            await loadMarketData();
            break;
    }
}

// Load dashboard data
async function loadDashboardData() {
    try {
        const response = await fetch(`${API_BASE}/api/v1/dashboard/summary`);
        const data = await response.json();
        
        document.getElementById('total-assets').textContent = formatCurrency(data.total_assets);
        document.getElementById('cash').textContent = formatCurrency(data.cash);
        document.getElementById('stocks-value').textContent = formatCurrency(data.stocks_value);
        document.getElementById('total-return').textContent = formatPercent(data.total_return_pct);
    } catch (error) {
        console.error('대시보드 데이터 로드 실패:', error);
        document.getElementById('total-assets').textContent = '데이터 없음';
        document.getElementById('cash').textContent = '데이터 없음';
        document.getElementById('stocks-value').textContent = '데이터 없음';
        document.getElementById('total-return').textContent = '데이터 없음';
    }
}

// Load backtest data
async function loadBacktestData() {
    try {
        const response = await fetch(`${API_BASE}/api/v1/backtest/results`);
        
        if (response.status === 404) {
            document.getElementById('jason-cagr').textContent = '데이터 없음';
            document.getElementById('jason-sharpe').textContent = '데이터 없음';
            document.getElementById('hybrid-cagr').textContent = '데이터 없음';
            document.getElementById('hybrid-sharpe').textContent = '데이터 없음';
            return;
        }
        
        const data = await response.json();
        
        const jason = data.find(d => d.strategy === 'Jason');
        const hybrid = data.find(d => d.strategy === 'Hybrid');
        
        if (jason) {
            document.getElementById('jason-cagr').textContent = formatPercent(jason.cagr);
            document.getElementById('jason-sharpe').textContent = jason.sharpe.toFixed(2);
        }
        
        if (hybrid) {
            document.getElementById('hybrid-cagr').textContent = formatPercent(hybrid.cagr);
            document.getElementById('hybrid-sharpe').textContent = hybrid.sharpe.toFixed(2);
        }
    } catch (error) {
        console.error('백테스트 데이터 로드 실패:', error);
    }
}

// Load stop loss data
async function loadStopLossData() {
    try {
        const response = await fetch(`${API_BASE}/api/v1/stop-loss/strategies`);
        const data = await response.json();
        
        const tbody = document.querySelector('#stop-loss-table tbody');
        tbody.innerHTML = '';
        
        data.forEach(strategy => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><strong>${strategy.name}</strong><br><small>${strategy.description}</small></td>
                <td>${strategy.stop_loss_count}</td>
                <td>${strategy.safe_count}</td>
                <td><strong style="color: var(--success)">+${strategy.improvement.toFixed(2)}%p</strong></td>
            `;
            tbody.appendChild(row);
        });
    } catch (error) {
        console.error('손절 전략 데이터 로드 실패:', error);
    }
}

// Load market data
async function loadMarketData() {
    try {
        const response = await fetch(`${API_BASE}/api/v1/market/regime`);
        const data = await response.json();
        
        const regimeText = {
            'bull': '🐂 상승장',
            'neutral': '➡️ 중립장',
            'bear': '🐻 하락장'
        };
        
        document.getElementById('market-regime').textContent = regimeText[data.current_regime] || data.current_regime;
        document.getElementById('market-confidence').textContent = formatPercent(data.confidence);
        document.getElementById('market-volatility').textContent = data.volatility.toUpperCase();
    } catch (error) {
        console.error('시장 데이터 로드 실패:', error);
    }
}

// Utility functions
function formatCurrency(value) {
    if (value === null || value === undefined) return '₩0';
    return '₩' + Math.round(value).toLocaleString('ko-KR');
}

function formatPercent(value) {
    if (value === null || value === undefined) return '0%';
    return value.toFixed(2) + '%';
}
