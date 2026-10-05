"""Redacting local source scan; prints locations and pattern names, never matches."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "Groq token": re.compile(r"gsk_[A-Za-z0-9_-]{12,}"),
    "OpenAI token": re.compile(r"sk-(?:proj-[A-Za-z0-9_-]{20,}|[A-Za-z0-9]{20,})"),
    "Tavily token": re.compile(r"tvly-[A-Za-z0-9_-]{12,}"),
    "AWS access key": re.compile(r"(?:AKIA|ASIA)[A-Z0-9]{16}"),
    "GitHub token": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    "Langfuse token": re.compile(r"[ps]k-lf-[A-Za-z0-9_-]{16,}"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "literal Groq assignment": re.compile(
        r"GROQ_API_KEY[\"']?\s*\]?\s*=\s*[\"'][^\"'\s]{8,}"
    ),
}
TEXT_SUFFIXES = {
    ".py",
    ".ipynb",
    ".md",
    ".json",
    ".txt",
    ".example",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".html",
    ".css",
    ".yaml",
    ".yml",
    ".toml",
    ".sh",
    ".map",
}
LOCAL_COURSE_DIRS = (
    "01_build_a_structured_generative_ai_application",
    "02_design_a_multimodal_rag_system",
    "03_agents",
    "04_mcp",
)


def scan_files(paths, root):
    """Return only locations and pattern labels; never retain matched values."""
    files = 0
    findings = []
    manifest = hashlib.sha256()
    for path in sorted(set(paths)):
        if (
            not path.is_file()
            or path.is_symlink()
            or path.name.startswith(".env")
            and path.name != ".env.example"
            or path.suffix not in TEXT_SUFFIXES
        ):
            continue
        files += 1
        content = path.read_bytes()
        manifest.update(
            str(path.relative_to(root)).encode()
            + b"\0"
            + hashlib.sha256(content).digest()
        )
        for line_number, line in enumerate(
            content.decode(errors="replace").splitlines(), 1
        ):
            for label, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append(
                        {
                            "file": str(path.relative_to(root)),
                            "line": line_number,
                            "pattern": label,
                        }
                    )
    return {
        "files_scanned": files,
        "input_manifest_sha256": manifest.hexdigest(),
        "findings": findings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--build-root",
        type=Path,
        help="Also scan existing built assets, including JavaScript/HTML/source maps",
    )
    parser.add_argument("--output", type=Path, help="Write a redacted JSON report")
    args = parser.parse_args()
    listed = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
    )
    paths = {ROOT / raw.decode() for raw in listed.split(b"\0") if raw}
    for directory in LOCAL_COURSE_DIRS:
        if (ROOT / directory).exists():
            paths.update((ROOT / directory).rglob("*"))
    if args.output:
        paths.discard(args.output.resolve())
    report = {"source": scan_files(paths, ROOT)}
    if args.build_root:
        build = args.build_root.resolve()
        if not build.is_relative_to(ROOT) or not build.is_dir():
            parser.error(
                "Build root must be an existing directory within the repository"
            )
        report["build"] = scan_files(build.rglob("*"), ROOT)
        if not report["build"]["files_scanned"]:
            parser.error("Build root contains no scannable assets")
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    total = sum(group["files_scanned"] for group in report.values())
    findings = [row for group in report.values() for row in group["findings"]]
    print(
        f"Scanned {total} source/build files; {len(findings)} findings (match values never printed)."
    )
    for finding in findings:
        print(f"{finding['file']}:{finding['line']}: {finding['pattern']}")
    if findings:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
