-- PostgreSQL Schema for GovGraph

-- Enable Extension for UUIDs and utility functions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Raw Contracts (Landing Zone)
CREATE TABLE IF NOT EXISTS raw_contracts (
    id UUID PRIMARY KEY,
    usaspending_id VARCHAR(255) UNIQUE NOT NULL,
    raw_payload JSONB NOT NULL,
    ingested_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE,
    processing_errors TEXT
);
CREATE INDEX IF NOT EXISTS idx_raw_contracts_processed ON raw_contracts(processed) WHERE processed = FALSE;

-- 2. Vendors (Canonical Records)
CREATE TABLE IF NOT EXISTS vendors (
    id UUID PRIMARY KEY,
    duns VARCHAR(20) UNIQUE,
    uei VARCHAR(20) UNIQUE,
    canonical_name VARCHAR(500) UNIQUE NOT NULL,
    legal_name VARCHAR(500),
    doing_business_as TEXT[],
    vendor_type VARCHAR(50),
    
    -- Location
    address_line1 VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(2),
    zip_code VARCHAR(10),
    country VARCHAR(3) DEFAULT 'USA',
    
    -- Classification
    business_types TEXT[],
    naics_codes VARCHAR(10)[],
    psc_codes VARCHAR(10)[],
    
    -- Entity Resolution
    resolution_confidence DECIMAL(3,2),
    resolved_by_llm BOOLEAN DEFAULT FALSE,
    alternative_names TEXT[],
    matched_vendor_ids UUID[],
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indices for Entity Resolution Performance
CREATE INDEX IF NOT EXISTS idx_vendors_canonical_name ON vendors (canonical_name);
CREATE INDEX IF NOT EXISTS idx_vendors_duns ON vendors (duns) WHERE duns IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_vendors_uei ON vendors (uei) WHERE uei IS NOT NULL;

-- 3. Agencies
CREATE TABLE IF NOT EXISTS agencies (
    id UUID PRIMARY KEY,
    agency_code VARCHAR(10) UNIQUE NOT NULL,
    agency_name VARCHAR(500) NOT NULL,
    department VARCHAR(255),
    agency_type VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. Contracts (Core Data) - Partitioned by signed_date
CREATE TABLE IF NOT EXISTS contracts (
    id UUID NOT NULL,
    contract_id VARCHAR(255) NOT NULL,
    vendor_id UUID REFERENCES vendors(id),
    agency_id UUID REFERENCES agencies(id),
    parent_contract_id UUID, -- References handled manually due to partitioning
    
    description TEXT,
    award_type VARCHAR(100),
    contract_type VARCHAR(100),
    
    -- Financial
    obligated_amount DECIMAL(15,2),
    base_amount DECIMAL(15,2),
    total_value DECIMAL(15,2),
    
    -- Dates
    signed_date DATE NOT NULL,
    start_date DATE,
    end_date DATE,
    current_end_date DATE,
    
    -- Classification
    naics_code VARCHAR(10),
    psc_code VARCHAR(10),
    place_of_performance_state VARCHAR(2),
    
    is_subcontract BOOLEAN DEFAULT FALSE,
    raw_contract_id UUID REFERENCES raw_contracts(id),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    PRIMARY KEY (id, signed_date),
    UNIQUE (contract_id, signed_date)
) PARTITION BY RANGE (signed_date);

-- Create Default Partition to catch any dates not explicitly defined
CREATE TABLE IF NOT EXISTS contracts_default PARTITION OF contracts DEFAULT;

-- Indices for Contracts
CREATE INDEX IF NOT EXISTS idx_contracts_signed_date ON contracts (signed_date);
CREATE INDEX IF NOT EXISTS idx_contracts_vendor_id ON contracts (vendor_id);
CREATE INDEX IF NOT EXISTS idx_contracts_contract_id ON contracts (contract_id);

-- 5. Subcontracts
CREATE TABLE IF NOT EXISTS subcontracts (
    id UUID PRIMARY KEY,
    prime_contract_id UUID, -- Link manually or include partition key
    prime_vendor_id UUID REFERENCES vendors(id),
    subcontractor_vendor_id UUID REFERENCES vendors(id),
    subcontract_amount DECIMAL(15,2),
    subcontract_description TEXT,
    tier_level INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. Entity Resolution Log
CREATE TABLE IF NOT EXISTS entity_resolution_log (
    id UUID PRIMARY KEY,
    source_vendor_name VARCHAR(500) NOT NULL,
    resolved_vendor_id UUID REFERENCES vendors(id),
    
    llm_model VARCHAR(100),
    llm_prompt_tokens INTEGER,
    llm_completion_tokens INTEGER,
    confidence_score DECIMAL(3,2),
    
    reasoning TEXT,
    alternative_matches JSONB,
    
    manually_verified BOOLEAN DEFAULT FALSE,
    verified_by VARCHAR(255),
    verified_at TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 7. Neo4j Sync Status
CREATE TABLE IF NOT EXISTS neo4j_sync_status (
    id UUID PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    synced_at TIMESTAMP WITH TIME ZONE,
    neo4j_node_id BIGINT,
    sync_status VARCHAR(20) DEFAULT 'pending',
    error_message TEXT,
    UNIQUE(entity_type, entity_id)
);

-- 8. Vendor Analytics
CREATE TABLE IF NOT EXISTS vendor_analytics (
    vendor_id UUID PRIMARY KEY REFERENCES vendors(id),
    total_contracts INTEGER DEFAULT 0,
    total_obligated_amount DECIMAL(15,2) DEFAULT 0,
    active_contracts INTEGER DEFAULT 0,
    first_contract_date DATE,
    last_contract_date DATE,
    top_agencies UUID[],
    top_naics_codes VARCHAR(10)[],
    subcontractor_count INTEGER DEFAULT 0,
    prime_contractor_count INTEGER DEFAULT 0,
    calculated_at TIMESTAMP WITH TIME ZONE
);

-- 9. ETL Runs
CREATE TABLE IF NOT EXISTS etl_runs (
    id UUID PRIMARY KEY,
    run_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    records_fetched INTEGER,
    records_processed INTEGER,
    records_failed INTEGER,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    metadata JSONB
);
