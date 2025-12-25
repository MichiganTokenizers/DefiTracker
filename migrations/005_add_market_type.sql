-- Add market_type column to kinetic_apy_snapshots
-- Distinguishes between Primary market and ISO markets

-- ============================================
-- 1. Add market_type column
-- ============================================
ALTER TABLE kinetic_apy_snapshots 
ADD COLUMN IF NOT EXISTS market_type VARCHAR(50) DEFAULT 'Primary';

-- ============================================
-- 2. Update existing records
-- ============================================
-- Set existing records to appropriate market type based on asset symbol
-- ISO Market: FXRP-USDT0-stXRP tokens
UPDATE kinetic_apy_snapshots kas
SET market_type = 'ISO: FXRP-USDT0-stXRP'
FROM assets a
WHERE kas.asset_id = a.asset_id 
AND a.symbol IN ('FXRP', 'USDT0', 'stXRP');

-- ISO Market: JOULE-USDC-FLR tokens  
UPDATE kinetic_apy_snapshots kas
SET market_type = 'ISO: JOULE-USDC-FLR'
FROM assets a
WHERE kas.asset_id = a.asset_id 
AND a.symbol IN ('FLR', 'USDC', 'JOULE');

-- Primary market tokens (all others)
UPDATE kinetic_apy_snapshots kas
SET market_type = 'Primary'
FROM assets a
WHERE kas.asset_id = a.asset_id 
AND a.symbol IN ('sFLR', 'USDC.e', 'USDT', 'wETH', 'FLRETH');

-- ============================================
-- 3. Create index for filtering by market type
-- ============================================
CREATE INDEX IF NOT EXISTS idx_kinetic_apy_market_type 
ON kinetic_apy_snapshots(market_type);

CREATE INDEX IF NOT EXISTS idx_kinetic_apy_market_type_timestamp 
ON kinetic_apy_snapshots(market_type, timestamp DESC);

-- ============================================
-- 4. Add comments
-- ============================================
COMMENT ON COLUMN kinetic_apy_snapshots.market_type IS 
  'Market type: Primary, ISO: FXRP-USDT0-stXRP, or ISO: JOULE-USDC-FLR';

