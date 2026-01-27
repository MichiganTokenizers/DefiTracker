-- Check WingRiders farm data in database

-- Recent WingRiders entries with farm_apr > 0
SELECT a.symbol, s.farm_apr, s.fee_apr, s.staking_apr, s.apr, s.timestamp
FROM apr_snapshots s
JOIN protocols p ON s.protocol_id = p.id
JOIN assets a ON s.asset_id = a.id
WHERE p.name = 'wingriders'
AND s.timestamp > NOW() - INTERVAL '2 days'
AND s.farm_apr IS NOT NULL AND s.farm_apr > 0
ORDER BY s.timestamp DESC
LIMIT 20;

-- Check all WingRiders entries in last 2 days to see farm_apr values
SELECT a.symbol, s.farm_apr, s.fee_apr, s.staking_apr, s.apr, s.timestamp
FROM apr_snapshots s
JOIN protocols p ON s.protocol_id = p.id
JOIN assets a ON s.asset_id = a.id
WHERE p.name = 'wingriders'
AND s.timestamp > NOW() - INTERVAL '2 days'
ORDER BY s.farm_apr DESC NULLS LAST, s.timestamp DESC
LIMIT 30;
