"""Static artifact validation independent from experimental outcomes."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .registry import RESEARCH_ROOT, experiments, registry
from .governed_comparison import validate_governed_baselines
from .real_site_comparison import load_real_site_catalog, validate_real_site_baselines
from .template_maintenance import validate_frozen_integration_manifest
from .live_websites import load_live_manifest


def validate_manuscript(root: Path) -> list[str]:
    """Perform dependency-free structural checks when a TeX engine is absent."""

    errors: list[str] = []
    tex_files = sorted(root.rglob("*.tex"))
    combined = "\n".join(path.read_text(encoding="utf-8") for path in tex_files)
    for path in tex_files:
        source = path.read_text(encoding="utf-8")
        if source.count("{") != source.count("}"):
            errors.append(f"unbalanced TeX braces: {path.relative_to(root)}")
        begins = re.findall(r"\\begin\{([^}]+)\}", source)
        ends = re.findall(r"\\end\{([^}]+)\}", source)
        if sorted(begins) != sorted(ends):
            errors.append(f"unbalanced TeX environments: {path.relative_to(root)}")
    main = (root / "main.tex").read_text(encoding="utf-8")
    for relative in re.findall(r"\\input\{([^}]+)\}", main):
        candidate = root / (relative if relative.endswith(".tex") else f"{relative}.tex")
        if not candidate.is_file():
            errors.append(f"missing TeX input: {relative}")
    bib = (root / "references.bib").read_text(encoding="utf-8")
    bib_keys = set(re.findall(r"@\w+\{([^,]+),", bib))
    citations = {
        key.strip()
        for group in re.findall(r"\\cite\{([^}]+)\}", combined)
        for key in group.split(",")
    }
    for key in sorted(citations - bib_keys):
        errors.append(f"missing bibliography entry: {key}")
    labels = set(re.findall(r"\\label\{([^}]+)\}", combined))
    references = set(re.findall(r"\\ref\{([^}]+)\}", combined))
    for key in sorted(references - labels):
        errors.append(f"missing TeX label: {key}")
    return errors


def validate_artifact() -> dict[str, Any]:
    errors: list[str] = []
    defined = experiments()
    active = {
        identifier
        for question in registry().get("researchQuestions", {}).values()
        for identifier in question.get("experiments", [])
    }
    retired = set(registry().get("retiredExperiments", []))
    registered = active | retired
    overlap = active & retired
    if overlap:
        errors.append(f"experiments cannot be both active and retired: {sorted(overlap)}")
    if set(defined) != registered:
        errors.append(f"registry mismatch: defined={sorted(defined)} registered={sorted(registered)}")
    manifest = RESEARCH_ROOT / "corpora/manifest.jsonl"
    corpus_rows = 0
    for number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        corpus_rows += 1
        row = json.loads(line)
        path = (manifest.parent / row["path"]).resolve()
        if manifest.parent.resolve() not in path.parents:
            errors.append(f"corpus row {number} escapes root")
            continue
        if not path.is_file():
            errors.append(f"corpus row {number} is missing {path.name}")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != row["sha256"]:
            errors.append(f"corpus row {number} checksum mismatch")
        rights_fields = (
            "license", "provenance", "capturedAt", "sourceUrl",
            "robotsAccess", "redistributionPermission",
        )
        if any(not row.get(field) for field in rights_fields):
            errors.append(f"corpus row {number} lacks rights metadata")
    firecrawl_version = (RESEARCH_ROOT / "baselines/firecrawl/VERSION").read_text().strip()
    if firecrawl_version != "v2.9.0":
        errors.append(f"unexpected Firecrawl pin: {firecrawl_version}")
    errors.extend(
        validate_frozen_integration_manifest(
            RESEARCH_ROOT / "baselines/template-maintenance/frozen-v2-manifest.json"
        )
    )
    try:
        fictional = load_real_site_catalog(RESEARCH_ROOT / "corpora/synthetic-scopes/catalog.json")
        if fictional.get("license") != "CC0-1.0" or any(not site["host"].endswith(".example") for site in fictional["sites"]):
            errors.append("current synthetic scopes must retain CC0 and fictional .example hosts")
        real_sites = load_real_site_catalog(RESEARCH_ROOT / "corpora/real-sites/catalog.json")
        if real_sites.get("license") != "CC0-1.0":
            errors.append("real-site-derived corpus must retain its CC0 fixture license")
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        errors.append(f"invalid T09 catalog: {exc}")
    try:
        errors.extend(validate_real_site_baselines(
            RESEARCH_ROOT / "corpora/real-sites/catalog.json",
            RESEARCH_ROOT / "baselines/real-sites",
        ))
        errors.extend(validate_governed_baselines(RESEARCH_ROOT / "baselines/governed-data"))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        errors.append(f"invalid T09/D10 frozen baseline: {exc}")
    external_schema = json.loads(
        (RESEARCH_ROOT / "corpora/external/manifest.schema.json").read_text(encoding="utf-8")
    )
    required_external = {
        "path", "sha256", "sourceUrl", "capturedAt", "license",
        "redistributionPermission", "robotsAccess", "labelProvenance",
    }
    if not required_external.issubset(set(external_schema.get("required") or [])):
        errors.append("external corpus schema is missing required rights/provenance fields")
    for study in ("news", "commerce"):
        live_manifest = RESEARCH_ROOT / "corpora" / f"live-{study}" / "site-manifest.json"
        try:
            load_live_manifest(live_manifest, expected_study=study)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            errors.append(f"invalid live {study} manifest: {exc}")
    errors.extend(validate_manuscript(RESEARCH_ROOT / "thesis"))
    return {
        "valid": not errors,
        "errors": errors,
        "experiments": len(defined),
        "corpusDocuments": corpus_rows,
        "firecrawlVersion": firecrawl_version,
    }
