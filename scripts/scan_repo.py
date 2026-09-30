"""Pre-commit safety scan: staged files larger than 20 MB and likely secrets.

    python scripts/scan_repo.py          # scans files staged for commit (git diff --cached)
    python scripts/scan_repo.py --all    # scans every tracked + untracked, non-ignored file

Exit code 1 if anything is found (the commit should then be stopped and reviewed).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

MAX_BYTES = 20 * 1024 * 1024
PATTERNS = {
    "private key": re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
    "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "GitHub token": re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),
    "Google API key": re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
    "Slack token": re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}"),
    "Anthropic/OpenAI key": re.compile(r"sk-(ant-)?[A-Za-z0-9_\-]{32,}"),
    "generic secret assignment": re.compile(
        r"(?i)(api[_-]?key|secret|password|passwd|token)\s*[:=]\s*['\"][^'\"\s]{12,}['\"]"
    ),
}
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".parquet", ".npz", ".nc", ".woff", ".woff2", ".pdf"}


def files(all_files: bool, root: Path) -> list[Path]:
    cmd = (
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"]
        if all_files
        else ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"]
    )
    out = subprocess.run(cmd, cwd=root, capture_output=True, text=True, check=True).stdout
    return [root / p for p in out.splitlines() if p.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    root = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True).stdout.strip())
    problems: list[str] = []
    checked = 0
    for f in files(args.all, root):
        if not f.is_file():
            continue
        checked += 1
        size = f.stat().st_size
        if size > MAX_BYTES:
            problems.append(f"LARGE FILE ({size / 1e6:.1f} MB): {f.relative_to(root)}")
        if f.suffix.lower() in SKIP_SUFFIXES or size > 5 * 1024 * 1024:
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for name, pat in PATTERNS.items():
            for m in pat.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                problems.append(f"POSSIBLE {name.upper()}: {f.relative_to(root)}:{line}")
    for p in problems:
        print(p)
    print(f"[scan] {checked} files checked, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
