# Deployment runbook

## Normal staging and production release

1. Confirm the relevant GitHub Environment variables and secret ARN point to the intended environment.
2. Merge an approved change to `main`; watch the staging `Deploy` run through migration, ECS stability, readiness, and admin publication.
3. Verify `GET /health/live` and `GET /health/ready`, sign in to the admin UI, and complete one non-destructive report read/write smoke test.
4. Create an approved `v*` tag from the exact tested commit. Approve the protected production environment when GitHub requests it.
5. Record the workflow URL and attach its deployment manifest to the release ticket.

Never rerun a production job against an unreviewed SHA, change secrets during a deployment, or use the migration script's `--reset` option.

## Failed migration

The workflow stops before updating services. Inspect the stopped `baladiguard-<environment>-migration` task and its CloudWatch log stream. Correct the migration so it is safe to rerun against a partially upgraded database, review it, and release a new commit. Do not manually delete tables or edit production data to force success.

## Failed or unhealthy service release

ECS deployment circuit breakers and the deployment program restore the previous task definitions. Confirm the services are stable and the old `/health/ready` is healthy. If automation itself was interrupted, download the prior successful `deployment-manifest.json` and update each ECS service to its `previous_task_definitions` value, then wait for `services-stable`. Do not roll back database state; releases must preserve backward compatibility.

## Secret rotation drill

Create a new secret version in the target environment, retaining the prior version. Force a new ECS deployment, verify readiness and one authenticated request, then retire the old credential according to the provider's overlap window. If verification fails, restore the previous Secrets Manager version stage and force another deployment. Confirm no secret value appears in Actions or CloudWatch logs.

## Provider outage drill

In staging, deny or temporarily misconfigure one external provider at a time (Bedrock/Rekognition, SES/SNS, or geocoding). Confirm readiness reflects only true platform dependencies, requests fail safely without exposing credentials, queued work can recover, and alerts identify the provider. Restore access and verify backlog processing before ending the drill.

## Quarterly staging recovery drill

Run all three scenarios above in staging: failed migration, unhealthy image rollback, and secret rotation. Also restore one prior S3 object version and verify the expected CloudTrail/GitHub audit trail. Record start time, detection, recovery time, evidence links, and follow-up actions in the operations ticket.

## Emergency stop

Cancel the active GitHub workflow to stop further promotion. If a harmful API is already live, update the API/worker services (`api`, `ai-worker`, `redaction-worker`, `content-safety-worker`) to the last known-good task definitions from the previous manifest. Scaling workers to zero is acceptable only when processing itself is harmful; keep the API available when safe. Escalate credentials or data exposure immediately and rotate affected secrets.
