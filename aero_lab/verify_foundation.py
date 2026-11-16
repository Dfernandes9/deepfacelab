#!/usr/bin/env python3
"""Non-destructive static checks for DeepFaceLab head-swap integration points."""
from __future__ import annotations
import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "facelib/FaceType.py": ("HEAD", "HEAD_NO_ALIGN"),
    "mainscripts/Extractor.py": ("FaceType.HEAD", "landmarks_3D"),
    "models/Model_SAEHD/Model.py": ("'head'", "XSeg"),
    "mainscripts/Merger.py": ("XSegNet", "MergerConfig"),
    "mainscripts/ExportDFM.py": ("export_dfm",),
    "main.py": ("extract", "train", "merge", "exportdfm"),
    "requirements-cuda.txt": ("tensorflow-gpu==2.4.0",),
}
 
def verify(root: Path = ROOT) -> tuple[bool, list[str]]:
    outcomes = []
    success = True
    for relative, markers in REQUIRED.items():
        path = root / relative
        if not path.is_file():
            success = False
            outcomes.append(f"FAIL missing: {relative}")
            continue
        try:
            content = path.read_text(encoding="utf-8-sig")
            if path.suffix == ".py":
                ast.parse(content, filename=relative)
        except (OSError, UnicodeError, SyntaxError) as exc:
            success = False
            outcomes.append(f"FAIL unreadable/invalid: {relative}: {exc}")
            continue
        missing = [marker for marker in markers if marker not in content]
        if missing:
            success = False
            outcomes.append(f"FAIL missing markers: {relative}: {', '.join(missing)}")
        else:
            outcomes.append(f"PASS: {relative}")
    return success, outcomes

def main() -> int:
    ok, messages = verify()
    print("AERO LAB static foundation checks (no model runtime/test inference)")
    for message in messages:
        print(message)
    print("PASS static foundation" if ok else "FAIL static foundation")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
