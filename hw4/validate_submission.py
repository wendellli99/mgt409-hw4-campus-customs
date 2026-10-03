#!/usr/bin/env python3
"""Check the local HW4 hand-in without contacting an API or changing the app.

This verifies packaging, source data, documentation, image links, audit evidence,
and (when requested) Git exclusions and current public-file snapshots. It does
not establish live provider behavior, visual quality, publication, or submission.
"""

from __future__ import annotations

import argparse
import ast
from collections import defaultdict
from datetime import datetime
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sqlite3
import struct
import subprocess
import sys
from urllib.parse import unquote, urlsplit


REQUIRED_FILES = (
    "AI_prompts.md", "requirements.txt", ".env.example", ".gitignore", "README.md",
    "frontend/package.json", "frontend/index.html", "backend/main.py",
    "backend/agent.py", "backend/models.py", "backend/tools.py",
    "backend/prompts/prompt.md", "output/harness.md", "output/design.md",
    "output/usability.md", "output/app_check.html", "output/audit_trail.json",
)
SEED_COUNTS = {"catalogue": 102, "inventory": 612}
# Canonical rows from the course's actual data.zip, not a generated fixture.
SEED_DIGESTS = {
    "catalogue": "9121c3659a1dde7382ff0024bb6e1dfae5c9bbc5bcd47eab92f170dc55800ba3",
    "inventory": "e715fa3d63cd063e242bcaee944204836ae4277bcc4c834cc72b9e3f1956b145",
}
SECRET_PATTERNS = (
    ("provider API key", re.compile(r"\b(?:sk|pk)-[A-Za-z0-9_-]{20,}\b")),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    ("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
)
KEY_ASSIGNMENT = re.compile(
    r"(?im)^\s*(?:export\s+)?(?:PORTKEY|OPENAI|ANTHROPIC|MODEL)_API_KEY\s*[:=]\s*[\"']?([^\s\"'#]+)"
)
PLACEHOLDER = re.compile(r"(?i)(?:your|replace|placeholder|example|changeme|not[-_]a[-_]real|<|\$\{|os\.getenv|None)")


class Report:
    def __init__(self) -> None:
        self.checks: list[dict[str, str]] = []

    def add(self, status: str, area: str, detail: str) -> None:
        self.checks.append({"status": status, "area": area, "detail": detail})

    def require(self, condition: bool, area: str, detail: str) -> None:
        self.add("PASS" if condition else "FAIL", area, detail)

    @property
    def failures(self) -> int:
        return sum(c["status"] == "FAIL" for c in self.checks)


def read_text(root: Path, relative: str) -> str:
    try:
        return (root / relative).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""


def inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def check_files(root: Path, report: Report) -> None:
    missing = [name for name in REQUIRED_FILES if not (root / name).is_file()]
    report.require(not missing, "required tree", "All required files exist" if not missing else "Missing: " + ", ".join(missing))
    empty = [name for name in REQUIRED_FILES if (root / name).is_file() and (root / name).stat().st_size == 0]
    report.require(not empty, "required tree", "Required files are nonempty" if not empty else "Empty: " + ", ".join(empty))
    report.require((root / "frontend/src").is_dir(), "frontend", "frontend/src exists")
    report.require((root / "output/app_check_images").is_dir(), "screenshots", "output/app_check_images exists")
    requirements = read_text(root, "requirements.txt").lower().replace("_", "-")
    report.require("fastapi" in requirements and "pydantic-ai" in requirements and "uvicorn" in requirements, "backend dependencies", "FastAPI, PydanticAI and Uvicorn are declared")
    try:
        package = json.loads(read_text(root, "frontend/package.json"))
        dependencies = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
        report.require(all(name in dependencies for name in ("react", "react-dom", "vite", "typescript")), "frontend", "React, Vite and TypeScript are declared")
        report.require("dev" in package.get("scripts", {}) and "build" in package.get("scripts", {}), "frontend", "Development and build commands are declared")
    except (json.JSONDecodeError, TypeError, AttributeError):
        report.add("FAIL", "frontend", "package.json is missing or invalid")
    python_files = list((root / "backend").glob("*.py"))
    syntax_errors = []
    for path in python_files:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, UnicodeError, SyntaxError) as exc:
            syntax_errors.append(f"{path.name}: {type(exc).__name__}")
    report.require(bool(python_files) and not syntax_errors, "backend syntax", "Backend Python files parse" if python_files and not syntax_errors else "; ".join(syntax_errors) or "No backend Python files")


def check_prompts(root: Path, report: Report) -> None:
    text = read_text(root, "AI_prompts.md")
    headings = list(re.finditer(r"(?m)^##\s+(\d{1,2})\s*[.):\-]\s*(.+)$", text))
    numbers = [int(h.group(1)) for h in headings]
    report.require(numbers == list(range(1, 14)), "working prompts", "Exactly one numbered section for each of Problems 1–13")
    short = []
    for index, heading in enumerate(headings):
        section = text[heading.end():headings[index + 1].start() if index + 1 < len(headings) else len(text)]
        prompts = re.findall(r"(?m)^\s*\d+[.)]\s+(.+)$", section)
        usable = [p for p in prompts if len(p.split()) >= 8]
        if len(usable) < 4:
            short.append(f"Problem {heading.group(1)} has {len(usable)} substantive working prompts")
    report.require(bool(headings) and not short, "working prompts", "At least four substantive working prompts in every problem" if headings and not short else "; ".join(short) or "No prompt sections")
    report.require(not re.search(r"(?im)^#{1,6}\s+Actual user prompt\b", text), "working prompts", "No 'Actual user prompt' section")
    introduction = text[:headings[0].start()] if headings else text
    truthful = bool(re.search(r"(?is)(?:not|aren['’]t)\s+(?:a\s+)?transcript|not\s+.*?separately\s+typed|prepared\s+working\s+prompts", introduction))
    report.require(truthful, "working prompts", "Prepared working prompts are distinguished from invented historical messages")


def image_size(path: Path) -> tuple[int, int]:
    """Read image headers using only the standard library; do not render or edit."""
    raw = path.read_bytes()
    if raw.startswith(b"\x89PNG\r\n\x1a\n") and len(raw) >= 33 and raw[12:16] == b"IHDR":
        if not raw.endswith(b"IEND\xaeB`\x82"):
            raise ValueError("PNG has no terminal IEND chunk")
        return struct.unpack(">II", raw[16:24])
    if raw[:6] in (b"GIF87a", b"GIF89a") and len(raw) > 13:
        return struct.unpack("<HH", raw[6:10])
    if raw.startswith(b"\xff\xd8"):
        offset = 2
        while offset < len(raw):
            if raw[offset] != 0xFF:
                offset += 1
                continue
            while offset < len(raw) and raw[offset] == 0xFF:
                offset += 1
            if offset >= len(raw):
                break
            marker = raw[offset]
            offset += 1
            if marker in (0x01, 0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                continue
            if offset + 2 > len(raw):
                break
            length = struct.unpack(">H", raw[offset:offset + 2])[0]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                if length < 7 or offset + length > len(raw):
                    break
                height, width = struct.unpack(">HH", raw[offset + 3:offset + 7])
                return width, height
            if length < 2:
                break
            offset += length
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        if raw[12:16] == b"VP8X" and len(raw) >= 30:
            width = 1 + int.from_bytes(raw[24:27], "little")
            height = 1 + int.from_bytes(raw[27:30], "little")
            return width, height
        if raw[12:16] == b"VP8 " and len(raw) >= 30 and raw[23:26] == b"\x9d\x01\x2a":
            width, height = struct.unpack("<HH", raw[26:30])
            return width & 0x3FFF, height & 0x3FFF
        if raw[12:16] == b"VP8L" and len(raw) >= 25 and raw[20] == 0x2F:
            bits = int.from_bytes(raw[21:25], "little")
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    raise ValueError("unrecognized or incomplete image")


class AppCheckHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.images: list[dict[str, str]] = []
        self.headings: list[str] = []
        self.captions: list[str] = []
        self.words: list[str] = []
        self.capture: str | None = None
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {k: v or "" for k, v in attrs}
        if tag == "img":
            self.images.append(attributes)
        if tag in ("h1", "h2", "h3", "figcaption", "p"):
            self.capture = tag
            self.parts = []

    def handle_endtag(self, tag: str) -> None:
        if self.capture == tag:
            content = " ".join(" ".join(self.parts).split())
            if tag.startswith("h"):
                self.headings.append(content)
            elif content:
                self.captions.append(content)
            self.capture = None

    def handle_data(self, data: str) -> None:
        self.words.append(data)
        if self.capture:
            self.parts.append(data)


def check_app_check(root: Path, report: Report) -> None:
    text = read_text(root, "output/app_check.html")
    parser = AppCheckHTML()
    try:
        parser.feed(text)
    except Exception as exc:
        report.add("FAIL", "app check", "Could not parse HTML: " + type(exc).__name__)
        return
    report.require(len(parser.images) >= 3, "app check", "At least three screenshot references")
    valid_images: set[Path] = set()
    broken = []
    for image in parser.images:
        source = image.get("src", "")
        split = urlsplit(source)
        if split.scheme or split.netloc or source.startswith(("/", "\\")):
            broken.append("Screenshot source is not a relative local path")
            continue
        target = (root / "output" / unquote(split.path)).resolve()
        if not inside(target, root / "output/app_check_images"):
            broken.append("Screenshot is outside output/app_check_images")
            continue
        if not target.is_file():
            broken.append("Missing screenshot: " + target.name)
            continue
        try:
            width, height = image_size(target)
            if width < 300 or height < 200:
                raise ValueError("too small to show a readable app state")
            valid_images.add(target)
        except (OSError, ValueError, struct.error) as exc:
            broken.append(f"Invalid screenshot {target.name}: {exc}")
        if not image.get("alt", "").strip():
            broken.append("Screenshot has no descriptive alt text: " + target.name)
    report.require(not broken and len(valid_images) >= 3, "app check", "Three distinct, readable image files use portable relative links" if not broken and len(valid_images) >= 3 else "; ".join(broken) or "Fewer than three distinct image files")
    report.require(len(parser.headings) >= 3 and len(parser.captions) >= 3, "app check", "Checks have headings and explanatory captions")
    visible = " ".join(parser.words).lower()
    required_topics = {
        "inventory lookup": bool(re.search(r"inventory|stock", visible)),
        "dynamic search cards": bool(re.search(r"search|category|hoodie", visible)) and "card" in visible,
        "usability feature": "usability" in visible,
    }
    report.require(all(required_topics.values()), "app check", "Inventory, category cards, and a usability check are labeled" if all(required_topics.values()) else "Missing labels: " + ", ".join(k for k, ok in required_topics.items() if not ok))


def check_database(data_dir: Path, root: Path, report: Report) -> set[str]:
    database = data_dir / "campus_customs.db"
    if not database.is_file():
        report.add("FAIL", "source database", "No campus_customs.db at --data-dir")
        return set()
    try:
        with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            report.require(integrity == "ok", "source database", "SQLite integrity check is clean")
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            report.require({"catalogue", "inventory", "users"}.issubset(tables), "source database", "Required catalogue, inventory, and users tables exist")
            if not {"catalogue", "inventory", "users"}.issubset(tables):
                return set()
            counts = {table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in sorted(tables)}
            report.require(all(counts[t] == expected for t, expected in SEED_COUNTS.items()) and counts["users"] >= 1, "source database", "Actual row counts: " + ", ".join(f"{name}={count}" for name, count in counts.items()))
            for table, ordering in (("catalogue", "product_id"), ("inventory", "product_id, size")):
                rows = connection.execute(f"SELECT * FROM {table} ORDER BY {ordering}").fetchall()
                digest = hashlib.sha256(json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
                report.require(digest == SEED_DIGESTS[table], "source database", f"{table} rows match the supplied course data, not a substitute fixture")
            paths = [row[0] for row in connection.execute("SELECT image_file_path FROM catalogue")]
            bad_images = []
            image_hashes: set[str] = set()
            for image_path in paths:
                target = (data_dir / image_path).resolve()
                if not inside(target, data_dir / "products") or not target.is_file():
                    bad_images.append(image_path)
                    continue
                try:
                    width, height = image_size(target)
                    if width < 1 or height < 1:
                        raise ValueError("empty image")
                    image_hashes.add(hashlib.sha256(target.read_bytes()).hexdigest())
                except (OSError, ValueError, struct.error):
                    bad_images.append(image_path)
            report.require(not bad_images and len(paths) == SEED_COUNTS["catalogue"], "product images", "All 102 real catalogue image paths resolve to valid local images" if not bad_images else "Missing/invalid catalogue images: " + ", ".join(bad_images[:8]))
            harness = read_text(root, "output/harness.md").lower()
            missing_fields = []
            for table in sorted(tables):
                if table.lower() not in harness:
                    missing_fields.append(table + " table")
                for row in connection.execute(f'PRAGMA table_info("{table}")'):
                    if row[1].lower() not in harness:
                        missing_fields.append(f"{table}.{row[1]}")
            report.require(not missing_fields, "database harness", "Harness names every actual table and field" if not missing_fields else "Undocumented fields: " + ", ".join(missing_fields))
            orphaned = connection.execute("SELECT COUNT(*) FROM inventory i LEFT JOIN catalogue c ON c.product_id=i.product_id WHERE c.product_id IS NULL").fetchone()[0]
            report.require(orphaned == 0, "source database", "Every inventory row links to a catalogue product")
            return image_hashes
    except (sqlite3.DatabaseError, OSError, TypeError) as exc:
        report.add("FAIL", "source database", "Read-only inspection failed: " + type(exc).__name__)
        return set()


def check_documents(root: Path, report: Report) -> None:
    documents = {
        "output/harness.md": (150, ("model", "tool", "safety", "limit", "context", "history", "password", "uvicorn")),
        "output/design.md": (60, ("design",)),
        "output/usability.md": (100, ("front", "backend")),
        "backend/prompts/prompt.md": (100, ("stock", "price", "privacy|private")),
        "README.md": (100, ("data", "npm", "uvicorn", ".env")),
    }
    for path, (minimum_words, topics) in documents.items():
        text = read_text(root, path)
        missing = [word for word in topics if not re.search(word, text.lower())]
        condition = len(text.split()) >= minimum_words and not missing
        report.require(condition, "documentation", f"{path} contains substantive required guidance" if condition else f"{path}: {len(text.split())} words; missing topics: {', '.join(missing) or 'none'}")
    safety = read_text(root, "backend/prompts/prompt.md").lower()
    report.require(bool(re.search(r"invent|fabricat|ground|database", safety)) and bool(re.search(r"password|credential|secret", safety)) and bool(re.search(r"inject|untrusted|ignore.*instruction", safety)), "agent safety", "Prompt covers grounded facts, protected credentials, and instruction injection")
    usability = read_text(root, "output/usability.md").lower()
    improvement_sections = list(re.finditer(r"(?m)^#{2,4}\s+(.+)$", usability))
    front_sections = [section for section in improvement_sections if re.search(r"front[ -]?end", section.group(1))]
    backend_sections = [section for section in improvement_sections if re.search(r"agent|back[ -]?end", section.group(1))]
    substantive_sections = 0
    for index, section in enumerate(improvement_sections):
        body = usability[section.end():improvement_sections[index + 1].start() if index + 1 < len(improvement_sections) else len(usability)]
        if len(body.split()) >= 30 and re.search(r"shopper|customer|business|cost|trust", body):
            substantive_sections += 1
    report.require(len(front_sections) >= 2 and len(backend_sections) >= 2 and substantive_sections >= 4, "usability", "Two frontend and two agent/backend improvements have substantive shopper/business explanations")
    readme = read_text(root, "README.md")
    report.require("uvicorn main:app --reload --port 8000" in readme, "startup", "README includes the required backend-folder launch command")


def iso_time(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.tzinfo is not None
    except ValueError:
        return False


def check_audit(root: Path, report: Report) -> None:
    try:
        payload = json.loads(read_text(root, "output/audit_trail.json"))
    except json.JSONDecodeError:
        report.add("FAIL", "audit trail", "Audit trail is missing, empty, or invalid JSON")
        return
    events = payload.get("events") if isinstance(payload, dict) else payload
    if not isinstance(events, list) or not events:
        report.add("FAIL", "audit trail", "Audit trail contains no events")
        return
    invalid = []
    runs: dict[str, list[dict]] = defaultdict(list)
    tools = 0
    for number, event in enumerate(events, 1):
        if not isinstance(event, dict):
            invalid.append(f"Event {number} is not an object")
            continue
        run_id = event.get("run_id")
        if not isinstance(run_id, str) or not run_id.strip():
            invalid.append(f"Event {number} has no run_id")
        else:
            runs[run_id].append(event)
        timestamp = event.get("time", event.get("timestamp", event.get("created_at")))
        if not iso_time(timestamp):
            invalid.append(f"Event {number} has no timezone-aware ISO timestamp")
        tool = event.get("tool_name", event.get("tool"))
        if tool:
            if tool not in ("run_start", "run_end"):
                tools += 1
            if not isinstance(tool, str):
                invalid.append(f"Event {number} has an invalid tool name")
            if not any(k in event for k in ("args", "arguments", "args_summary")) or not any(k in event for k in ("result", "result_summary")):
                invalid.append(f"Tool event {number} lacks short args/result")
        if len(json.dumps(event, ensure_ascii=False)) > 8000:
            invalid.append(f"Event {number} is not a short audit summary")
    report.require(not invalid, "audit trail", "Audit events have readable run IDs, timestamps, and short tool summaries" if not invalid else "; ".join(invalid[:8]))
    report.require(tools >= 1, "audit trail", "At least one real recorded tool call exists")
    completed = {run_id for run_id, entries in runs.items() if isinstance(entries[-1].get("stop_reason"), str) and entries[-1]["stop_reason"].strip()}
    report.require(len(completed) >= 2, "audit retention", f"{len(completed)} completed runs are retained with stop reasons; require at least two")
    unfinished = set(runs) - completed
    report.require(not unfinished, "audit trail", "Every recorded run has a terminal stop reason" if not unfinished else f"{len(unfinished)} recorded runs have no stop reason")
    report.add("NOTE", "audit retention", "Multiple retained runs provide evidence of retention; an offline snapshot cannot prove that no older entries were ever deleted")


def secret_findings(data: bytes) -> list[tuple[int, str]]:
    text = data.decode("utf-8", errors="ignore")
    findings = []
    for label, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            findings.append((text.count("\n", 0, match.start()) + 1, label))
    for match in KEY_ASSIGNMENT.finditer(text):
        value = match.group(1).strip("\"'")
        if len(value) >= 12 and not PLACEHOLDER.search(value):
            findings.append((text.count("\n", 0, match.start()) + 1, "non-placeholder API-key assignment"))
    return sorted(set(findings))


def check_env_example(root: Path, report: Report) -> None:
    path = root / ".env.example"
    if not path.is_file():
        return
    findings = secret_findings(path.read_bytes())
    report.require(not findings, "environment example", "Environment example has no detected real keys" if not findings else "Possible credential in .env.example; values are intentionally not printed")


def git_command(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)


def check_git(root: Path, data_dir: Path, image_hashes: set[str], report: Report) -> None:
    result = git_command(root, "rev-parse", "--show-toplevel")
    if result.returncode:
        report.add("FAIL", "git", "--check-git requested but the package is not in an initialized Git repository")
        return
    repo = Path(result.stdout.decode().strip()).resolve()
    ignored_probes = (".env", ".env.local", "data/campus_customs.db", "data/products/example.jpg")
    not_ignored = []
    for relative in ignored_probes:
        candidate = root / relative
        ignored = git_command(repo, "check-ignore", "--no-index", "-q", "--", str(candidate))
        if ignored.returncode != 0:
            not_ignored.append(relative)
    if inside(data_dir, repo):
        actual_db = git_command(repo, "check-ignore", "--no-index", "-q", "--", str(data_dir / "campus_customs.db"))
        if actual_db.returncode != 0:
            not_ignored.append("actual --data-dir/campus_customs.db")
    report.require(not not_ignored, "git exclusions", "Real environment, SQLite data, and original product images are ignored" if not not_ignored else "Not ignored: " + ", ".join(not_ignored))
    listed = git_command(repo, "ls-files", "-z")
    if listed.returncode:
        report.add("FAIL", "git", "Could not inspect tracked/staged files")
        return
    files = [name.decode("utf-8", errors="surrogateescape") for name in listed.stdout.split(b"\x00") if name]
    report.require(bool(files), "git", "Repository has tracked or staged hand-in files")
    prohibited = []
    findings = []
    snapshots = 0
    for name in files:
        path = repo / name
        base = path.name
        if (base == ".env" or (base.startswith(".env.") and base != ".env.example") or path.suffix.lower() in (".db", ".sqlite", ".sqlite3") or "/data/products/" in "/" + name.replace("\\", "/")):
            prohibited.append(name)
        versions: list[tuple[str, bytes]] = []
        if path.is_file():
            versions.append(("working tracked file", path.read_bytes()))
        for revision, label in ((":" + name, "staged file"), ("HEAD:" + name, "committed file")):
            blob = git_command(repo, "show", revision)
            if blob.returncode == 0:
                versions.append((label, blob.stdout))
        for label, content in versions:
            snapshots += 1
            if hashlib.sha256(content).hexdigest() in image_hashes:
                prohibited.append(name + " (original catalogue image)")
            for line, kind in secret_findings(content):
                findings.append(f"{name}:{line} ({label}; {kind})")
    report.require(not prohibited, "public files", "No original databases, product image files, or real .env files are tracked/staged" if not prohibited else "Prohibited public files: " + ", ".join(sorted(set(prohibited))[:12]))
    report.require(not findings, "secret scan", f"No common credential patterns in {snapshots} working/staged/committed file snapshots" if not findings else "Possible secrets; values not printed: " + "; ".join(sorted(set(findings))[:12]))
    report.add("NOTE", "secret scan", "Pattern scanning cannot prove absence of every possible secret or inspect unpublished provider credentials")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent, help="hw4 package directory")
    parser.add_argument("--data-dir", type=Path, help="Directory holding the actual campus_customs.db and products/")
    parser.add_argument("--check-git", action="store_true", help="Require Git exclusions and scan tracked/staged/current committed files")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable report")
    args = parser.parse_args()
    root = args.root.resolve()
    data_dir = args.data_dir.resolve() if args.data_dir else (root.parent / "data" if (root.parent / "data/campus_customs.db").is_file() else root / "data")
    report = Report()
    check_files(root, report)
    check_prompts(root, report)
    hashes = check_database(data_dir, root, report)
    check_documents(root, report)
    check_app_check(root, report)
    check_audit(root, report)
    check_env_example(root, report)
    if args.check_git:
        check_git(root, data_dir, hashes, report)
    else:
        report.add("SKIP", "git", "Git exclusions and tracked/staged secret scanning were not requested; rerun with --check-git before publication")
    report.add("NOTE", "scope", "Passing this offline check does not establish live-agent behavior, visual approval, public GitHub publication, or Canvas submission")
    if args.json:
        print(json.dumps({"ok": report.failures == 0, "failures": report.failures, "checks": report.checks}, indent=2))
    else:
        for check in report.checks:
            print(f"{check['status']}: {check['area']} — {check['detail']}")
        print(f"\nOffline package check: {'PASS' if report.failures == 0 else 'FAIL'} ({report.failures} failed checks)")
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main())
