#!/usr/bin/env python3
"""
================================================================================
Clean Code Smell Analyzer (CLI)
================================================================================
Punto de entrada principal para la auditoría estática de arquitectura,
deuda técnica y detección de Code Smells en Python y múltiples lenguajes.
================================================================================
"""

from __future__ import annotations

import sys

from analyzer.cli import run_cli
from analyzer.engine import SmellAnalyzerEngine
from analyzer.models import AnalysisConfig, CodeSmell, FileAnalysisResult, ProjectReport, Severity, SmellType

__all__ = [
    "AnalysisConfig",
    "CodeSmell",
    "FileAnalysisResult",
    "ProjectReport",
    "Severity",
    "SmellAnalyzerEngine",
    "SmellType",
    "main",
]


def main() -> int:
    """Ejecuta la interfaz de línea de comandos del analizador."""
    return run_cli()


if __name__ == "__main__":
    sys.exit(main())
