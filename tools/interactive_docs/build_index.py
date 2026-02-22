"""Build a local index for the interactive docs tool."""

from __future__ import annotations

import ast
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_MAX_BYTES = 1_500_000
DEFAULT_OUTPUT = "index.json"

IGNORE_DIRS = {
    ".git",
    "venv",
    ".venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    "node_modules",
    "dist",
    "build",
    ".tox",
    ".nox",
    "site-packages",
    ".ipynb_checkpoints",
}

IGNORE_DIR_MARKERS = {".egg-info"}
SKIP_DIR_HINTS = {"data", "datasets", "artifacts", "checkpoints", "models"}
TEXT_EXTENSIONS = {
    ".py", ".md", ".txt", ".rst", ".toml", ".yaml", ".yml", ".json", ".ini", ".cfg", ".csv", ".sh"
}


@dataclass
class SymbolInfo:
    name: str
    kind: str
    line: int
    signature: str | None = None
    docstring: str | None = None


@dataclass
class FileInfo:
    path: str
    size: int
    imports: list[str]
    symbols: list[SymbolInfo]
    summary: str


def detect_repo_root(start: Path | None = None) -> Path:
    base = start or Path.cwd()
    try:
        out = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=base, text=True).strip()
        if out:
            return Path(out)
    except Exception:
        pass
    return base


def is_binary(path: Path) -> bool:
    try:
        raw = path.read_bytes()[:2048]
    except Exception:
        return True
    if b"\x00" in raw:
        return True
    return False


def should_skip_dir(dir_name: str) -> bool:
    if dir_name in IGNORE_DIRS:
        return True
    if any(marker in dir_name for marker in IGNORE_DIR_MARKERS):
        return True
    return dir_name.lower() in SKIP_DIR_HINTS


def should_index_file(path: Path, max_bytes: int = DEFAULT_MAX_BYTES) -> bool:
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return False
    try:
        if path.stat().st_size > max_bytes:
            return False
    except OSError:
        return False
    return not is_binary(path)


def _signature_from_node(node: ast.AST) -> str | None:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None
    args = []
    for arg in node.args.args:
        args.append(arg.arg)
    if node.args.vararg:
        args.append(f"*{node.args.vararg.arg}")
    for arg in node.args.kwonlyargs:
        args.append(arg.arg)
    if node.args.kwarg:
        args.append(f"**{node.args.kwarg.arg}")
    return f"{node.name}({', '.join(args)})"


def parse_python_symbols(source: str) -> tuple[list[SymbolInfo], list[str]]:
    tree = ast.parse(source)
    symbols: list[SymbolInfo] = []
    imports: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            symbols.append(SymbolInfo(name=node.name, kind="class", line=node.lineno, docstring=ast.get_docstring(node)))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(
                SymbolInfo(
                    name=node.name,
                    kind="function",
                    line=node.lineno,
                    signature=_signature_from_node(node),
                    docstring=ast.get_docstring(node),
                )
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.append(module)

    return sorted(symbols, key=lambda s: (s.line, s.name)), sorted(set(i for i in imports if i))


def summarize_file(path: str, symbols: list[SymbolInfo], imports: list[str]) -> str:
    symbol_names = ", ".join(s.name for s in symbols[:5]) or "no top-level symbols"
    import_names = ", ".join(imports[:5]) or "minimal direct imports"
    return f"{path} defines {symbol_names} and depends on {import_names}."


def build_project_overview(index: dict[str, FileInfo], root: Path) -> dict[str, Any]:
    folders: dict[str, int] = {}
    for rel in index:
        top = rel.split("/")[0]
        folders[top] = folders.get(top, 0) + 1

    entrypoints = [p for p in index if p in {"main.py", "README.md"} or p.endswith("/__main__.py")]

    ranked = sorted(
        index.values(),
        key=lambda f: (len(f.symbols), -f.size),
        reverse=True,
    )[:5]

    top_modules = [
        {
            "path": f.path,
            "reason": f"Contains {len(f.symbols)} symbols and acts as a likely implementation hub.",
        }
        for f in ranked
    ]

    return {
        "root": str(root),
        "folders": folders,
        "entrypoints": entrypoints,
        "how_to_run": [
            "python main.py",
            "pytest",
        ],
        "top_modules": top_modules,
    }


def build_index(repo_root: Path, output_path: Path) -> dict[str, Any]:
    files: dict[str, FileInfo] = {}

    for current_root, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [d for d in dirnames if not should_skip_dir(d)]
        base = Path(current_root)
        for filename in filenames:
            path = base / filename
            if not should_index_file(path):
                continue

            rel = path.relative_to(repo_root).as_posix()
            try:
                source = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                source = path.read_text(encoding="utf-8", errors="ignore")

            symbols: list[SymbolInfo] = []
            imports: list[str] = []
            if path.suffix == ".py":
                try:
                    symbols, imports = parse_python_symbols(source)
                except SyntaxError:
                    symbols, imports = [], []

            info = FileInfo(
                path=rel,
                size=path.stat().st_size,
                imports=imports,
                symbols=symbols,
                summary=summarize_file(rel, symbols, imports),
            )
            files[rel] = info

    payload = {
        "repo": repo_root.name,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "overview": build_project_overview(files, repo_root),
        "files": {
            path: {
                **asdict(info),
                "symbols": [asdict(s) for s in info.symbols],
            }
            for path, info in sorted(files.items())
        },
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    repo_root = detect_repo_root()
    output_path = Path(__file__).resolve().parent / DEFAULT_OUTPUT
    data = build_index(repo_root, output_path)
    print(f"Indexed {len(data['files'])} files into {output_path}")


if __name__ == "__main__":
    main()
