#!/usr/bin/env python3
"""
================================================================================
Clean Code Smell Analyzer (CLI)
================================================================================
Autor: Principal Software Engineer & Clean Code Specialist
Licencia: MIT
Requisitos: Python 3.10+ (Biblioteca estándar + Soporte opcional para 'rich')

Analizador estático de arquitectura y código limpio para detección exhaustiva
y accionable de deuda técnica, anti-patrones y code smells.
================================================================================
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass, field
from enum import Enum
import math
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Dict, Generator, List, Optional, Set, Tuple

# Reconfigurar stdout y stderr para soportar UTF-8 en consolas Windows (cp1252)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ------------------------------------------------------------------------------
# Detección e Integración Opcional de 'rich'
# ------------------------------------------------------------------------------
HAS_RICH = False
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


# ------------------------------------------------------------------------------
# Modelos de Dominio y Enumeraciones
# ------------------------------------------------------------------------------
class Severity(str, Enum):
    CRITICA = "CRÍTICA"
    ALTA = "ALTA"
    MEDIA = "MEDIA"

    @property
    def weight(self) -> int:
        """Ponderación de penalización para cálculo de salud del proyecto."""
        if self == Severity.CRITICA:
            return 10
        elif self == Severity.ALTA:
            return 5
        return 2

    @property
    def color_ansi(self) -> str:
        if self == Severity.CRITICA:
            return "\033[91m\033[1m"  # Bold Red
        elif self == Severity.ALTA:
            return "\033[93m\033[1m"  # Bold Yellow
        return "\033[96m"             # Cyan

    @property
    def rich_style(self) -> str:
        if self == Severity.CRITICA:
            return "bold red"
        elif self == Severity.ALTA:
            return "bold yellow"
        return "cyan"


class SmellType(str, Enum):
    LONG_METHOD = "Long Method / Function"
    GOD_CLASS = "God Class"
    LARGE_FILE = "Large File"
    DEEP_NESTING = "Deep Nesting"
    LONG_PARAMETER_LIST = "Long Parameter List"
    MAGIC_NUMBER = "Magic Number"
    DEAD_COMMENTED_CODE = "Dead / Commented-out Code"
    COMPLEX_CONDITION = "Complex Condition"


@dataclass
class CodeSmell:
    file_path: Path
    line: int
    smell_type: SmellType
    severity: Severity
    diagnosis: str
    suggestion: str
    symbol_name: Optional[str] = None


@dataclass
class AnalysisConfig:
    path: Path
    lang: str = "all"
    max_line_func: int = 35
    max_line_file: int = 300
    max_params: int = 4
    max_nesting: int = 3
    max_line_class: int = 200
    max_methods_class: int = 12
    export_path: Optional[Path] = None
    min_severity: Optional[Severity] = None
    no_color: bool = False


@dataclass
class FileAnalysisResult:
    path: Path
    lines_count: int
    smells: List[CodeSmell] = field(default_factory=list)

    @property
    def penalty_score(self) -> int:
        return sum(s.severity.weight for s in self.smells)


@dataclass
class ProjectReport:
    total_files_scanned: int
    total_loc: int
    duration_seconds: float
    file_results: List[FileAnalysisResult]

    @property
    def all_smells(self) -> List[CodeSmell]:
        res = []
        for f in self.file_results:
            res.extend(f.smells)
        return res

    @property
    def total_penalties(self) -> int:
        return sum(f.penalty_score for f in self.file_results)

    @property
    def health_score(self) -> Tuple[float, str, str]:
        """
        Retorna (puntuación_numérica, calificación, descripción).
        Cálculo basado en la densidad de penalizaciones por cada 100 líneas de código.
        """
        if self.total_loc == 0:
            return 100.0, "A+", "Excelente: Código limpio sin deuda aparente"

        density = (self.total_penalties / self.total_loc) * 100.0
        # Escala no lineal graduada
        raw_score = 100.0 - (density * 4.5)
        score = max(0.0, min(100.0, round(raw_score, 1)))

        if score >= 95.0:
            return score, "A+", "Excelente: Código limpio, arquitectura sólida y mantenible"
        elif score >= 90.0:
            return score, "A", "Muy Bueno: Mínima deuda técnica acumulada"
        elif score >= 80.0:
            return score, "B", "Aceptable: Requiere refactorizaciones preventivas puntuales"
        elif score >= 70.0:
            return score, "C", "Regular: Acumulación moderada de smells y acoplamiento"
        elif score >= 60.0:
            return score, "D", "Deficiente: Alta deuda técnica con riesgo de regresión"
        else:
            return score, "F", "Crítico: Fragilidad arquitectónica y urgente refactorización"

    @property
    def top_priority_files(self) -> List[FileAnalysisResult]:
        files_with_smells = [f for f in self.file_results if f.smells]
        return sorted(files_with_smells, key=lambda x: x.penalty_score, reverse=True)[:3]


# ------------------------------------------------------------------------------
# Motor de Descubrimiento e Ignorado de Archivos
# ------------------------------------------------------------------------------
IGNORED_DIRS: Set[str] = {
    ".git", ".svn", ".hg", "node_modules", "venv", ".venv", "env", ".env",
    "__pycache__", "dist", "build", ".idea", ".vscode", ".tox", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "coverage", ".coverage", ".eggs", "site-packages"
}

IGNORED_FILE_SUFFIXES: Set[str] = {
    ".min.js", ".min.css", ".map", ".lock", "package-lock.json",
    "yarn.lock", "pnpm-lock.yaml", "poetry.lock"
}

BINARY_EXTENSIONS: Set[str] = {
    ".pyc", ".pyo", ".so", ".dll", ".dylib", ".exe", ".bin", ".class",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".pdf", ".zip",
    ".tar", ".gz", ".7z", ".rar", ".woff", ".woff2", ".ttf", ".eot"
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

ALL_SUPPORTED_EXTENSIONS: Set[str] = set()
for exts in LANGUAGE_EXTENSIONS.values():
    ALL_SUPPORTED_EXTENSIONS.update(exts)


def is_ignored_path(path: Path) -> bool:
    for part in path.parts:
        if part in IGNORED_DIRS or part.startswith(".egg-info"):
            return True
    name_lower = path.name.lower()
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return True
    for suff in IGNORED_FILE_SUFFIXES:
        if name_lower.endswith(suff):
            return True
    return False


def discover_files(root: Path, lang: str) -> Generator[Path, None, None]:
    target_extensions: Optional[Set[str]] = None
    if lang.lower() != "all":
        target_extensions = LANGUAGE_EXTENSIONS.get(lang.lower())
        if not target_extensions:
            # Si el usuario introdujo directamente una extensión como '.py' o 'py'
            clean_ext = f".{lang.lstrip('.')}"
            target_extensions = {clean_ext}

    if root.is_file():
        if not is_ignored_path(root):
            yield root
        return

    for current_dir, dirnames, filenames in os.walk(root):
        # Prune directorios ignorados en tiempo de escaneo
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS and not d.startswith(".egg-info")]

        for filename in filenames:
            file_path = Path(current_dir) / filename
            if is_ignored_path(file_path):
                continue

            ext = file_path.suffix.lower()
            if target_extensions is not None:
                if ext in target_extensions:
                    yield file_path
            else:
                if ext in ALL_SUPPORTED_EXTENSIONS:
                    yield file_path


# ------------------------------------------------------------------------------
# Heurística de Detección de Código Comentado (Polyglot)
# ------------------------------------------------------------------------------
def detect_commented_code_blocks(
    lines: List[str],
    min_consecutive: int = 3
) -> List[Tuple[int, int, int]]:
    """
    Detecta bloques de código comentado inspeccionando patrones sintácticos
    dentro de líneas con prefijos `#`, `//` o `*`.
    Retorna lista de tuplas: (start_line, end_line, line_count).
    """
    code_indicators = [
        r'^\s*def\s+\w+\s*\(',
        r'^\s*class\s+\w+',
        r'^\s*return(\s+.*)?$',
        r'^\s*import\s+\w+',
        r'^\s*from\s+\w+\s+import',
        r'^\s*if\s+.*:',
        r'^\s*elif\s+.*:',
        r'^\s*else\s*:',
        r'^\s*for\s+.*:',
        r'^\s*while\s+.*:',
        r'^\s*try\s*:',
        r'^\s*except(\s+.*)?:',
        r'^\s*with\s+.*:',
        r'^\s*@\w+',
        r'^\s*[a-zA-Z_]\w*\s*=\s*[^=].+',
        r'^\s*[a-zA-Z_]\w*\([^)]*\)\s*$',
        r'^\s*(const|let|var|function|public|private|protected)\s+',
        r'.*;\s*$',
    ]
    code_regex = re.compile('|'.join(f'(?:{p})' for p in code_indicators))

    blocks: List[Tuple[int, int, int]] = []
    current_block: List[int] = []

    for idx, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()
        comment_content = None
        if stripped.startswith('#'):
            comment_content = stripped.lstrip('#').strip()
        elif stripped.startswith('//'):
            comment_content = stripped.lstrip('/').strip()
        elif stripped.startswith('*') and not stripped.startswith('*/'):
            comment_content = stripped.lstrip('*').strip()

        if comment_content is not None:
            # Excluir cabeceras, notas de autor o etiquetas habituales
            is_prose = (
                comment_content.startswith(('TODO', 'FIXME', 'NOTE', 'BUG', 'HACK', 'XXX', 'Author:', 'License:', 'Copyright'))
                or comment_content.startswith(('#', '=', '-', '*', '/', '!', '@param', '@return', ':param', ':return'))
            )
            if not is_prose and code_regex.search(comment_content):
                current_block.append(idx)
            else:
                if len(current_block) >= min_consecutive:
                    blocks.append((current_block[0], current_block[-1], len(current_block)))
                current_block = []
        else:
            if len(current_block) >= min_consecutive:
                blocks.append((current_block[0], current_block[-1], len(current_block)))
            current_block = []

    if len(current_block) >= min_consecutive:
        blocks.append((current_block[0], current_block[-1], len(current_block)))

    return blocks


# ------------------------------------------------------------------------------
# Analizador Estático AST para Python
# ------------------------------------------------------------------------------
class PythonASTAnalyzer:
    def __init__(self, config: AnalysisConfig):
        self.config = config

    def analyze(self, file_path: Path, content: str) -> List[CodeSmell]:
        smells: List[CodeSmell] = []
        lines = content.splitlines()
        total_lines = len(lines)

        # 1. Smell: Large File
        if total_lines > self.config.max_line_file:
            sev = Severity.CRITICA if total_lines >= self.config.max_line_file * 2 else Severity.MEDIA
            smells.append(CodeSmell(
                file_path=file_path,
                line=1,
                smell_type=SmellType.LARGE_FILE,
                severity=sev,
                diagnosis=f"Archivo extenso de {total_lines} líneas (límite recomendado: {self.config.max_line_file}).",
                suggestion="Modularizar dividiendo responsabilidades en submódulos especializados (Domain, Services, DTOs)."
            ))

        # 2. Smell: Dead / Commented-out Code
        commented_blocks = detect_commented_code_blocks(lines, min_consecutive=3)
        for start_l, end_l, count in commented_blocks:
            sev = Severity.ALTA if count >= 6 else Severity.MEDIA
            smells.append(CodeSmell(
                file_path=file_path,
                line=start_l,
                smell_type=SmellType.DEAD_COMMENTED_CODE,
                severity=sev,
                diagnosis=f"Detectadas {count} líneas consecutivas de código comentado (líneas {start_l}-{end_l}).",
                suggestion="Eliminar el código comentado obsoleto. El control de versiones (Git) conserva el historial completo."
            ))

        # Parsear AST
        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError:
            # Degradación elegante si el archivo tiene errores sintácticos
            return smells

        # Enlazar nodos padre para contextualización
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                child.parent = parent  # type: ignore

        # 3. Inspeccionar Funciones y Métodos
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._check_function(file_path, node, smells)
            elif isinstance(node, ast.ClassDef):
                self._check_class(file_path, node, smells)

        # 4. Inspeccionar Anidación Profunda (Deep Nesting)
        self._check_nesting(file_path, tree, smells)

        # 5. Inspeccionar Condiciones Complejas (Complex Conditions)
        self._check_complex_conditions(file_path, tree, smells)

        # 6. Inspeccionar Números Mágicos (Magic Numbers)
        self._check_magic_numbers(file_path, tree, smells)

        return smells

    def _check_function(self, file_path: Path, node: ast.FunctionDef | ast.AsyncFunctionDef, smells: List[CodeSmell]):
        # Long Method
        func_lines = (getattr(node, 'end_lineno', node.lineno) - node.lineno) + 1
        if func_lines > self.config.max_line_func:
            sev = Severity.CRITICA if func_lines >= self.config.max_line_func * 2 else Severity.ALTA
            smells.append(CodeSmell(
                file_path=file_path,
                line=node.lineno,
                smell_type=SmellType.LONG_METHOD,
                severity=sev,
                diagnosis=f"Función '{node.name}' tiene {func_lines} líneas (límite recomendado: {self.config.max_line_func}).",
                suggestion="Aplicar 'Extract Method' para descomponer la lógica en pasos pequeños con nombres intencionales.",
                symbol_name=node.name
            ))

        # Long Parameter List
        args = node.args
        all_params = [a.arg for a in (args.posonlyargs + args.args + args.kwonlyargs)]
        # Excluir self / cls en métodos
        if all_params and all_params[0] in ("self", "cls"):
            all_params = all_params[1:]

        param_count = len(all_params)
        if param_count > self.config.max_params:
            sev = Severity.ALTA if param_count >= self.config.max_params + 2 else Severity.MEDIA
            preview = ", ".join(all_params[:4]) + ("..." if param_count > 4 else "")
            smells.append(CodeSmell(
                file_path=file_path,
                line=node.lineno,
                smell_type=SmellType.LONG_PARAMETER_LIST,
                severity=sev,
                diagnosis=f"Función '{node.name}' recibe {param_count} parámetros ({preview}) (límite: {self.config.max_params}).",
                suggestion="Aplicar 'Introduce Parameter Object' o encapsular parámetros en una dataclass de contexto.",
                symbol_name=node.name
            ))

    def _check_class(self, file_path: Path, node: ast.ClassDef, smells: List[CodeSmell]):
        class_lines = (getattr(node, 'end_lineno', node.lineno) - node.lineno) + 1
        methods = [m for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))]
        method_count = len(methods)

        is_large = class_lines > self.config.max_line_class
        is_overburdened = method_count > self.config.max_methods_class

        if is_large or is_overburdened:
            sev = Severity.CRITICA if (class_lines > self.config.max_line_class * 2 or method_count > 20) else Severity.ALTA
            smells.append(CodeSmell(
                file_path=file_path,
                line=node.lineno,
                smell_type=SmellType.GOD_CLASS,
                severity=sev,
                diagnosis=f"Clase '{node.name}' tiene {class_lines} líneas y {method_count} métodos (posible God Class).",
                suggestion="Aplicar Single Responsibility Principle (SRP). Dividir responsabilidades extrayendo clases colaboradoras.",
                symbol_name=node.name
            ))

    def _check_nesting(self, file_path: Path, tree: ast.AST, smells: List[CodeSmell]):
        reported_lines: Set[int] = set()

        def walk_node(node: ast.AST, current_depth: int):
            for child in ast.iter_child_nodes(node):
                child_depth = current_depth
                is_control = isinstance(
                    child,
                    (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith, ast.Match)
                )

                # Tratamiento especial para 'elif': no incrementar profundidad ya que es plano
                is_elif = False
                if isinstance(child, ast.If) and hasattr(child, 'parent') and isinstance(child.parent, ast.If):
                    if child in child.parent.orelse and len(child.parent.orelse) == 1:
                        is_elif = True

                if is_control:
                    if not is_elif:
                        child_depth = current_depth + 1

                    if child_depth > self.config.max_nesting and child.lineno not in reported_lines:
                        reported_lines.add(child.lineno)
                        sev = Severity.CRITICA if child_depth >= self.config.max_nesting + 2 else Severity.ALTA
                        node_name = type(child).__name__.replace("Async", "")
                        smells.append(CodeSmell(
                            file_path=file_path,
                            line=child.lineno,
                            smell_type=SmellType.DEEP_NESTING,
                            severity=sev,
                            diagnosis=f"Estructura '{node_name}' alcanza profundidad de anidación de {child_depth} niveles (límite: {self.config.max_nesting}).",
                            suggestion="Aplicar 'Guard Clauses' (retornos tempranos) o extraer ramas internas a funciones independientes."
                        ))

                walk_node(child, child_depth)

        walk_node(tree, 0)

    def _check_complex_conditions(self, file_path: Path, tree: ast.AST, smells: List[CodeSmell]):
        def count_logical_operators(expr: ast.AST) -> int:
            if isinstance(expr, ast.BoolOp):
                ops = len(expr.values) - 1
                for v in expr.values:
                    ops += count_logical_operators(v)
                return ops
            elif isinstance(expr, ast.UnaryOp) and isinstance(expr.op, ast.Not):
                return 1 + count_logical_operators(expr.operand)
            return 0

        for node in ast.walk(tree):
            test = getattr(node, 'test', None)
            if test is not None:
                op_count = count_logical_operators(test)
                if op_count >= 3:
                    smells.append(CodeSmell(
                        file_path=file_path,
                        line=node.lineno,
                        smell_type=SmellType.COMPLEX_CONDITION,
                        severity=Severity.ALTA,
                        diagnosis=f"Condición booleana compleja con {op_count} operadores lógicos encadenados.",
                        suggestion="Extraer subcondiciones a variables explicativas ('Explaining Variables') o funciones predicado legibles."
                    ))

    def _check_magic_numbers(self, file_path: Path, tree: ast.AST, smells: List[CodeSmell]):
        allowed_values = {-1, 0, 1, 2, 0.0, 1.0, 0.5, 100}

        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                val = node.value
                if val in allowed_values:
                    continue

                # Evitar falsos positivos en asignaciones de constantes en mayúsculas, enums y valores por defecto
                curr = getattr(node, 'parent', None)
                is_named_constant = False
                is_default_param = False

                while curr:
                    if isinstance(curr, ast.Assign):
                        for target in curr.targets:
                            if isinstance(target, ast.Name) and target.id.isupper():
                                is_named_constant = True
                                break
                    elif isinstance(curr, ast.AnnAssign):
                        if isinstance(curr.target, ast.Name) and curr.target.id.isupper():
                            is_named_constant = True
                            break
                    elif isinstance(curr, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node in curr.args.defaults or node in curr.args.kw_defaults:
                            is_default_param = True
                        break
                    elif isinstance(curr, ast.ClassDef):
                        for base in curr.bases:
                            if isinstance(base, ast.Name) and "Enum" in base.id:
                                is_named_constant = True
                                break
                    curr = getattr(curr, 'parent', None)

                if not is_named_constant and not is_default_param:
                    smells.append(CodeSmell(
                        file_path=file_path,
                        line=node.lineno,
                        smell_type=SmellType.MAGIC_NUMBER,
                        severity=Severity.MEDIA,
                        diagnosis=f"Número mágico literal '{val}' sin nombrar en la lógica de ejecución.",
                        suggestion=f"Extraer '{val}' a una constante en MAYÚSCULAS descriptiva o Enum de dominio."
                    ))


# ------------------------------------------------------------------------------
# Analizador Heurístico Polyglot (JS, TS, Java, C#, Go, etc.)
# ------------------------------------------------------------------------------
class PolyglotHeuristicAnalyzer:
    def __init__(self, config: AnalysisConfig):
        self.config = config

    def analyze(self, file_path: Path, content: str) -> List[CodeSmell]:
        smells: List[CodeSmell] = []
        lines = content.splitlines()
        total_lines = len(lines)

        # 1. Large File
        if total_lines > self.config.max_line_file:
            sev = Severity.CRITICA if total_lines >= self.config.max_line_file * 2 else Severity.MEDIA
            smells.append(CodeSmell(
                file_path=file_path,
                line=1,
                smell_type=SmellType.LARGE_FILE,
                severity=sev,
                diagnosis=f"Archivo extenso de {total_lines} líneas (límite recomendado: {self.config.max_line_file}).",
                suggestion="Modularizar separando interfaces, lógica de dominio y adaptadores en submódulos."
            ))

        # 2. Dead / Commented-out Code
        commented_blocks = detect_commented_code_blocks(lines, min_consecutive=3)
        for start_l, end_l, count in commented_blocks:
            sev = Severity.ALTA if count >= 6 else Severity.MEDIA
            smells.append(CodeSmell(
                file_path=file_path,
                line=start_l,
                smell_type=SmellType.DEAD_COMMENTED_CODE,
                severity=sev,
                diagnosis=f"Detectadas {count} líneas consecutivas de código comentado (líneas {start_l}-{end_l}).",
                suggestion="Eliminar el código comentado obsoleto. El control de versiones (Git) conserva el historial."
            ))

        # Regex para firmas de funciones polyglot
        fn_pattern = re.compile(
            r'(?:(?:async\s+)?function\s+([a-zA-Z_]\w*)\s*\(([^)]*)\)|'
            r'([a-zA-Z_]\w*)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>|'
            r'(?:public|private|protected|static|\s)*\s*[\w<>\[\]]+\s+([a-zA-Z_]\w*)\s*\(([^)]*)\)\s*\{|'
            r'func\s+(?:\([^)]+\)\s*)?([a-zA-Z_]\w*)\s*\(([^)]*)\)|'
            r'([a-zA-Z_]\w*)\s*\(([^)]*)\)\s*\{)'
        )

        ctrl_pattern = re.compile(r'\b(if|for|while|switch|catch)\s*\(')
        complex_cond_pattern = re.compile(r'\b(?:if|while)\s*\((.*?)\)')
        magic_number_pattern = re.compile(r'(?<![a-zA-Z0-9_\$])(\d+(?:\.\d+)?)(?![a-zA-Z0-9_\$])')

        brace_depth = 0
        fn_start_line = None
        fn_name = ""
        fn_base_depth = 0

        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
                continue

            # Complex Condition
            m_cond = complex_cond_pattern.search(stripped)
            if m_cond:
                cond_str = m_cond.group(1)
                op_count = len(re.findall(r'&&|\|\|', cond_str))
                if op_count >= 3:
                    smells.append(CodeSmell(
                        file_path=file_path,
                        line=idx,
                        smell_type=SmellType.COMPLEX_CONDITION,
                        severity=Severity.ALTA,
                        diagnosis=f"Condición booleana compleja con {op_count} operadores lógicos encadenados.",
                        suggestion="Extraer subcondiciones a variables explicativas booleanas intermedias."
                    ))

            # Function Start & Long Parameter List
            m_fn = fn_pattern.search(stripped)
            if m_fn and fn_start_line is None:
                # Extraer nombre y parámetros de los grupos emparejados
                name = m_fn.group(1) or m_fn.group(3) or m_fn.group(5) or m_fn.group(7) or m_fn.group(9) or "function"
                params_str = m_fn.group(2) or m_fn.group(4) or m_fn.group(6) or m_fn.group(8) or m_fn.group(10) or ""
                params = [p.strip() for p in params_str.split(',') if p.strip()]

                if len(params) > self.config.max_params:
                    sev = Severity.ALTA if len(params) >= self.config.max_params + 2 else Severity.MEDIA
                    smells.append(CodeSmell(
                        file_path=file_path,
                        line=idx,
                        smell_type=SmellType.LONG_PARAMETER_LIST,
                        severity=sev,
                        diagnosis=f"Función '{name}' recibe {len(params)} parámetros (límite: {self.config.max_params}).",
                        suggestion="Agrupar parámetros en un objeto de configuración o DTO.",
                        symbol_name=name
                    ))

                fn_start_line = idx
                fn_name = name
                fn_base_depth = brace_depth

            # Deep Nesting
            if ctrl_pattern.search(stripped):
                current_nesting = (brace_depth - fn_base_depth) if fn_start_line else brace_depth
                if current_nesting > self.config.max_nesting:
                    sev = Severity.CRITICA if current_nesting >= self.config.max_nesting + 2 else Severity.ALTA
                    smells.append(CodeSmell(
                        file_path=file_path,
                        line=idx,
                        smell_type=SmellType.DEEP_NESTING,
                        severity=sev,
                        diagnosis=f"Estructura de control alcanza nivel de anidación {current_nesting} (límite: {self.config.max_nesting}).",
                        suggestion="Aplicar 'Guard Clauses' (retornos tempranos) o descomponer ramas anidadas."
                    ))

            # Magic Numbers (Heurística en líneas de lógica)
            if not stripped.startswith(('const ', 'final ', '#define', 'static const')):
                for m_num in magic_number_pattern.finditer(stripped):
                    raw_val = m_num.group(1)
                    val = float(raw_val) if '.' in raw_val else int(raw_val)
                    if val not in {-1, 0, 1, 2, 0.0, 1.0, 0.5, 100}:
                        # Comprobar que no esté dentro de una asignación constante en MAYÚSCULAS
                        if not re.search(r'\b[A-Z0-9_]{3,}\s*=\s*' + re.escape(raw_val), stripped):
                            smells.append(CodeSmell(
                                file_path=file_path,
                                line=idx,
                                smell_type=SmellType.MAGIC_NUMBER,
                                severity=Severity.MEDIA,
                                diagnosis=f"Número mágico literal '{val}' en lógica ejecutable.",
                                suggestion=f"Extraer '{val}' a una constante con nombre descriptivo en MAYÚSCULAS."
                            ))
                            break  # Un aviso por línea es suficiente

            # Rastrear profundidad de llaves
            open_braces = line.count('{')
            close_braces = line.count('}')
            brace_depth += (open_braces - close_braces)

            # Fin de función
            if fn_start_line is not None and brace_depth <= fn_base_depth and close_braces > 0:
                fn_length = idx - fn_start_line + 1
                if fn_length > self.config.max_line_func:
                    sev = Severity.CRITICA if fn_length >= self.config.max_line_func * 2 else Severity.ALTA
                    smells.append(CodeSmell(
                        file_path=file_path,
                        line=fn_start_line,
                        smell_type=SmellType.LONG_METHOD,
                        severity=sev,
                        diagnosis=f"Función '{fn_name}' tiene {fn_length} líneas (límite: {self.config.max_line_func}).",
                        suggestion="Aplicar 'Extract Method' para descomponer la función en unidades atómicas.",
                        symbol_name=fn_name
                    ))
                fn_start_line = None

        return smells


# ------------------------------------------------------------------------------
# Motor Central de Análisis
# ------------------------------------------------------------------------------
class SmellAnalyzerEngine:
    def __init__(self, config: AnalysisConfig):
        self.config = config
        self.python_analyzer = PythonASTAnalyzer(config)
        self.polyglot_analyzer = PolyglotHeuristicAnalyzer(config)

    def run(self) -> ProjectReport:
        start_time = time.time()
        file_results: List[FileAnalysisResult] = []
        total_loc = 0
        total_files = 0

        target_files = list(discover_files(self.config.path, self.config.lang))

        for file_path in target_files:
            total_files += 1
            content = ""
            try:
                # Intento de lectura tolerante a encodings
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                try:
                    content = file_path.read_text(encoding="latin-1", errors="replace")
                except Exception:
                    continue

            lines_count = len(content.splitlines())
            total_loc += lines_count

            # Seleccionar analizador
            if file_path.suffix.lower() == ".py":
                raw_smells = self.python_analyzer.analyze(file_path, content)
            else:
                raw_smells = self.polyglot_analyzer.analyze(file_path, content)

            # Filtrar por severidad si se solicitó
            if self.config.min_severity is not None:
                min_weight = self.config.min_severity.weight
                filtered_smells = [s for s in raw_smells if s.severity.weight >= min_weight]
            else:
                filtered_smells = raw_smells

            # Ordenar smells por línea
            filtered_smells.sort(key=lambda s: s.line)

            file_results.append(FileAnalysisResult(
                path=file_path,
                lines_count=lines_count,
                smells=filtered_smells
            ))

        duration = time.time() - start_time
        return ProjectReport(
            total_files_scanned=total_files,
            total_loc=total_loc,
            duration_seconds=duration,
            file_results=file_results
        )


# ------------------------------------------------------------------------------
# Renderizado Visual en Terminal (Rich + Fallback ANSI Estándar)
# ------------------------------------------------------------------------------
class ConsoleRenderer:
    def __init__(self, no_color: bool = False):
        self.use_rich = HAS_RICH and not no_color
        self.no_color = no_color
        if self.use_rich:
            self.console = Console()

    def render(self, report: ProjectReport, config: AnalysisConfig):
        if self.use_rich:
            self._render_rich(report, config)
        else:
            self._render_plain(report, config)

    def _render_rich(self, report: ProjectReport, config: AnalysisConfig):
        # 1. Cabecera Principal
        title_text = Text()
        title_text.append("CLEAN CODE SMELL ANALYZER\n", style="bold cyan")
        title_text.append(f"Directorio: {config.path.resolve()} | Lenguaje: {config.lang.upper()} | Python 3.10+", style="dim")
        self.console.print(Panel(title_text, box=box.ROUNDED, border_style="cyan"))

        # 2. Desglose detallado por archivo con hallazgos
        files_with_smells = [f for f in report.file_results if f.smells]

        if not files_with_smells:
            self.console.print("\n[bold green]✓ No se detectaron code smells. El código cumple con los umbrales configurados.[/bold green]\n")
        else:
            self.console.print(f"\n[bold underline]Hallazgos Detallados ({len(files_with_smells)} archivos con deuda técnica):[/bold underline]\n")

            for file_res in files_with_smells:
                # Tabla por archivo
                table = Table(
                    title=f"📂 {file_res.path} ({len(file_res.smells)} smells | {file_res.lines_count} LOC)",
                    title_style="bold white on blue",
                    box=box.SIMPLE_HEAVY,
                    show_header=True,
                    header_style="bold magenta",
                    expand=True
                )
                table.add_column("Línea", justify="right", style="cyan", width=8)
                table.add_column("Severidad", justify="center", width=12)
                table.add_column("Code Smell", style="bold yellow", width=22)
                table.add_column("Diagnóstico y Refactorización Sugerida", style="white")

                for smell in file_res.smells:
                    sev_text = Text(f"[{smell.severity.value}]", style=smell.severity.rich_style)
                    detail = Text()
                    detail.append(f"{smell.diagnosis}\n", style="white")
                    detail.append("💡 Refactor: ", style="bold green")
                    detail.append(smell.suggestion, style="italic green")
                    table.add_row(str(smell.line), sev_text, smell.smell_type.value, detail)

                self.console.print(table)
                self.console.print()

        # 3. Resumen Ejecutivo y Estadísticas
        score, grade, description = report.health_score

        # Determinar color del score
        grade_color = "bold green" if score >= 85 else ("bold yellow" if score >= 70 else "bold red")

        score_text = Text()
        score_text.append("HEALTH SCORE GLOBAL: ", style="bold")
        score_text.append(f"{grade} ({score}/100)\n", style=grade_color)
        score_text.append(f"Evaluación: {description}\n", style="italic")
        score_text.append(f"Archivos analizados: {report.total_files_scanned} | LOC totales: {report.total_loc} | Tiempo: {report.duration_seconds:.2f}s", style="dim")

        self.console.print(Panel(score_text, title="[bold]Resumen de Salud del Proyecto[/bold]", border_style="green" if score >= 70 else "red", box=box.ROUNDED))

        # Tabla de Smells por Tipo y Severidad
        summary_table = Table(title="📊 Recuento de Code Smells por Tipo", box=box.ROUNDED, expand=False)
        summary_table.add_column("Tipo de Code Smell", style="bold")
        summary_table.add_column("CRÍTICA", justify="center", style="bold red")
        summary_table.add_column("ALTA", justify="center", style="bold yellow")
        summary_table.add_column("MEDIA", justify="center", style="cyan")
        summary_table.add_column("Total", justify="right", style="bold white")

        all_smells = report.all_smells
        for st in SmellType:
            c_crit = sum(1 for s in all_smells if s.smell_type == st and s.severity == Severity.CRITICA)
            c_alt = sum(1 for s in all_smells if s.smell_type == st and s.severity == Severity.ALTA)
            c_med = sum(1 for s in all_smells if s.smell_type == st and s.severity == Severity.MEDIA)
            tot = c_crit + c_alt + c_med
            if tot > 0:
                summary_table.add_row(st.value, str(c_crit), str(c_alt), str(c_med), str(tot))

        self.console.print(summary_table)

        # 4. Top 3 Archivos Prioritarios a Refactorizar
        top_files = report.top_priority_files
        if top_files:
            prio_table = Table(title="🎯 Top 3 Archivos de Mayor Prioridad a Refactorizar", box=box.ROUNDED, expand=False)
            prio_table.add_column("Rank", justify="center", style="bold cyan")
            prio_table.add_column("Ruta del Archivo", style="bold white")
            prio_table.add_column("Smells", justify="center", style="yellow")
            prio_table.add_column("Penalización", justify="center", style="bold red")
            prio_table.add_column("Principal Recomendación", style="italic")

            for rank, f_res in enumerate(top_files, start=1):
                top_smell_obj = max(f_res.smells, key=lambda s: s.severity.weight) if f_res.smells else None
                top_smell_name = top_smell_obj.smell_type.value if top_smell_obj else "General"
                prio_table.add_row(
                    f"#{rank}",
                    str(f_res.path),
                    str(len(f_res.smells)),
                    str(f_res.penalty_score),
                    f"Priorizar refactorización de {top_smell_name}"
                )
            self.console.print(prio_table)
            self.console.print()

    def _render_plain(self, report: ProjectReport, config: AnalysisConfig):
        # Fallback estándar ANSI o plano
        c_reset = "" if self.no_color else "\033[0m"
        c_bold = "" if self.no_color else "\033[1m"
        c_cyan = "" if self.no_color else "\033[96m"
        c_green = "" if self.no_color else "\033[92m"

        print(f"\n{c_bold}{c_cyan}======================================================================{c_reset}")
        print(f"{c_bold} CLEAN CODE SMELL ANALYZER — REPORTE DE DEUDA TÉCNICA{c_reset}")
        print(f" Directorio: {config.path.resolve()} | Lenguaje: {config.lang.upper()}")
        print(f"{c_bold}{c_cyan}======================================================================{c_reset}\n")

        files_with_smells = [f for f in report.file_results if f.smells]
        if not files_with_smells:
            print(f"{c_green}✓ No se detectaron code smells en los archivos escaneados.{c_reset}\n")
        else:
            for file_res in files_with_smells:
                print(f"{c_bold}📂 Archivo: {file_res.path} ({len(file_res.smells)} smells, {file_res.lines_count} LOC){c_reset}")
                print("-" * 75)
                for s in file_res.smells:
                    sev_col = "" if self.no_color else s.severity.color_ansi
                    print(f"  [L{s.line:>4}] {sev_col}[{s.severity.value:<7}]{c_reset} {c_bold}{s.smell_type.value}{c_reset}")
                    print(f"         Diagnóstico: {s.diagnosis}")
                    print(f"         {c_green}💡 Refactor:  {s.suggestion}{c_reset}")
                print()

        # Resumen Global
        score, grade, desc = report.health_score
        print(f"{c_bold}{c_cyan}----------------------------------------------------------------------{c_reset}")
        print(f"{c_bold}HEALTH SCORE GLOBAL: {grade} ({score}/100){c_reset}")
        print(f"Diagnóstico: {desc}")
        print(f"Archivos analizados: {report.total_files_scanned} | LOC: {report.total_loc} | Tiempo: {report.duration_seconds:.2f}s")
        print(f"{c_bold}{c_cyan}----------------------------------------------------------------------{c_reset}\n")

        # Top 3 Archivos
        top_files = report.top_priority_files
        if top_files:
            print(f"{c_bold}Top 3 Archivos de Mayor Prioridad a Refactorizar:{c_reset}")
            for rank, f in enumerate(top_files, start=1):
                top_smell_obj = max(f.smells, key=lambda s: s.severity.weight) if f.smells else None
                top_smell_name = f" (Foco: {top_smell_obj.smell_type.value})" if top_smell_obj else ""
                print(f"  {rank}. {f.path} — {len(f.smells)} smells, Penalización: {f.penalty_score} pts{top_smell_name}")
            print()


# ------------------------------------------------------------------------------
# Exportador a Markdown
# ------------------------------------------------------------------------------
class MarkdownExporter:
    @staticmethod
    def export(report: ProjectReport, config: AnalysisConfig, output_path: Path):
        score, grade, description = report.health_score

        md: List[str] = []
        md.append("# Reporte de Análisis de Code Smells y Deuda Técnica\n")
        md.append(f"> Generado automáticamente por **Clean Code Smell Analyzer**  ")
        md.append(f"> Fecha de análisis: `{time.strftime('%Y-%m-%d %H:%M:%S')}`  ")
        md.append(f"> Objetivo: `{config.path.resolve()}` | Lenguaje: `{config.lang.upper()}`\n")

        md.append("## 1. Resumen Ejecutivo de Salud\n")
        md.append("| Métrica | Valor |")
        md.append("| :--- | :--- |")
        md.append(f"| **Health Score Global** | **`{grade}` ({score}/100)** |")
        md.append(f"| **Diagnóstico de Salud** | {description} |")
        md.append(f"| **Archivos Escaneados** | {report.total_files_scanned} |")
        md.append(f"| **Líneas de Código (LOC)** | {report.total_loc:,} |")
        md.append(f"| **Total de Smells Detectados** | {len(report.all_smells)} |")
        md.append(f"| **Tiempo de Ejecución** | {report.duration_seconds:.2f} s |\n")

        # Top 3
        top_files = report.top_priority_files
        if top_files:
            md.append("## 2. Top 3 Archivos Prioritarios a Refactorizar\n")
            md.append("| Prioridad | Archivo | Smells Detectados | Penalización | Foco Principal |")
            md.append("| :---: | :--- | :---: | :---: | :--- |")
            for idx, f in enumerate(top_files, start=1):
                top_smell_obj = max(f.smells, key=lambda s: s.severity.weight) if f.smells else None
                top_smell_name = top_smell_obj.smell_type.value if top_smell_obj else "General"
                md.append(f"| **#{idx}** | `{f.path}` | {len(f.smells)} | {f.penalty_score} pts | {top_smell_name} |")
            md.append("")

        # Tabla de distribución de Smells
        md.append("## 3. Distribución de Code Smells por Tipo y Severidad\n")
        md.append("| Tipo de Code Smell | CRÍTICA | ALTA | MEDIA | Total |")
        md.append("| :--- | :---: | :---: | :---: | :---: |")
        all_smells = report.all_smells
        for st in SmellType:
            c_crit = sum(1 for s in all_smells if s.smell_type == st and s.severity == Severity.CRITICA)
            c_alt = sum(1 for s in all_smells if s.smell_type == st and s.severity == Severity.ALTA)
            c_med = sum(1 for s in all_smells if s.smell_type == st and s.severity == Severity.MEDIA)
            tot = c_crit + c_alt + c_med
            if tot > 0:
                md.append(f"| **{st.value}** | {c_crit} | {c_alt} | {c_med} | **{tot}** |")
        md.append("")

        # Hallazgos Detallados
        files_with_smells = [f for f in report.file_results if f.smells]
        md.append("## 4. Hallazgos Detallados por Archivo\n")
        if not files_with_smells:
            md.append("✓ *No se detectaron code smells. El código cumple con las heurísticas de Clean Code.*\n")
        else:
            for f in files_with_smells:
                md.append(f"### 📂 `{f.path}`\n")
                md.append(f"- **Métricas del archivo:** {f.lines_count} líneas de código, {len(f.smells)} smells detectados.\n")
                md.append("| Línea | Severidad | Code Smell | Diagnóstico | Sugerencia de Refactorización |")
                md.append("| :---: | :---: | :--- | :--- | :--- |")
                for s in f.smells:
                    badge = f"**{s.severity.value}**"
                    md.append(f"| `{s.line}` | {badge} | {s.smell_type.value} | {s.diagnosis} | *{s.suggestion}* |")
                md.append("")

        output_path.write_text("\n".join(md), encoding="utf-8")


# ------------------------------------------------------------------------------
# Interfaz de Línea de Comandos (CLI)
# ------------------------------------------------------------------------------
def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="smell_analyzer.py",
        description="Analizador estático de arquitectura y Code Smells para Clean Code y Refactorización.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--path",
        type=str,
        default=".",
        help="Ruta de la carpeta o archivo a analizar."
    )
    parser.add_argument(
        "--lang",
        type=str,
        default="all",
        help="Lenguaje a inspeccionar (o 'all' para autodetección: py, js, ts, java, c, cpp, cs, go, etc.)."
    )
    parser.add_argument(
        "--max-line-func",
        type=int,
        default=35,
        help="Límite máximo recomendado de líneas por función o método."
    )
    parser.add_argument(
        "--max-line-file",
        type=int,
        default=300,
        help="Límite máximo recomendado de líneas por archivo."
    )
    parser.add_argument(
        "--max-params",
        type=int,
        default=4,
        help="Límite máximo de parámetros admitidos por función."
    )
    parser.add_argument(
        "--max-nesting",
        type=int,
        default=3,
        help="Profundidad máxima recomendada de anidación de bloques de control."
    )
    parser.add_argument(
        "--export",
        type=str,
        default=None,
        metavar="FILE.md",
        help="Ruta opcional para exportar el informe de auditoría a formato Markdown."
    )
    parser.add_argument(
        "--severity",
        type=str,
        choices=["MEDIA", "ALTA", "CRITICA", "CRÍTICA"],
        default=None,
        help="Filtrar reporte para mostrar únicamente smells iguales o superiores a esta severidad."
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Desactivar secuencias de escape de color ANSI."
    )

    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    target_path = Path(args.path)
    if not target_path.exists():
        sys.stderr.write(f"Error: La ruta especificada no existe: {args.path}\n")
        return 1

    # Normalizar severidad
    min_sev: Optional[Severity] = None
    if args.severity:
        sev_str = args.severity.upper().replace("Í", "I")
        if sev_str == "CRITICA":
            min_sev = Severity.CRITICA
        elif sev_str == "ALTA":
            min_sev = Severity.ALTA
        elif sev_str == "MEDIA":
            min_sev = Severity.MEDIA

    export_p = Path(args.export) if args.export else None

    config = AnalysisConfig(
        path=target_path,
        lang=args.lang,
        max_line_func=args.max_line_func,
        max_line_file=args.max_line_file,
        max_params=args.max_params,
        max_nesting=args.max_nesting,
        export_path=export_p,
        min_severity=min_sev,
        no_color=args.no_color
    )

    engine = SmellAnalyzerEngine(config)
    report = engine.run()

    # Renderizar en terminal
    renderer = ConsoleRenderer(no_color=config.no_color)
    renderer.render(report, config)

    # Exportar informe si fue solicitado
    if config.export_path:
        MarkdownExporter.export(report, config, config.export_path)
        if HAS_RICH and not config.no_color:
            Console().print(f"[bold green]✓ Informe Markdown exportado exitosamente en:[/bold green] [underline]{config.export_path.resolve()}[/underline]\n")
        else:
            print(f"✓ Informe Markdown exportado exitosamente en: {config.export_path.resolve()}\n")

    # Retornar código de salida: 1 si hay smells críticos, 0 si todo está en orden
    has_crit = any(s.severity == Severity.CRITICA for s in report.all_smells)
    return 1 if has_crit else 0


if __name__ == "__main__":
    sys.exit(main())
