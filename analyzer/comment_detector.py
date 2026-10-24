"""
Heurística poliglota para la detección de bloques de código muerto/comentado.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from analyzer.constants import MIN_COMMENTED_CODE_LINES

PROSE_PREFIXES: Tuple[str, ...] = (
    "TODO", "FIXME", "NOTE", "BUG", "HACK", "XXX",
    "Author:", "License:", "Copyright", "noinspection", "type:", "pragma:", "ruff:", "flake8:",
)

DOC_DECORATION_PREFIXES: Tuple[str, ...] = (
    "#", "=", "-", "*", "/", "!", "@param", "@return", ":param", ":return",
)

CODE_SYNTAX_PATTERNS: Tuple[str, ...] = (
    r"^\s*def\s+\w+\s*\(",
    r"^\s*class\s+\w+",
    r"^\s*return(\s+.*)?$",
    r"^\s*import\s+\w+",
    r"^\s*from\s+\w+\s+import",
    r"^\s*if\s+.*:",
    r"^\s*elif\s+.*:",
    r"^\s*else\s*:",
    r"^\s*for\s+.*:",
    r"^\s*while\s+.*:",
    r"^\s*try\s*:",
    r"^\s*except(\s+.*)?:",
    r"^\s*with\s+.*:",
    r"^\s*@\w+",
    r"^\s*[a-zA-Z_]\w*\s*=\s*[^=].+",
    r"^\s*[a-zA-Z_]\w*\([^)]*\)\s*$",
    r"^\s*(const|let|var|function|public|private|protected)\s+",
    r".*;\s*$",
)

COMPILED_CODE_REGEX = re.compile("|".join(f"(?:{pattern})" for pattern in CODE_SYNTAX_PATTERNS))


def extract_comment_body(raw_line: str) -> Optional[str]:
    """Extrae el texto interno si la línea es un comentario, o retorna None."""
    stripped = raw_line.strip()
    if stripped.startswith("#"):
        return stripped.lstrip("#").strip()
    if stripped.startswith("//"):
        return stripped.lstrip("/").strip()
    if stripped.startswith("*") and not stripped.startswith("*/"):
        return stripped.lstrip("*").strip()
    return None


def is_commented_code_line(comment_body: Optional[str]) -> bool:
    """Evalúa si el texto de un comentario corresponde a instrucciones de código."""
    if not comment_body:
        return False
    if comment_body.startswith(PROSE_PREFIXES):
        return False
    if comment_body.startswith(DOC_DECORATION_PREFIXES):
        return False
    return bool(COMPILED_CODE_REGEX.search(comment_body))


def _flush_block(
    current_block: List[int],
    min_consecutive: int,
    blocks: List[Tuple[int, int, int]],
) -> None:
    """Agrega el bloque acumulado si supera el mínimo de líneas consecutivas."""
    if len(current_block) >= min_consecutive:
        blocks.append((current_block[0], current_block[-1], len(current_block)))
    current_block.clear()


def detect_commented_code_blocks(
    lines: List[str],
    min_consecutive: int = MIN_COMMENTED_CODE_LINES,
) -> List[Tuple[int, int, int]]:
    """
    Escanea las líneas de un archivo identificando bloques de código comentado.
    Retorna lista de tuplas: (start_line, end_line, line_count).
    """
    blocks: List[Tuple[int, int, int]] = []
    current_block: List[int] = []

    for line_num, raw_line in enumerate(lines, start=1):
        comment_body = extract_comment_body(raw_line)
        if is_commented_code_line(comment_body):
            current_block.append(line_num)
        else:
            _flush_block(current_block, min_consecutive, blocks)

    _flush_block(current_block, min_consecutive, blocks)
    return blocks
