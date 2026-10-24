"""Guard: nothing that looks like a credential may be committed (gitleaks also runs in CI)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SKIP_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    ".next",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".terraform",
    "build",
    "dist",
}
SKIP_FILES = {"package-lock.json", ".env"}  # .env is the developer's own, gitignored file
PATTERNS = {
    "AWS access key id": re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"),
    "provider API key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "URL with inline password": re.compile(
        r"://[A-Za-z0-9_.-]+:[^@\s/${}<>'\"]{3,}@(?!localhost:\d+/bionexus\"?\))"
    ),
    "hard-coded secret assignment": re.compile(
        r"(?i)\b(password|passwd|secret|api_?key|token)\b\s*[:=]\s*[\"'][A-Za-z0-9+/_-]{12,}[\"']"
    ),
}


TEXT_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".mjs",
    ".json",
    ".yml",
    ".yaml",
    ".tf",
    ".sh",
    ".md",
    ".sql",
    ".example",
    ".toml",
    ".env",
    "",
}


def candidate_files():
    for path in ROOT.rglob("*"):
        skipped = set(path.parts) & SKIP_DIRS or path.name in SKIP_FILES
        if path.is_file() and not skipped and path.suffix in TEXT_SUFFIXES:
            yield path


def test_no_credential_shaped_strings_are_committed():
    findings = []
    for path in candidate_files():
        if path == Path(__file__):
            continue
        text = path.read_text(errors="ignore")
        for name, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                findings.append(f"{path.relative_to(ROOT)}: {name}: {match.group(0)[:30]}")
    assert not findings, "possible secrets:\n" + "\n".join(findings)


def test_example_env_files_hold_no_values():
    for name in (".env.example", "infra/lightsail/.env.example"):
        for line in (ROOT / name).read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                key, _, value = line.partition("=")
                assert not re.search(r"(?i)secret|password|token|key", key) or value == "", (
                    name,
                    key,
                )
