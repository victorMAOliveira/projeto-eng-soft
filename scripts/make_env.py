"""Create ``.env`` from ``.env.example`` and fill empty secrets with random values.

Idempotent: existing non-empty values are kept, so running ``make env`` twice
never rotates secrets of a running stack. ``ANTHROPIC_API_KEY`` is never
generated (it is filled by the team, or left empty to use rules mode).
"""

import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GENERATORS = {
    "JWT_SECRET": lambda: secrets.token_urlsafe(48),
    "POSTGRES_PASSWORD": lambda: secrets.token_hex(16),
    "MONGO_PASSWORD": lambda: secrets.token_hex(16),
    "REDIS_PASSWORD": lambda: secrets.token_hex(16),
    "RABBITMQ_PASSWORD": lambda: secrets.token_hex(16),
}


def parse(text: str) -> dict[str, str]:
    """Parse ``KEY=VALUE`` lines (comments and blanks ignored)."""
    values = {}
    for line in text.splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def main() -> int:
    """Write ``.env`` keeping the layout and comments of ``.env.example``."""
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    target = ROOT / ".env"
    current = parse(target.read_text(encoding="utf-8")) if target.exists() else {}
    lines, generated = [], []
    for line in example.splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, _, default = line.partition("=")
            key = key.strip()
            value = current.get(key) or default.strip()
            if not value and key in GENERATORS:
                value = GENERATORS[key]()
                generated.append(key)
            line = f"{key}={value}"
        lines.append(line)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f".env pronto ({len(generated)} segredo(s) gerado(s): {', '.join(generated) or 'nenhum'})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
