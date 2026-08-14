# ADV Security Layer — Reference

Security checks span multiple gates, not just the static layer, and must be just as deterministic as every other gate — an LLM saying "this looks safe" is the same anti-pattern as an LLM reviewing LLM-written code.

## Where security sits across the pipeline

| Stage | Security checks | Blocks on |
|---|---|---|
| Static | SAST (Semgrep, bandit, gosec, SecurityCodeScan), dependency/SCA scanning, secret detection | Any Critical/High finding |
| Build | SBOM generation (Syft) — artifact, not blocking | — |
| Contract | Schema validation prevents unvalidated input shapes reaching handlers | Contract violation |
| Regression | Security-relevant golden tests (auth bypass attempts, injection payloads as fixed cases) | Any regression |
| Deploy Gate | Container image scan, DAST vs staging, artifact signing/provenance | Critical CVE in final image, failed signature verification |

## Tool set beyond language-specific SAST

- **Container/image scanning**: `Trivy` or `Grype`, run against the final built image in the deploy-gate stage — catches CVEs from the base image itself, which source-level SCA never sees.
- **IaC scanning** (if Terraform/Helm/K8s manifests exist): `checkov` or `tfsec`, in the static stage.
- **SBOM**: `Syft` — not blocking by itself, but makes every future CVE disclosure instantly checkable against what's actually shipped.
- **DAST**: `OWASP ZAP` against the real deployed staging environment, after smoke tests confirm it's up.
- **Supply chain / provenance**: `cosign` (sigstore) signs artifacts; deploy-gate verifies the signature before deploying — stops a compromised CI runner or tampered artifact from reaching production undetected.

## Severity-based blocking, not blanket blocking

A pipeline that hard-fails on every low-severity finding trains people to ignore red pipelines — the alert fatigue becomes its own risk.

- **Critical / High** → blocks merge. No exceptions without an explicit, logged suppression with a reason and expiry date.
- **Medium** → surfaces in the MR, doesn't block, tracked for scheduled remediation.
- **Low / informational** → logged, visible in a dashboard, not surfaced per-MR.

Suppressions live in a committed file (`.trivyignore`, `.semgrepignore` with a reason comment) — never in someone's memory. An unreviewed suppression is a silent hole in the gate, same failure mode as an agent quietly weakening a test.

## Agent-specific consideration

An agent "fixing" a failing security scan by adding a suppression instead of fixing the vulnerability is the security-specific version of the test-weakening anti-pattern. Suppression files belong on the `CODEOWNERS`-protected list alongside test files and CI config — see `assets/guardrails/CODEOWNERS` for the concrete pattern.

## Ready-to-use asset

`assets/security/security-debt-ci-job.yml` + `assets/security/create_security_debt_cards.py` — a GitLab CI job pair that runs Trivy against the final container image and files Plane.so work items for any Critical/High finding, so security debt becomes visible on a Kanban board instead of only living in a CI log. See `references/kanban-integration.md` for the broader pattern this is one instance of.
