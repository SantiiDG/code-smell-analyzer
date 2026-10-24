"""
Suite de pruebas unitarias para Clean Code Smell Analyzer.
Verifica todas las heurísticas AST, Polyglot, exportadores y auto-auditoría.
"""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from analyzer.engine import SmellAnalyzerEngine
from analyzer.exporters import ReportExporter
from analyzer.models import AnalysisConfig, SmellType
from analyzer.polyglot_analyzer import PolyglotHeuristicAnalyzer
from analyzer.python_analyzer import PythonASTAnalyzer

TEST_FUNC_LIMIT: int = 5
TEST_FILE_LIMIT: int = 10
TEST_PARAM_LIMIT: int = 3
TEST_NESTING_LIMIT: int = 2
TEST_CLASS_METHODS_LIMIT: int = 3
TEST_COMPLEXITY_LIMIT: int = 3
PERFECT_SCORE: float = 100.0


class TestPythonASTSmells(unittest.TestCase):
    """Pruebas unitarias para el analizador AST de Python."""

    def setUp(self) -> None:
        self.config = AnalysisConfig(
            path=Path("."),
            max_line_func=TEST_FUNC_LIMIT,
            max_line_file=TEST_FILE_LIMIT,
            max_params=TEST_PARAM_LIMIT,
            max_nesting=TEST_NESTING_LIMIT,
            max_methods_class=TEST_CLASS_METHODS_LIMIT,
            max_complexity=TEST_COMPLEXITY_LIMIT,
        )
        self.analyzer = PythonASTAnalyzer(self.config)
        self.dummy_path = Path("sample.py")

    def test_detects_long_method_excluding_docstring(self) -> None:
        code_with_docstring = (
            "def documented():\n"
            '    """\n'
            "    Línea 1\n"
            "    Línea 2\n"
            "    Línea 3\n"
            "    Línea 4\n"
            '    """\n'
            "    return 1\n"
        )
        smells = self.analyzer.analyze(self.dummy_path, code_with_docstring)
        self.assertFalse(any(s.smell_type == SmellType.LONG_METHOD for s in smells))

        long_code = "def too_long():\n" + "".join(
            f"    x_{i} = 1\n" for i in range(TEST_FUNC_LIMIT + 1)
        )
        smells_long = self.analyzer.analyze(self.dummy_path, long_code)
        self.assertTrue(any(s.smell_type == SmellType.LONG_METHOD for s in smells_long))

    def test_detects_long_parameter_list_and_ignores_self(self) -> None:
        code = (
            "class Service:\n"
            "    def ok_method(self, a, b, c):\n"
            "        return a\n"
            "    def bad_method(self, a, b, c, d):\n"
            "        return a\n"
        )
        smells = self.analyzer.analyze(self.dummy_path, code)
        param_smells = [s for s in smells if s.smell_type == SmellType.LONG_PARAMETER_LIST]
        self.assertEqual(len(param_smells), 1)
        self.assertEqual(param_smells[0].symbol_name, "bad_method")

    def test_detects_deep_nesting_and_allows_elif_ladder(self) -> None:
        elif_code = (
            "def check(x):\n"
            "    if x == 1:\n"
            "        return 1\n"
            "    elif x == 2:\n"
            "        return 2\n"
        )
        self.assertFalse(any(
            s.smell_type == SmellType.DEEP_NESTING
            for s in self.analyzer.analyze(self.dummy_path, elif_code)
        ))

        nested_code = (
            "def deep(a):\n"
            "    if a:\n"
            "        for i in a:\n"
            "            while i:\n"
            "                return 1\n"
        )
        self.assertTrue(any(
            s.smell_type == SmellType.DEEP_NESTING
            for s in self.analyzer.analyze(self.dummy_path, nested_code)
        ))

    def test_detects_magic_numbers_and_ignores_constants(self) -> None:
        code = (
            "MAX_TIMEOUT = 3600\n"
            "def calc(val):\n"
            "    return val * 42\n"
        )
        smells = self.analyzer.analyze(self.dummy_path, code)
        magic = [s for s in smells if s.smell_type == SmellType.MAGIC_NUMBER]
        self.assertEqual(len(magic), 1)
        self.assertIn("42", magic[0].diagnosis)

    def test_detects_complex_condition_and_mutable_defaults(self) -> None:
        code = (
            "def process(a, b, c, items=[]):\n"
            "    if a and b and c and not items:\n"
            "        return 1\n"
            "    return 0\n"
        )
        smells = self.analyzer.analyze(self.dummy_path, code)
        types = {s.smell_type for s in smells}
        self.assertIn(SmellType.COMPLEX_CONDITION, types)
        self.assertIn(SmellType.MUTABLE_DEFAULT_ARG, types)

    def test_detects_god_class_and_commented_code(self) -> None:
        code = (
            "# def old_fn():\n"
            "#     x = 10\n"
            "#     return x\n"
            "class Huge:\n"
            "    def m1(self): pass\n"
            "    def m2(self): pass\n"
            "    def m3(self): pass\n"
            "    def m4(self): pass\n"
        )
        smells = self.analyzer.analyze(self.dummy_path, code)
        types = {s.smell_type for s in smells}
        self.assertIn(SmellType.DEAD_COMMENTED_CODE, types)
        self.assertIn(SmellType.GOD_CLASS, types)


class TestPolyglotAndSelfAudit(unittest.TestCase):
    """Pruebas para analizador Polyglot, exportadores y auto-auditoría del repositorio."""

    def test_polyglot_javascript_analysis(self) -> None:
        config = AnalysisConfig(path=Path("."), max_params=TEST_PARAM_LIMIT, max_nesting=TEST_NESTING_LIMIT)
        analyzer = PolyglotHeuristicAnalyzer(config)
        js_code = (
            "function pay(a, b, c, d) {\n"
            '    const msg = "{ llaves en string ignoradas }";\n'
            "    if (a && b && c && d) {\n"
            "        for (let i = 0; i < 1; i++) {\n"
            "            while (a) {\n"
            "                console.log(999);\n"
            "            }\n"
            "        }\n"
            "    }\n"
            "}\n"
        )
        smells = analyzer.analyze(Path("app.js"), js_code)
        types = {s.smell_type for s in smells}
        self.assertIn(SmellType.LONG_PARAMETER_LIST, types)
        self.assertIn(SmellType.COMPLEX_CONDITION, types)
        self.assertIn(SmellType.DEEP_NESTING, types)
        self.assertIn(SmellType.MAGIC_NUMBER, types)

    def test_exporters_markdown_and_json(self) -> None:
        project_root = Path(__file__).resolve().parent.parent
        config = AnalysisConfig(path=project_root)
        report = SmellAnalyzerEngine(config).run()

        with tempfile.TemporaryDirectory() as tmp_dir:
            md_path = Path(tmp_dir) / "report.md"
            json_path = Path(tmp_dir) / "report.json"
            ReportExporter.export(report, config, md_path)
            ReportExporter.export(report, config, json_path)
            self.assertTrue(md_path.exists())
            self.assertTrue(json_path.exists())

    def test_project_self_audit_is_hundred_percent_clean(self) -> None:
        project_root = Path(__file__).resolve().parent.parent
        config = AnalysisConfig(path=project_root)
        report = SmellAnalyzerEngine(config).run()
        score, grade, _ = report.health_score
        self.assertEqual(len(report.all_smells), 0, f"Smells encontrados: {report.all_smells}")
        self.assertEqual(score, PERFECT_SCORE)
        self.assertEqual(grade, "A+")


if __name__ == "__main__":
    unittest.main()
