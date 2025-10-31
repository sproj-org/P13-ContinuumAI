-- =============================================================================
-- ContinuumAI Data Import Script
-- =============================================================================
-- Description: Bulk data import script for loading CSV files into ContinuumAI
--              star schema tables using LOAD DATA LOCAL INFILE commands
-- Created: October 31, 2025
-- Database: continuum_ai
-- =============================================================================

-- Use the ContinuumAI database
USE continuum_ai;

-- Disable foreign key checks during import to avoid constraint violations
SET FOREIGN_KEY_CHECKS = 0;

-- =============================================================================
-- DIMENSION TABLES DATA IMPORT
-- =============================================================================

-- Import Products data
LOAD DATA LOCAL INFILE 'C:/SensAi/P13-ContinuumAI/Prototype/Code/backend/database/data/products.csv'
INTO TABLE Products
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS;

-- Import Customers data
LOAD DATA LOCAL INFILE 'C:/SensAi/P13-ContinuumAI/Prototype/Code/backend/database/data/customers.csv'
INTO TABLE Customers
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS;

-- Import Regions data
LOAD DATA LOCAL INFILE 'C:/SensAi/P13-ContinuumAI/Prototype/Code/backend/database/data/regions.csv'
INTO TABLE Regions
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS;

-- Import Sales Representatives data
LOAD DATA LOCAL INFILE 'C:/SensAi/P13-ContinuumAI/Prototype/Code/backend/database/data/salesreps.csv'
INTO TABLE SalesReps
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS;

-- =============================================================================
-- FACT TABLES DATA IMPORT
-- =============================================================================

-- Import Sales Transactions data
LOAD DATA LOCAL INFILE 'C:/SensAi/P13-ContinuumAI/Prototype/Code/backend/database/data/sales_transactions.csv'
INTO TABLE SalesTransactions
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS;

-- Import Opportunities data
LOAD DATA LOCAL INFILE 'C:/SensAi/P13-ContinuumAI/Prototype/Code/backend/database/data/opportunities.csv'
INTO TABLE Opportunities
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS;

-- =============================================================================
-- DATA VALIDATION AND CLEANUP
-- =============================================================================
-- Re-enable foreign key checks
SET FOREIGN_KEY_CHECKS = 1;

-- Verify data import counts
SELECT 'Products' AS table_name, COUNT(*) AS record_count FROM Products
UNION ALL
SELECT 'Customers' AS table_name, COUNT(*) AS record_count FROM Customers
UNION ALL
SELECT 'Regions' AS table_name, COUNT(*) AS record_count FROM Regions
UNION ALL
SELECT 'SalesReps' AS table_name, COUNT(*) AS record_count FROM SalesReps
UNION ALL
SELECT 'SalesTransactions' AS table_name, COUNT(*) AS record_count FROM SalesTransactions
UNION ALL
SELECT 'Opportunities' AS table_name, COUNT(*) AS record_count FROM Opportunities;

-- =============================================================================
-- END OF IMPORT SCRIPT
-- =============================================================================