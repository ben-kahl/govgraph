# Project: GovGraph

## Project Information
* **Project Name:** GovGraph
* **Description:** An OSINT supply chain intelligence platform for federal procurement analysis. Aggregates USAspending.gov contract data, uses LLMs (Amazon Bedrock) for entity resolution on vendor records, and builds a knowledge graph (Neo4j) to identify vendor relationships, subsidiaries, and contracting patterns.

## Key Features
* **AI-Driven Entity Resolution:** Utilizes Amazon Bedrock (Claude Haiku 4.5) via a 6-tier resolution strategy (DynamoDB cache → DUNS/UEI → exact match → normalized match → fuzzy matching → LLM) to normalize inconsistent vendor names with 95%+ accuracy while reducing LLM costs by 95%
* **Infrastructure as Code:** Fully provisioned via Terraform with strict cost-control policies (serverless architecture, fck-nat for NAT, selective Neo4j sync) targeting <$15/month operational costs
* **Serverless Event-Driven Architecture:** Lambda-based microservices with SQS message queuing, DynamoDB caching, and automatic scaling based on queue depth
* **Polyglot Persistence:** Combines PostgreSQL (relational integrity), DynamoDB (caching), S3 (data lake), and Neo4j (graph analytics) for optimal data storage strategies

## Tech Stack
* **Infrastructure:** AWS Lambda, SQS, RDS, DynamoDB, S3, fck-nat (t4g.nano), EventBridge, Terraform
* **Backend:** Python (asyncio), Boto3, psycopg2, RapidFuzz
* **Data & AI:** AuraDB free tier (Neo4j), AWS RDS (PostgreSQL), Amazon Bedrock (Claude Haiku 4.5), Pandas
* **Frontend:** Next.js 16 (App Router), React 19, AWS Amplify v6 (auth), TanStack Query v5, Cytoscape.js, Recharts, shadcn/ui, Tailwind CSS v4, TypeScript, Bun
* **CI/CD:** GitHub Actions, pytest, Jest, Terraform Cloud, AWS Amplify Hosting

## Architecture Overview

### Data Flow
```
EventBridge Schedule (Daily 6am UTC)
    ↓
Lambda Scraper → S3 (archival) + SQS (raw contracts queue)
    ↓
Lambda Entity Resolver (SQS-triggered, 10 concurrent)
    ├─→ SAM Entity Manager API (Public info of entity names)
    ├─→ DynamoDB (entity resolution cache)
    ├─→ Bedrock (LLM for novel entities, ~5% of requests)
    └─→ RDS PostgreSQL (cleaned, structured data)
    ↓
Lambda Neo4j Syncer (triggered by DynamoDB Streams)
    └─→ Neo4j AuraDB (selective graph projection)
```

### Key Design Decisions
* **Serverless-First:** Eliminated Kubernetes/EKS to reduce costs from $126/month to <$15/month
* **6-Tier Entity Resolution:** DynamoDB cache → DUNS/UEI exact match → canonical name match → normalized name match → fuzzy matching (RapidFuzz) → Bedrock LLM (~5% of requests)
* **fck-nat:** t4g.nano EC2 NAT instance (~$3/month) replaces VPC Interface endpoint for Bedrock ($7/month) — saves ~$4/month
* **Selective Neo4j Sync:** Only sync vendors with >$1M contract value to stay within free tier limits (50K nodes, 175K relationships)
* **S3 Data Lake:** Archive raw USAspending JSON for reprocessing and historical analysis

## Code Style
* PEP 8 compliant style for Python files
* Type hints for all function signatures
* Comprehensive docstrings (PEP 257)
* Robust unit and integration testing (>80% coverage target)

## Testing
**Backend (Python):** Use the virtual environment in `./venv/`
```bash
venv/bin/python -m pytest
```
pytest.ini is at root; `src/api` is on pythonpath so `import auth` works correctly in tests.

**Frontend (TypeScript):** Run from `./frontend/`
```bash
cd frontend && bun run test
# or with coverage:
bun run test:coverage
```
Uses Jest + @testing-library/react. Tests live in `frontend/__tests__/`.
**Important:** Use `bun run test` (invokes Jest), NOT `bun test` (Bun's native runner — incompatible with jest.mock/jsdom).

## Installation & Deployment

### Prerequisites
* AWS CLI configured with appropriate IAM permissions
* Terraform v1.6+
* Python v3.11+
* PostgreSQL client (for local DB access)

### Local Development

1. **Clone the repository:**
   ```bash
   git clone https://github.com/ben-kahl/govgraph.git
   cd govgraph
   ```

2. **Set up Terraform backend:**
   ```bash
   cd infra
   terraform init
   ```

3. **Deploy infrastructure (Dev environment):**
   ```bash
   terraform workspace new dev
   terraform apply -var-file="dev.tfvars"
   ```

4. **Initialize database schema:**
   ```bash
   python scripts/init_db.py
   ```

5. **Deploy Lambda functions:**
   ```bash
   ./deploy.sh
   ```

### CI/CD Workflow
This project uses GitOps. Infrastructure and code changes are automatically deployed on merge to `main`:
* **Pull Requests:** Terraform plan, unit tests, integration tests
* **Main Branch:** Automated Terraform apply, Lambda deployment

## Agent Persona & Behavior
* **Tone:** Be professional, direct, and concise. Avoid conversational filler.
* **Process:** When a task is requested, first generate a plan (`PLAN.md` file) and ask for approval before implementing any code changes.
* **Output:** Ensure all new functions and classes have PEP 257 compliant docstrings with type hints
* **Priorities:** This is a resume project. Prioritize:
  1. Keeping costs low (target <$15/month, max $30/month)
  2. Demonstrating modern cloud architecture skills
  3. Building a sleek, modern UI that looks professional (glassmorphism, dark mode, smooth animations)
  4. Code quality and testing over speed of delivery

## Implementation Plan

### Current Status
* [x] System design completed (serverless architecture)
* [x] Terraform backend configured
* [x] Phase 1: ETL Backend Pipeline
* [x] Phase 2: Neo4j Sync
* [x] Phase 3: FastAPI — Cognito JWT auth, rate limiting, 16+ endpoints, API Gateway, infra complete
* [x] Phase 4: Frontend — Next.js 16 App Router, Amplify Auth, TanStack Query v5, Recharts, Cytoscape
* [ ] **Active:** Frontend polish, UX improvements, testing

### Phase 1: Data Pipeline (Serverless)
**Focus:** Ingest, clean, and store contract data using Lambda-based event-driven architecture

* **Task 1.1: Lambda Scraper**
  * Create EventBridge scheduled rule (daily 6am UTC trigger)
  * Implement Lambda function to fetch USAspending API data with pagination handling
  * Store raw JSON in S3 for archival (s3://govgraph-raw-data/YYYY-MM-DD/contracts.json)
  * Send individual contracts to SQS queue in batches of 10
  * *Success:* Daily ingestion completes in <15 minutes, stores raw data in S3 and SQS
  * *Tech:* Python, boto3, requests, AWS Lambda, SQS, S3

* **Task 1.2: Entity Resolution Lambda** ✅
  * Implemented 6-tier resolution strategy:
    1. DynamoDB cache lookup (Tier 1 — fastest)
    2. DUNS/UEI exact match (DB query)
    3. Canonical name exact match (DB query)
    4. Normalized name exact match
    5. Fuzzy matching with RapidFuzz (in-memory)
    6. Bedrock LLM resolution (fallback, ~5%)
  * Configure SQS trigger with batch size of 10
  * Set up DynamoDB table for entity cache (TTL: 90 days)
  * *Success:* Processes 500 contracts in ~5 minutes, <5% require LLM calls
  * *Tech:* Python, boto3, psycopg2, RapidFuzz, Amazon Bedrock

* **Task 1.3: RDS PostgreSQL Setup**
  * Provision db.t3.micro instance in private subnet
  * Create database schema with monthly partitioning
  * Implement indexes for performance (vendor canonical name, DUNS, UEI, contract dates)
  * Store credentials in AWS Secrets Manager
  * *Success:* Schema deployed, Lambda can connect via VPC, query latency <100ms
  * *Tech:* Terraform, PostgreSQL, AWS RDS, Secrets Manager

* **Task 1.4: VPC & Networking** ✅
  * VPC with private subnets; S3/DynamoDB via Gateway endpoints (free)
  * fck-nat (t4g.nano, ~$3/month) for Bedrock internet access — no Bedrock Interface endpoint
  * Security groups: Lambda → RDS (port 5432)
  * *Tech:* Terraform, AWS VPC, VPC Gateway Endpoints, fck-nat

* **Task 1.5: Monitoring & Alerting**
  * Create CloudWatch dashboard (Lambda metrics, SQS depth, RDS connections)
  * Configure SQS Dead Letter Queue with CloudWatch alarm
  * Set up AWS Budget alert at $20/month threshold
  * *Success:* Real-time visibility into pipeline health, cost alerts configured
  * *Tech:* CloudWatch, SNS, AWS Budgets

### Phase 2: Source of Truth (PostgreSQL) and Knowledge Graph (Neo4j) Synchronization
**Focus:** Sync cleaned data from PostgreSQL to Neo4j for graph analytics

* **Task 2.1: Neo4j Selective Sync Strategy**
  * Identify high-value vendors (>$1M total contract value)
  * Create sync tracking table in PostgreSQL
  * Implement idempotent MERGE operations for Neo4j
  * *Success:* Stay within 50K node limit while capturing 80% of analytical value

* **Task 2.2: Lambda Neo4j Syncer**
  * Trigger via DynamoDB Streams (on entity resolution completion)
  * Batch sync vendors and contracts to Neo4j
  * Update sync status in PostgreSQL
  * *Success:* New vendors appear in graph within 5 minutes of resolution

* **Task 2.3: Historical Data Backfill**
  * Load 6 months of USAspending data for testing
  * Run backfill sync to populate Neo4j
  * Validate graph relationships (vendor → contract → agency)
  * *Success:* 6 months of data loaded, graph queries return accurate results

### Phase 3: API and Deployment
**Focus:** Expose data via REST API and deploy frontend

* **Task 3.1: FastAPI Lambda**
  * Create API routes: /search, /vendor/{id}, /agencies/{id},/contracts/{id}
  * Implement pagination, filtering, sorting
  * Add Redis caching layer (ElastiCache) for frequent queries
  * *Success:* API returns results in <200ms, handles 100 req/min
  * *Tech:* FastAPI, Mangum (Lambda adapter), API Gateway

* **Task 3.2: Authentication & Rate Limiting** ✅
  * Cognito User Pool + JWT validation (JWKS cached in auth.py)
  * slowapi rate limits: 60/min standard, 20/min graph, 30/min analytics (keyed on JWT sub)
  * CORS controlled via `var.allowed_origins` in Terraform
  * *Success:* All data endpoints require Bearer token; /health and / are public

* **Task 3.3: API Documentation**
  * Auto-generate OpenAPI spec from FastAPI
  * Deploy Swagger UI endpoint
  * *Success:* Interactive API documentation available

### Phase 4: Frontend Visualization (Next.js) — Active
**Focus:** Create interactive dashboard with graph visualization

**Runtime:** Next.js 16 App Router, React 19, TypeScript, Tailwind CSS v4, Bun
**Auth:** AWS Amplify v6 (`fetchAuthSession` → Bearer token injected on all API calls)
**Data fetching:** TanStack Query v5 (queryKey/queryFn pattern)
**UI components:** shadcn/ui (radix-ui base, class-variance-authority, tailwind-merge)
**Testing:** Jest + @testing-library/react
**Hosting:** AWS Amplify Hosting (amplify.yml at root)

**Route structure (`frontend/app/`):**
```
/                          → Landing page
/login                     → Amplify Authenticator UI
/(authed)/dashboard        → Market share chart (Recharts)
/(authed)/vendors          → Paginated vendor list + search
/(authed)/vendors/detail   → Vendor detail (contracts, graph)
/(authed)/agencies         → Agency list
/(authed)/agencies/detail  → Agency detail + spending over time
/(authed)/graph            → Cytoscape.js full-screen graph
/(authed)/risk             → Award spikes, new entrants, sole-source flags
```

**Key components (`frontend/components/`):**
- `CytoscapeGraph.tsx` — Network visualization (react-cytoscapejs)
- `MarketShareChart.tsx` — Bar chart (Recharts)
- `SpendingChart.tsx` — Time-series chart (Recharts)
- `Nav.tsx` — Top navigation bar
- `ui/` — shadcn/ui primitives (Card, Button, etc.)

**API client (`frontend/lib/api.ts`):**
- Typed fetch wrapper; reads `NEXT_PUBLIC_API_URL`
- Namespaced: `api.vendors.*`, `api.agencies.*`, `api.analytics.*`, `api.graph.*`

* **Task 4.1: Auth & Shell** ✅ — Amplify Authenticator, `(authed)` route group with session guard
* **Task 4.2: Cytoscape.js Graph** ✅ — `/graph` page, vendor/agency graph endpoints
* **Task 4.3: Dashboard Analytics** ✅ — market share, spending over time, risk flags (Recharts)

### Frontend Design Goals
**Visual Identity:** Modern, professional, data-focused aesthetic suitable for a SaaS product

**Key UI Patterns:**
* **Glassmorphism:** Semi-transparent panels with backdrop blur for depth and hierarchy
* **Dark Mode First:** Design for dark backgrounds with bright data visualizations
* **Smooth Animations:** Framer Motion for panel transitions, hover states, and loading states
* **Data-Driven Styling:** Node sizes, edge widths, and colors map to contract values and relationships
* **Progressive Disclosure:** Show high-level overview, reveal details on interaction
* **Responsive Layout:** Mobile-friendly sidebar collapse, touch-friendly graph controls

**Component Architecture:**
```
/(authed) route group
  ├─ <Nav>                  (top nav: logo, links, sign-out)
  ├─ /dashboard             → <MarketShareChart> (Recharts bar)
  ├─ /graph                 → <CytoscapeGraph> (full-screen network)
  ├─ /vendors[/detail]      → vendor table + contract list
  ├─ /agencies[/detail]     → agency table + <SpendingChart>
  └─ /risk                  → award spikes, new entrants, sole-source
```

**Color Palette:**
* Background: Slate-900 gradient
* Primary: Blue-500 (nodes, accents)
* Secondary: Slate-400 (edges, text)
* Glass: White/10 with 16px blur
* Success: Emerald-500
* Warning: Amber-500

**Typography:**
* Headings: Inter Bold
* Body: Inter Regular
* Monospace: JetBrains Mono (for IDs, codes)

**Reference Inspiration:**
* Neo4j Bloom (graph visualization)
* Notion (clean panels and typography)
* Linear (glassmorphism and animations)
* Vercel Dashboard (dark mode aesthetic)

## Repository Structure
```text
govgraph/
├── .github/workflows/          # CI/CD pipelines
│   ├── deploy.yml              # Automated deployment
│   └── test.yml                # Unit and integration tests
├── amplify.yml                 # AWS Amplify Hosting build config
├── infra/                      # Terraform infrastructure
│   ├── main.tf                 # Root configuration
│   ├── lambda.tf               # 6 Lambda functions
│   ├── gateway.tf              # HTTP API Gateway
│   ├── cognito.tf              # Cognito User Pool + app client
│   ├── rds.tf                  # PostgreSQL database
│   ├── vpc.tf                  # VPC, fck-nat, gateway endpoints
│   ├── sqs.tf                  # Message queues + DLQ
│   ├── monitoring.tf           # CloudWatch dashboards & alarms
│   ├── variables.tf            # Input variables
│   ├── outputs.tf              # api_gateway_url, cognito IDs, etc.
│   ├── dev.tfvars
│   └── prod.tfvars
├── src/
│   ├── ingestion/              # Data ingestion Lambda
│   │   ├── scraper.py          # USAspending API scraper
│   │   └── requirements.txt
│   ├── processing/             # Entity resolution Lambda
│   │   ├── entity_resolver.py  # 6-tier resolution logic
│   │   ├── reprocess_lambda.py # Backfill reprocessing
│   │   └── requirements.txt
│   ├── sync/                   # Neo4j sync Lambda
│   │   ├── neo4j_syncer.py     # PostgreSQL → Neo4j sync
│   │   └── requirements.txt
│   ├── api/                    # FastAPI service (Mangum adapter)
│   │   ├── api.py              # All routes (JWT-protected)
│   │   ├── auth.py             # Cognito JWKS validation
│   │   ├── models.py           # Pydantic models
│   │   ├── database.py         # DB connection (lazy init)
│   │   └── requirements.txt
│   ├── db/
│   │   └── apply_schema.py     # Schema migration Lambda
│   ├── monitoring/
│   │   └── weekly_report.py    # CloudWatch Insights → SNS
│   └── tests/
│       └── unit/               # pytest unit tests
├── frontend/                   # Next.js 16 App Router frontend
│   ├── app/
│   │   ├── (authed)/           # Route group — session-gated
│   │   │   ├── layout.tsx      # Auth guard (fetchAuthSession)
│   │   │   ├── dashboard/      # Market share chart
│   │   │   ├── graph/          # Cytoscape.js full-screen graph
│   │   │   ├── vendors/        # Vendor list + detail
│   │   │   ├── agencies/       # Agency list + detail
│   │   │   └── risk/           # Risk flags (spikes, entrants)
│   │   ├── login/              # Amplify Authenticator UI
│   │   ├── layout.tsx          # Root layout + providers
│   │   ├── page.tsx            # Landing page
│   │   └── providers.tsx       # Amplify + QueryClient providers
│   ├── components/
│   │   ├── CytoscapeGraph.tsx  # Network visualization
│   │   ├── MarketShareChart.tsx # Bar chart (Recharts)
│   │   ├── SpendingChart.tsx   # Time-series chart (Recharts)
│   │   ├── Nav.tsx             # Top nav
│   │   └── ui/                 # shadcn/ui primitives
│   ├── lib/
│   │   ├── api.ts              # Typed API client (TanStack Query ready)
│   │   ├── amplify.ts          # Amplify config
│   │   └── utils.ts            # cn() helper
│   ├── types/
│   │   └── api.ts              # TypeScript interfaces for API responses
│   ├── __tests__/              # Jest + @testing-library/react
│   ├── package.json            # Bun-managed dependencies
│   └── next.config.ts
├── pytest.ini                  # Python test config (src/api on pythonpath)
├── deploy.sh                   # Lambda build & deploy script
└── README.md                   # Public documentation
```

## Database Schema Context

### PostgreSQL Tables

**vendors**
```sql
CREATE TABLE vendors (
    id UUID PRIMARY KEY,
    canonical_name VARCHAR(500) UNIQUE NOT NULL,
    duns VARCHAR(20),
    uei VARCHAR(20),
    resolved_by_llm BOOLEAN DEFAULT FALSE,
    resolution_confidence DECIMAL(3,2),
    alternative_names TEXT[],
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE
);
```

**contracts (partitioned by signed_date)**
```sql
CREATE TABLE contracts (
    id UUID,
    contract_id VARCHAR(255) UNIQUE NOT NULL,
    vendor_id UUID REFERENCES vendors(id),
    description TEXT,
    award_type VARCHAR(100),
    obligated_amount DECIMAL(15,2),
    signed_date DATE,
    resolution_method VARCHAR(50),
    resolution_confidence DECIMAL(3,2),
    created_at TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (id, signed_date)
) PARTITION BY RANGE (signed_date);
```

### Neo4j Schema

**Nodes:**
* `(:Vendor {id, canonicalName, state, naicsCodes})`
* `(:Agency {id, agencyCode, agencyName})`
* `(:Contract {id, contractId, obligatedAmount, signedDate})`

**Relationships:**
* `(:Vendor)-[:AWARDED]->(:Contract)`
* `(:Agency)-[:AWARDED_CONTRACT]->(:Contract)`
* `(:Vendor)-[:SUBCONTRACTED {tierLevel, amount}]->(:Vendor)`

## Cost Breakdown

### Monthly Operating Costs (Estimated)

| Service | Configuration | Year 1 | Year 2+ |
|---------|---------------|--------|---------|
| Lambda | 1,500 invocations/month | $0 (free tier) | $0.50 |
| SQS | 15K messages/month | $0 (free tier) | $0.10 |
| DynamoDB | On-demand, 100K reads | $0.50 | $0.50 |
| Bedrock | 750 Claude Haiku calls | $2.25 | $2.25 |
| RDS | db.t3.micro, 20GB | $0 (free tier) | $16 |
| fck-nat | t4g.nano EC2 NAT instance | $3 | $3 |
| S3 | 5GB storage, 100K requests | $0.50 | $0.50 |
| CloudWatch | Logs, alarms | $2 | $2 |
| Secrets Manager | 1 secret | $0.40 | $0.40 |
| **Total** | | **~$9** | **~$25** |

### Cost Optimization Strategies
* **4-Tier Resolution:** Reduces Bedrock costs from $45/month to $2.25/month (95% reduction)
* **fck-nat:** Replaces Bedrock Interface VPC endpoint ($7/month) with t4g.nano EC2 NAT ($3/month)
* **Serverless:** No fixed compute costs, pay-per-use only
* **Free Tier Maximization:** Lambda, SQS, RDS (year 1)
* **Selective Neo4j Sync:** Stays within free tier limits

## Key Metrics & Success Criteria

### Performance
* Daily pipeline completes in <1 hour
* Entity resolution accuracy >95%
* API response time <200ms (p95)
* Graph query latency <1 second
* Frontend graph render time <2 seconds for 1000 nodes
* Smooth 60fps animations on graph interactions

### User Experience
* Graph canvas loads in <2 seconds
* Node selection reveals details in <100ms
* Filters update graph in <500ms
* Dark mode with glassmorphic UI elements
* Mobile-responsive design (collapsible sidebar)

### Cost
* Monthly AWS bill <$15 (year 1), <$30 (year 2+)
* Bedrock costs <$3/month
* Zero NAT Gateway charges

### Reliability
* Pipeline success rate >99%
* Zero data loss (DLQ captures all failures)
* Automated backups (7-day retention)

### Code Quality
* Test coverage >80%
* Zero critical security vulnerabilities (Checkov scans)
* All infrastructure in version control

## Resume Talking Points

**For Interviews:**

**Backend & Architecture:**
* "Designed serverless event-driven ETL pipeline processing 10K+ federal contracts daily at <$15/month operational cost"
* "Optimized LLM usage 95% through 4-tier entity resolution strategy: DUNS/UEI matching → fuzzy search → DynamoDB cache → Bedrock"
* "Implemented polyglot persistence architecture combining PostgreSQL (ACID compliance), DynamoDB (caching), and Neo4j (graph analytics)"
* "Built resilient data pipeline with SQS message queuing, dead-letter queues, automatic retries, and idempotent processing"
* "Provisioned entire AWS infrastructure as code using Terraform with automated cost control testing"

**Frontend & Visualization:**
* "Built interactive network graph visualization using Cytoscape.js to explore supply chain relationships across 1000+ vendors and 10K+ contracts"
* "Designed modern glassmorphic UI with dark mode, smooth animations (Framer Motion), and progressive disclosure patterns"
* "Implemented data-driven graph styling where node sizes and edge widths map to contract values and relationship strength"
* "Created responsive dashboard with real-time filtering, search, and vendor detail exploration"

## Notes
* This is a portfolio/resume project demonstrating cloud architecture, data engineering, AI integration, and modern UI/UX design skills
* Primary goals are technical depth, cost efficiency, and visual polish — not production scale
* Code quality, testing, documentation, and user experience are prioritized over feature velocity
* Frontend should look like a modern SaaS product (think Vercel, Linear, Notion aesthetics) to differentiate from typical data engineering portfolios
