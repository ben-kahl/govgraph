# GovGraph

GovGraph is an Open-Source Intelligence (OSINT) supply chain platform designed for federal procurement analysis. The system aggregates contract data from USAspending.gov, leverages Large Language Models (Amazon Bedrock) for entity resolution, and constructs a knowledge graph (Neo4j) to map complex relationships between government agencies, prime contractors, and subcontractors.

## Key Features

* AI-Driven Entity Resolution: Utilizes Amazon Bedrock (Claude Haiku) to normalize inconsistent vendor records (e.g., merging "Lockheed," "LMT," and "Lockheed Martin Corp")

* Polyglot Persistence: Combines PostgreSQL for relational data integrity (raw and cleaned contracts) with Neo4j for high-performance graph traversal and relationship discovery

* Infrastructure as Code: The entire environment is fully provisioned via Terraform

* Serviceless Architecture: Using Lambda with scheduled jobs and to host the FastAPI backend. 

## Tech Stack

* Infrastructure: AWS (RDS, SQS, Bedrock, Lambda), Terraform, Docker

* Backend: Python (FastAPI).

* Data & AI: Neo4j (AuraDB), PostgreSQL, Amazon Bedrock (LLM), Pandas

* Frontend: Next.js, React Flow (Graph Visualization), Tailwind CSS

* CI/CD: GitHub Actions, Pytest

## Data Architecture

GovGraph follows a structured pipeline to transform messy public data into actionable intelligence:

* Ingestion: A Python-based scraper (AWS Lambda) pulls daily contract updates from the USAspending API into a PostgreSQL "landing zone"

* Cleaning: The LLM processing engine resolves entity names and assesses confidence scores for every vendor

* Graph Projection: Cleaned data is synced to Neo4j, where vendors, agencies, and contracts are represented as nodes and relationships


**Database Schema**

The platform manages complex relationships with plans to include:

* Prime-to-Subcontractor links (including Tier 2+ depth)

* Agency-to-Contract awards

* Entity Resolution Logs for auditing LLM decision-making and token costs

## Getting Started
**Prerequisites**

* AWS CLI configured with appropriate permissions

* Terraform v1.6+

* Python v3.12+

**Local Development**

* Clone the repository:
    ```Bash
    git clone https://github.com/ben-kahl/gov-graph.git
    cd gov-graph
    ```

* Deploy Infrastructure (Development Profile):
    ```Bash
    cd infra
    terraform init
    terraform apply -var-file="dev.tfvars"
    ```

### Roadmap

    [x] Core Backend Infrastructure

    [Testing] Phase 1: ETL Backend Pipeline (Scraper, Bedrock Cleaner, SQS integration)

    [ ] Phase 2: Neo4j Sync Engine

    [ ] Phase 3: Graph Visualization Dashboard
