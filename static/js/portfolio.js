/**
 * Portfolio page functionality
 * Fetches and displays user's DeFi positions organized by protocol
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

        // Organize positions by protocol
        const positionsByProtocol = organizeByProtocol(
            data.lp_positions || [],
            data.farm_positions || [],
            data.lending_positions || [],
            data.warning
        );

        // Render each protocol section
        renderProtocolSection('minswap', positionsByProtocol.minswap);
        renderProtocolSection('wingriders', positionsByProtocol.wingriders);
        renderProtocolSection('sundaeswap', positionsByProtocol.sundaeswap);
        renderLiqwidSection(positionsByProtocol.liqwid);

        updateTotalValue(data.total_usd_value || 0);

    } catch (error) {
        console.error('Error loading portfolio:', error);
        showError(error.message || 'Failed to load portfolio positions');
        renderEmptyStates();
        updateTotalValue(0);
    } finally {
        setLoading(false);
    }
}

/**
 * Organize positions by protocol
 */
function organizeByProtocol(lpPositions, farmPositions, lendingPositions, warning) {
    const protocols = {
        minswap: { lp: [], farm: [], warning: null },
        wingriders: { lp: [], farm: [], warning: null },
        sundaeswap: { lp: [], farm: [], warning: null },
        liqwid: { supply: [], borrow: [], warning: null }
    };

    // Store warning for LP section
    if (warning) {
        protocols.minswap.warning = warning;
        protocols.wingriders.warning = warning;
        protocols.sundaeswap.warning = warning;
    }

    // Organize LP positions
    lpPositions.forEach(pos => {
        const protocol = (pos.protocol || '').toLowerCase();
        if (protocols[protocol]) {
            protocols[protocol].lp.push(pos);
        }
    });

    // Organize farm positions
    farmPositions.forEach(pos => {
        const protocol = (pos.protocol || '').toLowerCase();
        if (protocols[protocol]) {
            protocols[protocol].farm.push(pos);
        }
    });

    // Organize lending positions
    lendingPositions.forEach(pos => {
        if (pos.type === 'supply') {
            protocols.liqwid.supply.push(pos);
        } else if (pos.type === 'borrow') {
            protocols.liqwid.borrow.push(pos);
        }
    });

    return protocols;
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
 * Render a DEX protocol section (Minswap, WingRiders, SundaeSwap)
 */
function renderProtocolSection(protocol, data) {
    const containerId = `${protocol}Section`;
    const container = document.getElementById(containerId);
    if (!container) return;

    const hasLp = data.lp && data.lp.length > 0;
    const hasFarm = data.farm && data.farm.length > 0;
    const hasWarning = data.warning;

    // Show warning if API key not configured
    if (hasWarning && !hasLp && !hasFarm) {
        container.innerHTML = `
            <div class="alert alert-warning" style="background: rgba(255, 193, 7, 0.15); border: 1px solid rgba(255, 193, 7, 0.3); color: #856404; border-radius: 8px; padding: 1rem;">
                <strong>Note:</strong> ${data.warning}
            </div>
        `;
        return;
    }

    if (!hasLp && !hasFarm) {
        container.innerHTML = `
            <div class="empty-state">
                <p>No positions found</p>
                <small>Provide liquidity or stake LP tokens on ${capitalizeFirst(protocol)} to see your positions here.</small>
            </div>
        `;
        return;
    }

    let html = '';

    // Yield Farming subsection
    if (hasFarm) {
        html += `
            <div class="subsection-header">
                <span class="subsection-icon">🌾</span>
                <h6>Yield Farming (Staked LP)</h6>
            </div>
        `;
        data.farm.forEach(pos => {
            html += renderFarmPositionCard(pos);
        });
    }

    // LP Positions subsection
    if (hasLp) {
        html += `
            <div class="subsection-header">
                <span class="subsection-icon">💧</span>
                <h6>Liquidity Pools (In Wallet)</h6>
            </div>
        `;
        data.lp.forEach(pos => {
            html += renderLPPositionCard(pos);
        });
    }

    container.innerHTML = html;
}

/**
 * Render a single LP position card
 */
function renderLPPositionCard(pos) {
    const usdValue = pos.usd_value ? `${formatNumber(pos.usd_value)} ADA` : '--';
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
 * Render a single farm position card
 */
function renderFarmPositionCard(pos) {
    // Value displayed in ADA (not USD)
    const adaValue = pos.usd_value ? `${formatNumber(pos.usd_value)} ADA` : '--';
    const apr = pos.current_apr ? `${formatNumber(pos.current_apr)}%` : '--';

    const tokenA = pos.token_a || {};
    const tokenB = pos.token_b || {};
    const tokenAAmount = tokenA.amount ? formatNumber(tokenA.amount) : '0';
    const tokenBAmount = tokenB.amount ? formatNumber(tokenB.amount) : '0';
    const tokenASymbol = tokenA.symbol || '?';
    const tokenBSymbol = tokenB.symbol || '?';

    // Pool share percentage
    const poolShare = pos.pool_share_percent
        ? `${(pos.pool_share_percent * 100).toFixed(4)}%`
        : '--';

    return `
        <div class="position-card farm-position">
            <div class="d-flex justify-content-between align-items-start">
                <div>
                    <strong>${pos.pool || 'Unknown Pool'}</strong>
                    <span class="farm-badge">staked</span>
                </div>
                <div class="text-end">
                    <div class="h5 mb-0">${adaValue}</div>
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
                    <div class="apr-label">Your Tokens</div>
                    <div class="token-amount">
                        ${tokenAAmount} ${tokenASymbol}<br>
                        ${tokenBAmount} ${tokenBSymbol}
                    </div>
                </div>
            </div>
        </div>
    `;
}

/**
 * Render Liqwid section with Supply and Borrow subsections
 */
function renderLiqwidSection(data) {
    const container = document.getElementById('liqwidSection');
    if (!container) return;

    const hasSupply = data.supply && data.supply.length > 0;
    const hasBorrow = data.borrow && data.borrow.length > 0;

    if (!hasSupply && !hasBorrow) {
        container.innerHTML = `
            <div class="empty-state">
                <p>No lending positions found</p>
                <small>Supply or borrow on Liqwid Finance to see your positions here.</small>
            </div>
        `;
        return;
    }

    let html = '';

    // Supply subsection
    if (hasSupply) {
        html += `
            <div class="subsection-header">
                <span class="subsection-icon" style="color: var(--sea-green);">📈</span>
                <h6>Supplying</h6>
            </div>
        `;
        data.supply.forEach(pos => {
            html += renderLendingPositionCard(pos);
        });
    }

    // Borrow subsection
    if (hasBorrow) {
        html += `
            <div class="subsection-header">
                <span class="subsection-icon" style="color: var(--crimson-carrot);">📉</span>
                <h6>Borrowing</h6>
            </div>
        `;
        data.borrow.forEach(pos => {
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
            el.textContent = `${formatNumber(value)} ADA`;
        } else {
            el.textContent = '0 ADA';
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
 * Capitalize first letter
 */
function capitalizeFirst(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
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
 * Render empty states for all protocol sections
 */
function renderEmptyStates() {
    const protocols = ['minswap', 'wingriders', 'sundaeswap'];
    protocols.forEach(protocol => {
        const container = document.getElementById(`${protocol}Section`);
        if (container) {
            container.innerHTML = `
                <div class="empty-state">
                    <p>No positions found</p>
                    <small>Unable to load positions at this time.</small>
                </div>
            `;
        }
    });

    const liqwidContainer = document.getElementById('liqwidSection');
    if (liqwidContainer) {
        liqwidContainer.innerHTML = `
            <div class="empty-state">
                <p>No lending positions found</p>
                <small>Unable to load positions at this time.</small>
            </div>
        `;
    }
}

/**
 * Show/hide loading state
 */
function setLoading(isLoading) {
    const containers = [
        'minswapSection',
        'wingridersSection',
        'sundaeswapSection',
        'liqwidSection'
    ];

    if (isLoading) {
        const loadingHtml = `
            <div class="loading-spinner">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p class="mt-2 text-muted">Loading positions...</p>
            </div>
        `;
        containers.forEach(id => {
            const container = document.getElementById(id);
            if (container) container.innerHTML = loadingHtml;
        });
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
