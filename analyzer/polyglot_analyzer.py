"""
Analizador léxico y heurístico para lenguajes tipo C/Algol (JS, TS, Java, C#, C++, Go, PHP).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import List, Optional, Tuple

from analyzer.constants import (
    ALLOWED_NUMERIC_LITERALS,
    CRITICAL_MULTIPLIER,
    CRITICAL_NESTING_OFFSET,
    HIGH_PARAM_OFFSET,
    MIN_COMPLEX_BOOL_OPS,
)
from analyzer.models import AnalysisConfig, CodeSmell, Severity, SmellType
from analyzer.python_analyzer import check_file_level_smells

FN_SIGNATURE_REGEX = re.compile(
    r"(?:(?:async\s+)?function\s+([a-zA-Z_]\w*)\s*\(([^)]*)\)|"
    r"([a-zA-Z_]\w*)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>|"
    r"(?:public|private|protected|static|\s)*\s*[\w<>\[\]]+\s+([a-zA-Z_]\w*)\s*\(([^)]*)\)\s*\{|"
    r"func\s+(?:\([^)]+\)\s*)?([a-zA-Z_]\w*)\s*\(([^)]*)\)|"
    r"([a-zA-Z_]\w*)\s*\(([^)]*)\)\s*\{)"
)

CLASS_SIGNATURE_REGEX = re.compile(r"\bclass\s+([a-zA-Z_]\w*)")
CONTROL_KEYWORD_REGEX = re.compile(r"\b(if|for|while|switch|catch)\s*\(")
CONDITION_EXPR_REGEX = re.compile(r"\b(?:if|while)\s*\((.*?)\)")
LOGICAL_OP_REGEX = re.compile(r"&&|\|\|")
NUMERIC_LITERAL_REGEX = re.compile(r"(?<![a-zA-Z0-9_\$])(\d+(?:\.\d+)?)(?![a-zA-Z0-9_\$])")
STRING_AND_COMMENT_REGEX = re.compile(r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`|//.*$)')
CONST_DECL_PREFIXES: Tuple[str, ...] = ("const ", "final ", "#define", "static const", "readonly ")
CONTROL_NAMES = frozenset({"if", "for", "while", "switch", "catch", "return", "sizeof"})
GROUP_PAIR_STEP: int = 2


def sanitize_code_line(raw_line: str) -> str:
    """Elimina literales de texto y comentarios en línea para evitar falsos conteos de llaves."""
    stripped = raw_line.strip()
    if not stripped or stripped.startswith(("//", "/*", "*")):
        return ""
    return STRING_AND_COMMENT_REGEX.sub("", stripped).strip()


def _extract_fn_signature(clean_line: str) -> Optional[Tuple[str, List[str]]]:
    """Extrae el nombre y la lista de parámetros si la línea declara una función o método."""
    match = FN_SIGNATURE_REGEX.search(clean_line)
    if not match:
        return None
    groups = match.groups()
    for idx in range(0, len(groups), GROUP_PAIR_STEP):
        name = groups[idx]
        if name and name not in CONTROL_NAMES:
            raw_params = groups[idx + 1] or ""
            params = [p.strip() for p in raw_params.split(",") if p.strip()]
            return name, params
    return None


@dataclass
class LexicalContext:
    """Objeto de contexto (Parameter Object) para el escaneo léxico de un archivo."""

    file_path: Path
    smells: List[CodeSmell] = field(default_factory=list)
    line_num: int = 0
    clean_line: str = ""
    brace_depth: int = 0
    fn_start_line: Optional[int] = None
    fn_name: str = ""
    fn_base_depth: int = 0
    class_start_line: Optional[int] = None
    class_name: str = ""
    class_base_depth: int = 0
    class_methods: int = 0


class PolyglotHeuristicAnalyzer:
    """Analizador heurístico basado en expresiones regulares y balanceo de llaves."""

    def __init__(self, config: AnalysisConfig) -> None:
        self.config = config

    def analyze(self, file_path: Path, content: str) -> List[CodeSmell]:
        lines = content.splitlines()
        initial_smells = check_file_level_smells(file_path, lines, self.config.max_line_file)
        ctx = LexicalContext(file_path=file_path, smells=initial_smells)

        for line_num, raw_line in enumerate(lines, start=1):
            clean_line = sanitize_code_line(raw_line)
            if not clean_line:
                continue
            ctx.line_num = line_num
            ctx.clean_line = clean_line
            self._inspect_line(ctx)

        return ctx.smells

    def _inspect_line(self, ctx: LexicalContext) -> None:
        self._check_line_expressions(ctx)
        self._check_scope_entries(ctx)
        self._check_control_nesting(ctx)
        self._update_braces_and_closures(ctx)

    def _check_line_expressions(self, ctx: LexicalContext) -> None:
        cond_match = CONDITION_EXPR_REGEX.search(ctx.clean_line)
        if cond_match:
            op_count = len(LOGICAL_OP_REGEX.findall(cond_match.group(1)))
            if op_count >= MIN_COMPLEX_BOOL_OPS:
                ctx.smells.append(CodeSmell(
                    file_path=ctx.file_path,
                    line=ctx.line_num,
                    smell_type=SmellType.COMPLEX_CONDITION,
                    severity=Severity.ALTA,
                    diagnosis=f"Condición booleana compleja con {op_count} operadores lógicos encadenados.",
                    suggestion="Extraer subcondiciones a variables explicativas booleanas intermedias.",
                ))

        magic_smell = self._detect_magic_number(ctx)
        if magic_smell:
            ctx.smells.append(magic_smell)

    def _detect_magic_number(self, ctx: LexicalContext) -> Optional[CodeSmell]:
        if ctx.clean_line.startswith(CONST_DECL_PREFIXES):
            return None
        for match in NUMERIC_LITERAL_REGEX.finditer(ctx.clean_line):
            raw_val = match.group(1)
            val = float(raw_val) if "." in raw_val else int(raw_val)
            if val in ALLOWED_NUMERIC_LITERALS:
                continue
            if not re.search(r"\b[A-Z0-9_]{3,}\s*=\s*" + re.escape(raw_val), ctx.clean_line):
                return CodeSmell(
                    file_path=ctx.file_path,
                    line=ctx.line_num,
                    smell_type=SmellType.MAGIC_NUMBER,
                    severity=Severity.MEDIA,
                    diagnosis=f"Número mágico literal '{val}' en lógica ejecutable.",
                    suggestion=f"Extraer '{val}' a una constante con nombre descriptivo en MAYÚSCULAS.",
                )
        return None

    def _check_scope_entries(self, ctx: LexicalContext) -> None:
        class_match = CLASS_SIGNATURE_REGEX.search(ctx.clean_line)
        if class_match and ctx.class_start_line is None:
            ctx.class_start_line = ctx.line_num
            ctx.class_name = class_match.group(1)
            ctx.class_base_depth = ctx.brace_depth
            ctx.class_methods = 0

        sig = _extract_fn_signature(ctx.clean_line)
        if sig and ctx.fn_start_line is None:
            name, params = sig
            ctx.fn_start_line = ctx.line_num
            ctx.fn_name = name
            ctx.fn_base_depth = ctx.brace_depth
            if ctx.class_start_line is not None:
                ctx.class_methods += 1
            param_smell = self._build_param_smell(ctx.file_path, ctx.line_num, name, len(params))
            if param_smell:
                ctx.smells.append(param_smell)

    def _build_param_smell(
        self, file_path: Path, line_num: int, fn_name: str, param_count: int
    ) -> Optional[CodeSmell]:
        limit = self.config.max_params
        if param_count <= limit:
            return None
        sev = Severity.ALTA if param_count >= limit + HIGH_PARAM_OFFSET else Severity.MEDIA
        return CodeSmell(
            file_path=file_path,
            line=line_num,
            smell_type=SmellType.LONG_PARAMETER_LIST,
            severity=sev,
            diagnosis=f"Función '{fn_name}' recibe {param_count} parámetros (límite: {limit}).",
            suggestion="Agrupar parámetros en un objeto de configuración o DTO.",
            symbol_name=fn_name,
        )

    def _check_control_nesting(self, ctx: LexicalContext) -> None:
        if not CONTROL_KEYWORD_REGEX.search(ctx.clean_line):
            return
        base = ctx.fn_base_depth if ctx.fn_start_line is not None else 0
        nesting = ctx.brace_depth - base
        limit = self.config.max_nesting
        if nesting > limit:
            sev = Severity.CRITICA if nesting >= limit + CRITICAL_NESTING_OFFSET else Severity.ALTA
            ctx.smells.append(CodeSmell(
                file_path=ctx.file_path,
                line=ctx.line_num,
                smell_type=SmellType.DEEP_NESTING,
                severity=sev,
                diagnosis=f"Estructura de control alcanza nivel de anidación {nesting} (límite: {limit}).",
                suggestion="Aplicar 'Guard Clauses' (retornos tempranos) o descomponer ramas anidadas.",
            ))

    def _update_braces_and_closures(self, ctx: LexicalContext) -> None:
        close_braces = ctx.clean_line.count("}")
        ctx.brace_depth += ctx.clean_line.count("{") - close_braces
        if close_braces == 0:
            return

        if ctx.fn_start_line is not None and ctx.brace_depth <= ctx.fn_base_depth:
            self._close_function_scope(ctx)

        if ctx.class_start_line is not None and ctx.brace_depth <= ctx.class_base_depth:
            self._close_class_scope(ctx)

    def _close_function_scope(self, ctx: LexicalContext) -> None:
        start_line = ctx.fn_start_line or ctx.line_num
        fn_length = (ctx.line_num - start_line) + 1
        limit = self.config.max_line_func
        if fn_length > limit:
            sev = Severity.CRITICA if fn_length >= limit * CRITICAL_MULTIPLIER else Severity.ALTA
            ctx.smells.append(CodeSmell(
                file_path=ctx.file_path,
                line=start_line,
                smell_type=SmellType.LONG_METHOD,
                severity=sev,
                diagnosis=f"Función '{ctx.fn_name}' tiene {fn_length} líneas (límite: {limit}).",
                suggestion="Aplicar 'Extract Method' para descomponer la función en unidades atómicas.",
                symbol_name=ctx.fn_name,
            ))
        ctx.fn_start_line = None

    def _close_class_scope(self, ctx: LexicalContext) -> None:
        start_line = ctx.class_start_line or ctx.line_num
        class_lines = (ctx.line_num - start_line) + 1
        if class_lines > self.config.max_line_class or ctx.class_methods > self.config.max_methods_class:
            ctx.smells.append(CodeSmell(
                file_path=ctx.file_path,
                line=start_line,
                smell_type=SmellType.GOD_CLASS,
                severity=Severity.ALTA,
                diagnosis=f"Clase '{ctx.class_name}' tiene {class_lines} líneas y {ctx.class_methods} métodos.",
                suggestion="Aplicar Single Responsibility Principle (SRP) dividiendo la clase.",
                symbol_name=ctx.class_name,
            ))
        ctx.class_start_line = None
