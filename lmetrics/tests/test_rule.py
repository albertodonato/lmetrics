import logging
from operator import attrgetter
from pathlib import Path

import pytest

from ..rule import (
    create_file_analyzers,
    FileAnalyzer,
    LuaFileRule,
    RuleRegistry,
    RuleSyntaxError,
)


class FakeRule:
    def __init__(self, *args, **kwargs):
        self.lines = []

    def analyze_line(self, line):
        self.lines.append(line)


class FakeLuaRule:
    def __init__(self, regexp):
        self.regexp = regexp
        self.calls = []

    def action(self, values):
        self.calls.append(values)


class TestFileAnalyzer:
    def test_analyze_line(self):
        """analyze_line calls all rules with every line."""
        rule1 = FakeRule()
        rule2 = FakeRule()
        analyzer = FileAnalyzer(Path("file.txt"), [rule1, rule2])
        analyzer.analyze_line("line1")
        analyzer.analyze_line("line2")
        assert rule1.lines == ["line1", "line2"]
        assert rule2.lines == ["line1", "line2"]


class TestLuaFileRule:
    def test_analyze_line_matching(self):
        """analyze_line calls the LuaRule if the regexp matches."""
        lua_rule = FakeLuaRule("foo(?P<val>.*)foo")
        rule = LuaFileRule(Path("file.txt"), lua_rule)
        rule.analyze_line("foobarfoo")
        rule.analyze_line("foobazfoo")
        assert lua_rule.calls == [{"val": "bar"}, {"val": "baz"}]

    def test_analyze_line_no_match(self):
        """analyze_line doesn't call the rule if the regexp doesn't match."""
        lua_rule = FakeLuaRule("foo(?P<val>.*)foo")
        rule = LuaFileRule(Path("file.txt"), lua_rule)
        rule.analyze_line("barfoobar")
        assert lua_rule.calls == []


@pytest.fixture
def registry():
    # fake metrics
    metrics = {"metric1": object(), "metric2": object()}
    yield RuleRegistry(metrics)


@pytest.fixture
def log_file(tmpdir):
    yield Path(tmpdir / "logfile")


@pytest.fixture
def rule_file(tmpdir):
    rule_code = """
    rules.rule = Rule('regexp')
    function rules.rule.action(match)
    end
    """
    rule_file = tmpdir / "rule"
    rule_file.write_text(rule_code, "utf-8")
    yield rule_file


class TestRuleRegistry:
    def test_get_file_analyzer(self, tmpdir, rule_file, log_file, registry):
        """get_file_analyzer returns a FileAnalyzer instance."""
        analyzer = registry.get_file_analyzer(log_file, rule_file)
        assert isinstance(analyzer, FileAnalyzer)
        assert analyzer.path == log_file

    def test_get_file_analyzer_caches_rules(self, rule_file, registry):
        """LuaFileRules are created once for each Lua file."""
        analyzer1 = registry.get_file_analyzer("file1.txt", rule_file)
        analyzer2 = registry.get_file_analyzer("file2.txt", rule_file)
        # The same rule is used in both analyzers
        assert len(analyzer1.rules) == 1
        assert analyzer1.rules == analyzer2.rules

    def test_get_file_analyzer_skip_empty_rules(self, caplog, rule_file, registry):
        """If a rule has no regexp defined, it's skipped."""
        rule_code = """
        rules.rule = Rule()
        function rules.rule.action(match)
        end
        """
        rule_file.write_text(rule_code, "utf-8")
        caplog.set_level(logging.DEBUG)
        analyzer = registry.get_file_analyzer("file1.txt", rule_file)
        # No rule is loaded
        assert len(analyzer.rules) == 0
        assert f"loaded 0 rule(s) from {rule_file}" in caplog.messages

    def test_rule_analyzer_run_rule_code(self, rule_file, log_file):
        """The returned FileAnalyzer runs the metric code."""

        class FakeMetric:
            def __init__(self):
                self.calls = []

            def call(self, match):
                self.calls.append(match)

        # create a registry with the metric
        metric = FakeMetric()
        registry = RuleRegistry({"metric": metric})
        rule_code = """
        rules.rule = Rule('foo(?P<val>.*)foo')
        function rules.rule.action(match)
          metrics.metric.call(match)
        end
        """
        rule_file.write_text(rule_code, "utf-8")
        analyzer = registry.get_file_analyzer(log_file, rule_file)
        analyzer.analyze_line("foobarfoo")
        analyzer.analyze_line("baz foo")
        analyzer.analyze_line("foobazfoo")
        # The rule code has called the call() method on the metric
        assert metric.calls == [{"val": "bar"}, {"val": "baz"}]

    def test_rule_print_logs(self, rule_file, caplog, log_file, registry):
        """The print function logs."""
        rule_code = """
        rules.rule = Rule('foo(?P<val>.*)foo')
        function rules.rule.action(match)
          print('value', match.val)
        end
        """
        rule_file.write_text(rule_code, "utf-8")
        caplog.set_level(logging.DEBUG)
        analyzer = registry.get_file_analyzer(log_file, rule_file)
        analyzer.analyze_line("foo33foo")
        assert "value 33" in caplog.messages

    def test_rule_without_action(self, rule_file, log_file, registry):
        """A rule without action no-ops and doesn't fail."""
        rule_code = """rules.rule = Rule('foo(?P<val>.*)foo')"""
        rule_file.write_text(rule_code, "utf-8")
        analyzer = registry.get_file_analyzer(log_file, rule_file)
        analyzer.analyze_line("foo bar baz")

    def test_rule_with_sintax_error(self, rule_file, caplog, log_file, registry):
        """A syntax error in rule code raises an error."""
        rule_code = """!WRONG"""
        rule_file.write_text(rule_code, "utf-8")
        with pytest.raises(RuleSyntaxError) as err:
            registry.get_file_analyzer(log_file, rule_file)
        assert "unexpected symbol" in str(err.value)


class TestCreateFileAnalyzers:
    def test_create_analyzers(self, tmpdir):
        """create_file_analyzers create a FileAnalyzer for each file."""
        rule_code1 = """
        rules.rule = Rule('regexp')
        function rules.rule.action(match)
        end
        """
        rule_file1 = tmpdir / "rule1"
        rule_file1.write_text(rule_code1, "utf-8")
        rule_code2 = """
        rules.rule = Rule('regexp')
        function rules.rule.action(match)
        end
        """
        rule_file2 = tmpdir / "rule2"
        rule_file2.write_text(rule_code2, "utf-8")
        rules_map = {
            Path("file1.txt").absolute(): rule_file1,
            Path("file2.txt").absolute(): rule_file2,
        }
        metrics = {"metric1": object(), "metric2": object()}
        analyzers = create_file_analyzers(rules_map, metrics)
        analyzer1, analyzer2 = sorted(analyzers, key=attrgetter("path"))
        assert analyzer1.path == Path("file1.txt").absolute()
        assert analyzer2.path == Path("file2.txt").absolute()
        # Each file uses a different rule (since they come from different
        # rule files)
        assert analyzer1.rules[0] is not analyzer2.rules[0]
