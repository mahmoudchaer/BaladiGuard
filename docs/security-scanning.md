# Security scanning and dependency policy

BaladiGuard runs `.github/workflows/security.yml` on pull requests, pushes to
`main`, and weekly on Monday. It covers Python and npm production dependencies,
repository-history secrets, Python SAST, TypeScript/JavaScript lint checks, and
the backend container image.

## Gates and remediation

- `pip-audit` and `npm audit` fail on high or critical known vulnerabilities.
- Trivy fails on high or critical fixed container vulnerabilities; unfixed
  findings are reported but do not block until an upstream fix exists.
- Gitleaks fails on any detected secret. Revoke a secret first; never paste it
  into a workflow log or issue.
- Bandit blocks high-severity/high-confidence Python findings. Medium-confidence
  findings remain visible in the job log for remediation triage. ESLint is the
  JavaScript/TypeScript baseline; security-sensitive rules belong in the
  relevant ESLint configuration.

Every finding must identify the package/file, advisory or rule, affected path,
and practical remediation. CI output must contain identifiers and remediation
text only, never credential values.

## Exceptions and ownership

An exception requires a linked GitHub issue, owner, affected package/rule,
rationale, compensating control, creation date, and expiry within 30 days of
creation. The npm audit gate validates these fields and fails closed when npm
reports a high/critical finding without a parseable advisory ID. Backend owners handle
Python/container findings; web/mobile owners handle npm findings; the repository
owner handles secret incidents. Expired exceptions fail review.

Dependabot opens grouped weekly update pull requests for admin, mobile, backend,
and Docker dependencies. Reviewers inspect changelogs and advisories before
merging. `package-lock.json` files and `backend/requirements.lock` are committed;
CI uses `npm ci` and the pinned Python production/development lockfiles for
reproducible installation.

The current mobile Expo SDK has a time-boxed exception for high-severity
transitive `brace-expansion` and `postcss` advisories. It is recorded in
`security/audit-exceptions.json`, owned by `mobile-platform`, and expires on
2026-08-31 pending an Expo SDK upgrade. The audit gate still fails on any
critical finding, expired exception, or unexpected high-severity advisory.

The weekly scheduled workflow catches vulnerabilities disclosed after merge.
Retain the workflow URL and approved exception issue in the release handoff.

The `main` branch ruleset requires the dependency, secret, static-analysis, and
backend-container Security checks, in addition to the existing backend and mobile
checks. A failed Security job therefore blocks merging.
