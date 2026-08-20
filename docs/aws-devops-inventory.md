# AWS and DevOps inventory

This is the operational map of the AWS resources currently used by BaladiGuard. It is for future maintainers: it explains what is live, why it exists, and where changes should be made. It intentionally contains no credentials, secret values, or account identifiers.

For infrastructure code and release mechanics, see [deployment-infrastructure.md](./deployment-infrastructure.md). For a normal release, see [deployment-runbook.md](./deployment-runbook.md).

## Live environments and public URLs

| Environment | API | Staff admin | Citizen web | Purpose |
| --- | --- | --- | --- | --- |
| Staging | `https://api.staging.baladiguard.site` | `https://admin.staging.baladiguard.site` | `https://staging.baladiguard.site` | Release validation before production |
| Production | `https://api.baladiguard.site` | `https://admin.baladiguard.site` | `https://baladiguard.site` | Public MVP |

The API readiness probe is available at `/health/ready`. All public endpoints use HTTPS. DNS is hosted in Route 53; the domain registrar delegates `baladiguard.site` to the Route 53 nameservers.

## Architecture at a glance

```text
Browser / mobile
       | HTTPS
       +--> CloudFront --> private S3: citizen web and staff admin
       |
       +--> ALB --> ECS Fargate API --> DynamoDB, private report-photo S3, AWS services
                         |
                         +--> ECS AI worker and image-redaction worker

GitHub Actions -- OIDC --> environment-specific AWS deploy role
       --> ECR image --> Terraform --> ECS migration --> ECS service promotion
```

Staging and production do not share application data, runtime secrets, ECS clusters, S3 buckets, or DynamoDB table prefixes.

## AWS services in use

| Service | What exists | What it serves |
| --- | --- | --- |
| Route 53 | Public hosted zone for `baladiguard.site` | DNS for API, admin, citizen web, and ACM validation records |
| ACM | Separate certificates for every API/admin/citizen hostname in `us-east-1` | TLS for the ALBs and CloudFront distributions |
| VPC, subnets, security groups | One VPC per environment, with two public subnets | ECS networking; only the ALB can reach the API on port 8000; workers have no inbound route |
| Application Load Balancer | One HTTPS ALB per environment | Terminates API HTTPS and forwards to the ECS API task; HTTP redirects to HTTPS |
| ECS Fargate | `baladiguard-staging` and `baladiguard-production` clusters | API, AI worker, image-redaction worker, and one-off migration tasks |
| ECR | One immutable backend repository per environment | Stores digest-pinned backend images built by GitHub Actions |
| DynamoDB | Environment-prefixed application tables, plus a Terraform state-lock table | Tickets, accounts, OTP/session state, workforce data, queues, audit/history, rate limiting, and deployment locking |
| S3 | Environment photo buckets; admin buckets; production citizen-web bucket; Terraform state bucket | Private report photos, static web assets, and encrypted/versioned Terraform state |
| CloudFront | Admin and citizen-web distributions per environment | HTTPS static-site delivery, SPA route fallback, caching, HSTS, CSP, and other browser security headers |
| Secrets Manager | `baladiguard/staging/runtime` and `baladiguard/production/runtime` | Runtime-only configuration such as application signing key, CORS origins, SES settings, and smoke token; injected into ECS without exposing values to CI/Terraform |
| IAM and GitHub OIDC | Dedicated staging and production GitHub deploy roles; ECS task/execution roles | Short-lived credentials for CI and least-privilege service access; no long-lived deployment key is used |
| CloudWatch | ECS log groups and Container Insights | API/worker/migration logs and runtime diagnostics |

## Application AWS integrations

| Integration | Current use | Operational note |
| --- | --- | --- |
| Amazon Bedrock | AI worker classification | Nova Lite is the active model integration. Monitor worker logs and queue tables for failures/backlog. |
| Amazon Rekognition | Image-redaction worker | Production runtime enables redaction before a photo is made publicly usable. |
| Amazon Location Service | Place validation/search | Uses the `baladiguard-places` place index. |
| Amazon SES | Email notifications from `baladi.guard@outlook.com` | The account is currently in the SES sandbox: delivery is limited to verified recipients until SES production access is approved. |
| SNS | SMS integration configuration | Sender/configuration is held only in the runtime secret; validate provider approval before relying on real OTP delivery. |

## Deployment and ownership

`main` is the deployment source:

1. A merge to `main` runs CI and deploys staging.
2. A reviewed `v*` tag on `main` deploys production.
3. GitHub Environment rules allow production only from `main`.

The workflow builds an immutable backend image, applies Terraform with remote state, runs the idempotent database migration, promotes ECS services, verifies API readiness, then publishes the staff admin build. Deployment manifests and Terraform outputs are retained as GitHub Action artifacts for 90 days.

Citizen web in both environments is provisioned by the reviewed CloudFormation template at [`citizen-web/infra/cloudfront-spa.json`](../citizen-web/infra/cloudfront-spa.json). Its production bundle must use:

```text
VITE_APP_ENV=production
VITE_API_BASE_URL=https://api.baladiguard.site
VITE_USE_MOCK_DATA=false
```

Its API origin must remain listed in production `CORS_ALLOWED_ORIGINS`. The citizen site and the API intentionally share the `baladiguard.site` registrable domain so secure cookie-based citizen sessions remain compatible.

## Important operational limits and follow-up work

- SES production access has not been approved; notification delivery is not yet ready for arbitrary recipients.
- CloudWatch logs exist, but the production alarm/dashboard work belongs to the observability ticket. Do not interpret the absence of an alarm as monitoring coverage.
- The current Fargate layout uses public subnets/public IPs for cost-conscious outbound access to managed AWS APIs. A future private-subnet design should use NAT gateways or VPC endpoints.
- Citizen web hosting is live; ongoing UX/accessibility/browser refinement remains in issue #314.
- Never place secrets in this document, GitHub variables, source code, a client bundle, or Terraform variables. Store values in the environment runtime secret and reference only the ARN/key names.

## Safe checks for maintainers

```sh
# Public API readiness
curl -fsS https://api.baladiguard.site/health/ready

# ECS service status (use an authorised profile)
aws ecs describe-services --cluster baladiguard-production \
  --services api ai-worker redaction-worker --region us-east-1

# Recent API logs
aws logs tail /ecs/baladiguard-production/api --since 30m --region us-east-1
```

Use the [deployment runbook](./deployment-runbook.md) for rollback and migration failures. Do not manually alter DynamoDB application data or delete ECS/S3 resources to work around a failed deployment.
