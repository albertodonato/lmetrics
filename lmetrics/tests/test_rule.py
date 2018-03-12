from collections import namedtuple
import logging
from operator import attrgetter
from pathlib import Path

from fixtures import LoggerFixture
from toolrack.testing import (
    TestCase,
    TempDirFixture,
)

from ..rule import (
    RuleSyntaxError,
    FileAnalyzer,
    LuaFileRule,
    RuleRegistry,
    create_file_analyzers,
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


FakeLuaFileRule = namedtuple('FakeLuaFileRule', ['name', 'lua_rule'])


class FileAnalyzerTests(TestCase):

    def test_analyze_line(self):
        """analyze_line calls all rules with every line."""
        rule1 = FakeRule()
        rule2 = FakeRule()
        analyzer = FileAnalyzer(Path('file.txt'), [rule1, rule2])
        analyzer.analyze_line('line1')
        analyzer.analyze_line('line2')
        self.assertEqual(rule1.lines, ['line1', 'line2'])
        self.assertEqual(rule2.lines, ['line1', 'line2'])


class LuaFileRuleTests(TestCase):

    def test_analyze_line_matching(self):
        """analyze_line calls the LuaRule if the regexp matches."""
        lua_rule = FakeLuaRule('foo(?P<val>.*)foo')
        rule = LuaFileRule(Path('file.txt'), lua_rule)
        rule.analyze_line('foobarfoo')
        rule.analyze_line('foobazfoo')
        self.assertEqual(lua_rule.calls, [{'val': 'bar'}, {'val': 'baz'}])

    def test_analyze_line_no_match(self):
        """analyze_line doesn't call the rule if the regexp doesn't match."""
        lua_rule = FakeLuaRule('foo(?P<val>.*)foo')
        rule = LuaFileRule(Path('file.txt'), lua_rule)
        rule.analyze_line('barfoobar')
        self.assertEqual(lua_rule.calls, [])


class RuleRegistryTests(TestCase):

    def setUp(self):
        super().setUp()
        self.tempdir = self.useFixture(TempDirFixture())
        self.logfile = self.tempdir.mkfile(path='file.txt')
        # fake metrics
        self.metrics = {'metric1': object(), 'metric2': object()}
        self.registry = RuleRegistry(self.metrics)
        self.registry.lua_rule_class = FakeLuaFileRule

        self.logger = self.useFixture(LoggerFixture(level=logging.DEBUG))

    def test_get_file_analyzer(self):
        """get_file_analyzer returns a FileAnalyzer instance."""
        rule_file = self.tempdir.mkfile()
        analyzer = self.registry.get_file_analyzer(self.logfile, rule_file)
        self.assertIsInstance(analyzer, FileAnalyzer)
        self.assertEqual(analyzer.path, self.logfile)

    def test_get_file_analyzer_caches_rules(self):
        """LuaFileRules are created once for each Lua file."""
        rule_code = '''
        rules.rule = Rule('regexp')
        function rules.rule.action(match)
        end
        '''
        rule_file = self.tempdir.mkfile(content=rule_code)
        analyzer1 = self.registry.get_file_analyzer('file1.txt', rule_file)
        analyzer2 = self.registry.get_file_analyzer('file2.txt', rule_file)
        # The same rule is used in both analyzers
        self.assertEqual(len(analyzer1.rules), 1)
        self.assertEqual(analyzer1.rules, analyzer2.rules)

    def test_get_file_analyzer_skip_empty_rules(self):
        """If a rule has no regexp defined, it's skipped."""
        rule_code = '''
        rules.rule = Rule()
        function rules.rule.action(match)
        end
        '''
        rule_file = self.tempdir.mkfile(content=rule_code)
        analyzer = self.registry.get_file_analyzer('file1.txt', rule_file)
        # No rule is loaded
        self.assertEqual(len(analyzer.rules), 0)
        self.assertIn('loaded 0 rule(s)', self.logger.output)

    def test_rule_analyzer_run_rule_code(self):
        """The returned FileAnalyzer runs the metric code."""

        class FakeMetric:

            def __init__(self):
                self.calls = []

            def call(self, match):
                self.calls.append(match)

        # create a registry with the metric
        metric = FakeMetric()
        registry = RuleRegistry({'metric': metric})
        rule_code = '''
        rules.rule = Rule('foo(?P<val>.*)foo')
        function rules.rule.action(match)
          metrics.metric.call(match)
        end
        '''
        rule_file = self.tempdir.mkfile(content=rule_code)
        analyzer = registry.get_file_analyzer(self.logfile, rule_file)
        analyzer.analyze_line('foobarfoo')
        analyzer.analyze_line('baz foo')
        analyzer.analyze_line('foobazfoo')
        # The rule code has called the call() method on the metric
        self.assertEqual(metric.calls, [{'val': 'bar'}, {'val': 'baz'}])

    def test_rule_print_logs(self):
        """The print function logs."""
        rule_code = '''
        rules.rule = Rule('foo(?P<val>.*)foo')
        function rules.rule.action(match)
          print('value', match.val)
        end
        '''
        rule_file = self.tempdir.mkfile(content=rule_code)
        analyzer = self.registry.get_file_analyzer(self.logfile, rule_file)
        analyzer.analyze_line('foo33foo')
        self.assertIn('value 33', self.logger.output)

    def test_rule_without_action(self):
        """A rule without action no-ops and doesn't fail."""
        rule_code = '''rules.rule = Rule('foo(?P<val>.*)foo')'''
        rule_file = self.tempdir.mkfile(content=rule_code)
        analyzer = self.registry.get_file_analyzer(self.logfile, rule_file)
        analyzer.analyze_line('foo bar baz')

    def test_rule_with_sintax_error(self):
        """A syntax error in rule code raises an error."""
        rule_code = '''!WRONG'''
        rule_file = self.tempdir.mkfile(content=rule_code)
        with self.assertRaises(RuleSyntaxError) as context_manager:
            self.registry.get_file_analyzer(self.logfile, rule_file)
        self.assertIn('unexpected symbol', str(context_manager.exception))


class CreateFileAnalyzersTests(TestCase):

    def setUp(self):
        super().setUp()
        self.tempdir = self.useFixture(TempDirFixture())
        # fake metrics
        self.metrics = {'metric1': object(), 'metric2': object()}

    def test_create_analyzers(self):
        """create_file_analyzers create a FileAnalyzer for each file."""
        rule_code1 = '''
        rules.rule = Rule('regexp')
        function rules.rule.action(match)
        end
        '''
        rule_file1 = self.tempdir.mkfile(content=rule_code1)
        rule_code2 = '''
        rules.rule = Rule('regexp')
        function rules.rule.action(match)
        end
        '''
        rule_file2 = self.tempdir.mkfile(content=rule_code2)
        rules_map = {
            Path('file1.txt').absolute(): rule_file1,
            Path('file2.txt').absolute(): rule_file2}
        analyzers = create_file_analyzers(rules_map, self.metrics)
        analyzer1, analyzer2 = sorted(analyzers, key=attrgetter('path'))
        self.assertEqual(analyzer1.path, Path('file1.txt').absolute())
        self.assertEqual(analyzer2.path, Path('file2.txt').absolute())
        # Each file uses a different rule (since they come from different
        # rule files)
        self.assertIsNot(analyzer1.rules[0], analyzer2.rules[0])
