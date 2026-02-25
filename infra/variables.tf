# variables.tf

# VPC Variables

variable "vpc_name" {
  description = "Name of the VPC"
  type        = string
  default     = "gov-graph-vpc"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "vpc_azs" {
  description = "Availability Zones"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "vpc_private_subnets" {
  description = "Private Subnet CIDRs"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "vpc_public_subnets" {
  description = "Public Subnet CIDRs"
  type        = list(string)
  default     = ["10.0.101.0/24", "10.0.102.0/24"]
}

variable "vpc_database_subnets" {
  description = "Database Subnet CIDRs"
  type        = list(string)
  default     = ["10.0.21.0/24", "10.0.22.0/24"]
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "admin_email" {
  description = "Email for budget alerts"
  type        = string
  default     = "admin@example.com"
}

# Database Variables

variable "db_name" {
  description = "Name of the PostgreSQL database"
  type        = string
  default     = "govgraphdb"
}

variable "db_username" {
  description = "Username for the database"
  type        = string
  default     = "govgraph"
}

variable "db_instance_class" {
  description = "RDS Instance Class"
  type        = string
  default     = "db.t3.micro"
}

variable "cognito_domain_prefix" {
  description = "Globally unique prefix for the Cognito hosted-UI domain (e.g. gov-graph-auth)"
  type        = string
  default     = "gov-graph-auth"
}

variable "google_oauth_client_id" {
  description = "Google OAuth 2.0 Client ID for Cognito social login"
  type        = string
  sensitive   = true
  default     = ""
}

variable "google_oauth_client_secret" {
  description = "Google OAuth 2.0 Client Secret for Cognito social login"
  type        = string
  sensitive   = true
  default     = ""
}

variable "github_repo_url" {
  description = "GitHub repository URL for Amplify Hosting"
  type        = string
}

variable "github_oauth_token" {
  description = "GitHub OAuth token for Amplify to access the repo"
  type        = string
  sensitive   = true
}

variable "allowed_origins" {
  description = "Comma-separated allowed CORS origins (e.g. http://localhost:3000 or Amplify URL)"
  type        = string
  default     = "http://localhost:3000"
}
