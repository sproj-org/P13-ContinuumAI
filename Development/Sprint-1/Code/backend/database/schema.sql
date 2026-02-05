-- =============================================================================
-- ContinuumAI Database Schema - Star Schema Design
-- =============================================================================
-- Description: Complete DDL script for ContinuumAI star schema with dimension 
--              and fact tables for sales analytics and opportunity tracking
-- Created: October 31, 2025
-- Engine: InnoDB with foreign key constraints and optimized indexes
-- =============================================================================

-- Create database
CREATE DATABASE IF NOT EXISTS continuum_ai 
    CHARACTER SET utf8mb4 
    COLLATE utf8mb4_unicode_ci;

-- Use the database
USE continuum_ai;

-- =============================================================================
-- DIMENSION TABLES
-- =============================================================================

-- Products Dimension Table
CREATE TABLE Products (
    product_id INT PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    category VARCHAR(128),
    sub_category VARCHAR(128),
    INDEX idx_products_category (category),
    INDEX idx_products_sub_category (sub_category),
    INDEX idx_products_name (product_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Customers Dimension Table
CREATE TABLE Customers (
    customer_id INT PRIMARY KEY,
    customer_name VARCHAR(255),
    segment VARCHAR(64),
    INDEX idx_customers_segment (segment),
    INDEX idx_customers_name (customer_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Regions Dimension Table
CREATE TABLE Regions (
    region_id INT PRIMARY KEY,
    region_name VARCHAR(128),
    state VARCHAR(128),
    city VARCHAR(128),
    INDEX idx_regions_name (region_name),
    INDEX idx_regions_state (state),
    INDEX idx_regions_city (city)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Sales Representatives Dimension Table
CREATE TABLE SalesReps (
    rep_id INT PRIMARY KEY,
    rep_name VARCHAR(255),
    region_id INT,
    quota DECIMAL(14,2),
    title VARCHAR(128),
    hire_date DATE,
    INDEX idx_salesreps_region_id (region_id),
    INDEX idx_salesreps_name (rep_name),
    INDEX idx_salesreps_title (title),
    INDEX idx_salesreps_hire_date (hire_date),
    FOREIGN KEY (region_id) REFERENCES Regions(region_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Users Table for Authentication and Authorization
CREATE TABLE Users (
    user_id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(128) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(64) NOT NULL DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    INDEX idx_users_username (username),
    INDEX idx_users_email (email),
    INDEX idx_users_role (role),
    INDEX idx_users_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- FACT TABLES
-- =============================================================================

-- Sales Transactions Fact Table
CREATE TABLE SalesTransactions (
    transaction_id BIGINT PRIMARY KEY,
    order_date DATE NOT NULL,
    sales_amount DECIMAL(14,2) NOT NULL,
    quantity INT NOT NULL,
    discount DECIMAL(6,4) DEFAULT 0.0000,
    product_id INT,
    customer_id INT,
    region_id INT,
    rep_id INT,
    ship_mode VARCHAR(64),
    order_priority VARCHAR(16),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Foreign Key Indexes (automatically created with FOREIGN KEY constraints)
    INDEX idx_salestransactions_product_id (product_id),
    INDEX idx_salestransactions_customer_id (customer_id),
    INDEX idx_salestransactions_region_id (region_id),
    INDEX idx_salestransactions_rep_id (rep_id),
    
    -- Performance Indexes for common queries
    INDEX idx_salestransactions_order_date (order_date),
    INDEX idx_salestransactions_sales_amount (sales_amount),
    INDEX idx_salestransactions_ship_mode (ship_mode),
    INDEX idx_salestransactions_order_priority (order_priority),
    INDEX idx_salestransactions_created_at (created_at),
    
    -- Composite indexes for common query patterns
    INDEX idx_salestransactions_date_rep (order_date, rep_id),
    INDEX idx_salestransactions_date_product (order_date, product_id),
    INDEX idx_salestransactions_rep_amount (rep_id, sales_amount),
    
    -- Foreign Key Constraints
    FOREIGN KEY (product_id) REFERENCES Products(product_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE,
    FOREIGN KEY (customer_id) REFERENCES Customers(customer_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE,
    FOREIGN KEY (region_id) REFERENCES Regions(region_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE,
    FOREIGN KEY (rep_id) REFERENCES SalesReps(rep_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Opportunities Fact Table
CREATE TABLE Opportunities (
    opportunity_id BIGINT PRIMARY KEY,
    created_date DATE NOT NULL,
    close_date DATE NULL,
    deal_stage ENUM('Won', 'Lost', 'Pending') NOT NULL DEFAULT 'Pending',
    deal_amount DECIMAL(14,2) NOT NULL,
    rep_id INT,
    customer_id INT,
    product_id INT,
    probability DECIMAL(5,2) DEFAULT 0.00,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Foreign Key Indexes
    INDEX idx_opportunities_rep_id (rep_id),
    INDEX idx_opportunities_customer_id (customer_id),
    INDEX idx_opportunities_product_id (product_id),
    
    -- Performance Indexes
    INDEX idx_opportunities_created_date (created_date),
    INDEX idx_opportunities_close_date (close_date),
    INDEX idx_opportunities_deal_stage (deal_stage),
    INDEX idx_opportunities_deal_amount (deal_amount),
    INDEX idx_opportunities_probability (probability),
    INDEX idx_opportunities_created_at (created_at),
    
    -- Composite indexes for analytics
    INDEX idx_opportunities_stage_amount (deal_stage, deal_amount),
    INDEX idx_opportunities_rep_stage (rep_id, deal_stage),
    INDEX idx_opportunities_date_stage (created_date, deal_stage),
    
    -- Foreign Key Constraints
    FOREIGN KEY (rep_id) REFERENCES SalesReps(rep_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE,
    FOREIGN KEY (customer_id) REFERENCES Customers(customer_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE,
    FOREIGN KEY (product_id) REFERENCES Products(product_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- VIEWS FOR COMMON ANALYTICS QUERIES
-- =============================================================================

-- Sales Summary View
CREATE VIEW SalesSummary AS
SELECT 
    st.transaction_id,
    st.order_date,
    st.sales_amount,
    st.quantity,
    st.discount,
    p.product_name,
    p.category,
    p.sub_category,
    c.customer_name,
    c.segment,
    r.region_name,
    r.state,
    r.city,
    sr.rep_name,
    sr.title as rep_title,
    st.ship_mode,
    st.order_priority
FROM SalesTransactions st
LEFT JOIN Products p ON st.product_id = p.product_id
LEFT JOIN Customers c ON st.customer_id = c.customer_id
LEFT JOIN Regions r ON st.region_id = r.region_id
LEFT JOIN SalesReps sr ON st.rep_id = sr.rep_id;

-- Opportunities Summary View
CREATE VIEW OpportunitiesSummary AS
SELECT 
    o.opportunity_id,
    o.created_date,
    o.close_date,
    o.deal_stage,
    o.deal_amount,
    o.probability,
    p.product_name,
    p.category,
    c.customer_name,
    c.segment,
    sr.rep_name,
    r.region_name,
    r.state,
    o.notes
FROM Opportunities o
LEFT JOIN Products p ON o.product_id = p.product_id
LEFT JOIN Customers c ON o.customer_id = c.customer_id
LEFT JOIN SalesReps sr ON o.rep_id = sr.rep_id
LEFT JOIN Regions r ON sr.region_id = r.region_id;

-- =============================================================================
-- SAMPLE DATA INSERTION (Optional - for testing)
-- =============================================================================

-- Insert sample regions
INSERT INTO Regions (region_id, region_name, state, city) VALUES
(1, 'North America', 'California', 'San Francisco'),
(2, 'North America', 'New York', 'New York City'),
(3, 'Europe', 'England', 'London'),
(4, 'Asia Pacific', 'Japan', 'Tokyo');

-- Insert sample products
INSERT INTO Products (product_id, product_name, category, sub_category) VALUES
(1, 'ContinuumAI Pro', 'Software', 'AI Platform'),
(2, 'ContinuumAI Enterprise', 'Software', 'AI Platform'),
(3, 'Data Analytics Module', 'Software', 'Analytics'),
(4, 'Custom AI Solutions', 'Services', 'Consulting');

-- Insert sample customers
INSERT INTO Customers (customer_id, customer_name, segment) VALUES
(1, 'TechCorp Inc', 'Enterprise'),
(2, 'StartupAI Ltd', 'SMB'),
(3, 'Global Industries', 'Enterprise'),
(4, 'Innovation Labs', 'Mid-Market');

-- Insert sample sales reps
INSERT INTO SalesReps (rep_id, rep_name, region_id, quota, title, hire_date) VALUES
(1, 'John Smith', 1, 1000000.00, 'Senior Sales Manager', '2023-01-15'),
(2, 'Sarah Johnson', 2, 800000.00, 'Sales Representative', '2023-03-10'),
(3, 'Mike Chen', 4, 750000.00, 'Regional Sales Lead', '2022-11-20'),
(4, 'Emma Wilson', 3, 900000.00, 'Sales Manager', '2023-02-01');

-- Insert sample user
INSERT INTO Users (username, email, password_hash, role) VALUES
('admin', 'admin@continuumai.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewjuPKQGhbxUbtF.', 'admin'),
('demo_user', 'demo@continuumai.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewjuPKQGhbxUbtF.', 'user');

-- =============================================================================
-- SCHEMA VALIDATION AND PERFORMANCE OPTIMIZATION
-- =============================================================================

-- Show all tables created
SHOW TABLES;

-- Display table structure for verification
DESCRIBE Products;
DESCRIBE Customers;
DESCRIBE Regions;
DESCRIBE SalesReps;
DESCRIBE Users;
DESCRIBE SalesTransactions;
DESCRIBE Opportunities;

-- =============================================================================
-- END OF SCHEMA
-- =============================================================================