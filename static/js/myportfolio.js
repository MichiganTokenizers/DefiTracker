/**
 * My Portfolio page - New layout with two-column position cards
 * Layout based on sketch: Attributes (left) | Results (right)
 */

// Protocol logo mappings
const PROTOCOL_LOGOS = {
    'minswap': '/static/minswap-logo.png',
    'wingriders': '/static/wingriders-logo.svg',
    'sundaeswap': '/static/sundaeswap-logo.ico',
    'liqwid': '/static/liqwid-logo.png'
};

// Current ADA price in USD
let adaPriceUsd = null;

// Tooltip element reference
let tooltipEl = null;

// Load positions on page load
document.addEventListener('DOMContentLoaded', function() {
    loadPortfolioPositions();
    initTooltips();
});

/**
 * Initialize tooltip event listeners
 */
function initTooltips() {
    tooltipEl = document.createElement('div');
    tooltipEl.className = 'tooltip-popup';
    tooltipEl.style.display = 'none';
    document.body.appendChild(tooltipEl);

    document.addEventListener('mouseenter', function(e) {
        if (e.target.classList.contains('tooltip-trigger')) {
            const text = e.target.getAttribute('data-tooltip');
            if (text) {
                tooltipEl.textContent = text;
                tooltipEl.style.display = 'block';
                positionTooltip(e.target);
            }
        }
    }, true);

    document.addEventListener('mouseleave', function(e) {
        if (e.target.classList.contains('tooltip-trigger')) {
            tooltipEl.style.display = 'none';
        }
    }, true);
}

/**
 * Position tooltip below the target element
 */
function positionTooltip(target) {
    const rect = target.getBoundingClientRect();
    const tooltipRect = tooltipEl.getBoundingClientRect();

    let left = rect.left;
    let top = rect.bottom + 8;

    if (left + tooltipRect.width > window.innerWidth - 10) {
        left = window.innerWidth - tooltipRect.width - 10;
    }
    if (left < 10) left = 10;

    if (top + tooltipRect.height > window.innerHeight - 10) {
        top = rect.top - tooltipRect.height - 8;
    }

    tooltipEl.style.left = left + 'px';
    tooltipEl.style.top = top + 'px';
}

/**
 * Fetch current ADA price from CoinGecko
 */
async function fetchAdaPrice() {
    try {
        const response = await fetch('https://api.coingecko.com/api/v3/simple/price?ids=cardano&vs_currencies=usd');
        if (response.ok) {
            const data = await response.json();
            adaPriceUsd = data.cardano?.usd || null;
        }
    } catch (e) {
        console.warn('Could not fetch ADA price:', e);
    }
}

/**
 * Convert ADA value to USD
 */
function adaToUsd(adaValue) {
    if (!adaPriceUsd || !adaValue) return null;
    return adaValue * adaPriceUsd;
}

/**
 * Generate IL tooltip text
 */
function generateILTooltip(entryRatio, currentRatio, ilPercent) {
    if (!entryRatio || !currentRatio || ilPercent === null) {
        return 'Impermanent loss measures the difference between holding tokens in a liquidity pool vs holding them separately.';
    }

    const k = currentRatio / entryRatio;
    const priceChange = ((k - 1) * 100).toFixed(1);
    const priceChangeSign = k >= 1 ? '+' : '';

    return `IL Calculation:
Entry ratio: ${entryRatio.toFixed(4)}
Current ratio: ${currentRatio.toFixed(4)}
Price change: ${priceChangeSign}${priceChange}%

Formula: IL = 2*sqrt(k) / (1+k) - 1
Result: ${ilPercent.toFixed(2)}%`;
}

/**
 * Generate deposit history tooltip text
 */
function generateDepositHistoryTooltip(pos) {
    const originalDate = pos.original_entry_date
        ? formatEntryDate(pos.original_entry_date)
        : null;
    const history = pos.deposit_history || [];

    if (!history.length && !originalDate) {
        return '';
    }

    let lines = ['Position History:'];

    if (originalDate) {
        lines.push(`${originalDate} - Initial deposit`);
    }

    for (const event of history) {
        const date = event.date ? formatEntryDate(event.date) : '?';
        const type = event.event_type === 'deposit' ? 'Added to position' : 'Partial withdrawal';
        lines.push(`${date} - ${type}`);
    }

    return lines.join('\n');
}

/**
 * Generate yield tooltip text
 */
function generateYieldTooltip(pos) {
    if (!pos.actual_apr || !pos.days_held) {
        return 'Net Gain/Loss = Actual Yield + Impermanent Loss';
    }

    const yieldCalc = pos.actual_apr * (pos.days_held / 365);
    const ilPercent = pos.il_percent || 0;
    const netGainLoss = pos.net_gain_loss || (yieldCalc + ilPercent);

    return `Yield Calculation:
Avg APR: ${pos.actual_apr.toFixed(2)}%
Days held: ${pos.days_held}
Actual Yield: ${yieldCalc.toFixed(2)}%

Net = Yield + IL
${yieldCalc.toFixed(2)}% + ${ilPercent.toFixed(2)}%
= ${netGainLoss.toFixed(2)}%`;
}

/**
 * Fetch all portfolio positions from the API
 */
async function loadPortfolioPositions() {
    hideError();
    setLoading(true);

    try {
        await fetchAdaPrice();

        const response = await fetch('/api/portfolio/positions', {
            credentials: 'include'
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.message || data.error || 'Failed to load positions');
        }

        const positionsByProtocol = organizeByProtocol(
            data.lp_positions || [],
            data.farm_positions || [],
            data.lending_positions || [],
            data.warning
        );

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

    if (warning) {
        protocols.minswap.warning = warning;
        protocols.wingriders.warning = warning;
        protocols.sundaeswap.warning = warning;
    }

    lpPositions.forEach(pos => {
        const protocol = (pos.protocol || '').toLowerCase();
        if (protocols[protocol]) {
            protocols[protocol].lp.push(pos);
        }
    });

    farmPositions.forEach(pos => {
        const protocol = (pos.protocol || '').toLowerCase();
        if (protocols[protocol]) {
            protocols[protocol].farm.push(pos);
        }
    });

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
 * Refresh positions
 */
async function refreshPositions() {
    const btn = document.getElementById('refreshBtn');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = 'Refreshing...';
    }

    await loadPortfolioPositions();

    if (btn) {
        btn.disabled = false;
        btn.innerHTML = 'Refresh';
    }
}

/**
 * Render a DEX protocol section
 */
function renderProtocolSection(protocol, data) {
    const containerId = `${protocol}Section`;
    const container = document.getElementById(containerId);
    if (!container) return;

    const hasLp = data.lp && data.lp.length > 0;
    const hasFarm = data.farm && data.farm.length > 0;
    const hasWarning = data.warning;

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
                <div class="empty-state-icon">💧</div>
                <p>No positions found</p>
                <small>Provide liquidity on ${capitalizeFirst(protocol)} to see your positions here.</small>
            </div>
        `;
        return;
    }

    let html = '';

    // Render farming positions first
    if (hasFarm) {
        data.farm.forEach(pos => {
            html += renderPositionCard(pos, true);
        });
    }

    // Then render non-farming LP positions
    if (hasLp) {
        data.lp.forEach(pos => {
            html += renderPositionCard(pos, false);
        });
    }

    container.innerHTML = html;
}

/**
 * Render a single LP position card with two-column layout
 * Left: Attributes (Start, Duration, Value, Pool Share, 1d APR, Tokens)
 * Right: Results (Avg APR, Actual Yield, Impermanent Loss, Net Gain/Loss)
 */
function renderPositionCard(pos, isFarm) {
    // Extract data
    const poolName = pos.pool || 'Unknown Pool';

    // Left column values - show original start date, use weighted date for calculations
    const displayDate = pos.original_entry_date || pos.entry_date;
    const entryDate = displayDate ? formatEntryDate(displayDate) : '--';
    const daysHeld = pos.days_held || 0;
    const duration = formatDuration(daysHeld);
    const depositTooltip = generateDepositHistoryTooltip(pos);

    const adaValue = pos.usd_value ? `${formatNumber(pos.usd_value)} ADA` : '--';
    const usdValue = pos.usd_value ? adaToUsd(pos.usd_value) : null;
    const usdDisplay = usdValue ? `$${formatNumber(usdValue)}` : '';

    const poolShare = pos.pool_share_percent
        ? `${(pos.pool_share_percent * 100).toFixed(4)}%`
        : '--';

    const apr1d = pos.apr_1d ? `${formatNumber(pos.apr_1d)}%` : (pos.current_apr ? `${formatNumber(pos.current_apr)}%` : '--');

    const tokenA = pos.token_a || {};
    const tokenB = pos.token_b || {};
    const tokenAAmount = tokenA.amount ? formatNumber(tokenA.amount) : '0';
    const tokenBAmount = tokenB.amount ? formatNumber(tokenB.amount) : '0';
    const tokenASymbol = tokenA.symbol || '?';
    const tokenBSymbol = tokenB.symbol || '?';

    // Right column values
    const avgApr = pos.actual_apr ? `${formatNumber(pos.actual_apr)}%` : '--';

    const actualYield = pos.actual_yield !== null && pos.actual_yield !== undefined
        ? `${pos.actual_yield >= 0 ? '+' : ''}${pos.actual_yield.toFixed(2)}%` : '--';
    const yieldClass = pos.actual_yield !== null
        ? (pos.actual_yield >= 0 ? 'positive' : 'negative') : '';

    const hasIL = pos.il_percent !== null && pos.il_percent !== undefined;
    const ilPercent = hasIL ? pos.il_percent : null;
    const ilDisplay = ilPercent !== null ? `${ilPercent > 0 ? '+' : ''}${ilPercent.toFixed(2)}%` : '--';
    const ilClass = ilPercent !== null ? (ilPercent < 0 ? 'negative' : 'positive') : '';
    const ilTooltip = generateILTooltip(pos.entry_price_ratio, pos.current_price_ratio, ilPercent);

    const netGainLoss = pos.net_gain_loss !== null && pos.net_gain_loss !== undefined
        ? `${pos.net_gain_loss >= 0 ? '+' : ''}${pos.net_gain_loss.toFixed(2)}%` : '--';
    const netClass = pos.net_gain_loss !== null
        ? (pos.net_gain_loss >= 0 ? 'positive' : 'negative') : '';
    const yieldTooltip = generateYieldTooltip(pos);

    const farmClass = isFarm ? 'farm-position' : '';
    const farmBadge = isFarm ? '<span class="farm-badge">Farming</span>' : '';

    return `
        <div class="position-card ${farmClass}">
            <div class="pool-name">${poolName}${farmBadge}</div>

            <div class="position-columns">
                <!-- Left Column: Attributes -->
                <div class="attributes-column">
                    <div class="column-header">Attributes</div>

                    <div class="attr-row">
                        <span class="attr-label">Start</span>
                        <span class="attr-value${depositTooltip ? ' tooltip-trigger' : ''}"${depositTooltip ? ` data-tooltip="${depositTooltip.replace(/"/g, '&quot;')}"` : ''}>${entryDate}</span>
                    </div>

                    <div class="attr-row">
                        <span class="attr-label">Value</span>
                        <span class="attr-value">${adaValue}${usdDisplay ? ` <span class="small">(${usdDisplay})</span>` : ''}</span>
                    </div>

                    <div class="attr-row">
                        <span class="attr-label">Pool Share</span>
                        <span class="attr-value mono">${poolShare}</span>
                    </div>

                    <div class="attr-row">
                        <span class="attr-label">1d APR</span>
                        <span class="attr-value">${apr1d}</span>
                    </div>

                    <div class="attr-row">
                        <span class="attr-label">Tokens</span>
                        <div class="tokens-display">
                            <div class="token-line">${tokenAAmount} ${tokenASymbol}</div>
                            <div class="token-line">${tokenBAmount} ${tokenBSymbol}</div>
                        </div>
                    </div>
                </div>

                <!-- Right Column: Results -->
                <div class="results-column">
                    <div class="column-header">Results</div>

                    <div class="result-row">
                        <span class="result-label">Duration</span>
                        <span class="result-value">${duration}</span>
                    </div>

                    <div class="result-row">
                        <span class="result-label">Avg APR</span>
                        <span class="result-value">${avgApr}</span>
                    </div>

                    <div class="result-row">
                        <span class="result-label">Actual Yield</span>
                        <span class="result-value ${yieldClass}">${actualYield}</span>
                    </div>

                    <div class="result-row">
                        <span class="result-label">Impermanent Loss</span>
                        <span class="result-value ${ilClass} tooltip-trigger" data-tooltip="${ilTooltip.replace(/"/g, '&quot;')}">${ilDisplay}</span>
                    </div>

                    <div class="net-gain-row">
                        <div class="result-row">
                            <span class="net-gain-label">Net Gain/Loss</span>
                            <span class="net-gain-value ${netClass} tooltip-trigger" data-tooltip="${yieldTooltip.replace(/"/g, '&quot;')}">${netGainLoss}</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

/**
 * Format entry date (e.g., "Dec 8, '25")
 */
function formatEntryDate(isoDate) {
    if (!isoDate) return null;
    try {
        const date = new Date(isoDate);
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        const year = date.getFullYear().toString().slice(-2);
        return `${months[date.getMonth()]} ${date.getDate()}, '${year}`;
    } catch (e) {
        return null;
    }
}

/**
 * Format duration in days
 */
function formatDuration(days) {
    if (!days || days <= 0) return '--';
    if (days === 1) return '1 day';
    return `${days} days`;
}

/**
 * Render Liqwid section
 */
function renderLiqwidSection(data) {
    const container = document.getElementById('liqwidSection');
    if (!container) return;

    const hasSupply = data.supply && data.supply.length > 0;
    const hasBorrow = data.borrow && data.borrow.length > 0;

    if (!hasSupply && !hasBorrow) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">🏦</div>
                <p>No lending positions found</p>
                <small>Supply or borrow on Liqwid Finance to see your positions here.</small>
            </div>
        `;
        return;
    }

    let html = '';

    if (hasSupply) {
        html += `
            <div class="subsection-header">
                <span class="subsection-icon" style="color: var(--sea-green);">📈</span>
                <h6>Supplying</h6>
            </div>
        `;
        data.supply.forEach(pos => {
            html += renderLendingCard(pos);
        });
    }

    if (hasBorrow) {
        html += `
            <div class="subsection-header">
                <span class="subsection-icon" style="color: var(--crimson-carrot);">📉</span>
                <h6>Borrowing</h6>
            </div>
        `;
        data.borrow.forEach(pos => {
            html += renderLendingCard(pos);
        });
    }

    container.innerHTML = html;
}

/**
 * Render a lending position card
 */
function renderLendingCard(pos) {
    const isSupply = pos.type === 'supply';
    const typeBadgeClass = isSupply ? 'supply' : 'borrow';

    const usdValue = pos.usd_value ? `$${formatNumber(pos.usd_value)}` : '--';
    const apy = pos.current_apy ? `${formatNumber(pos.current_apy)}%` : '--';
    const amount = pos.amount ? formatNumber(pos.amount) : '0';

    return `
        <div class="lending-card">
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <span class="pool-name">${pos.market || '?'}</span>
                    <span class="type-badge ${typeBadgeClass}">${isSupply ? 'Supply' : 'Borrow'}</span>
                </div>
                <div class="text-end">
                    <div style="font-size: 1.1rem; font-weight: 600;">${amount} ${pos.market || ''}</div>
                    <div style="font-size: 0.85rem; color: var(--text-secondary);">${usdValue}</div>
                </div>
            </div>
            <div class="mt-3">
                <span class="attr-label">${isSupply ? 'Earn APY' : 'Borrow APY'}</span>
                <span class="result-value ${isSupply ? 'positive' : 'negative'}" style="margin-left: 0.5rem;">${apy}</span>
            </div>
        </div>
    `;
}

/**
 * Update total portfolio value
 */
function updateTotalValue(value) {
    const el = document.getElementById('totalValue');
    const usdEl = document.getElementById('totalValueUsd');

    if (el) {
        if (value && value > 0) {
            el.textContent = `${formatNumber(value)} ADA`;
        } else {
            el.textContent = '0 ADA';
        }
    }

    if (usdEl) {
        const usdValue = value && adaPriceUsd ? value * adaPriceUsd : null;
        if (usdValue) {
            usdEl.textContent = `≈ $${formatNumber(usdValue)}`;
            usdEl.style.display = 'block';
        } else {
            usdEl.style.display = 'none';
        }
    }
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
 * Render empty states
 */
function renderEmptyStates() {
    const protocols = ['minswap', 'wingriders', 'sundaeswap'];
    protocols.forEach(protocol => {
        const container = document.getElementById(`${protocol}Section`);
        if (container) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">💧</div>
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
                <div class="empty-state-icon">🏦</div>
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
                <div class="spinner-border" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p>Loading positions...</p>
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
