"""
Motor central de orquestación del análisis de código fuente.
"""

from __future__ import annotations

from pathlib import Path
import time
from typing import List, Optional

from analyzer.discovery import discover_files
from analyzer.models import AnalysisConfig, CodeSmell, FileAnalysisResult, ProjectReport
from analyzer.polyglot_analyzer import PolyglotHeuristicAnalyzer
from analyzer.python_analyzer import PythonASTAnalyzer


def read_source_safely(file_path: Path) -> Optional[str]:
    """Lee el contenido de un archivo tolerando distintas codificaciones de caracteres."""
    for encoding in ("utf-8", "latin-1"):
        try:
            return file_path.read_text(encoding=encoding, errors="replace")
        except OSError:
            continue
    return None


class SmellAnalyzerEngine:
    """Coordina el descubrimiento de archivos, despacho de analizadores y agregación de métricas."""

    def __init__(self, config: AnalysisConfig) -> None:
        self.config = config
        self.python_analyzer = PythonASTAnalyzer(config)
        self.polyglot_analyzer = PolyglotHeuristicAnalyzer(config)

    def run(self) -> ProjectReport:
        start_time = time.time()
        file_results: List[FileAnalysisResult] = []
        total_loc = 0

        target_files = list(discover_files(
            self.config.path,
            self.config.lang,
            self.config.exclude_patterns,
        ))

        for file_path in target_files:
            result = self._analyze_single_file(file_path)
            if result is not None:
                total_loc += result.lines_count
                file_results.append(result)

        duration = time.time() - start_time
        return ProjectReport(
            total_files_scanned=len(file_results),
            total_loc=total_loc,
            duration_seconds=duration,
            file_results=file_results,
        )

    def _analyze_single_file(self, file_path: Path) -> Optional[FileAnalysisResult]:
        content = read_source_safely(file_path)
        if content is None:
            return None

        lines_count = len(content.splitlines())
        raw_smells = self._dispatch_analyzer(file_path, content)
        filtered = self._filter_and_sort_smells(raw_smells)

        return FileAnalysisResult(
            path=file_path,
            lines_count=lines_count,
            smells=filtered,
        )

    def _dispatch_analyzer(self, file_path: Path, content: str) -> List[CodeSmell]:
        if file_path.suffix.lower() == ".py":
            return self.python_analyzer.analyze(file_path, content)
        return self.polyglot_analyzer.analyze(file_path, content)

    def _filter_and_sort_smells(self, smells: List[CodeSmell]) -> List[CodeSmell]:
        if self.config.min_severity is not None:
            min_weight = self.config.min_severity.weight
            smells = [s for s in smells if s.severity.weight >= min_weight]
        return sorted(smells, key=lambda item: item.line)
