# Deployment infrastructure

This repository defines the reviewable staging and production platform for BaladiGuard. Issue #74 supplies the code and operating contract; issue #54 performs the first deployment in the AWS account.

For the live AWS resource inventory, domains, and service purposes, see [AWS and DevOps inventory](./aws-devops-inventory.md).

## Target architecture and ownership

| Component | AWS target | Exposure | Owner |
| --- | --- | --- | --- |
| Backend API | ECS Fargate behind an Application Load Balancer | HTTPS at `api.<environment-domain>` | Backend/on-call |
| AI worker | ECS Fargate service | No inbound route | Backend/on-call |
| Image-redaction worker | ECS Fargate service | No inbound route | Backend/on-call |
| Content-safety worker | ECS Fargate service | No inbound route | Backend/on-call |
| Admin UI | Private S3 origin behind CloudFront | HTTPS at `admin.<environment-domain>` | Web/on-call |
| Report photos | Private, encrypted, versioned S3 bucket | Runtime IAM only | Backend/on-call |
| Application data | Existing DynamoDB account, with environment-prefixed tables | Runtime IAM only | Backend/on-call |
| Runtime configuration | One Secrets Manager JSON secret per environment | ECS execution role only | Platform owner |
| Logs and metrics | CloudWatch Logs and ECS Container Insights | AWS console/IAM | Platform owner |

Staging and production use separate Terraform state keys, DNS names, secrets, buckets, ECS clusters, task roles, and DynamoDB table prefixes. Production is not a larger staging service sharing data; it is an isolated instance of the same module.

The initial cost-conscious layout runs Fargate tasks in two public subnets with public addresses so they can reach managed AWS APIs without a NAT gateway. Their security group accepts port 8000 only from the load balancer; workers accept no internet ingress. A later private-subnet/NAT or VPC-endpoint design can be introduced without changing application deployment semantics.

## What Terraform creates

[`infra/deployment/terraform`](../infra/deployment/terraform) creates the VPC, two availability-zone subnets, security groups, ECR repository, ECS services/task definitions, ALB, TLS certificates and DNS records, CloudFront distribution, S3 buckets, log groups, and distinct task/execution IAM roles.

Security defaults are intentional:

- ALB and CloudFront redirect HTTP to TLS and use TLS 1.2 or newer.
- S3 public access is blocked, transport without TLS is denied, encryption and versioning are enabled.
- Runtime roles are service-specific. Applications receive temporary ECS credentials, never access keys.
- Secrets are injected directly from Secrets Manager; Terraform and the workflow hold only the secret ARN/key names.
- Container images are ECR digests and the repository rejects mutable tags.
- API health is checked both inside the task and through `/health/ready` at the ALB.

## Account bootstrap required by #54

An AWS administrator runs [`infra/deployment/bootstrap`](../infra/deployment/bootstrap) once, using local authenticated credentials. Keep this small bootstrap state encrypted and access-controlled. It creates:

1. An encrypted, versioned S3 Terraform-state bucket and a DynamoDB lock table.
2. A GitHub OIDC provider and separate staging/production deployment roles. Trust is limited to this repository and the matching GitHub Environment; no GitHub access keys are created.
3. Immutable, encrypted ECR repositories for the first and subsequent images.

The administrator must also supply a public Route 53 hosted zone, one Secrets Manager JSON secret per environment, and GitHub Environments named `staging` and `production`. Require reviewers for production.

Configure these non-secret GitHub Environment variables:

| Variable | Meaning |
| --- | --- |
| `AWS_DEPLOY_ROLE_ARN` | Environment-specific OIDC role |
| `AWS_REGION` | Deployment region; use `us-east-1` while CloudFront certificates are in this module |
| `TF_STATE_BUCKET` / `TF_LOCK_TABLE` | Remote state and locking |
| `ECR_REPOSITORY_URL` | Environment ECR URL created at bootstrap |
| `ROUTE53_ZONE_ID` | Public zone ID |
| `API_DOMAIN_NAME` / `ADMIN_DOMAIN_NAME` | Environment hostnames |
| `API_URL` | `https://` URL used by the admin build |
| `RUNTIME_SECRET_ARN` | ARN only, not the secret value |

Use [`environments/staging.tfvars.example`](../infra/deployment/terraform/environments/staging.tfvars.example) and its production counterpart for local plans. Never commit real account IDs or secret values.

## Release flow

Every merge to `main` deploys staging. A signed/approved `v*` tag targets production, whose GitHub Environment approval is the promotion gate. A manual run may target either environment.

The workflow assumes the environment OIDC role, builds and pushes one immutable backend image, reconciles Terraform, registers new task revisions, runs the idempotent migration task, then promotes all services. Every backend task definition receives `ALLOWED_HOSTS` from `var.api_domain_name` (the public API hostname, not a Secrets Manager key). It waits for ECS stability and the public readiness endpoint. A stabilization timeout records recent ECS service events, stopped-task reasons, and CloudWatch log group names. A failure restores the previous service task definitions. The admin build is uploaded only after the backend is healthy. Each run retains its deployment manifest and Terraform outputs as a 90-day audit artifact; GitHub and CloudTrail identify the actor.

Migrations must remain additive and backward compatible because old and new tasks overlap during a rolling release. The deployment command never passes `--reset`. Destructive schema/data changes require a separately reviewed expand/migrate/contract sequence.

## Local validation

```sh
terraform fmt -check -recursive infra/deployment
terraform -chdir=infra/deployment/terraform init -backend=false
terraform -chdir=infra/deployment/terraform validate
python -m unittest discover -s scripts/deployment -p 'test_*.py'
```
