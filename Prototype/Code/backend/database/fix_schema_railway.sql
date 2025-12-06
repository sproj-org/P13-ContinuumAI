-- Drop existing tables
DROP TABLE IF EXISTS OpportunitiesSummary;
DROP TABLE IF EXISTS SalesSummary;
DROP TABLE IF EXISTS Opportunities;
DROP TABLE IF EXISTS SalesTransactions;
DROP TABLE IF EXISTS Users;
DROP TABLE IF EXISTS SalesReps;
DROP TABLE IF EXISTS Regions;
DROP TABLE IF EXISTS Customers;
DROP TABLE IF EXISTS Products;

-- Products Dimension Table
CREATE TABLE Products (
    product_id VARCHAR(50) PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    category VARCHAR(128),
    sub_category VARCHAR(128),
    INDEX idx_products_category (category),
    INDEX idx_products_sub_category (sub_category),
    INDEX idx_products_name (product_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Customers Dimension Table
CREATE TABLE Customers (
    customer_id VARCHAR(50) PRIMARY KEY,
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
    FOREIGN KEY (region_id) REFERENCES Regions(region_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Users Table
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
    INDEX idx_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Sales Transactions Fact Table
CREATE TABLE SalesTransactions (
    transaction_id VARCHAR(50) PRIMARY KEY,
    order_date DATE NOT NULL,
    sales_amount DECIMAL(14,2) NOT NULL,
    quantity INT NOT NULL,
    discount DECIMAL(6,4) DEFAULT 0.0000,
    product_id VARCHAR(50),
    customer_id VARCHAR(50),
    region_id INT,
    rep_id INT,
    ship_mode VARCHAR(64),
    order_priority VARCHAR(16),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_salestransactions_product_id (product_id),
    INDEX idx_salestransactions_customer_id (customer_id),
    INDEX idx_salestransactions_region_id (region_id),
    INDEX idx_salestransactions_rep_id (rep_id),
    INDEX idx_salestransactions_order_date (order_date),
    
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
    customer_id VARCHAR(50),
    product_id VARCHAR(50),
    probability DECIMAL(5,2) DEFAULT 0.00,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_opportunities_rep_id (rep_id),
    INDEX idx_opportunities_customer_id (customer_id),
    INDEX idx_opportunities_product_id (product_id),
    INDEX idx_opportunities_deal_stage (deal_stage),
    
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
    sr.rep_name,
    c.customer_name,
    c.segment,
    p.product_name,
    p.category
FROM Opportunities o
LEFT JOIN SalesReps sr ON o.rep_id = sr.rep_id
LEFT JOIN Customers c ON o.customer_id = c.customer_id
LEFT JOIN Products p ON o.product_id = p.product_id;
