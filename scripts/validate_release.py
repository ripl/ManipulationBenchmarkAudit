#!/usr/bin/env python3
"""Validate the public release package shape, parseability, claims, and hygiene."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

REQUIRED_TOP_LEVEL = {
    "shortcut_solvability",
    "statistical_significance",
    "creeping_overfitting",
    "data_source_dependency",
    "provenance",
    "scripts",
    "CLAIMS.md",
    "public_manifest.json",
    "README.md",
    "SHA256SUMS",
    "LICENSE",
}

ALLOWED_EXTENSIONS = {".csv", ".json", ".yaml", ".yml", ".md", ".py"}
ALLOWED_EXTENSIONLESS = {"LICENSE", "SHA256SUMS", ".gitignore"}
EXCLUDED_EXTENSIONS = {
    ".7z",
    ".avi",
    ".bz2",
    ".ckpt",
    ".db",
    ".gz",
    ".h5",
    ".hdf5",
    ".log",
    ".mov",
    ".mp4",
    ".mkv",
    ".npy",
    ".npz",
    ".onnx",
    ".parquet",
    ".pickle",
    ".pkl",
    ".pth",
    ".pt",
    ".safetensors",
    ".sqlite",
    ".sqlite3",
    ".tar",
    ".tgz",
    ".xz",
    ".zip",
}
EXCLUDED_PATH_PARTS = {
    ".aws",
    ".azure",
    ".cache",
    ".conda",
    ".docker",
    ".git",
    ".gnupg",
    ".ssh",
    "browser_state",
    "cache",
    "checkpoints",
    "conda_env",
    "cookies",
    "datasets",
    "envs",
    "third_party",
    "videos",
    "wandb",
    "weights",
}
SECRET_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bASIA[0-9A-Z]{16}\b"),
    re.compile(r"\bghp_[A-Za-z0-9_]{30,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"),
    re.compile(r"(?i)\bAuthorization\s*:\s*(Bearer|Basic)\s+\S+"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._=-]{20,}"),
    re.compile(r"(?i)\bWANDB_API_KEY\b\s*[:=]\s*[\"']?[A-Za-z0-9_./+=:-]{12,}"),
    re.compile(r"(?i)extra-index-url\s+\S*://[^/\s:]+:[^@\s]+@"),
    re.compile(r"\bX-Amz-Signature=[A-Fa-f0-9]{16,}\b"),
    re.compile(r"(?i)\b(password|api[_-]?key|secret|access[_-]?token|refresh[_-]?token)\b\s*[:=]\s*[\"']?[A-Za-z0-9_./+=:-]{12,}"),
]
MAX_TEXT_FILE_BYTES = 5_000_000
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


def iter_release_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        rel_parts = path.relative_to(root).parts
        if ".git" in rel_parts:
            continue
        if path.is_file():
            files.append(path)
    return sorted(files)


def load_recompute_module(root: Path) -> Any:
    sys.dont_write_bytecode = True
    script = root / "scripts" / "recompute_claims.py"
    spec = importlib.util.spec_from_file_location("recompute_claims", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import scripts/recompute_claims.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_shape(root: Path, errors: list[str]) -> None:
    present = {path.name for path in root.iterdir()}
    missing = sorted(REQUIRED_TOP_LEVEL - present)
    if missing:
        errors.append(f"missing required top-level entries: {missing}")
    for required_dir in ["shortcut_solvability", "statistical_significance", "creeping_overfitting", "data_source_dependency", "provenance", "scripts"]:
        if not (root / required_dir).is_dir():
            errors.append(f"required top-level directory missing: {required_dir}")


def validate_parseability(files: list[Path], root: Path, errors: list[str]) -> dict[str, int]:
    counts = {"csv": 0, "json": 0, "yaml": 0, "md": 0, "py": 0}
    for path in files:
        rel = path.relative_to(root)
        suffix = path.suffix.lower()
        if suffix == ".csv":
            with path.open(newline="") as f:
                rows = list(csv.reader(f))
            if not rows:
                errors.append(f"empty CSV file: {rel}")
            counts["csv"] += 1
        elif suffix == ".json":
            with path.open() as f:
                json.load(f)
            counts["json"] += 1
        elif suffix in {".yaml", ".yml"}:
            text = path.read_text()
            if yaml is not None:
                yaml.safe_load(text)
            elif "\t" in text:
                errors.append(f"YAML file contains tab indentation and PyYAML is unavailable: {rel}")
            counts["yaml"] += 1
        elif suffix == ".md":
            if not path.read_text().strip():
                errors.append(f"empty Markdown file: {rel}")
            counts["md"] += 1
        elif suffix == ".py":
            compile(path.read_text(), str(path), "exec")
            counts["py"] += 1
    return counts


def validate_artifact_types(files: list[Path], root: Path, errors: list[str]) -> None:
    for path in files:
        rel = path.relative_to(root)
        suffix = path.suffix.lower()
        if suffix in EXCLUDED_EXTENSIONS:
            errors.append(f"excluded artifact extension present: {rel}")
        if suffix and suffix not in ALLOWED_EXTENSIONS:
            errors.append(f"unexpected file extension in release: {rel}")
        if not suffix and path.name not in ALLOWED_EXTENSIONLESS:
            errors.append(f"unexpected extensionless file in release: {rel}")
        if path.stat().st_size > MAX_TEXT_FILE_BYTES:
            errors.append(f"file exceeds lightweight size limit: {rel} ({path.stat().st_size} bytes)")
        lowered_parts = {part.lower() for part in rel.parts}
        blocked = sorted((lowered_parts & EXCLUDED_PATH_PARTS) - {".git"})
        if blocked:
            errors.append(f"excluded path component {blocked} present in {rel}")


def validate_credentials(files: list[Path], root: Path, errors: list[str]) -> None:
    risky_names = {
        ".netrc",
        "credentials",
        "credentials.json",
        "cookies.sqlite",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        "id_rsa",
    }
    for path in files:
        rel = path.relative_to(root)
        if path.name.lower() in risky_names:
            errors.append(f"credential-like file name present: {rel}")
            continue
        try:
            text = path.read_text(errors="ignore")
        except UnicodeDecodeError:
            errors.append(f"non-text file could not be scanned: {rel}")
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"high-risk credential pattern matched in {rel}: {pattern.pattern}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_sha256sums(files: list[Path], root: Path, errors: list[str]) -> None:
    manifest_path = root / "SHA256SUMS"
    if not manifest_path.is_file():
        errors.append("missing required top-level SHA256SUMS")
        return

    expected_files = {
        path.relative_to(root).as_posix(): path
        for path in files
        if path.relative_to(root).as_posix() != "SHA256SUMS"
    }
    entries: dict[str, str] = {}
    for line_number, line in enumerate(manifest_path.read_text().splitlines(), start=1):
        if not line.strip():
            errors.append(f"SHA256SUMS line {line_number}: blank lines are not allowed")
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            errors.append(f"SHA256SUMS line {line_number}: expected '<sha256>  <relative_path>'")
            continue
        digest, rel = parts
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            errors.append(f"SHA256SUMS line {line_number}: invalid SHA256 digest")
        if rel.startswith("./") or Path(rel).is_absolute() or ".." in Path(rel).parts:
            errors.append(f"SHA256SUMS line {line_number}: path must be a repository-relative path without leading ./")
        if rel == "SHA256SUMS":
            errors.append("SHA256SUMS must not include itself")
        if rel in entries:
            errors.append(f"SHA256SUMS line {line_number}: duplicate path {rel}")
        entries[rel] = digest

    expected = set(expected_files)
    actual = set(entries)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        errors.append(f"SHA256SUMS missing files: {missing}")
    if extra:
        errors.append(f"SHA256SUMS has extra files: {extra}")

    for rel in sorted(expected & actual):
        actual_digest = sha256_file(expected_files[rel])
        if actual_digest != entries[rel]:
            errors.append(f"SHA256SUMS mismatch for {rel}: expected {entries[rel]}, recomputed {actual_digest}")


def validate_manifest(root: Path, errors: list[str]) -> dict[str, Any]:
    manifest = json.loads((root / "public_manifest.json").read_text())
    groups = {group["directory"]: group for group in manifest.get("artifact_groups", [])}
    for required in ["shortcut_solvability", "statistical_significance", "creeping_overfitting", "data_source_dependency", "provenance"]:
        if required not in groups:
            errors.append(f"public_manifest.json missing artifact group: {required}")
    if not manifest.get("source_candidates_used"):
        errors.append("public_manifest.json must record source candidates")
    return manifest


def validate_provenance(root: Path, errors: list[str]) -> dict[str, Any]:
    provenance_dir = root / "provenance"
    env_path = provenance_dir / "environment_manifest.csv"
    checkpoint_path = provenance_dir / "checkpoint_identity_manifest.csv"
    env_rows: list[dict[str, str]] = []
    checkpoint_rows: list[dict[str, str]] = []

    def read_csv(path: Path, required_columns: set[str], label: str) -> list[dict[str, str]]:
        if not path.is_file():
            errors.append(f"missing {path.relative_to(root)}")
            return []
        with path.open(newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = set(reader.fieldnames or [])
            missing = sorted(required_columns - fieldnames)
            if missing:
                errors.append(f"{label} missing required columns: {missing}")
                return []
            rows = list(reader)
        if not rows:
            errors.append(f"{label} must contain at least one row")
        return rows

    env_required_columns = {
        "record_id",
        "claim_ids",
        "experiments",
        "environment_status",
        "python",
        "cuda",
        "nvidia_driver",
        "pytorch",
        "key_package_versions",
        "evidence",
        "notes",
    }
    checkpoint_required_columns = {
        "record_id",
        "policy_or_model",
        "claim_ids",
        "experiment",
        "artifact_kind",
        "source_repo_or_model_id",
        "upstream_revision",
        "local_filename",
        "file_size_bytes",
        "sha256",
        "identity_status",
        "payload_included",
        "evidence",
        "notes",
    }

    env_rows = read_csv(env_path, env_required_columns, "environment_manifest.csv")
    checkpoint_rows = read_csv(checkpoint_path, checkpoint_required_columns, "checkpoint_identity_manifest.csv")

    required_claims = {
        "shortcut_libero",
        "shortcut_calvin",
        "libero_goal_pairwise_d",
        "libero_layer2",
        "simplerenv_fixed_grid",
        "simplerenv_protocol_abcde",
        "calvin_protocol1",
        "calvin_fresh_sequence",
        "widowx_scripted_dsd_91_of_96",
    }
    required_policy_by_claim = {
        "shortcut_libero": {"DINO+MLP/task-id"},
        "shortcut_calvin": {"DINO+MLP/task-id"},
        "libero_goal_pairwise_d": {"Spatial Forcing", "OpenVLA-OFT", "HiF-VLA", "SimVLA", "Pi0.5 LeRobot"},
        "libero_layer2": {"Spatial Forcing", "SimVLA", "Pi0.5 LeRobot"},
        "simplerenv_fixed_grid": {"CogACT-Base", "SpatialVLA", "InternVLA-M1", "X-VLA-WidowX", "Dexbotic / DB-MemVLA"},
        "simplerenv_protocol_abcde": {"CogACT-Base", "SpatialVLA", "InternVLA-M1", "X-VLA-WidowX", "Dexbotic / DB-MemVLA"},
        "calvin_protocol1": {"X-VLA", "GR-1", "RoboFlamingo"},
        "calvin_fresh_sequence": {"X-VLA", "GR-1", "RoboFlamingo"},
        "widowx_scripted_dsd_91_of_96": {"DINOv2 ViT-S MLP BC"},
    }
    allowed_identity_statuses = {
        "verified_local_sha256",
        "verified_hf_lfs_sha256",
        "best_effort_local_sha256_no_manifest",
        "unknown_exact_weight_files",
        "unknown_backbone_identity",
    }

    def split_claims(value: str) -> set[str]:
        return {part.strip() for part in value.split(";") if part.strip()}

    seen_ids: set[str] = set()
    env_claims: set[str] = set()
    for index, row in enumerate(env_rows, start=2):
        prefix = f"environment_manifest.csv line {index}"
        record_id = row["record_id"].strip()
        if not record_id:
            errors.append(f"{prefix}: record_id is empty")
            continue
        if record_id in seen_ids:
            errors.append(f"{prefix}: duplicate record_id {record_id}")
        seen_ids.add(record_id)
        claims = split_claims(row["claim_ids"])
        env_claims.update(claims)
        if not claims:
            errors.append(f"{prefix}: claim_ids is empty")
        for field in ["experiments", "environment_status", "python", "cuda", "nvidia_driver", "pytorch", "key_package_versions", "evidence", "notes"]:
            if not row[field].strip():
                errors.append(f"{prefix}: {field} is empty")
        if all(row[field].strip().lower() == "unknown" for field in ["python", "cuda", "nvidia_driver", "pytorch"]):
            if "unknown" not in row["environment_status"].lower() and "best_effort" not in row["environment_status"].lower():
                errors.append(f"{prefix}: unknown package fields need an unknown or best_effort environment_status")

    seen_ids.clear()
    checkpoint_claims: set[str] = set()
    observed_policy_by_claim = {claim: set() for claim in required_policy_by_claim}
    status_counts: dict[str, int] = {}
    for index, row in enumerate(checkpoint_rows, start=2):
        prefix = f"checkpoint_identity_manifest.csv line {index}"
        record_id = row["record_id"].strip()
        if not record_id:
            errors.append(f"{prefix}: record_id is empty")
            continue
        if record_id in seen_ids:
            errors.append(f"{prefix}: duplicate record_id {record_id}")
        seen_ids.add(record_id)

        claims = split_claims(row["claim_ids"])
        checkpoint_claims.update(claims)
        policy = row["policy_or_model"].strip()
        for claim in claims:
            if claim in observed_policy_by_claim:
                observed_policy_by_claim[claim].add(policy)
        for field in ["experiment", "policy_or_model", "artifact_kind", "source_repo_or_model_id", "upstream_revision", "local_filename", "file_size_bytes", "sha256", "identity_status", "payload_included", "evidence", "notes"]:
            if not row[field].strip():
                errors.append(f"{prefix}: {field} is empty")

        status = row["identity_status"].strip()
        status_counts[status] = status_counts.get(status, 0) + 1
        if status not in allowed_identity_statuses:
            errors.append(f"{prefix}: unsupported identity_status {status}")
        if row["payload_included"].strip().lower() != "false":
            errors.append(f"{prefix}: payload_included must be false")

        sha = row["sha256"].strip()
        size = row["file_size_bytes"].strip()
        if status.startswith("verified") or status == "best_effort_local_sha256_no_manifest":
            if not HEX64_RE.match(sha):
                errors.append(f"{prefix}: exact checkpoint identity rows need a lowercase 64-hex sha256")
            if not size.isdigit() or int(size) <= 0:
                errors.append(f"{prefix}: exact checkpoint identity rows need a positive integer file_size_bytes")
            if row["source_repo_or_model_id"].strip().lower() == "unknown":
                errors.append(f"{prefix}: exact checkpoint identity rows need a source_repo_or_model_id")
            if row["local_filename"].strip().lower() == "unknown":
                errors.append(f"{prefix}: exact checkpoint identity rows need a local_filename")
        elif status.startswith("unknown"):
            if sha.lower() != "unknown" or size.lower() != "unknown":
                errors.append(f"{prefix}: unknown identity rows must use unknown for sha256 and file_size_bytes")
        else:
            if sha.lower() != "unknown" and not HEX64_RE.match(sha):
                errors.append(f"{prefix}: sha256 must be unknown or lowercase 64-hex")

    missing_env_claims = sorted(required_claims - env_claims)
    if missing_env_claims:
        errors.append(f"environment_manifest.csv missing claim coverage: {missing_env_claims}")
    missing_checkpoint_claims = sorted(required_claims - checkpoint_claims)
    if missing_checkpoint_claims:
        errors.append(f"checkpoint_identity_manifest.csv missing claim coverage: {missing_checkpoint_claims}")
    for claim, required_policies in required_policy_by_claim.items():
        missing_policies = sorted(required_policies - observed_policy_by_claim[claim])
        if missing_policies:
            errors.append(f"checkpoint_identity_manifest.csv missing policies for {claim}: {missing_policies}")

    return {
        "environment_records": len(env_rows),
        "checkpoint_records": len(checkpoint_rows),
        "checkpoint_identity_status_counts": status_counts,
    }


def validate_release(root: Path) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    validate_shape(root, errors)
    files = iter_release_files(root)
    parse_counts = validate_parseability(files, root, errors)
    validate_artifact_types(files, root, errors)
    validate_credentials(files, root, errors)
    validate_sha256sums(files, root, errors)
    manifest = validate_manifest(root, errors)
    provenance_summary = validate_provenance(root, errors)

    recompute = load_recompute_module(root)
    recompute_results, recompute_errors = recompute.recompute_release(root)
    errors.extend(recompute_errors)

    payload = {
        "files_scanned": len(files),
        "parse_counts": parse_counts,
        "manifest_groups": [group["directory"] for group in manifest.get("artifact_groups", [])],
        "provenance_summary": provenance_summary,
        "recompute_results": recompute_results,
        "credential_scan_policy": "credential patterns are hard blockers; private paths/logs/hostnames/W&B links are allowed if credential-clean",
    }
    return payload, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    payload, errors = validate_release(args.root)
    output = {
        "status": "passed" if not errors else "failed",
        "errors": errors,
        **payload,
    }
    print(json.dumps(output, indent=2 if args.pretty else None, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
