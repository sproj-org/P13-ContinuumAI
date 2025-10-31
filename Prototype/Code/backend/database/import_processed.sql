USE continuum_ai;

SET FOREIGN_KEY_CHECKS = 0;

TRUNCATE TABLE Opportunities;
TRUNCATE TABLE SalesTransactions;
TRUNCATE TABLE SalesReps;
TRUNCATE TABLE Regions;
TRUNCATE TABLE Customers;
TRUNCATE TABLE Products;

LOAD DATA LOCAL INFILE 'C:/SensAi/P13-ContinuumAI/Prototype/Code/backend/database/data/processed/products.csv'
INTO TABLE Products
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS;

LOAD DATA LOCAL INFILE 'C:/SensAi/P13-ContinuumAI/Prototype/Code/backend/database/data/processed/customers.csv'
INTO TABLE Customers
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS;

LOAD DATA LOCAL INFILE 'C:/SensAi/P13-ContinuumAI/Prototype/Code/backend/database/data/processed/regions.csv'
INTO TABLE Regions
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS;

LOAD DATA LOCAL INFILE 'C:/SensAi/P13-ContinuumAI/Prototype/Code/backend/database/data/processed/salesreps.csv'
INTO TABLE SalesReps
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS;

-- Insert 4 additional sales representatives
INSERT INTO SalesReps (rep_id, rep_name, region_id, quota, title, hire_date) VALUES
(7, 'Michael Thompson', 2, 185000.00, 'Senior Account Executive', '2020-03-15'),
(8, 'Jennifer Rodriguez', 1, 142000.00, 'Account Executive', '2021-07-22'),
(9, 'Robert Kim', 3, 220000.00, 'Senior Sales Executive', '2019-11-08'),
(10, 'Amanda Foster', 4, 98000.00, 'Account Executive', '2022-04-12');

LOAD DATA LOCAL INFILE 'C:/SensAi/P13-ContinuumAI/Prototype/Code/backend/database/data/processed/sales_transactions_enriched.csv'
INTO TABLE SalesTransactions
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS;

LOAD DATA LOCAL INFILE 'C:/SensAi/P13-ContinuumAI/Prototype/Code/backend/database/data/processed/opportunities.csv'
INTO TABLE Opportunities
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS;

SET FOREIGN_KEY_CHECKS = 1;
