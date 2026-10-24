"""
Renderizador visual de resultados en consola (Soporte para 'rich' y fallback ANSI).
"""

from __future__ import annotations

from analyzer.constants import (
    COL_WIDTH_LINE,
    COL_WIDTH_SEVERITY,
    COL_WIDTH_SMELL,
    PLAIN_SEPARATOR_WIDTH,
    SCORE_GRADE_C,
    SCORE_GREEN_THRESHOLD,
)
from analyzer.models import AnalysisConfig, FileAnalysisResult, ProjectReport

HAS_RICH = False
try:
    from rich import box
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


class ConsoleRenderer:
    """Presenta el informe de auditoría en la terminal con formato enriquecido o ANSI."""

    def __init__(self, no_color: bool = False) -> None:
        self.no_color = no_color
        self.use_rich = HAS_RICH and not no_color
        if self.use_rich:
            self.console = Console()

    def render(self, report: ProjectReport, config: AnalysisConfig) -> None:
        if self.use_rich:
            self._render_rich_report(report, config)
        else:
            self._render_plain_report(report, config)

    def _render_rich_report(self, report: ProjectReport, config: AnalysisConfig) -> None:
        self._print_rich_banner(config)
        self._print_rich_file_tables(report)
        self._print_rich_health_panel(report)
        self._print_rich_distribution_table(report)
        self._print_rich_priority_table(report)

    def _print_rich_banner(self, config: AnalysisConfig) -> None:
        title_text = Text()
        title_text.append("CLEAN CODE SMELL ANALYZER\n", style="bold cyan")
        subtitle = f"Directorio: {config.path.resolve()} | Lenguaje: {config.lang.upper()} | Python 3.10+"
        title_text.append(subtitle, style="dim")
        self.console.print(Panel(title_text, box=box.ROUNDED, border_style="cyan"))

    def _print_rich_file_tables(self, report: ProjectReport) -> None:
        flagged = report.files_with_smells
        if not flagged:
            msg = "\n[bold green]✓ No se detectaron code smells. El código cumple con los umbrales de Clean Code.[/bold green]\n"
            self.console.print(msg)
            return

        header = f"\n[bold underline]Hallazgos Detallados ({len(flagged)} archivos con deuda técnica):[/bold underline]\n"
        self.console.print(header)
        for file_res in flagged:
            self.console.print(self._build_rich_file_table(file_res))
            self.console.print()

    def _build_rich_file_table(self, file_res: FileAnalysisResult) -> Table:
        table = Table(
            title=f"📂 {file_res.path} ({len(file_res.smells)} smells | {file_res.lines_count} LOC)",
            title_style="bold white on blue",
            box=box.SIMPLE_HEAVY,
            header_style="bold magenta",
            expand=True,
        )
        table.add_column("Línea", justify="right", style="cyan", width=COL_WIDTH_LINE)
        table.add_column("Severidad", justify="center", width=COL_WIDTH_SEVERITY)
        table.add_column("Code Smell", style="bold yellow", width=COL_WIDTH_SMELL)
        table.add_column("Diagnóstico y Refactorización Sugerida", style="white")

        for smell in file_res.smells:
            sev_badge = Text(f"[{smell.severity.value}]", style=smell.severity.rich_style)
            detail = Text(f"{smell.diagnosis}\n", style="white")
            detail.append("💡 Refactor: ", style="bold green")
            detail.append(smell.suggestion, style="italic green")
            table.add_row(str(smell.line), sev_badge, smell.smell_type.value, detail)
        return table

    def _print_rich_health_panel(self, report: ProjectReport) -> None:
        score, grade, description = report.health_score
        grade_style = "bold green" if score >= SCORE_GREEN_THRESHOLD else (
            "bold yellow" if score >= SCORE_GRADE_C else "bold red"
        )
        score_text = Text("HEALTH SCORE GLOBAL: ", style="bold")
        score_text.append(f"{grade} ({score}/100)\n", style=grade_style)
        score_text.append(f"Evaluación: {description}\n", style="italic")
        stats = f"Archivos: {report.total_files_scanned} | LOC: {report.total_loc} | Tiempo: {report.duration_seconds:.2f}s"
        score_text.append(stats, style="dim")

        border = "green" if score >= SCORE_GRADE_C else "red"
        self.console.print(Panel(
            score_text,
            title="[bold]Resumen de Salud del Proyecto[/bold]",
            border_style=border,
            box=box.ROUNDED,
        ))

    def _print_rich_distribution_table(self, report: ProjectReport) -> None:
        counts = report.count_by_type_and_severity()
        if not counts:
            return
        table = Table(title="📊 Recuento de Code Smells por Tipo", box=box.ROUNDED)
        table.add_column("Tipo de Code Smell", style="bold")
        table.add_column("CRÍTICA", justify="center", style="bold red")
        table.add_column("ALTA", justify="center", style="bold yellow")
        table.add_column("MEDIA", justify="center", style="cyan")
        table.add_column("Total", justify="right", style="bold white")

        for smell_type, (c_crit, c_high, c_med, total) in counts.items():
            table.add_row(smell_type.value, str(c_crit), str(c_high), str(c_med), str(total))
        self.console.print(table)

    def _print_rich_priority_table(self, report: ProjectReport) -> None:
        top_files = report.top_priority_files
        if not top_files:
            return
        table = Table(title="🎯 Top 3 Archivos de Mayor Prioridad a Refactorizar", box=box.ROUNDED)
        table.add_column("Rank", justify="center", style="bold cyan")
        table.add_column("Ruta del Archivo", style="bold white")
        table.add_column("Smells", justify="center", style="yellow")
        table.add_column("Penalización", justify="center", style="bold red")
        table.add_column("Principal Recomendación", style="italic")

        for rank, f_res in enumerate(top_files, start=1):
            table.add_row(
                f"#{rank}",
                str(f_res.path),
                str(len(f_res.smells)),
                str(f_res.penalty_score),
                f"Priorizar refactorización de {f_res.dominant_smell}",
            )
        self.console.print(table)
        self.console.print()

    def _render_plain_report(self, report: ProjectReport, config: AnalysisConfig) -> None:
        c_reset = "" if self.no_color else "\033[0m"
        c_bold = "" if self.no_color else "\033[1m"
        c_cyan = "" if self.no_color else "\033[96m"
        c_green = "" if self.no_color else "\033[92m"
        sep = "=" * PLAIN_SEPARATOR_WIDTH

        print(f"\n{c_bold}{c_cyan}{sep}{c_reset}")
        print(f"{c_bold} CLEAN CODE SMELL ANALYZER — REPORTE DE DEUDA TÉCNICA{c_reset}")
        print(f" Directorio: {config.path.resolve()} | Lenguaje: {config.lang.upper()}")
        print(f"{c_bold}{c_cyan}{sep}{c_reset}\n")

        self._print_plain_files(report, c_bold, c_green, c_reset)
        self._print_plain_summary(report, c_bold, c_cyan, c_reset)

    def _print_plain_files(
        self, report: ProjectReport, c_bold: str, c_green: str, c_reset: str
    ) -> None:
        flagged = report.files_with_smells
        if not flagged:
            print(f"{c_green}✓ No se detectaron code smells en los archivos escaneados.{c_reset}\n")
            return
        for file_res in flagged:
            print(f"{c_bold}📂 Archivo: {file_res.path} ({len(file_res.smells)} smells, {file_res.lines_count} LOC){c_reset}")
            print("-" * PLAIN_SEPARATOR_WIDTH)
            for smell in file_res.smells:
                sev_col = "" if self.no_color else smell.severity.color_ansi
                print(f"  [L{smell.line:>4}] {sev_col}[{smell.severity.value:<7}]{c_reset} {c_bold}{smell.smell_type.value}{c_reset}")
                print(f"         Diagnóstico: {smell.diagnosis}")
                print(f"         {c_green}💡 Refactor:  {smell.suggestion}{c_reset}")
            print()

    def _print_plain_summary(
        self, report: ProjectReport, c_bold: str, c_cyan: str, c_reset: str
    ) -> None:
        score, grade, desc = report.health_score
        line = "-" * PLAIN_SEPARATOR_WIDTH
        print(f"{c_bold}{c_cyan}{line}{c_reset}")
        print(f"{c_bold}HEALTH SCORE GLOBAL: {grade} ({score}/100){c_reset}")
        print(f"Diagnóstico: {desc}")
        print(f"Archivos: {report.total_files_scanned} | LOC: {report.total_loc} | Tiempo: {report.duration_seconds:.2f}s")
        print(f"{c_bold}{c_cyan}{line}{c_reset}\n")

        top_files = report.top_priority_files
        if top_files:
            print(f"{c_bold}Top 3 Archivos de Mayor Prioridad a Refactorizar:{c_reset}")
            for rank, f_res in enumerate(top_files, start=1):
                print(f"  {rank}. {f_res.path} — {len(f_res.smells)} smells, Penalización: {f_res.penalty_score} pts (Foco: {f_res.dominant_smell})")
            print()
