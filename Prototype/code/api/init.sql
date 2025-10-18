-- ContinuumAI MySQL Database Initialization Script
-- This script sets up the database for the ContinuumAI application

-- Create database if it doesn't exist (handled by docker-compose)
-- USE continuumai_db;

-- Set timezone
SET time_zone = '+00:00';

-- Create indexes for better performance
-- These will be created automatically by SQLAlchemy, but we can pre-create some

-- Enable event scheduler (if needed for cleanup tasks)
-- SET GLOBAL event_scheduler = ON;

-- Initial setup complete message
SELECT 'ContinuumAI MySQL Database initialized successfully!' as message;