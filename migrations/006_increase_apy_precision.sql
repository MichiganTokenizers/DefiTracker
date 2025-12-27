-- Migration 006: Increase APY column precision
-- 
-- The original NUMERIC(10, 4) can overflow with extreme APY values
-- Increase to NUMERIC(20, 6) to handle:
-- - Very high APYs (up to 99999999999999.999999)
-- - More decimal precision (6 digits instead of 4)
--
-- This is a safety measure even though we now cap values in the application

-- Increase precision for kinetic_apy_snapshots
ALTER TABLE kinetic_apy_snapshots 
    ALTER COLUMN supply_apy TYPE NUMERIC(20, 6),
    ALTER COLUMN supply_distribution_apy TYPE NUMERIC(20, 6),
    ALTER COLUMN total_supply_apy TYPE NUMERIC(20, 6),
    ALTER COLUMN borrow_apy TYPE NUMERIC(20, 6),
    ALTER COLUMN borrow_distribution_apy TYPE NUMERIC(20, 6),
    ALTER COLUMN utilization_rate TYPE NUMERIC(10, 6);

-- Also update apr_snapshots if it exists
ALTER TABLE apr_snapshots 
    ALTER COLUMN apr TYPE NUMERIC(20, 6);

-- Update comments
COMMENT ON COLUMN kinetic_apy_snapshots.supply_apy IS 'Interest rate APY earned by suppliers (up to 6 decimal places)';
COMMENT ON COLUMN kinetic_apy_snapshots.supply_distribution_apy IS 'rFLR/WFLR reward APY for supplying (up to 6 decimal places)';
COMMENT ON COLUMN kinetic_apy_snapshots.total_supply_apy IS 'Total APY for suppliers (up to 6 decimal places)';

