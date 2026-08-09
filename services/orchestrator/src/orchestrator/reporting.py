"""Local Markdown finding reports, written to FINDINGS_DIR (workspace/findings/
in docker-compose.yml, git-ignored). This module never touches git - no
service in this repo commits or pushes on its own; a human decides what to
do with a confirmed finding."""

from __future__ import annotations

import os
from datetime import datetime, timezone


def _slugify(value: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in value).strip("_").upper() or "UNKNOWN"


def write_finding_report(
    findings_dir: str,
    *,
    target_name: str,
    category: str,
    severity: str,
    title: str,
    summary: str,
    steps: list[str],
    raw_baseline_request: str,
    raw_baseline_response: str,
    raw_mutated_request: str,
    raw_mutated_response: str,
    remediation: str,
    cvss_score: float | None = None,
) -> str:
    os.makedirs(findings_dir, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"CONFIRMED_{_slugify(category)}_{_slugify(target_name)}_{timestamp}.md"
    path = os.path.join(findings_dir, filename)

    cvss_line = f" (CVSS v3.1: {cvss_score})" if cvss_score is not None else ""
    steps_md = "\n".join(f"{i}. {s}" for i, s in enumerate(steps, start=1))

    content = f"""# [CONFIRMED] {title}

- **Target:** `{target_name}`
- **Severity:** `{severity}`{cvss_line}
- **Vulnerability Category:** `{category}`
- **Discovered Via:** BugOrchestrator (automated probe, human-approved via HITL gate)

## Executive Summary

{summary}

## Steps to Reproduce

{steps_md}

## Raw Proof-of-Concept (HTTP Context)

### Baseline Request

```http
{raw_baseline_request}
```

### Baseline Response

```http
{raw_baseline_response}
```

### Mutated Request

```http
{raw_mutated_request}
```

### Mutated Response

```http
{raw_mutated_response}
```

## Remediation

{remediation}
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path
