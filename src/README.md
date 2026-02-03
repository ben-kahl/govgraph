# GovGraph Source Code

## Deployment Instructions

### Lambda Dependencies
The Python scripts in `ingestion/` and `processing/` rely on external libraries (`requests`, `psycopg2-binary`).
The standard AWS Lambda runtime includes `boto3` and `json`, but NOT `requests` or `psycopg2`.

To successfully deploy the `ingest_contracts` function, you must create a deployment package that includes these dependencies.

#### Option 1: AWS Lambda Layers (Recommended)
1. Create a Lambda Layer containing `requests` and `psycopg2-binary` (compiled for Amazon Linux 2).
2. Attach this layer to the `aws_lambda_function` resource in `infra/main.tf`.

#### Option 2: Vendor Dependencies in Zip
Before running `terraform apply`, install the dependencies into the `src/ingestion` folder:

```bash
cd src/ingestion
pip install --target . requests psycopg2-binary
```

*Note: `psycopg2-binary` may cause issues on AWS Lambda if installed from a non-Linux machine. It is safer to use `aws-psycopg2` or build inside a Docker container.*

### Database Setup
The `infra/main.tf` creates an RDS instance. You will need to apply the schema manually after creation:

1. Connect to the RDS instance (you may need to use a Bastion host or allow your IP in the Security Group temporarily).
2. Run the SQL commands from `src/db/schema.sql`.

```bash
psql -h <RDS_ENDPOINT> -U postgres -d govgraph -f src/db/schema.sql
```

## Local Development & Testing

### 1. Start a Local Database
Use Docker to run a PostgreSQL 17 container:

```bash
docker run --name govgraph-postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=govgraph -p 5432:5432 -d postgres:17
```

### 2. Apply Database Schema
Apply the schema to the local database:

```bash
docker exec -i govgraph-postgres psql -U postgres -d govgraph < src/db/schema.sql
```

### 3. Run Ingestion Script Locally
To test the ingestion pipeline without AWS dependencies, set the following environment variables:

```bash
export DB_HOST=localhost
export DB_NAME=govgraph
export DB_USER=postgres
export DB_PASSWORD=postgres

# Run using the project's virtual environment
python src/ingestion/ingest_contracts.py
```

The script will detect these environment variables and bypass AWS Secrets Manager.

### 4. Start Neo4j (Graph DB)
Run a local Neo4j instance for the knowledge graph:

```bash
docker run --name govgraph-neo4j -e NEO4J_AUTH=neo4j/password -p 7474:7474 -p 7687:7687 -d neo4j:5
```

Access the Neo4j Browser at [http://localhost:7474](http://localhost:7474).

### 5. Run Graph Sync
Sync data from PostgreSQL to Neo4j:

```bash
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=password

python src/processing/sync_to_graph.py
```
