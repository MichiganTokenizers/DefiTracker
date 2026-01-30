-- Expand version column to handle longer version strings from DEX APIs
-- (e.g., Sundaeswap returning versions longer than 10 characters)

ALTER TABLE apr_snapshots ALTER COLUMN version TYPE VARCHAR(50);
