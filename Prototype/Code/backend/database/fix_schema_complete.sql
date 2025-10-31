-- =============================================================================
-- Fix ContinuumAI Database Schema - Complete Foreign Key Rebuild
-- =============================================================================
-- Purpose: Drop foreign keys, change data types, recreate foreign keys
-- =============================================================================

USE continuum_ai;

-- Disable foreign key checks
SET FOREIGN_KEY_CHECKS = 0;

-- Clear all data first (required for primary key type changes)
TRUNCATE TABLE Opportunities;
TRUNCATE TABLE SalesTransactions;

-- Drop all foreign key constraints
ALTER TABLE SalesTransactions DROP FOREIGN KEY SalesTransactions_ibfk_1;
ALTER TABLE SalesTransactions DROP FOREIGN KEY SalesTransactions_ibfk_2;
ALTER TABLE SalesTransactions DROP FOREIGN KEY SalesTransactions_ibfk_3;
ALTER TABLE SalesTransactions DROP FOREIGN KEY SalesTransactions_ibfk_4;

ALTER TABLE Opportunities DROP FOREIGN KEY Opportunities_ibfk_1;
ALTER TABLE Opportunities DROP FOREIGN KEY Opportunities_ibfk_2;
ALTER TABLE Opportunities DROP FOREIGN KEY Opportunities_ibfk_3;

ALTER TABLE SalesReps DROP FOREIGN KEY SalesReps_ibfk_1;

-- Now modify the column types
ALTER TABLE Products MODIFY COLUMN product_id VARCHAR(50) NOT NULL;
ALTER TABLE Customers MODIFY COLUMN customer_id VARCHAR(50) NOT NULL;

ALTER TABLE SalesTransactions 
  MODIFY COLUMN transaction_id VARCHAR(50) NOT NULL,
  MODIFY COLUMN product_id VARCHAR(50),
  MODIFY COLUMN customer_id VARCHAR(50),
  DROP COLUMN order_priority;

ALTER TABLE Opportunities
  MODIFY COLUMN opportunity_id VARCHAR(50) NOT NULL,
  MODIFY COLUMN product_id VARCHAR(50),
  MODIFY COLUMN customer_id VARCHAR(50);

-- Recreate foreign key constraints
ALTER TABLE SalesTransactions 
  ADD CONSTRAINT SalesTransactions_ibfk_1 FOREIGN KEY (product_id) REFERENCES Products(product_id) ON DELETE SET NULL ON UPDATE CASCADE,
  ADD CONSTRAINT SalesTransactions_ibfk_2 FOREIGN KEY (customer_id) REFERENCES Customers(customer_id) ON DELETE SET NULL ON UPDATE CASCADE,
  ADD CONSTRAINT SalesTransactions_ibfk_3 FOREIGN KEY (region_id) REFERENCES Regions(region_id) ON DELETE SET NULL ON UPDATE CASCADE,
  ADD CONSTRAINT SalesTransactions_ibfk_4 FOREIGN KEY (rep_id) REFERENCES SalesReps(rep_id) ON DELETE SET NULL ON UPDATE CASCADE;

ALTER TABLE Opportunities
  ADD CONSTRAINT Opportunities_ibfk_1 FOREIGN KEY (rep_id) REFERENCES SalesReps(rep_id) ON DELETE SET NULL ON UPDATE CASCADE,
  ADD CONSTRAINT Opportunities_ibfk_2 FOREIGN KEY (customer_id) REFERENCES Customers(customer_id) ON DELETE SET NULL ON UPDATE CASCADE,
  ADD CONSTRAINT Opportunities_ibfk_3 FOREIGN KEY (product_id) REFERENCES Products(product_id) ON DELETE SET NULL ON UPDATE CASCADE;

ALTER TABLE SalesReps
  ADD CONSTRAINT SalesReps_ibfk_1 FOREIGN KEY (region_id) REFERENCES Regions(region_id) ON DELETE SET NULL ON UPDATE CASCADE;

-- Re-enable foreign key checks
SET FOREIGN_KEY_CHECKS = 1;

-- Verification
SELECT 'Schema fix completed successfully!' AS status;
DESCRIBE Products;
DESCRIBE Customers;
DESCRIBE SalesTransactions;