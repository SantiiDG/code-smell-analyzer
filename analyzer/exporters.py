"""
Exportadores de informes de auditoría a formato Markdown (.md) y JSON (.json).
"""

from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any, Dict, List

from analyzer.models import AnalysisConfig, FileAnalysisResult, ProjectReport

JSON_INDENT_SPACES: int = 2
DURATION_DECIMALS: int = 4


class ReportExporter:
    """Gestiona la exportación del reporte de análisis a disco en Markdown o JSON."""

    @classmethod
    def export(cls, report: ProjectReport, config: AnalysisConfig, output_path: Path) -> None:
        if output_path.suffix.lower() == ".json":
            cls._export_json(report, config, output_path)
        else:
            cls._export_markdown(report, config, output_path)

    @classmethod
    def _export_json(cls, report: ProjectReport, config: AnalysisConfig, output_path: Path) -> None:
        score, grade, description = report.health_score
        payload: Dict[str, Any] = {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "target_path": str(config.path.resolve()),
            "language_filter": config.lang,
            "summary": {
                "health_score": score,
                "grade": grade,
                "description": description,
                "total_files_scanned": report.total_files_scanned,
                "total_loc": report.total_loc,
                "total_smells": len(report.all_smells),
                "duration_seconds": round(report.duration_seconds, DURATION_DECIMALS),
            },
            "files": [cls._serialize_file_result(f_res) for f_res in report.files_with_smells],
        }
        content = json.dumps(payload, indent=JSON_INDENT_SPACES, ensure_ascii=False)
        output_path.write_text(content, encoding="utf-8")

    @staticmethod
    def _serialize_file_result(f_res: FileAnalysisResult) -> Dict[str, Any]:
        return {
            "path": str(f_res.path),
            "lines_count": f_res.lines_count,
            "penalty_score": f_res.penalty_score,
            "smells": [
                {
                    "line": s.line,
                    "type": s.smell_type.value,
                    "severity": s.severity.value,
                    "diagnosis": s.diagnosis,
                    "suggestion": s.suggestion,
                    "symbol": s.symbol_name,
                }
                for s in f_res.smells
            ],
        }

    @classmethod
    def _export_markdown(cls, report: ProjectReport, config: AnalysisConfig, output_path: Path) -> None:
        sections: List[str] = []
        sections.extend(cls._build_md_header(report, config))
        sections.extend(cls._build_md_priorities(report))
        sections.extend(cls._build_md_distribution(report))
        sections.extend(cls._build_md_file_details(report))
        output_path.write_text("\n".join(sections), encoding="utf-8")

    @staticmethod
    def _build_md_header(report: ProjectReport, config: AnalysisConfig) -> List[str]:
        score, grade, description = report.health_score
        return [
            "# Reporte de Análisis de Code Smells y Deuda Técnica\n",
            "> Generado automáticamente por **Clean Code Smell Analyzer**  ",
            f"> Fecha de análisis: `{time.strftime('%Y-%m-%d %H:%M:%S')}`  ",
            f"> Objetivo: `{config.path.resolve()}` | Lenguaje: `{config.lang.upper()}`\n",
            "## 1. Resumen Ejecutivo de Salud\n",
            "| Métrica | Valor |",
            "| :--- | :--- |",
            f"| **Health Score Global** | **`{grade}` ({score}/100)** |",
            f"| **Diagnóstico de Salud** | {description} |",
            f"| **Archivos Escaneados** | {report.total_files_scanned} |",
            f"| **Líneas de Código (LOC)** | {report.total_loc:,} |",
            f"| **Total de Smells Detectados** | {len(report.all_smells)} |",
            f"| **Tiempo de Ejecución** | {report.duration_seconds:.2f} s |\n",
        ]

    @staticmethod
    def _build_md_priorities(report: ProjectReport) -> List[str]:
        top_files = report.top_priority_files
        if not top_files:
            return []
        lines = [
            "## 2. Top 3 Archivos Prioritarios a Refactorizar\n",
            "| Prioridad | Archivo | Smells Detectados | Penalización | Foco Principal |",
            "| :---: | :--- | :---: | :---: | :--- |",
        ]
        for idx, f_res in enumerate(top_files, start=1):
            lines.append(
                f"| **#{idx}** | `{f_res.path}` | {len(f_res.smells)} | {f_res.penalty_score} pts | {f_res.dominant_smell} |"
            )
        lines.append("")
        return lines

    @staticmethod
    def _build_md_distribution(report: ProjectReport) -> List[str]:
        counts = report.count_by_type_and_severity()
        if not counts:
            return []
        lines = [
            "## 3. Distribución de Code Smells por Tipo y Severidad\n",
            "| Tipo de Code Smell | CRÍTICA | ALTA | MEDIA | Total |",
            "| :--- | :---: | :---: | :---: | :---: |",
        ]
        for smell_type, (c_crit, c_high, c_med, total) in counts.items():
            lines.append(f"| **{smell_type.value}** | {c_crit} | {c_high} | {c_med} | **{total}** |")
        lines.append("")
        return lines

    @classmethod
    def _build_md_file_details(cls, report: ProjectReport) -> List[str]:
        flagged = report.files_with_smells
        lines = ["## 4. Hallazgos Detallados por Archivo\n"]
        if not flagged:
            lines.append("✓ *No se detectaron code smells. El código cumple con las heurísticas de Clean Code.*\n")
            return lines
        for f_res in flagged:
            lines.extend(cls._format_single_file_md(f_res))
        return lines

    @staticmethod
    def _format_single_file_md(f_res: FileAnalysisResult) -> List[str]:
        rows = [
            f"### 📂 `{f_res.path}`\n",
            f"- **Métricas del archivo:** {f_res.lines_count} líneas de código, {len(f_res.smells)} smells detectados.\n",
            "| Línea | Severidad | Code Smell | Diagnóstico | Sugerencia de Refactorización |",
            "| :---: | :---: | :--- | :--- | :--- |",
        ]
        for smell in f_res.smells:
            rows.append(
                f"| `{smell.line}` | **{smell.severity.value}** | {smell.smell_type.value} | {smell.diagnosis} | *{smell.suggestion}* |"
            )
        rows.append("")
        return rows
