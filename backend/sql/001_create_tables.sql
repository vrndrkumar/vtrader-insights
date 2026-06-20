-- ============================================================
-- Swing Trade Analysis System -- additional tables
-- Run against: knowingly_trade
-- These are ADDITIVE ONLY. stock_mstr is untouched.
-- (The backend will also create these automatically on first
--  run via SQLAlchemy's init_db(), so this script is optional
--  but recommended for production so you control indexing.)
-- ============================================================

CREATE TABLE IF NOT EXISTS `stock_analysis_reports` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `stock_id` BIGINT NOT NULL,
  `symbol_code` VARCHAR(20) DEFAULT NULL,
  `exchange` VARCHAR(5) DEFAULT NULL,

  `overall_score` FLOAT DEFAULT NULL,
  `fundamental_score` FLOAT DEFAULT NULL,
  `technical_score` FLOAT DEFAULT NULL,
  `sector_score` FLOAT DEFAULT NULL,
  `momentum_score` FLOAT DEFAULT NULL,

  `verdict` VARCHAR(20) DEFAULT NULL,
  `confidence` VARCHAR(20) DEFAULT NULL,
  `probability_3_6m` FLOAT DEFAULT NULL,

  `swing_view` JSON DEFAULT NULL,
  `long_term_view` JSON DEFAULT NULL,
  `technical_detail` JSON DEFAULT NULL,
  `fundamental_detail` JSON DEFAULT NULL,
  `sector_detail` JSON DEFAULT NULL,
  `momentum_detail` JSON DEFAULT NULL,
  `risk_factors` JSON DEFAULT NULL,
  `raw_quote` JSON DEFAULT NULL,

  `is_latest` TINYINT(1) DEFAULT 1,
  `generated_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,

  PRIMARY KEY (`id`),
  KEY `idx_sar_stock_id` (`stock_id`),
  KEY `idx_sar_symbol_code` (`symbol_code`),
  KEY `idx_sar_is_latest` (`is_latest`),
  KEY `idx_sar_generated_at` (`generated_at`),
  CONSTRAINT `fk_sar_stock_mstr` FOREIGN KEY (`stock_id`) REFERENCES `stock_mstr` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


CREATE TABLE IF NOT EXISTS `market_overview` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `market_view` TEXT,
  `favoured_sectors` JSON DEFAULT NULL,
  `avoid_sectors` JSON DEFAULT NULL,
  `key_risks` JSON DEFAULT NULL,
  `key_opportunities` JSON DEFAULT NULL,
  `raw` JSON DEFAULT NULL,
  `generated_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


CREATE TABLE IF NOT EXISTS `analysis_jobs` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `job_type` VARCHAR(20) DEFAULT NULL,
  `status` VARCHAR(20) DEFAULT 'pending',
  `total` INT DEFAULT 0,
  `completed` INT DEFAULT 0,
  `failed` INT DEFAULT 0,
  `symbols` JSON DEFAULT NULL,
  `result_summary` JSON DEFAULT NULL,
  `error` TEXT,
  `created_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
  `completed_at` TIMESTAMP NULL DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
