"""Redacting local source scan; prints locations and pattern names, never matches."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "Groq token": re.compile(r"gsk_[A-Za-z0-9_-]{12,}"),
    "OpenAI token": re.compile(r"sk-(?:proj-[A-Za-z0-9_-]{20,}|[A-Za-z0-9]{20,})"),
    "Tavily token": re.compile(r"tvly-[A-Za-z0-9_-]{12,}"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "literal Groq assignment": re.compile(r"GROQ_API_KEY[\"']?\s*\]?\s*=\s*[\"'][^\"'\s]{8,}"),
}
TEXT_SUFFIXES = {".py", ".ipynb", ".md", ".json", ".txt", ".example"}
LOCAL_COURSE_DIRS = (
    "01_build_a_structured_generative_ai_application",
    "02_design_a_multimodal_rag_system",
    "03_agents",
    "04_mcp",
)


def main() -> None:
    listed = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT
    )
    paths = {ROOT / raw.decode() for raw in listed.split(b"\0") if raw}
    for directory in LOCAL_COURSE_DIRS:
        if (ROOT / directory).exists():
            paths.update((ROOT / directory).rglob("*"))
    files = 0
    findings = []
    for path in sorted(paths):
        if not path.is_file() or path.name.startswith(".env") or path.suffix not in TEXT_SUFFIXES:
            continue
        files += 1
        for line_number, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
            for label, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append(f"{path.relative_to(ROOT)}:{line_number}: {label}")
    print(f"Scanned {files} source files; {len(findings)} findings (match values never printed).")
    for finding in findings:
        print(finding)
    if findings:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
