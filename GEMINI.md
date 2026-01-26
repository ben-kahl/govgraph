# Project: GovGraph

## Project information
* Project name: GovGraph
* Description: An OSINT supply chain intelligence platform for federal procurement analysis. Aggregates USAspending.gov contract data, uses LLMs(Amazon Bedrock) for entity resolution on vendor records, and builds a knowledge graph(Neo4j) to identify vendor relationships, subsidiaries, and contracting patterns."

## Key Features
* AI-Driven Entity Resolution: Utilizes Amazon Bedrock (Claude 3) to normalize inconsistent vendor names (e.g., merging "Lockheed," "LMT," and "Lockheed Martin Corp") with 99% accuracy.
* Infrastructure as Code: Fully provisioned via Terraform with strict cost-control policies (Spot Instances, Single NAT Gateway) enforced via automated tests.
*Kubernetes Native: Microservices architecture deployed on Amazon EKS with autoscaling based on queue depth (KEDA).

## Tech Stack
* Infrastructure: AWS EKS, Terraform, Docker, Helm
* Backend: Python(FastAPI), Boto3, Celery/SQS
* Data & AI: Neo4j(AuraDB free tier), Amazon Bedrock(LLM), Pandas
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

## Implementation Plan
Currently, the core eks infrastructure has been completed in ./infra/main.tf
The next phase of the project is to build out the backend data pipeline
#### **Phase 1: The "Dirty Data" Pipeline (Backend Logic)**
*Focus: Getting data, cleaning it with AI, and printing it to the console.*

* **Task 1.1: The Scraper (Lambda)**
    * Write a Python script that hits the `USAspending` API for yesterday's contracts.
    * *Success:* It prints a JSON list of contracts to the console.
    * *Tech:* Python, `requests`.
* **Task 1.2: The Cleaner (Bedrock Integration)**
    * Write a Python function that takes a "Messy Name" and sends it to Amazon Bedrock (Claude).
    * *Prompt:* "Standardize this company name. 'L.M. Corp' -> 'Lockheed Martin'."
    * *Success:* You input "Boeing Co." and get back "The Boeing Company".
    * *Tech:* `boto3`.
* **Task 1.3: The Infrastructure (Terraform Update)**
    * Add the `aws_lambda_function` and `aws_sqs_queue` resources to your Terraform.
    * *Success:* `terraform apply` creates the queue.


## Repo Structure
```text
gov-graph/
├── .github/workflows/    # CI/CD
├── infra/                # Terraform (Move your current files here)
├── src/
│   ├── ingestion/        # Lambda scripts
│   ├── processing/       # Bedrock/Worker scripts
│   ├── api/              # FastAPI
│   └── dashboard/        # Next.js
├── tests/                # Tests
└── README.md
