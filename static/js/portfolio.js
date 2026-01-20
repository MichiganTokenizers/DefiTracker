/**
 * Portfolio page functionality
 * Fetches and displays user's DeFi positions from connected wallet
 */

// Protocol logo mappings
const PROTOCOL_LOGOS = {
    'minswap': '/static/minswap-logo.png',
    'wingriders': '/static/wingriders-logo.svg',
    'sundaeswap': '/static/sundaeswap-logo.ico',
    'liqwid': '/static/liqwid-logo.png'
};

// Load positions on page load
document.addEventListener('DOMContentLoaded', function() {
    loadPortfolioPositions();
});

/**
 * Fetch all portfolio positions from the API
 */
async function loadPortfolioPositions() {
    hideError();
    setLoading(true);

    try {
        const response = await fetch('/api/portfolio/positions', {
            credentials: 'include'
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.message || data.error || 'Failed to load positions');
        }

        renderLPPositions(data.lp_positions || [], data.warning);
        renderFarmPositions(data.farm_positions || []);
        renderLendingPositions(data.lending_positions || []);
        updateTotalValue(data.total_usd_value || 0);

    } catch (error) {
        console.error('Error loading portfolio:', error);
        showError(error.message || 'Failed to load portfolio positions');
        renderLPPositions([]);
        renderFarmPositions([]);
        renderLendingPositions([]);
        updateTotalValue(0);
    } finally {
        setLoading(false);
    }
}

/**
 * Refresh positions (called by refresh button)
 */
async function refreshPositions() {
    const btn = document.getElementById('refreshBtn');
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Refreshing...';
    }

    await loadPortfolioPositions();

    if (btn) {
        btn.disabled = false;
        btn.textContent = 'Refresh';
    }
}

/**
 * Render LP positions
 */
function renderLPPositions(positions, warning) {
    const container = document.getElementById('lpPositionsContainer');

    // Show warning if API key not configured
    if (warning) {
        container.innerHTML = `
            <div class="alert alert-warning" style="background: rgba(255, 193, 7, 0.15); border: 1px solid rgba(255, 193, 7, 0.3); color: #856404; border-radius: 8px; padding: 1rem; margin-bottom: 1rem;">
                <strong>Note:</strong> ${warning}
            </div>
        `;
        return;
    }

    if (!positions || positions.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>No LP positions found</p>
                <small>Provide liquidity on Minswap, WingRiders, or SundaeSwap to see your positions here.</small>
            </div>
        `;
        return;
    }

    // Group positions by protocol
    const grouped = {};
    positions.forEach(pos => {
        const protocol = pos.protocol || 'unknown';
        if (!grouped[protocol]) {
            grouped[protocol] = [];
        }
        grouped[protocol].push(pos);
    });

    let html = '';

    // Render positions grouped by protocol
    for (const [protocol, protocolPositions] of Object.entries(grouped)) {
        html += `<div class="protocol-group mb-3">`;
        html += `<h6 class="text-muted mb-2" style="font-size: 0.8rem; text-transform: uppercase;">
            <img src="${getProtocolLogo(protocol)}" height="16" class="me-1" alt="${protocol}">
            ${protocol}
        </h6>`;

        protocolPositions.forEach(pos => {
            html += renderLPPositionCard(pos);
        });

        html += `</div>`;
    }

    container.innerHTML = html;
}

/**
 * Render a single LP position card
 */
function renderLPPositionCard(pos) {
    const usdValue = pos.usd_value ? `$${formatNumber(pos.usd_value)}` : '--';
    const apr = pos.current_apr ? `${formatNumber(pos.current_apr)}%` : '--';
    const poolShare = pos.pool_share_percent
        ? `${(pos.pool_share_percent * 100).toFixed(4)}%`
        : '--';

    const tokenA = pos.token_a || {};
    const tokenB = pos.token_b || {};
    const tokenAAmount = tokenA.amount ? formatNumber(tokenA.amount) : '0';
    const tokenBAmount = tokenB.amount ? formatNumber(tokenB.amount) : '0';

    return `
        <div class="position-card">
            <div class="d-flex justify-content-between align-items-start">
                <div>
                    <strong>${pos.pool || 'Unknown Pool'}</strong>
                    <span class="protocol-badge ${pos.protocol}">${pos.protocol}</span>
                </div>
                <div class="text-end">
                    <div class="h5 mb-0">${usdValue}</div>
                </div>
            </div>
            <div class="row mt-2">
                <div class="col-4">
                    <div class="apr-label">APR</div>
                    <div class="apr-value">${apr}</div>
                </div>
                <div class="col-4">
                    <div class="apr-label">Pool Share</div>
                    <div class="token-amount">${poolShare}</div>
                </div>
                <div class="col-4">
                    <div class="apr-label">Tokens</div>
                    <div class="token-amount">
                        ${tokenAAmount} ${tokenA.symbol || '?'}<br>
                        ${tokenBAmount} ${tokenB.symbol || '?'}
                    </div>
                </div>
            </div>
        </div>
    `;
}

/**
 * Render farm (staked LP) positions
 */
function renderFarmPositions(positions) {
    const container = document.getElementById('farmPositionsContainer');
    if (!container) return;

    if (!positions || positions.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>No staked positions found</p>
                <small>Stake your LP tokens in yield farms to see them here.</small>
            </div>
        `;
        return;
    }

    // Group positions by protocol
    const grouped = {};
    positions.forEach(pos => {
        const protocol = pos.protocol || 'unknown';
        if (!grouped[protocol]) {
            grouped[protocol] = [];
        }
        grouped[protocol].push(pos);
    });

    let html = '';

    // Render positions grouped by protocol
    for (const [protocol, protocolPositions] of Object.entries(grouped)) {
        html += `<div class="protocol-group mb-3">`;
        html += `<h6 class="text-muted mb-2" style="font-size: 0.8rem; text-transform: uppercase;">
            <img src="${getProtocolLogo(protocol)}" height="16" class="me-1" alt="${protocol}">
            ${protocol}
        </h6>`;

        protocolPositions.forEach(pos => {
            html += renderFarmPositionCard(pos);
        });

        html += `</div>`;
    }

    container.innerHTML = html;
}

/**
 * Render a single farm position card
 */
function renderFarmPositionCard(pos) {
    const usdValue = pos.usd_value ? `$${formatNumber(pos.usd_value)}` : '--';
    const apr = pos.current_apr ? `${formatNumber(pos.current_apr)}%` : '--';
    const rewards = pos.rewards_earned ? formatNumber(pos.rewards_earned) : '--';

    const tokenA = pos.token_a || {};
    const tokenB = pos.token_b || {};
    const tokenAAmount = tokenA.amount ? formatNumber(tokenA.amount) : '0';
    const tokenBAmount = tokenB.amount ? formatNumber(tokenB.amount) : '0';

    // Format LP amount (usually large numbers)
    const lpAmount = pos.lp_amount ? formatLPAmount(pos.lp_amount) : '0';

    return `
        <div class="position-card farm-position">
            <div class="d-flex justify-content-between align-items-start">
                <div>
                    <strong>${pos.pool || 'Unknown Pool'}</strong>
                    <span class="protocol-badge ${pos.protocol}">${pos.protocol}</span>
                    <span class="farm-badge">staked</span>
                </div>
                <div class="text-end">
                    <div class="h5 mb-0">${usdValue}</div>
                </div>
            </div>
            <div class="row mt-2">
                <div class="col-4">
                    <div class="apr-label">APR</div>
                    <div class="apr-value">${apr}</div>
                </div>
                <div class="col-4">
                    <div class="apr-label">LP Tokens</div>
                    <div class="token-amount">${lpAmount}</div>
                </div>
                <div class="col-4">
                    <div class="apr-label">Rewards</div>
                    <div class="token-amount">${rewards}</div>
                </div>
            </div>
        </div>
    `;
}

/**
 * Format LP token amounts (usually very large numbers)
 */
function formatLPAmount(amount) {
    const n = parseFloat(amount);
    if (isNaN(n)) return '0';

    if (n >= 1e12) {
        return (n / 1e12).toFixed(2) + 'T';
    } else if (n >= 1e9) {
        return (n / 1e9).toFixed(2) + 'B';
    } else if (n >= 1e6) {
        return (n / 1e6).toFixed(2) + 'M';
    } else if (n >= 1e3) {
        return (n / 1e3).toFixed(2) + 'K';
    } else {
        return n.toFixed(2);
    }
}

/**
 * Render lending positions
 */
function renderLendingPositions(positions) {
    const container = document.getElementById('lendingPositionsContainer');

    if (!positions || positions.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>No lending positions found</p>
                <small>Supply or borrow on Liqwid to see your positions here.</small>
            </div>
        `;
        return;
    }

    // Separate supply and borrow positions
    const supplies = positions.filter(p => p.type === 'supply');
    const borrows = positions.filter(p => p.type === 'borrow');

    let html = '';

    // Render supply positions
    if (supplies.length > 0) {
        html += `<h6 class="text-success mb-2" style="font-size: 0.85rem;">
            <span style="display: inline-block; width: 8px; height: 8px; background: var(--sea-green); border-radius: 50%; margin-right: 6px;"></span>
            Supplying
        </h6>`;
        supplies.forEach(pos => {
            html += renderLendingPositionCard(pos);
        });
    }

    // Render borrow positions
    if (borrows.length > 0) {
        html += `<h6 class="text-danger mb-2 mt-3" style="font-size: 0.85rem;">
            <span style="display: inline-block; width: 8px; height: 8px; background: var(--crimson-carrot); border-radius: 50%; margin-right: 6px;"></span>
            Borrowing
        </h6>`;
        borrows.forEach(pos => {
            html += renderLendingPositionCard(pos);
        });
    }

    container.innerHTML = html;
}

/**
 * Render a single lending position card
 */
function renderLendingPositionCard(pos) {
    const isSupply = pos.type === 'supply';
    const colorClass = isSupply ? 'text-success' : 'text-danger';
    const typeBadgeClass = isSupply ? 'supply' : 'borrow';

    const usdValue = pos.usd_value ? `$${formatNumber(pos.usd_value)}` : '--';
    const apy = pos.current_apy ? `${formatNumber(pos.current_apy)}%` : '--';
    const amount = pos.amount ? formatNumber(pos.amount) : '0';

    return `
        <div class="position-card">
            <div class="d-flex justify-content-between align-items-start">
                <div>
                    <strong>${pos.market || '?'}</strong>
                    <span class="type-badge ${typeBadgeClass}">${pos.type}</span>
                    <span class="protocol-badge liqwid">liqwid</span>
                </div>
                <div class="text-end">
                    <div class="h6 mb-0">${amount} ${pos.market || ''}</div>
                    <small class="text-muted">${usdValue}</small>
                </div>
            </div>
            <div class="row mt-2">
                <div class="col-6">
                    <div class="apr-label">APY</div>
                    <div class="apr-value ${colorClass}">${apy}</div>
                </div>
                <div class="col-6">
                    <div class="apr-label">Protocol</div>
                    <div>
                        <img src="${getProtocolLogo('liqwid')}" height="16" class="me-1" alt="Liqwid">
                        Liqwid
                    </div>
                </div>
            </div>
        </div>
    `;
}

/**
 * Update the total portfolio value display
 */
function updateTotalValue(value) {
    const el = document.getElementById('totalValue');
    if (el) {
        if (value && value > 0) {
            el.textContent = `$${formatNumber(value)}`;
        } else {
            el.textContent = '$0.00';
        }
    }
}

/**
 * Get protocol logo URL
 */
function getProtocolLogo(protocol) {
    return PROTOCOL_LOGOS[protocol?.toLowerCase()] || '/static/cardano-symbol.svg';
}

/**
 * Format number with appropriate precision
 */
function formatNumber(num) {
    if (num === null || num === undefined) return '0';

    const n = parseFloat(num);
    if (isNaN(n)) return '0';

    if (n >= 1000000) {
        return (n / 1000000).toFixed(2) + 'M';
    } else if (n >= 1000) {
        return (n / 1000).toFixed(2) + 'K';
    } else if (n >= 100) {
        return n.toFixed(2);
    } else if (n >= 1) {
        return n.toFixed(2);
    } else if (n >= 0.01) {
        return n.toFixed(4);
    } else {
        return n.toFixed(6);
    }
}

/**
 * Show/hide loading state
 */
function setLoading(isLoading) {
    const lpContainer = document.getElementById('lpPositionsContainer');
    const farmContainer = document.getElementById('farmPositionsContainer');
    const lendingContainer = document.getElementById('lendingPositionsContainer');

    if (isLoading) {
        const loadingHtml = `
            <div class="loading-spinner">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p class="mt-2 text-muted">Loading positions...</p>
            </div>
        `;
        if (lpContainer) lpContainer.innerHTML = loadingHtml;
        if (farmContainer) farmContainer.innerHTML = loadingHtml;
        if (lendingContainer) lendingContainer.innerHTML = loadingHtml;
    }
}

/**
 * Show error message
 */
function showError(message) {
    const alertEl = document.getElementById('errorAlert');
    const messageEl = document.getElementById('errorMessage');

    if (alertEl && messageEl) {
        messageEl.textContent = message;
        alertEl.classList.remove('d-none');
    }
}

/**
 * Hide error message
 */
function hideError() {
    const alertEl = document.getElementById('errorAlert');
    if (alertEl) {
        alertEl.classList.add('d-none');
    }
}
