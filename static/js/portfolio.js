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

// Current ADA price in USD (fetched on page load)
let adaPriceUsd = null;

// Tooltip element reference
let tooltipEl = null;

// Load positions on page load
document.addEventListener('DOMContentLoaded', function() {
    loadPortfolioPositions();
    initTooltips();
});

/**
 * Initialize tooltip event listeners (delegated)
 */
function initTooltips() {
    // Create tooltip element
    tooltipEl = document.createElement('div');
    tooltipEl.className = 'il-tooltip-popup';
    tooltipEl.style.display = 'none';
    document.body.appendChild(tooltipEl);

    // Delegated event listeners for dynamic content
    document.addEventListener('mouseenter', function(e) {
        if (e.target.classList.contains('il-tooltip')) {
            const text = e.target.getAttribute('data-tooltip');
            if (text) {
                tooltipEl.textContent = text;
                tooltipEl.style.display = 'block';
                positionTooltip(e.target);
            }
        }
    }, true);

    document.addEventListener('mouseleave', function(e) {
        if (e.target.classList.contains('il-tooltip')) {
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

    // Keep tooltip within viewport horizontally
    if (left + tooltipRect.width > window.innerWidth - 10) {
        left = window.innerWidth - tooltipRect.width - 10;
    }
    if (left < 10) left = 10;

    // If tooltip would go below viewport, show above instead
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
            console.log('ADA price:', adaPriceUsd);
        }
    } catch (e) {
        console.warn('Could not fetch ADA price:', e);
    }
}

/**
 * Convert ADA value to USD string
 */
function adaToUsd(adaValue) {
    if (!adaPriceUsd || !adaValue) return null;
    return adaValue * adaPriceUsd;
}

/**
 * Calculate price ratio change as a percentage string
 * @param {number} entryRatio - Price ratio at entry
 * @param {number} currentRatio - Current price ratio
 * @returns {string|null} - Formatted string like "+4.2%" or "-8.5%", or null if can't calculate
 */
function calculatePriceRatioDelta(entryRatio, currentRatio) {
    if (!entryRatio || !currentRatio || entryRatio <= 0) return null;
    const delta = ((currentRatio - entryRatio) / entryRatio) * 100;
    const sign = delta >= 0 ? '+' : '';
    return `${sign}${delta.toFixed(1)}%`;
}

/**
 * Generate IL tooltip text with napkin math breakdown
 * @param {number} entryRatio - Price ratio at entry
 * @param {number} currentRatio - Current price ratio
 * @param {number} ilPercent - Calculated IL percentage
 * @returns {string} - Tooltip text explaining the calculation
 */
function generateILTooltip(entryRatio, currentRatio, ilPercent) {
    if (!entryRatio || !currentRatio || ilPercent === null) {
        return 'Impermanent loss measures the difference between holding tokens in a liquidity pool vs holding them separately.';
    }

    const k = currentRatio / entryRatio;
    const priceChange = ((k - 1) * 100).toFixed(1);
    const priceChangeSign = k >= 1 ? '+' : '';

    return `IL Calculation:
• Entry ratio: ${entryRatio.toFixed(4)}
• Current ratio: ${currentRatio.toFixed(4)}
• Price change (k): ${priceChangeSign}${priceChange}%

Formula: IL = 2×√k / (1+k) − 1
• k = ${k.toFixed(4)}
• √k = ${Math.sqrt(k).toFixed(4)}
• IL = 2×${Math.sqrt(k).toFixed(4)} / ${(1 + k).toFixed(4)} − 1
• IL = ${ilPercent.toFixed(2)}%

A ${Math.abs(priceChange)}% price move → ${Math.abs(ilPercent).toFixed(2)}% IL`;
}

/**
 * Fetch all portfolio positions from the API
 */
async function loadPortfolioPositions() {
    hideError();
    setLoading(true);

    try {
        // Fetch ADA price first (in parallel with positions would be better but keep simple)
        await fetchAdaPrice();

        const response = await fetch('/api/portfolio/positions', {
            credentials: 'include'
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.message || data.error || 'Failed to load positions');
        }

        // Debug: Log raw positions data to check IL fields
        console.log('LP Positions from API:', data.lp_positions);
        console.log('Farm Positions from API:', data.farm_positions);
        if (data.farm_positions && data.farm_positions.length > 0) {
            console.log('First Farm position IL data:', {
                pool: data.farm_positions[0].pool,
                il_percent: data.farm_positions[0].il_percent,
                entry_date: data.farm_positions[0].entry_date,
                entry_price_ratio: data.farm_positions[0].entry_price_ratio,
                current_price_ratio: data.farm_positions[0].current_price_ratio
            });
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
        btn.innerHTML = '↻ Refreshing...';
    }

    await loadPortfolioPositions();

    if (btn) {
        btn.disabled = false;
        btn.innerHTML = '↻ Refresh';
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
                <div class="empty-state-icon">💧</div>
                <p>No positions found</p>
                <small>Provide liquidity or stake LP tokens on ${capitalizeFirst(protocol)} to see your positions here.</small>
            </div>
        `;
        return;
    }

    let html = '';

    // Single combined section for all LP positions
    html += `
        <div class="subsection-header">
            <span class="subsection-icon">💧</span>
            <h6>Liquidity Pool Positions</h6>
        </div>
    `;

    // Render farming positions first (with "Farming" pill)
    if (hasFarm) {
        data.farm.forEach(pos => {
            html += renderFarmPositionCard(pos);
        });
    }

    // Then render non-farming LP positions
    if (hasLp) {
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
    const adaValue = pos.usd_value ? `${formatNumber(pos.usd_value)} ADA` : '--';
    const usdValue = pos.usd_value ? adaToUsd(pos.usd_value) : null;
    const usdDisplay = usdValue ? `$${formatNumber(usdValue)}` : '';
    const apr = pos.current_apr ? `${formatNumber(pos.current_apr)}%` : '--';
    const poolShare = pos.pool_share_percent
        ? `${(pos.pool_share_percent * 100).toFixed(4)}%`
        : '--';

    const tokenA = pos.token_a || {};
    const tokenB = pos.token_b || {};
    const tokenAAmount = tokenA.amount ? formatNumber(tokenA.amount) : '0';
    const tokenBAmount = tokenB.amount ? formatNumber(tokenB.amount) : '0';

    // Impermanent loss display with price ratio delta
    const hasIL = pos.il_percent !== null && pos.il_percent !== undefined;
    const ilPercent = hasIL ? pos.il_percent : null;
    const ilClass = ilPercent !== null ? (ilPercent < 0 ? 'il-loss' : 'il-gain') : '';
    const ilDisplay = ilPercent !== null ? `${ilPercent > 0 ? '+' : ''}${ilPercent.toFixed(2)}%` : '--';
    const entryDate = pos.entry_date ? formatEntryDate(pos.entry_date) : null;

    // Calculate price ratio change percentage and tooltip
    const priceRatioDelta = calculatePriceRatioDelta(pos.entry_price_ratio, pos.current_price_ratio);
    const ilTooltip = generateILTooltip(pos.entry_price_ratio, pos.current_price_ratio, ilPercent);

    return `
        <div class="position-card">
            <div class="d-flex justify-content-between align-items-start mb-3">
                <div>
                    <span class="pool-name">${pos.pool || 'Unknown Pool'}</span>
                    ${entryDate ? `<span class="entry-date-badge">Since ${entryDate}</span>` : ''}
                </div>
                <div class="text-end">
                    <div class="value-display">${adaValue}</div>
                    ${usdDisplay ? `<div class="value-usd">${usdDisplay}</div>` : ''}
                </div>
            </div>
            <div class="row g-3">
                <div class="col-3">
                    <div class="data-label">APR</div>
                    <div class="apr-value">${apr}</div>
                </div>
                <div class="col-3">
                    <div class="data-label">Impermanent Loss</div>
                    <div class="il-value ${ilClass} il-tooltip" data-tooltip="${ilTooltip.replace(/"/g, '&quot;')}">${ilDisplay}${priceRatioDelta ? ` <span class="price-delta">(${priceRatioDelta})</span>` : ''}</div>
                </div>
                <div class="col-3">
                    <div class="data-label">Pool Share</div>
                    <div class="data-value token-amount">${poolShare}</div>
                </div>
                <div class="col-3">
                    <div class="data-label">Your Tokens</div>
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
 * Format entry date for display (e.g., "Dec 9, 2025")
 */
function formatEntryDate(isoDate) {
    if (!isoDate) return null;
    try {
        const date = new Date(isoDate);
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        return `${months[date.getMonth()]} ${date.getDate()}, ${date.getFullYear()}`;
    } catch (e) {
        return null;
    }
}

/**
 * Render a single farm position card
 */
function renderFarmPositionCard(pos) {
    // Value displayed in ADA with USD conversion
    const adaValue = pos.usd_value ? `${formatNumber(pos.usd_value)} ADA` : '--';
    const usdValue = pos.usd_value ? adaToUsd(pos.usd_value) : null;
    const usdDisplay = usdValue ? `$${formatNumber(usdValue)}` : '';
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

    // Impermanent loss display with price ratio delta (same as LP positions)
    const hasIL = pos.il_percent !== null && pos.il_percent !== undefined;
    const ilPercent = hasIL ? pos.il_percent : null;
    const ilClass = ilPercent !== null ? (ilPercent < 0 ? 'il-loss' : 'il-gain') : '';
    const ilDisplay = ilPercent !== null ? `${ilPercent > 0 ? '+' : ''}${ilPercent.toFixed(2)}%` : '--';
    const entryDate = pos.entry_date ? formatEntryDate(pos.entry_date) : null;

    // Calculate price ratio change percentage and tooltip
    const priceRatioDelta = calculatePriceRatioDelta(pos.entry_price_ratio, pos.current_price_ratio);
    const ilTooltip = generateILTooltip(pos.entry_price_ratio, pos.current_price_ratio, ilPercent);

    return `
        <div class="position-card farm-position">
            <div class="d-flex justify-content-between align-items-start mb-3">
                <div>
                    <span class="pool-name">${pos.pool || 'Unknown Pool'}</span>
                    <span class="farm-badge">Farming</span>
                    ${entryDate ? `<span class="entry-date-badge">Since ${entryDate}</span>` : ''}
                </div>
                <div class="text-end">
                    <div class="value-display">${adaValue}</div>
                    ${usdDisplay ? `<div class="value-usd">${usdDisplay}</div>` : ''}
                </div>
            </div>
            <div class="row g-3">
                <div class="col-3">
                    <div class="data-label">Farm APR</div>
                    <div class="apr-value">${apr}</div>
                </div>
                <div class="col-3">
                    <div class="data-label">Impermanent Loss</div>
                    <div class="il-value ${ilClass} il-tooltip" data-tooltip="${ilTooltip.replace(/"/g, '&quot;')}">${ilDisplay}${priceRatioDelta ? ` <span class="price-delta">(${priceRatioDelta})</span>` : ''}</div>
                </div>
                <div class="col-3">
                    <div class="data-label">Pool Share</div>
                    <div class="data-value token-amount">${poolShare}</div>
                </div>
                <div class="col-3">
                    <div class="data-label">Your Tokens</div>
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
                <div class="empty-state-icon">🏦</div>
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
    const colorClass = isSupply ? '' : 'text-danger';
    const typeBadgeClass = isSupply ? 'supply' : 'borrow';

    const usdValue = pos.usd_value ? `$${formatNumber(pos.usd_value)}` : '--';
    const apy = pos.current_apy ? `${formatNumber(pos.current_apy)}%` : '--';
    const amount = pos.amount ? formatNumber(pos.amount) : '0';

    return `
        <div class="position-card">
            <div class="d-flex justify-content-between align-items-start mb-3">
                <div>
                    <span class="pool-name">${pos.market || '?'}</span>
                    <span class="type-badge ${typeBadgeClass}">${isSupply ? 'Supply' : 'Borrow'}</span>
                </div>
                <div class="text-end">
                    <div class="value-display">${amount} ${pos.market || ''}</div>
                    <div class="value-usd">${usdValue}</div>
                </div>
            </div>
            <div class="row g-3">
                <div class="col-6">
                    <div class="data-label">${isSupply ? 'Earn APY' : 'Borrow APY'}</div>
                    <div class="apr-value ${colorClass}">${apy}</div>
                </div>
                <div class="col-6">
                    <div class="data-label">Protocol</div>
                    <div class="d-flex align-items-center">
                        <img src="${getProtocolLogo('liqwid')}" height="18" class="me-2" alt="Liqwid" style="border-radius: 4px;">
                        <span class="data-value">Liqwid</span>
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
    const usdEl = document.getElementById('totalValueUsd');

    if (el) {
        if (value && value > 0) {
            el.textContent = `${formatNumber(value)} ADA`;
        } else {
            el.textContent = '0 ADA';
        }
    }

    // Update USD value if element exists and we have ADA price
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
