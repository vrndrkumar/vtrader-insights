-- ============================================================
-- One-time migration: populate sector_index_symbol
-- VTrader Stock Intelligence
--
-- Maps each sector value to a verified yfinance index symbol.
-- Verified live on 2026-06-20 against Yahoo Finance.
--
-- Sectors with NO dedicated NSE index fall back to Nifty 500
-- (^CRSLDX) — broad market relative strength instead of a
-- true peer-group benchmark. This is a real data gap, not a
-- mapping error: NSE simply does not publish standalone
-- indices for these categories.
-- ============================================================

-- Confirmed working sector indices (verified live)
UPDATE stock_mstr SET sector_index_symbol = '^NSEBANK'   WHERE sector = 'Bank';
UPDATE stock_mstr SET sector_index_symbol = '^CNXAUTO'   WHERE sector = 'Auto';
UPDATE stock_mstr SET sector_index_symbol = '^CNXIT'     WHERE sector = 'I.T';
UPDATE stock_mstr SET sector_index_symbol = '^CNXFMCG'   WHERE sector = 'FMCG';
UPDATE stock_mstr SET sector_index_symbol = '^CNXMETAL'  WHERE sector = 'Metals & Mining';
UPDATE stock_mstr SET sector_index_symbol = '^CNXREALTY' WHERE sector = 'Realty';
UPDATE stock_mstr SET sector_index_symbol = '^CNXPHARMA' WHERE sector = 'Healthcare';
UPDATE stock_mstr SET sector_index_symbol = '^CNXENERGY' WHERE sector = 'Energy';
UPDATE stock_mstr SET sector_index_symbol = '^CNXMEDIA'  WHERE sector = 'Media';
UPDATE stock_mstr SET sector_index_symbol = '^CNXFIN'    WHERE sector = 'Financials';
UPDATE stock_mstr SET sector_index_symbol = '^CNXINFRA'  WHERE sector = 'Industrials';
UPDATE stock_mstr SET sector_index_symbol = '^CNXSERVICE' WHERE sector = 'Services';
UPDATE stock_mstr SET sector_index_symbol = '^CNXCONSUM' WHERE sector = 'Consumer Discretionary';

-- Power & Utilities — no dedicated index, closest proxy is Energy
UPDATE stock_mstr SET sector_index_symbol = '^CNXENERGY' WHERE sector = 'Power & Utilities';

-- Building Materials — no dedicated index, closest proxy is Infra
UPDATE stock_mstr SET sector_index_symbol = '^CNXINFRA'  WHERE sector = 'Building Materials';

-- Telecom-Service — merge with Telecom (same fallback below)
-- Both Telecom and Telecom-Service: NO dedicated working NSE index found.
-- Confirmed ^CNXMEDIA does NOT carry telecom data despite some documentation
-- suggesting otherwise. Falls back to Nifty 500 broad market.
UPDATE stock_mstr SET sector_index_symbol = '^CRSLDX'    WHERE sector IN ('Telecom', 'Telecom-Service');

-- Chemicals — no working yfinance symbol found (NIFTYCHEMICALS.NS failed)
-- Falls back to Nifty 500 broad market.
UPDATE stock_mstr SET sector_index_symbol = '^CRSLDX'    WHERE sector = 'Chemicals';

-- Aerospace & Defence — no working yfinance symbol found
-- (NIFTYINDDEFENCE.NS and NIFTYDEFENCE.NS both failed)
-- Falls back to Nifty 500 broad market.
UPDATE stock_mstr SET sector_index_symbol = '^CRSLDX'    WHERE sector = 'Aerospace & Defence';

-- Sectors with NO NSE sector index at all — fall back to Nifty 500
UPDATE stock_mstr SET sector_index_symbol = '^CRSLDX'    WHERE sector IN (
    'Co-Working',
    'Indices',
    'Miscellaneous',
    'N/A',
    'Plastic Products',
    'Textiles',
    'Transportation'
);

-- Safety net: any sector value not explicitly handled above
-- (new sectors added later, typos, etc.) also falls back to Nifty 500
UPDATE stock_mstr SET sector_index_symbol = '^CRSLDX'
WHERE sector_index_symbol IS NULL AND sector IS NOT NULL;

-- ============================================================
-- Verification query — run after migration to confirm coverage
-- ============================================================
-- SELECT sector, sector_index_symbol, COUNT(*) as stock_count
-- FROM stock_mstr
-- WHERE is_active = 1
-- GROUP BY sector, sector_index_symbol
-- ORDER BY sector;