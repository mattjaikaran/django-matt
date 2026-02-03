-- =============================================================================
-- SaaS Starter - Database Initialization Script
-- =============================================================================
--
-- This script runs when the PostgreSQL container is first created.
-- It sets up necessary extensions and initial configurations.
--
-- =============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";      -- UUID generation
CREATE EXTENSION IF NOT EXISTS "pg_trgm";        -- Trigram matching for search
CREATE EXTENSION IF NOT EXISTS "btree_gin";      -- GIN index for JSONB

-- Create additional schemas if needed
-- CREATE SCHEMA IF NOT EXISTS analytics;

-- Set default search path
ALTER DATABASE saas_starter SET search_path TO public;

-- Performance tuning for development
-- (adjust these for production based on your server specs)
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '512MB';
ALTER SYSTEM SET work_mem = '16MB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';

-- Logging for development
ALTER SYSTEM SET log_statement = 'none';  -- Change to 'all' for debugging
ALTER SYSTEM SET log_duration = off;
ALTER SYSTEM SET log_min_duration_statement = 1000;  -- Log slow queries > 1s

-- Grant permissions (if needed for additional users)
-- GRANT ALL PRIVILEGES ON DATABASE saas_starter TO saas_user;

-- Create indexes on common queries (if tables exist)
-- These will be created by Django migrations, but you can add custom ones here

-- Output confirmation
DO $$
BEGIN
    RAISE NOTICE 'Database initialization complete!';
END $$;
