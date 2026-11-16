#!/usr/bin/env python3
"""AERO LAB: universal, read-only project manifest validator (stdlib only).

This module intentionally does not perform face swaps or voice synthesis.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
DIGEST = re.compile(r"^[0-9a-fA-F]{64}$")
VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
AUDIO_SUFFIXES = {".wav", ".mp3", ".flac", ".m4a", ".ogg"}
MODES = {"head"}

class ManifestError(ValueError):
    """Manifest is invalid or an asset cannot be safely verified."""

def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ManifestError(reason)

def require_id(value: object, field: str) -> str:
    require(isinstance(value, str) and ID.fullmatch(value) is not None, f"{field}: invalid identifier")
    return value

def resolve_asset(root: Path, relative: object, suffixes: set[str]) -> Path:
    require(isinstance(relative, str) and bool(relative), "asset path must be a nonempty string")
    path = Path(relative)
    require(not path.is_absolute() and ".." not in path.parts, "absolute or parent-traversal path forbidden")
    resolved_root = root.resolve(strict=True)
    resolved = (resolved_root / path).resolve(strict=True)
    require(resolved.is_relative_to(resolved_root), "asset resolves outside workspace")
    require(resolved.is_file(), "asset is not a regular file")
    require(resolved.suffix.lower() in suffixes, "unsupported asset extension")
    return resolved

def checksum(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def validate(manifest: dict, workspace: Path, verify_hashes: bool = True) -> dict:
    require(isinstance(manifest, dict), "manifest must be a JSON object")
    require(manifest.get("schema_version") == "0.1", "unsupported schema_version")
    job_id = require_id(manifest.get("job_id"), "job_id")
    identities = manifest.get("identities")
    assets = manifest.get("assets")
    require(isinstance(identities, list) and len(identities) > 0, "identities must be nonempty array")
    require(isinstance(assets, list) and len(assets) > 0, "assets must be nonempty array")

    identities_by_id = {}
    for identity in identities:
        require(isinstance(identity, dict), "identity entry must be object")
        key = require_id(identity.get("id"), "identity.id")
        require(key not in identities_by_id, "duplicate identity id")
        require(identity.get("head_swap_authorized") is True, "head swap must be specifically authorized")
        require(isinstance(identity.get("authorization_record"), str) and bool(identity["authorization_record"].strip()),
                "identity needs an authorization record reference")
        identities_by_id[key] = identity

    assets_by_id = {}
    for asset in assets:
        require(isinstance(asset, dict), "asset entry must be object")
        key = require_id(asset.get("id"), "asset.id")
        require(key not in assets_by_id, "duplicate asset id")
        kind = asset.get("kind")
        require(kind in {"video", "image", "audio"}, "unsupported asset kind")
        allowed = {"video": VIDEO_SUFFIXES, "image": IMAGE_SUFFIXES, "audio": AUDIO_SUFFIXES}[kind]
        path = resolve_asset(workspace, asset.get("path"), allowed)
        digest = asset.get("sha256")
        require(isinstance(digest, str) and DIGEST.fullmatch(digest) is not None, "sha256 required (64 hexadecimal digits)")
        if verify_hashes:
            require(checksum(path).lower() == digest.lower(), f"checksum mismatch for {key}")
        assets_by_id[key] = {"kind": kind, "path": str(path)}

    src = require_id(manifest.get("source_identity_id"), "source_identity_id")
    target = require_id(manifest.get("target_asset_id"), "target_asset_id")
    require(src in identities_by_id, "source identity not in registry")
    require(target in assets_by_id and assets_by_id[target]["kind"] == "video", "target asset must be a registered video")
    require(manifest.get("mode") in MODES, "unsupported mode")
    require(manifest.get("pipeline_profile") in {"quality", "balanced"}, "unsupported pipeline_profile")
    require(manifest.get("target_use_authorized") is True, "target video usage must be authorized")
    require(isinstance(manifest.get("target_authorization_record"), str) and bool(manifest["target_authorization_record"].strip()),
            "target video needs an authorization record reference")
    voice = manifest.get("voice", {"enabled": False})
    require(isinstance(voice, dict) and isinstance(voice.get("enabled"), bool), "voice.enabled must be boolean")
    require(voice["enabled"] is False, "voice integration is not implemented; keep voice.enabled=false")
    out = manifest.get("output")
    require(isinstance(out, dict) and out.get("preserve_original") is True and out.get("synthetic_content_label") is True,
            "output must preserve originals and label synthetic content")
    return {"job_id": job_id, "source_identity_id": src, "target_asset_id": target,
            "resolved_target_path": assets_by_id[target]["path"], "asset_count": len(assets_by_id),
            "identity_count": len(identities_by_id), "status": "VALIDATED_NOT_RENDERED"}

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an AERO LAB project without modifying media")
    parser.add_argument("manifest", type=Path, help="JSON manifest file")
    parser.add_argument("--workspace", type=Path, required=True, help="root directory of referenced assets")
    args = parser.parse_args(argv)
    try:
        project = json.loads(args.manifest.read_text(encoding="utf-8"))
        result = validate(project, args.workspace)
    except (ManifestError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "INVALID", "reason": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())
