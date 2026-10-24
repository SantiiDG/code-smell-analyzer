"""
Modelos de dominio, enumeraciones y estructuras de datos para el reporte de auditoría.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from analyzer.constants import (
    DEFAULT_MAX_COMPLEXITY,
    DEFAULT_MAX_LINE_CLASS,
    DEFAULT_MAX_LINE_FILE,
    DEFAULT_MAX_LINE_FUNC,
    DEFAULT_MAX_METHODS_CLASS,
    DEFAULT_MAX_NESTING,
    DEFAULT_MAX_PARAMS,
    DENSITY_PENALTY_FACTOR,
    LOC_NORMALIZATION_FACTOR,
    MAX_HEALTH_SCORE,
    MIN_HEALTH_SCORE,
    SCORE_GRADE_A,
    SCORE_GRADE_A_PLUS,
    SCORE_GRADE_B,
    SCORE_GRADE_C,
    SCORE_GRADE_D,
    TOP_PRIORITY_COUNT,
    WEIGHT_CRITICAL,
    WEIGHT_HIGH,
    WEIGHT_MEDIUM,
)


class Severity(str, Enum):
    """Niveles de severidad de un Code Smell con sus pesos y estilos visuales."""

    CRITICA = "CRÍTICA"
    ALTA = "ALTA"
    MEDIA = "MEDIA"

    @property
    def weight(self) -> int:
        if self == Severity.CRITICA:
            return WEIGHT_CRITICAL
        if self == Severity.ALTA:
            return WEIGHT_HIGH
        return WEIGHT_MEDIUM

    @property
    def color_ansi(self) -> str:
        if self == Severity.CRITICA:
            return "\033[91m\033[1m"
        if self == Severity.ALTA:
            return "\033[93m\033[1m"
        return "\033[96m"

    @property
    def rich_style(self) -> str:
        if self == Severity.CRITICA:
            return "bold red"
        if self == Severity.ALTA:
            return "bold yellow"
        return "cyan"

    @classmethod
    def from_string(cls, value: Optional[str]) -> Optional[Severity]:
        if not value:
            return None
        normalized = value.strip().upper().replace("Í", "I")
        mapping = {
            "CRITICA": cls.CRITICA,
            "ALTA": cls.ALTA,
            "MEDIA": cls.MEDIA,
        }
        return mapping.get(normalized)


class SmellType(str, Enum):
    """Catálogo de Code Smells soportados por el motor de análisis."""

    LONG_METHOD = "Long Method / Function"
    GOD_CLASS = "God Class"
    LARGE_FILE = "Large File"
    DEEP_NESTING = "Deep Nesting"
    LONG_PARAMETER_LIST = "Long Parameter List"
    MAGIC_NUMBER = "Magic Number"
    DEAD_COMMENTED_CODE = "Dead / Commented-out Code"
    COMPLEX_CONDITION = "Complex Condition"
    HIGH_CYCLOMATIC_COMPLEXITY = "High Cyclomatic Complexity"
    MUTABLE_DEFAULT_ARG = "Mutable Default Argument"


@dataclass(frozen=True)
class CodeSmell:
    """Representa un hallazgo individual de deuda técnica en un archivo."""

    file_path: Path
    line: int
    smell_type: SmellType
    severity: Severity
    diagnosis: str
    suggestion: str
    symbol_name: Optional[str] = None


@dataclass
class AnalysisConfig:
    """Configuración y umbrales de ejecución del analizador."""

    path: Path
    lang: str = "all"
    max_line_func: int = DEFAULT_MAX_LINE_FUNC
    max_line_file: int = DEFAULT_MAX_LINE_FILE
    max_params: int = DEFAULT_MAX_PARAMS
    max_nesting: int = DEFAULT_MAX_NESTING
    max_line_class: int = DEFAULT_MAX_LINE_CLASS
    max_methods_class: int = DEFAULT_MAX_METHODS_CLASS
    max_complexity: int = DEFAULT_MAX_COMPLEXITY
    export_path: Optional[Path] = None
    min_severity: Optional[Severity] = None
    no_color: bool = False
    exclude_patterns: Set[str] = field(default_factory=set)


@dataclass
class FileAnalysisResult:
    """Resultado consolidado del análisis de un archivo individual."""

    path: Path
    lines_count: int
    smells: List[CodeSmell] = field(default_factory=list)

    @property
    def penalty_score(self) -> int:
        return sum(smell.severity.weight for smell in self.smells)

    @property
    def dominant_smell(self) -> str:
        if not self.smells:
            return "General"
        most_severe = max(self.smells, key=lambda s: s.severity.weight)
        return most_severe.smell_type.value


GRADE_THRESHOLDS: List[Tuple[float, str, str]] = [
    (SCORE_GRADE_A_PLUS, "A+", "Excelente: Código limpio, arquitectura sólida y mantenible"),
    (SCORE_GRADE_A, "A", "Muy Bueno: Mínima deuda técnica acumulada"),
    (SCORE_GRADE_B, "B", "Aceptable: Requiere refactorizaciones preventivas puntuales"),
    (SCORE_GRADE_C, "C", "Regular: Acumulación moderada de smells y acoplamiento"),
    (SCORE_GRADE_D, "D", "Deficiente: Alta deuda técnica con riesgo de regresión"),
]


@dataclass
class ProjectReport:
    """Informe global de salud arquitectónica del proyecto escaneado."""

    total_files_scanned: int
    total_loc: int
    duration_seconds: float
    file_results: List[FileAnalysisResult]

    @property
    def all_smells(self) -> List[CodeSmell]:
        return [smell for f_res in self.file_results for smell in f_res.smells]

    @property
    def files_with_smells(self) -> List[FileAnalysisResult]:
        return [f_res for f_res in self.file_results if f_res.smells]

    @property
    def total_penalties(self) -> int:
        return sum(f_res.penalty_score for f_res in self.file_results)

    @property
    def health_score(self) -> Tuple[float, str, str]:
        if self.total_loc == 0:
            return MAX_HEALTH_SCORE, "A+", GRADE_THRESHOLDS[0][2]

        density = (self.total_penalties / self.total_loc) * LOC_NORMALIZATION_FACTOR
        raw_score = MAX_HEALTH_SCORE - (density * DENSITY_PENALTY_FACTOR)
        score = max(MIN_HEALTH_SCORE, min(MAX_HEALTH_SCORE, round(raw_score, 1)))

        for threshold, grade, description in GRADE_THRESHOLDS:
            if score >= threshold:
                return score, grade, description
        return score, "F", "Crítico: Fragilidad arquitectónica y urgente refactorización"

    @property
    def top_priority_files(self) -> List[FileAnalysisResult]:
        return sorted(
            self.files_with_smells,
            key=lambda item: item.penalty_score,
            reverse=True,
        )[:TOP_PRIORITY_COUNT]

    def count_by_type_and_severity(self) -> Dict[SmellType, Tuple[int, int, int, int]]:
        counts: Dict[SmellType, Tuple[int, int, int, int]] = {}
        smells = self.all_smells
        for st in SmellType:
            c_crit = sum(1 for s in smells if s.smell_type == st and s.severity == Severity.CRITICA)
            c_high = sum(1 for s in smells if s.smell_type == st and s.severity == Severity.ALTA)
            c_med = sum(1 for s in smells if s.smell_type == st and s.severity == Severity.MEDIA)
            total = c_crit + c_high + c_med
            if total > 0:
                counts[st] = (c_crit, c_high, c_med, total)
        return counts
