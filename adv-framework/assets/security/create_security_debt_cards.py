#!/usr/bin/env python3
"""
create_security_debt_cards.py

Reads a Trivy JSON scan report and creates Plane work items for any
Critical/High severity finding, so security debt from the ADV pipeline's
deploy-gate stage becomes visible on the Kanban board instead of only
living in a CI log.

This is a VISIBILITY mechanism, not a substitute for the pipeline's own
severity-based blocking (Critical/High still fails the build per the
ADV Security section) — the card exists so someone has to consciously
triage and close it, even after the immediate build is fixed.

Required environment variables (set as masked GitLab CI/CD variables):
  PLANE_API_KEY            - Plane API key (Settings > API tokens)
  PLANE_WORKSPACE_SLUG     - e.g. "your-workspace"
  PLANE_SECURITY_PROJECT_ID - UUID of the Plane project to file findings into
  PLANE_SECURITY_STATE_ID   - UUID of the target state (e.g. "Backlog" or
                               a dedicated "Security Debt" state)
  PLANE_SECURITY_LABEL_ID   - UUID of a "security" label, for board filtering

Usage:
  python create_security_debt_cards.py --report trivy-report.json
"""

import argparse
import json
import os
import sys
from typing import Optional

import requests

PLANE_BASE_URL = "https://api.plane.so/api/v1"

SEVERITY_TO_PLANE_PRIORITY = {
    "CRITICAL": "urgent",
    "HIGH": "high",
}

TARGET_SEVERITIES = set(SEVERITY_TO_PLANE_PRIORITY.keys())


def load_env_config() -> dict:
    required = [
        "PLANE_API_KEY",
        "PLANE_WORKSPACE_SLUG",
        "PLANE_SECURITY_PROJECT_ID",
        "PLANE_SECURITY_STATE_ID",
        "PLANE_SECURITY_LABEL_ID",
    ]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)
    return {k: os.environ[k] for k in required}


def parse_trivy_findings(report_path: str) -> list[dict]:
    """Normalizes Trivy's report structure into a flat list of findings."""
    with open(report_path) as f:
        data = json.load(f)

    findings = []
    for result in data.get("Results", []):
        target = result.get("Target", "unknown")
        for vuln in result.get("Vulnerabilities", []) or []:
            severity = vuln.get("Severity", "").upper()
            if severity not in TARGET_SEVERITIES:
                continue
            findings.append({
                "id": vuln.get("VulnerabilityID", "UNKNOWN"),
                "pkg_name": vuln.get("PkgName", "unknown"),
                "installed_version": vuln.get("InstalledVersion", "unknown"),
                "fixed_version": vuln.get("FixedVersion", "not yet available"),
                "severity": severity,
                "title": vuln.get("Title", vuln.get("VulnerabilityID", "")),
                "description": vuln.get("Description", ""),
                "target": target,
                "primary_url": vuln.get("PrimaryURL", ""),
            })
    return findings


def find_existing_work_item(config: dict, external_id: str) -> Optional[str]:
    """
    Best-effort lookup for an already-filed card for this exact finding,
    so re-running the scan on every pipeline doesn't flood the board with
    duplicate cards for the same unresolved vulnerability.

    NOTE: verify against current Plane API docs whether GET .../work-items/
    supports filtering by external_id as a query param in your Plane
    version — this is written defensively (falls through to "not found"
    on any non-200) so a filter mismatch fails safe into card creation
    rather than crashing the pipeline.
    """
    url = (
        f"{PLANE_BASE_URL}/workspaces/{config['PLANE_WORKSPACE_SLUG']}"
        f"/projects/{config['PLANE_SECURITY_PROJECT_ID']}/work-items/"
    )
    try:
        resp = requests.get(
            url,
            headers={"X-API-Key": config["PLANE_API_KEY"]},
            params={"external_id": external_id, "external_source": "trivy"},
            timeout=10,
        )
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            if results:
                return results[0]["id"]
    except requests.RequestException as e:
        print(f"  warning: lookup failed ({e}), proceeding to create", file=sys.stderr)
    return None


def create_work_item(config: dict, finding: dict) -> None:
    external_id = f"{finding['id']}-{finding['pkg_name']}"

    existing_id = find_existing_work_item(config, external_id)
    if existing_id:
        print(f"  skip (already tracked): {external_id} -> work item {existing_id}")
        return

    description = (
        f"**Severity:** {finding['severity']}\n"
        f"**Package:** {finding['pkg_name']} (installed: {finding['installed_version']})\n"
        f"**Fixed in:** {finding['fixed_version']}\n"
        f"**Found in:** {finding['target']}\n\n"
        f"{finding['description']}\n\n"
        f"Reference: {finding['primary_url']}\n\n"
        f"---\n"
        f"_Auto-filed by the ADV pipeline's deploy-gate security scan. "
        f"This card exists for triage and tracking — it does not represent "
        f"an unresolved build failure; the pipeline already blocked on this "
        f"finding per the ADV severity policy._"
    )

    payload = {
        "name": f"[SECURITY] {finding['id']} in {finding['pkg_name']} ({finding['severity']})",
        "description": description,
        "priority": SEVERITY_TO_PLANE_PRIORITY[finding["severity"]],
        "state": config["PLANE_SECURITY_STATE_ID"],
        "labels": [config["PLANE_SECURITY_LABEL_ID"]],
        "external_id": external_id,
        "external_source": "trivy",
    }

    url = (
        f"{PLANE_BASE_URL}/workspaces/{config['PLANE_WORKSPACE_SLUG']}"
        f"/projects/{config['PLANE_SECURITY_PROJECT_ID']}/work-items/"
    )
    resp = requests.post(
        url,
        headers={"X-API-Key": config["PLANE_API_KEY"], "Content-Type": "application/json"},
        json=payload,
        timeout=10,
    )

    if resp.status_code in (200, 201):
        print(f"  created: {external_id} -> {resp.json().get('id', '?')}")
    else:
        # Deliberately does not raise — a Plane API hiccup should not fail
        # the deploy pipeline itself, since the actual security gate
        # (severity-based blocking) already ran earlier and independently
        print(f"  warning: failed to create card for {external_id}: "
              f"{resp.status_code} {resp.text[:200]}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, help="Path to Trivy JSON report")
    args = parser.parse_args()

    config = load_env_config()
    findings = parse_trivy_findings(args.report)

    if not findings:
        print("No Critical/High findings — nothing to file.")
        return

    print(f"Found {len(findings)} Critical/High finding(s):")
    for finding in findings:
        create_work_item(config, finding)


if __name__ == "__main__":
    main()
