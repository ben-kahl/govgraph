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
