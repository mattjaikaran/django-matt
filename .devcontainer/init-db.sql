-- Initialize PostgreSQL with pgvector extension
-- This runs automatically when the container is first created

-- Create the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create additional useful extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- Create test database for pytest
CREATE DATABASE django_matt_test;
GRANT ALL PRIVILEGES ON DATABASE django_matt_test TO django_matt;

-- Connect to test database and create extensions there too
\c django_matt_test
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
