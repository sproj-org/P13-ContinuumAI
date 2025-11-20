-- =============================================================================
-- Fix ContinuumAI Database Schema - Column Type Corrections
-- =============================================================================
-- Description: Alter table schemas to match CSV data types
-- Issue: CSV has VARCHAR IDs but database expects INT IDs
-- =============================================================================

USE continuum_ai;

-- Disable foreign key checks to allow schema changes
SET FOREIGN_KEY_CHECKS = 0;

-- =============================================================================
-- FIX PRODUCTS TABLE
-- =============================================================================
ALTER TABLE Products 
MODIFY COLUMN product_id VARCHAR(50) NOT NULL;

-- =============================================================================
-- FIX CUSTOMERS TABLE  
-- =============================================================================
ALTER TABLE Customers
MODIFY COLUMN customer_id VARCHAR(50) NOT NULL;

-- =============================================================================
-- FIX SALESTRANSACTIONS TABLE
-- =============================================================================
ALTER TABLE SalesTransactions
MODIFY COLUMN transaction_id VARCHAR(50) NOT NULL,
MODIFY COLUMN product_id VARCHAR(50),
MODIFY COLUMN customer_id VARCHAR(50),
DROP COLUMN order_priority;

-- =============================================================================
-- FIX OPPORTUNITIES TABLE
-- =============================================================================
ALTER TABLE Opportunities
MODIFY COLUMN customer_id VARCHAR(50),
MODIFY COLUMN product_id VARCHAR(50);

-- =============================================================================
-- FIX SALESREPS TABLE (region_id should reference Regions properly)
-- =============================================================================
-- No changes needed for SalesReps

-- Re-enable foreign key checks
SET FOREIGN_KEY_CHECKS = 1;

-- =============================================================================
-- VERIFICATION QUERIES
-- =============================================================================
DESCRIBE Products;
DESCRIBE Customers; 
DESCRIBE SalesTransactions;
DESCRIBE Opportunities;

SELECT 'Schema fixes completed successfully!' AS status;