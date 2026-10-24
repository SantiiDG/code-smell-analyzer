"""
Tema visual, iconos, barras de progreso y componentes estilizados para la terminal.
"""

from __future__ import annotations

from typing import Dict

from analyzer.constants import (
    LOC_NORMALIZATION_FACTOR,
    SCORE_GRADE_C,
    SCORE_GREEN_THRESHOLD,
)
from analyzer.models import Severity, SmellType

BAR_WIDTH_SCORE: int = 20
BAR_WIDTH_DIST: int = 12
RANK_FIRST: int = 1
RANK_SECOND: int = 2
RANK_THIRD: int = 3

SMELL_ICONS: Dict[SmellType, str] = {
    SmellType.LONG_METHOD: "📏",
    SmellType.GOD_CLASS: "🏛️",
    SmellType.LARGE_FILE: "📜",
    SmellType.DEEP_NESTING: "🪆",
    SmellType.LONG_PARAMETER_LIST: "📦",
    SmellType.MAGIC_NUMBER: "🔢",
    SmellType.DEAD_COMMENTED_CODE: "💀",
    SmellType.COMPLEX_CONDITION: "🧩",
    SmellType.HIGH_CYCLOMATIC_COMPLEXITY: "🌀",
    SmellType.MUTABLE_DEFAULT_ARG: "🧬",
}

SEVERITY_PILL_STYLES: Dict[Severity, str] = {
    Severity.CRITICA: "bold white on red",
    Severity.ALTA: "bold black on yellow",
    Severity.MEDIA: "bold black on cyan",
}

RANK_MEDALS: Dict[int, str] = {
    RANK_FIRST: "🥇 #1",
    RANK_SECOND: "🥈 #2",
    RANK_THIRD: "🥉 #3",
}


def get_smell_label(smell_type: SmellType) -> str:
    """Devuelve el nombre del Code Smell precedido por su icono representativo."""
    icon = SMELL_ICONS.get(smell_type, "⚠️")
    return f"{icon} {smell_type.value}"


def get_severity_pill_style(severity: Severity) -> str:
    """Devuelve el estilo de etiqueta tipo píldora (badge) para una severidad."""
    return SEVERITY_PILL_STYLES.get(severity, "cyan")


def get_score_color(score: float) -> str:
    """Determina el color semántico correspondiente a una puntuación de salud."""
    if score >= SCORE_GREEN_THRESHOLD:
        return "green"
    if score >= SCORE_GRADE_C:
        return "yellow"
    return "red"


def build_progress_bar(percentage: float, width: int = BAR_WIDTH_SCORE) -> str:
    """Construye una barra de progreso Unicode proporcional al porcentaje (0-100)."""
    clamped = max(0.0, min(LOC_NORMALIZATION_FACTOR, percentage))
    filled = round((clamped / LOC_NORMALIZATION_FACTOR) * width)
    empty = width - filled
    return f"{'█' * filled}{'░' * empty}"


def build_ratio_bar(count: int, total: int, width: int = BAR_WIDTH_DIST) -> str:
    """Construye una barra visual proporcional para tablas de distribución."""
    if total <= 0:
        return "░" * width
    ratio = (count / total) * LOC_NORMALIZATION_FACTOR
    bar = build_progress_bar(ratio, width=width)
    return f"{bar} {ratio:>4.0f}%"


def format_rank_medal(rank: int) -> str:
    """Formatea el número de prioridad con medalla visual para el Top 3."""
    return RANK_MEDALS.get(rank, f"#{rank}")
