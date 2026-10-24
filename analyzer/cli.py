"""
Interfaz de Línea de Comandos (CLI) y configuración de punto de entrada.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import List, Optional

from analyzer.constants import (
    DEFAULT_MAX_COMPLEXITY,
    DEFAULT_MAX_LINE_FILE,
    DEFAULT_MAX_LINE_FUNC,
    DEFAULT_MAX_NESTING,
    DEFAULT_MAX_PARAMS,
)
from analyzer.engine import SmellAnalyzerEngine
from analyzer.exporters import ReportExporter
from analyzer.models import AnalysisConfig, Severity
from analyzer.renderers import ConsoleRenderer, HAS_RICH


def configure_utf8_streams() -> None:
    """Reconfigura stdout y stderr a UTF-8 para soportar emojis y bordes en consolas Windows."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _add_threshold_arguments(parser: argparse.ArgumentParser) -> None:
    """Agrega los parámetros de umbrales de Clean Code al parser CLI."""
    parser.add_argument(
        "--max-line-func",
        type=int,
        default=DEFAULT_MAX_LINE_FUNC,
        help="Límite máximo recomendado de líneas efectivas por función o método.",
    )
    parser.add_argument(
        "--max-line-file",
        type=int,
        default=DEFAULT_MAX_LINE_FILE,
        help="Límite máximo recomendado de líneas por archivo.",
    )
    parser.add_argument(
        "--max-params",
        type=int,
        default=DEFAULT_MAX_PARAMS,
        help="Límite máximo de parámetros admitidos por función.",
    )
    parser.add_argument(
        "--max-nesting",
        type=int,
        default=DEFAULT_MAX_NESTING,
        help="Profundidad máxima recomendada de anidación de bloques de control.",
    )
    parser.add_argument(
        "--max-complexity",
        type=int,
        default=DEFAULT_MAX_COMPLEXITY,
        help="Límite máximo de Complejidad Ciclomática de McCabe por función.",
    )


def _add_output_arguments(parser: argparse.ArgumentParser) -> None:
    """Agrega los parámetros de exportación, filtrado y visualización al parser CLI."""
    parser.add_argument(
        "--export",
        type=str,
        default=None,
        metavar="FILE",
        help="Ruta opcional para exportar el informe a Markdown (.md) o JSON (.json).",
    )
    parser.add_argument(
        "--severity",
        type=str,
        choices=["MEDIA", "ALTA", "CRITICA", "CRÍTICA"],
        default=None,
        help="Filtrar reporte para mostrar únicamente smells iguales o superiores a esta severidad.",
    )
    parser.add_argument(
        "--exclude",
        type=str,
        nargs="*",
        default=[],
        help="Nombres de archivos o carpetas adicionales a excluir del análisis.",
    )
    parser.add_argument("--no-color", action="store_true", help="Desactivar colores ANSI y formato enriquecido.")


def build_argument_parser() -> argparse.ArgumentParser:
    """Construye y configura el parser de argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        prog="smell_analyzer.py",
        description="Analizador estático de arquitectura y Code Smells para Clean Code y Refactorización.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--path", type=str, default=".", help="Ruta de la carpeta o archivo a analizar.")
    parser.add_argument(
        "--lang",
        type=str,
        default="all",
        help="Lenguaje a inspeccionar (o 'all' para autodetección: py, js, ts, java, c, cpp, cs, go, etc.).",
    )
    _add_threshold_arguments(parser)
    _add_output_arguments(parser)
    return parser


def build_config_from_args(args: argparse.Namespace) -> AnalysisConfig:
    """Construye el objeto AnalysisConfig a partir de los argumentos parseados."""
    export_path = Path(args.export) if args.export else None
    return AnalysisConfig(
        path=Path(args.path),
        lang=args.lang,
        max_line_func=args.max_line_func,
        max_line_file=args.max_line_file,
        max_params=args.max_params,
        max_nesting=args.max_nesting,
        max_complexity=args.max_complexity,
        export_path=export_path,
        min_severity=Severity.from_string(args.severity),
        no_color=args.no_color,
        exclude_patterns=set(args.exclude or []),
    )


def _notify_export_success(export_path: Path, no_color: bool) -> None:
    """Imprime confirmación de exportación del reporte en terminal."""
    resolved = export_path.resolve()
    if HAS_RICH and not no_color:
        from rich.console import Console
        Console().print(f"[bold green]✓ Informe exportado exitosamente en:[/bold green] [underline]{resolved}[/underline]\n")
    else:
        print(f"✓ Informe exportado exitosamente en: {resolved}\n")


def run_cli(argv: Optional[List[str]] = None) -> int:
    """Ejecuta el flujo completo de la aplicación CLI y retorna el código de salida."""
    configure_utf8_streams()
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    config = build_config_from_args(args)
    if not config.path.exists():
        sys.stderr.write(f"Error: La ruta especificada no existe: {args.path}\n")
        return 1

    report = SmellAnalyzerEngine(config).run()
    ConsoleRenderer(no_color=config.no_color).render(report, config)

    if config.export_path is not None:
        ReportExporter.export(report, config, config.export_path)
        _notify_export_success(config.export_path, config.no_color)

    has_critical = any(smell.severity == Severity.CRITICA for smell in report.all_smells)
    return 1 if has_critical else 0
