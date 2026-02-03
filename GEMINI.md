# Project: GovGraph

## Project information
* Project name: GovGraph
* Description: An OSINT supply chain intelligence platform for federal procurement analysis. Aggregates USAspending.gov contract data, uses LLMs(Amazon Bedrock) for entity resolution on vendor records, and builds a knowledge graph(Neo4j) to identify vendor relationships, subsidiaries, and contracting patterns."

## Key Features
* AI-Driven Entity Resolution: Utilizes Amazon Bedrock (Claude Haiku 4.5) to normalize inconsistent vendor names (e.g., merging "Lockheed," "LMT," and "Lockheed Martin Corp") with 99% accuracy.
* Infrastructure as Code: Fully provisioned via Terraform with strict cost-control policies (Spot Instances, Single NAT Gateway) enforced via automated tests.
*Kubernetes Native: Microservices architecture deployed on Amazon EKS with autoscaling based on queue depth (KEDA).

## Tech Stack
* Infrastructure: AWS EKS, Terraform, Docker, Helm
* Backend: Python(FastAPI), Boto3, Celery/SQS
* Data & AI: AuraDB free tier(Neo4j), AWS RDS(PostgreSQL), Amazon Bedrock(LLM), Pandas
* Frontend: Next.js, React Flow(Graph Visualization), Tailwind CSS
* CI/CD: Github Actions, pytest

## Code Style
* PEP 8 compliant style for python files
* Robust unit and integration testing is essential

## Installation & Deployment
This project uses a "GitOps" workflow. Infrastructure changes are applied automatically on merge to main.

Prerequisites:
* AWS CLI configured
* Terraform v1.6+
* Kubectl

Local Development:

1. Clone the repo
git clone [https://github.com/ben-kahl/gov-graph.git](https://github.com/ben-kahl/gov-graph.git)

2. Deploy Infra (Dev Profile)
terraform init
terraform apply -var-file="dev.tfvars"

3. Connect to Cluster
aws eks update-kubeconfig --region us-east-1 --name gov-graph-cluster

## Agent Persona & Behavior
*   Tone: Be professional, direct, and concise. Avoid conversational filler.
*   Process: When a task is requested, first generate a plan (`PLAN.md` file) and ask for approval before implementing any code changes.
*   Output: Ensure all new functions and classes have PEP 257 compliant documentation
*   Priorities: This is a resume project. Prioritize keeping costs low or within free tiers.

## Implementation Plan
Currently, the core eks infrastructure has been completed in ./infra/main.tf
The next phase of the project is to build out the backend data pipeline
#### **Phase 1: The "Dirty Data" Pipeline (Backend Logic)**
*Focus: Getting data, cleaning it with AI, and printing it to the console.*

* **Task 1.1: The Scraper (Lambda)**
    * Write a Python script that hits the `USAspending` API for yesterday's contracts.
    * Store raw contract data in RDS database
    * Once this works, create a lambda function to run this as a daily cron job
    * *Success:* It stores contract data in RDS db.
    * *Tech:* Python, `requests`.
* **Task 1.2: The Cleaner (Bedrock Integration)**
    * Write a Python function that takes a "Messy Name" and sends it to Amazon Bedrock (Claude).
    * *Prompt:* "Standardize this company name. 'L.M. Corp' -> 'Lockheed Martin'."
    * *Success:* You input "Boeing Co." and get back "The Boeing Company".
    * *Tech:* `boto3`.
* **Task 1.3: The Infrastructure (Terraform Update)**
    * Add the `aws_lambda_function` and `aws_sqs_queue` resources to your Terraform.
    * *Success:* `terraform apply` creates the queue.

#### **Phase 2: Source of Truth(PostgreSQL) and Knowledge Graph(Neo4j) creation and synchronization**
*Focus: Store data in both the RDS database and the Graph DB(Neo4j) graph database in a queryable structure*

* **Task 2.1: Create Databases**
    * Use Database Schema Context to create both databases
    * Create local testing environment
    * Initialize a historical source of truth with at least 6 months of data for testing
* **Task 2.2: Update Python scripts**
    * Update python scripts to push data to postgres db
    * Ensure synchronization between databases with sqs/celery

#### **Phase 3: API and Deployment(Kubernetes)**
*Focus: Exposing the data to the world.*

* **Task 3.1: FastAPI Wrapper**
    * Create a simple API: `GET /search?q=Lockheed`.
    * It queries the Graph DB and returns the connections.
* **Task 3.2: Dockerize**
    * Create `Dockerfile` for your Worker and your API.
    * Push to Amazon ECR (Elastic Container Registry).
* **Task 3.3: Helm Charts**
    * Write the K8s manifests (`deployment.yaml`, `service.yaml`) to run your containers on EKS.

#### **Phase 4: Frontend Visualization(Next.js)**
*Focus: Creating an interactive dashboard with React Flow for users to interact with data.*

* **Task 4.1: Landing page**
    * Create a simple landing page with an explaination of the project and a login page
    * Use OAuth for authentication
* **Task 4.2: React Flow Visualization**
    * Using the AuraDB graph database, create a mvp of a subset of the graph data visualizing the connections between nodes


## Repo Structure
```text
gov-graph/
├── .github/workflows/    # CI/CD
├── infra/                # Terraform
├── src/
│   ├── ingestion/        # Lambda scripts
│   ├── processing/       # Bedrock/Worker scripts
│   ├── api/              # FastAPI
│   └── dashboard/        # Next.js
├── tests/                # Tests
└── README.md
```

# GovGraph Database Schema Context

This document provides complete database schema information for the GovGraph supply chain intelligence platform. Use this as context when generating code, queries, or documentation.

---

## Architecture Overview

GovGraph uses a **polyglot persistence** architecture:

- **PostgreSQL (RDS)**: Source of truth for raw and cleaned contract data, ETL tracking, entity resolution logs
- **Neo4j (AuraDB)**: Knowledge graph for relationship analysis, pattern detection, and graph visualization

**Data Flow**: USAspending API → Postgres (raw) → LLM Entity Resolution → Postgres (cleaned) → Neo4j (graph projection)

---

## PostgreSQL Schema

### Core Tables

#### `raw_contracts`
Landing zone for raw API data from USAspending.gov.

```sql
CREATE TABLE raw_contracts (
    id UUID PRIMARY KEY,
    usaspending_id VARCHAR(255) UNIQUE NOT NULL,
    raw_payload JSONB NOT NULL,
    ingested_at TIMESTAMP WITH TIME ZONE,
    processed BOOLEAN DEFAULT FALSE,
    processing_errors TEXT
);
```

**Purpose**: Store unprocessed API responses for auditability and reprocessing.

---

#### `vendors`
Canonical vendor records after LLM entity resolution.

```sql
CREATE TABLE vendors (
    id UUID PRIMARY KEY,
    duns VARCHAR(20),
    uei VARCHAR(20),
    canonical_name VARCHAR(500) NOT NULL,
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
    
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE
);
```

**Key Fields**:
- `canonical_name`: The resolved, standardized vendor name (e.g., "Lockheed Martin Corporation")
- `resolution_confidence`: 0.00-1.00 score from LLM entity matching
- `alternative_names`: All name variations found in source data
- `naics_codes`: Array of North American Industry Classification codes
- `business_types`: Small Business, Veteran-Owned, etc.

---

#### `agencies`
Government entities that award contracts.

```sql
CREATE TABLE agencies (
    id UUID PRIMARY KEY,
    agency_code VARCHAR(10) UNIQUE NOT NULL,
    agency_name VARCHAR(500) NOT NULL,
    department VARCHAR(255),
    agency_type VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE
);
```

**Example Values**:
- `agency_code`: "9700" (DoD), "8000" (NASA), "6900" (DOT)
- `agency_type`: "Federal", "Independent", "Legislative"

---

#### `contracts`
Core contract/award transaction data.

```sql
CREATE TABLE contracts (
    id UUID PRIMARY KEY,
    contract_id VARCHAR(255) UNIQUE NOT NULL,
    vendor_id UUID REFERENCES vendors(id),
    agency_id UUID REFERENCES agencies(id),
    parent_contract_id UUID REFERENCES contracts(id),
    
    description TEXT,
    award_type VARCHAR(100),
    contract_type VARCHAR(100),
    
    -- Financial
    obligated_amount DECIMAL(15,2),
    base_amount DECIMAL(15,2),
    total_value DECIMAL(15,2),
    
    -- Dates
    signed_date DATE,
    start_date DATE,
    end_date DATE,
    current_end_date DATE,
    
    -- Classification
    naics_code VARCHAR(10),
    psc_code VARCHAR(10),
    place_of_performance_state VARCHAR(2),
    
    is_subcontract BOOLEAN DEFAULT FALSE,
    raw_contract_id UUID REFERENCES raw_contracts(id),
    
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE
);
```

**Key Fields**:
- `obligated_amount`: Actual money obligated on this contract
- `total_value`: Potential total value including all options
- `parent_contract_id`: Links contract modifications/amendments
- `naics_code`: Industry classification (e.g., "336411" = Aircraft Manufacturing)
- `psc_code`: Product/Service code (e.g., "1520" = Aircraft, Fixed Wing)

---

#### `subcontracts`
Prime contractor → subcontractor relationships.

```sql
CREATE TABLE subcontracts (
    id UUID PRIMARY KEY,
    prime_contract_id UUID REFERENCES contracts(id),
    prime_vendor_id UUID REFERENCES vendors(id),
    subcontractor_vendor_id UUID REFERENCES vendors(id),
    subcontract_amount DECIMAL(15,2),
    subcontract_description TEXT,
    tier_level INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE
);
```

**`tier_level` Explanation**:
- `1`: Direct subcontractor to prime
- `2`: Sub-subcontractor (tier 2)
- `3+`: Deeper supply chain tiers

---

### Entity Resolution Tracking

#### `entity_resolution_log`
Tracks every LLM decision for entity matching.

```sql
CREATE TABLE entity_resolution_log (
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
    
    created_at TIMESTAMP WITH TIME ZONE
);
```

**Purpose**: 
- Track LLM costs (token usage)
- Audit resolution decisions
- Enable manual verification workflow
- Improve prompts based on reasoning

---

### Neo4j Sync Management

#### `neo4j_sync_status`
Tracks what's been synced to the knowledge graph.

```sql
CREATE TABLE neo4j_sync_status (
    id UUID PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    synced_at TIMESTAMP WITH TIME ZONE,
    neo4j_node_id BIGINT,
    sync_status VARCHAR(20) DEFAULT 'pending',
    error_message TEXT,
    UNIQUE(entity_type, entity_id)
);
```

**`entity_type` Values**: `'vendor'`, `'contract'`, `'agency'`, `'subcontract'`

**`sync_status` Values**: `'pending'`, `'synced'`, `'failed'`

---

### Analytics Tables

#### `vendor_analytics`
Pre-computed vendor statistics for performance.

```sql
CREATE TABLE vendor_analytics (
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
```

**Purpose**: Avoid expensive aggregations in real-time queries.

---

### ETL Management

#### `etl_runs`
Tracks pipeline execution.

```sql
CREATE TABLE etl_runs (
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
```

**`run_type` Values**: `'full'`, `'incremental'`, `'backfill'`

---

## Neo4j Graph Schema

### Node Labels

#### `:Vendor`
Companies that receive contracts or act as subcontractors.

**Properties**:
```cypher
{
  id: "uuid-from-postgres",
  canonicalName: "Lockheed Martin Corporation",
  legalName: "Lockheed Martin Corporation",
  duns: "006928857",
  uei: "K4LJ9RPBMQ47",
  state: "MD",
  city: "Bethesda",
  vendorType: "Corporation",
  businessTypes: ["Large Business"],
  naicsCodes: ["336411", "541330"],
  resolutionConfidence: 0.98,
  syncedAt: datetime()
}
```

**Constraints**:
```cypher
CREATE CONSTRAINT vendor_id FOR (v:Vendor) REQUIRE v.id IS UNIQUE;
CREATE CONSTRAINT vendor_canonical_name FOR (v:Vendor) REQUIRE v.canonicalName IS NOT NULL;
```

---

#### `:Agency`
Government entities awarding contracts.

**Properties**:
```cypher
{
  id: "uuid-from-postgres",
  agencyCode: "9700",
  agencyName: "Department of Defense",
  department: "Defense",
  agencyType: "Federal",
  syncedAt: datetime()
}
```

**Constraints**:
```cypher
CREATE CONSTRAINT agency_id FOR (a:Agency) REQUIRE a.id IS UNIQUE;
CREATE CONSTRAINT agency_code FOR (a:Agency) REQUIRE a.agencyCode IS UNIQUE;
```

---

#### `:Contract`
Individual contract awards.

**Properties**:
```cypher
{
  id: "uuid-from-postgres",
  contractId: "W911S0-23-C-0001",
  description: "Weapons System Support",
  awardType: "Contract",
  obligatedAmount: 125000000.00,
  baseAmount: 100000000.00,
  totalValue: 150000000.00,
  signedDate: date("2023-03-15"),
  startDate: date("2023-04-01"),
  endDate: date("2028-03-31"),
  naicsCode: "336411",
  pscCode: "1520",
  placeOfPerformanceState: "TX",
  syncedAt: datetime()
}
```

**Constraints**:
```cypher
CREATE CONSTRAINT contract_id FOR (c:Contract) REQUIRE c.id IS UNIQUE;
```

---

### Relationship Types

#### `(:Vendor)-[:AWARDED]->(:Contract)`
A vendor was awarded a specific contract.

**Properties**: None (relationship itself is meaningful)

**Example**:
```cypher
MATCH (v:Vendor {canonicalName: "Boeing"})-[:AWARDED]->(c:Contract)
RETURN v, c
```

---

#### `(:Agency)-[:AWARDED_CONTRACT]->(:Contract)`
An agency issued a specific contract.

**Properties**: None

---

#### `(:Contract)-[:AWARDED_TO]->(:Vendor)`
A contract was awarded to a vendor (inverse of `AWARDED`).

**Properties**: None

**Note**: Both directions exist for query convenience.

---

#### `(:Vendor)-[:SUBCONTRACTED]->(:Vendor)`
Prime contractor subcontracted work to another vendor.

**Properties**:
```cypher
{
  tierLevel: 1,
  amount: 25000000.00,
  contractId: "uuid-of-prime-contract",
  description: "Engine components"
}
```

**Example**:
```cypher
MATCH (prime:Vendor)-[r:SUBCONTRACTED]->(sub:Vendor)
WHERE r.tierLevel = 1
RETURN prime.canonicalName, sub.canonicalName, r.amount
```

---

#### `(:Contract)-[:MODIFIED_BY]->(:Contract)`
Contract modification/amendment relationship.

**Properties**:
```cypher
{
  modificationType: "Extension",
  modifiedAt: date("2024-01-15")
}
```

---

### Indexes

```cypher
-- Text search
CREATE TEXT INDEX vendor_name_text FOR (v:Vendor) ON (v.canonicalName);

-- Range queries
CREATE INDEX contract_amount FOR (c:Contract) ON (c.obligatedAmount);
CREATE INDEX contract_dates FOR (c:Contract) ON (c.signedDate, c.startDate, c.endDate);

-- Filtering
CREATE INDEX vendor_state FOR (v:Vendor) ON (v.state);
CREATE INDEX vendor_naics FOR (v:Vendor) ON (v.naicsCodes);
```

---

## Common Query Patterns

### PostgreSQL

**Find all contracts for a vendor**:
```sql
SELECT c.* 
FROM contracts c
JOIN vendors v ON c.vendor_id = v.id
WHERE v.canonical_name ILIKE '%lockheed martin%';
```

**Top 10 vendors by spending**:
```sql
SELECT v.canonical_name, SUM(c.obligated_amount) as total
FROM vendors v
JOIN contracts c ON v.id = c.vendor_id
GROUP BY v.id, v.canonical_name
ORDER BY total DESC
LIMIT 10;
```

**Find unsynced records**:
```sql
SELECT c.* 
FROM contracts c
LEFT JOIN neo4j_sync_status s 
  ON s.entity_type = 'contract' AND s.entity_id = c.id
WHERE s.id IS NULL OR s.sync_status = 'failed';
```

---

### Neo4j

**Find all vendors connected to an agency within 2 hops**:
```cypher
MATCH path = (a:Agency {agencyCode: "9700"})-[*..2]-(v:Vendor)
RETURN DISTINCT v.canonicalName, v.state
ORDER BY v.canonicalName;
```

**Detect circular subcontractor relationships**:
```cypher
MATCH (v1:Vendor)-[:SUBCONTRACTED*2..4]->(v1)
RETURN v1.canonicalName, 
       [v IN nodes(path) | v.canonicalName] AS circle
LIMIT 10;
```

**Find tier-2 subcontractors for a prime vendor**:
```cypher
MATCH (prime:Vendor {canonicalName: "Lockheed Martin Corporation"})
      -[:SUBCONTRACTED]->(tier1)
      -[:SUBCONTRACTED]->(tier2)
RETURN tier2.canonicalName, 
       tier1.canonicalName AS through,
       COUNT(*) AS relationships
ORDER BY relationships DESC;
```

**Vendor concentration risk analysis**:
```cypher
MATCH (a:Agency)-[:AWARDED_CONTRACT]->(c:Contract)-[:AWARDED_TO]->(v:Vendor)
WITH a, v, COUNT(c) AS contractCount, SUM(c.obligatedAmount) AS totalSpend
WITH a, 
     COLLECT({vendor: v.canonicalName, spend: totalSpend}) AS vendors,
     SUM(totalSpend) AS agencyTotal
WITH a, vendors, agencyTotal,
     [vendor IN vendors | vendor.spend / agencyTotal] AS concentrations
WHERE ANY(conc IN concentrations WHERE conc > 0.25)
RETURN a.agencyName, 
       [vendor IN vendors WHERE vendor.spend / agencyTotal > 0.25 | 
        {vendor: vendor.vendor, percentage: vendor.spend / agencyTotal * 100}];
```

**PageRank centrality (requires GDS)**:
```cypher
CALL gds.pageRank.stream('vendor-network')
YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS vendor, score
WHERE vendor:Vendor
RETURN vendor.canonicalName, score
ORDER BY score DESC
LIMIT 20;
```

---

## Data Sync Process

### Sync Order (Important!)
1. **Agencies** first (no dependencies)
2. **Vendors** second (no dependencies)
3. **Contracts** third (requires vendors + agencies)
4. **Subcontracts** last (requires vendors)

### Sync Pseudocode
```python
# 1. Query unsynced records from Postgres
unsynced = db.query("""
    SELECT * FROM vendors 
    WHERE id NOT IN (
        SELECT entity_id FROM neo4j_sync_status 
        WHERE entity_type = 'vendor' AND sync_status = 'synced'
    )
""")

# 2. Batch sync to Neo4j
for batch in chunks(unsynced, 1000):
    neo4j.execute("""
        UNWIND $vendors AS v
        MERGE (vendor:Vendor {id: v.id})
        SET vendor.canonicalName = v.canonical_name,
            vendor.state = v.state,
            vendor.naicsCodes = v.naics_codes
    """, vendors=batch)
    
    # 3. Update sync status
    db.execute("""
        INSERT INTO neo4j_sync_status (entity_type, entity_id, sync_status)
        VALUES ('vendor', $vendor_id, 'synced')
    """)
```

---

## Key Terminology

- **DUNS**: Data Universal Numbering System (legacy vendor identifier)
- **UEI**: Unique Entity Identifier (newer standard replacing DUNS)
- **NAICS**: North American Industry Classification System
- **PSC**: Product Service Code (federal procurement classification)
- **Obligated Amount**: Money actually committed on a contract
- **Total Value**: Potential maximum including all options/modifications
- **Prime Contractor**: Main vendor awarded the contract
- **Subcontractor**: Vendor hired by prime to perform work
- **Tier Level**: Depth in subcontractor chain (1 = direct sub, 2 = sub-sub, etc.)

---

## Important Notes

1. **UUIDs**: All primary keys use UUID v4 for distributed system compatibility
2. **Timestamps**: All use `TIMESTAMP WITH TIME ZONE` for consistency
3. **Arrays**: PostgreSQL arrays (e.g., `TEXT[]`) store multi-valued attributes
4. **JSONB**: Used for flexible/semi-structured data (raw payloads, metadata)
5. **Soft Deletes**: Not implemented; use `updated_at` for change tracking
6. **Sync Idempotency**: Neo4j uses `MERGE` to prevent duplicates on retry

---

## Schema Version
**Version**: 1.0  
**Last Updated**: 2026-01-26  
**Compatible With**: PostgreSQL 14+, Neo4j 5.x (AuraDB)
