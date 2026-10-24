"""
Analizador estático basado en el Árbol de Sintaxis Abstracta (AST) para Python.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Optional, Set, Tuple, Type

from analyzer.comment_detector import detect_commented_code_blocks
from analyzer.constants import (
    ALLOWED_NUMERIC_LITERALS,
    CRITICAL_METHOD_LIMIT,
    CRITICAL_MULTIPLIER,
    CRITICAL_NESTING_OFFSET,
    HIGH_COMMENTED_CODE_LINES,
    HIGH_PARAM_OFFSET,
    MIN_COMMENTED_CODE_LINES,
    MIN_COMPLEX_BOOL_OPS,
    PARAM_PREVIEW_LIMIT,
)
from analyzer.models import AnalysisConfig, CodeSmell, Severity, SmellType

CONTROL_FLOW_NODES: Tuple[Type[ast.AST], ...] = (
    ast.If, ast.For, ast.AsyncFor, ast.While,
    ast.Try, ast.With, ast.AsyncWith, ast.Match,
)
COMPLEXITY_DECISION_NODES: Tuple[Type[ast.AST], ...] = (
    ast.If, ast.IfExp, ast.For, ast.AsyncFor, ast.While,
    ast.ExceptHandler, ast.With, ast.AsyncWith, ast.Assert, ast.comprehension,
)
MUTABLE_AST_NODES: Tuple[Type[ast.AST], ...] = (ast.List, ast.Dict, ast.Set)


def _attach_parent_references(tree: ast.AST) -> None:
    """Enlaza cada nodo del AST con su nodo padre para inspección contextual."""
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            setattr(child, "parent", parent)


def _calculate_docstring_lines(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> int:
    """Calcula cuántas líneas ocupa el docstring inicial de una función o clase."""
    if not node.body:
        return 0
    first_stmt = node.body[0]
    if not isinstance(first_stmt, ast.Expr):
        return 0
    val = first_stmt.value
    if isinstance(val, ast.Constant) and isinstance(val.value, str):
        return (getattr(first_stmt, "end_lineno", first_stmt.lineno) - first_stmt.lineno) + 1
    return 0


def _compute_cyclomatic_complexity(func_node: ast.AST) -> int:
    """Calcula la Complejidad Ciclomática de McCabe para un nodo de función."""
    complexity = 1
    for child in ast.walk(func_node):
        if isinstance(child, COMPLEXITY_DECISION_NODES):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            complexity += len(child.values) - 1
    return complexity


def _count_logical_operators(expr: ast.AST) -> int:
    """Cuenta recursivamente los operadores booleanos (and, or, not) en una condición."""
    if isinstance(expr, ast.BoolOp):
        return (len(expr.values) - 1) + sum(_count_logical_operators(v) for v in expr.values)
    if isinstance(expr, ast.UnaryOp) and isinstance(expr.op, ast.Not):
        return 1 + _count_logical_operators(expr.operand)
    return 0


def _is_elif_node(node: ast.AST) -> bool:
    """Determina si un nodo ast.If representa una cláusula 'elif' plana."""
    parent = getattr(node, "parent", None) if isinstance(node, ast.If) else None
    if not isinstance(parent, ast.If):
        return False
    return node in parent.orelse and len(parent.orelse) == 1


def _is_uppercase_assignment(node: ast.AST) -> bool:
    """Verifica si un nodo de asignación define una constante en MAYÚSCULAS."""
    if isinstance(node, ast.Assign):
        return any(isinstance(t, ast.Name) and t.id.isupper() for t in node.targets)
    if isinstance(node, ast.AnnAssign):
        return isinstance(node.target, ast.Name) and node.target.id.isupper()
    return False


def _is_exempt_numeric_context(const_node: ast.Constant) -> bool:
    """Evalúa si un número literal se encuentra en una definición de constante, atributo o default."""
    curr = getattr(const_node, "parent", None)
    while curr is not None:
        if _is_uppercase_assignment(curr) or isinstance(curr, ast.ClassDef):
            return True
        if isinstance(curr, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return const_node in curr.args.defaults or const_node in curr.args.kw_defaults
        curr = getattr(curr, "parent", None)
    return False


def _is_flagged_magic_number(node: ast.AST) -> bool:
    """Determina si un nodo AST representa un Magic Number no permitido."""
    if not isinstance(node, ast.Constant):
        return False
    if not isinstance(node.value, (int, float)) or isinstance(node.value, bool):
        return False
    if node.value in ALLOWED_NUMERIC_LITERALS:
        return False
    return not _is_exempt_numeric_context(node)


def check_file_level_smells(file_path: Path, lines: List[str], max_line_file: int) -> List[CodeSmell]:
    """Detecta Large File y Dead/Commented-out Code a nivel de archivo."""
    smells: List[CodeSmell] = []
    total_lines = len(lines)
    if total_lines > max_line_file:
        sev = Severity.CRITICA if total_lines >= max_line_file * CRITICAL_MULTIPLIER else Severity.MEDIA
        smells.append(CodeSmell(
            file_path=file_path, line=1, smell_type=SmellType.LARGE_FILE, severity=sev,
            diagnosis=f"Archivo extenso de {total_lines} líneas (límite recomendado: {max_line_file}).",
            suggestion="Modularizar dividiendo responsabilidades en submódulos especializados.",
        ))

    for start_line, end_line, count in detect_commented_code_blocks(lines, MIN_COMMENTED_CODE_LINES):
        sev = Severity.ALTA if count >= HIGH_COMMENTED_CODE_LINES else Severity.MEDIA
        smells.append(CodeSmell(
            file_path=file_path, line=start_line, smell_type=SmellType.DEAD_COMMENTED_CODE, severity=sev,
            diagnosis=f"Detectadas {count} líneas consecutivas de código comentado (líneas {start_line}-{end_line}).",
            suggestion="Eliminar el código comentado obsoleto. Git ya preserva el historial de versiones.",
        ))
    return smells


class PythonASTAnalyzer:
    """Motor de inspección estática de código Python mediante árboles AST."""

    def __init__(self, config: AnalysisConfig) -> None:
        self.config = config

    def analyze(self, file_path: Path, content: str) -> List[CodeSmell]:
        lines = content.splitlines()
        smells = check_file_level_smells(file_path, lines, self.config.max_line_file)
        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError:
            return smells

        _attach_parent_references(tree)
        self._inspect_ast_nodes(file_path, tree, smells)
        self._check_deep_nesting(file_path, tree, smells)
        return smells

    def _inspect_ast_nodes(self, file_path: Path, tree: ast.AST, smells: List[CodeSmell]) -> None:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                smells.extend(self._inspect_function(file_path, node))
            elif isinstance(node, ast.ClassDef):
                class_smell = self._inspect_class(file_path, node)
                if class_smell:
                    smells.append(class_smell)
            self._check_condition_and_literals(file_path, node, smells)

    def _inspect_function(self, file_path: Path, node: ast.FunctionDef | ast.AsyncFunctionDef) -> List[CodeSmell]:
        checkers = (
            self._check_function_length,
            self._check_parameter_list,
            self._check_mutable_defaults,
            self._check_function_complexity,
        )
        return [s for fn in checkers if (s := fn(file_path, node)) is not None]

    def _check_function_length(self, file_path: Path, node: ast.FunctionDef | ast.AsyncFunctionDef) -> Optional[CodeSmell]:
        raw_lines = (getattr(node, "end_lineno", node.lineno) - node.lineno) + 1
        effective_lines = raw_lines - _calculate_docstring_lines(node)
        limit = self.config.max_line_func
        if effective_lines <= limit:
            return None
        sev = Severity.CRITICA if effective_lines >= limit * CRITICAL_MULTIPLIER else Severity.ALTA
        return CodeSmell(
            file_path=file_path, line=node.lineno, smell_type=SmellType.LONG_METHOD, severity=sev,
            diagnosis=f"Función '{node.name}' tiene {effective_lines} líneas efectivas (límite: {limit}).",
            suggestion="Aplicar 'Extract Method' para descomponer la lógica en pasos cohesivos (SLAP).",
            symbol_name=node.name,
        )

    def _check_parameter_list(self, file_path: Path, node: ast.FunctionDef | ast.AsyncFunctionDef) -> Optional[CodeSmell]:
        args = node.args
        params = [a.arg for a in (args.posonlyargs + args.args + args.kwonlyargs)]
        if params and params[0] in ("self", "cls"):
            params = params[1:]
        count, limit = len(params), self.config.max_params
        if count <= limit:
            return None
        sev = Severity.ALTA if count >= limit + HIGH_PARAM_OFFSET else Severity.MEDIA
        preview = ", ".join(params[:PARAM_PREVIEW_LIMIT]) + ("..." if count > PARAM_PREVIEW_LIMIT else "")
        return CodeSmell(
            file_path=file_path, line=node.lineno, smell_type=SmellType.LONG_PARAMETER_LIST, severity=sev,
            diagnosis=f"Función '{node.name}' recibe {count} parámetros ({preview}) (límite: {limit}).",
            suggestion="Aplicar 'Introduce Parameter Object' o agrupar parámetros en una dataclass.",
            symbol_name=node.name,
        )

    def _check_mutable_defaults(self, file_path: Path, node: ast.FunctionDef | ast.AsyncFunctionDef) -> Optional[CodeSmell]:
        defaults = list(node.args.defaults) + [d for d in node.args.kw_defaults if d is not None]
        if not any(isinstance(d, MUTABLE_AST_NODES) for d in defaults):
            return None
        return CodeSmell(
            file_path=file_path, line=node.lineno, smell_type=SmellType.MUTABLE_DEFAULT_ARG, severity=Severity.ALTA,
            diagnosis=f"Función '{node.name}' utiliza un objeto mutable (list/dict/set) como valor por defecto.",
            suggestion="Usar 'None' por defecto e inicializar la estructura mutable dentro de la función.",
            symbol_name=node.name,
        )

    def _check_function_complexity(self, file_path: Path, node: ast.FunctionDef | ast.AsyncFunctionDef) -> Optional[CodeSmell]:
        complexity, limit = _compute_cyclomatic_complexity(node), self.config.max_complexity
        if complexity <= limit:
            return None
        sev = Severity.CRITICA if complexity >= limit * CRITICAL_MULTIPLIER else Severity.ALTA
        return CodeSmell(
            file_path=file_path, line=node.lineno, smell_type=SmellType.HIGH_CYCLOMATIC_COMPLEXITY, severity=sev,
            diagnosis=f"Función '{node.name}' tiene complejidad ciclomática de {complexity} (límite: {limit}).",
            suggestion="Simplificar bifurcaciones usando polimorfismo, tablas de despacho o funciones auxiliares.",
            symbol_name=node.name,
        )

    def _inspect_class(self, file_path: Path, node: ast.ClassDef) -> Optional[CodeSmell]:
        class_lines = (getattr(node, "end_lineno", node.lineno) - node.lineno) + 1
        method_count = sum(1 for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)))
        if class_lines <= self.config.max_line_class and method_count <= self.config.max_methods_class:
            return None
        is_crit = class_lines > self.config.max_line_class * CRITICAL_MULTIPLIER or method_count > CRITICAL_METHOD_LIMIT
        return CodeSmell(
            file_path=file_path, line=node.lineno, smell_type=SmellType.GOD_CLASS,
            severity=Severity.CRITICA if is_crit else Severity.ALTA,
            diagnosis=f"Clase '{node.name}' tiene {class_lines} líneas y {method_count} métodos (God Class).",
            suggestion="Aplicar Single Responsibility Principle (SRP) extrayendo responsabilidades a clases cohesivas.",
            symbol_name=node.name,
        )

    def _check_condition_and_literals(
        self, file_path: Path, node: ast.AST, smells: List[CodeSmell]
    ) -> None:
        test_expr = getattr(node, "test", None)
        if test_expr is not None:
            op_count = _count_logical_operators(test_expr)
            if op_count >= MIN_COMPLEX_BOOL_OPS:
                smells.append(CodeSmell(
                    file_path=file_path, line=getattr(node, "lineno", 1),
                    smell_type=SmellType.COMPLEX_CONDITION, severity=Severity.ALTA,
                    diagnosis=f"Condición booleana compleja con {op_count} operadores lógicos encadenados.",
                    suggestion="Extraer subcondiciones a variables explicativas ('Explaining Variables') o predicados.",
                ))

        if _is_flagged_magic_number(node):
            val = getattr(node, "value", None)
            smells.append(CodeSmell(
                file_path=file_path, line=getattr(node, "lineno", 1),
                smell_type=SmellType.MAGIC_NUMBER, severity=Severity.MEDIA,
                diagnosis=f"Número mágico literal '{val}' sin nombrar en la lógica de ejecución.",
                suggestion=f"Extraer '{val}' a una constante en MAYÚSCULAS o Enum de dominio.",
            ))

    def _check_deep_nesting(self, file_path: Path, tree: ast.AST, smells: List[CodeSmell]) -> None:
        reported_lines: Set[int] = set()
        stack: List[Tuple[ast.AST, int]] = [(tree, 0)]
        while stack:
            current_node, depth = stack.pop()
            for child in reversed(list(ast.iter_child_nodes(current_node))):
                next_depth, smell = self._evaluate_nesting_step(file_path, child, depth)
                if smell and smell.line not in reported_lines:
                    reported_lines.add(smell.line)
                    smells.append(smell)
                stack.append((child, next_depth))

    def _evaluate_nesting_step(
        self, file_path: Path, child: ast.AST, current_depth: int
    ) -> Tuple[int, Optional[CodeSmell]]:
        if not isinstance(child, CONTROL_FLOW_NODES):
            return current_depth, None
        next_depth = current_depth if _is_elif_node(child) else current_depth + 1
        limit = self.config.max_nesting
        if next_depth <= limit:
            return next_depth, None
        sev = Severity.CRITICA if next_depth >= limit + CRITICAL_NESTING_OFFSET else Severity.ALTA
        node_name = type(child).__name__.replace("Async", "")
        return next_depth, CodeSmell(
            file_path=file_path, line=getattr(child, "lineno", 1),
            smell_type=SmellType.DEEP_NESTING, severity=sev,
            diagnosis=f"Estructura '{node_name}' alcanza profundidad de anidación {next_depth} (límite: {limit}).",
            suggestion="Aplicar 'Guard Clauses' (retornos tempranos) o extraer bloques anidados a funciones.",
        )
