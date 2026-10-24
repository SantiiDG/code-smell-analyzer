"""
Constantes globales, umbrales de Clean Code y configuraciones de lenguajes.
Centraliza todos los valores numéricos para evitar Magic Numbers en la lógica.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Set

# Pesos de severidad para el cálculo del Health Score
WEIGHT_CRITICAL: int = 10
WEIGHT_HIGH: int = 5
WEIGHT_MEDIUM: int = 2

# Umbrales por defecto de Clean Code
DEFAULT_MAX_LINE_FUNC: int = 35
DEFAULT_MAX_LINE_FILE: int = 300
DEFAULT_MAX_PARAMS: int = 4
DEFAULT_MAX_NESTING: int = 3
DEFAULT_MAX_LINE_CLASS: int = 200
DEFAULT_MAX_METHODS_CLASS: int = 12
DEFAULT_MAX_COMPLEXITY: int = 10

# Multiplicadores y márgenes de escalado de severidad
CRITICAL_MULTIPLIER: int = 2
HIGH_PARAM_OFFSET: int = 2
CRITICAL_NESTING_OFFSET: int = 2
CRITICAL_METHOD_LIMIT: int = 20
MIN_COMMENTED_CODE_LINES: int = 3
HIGH_COMMENTED_CODE_LINES: int = 6
MIN_COMPLEX_BOOL_OPS: int = 3
PARAM_PREVIEW_LIMIT: int = 4
TOP_PRIORITY_COUNT: int = 3

# Parámetros de cálculo de Health Score (0.0 a 100.0)
MAX_HEALTH_SCORE: float = 100.0
MIN_HEALTH_SCORE: float = 0.0
DENSITY_PENALTY_FACTOR: float = 4.5
LOC_NORMALIZATION_FACTOR: float = 100.0

SCORE_GRADE_A_PLUS: float = 95.0
SCORE_GRADE_A: float = 90.0
SCORE_GRADE_B: float = 80.0
SCORE_GRADE_C: float = 70.0
SCORE_GRADE_D: float = 60.0
SCORE_GREEN_THRESHOLD: float = 85.0

# Literales numéricos idiomáticos exentos de ser considerados Magic Numbers
ALLOWED_NUMERIC_LITERALS: FrozenSet[int | float] = frozenset(
    {-1, 0, 1, 2, 0.0, 1.0, 0.5, 100}
)

# Anchos y separadores de tablas en consola
PLAIN_SEPARATOR_WIDTH: int = 75
COL_WIDTH_LINE: int = 8
COL_WIDTH_SEVERITY: int = 12
COL_WIDTH_SMELL: int = 26

# Directorios y archivos ignorados automáticamente durante el descubrimiento
IGNORED_DIRS: Set[str] = {
    ".git", ".svn", ".hg", "node_modules", "venv", ".venv", "env", ".env",
    "__pycache__", "dist", "build", ".idea", ".vscode", ".tox", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "coverage", ".coverage", ".eggs", "site-packages",
}

IGNORED_FILE_SUFFIXES: Set[str] = {
    ".min.js", ".min.css", ".map", ".lock", "package-lock.json",
    "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
}

BINARY_EXTENSIONS: Set[str] = {
    ".pyc", ".pyo", ".so", ".dll", ".dylib", ".exe", ".bin", ".class",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".pdf", ".zip",
    ".tar", ".gz", ".7z", ".rar", ".woff", ".woff2", ".ttf", ".eot",
}

LANGUAGE_EXTENSIONS: Dict[str, Set[str]] = {
    "py": {".py"},
    "python": {".py"},
    "js": {".js", ".mjs", ".cjs", ".jsx"},
    "javascript": {".js", ".mjs", ".cjs", ".jsx"},
    "ts": {".ts", ".mts", ".cts", ".tsx"},
    "typescript": {".ts", ".mts", ".cts", ".tsx"},
    "java": {".java"},
    "c": {".c", ".h"},
    "cpp": {".cpp", ".cc", ".cxx", ".hpp", ".h"},
    "csharp": {".cs"},
    "cs": {".cs"},
    "go": {".go"},
    "php": {".php"},
    "ruby": {".rb"},
}

ALL_SUPPORTED_EXTENSIONS: Set[str] = {
    ext for exts in LANGUAGE_EXTENSIONS.values() for ext in exts
}
