"""
Renderizador visual de resultados en consola (Dashboard 'rich' + Fallback ANSI).
"""

from __future__ import annotations

import sys
from typing import Optional

# Garantizar codificación UTF-8 para consolas Windows
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

from analyzer.constants import (
    COL_WIDTH_LINE,
    COL_WIDTH_SEVERITY,
    COL_WIDTH_SMELL,
    PLAIN_SEPARATOR_WIDTH,
)
from analyzer.models import AnalysisConfig, FileAnalysisResult, ProjectReport, Severity
from analyzer.ui_theme import (
    build_progress_bar,
    build_ratio_bar,
    format_rank_medal,
    get_score_color,
    get_severity_pill_style,
    get_smell_label,
)

HAS_RICH = False
try:
    from rich import box
    from rich.console import Console
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.table import Table
    from rich.text import Text
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


def _build_header_panel(config: AnalysisConfig) -> Panel:
    """Construye el banner superior con metadatos y reglas activas de la auditoría."""
    header = Text()
    header.append("⚡ CLEAN CODE SMELL ANALYZER v2.0", style="bold bright_cyan")
    header.append(" — ", style="dim")
    header.append("STATIC ARCHITECTURE & DEBT AUDITOR\n", style="bold white")
    header.append(f"📁 Destino:  {config.path.resolve()}\n", style="cyan")
    rules = (
        f"🌐 Lenguaje: {config.lang.upper()}  │  "
        f"⚙️ Umbrales: Func ≤ {config.max_line_func}L · File ≤ {config.max_line_file}L · "
        f"Params ≤ {config.max_params} · Nesting ≤ {config.max_nesting} · McCabe ≤ {config.max_complexity}"
    )
    header.append(rules, style="dim white")
    return Panel(header, box=box.HEAVY, border_style="bright_cyan", padding=(0, 1))


def _build_score_card(report: ProjectReport) -> Panel:
    """Construye la tarjeta KPI con el Health Score, nota y barra de progreso."""
    score, grade, description = report.health_score
    color = get_score_color(score)
    bar = build_progress_bar(score)

    content = Text()
    content.append("🏆 CALIFICACIÓN: ", style="bold white")
    content.append(f"{grade} ({score}/100)\n", style=f"bold {color}")
    content.append(f"{bar}\n", style=color)
    content.append(description, style="italic white")
    return Panel(content, title="[bold]🩺 Salud Arquitectónica[/bold]", border_style=color, box=box.ROUNDED)


def _build_metrics_card(report: ProjectReport) -> Panel:
    """Construye la tarjeta KPI con métricas de alcance, volumen y severidades."""
    smells = report.all_smells
    c_crit = sum(1 for s in smells if s.severity == Severity.CRITICA)
    c_high = sum(1 for s in smells if s.severity == Severity.ALTA)
    c_med = sum(1 for s in smells if s.severity == Severity.MEDIA)

    content = Text()
    content.append(f"📄 Archivos: {report.total_files_scanned:<5} ", style="white")
    content.append(f"📝 LOC: {report.total_loc:,}\n", style="cyan")
    content.append(f"⏱️ Tiempo:   {report.duration_seconds:.2f}s   ", style="dim white")
    content.append(f"⚖️ Penalización: {report.total_penalties} pts\n", style="yellow")
    content.append(f"🔴 Críticas: {c_crit}  ", style="bold red")
    content.append(f"🟡 Altas: {c_high}  ", style="bold yellow")
    content.append(f"🔵 Medias: {c_med}", style="bold cyan")
    return Panel(content, title="[bold]📊 Métricas de Escaneo[/bold]", border_style="bright_blue", box=box.ROUNDED)


def _build_kpi_dashboard(report: ProjectReport) -> Table:
    """Organiza las tarjetas de salud y métricas en una rejilla de dos columnas."""
    grid = Table.grid(expand=True, padding=(0, 1))
    grid.add_column(ratio=1)
    grid.add_column(ratio=1)
    grid.add_row(_build_score_card(report), _build_metrics_card(report))
    return grid


def _build_clean_project_panel() -> Panel:
    """Construye el panel de verificación exitosa cuando no existen code smells."""
    checklist = Text("✔ EXCELENTE: 0 Code Smells detectados en el código auditado\n\n", style="bold bright_green")
    checks = (
        "  ✓ Cohesión de Clases y Tamaño de Archivos (SRP) ......... OK\n"
        "  ✓ Longitud Efectiva y Nivel de Abstracción (SLAP) ....... OK\n"
        "  ✓ Complejidad Ciclomática de McCabe y Anidación ......... OK\n"
        "  ✓ Encapsulación de Parámetros y Constantes con Nombre ... OK\n"
        "  ✓ Higiene Sintáctica (Sin Código Muerto ni Mutables) .... OK"
    )
    checklist.append(checks, style="green")
    title = "[bold bright_green]🛡️ Auditoría Superada con Éxito[/bold bright_green]"
    return Panel(checklist, title=title, border_style="bright_green", box=box.ROUNDED)


def _build_file_smells_table(file_res: FileAnalysisResult) -> Table:
    """Construye la tabla detallada de hallazgos y sugerencias para un archivo."""
    title = (
        f"📂 [bold white]{file_res.path}[/bold white]  "
        f"[dim]│[/dim]  📏 [cyan]{file_res.lines_count} LOC[/cyan]  "
        f"[dim]│[/dim]  ⚠️ [yellow]{len(file_res.smells)} Smells[/yellow]  "
        f"[dim]│[/dim]  🔥 [bold red]{file_res.penalty_score} pts[/bold red]"
    )
    table = Table(
        title=title,
        title_justify="left",
        box=box.ROUNDED,
        border_style="blue",
        header_style="bold bright_magenta",
        show_lines=True,
        expand=True,
    )
    table.add_column("Línea", justify="right", style="bold cyan", width=COL_WIDTH_LINE, no_wrap=True)
    table.add_column("Severidad", justify="center", width=COL_WIDTH_SEVERITY, no_wrap=True)
    table.add_column("Code Smell", style="bold yellow", width=COL_WIDTH_SMELL)
    table.add_column("Diagnóstico Técnico y Refactorización Accionable", style="white")

    for smell in file_res.smells:
        pill_style = get_severity_pill_style(smell.severity)
        sev_badge = Text(f" {smell.severity.value:^7} ", style=pill_style)
        smell_label = get_smell_label(smell.smell_type)

        detail = Text("📌 Diagnóstico: ", style="bold white")
        detail.append(f"{smell.diagnosis}\n", style="white")
        detail.append("🛠️ Refactor:    ", style="bold bright_green")
        detail.append(smell.suggestion, style="italic bright_green")
        table.add_row(f"L{smell.line}", sev_badge, smell_label, detail)
    return table


def _build_distribution_table(report: ProjectReport) -> Optional[Table]:
    """Construye la tabla de distribución de smells con barras proporcionales alineadas."""
    counts = report.count_by_type_and_severity()
    if not counts:
        return None
    total_all = len(report.all_smells)
    table = Table(
        title="📊 Distribución de Deuda Técnica por Categoría",
        box=box.ROUNDED,
        border_style="cyan",
        header_style="bold cyan",
        expand=True,
    )
    table.add_column("Categoría de Code Smell", style="bold white")
    table.add_column("Crítica", justify="center", style="bold red")
    table.add_column("Alta", justify="center", style="bold yellow")
    table.add_column("Media", justify="center", style="cyan")
    table.add_column("Total", justify="right", style="bold white", no_wrap=True)
    table.add_column("Proporción", justify="left", style="bright_cyan", no_wrap=True)

    for smell_type, (c_crit, c_high, c_med, tot) in counts.items():
        ratio_bar = build_ratio_bar(tot, total_all)
        table.add_row(get_smell_label(smell_type), str(c_crit), str(c_high), str(c_med), str(tot), ratio_bar)
    return table


def _build_priority_table(report: ProjectReport) -> Optional[Table]:
    """Construye el podio de los 3 archivos más prioritarios para refactorizar."""
    top_files = report.top_priority_files
    if not top_files:
        return None
    table = Table(
        title="🎯 Podio de Prioridad: Top Archivos a Refactorizar",
        box=box.ROUNDED, border_style="yellow", header_style="bold yellow", expand=True,
    )
    table.add_column("Prioridad", justify="center", style="bold bright_yellow", width=COL_WIDTH_SEVERITY, no_wrap=True)
    table.add_column("Ruta del Archivo", style="bold white")
    table.add_column("Hallazgos", justify="center", style="yellow", no_wrap=True)
    table.add_column("Impacto", justify="center", style="bold red", no_wrap=True)
    table.add_column("Hoja de Ruta Sugerida", style="italic bright_green")

    for rank, f_res in enumerate(top_files, start=1):
        focus = f"Atacar primero: {f_res.dominant_smell}"
        table.add_row(format_rank_medal(rank), str(f_res.path), f"{len(f_res.smells)} smells", f"{f_res.penalty_score} pts", focus)
    return table


class ConsoleRenderer:
    """Presenta el informe de auditoría en la terminal con formato enriquecido o ANSI."""

    def __init__(self, no_color: bool = False) -> None:
        self.no_color = no_color
        self.use_rich = HAS_RICH and not no_color
        if self.use_rich:
            self.console = Console()

    def render(self, report: ProjectReport, config: AnalysisConfig) -> None:
        if self.use_rich:
            self._render_rich_dashboard(report, config)
        else:
            self._render_plain_report(report, config)

    def _render_rich_dashboard(self, report: ProjectReport, config: AnalysisConfig) -> None:
        self.console.print()
        self.console.print(_build_header_panel(config))
        self.console.print(_build_kpi_dashboard(report))

        flagged = report.files_with_smells
        if not flagged:
            self.console.print(_build_clean_project_panel())
            self.console.print()
            return

        self.console.print()
        self.console.print(Rule(f"[bold bright_cyan]🔍 HALLAZGOS DETALLADOS ({len(flagged)} archivos)[/bold bright_cyan]"))
        for file_res in flagged:
            self.console.print()
            self.console.print(_build_file_smells_table(file_res))

        self.console.print()
        self.console.print(Rule("[bold bright_cyan]📈 RESUMEN EJECUTIVO Y PRIORIDADES[/bold bright_cyan]"))
        dist_table = _build_distribution_table(report)
        if dist_table:
            self.console.print(dist_table)
        prio_table = _build_priority_table(report)
        if prio_table:
            self.console.print(prio_table)
        self.console.print()

    def _render_plain_report(self, report: ProjectReport, config: AnalysisConfig) -> None:
        c_reset = "" if self.no_color else "\033[0m"
        c_bold = "" if self.no_color else "\033[1m"
        c_cyan = "" if self.no_color else "\033[96m"
        c_green = "" if self.no_color else "\033[92m"
        sep = "=" * PLAIN_SEPARATOR_WIDTH

        print(f"\n{c_bold}{c_cyan}{sep}{c_reset}")
        print(f"{c_bold} ⚡ CLEAN CODE SMELL ANALYZER v2.0 — REPORTE DE AUDITORÍA{c_reset}")
        print(f" 📁 Destino: {config.path.resolve()} | 🌐 Lenguaje: {config.lang.upper()}")
        print(f"{c_bold}{c_cyan}{sep}{c_reset}\n")

        self._print_plain_files(report, c_bold, c_green, c_reset)
        self._print_plain_summary(report, c_bold, c_cyan, c_reset)

    def _print_plain_files(
        self, report: ProjectReport, c_bold: str, c_green: str, c_reset: str
    ) -> None:
        flagged = report.files_with_smells
        if not flagged:
            print(f"{c_green}✔ EXCELENTE: 0 Code Smells detectados en los archivos escaneados.{c_reset}\n")
            return
        for file_res in flagged:
            print(f"{c_bold}📂 {file_res.path} ({len(file_res.smells)} smells | {file_res.lines_count} LOC | {file_res.penalty_score} pts){c_reset}")
            print("-" * PLAIN_SEPARATOR_WIDTH)
            for smell in file_res.smells:
                sev_col = "" if self.no_color else smell.severity.color_ansi
                label = get_smell_label(smell.smell_type)
                print(f"  [L{smell.line:>4}] {sev_col}[{smell.severity.value:<7}]{c_reset} {c_bold}{label}{c_reset}")
                print(f"         📌 Diagnóstico: {smell.diagnosis}")
                print(f"         {c_green}🛠️ Refactor:    {smell.suggestion}{c_reset}")
            print()

    def _print_plain_summary(
        self, report: ProjectReport, c_bold: str, c_cyan: str, c_reset: str
    ) -> None:
        score, grade, desc = report.health_score
        bar = build_progress_bar(score)
        line = "-" * PLAIN_SEPARATOR_WIDTH
        print(f"{c_bold}{c_cyan}{line}{c_reset}")
        print(f"{c_bold}🏆 HEALTH SCORE GLOBAL: {grade} ({score}/100)  [{bar}]{c_reset}")
        print(f"Evaluación: {desc}")
        print(f"Archivos: {report.total_files_scanned} | LOC: {report.total_loc} | Tiempo: {report.duration_seconds:.2f}s")
        print(f"{c_bold}{c_cyan}{line}{c_reset}\n")

        top_files = report.top_priority_files
        if top_files:
            print(f"{c_bold}🎯 Top 3 Archivos de Mayor Prioridad a Refactorizar:{c_reset}")
            for rank, f_res in enumerate(top_files, start=1):
                medal = format_rank_medal(rank)
                print(f"  {medal} {f_res.path} — {len(f_res.smells)} smells ({f_res.penalty_score} pts) -> Foco: {f_res.dominant_smell}")
            print()
