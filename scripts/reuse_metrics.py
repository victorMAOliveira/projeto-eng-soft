"""Reuse metrics: lines of code reused from components vs. service-specific lines.

For every service (and the frontend) the script finds which ``eh_*``
components it imports (static analysis with ``ast``) and compares:

* **specific LOC** — logical lines of the service package (tests excluded);
* **reused LOC** — logical lines of the components it imports;
* **reuse ratio** — reused / (reused + specific).

Logical lines = non-blank lines that are not comments or docstrings.
Outputs ``docs/relatorio/generated/reuse_metrics.{md,json}`` (``make eval``).
"""

import ast
import io
import json
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "relatorio" / "generated"
COMPONENTS = ["eh_auth", "eh_events", "eh_db", "eh_observability", "eh_http", "eh_ui"]


def logical_lines(path: Path) -> int:
    """Count code lines, ignoring blanks, comments and docstrings (templates/CSS: non-blank)."""
    text = path.read_text(encoding="utf-8")
    if path.suffix != ".py":
        return sum(1 for line in text.splitlines() if line.strip())
    docstring_lines: set[int] = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(getattr(body[0], "value", None), ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                docstring_lines.update(range(body[0].lineno, body[0].end_lineno + 1))
    code_lines: set[int] = set()
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type in (
            tokenize.COMMENT,
            tokenize.NL,
            tokenize.NEWLINE,
            tokenize.INDENT,
            tokenize.DEDENT,
            tokenize.ENDMARKER,
        ):
            continue
        code_lines.update(range(token.start[0], token.end[0] + 1))
    return len(code_lines - docstring_lines)


def package_files(package_dir: Path) -> list[Path]:
    """Source files of a package (Python, plus templates/static for the UI)."""
    files = [p for p in package_dir.rglob("*.py")]
    files += [
        p
        for ext in ("*.html", "*.css", "*.js")
        for p in package_dir.rglob(ext)
        if "vendor" not in p.parts
    ]
    return sorted(files)


def imported_components(files: list[Path]) -> set[str]:
    """Components imported anywhere in ``files``."""
    found: set[str] = set()
    for path in files:
        if path.suffix != ".py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            found.update(n.split(".")[0] for n in names if n.split(".")[0] in COMPONENTS)
    return found


def main() -> int:
    """Compute and write the metrics."""
    component_loc = {
        c: sum(logical_lines(p) for p in package_files(ROOT / "components" / c / "src" / c))
        for c in COMPONENTS
    }
    targets = {
        p.name: p / p.name.replace("-", "_")
        for p in sorted((ROOT / "services").iterdir())
        if (p / p.name.replace("-", "_")).is_dir()
    }
    targets["web-frontend"] = ROOT / "frontend" / "web" / "web_frontend"
    rows, matrix = [], {}
    for name, package in targets.items():
        files = package_files(package)
        specific = sum(logical_lines(p) for p in files)
        used = imported_components(files)
        reused = sum(component_loc[c] for c in used)
        matrix[name] = sorted(used)
        rows.append(
            {
                "service": name,
                "specific_loc": specific,
                "reused_loc": reused,
                "components": len(used),
                "reuse_ratio": round(reused / (reused + specific), 3),
            }
        )
    total_specific = sum(r["specific_loc"] for r in rows)
    total_reused = sum(r["reused_loc"] for r in rows)
    usages = {c: sum(1 for used in matrix.values() if c in used) for c in COMPONENTS}
    without = total_specific + sum(component_loc[c] * usages[c] for c in COMPONENTS)
    with_components = total_specific + sum(component_loc.values())
    summary = {
        "component_loc": component_loc,
        "component_usages": usages,
        "total_specific_loc": total_specific,
        "total_reused_loc": total_reused,
        "overall_reuse_ratio": round(total_reused / (total_reused + total_specific), 3),
        "loc_if_copied": without,
        "loc_with_components": with_components,
        "loc_saved": without - with_components,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "reuse_metrics.json").write_text(
        json.dumps({"rows": rows, "matrix": matrix, "summary": summary}, indent=2) + "\n",
        encoding="utf-8",
    )

    def pct(x: float) -> str:
        return f"{x * 100:.1f}%".replace(".", ",")

    lines = [
        "| Serviço | LOC específicas | LOC reutilizadas (componentes) | Componentes usados | Taxa de reuso |",
        "|---|---|---|---|---|",
        *[
            f"| {r['service']} | {r['specific_loc']} | {r['reused_loc']} | {r['components']} | {pct(r['reuse_ratio'])} |"
            for r in rows
        ],
        f"| **Total** | **{total_specific}** | **{total_reused}** | — | **{pct(summary['overall_reuse_ratio'])}** |",
        "",
        f"Sem componentes, o código comum seria copiado em cada serviço: {without} LOC no total, "
        f"contra {with_components} LOC com componentes — **{summary['loc_saved']} LOC evitadas**.",
    ]
    matrix_lines = [
        "| Serviço | " + " | ".join(COMPONENTS) + " |",
        "|---|" + "---|" * len(COMPONENTS),
        *[
            f"| {name} | " + " | ".join("●" if c in used else "" for c in COMPONENTS) + " |"
            for name, used in matrix.items()
        ],
    ]
    (OUT_DIR / "reuse_metrics.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT_DIR / "reuse_matrix.md").write_text("\n".join(matrix_lines) + "\n", encoding="utf-8")
    print("\n".join(matrix_lines) + "\n\n" + "\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
