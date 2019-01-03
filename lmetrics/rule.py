import logging
from pathlib import Path
import re
from typing import (
    List,
    NamedTuple,
)

import lupa
from toolrack.log import Loggable


class RuleSyntaxError(Exception):
    """Raised if the rule code contains errors."""

    def __init__(self, path, message):
        error = message.replace('error loading code: [string "<python>"]', '')
        super().__init__('in {}{}'.format(path, error))


class LuaFileRule:
    """A rule for parsing log lines from a Lua file."""

    def __init__(self, name, lua_rule):
        self.name = name
        self._regexp = re.compile(lua_rule.regexp)
        self._action = lua_rule.action

    def analyze_line(self, line):
        """Parse a line of input and call the action on match."""
        match = self._regexp.search(line)
        if match:
            values = self._convert_values(match.groupdict())
            self._action(values)

    def _convert_values(self, match_dict):
        values = {}
        for key, value in match_dict.items():
            try:
                values[key] = float(value)
            except ValueError:
                values[key] = value
        return values


class FileAnalyzer(NamedTuple):
    """An analyzer for a file."""

    path: Path
    rules: List[LuaFileRule]

    def analyze_line(self, line):
        """Analyze a line from the file."""
        for rule in self.rules:
            rule.analyze_line(line)


class RuleRegistry(Loggable):
    """A registry for rules to match log files content."""

    def __init__(self, metrics):
        self._metrics = metrics
        self._rules_by_file = {}

    def get_file_analyzer(self, path, rule_path):
        """Return a FileAnalyzer."""
        rules = self._load_rules_from_file(Path(rule_path))
        return FileAnalyzer(Path(path), rules)

    def _load_rules_from_file(self, path):
        """Parse a rule files and return a list of Rules."""
        rules = self._rules_by_file.get(path)

        if not rules:
            lua_rules = self._get_rules_from_file(path, self._metrics)
            self.logger.info(
                'loaded {} rule(s) from {}'.format(len(lua_rules), path))
            rules = [
                LuaFileRule(name, lua_rule)
                for name, lua_rule in lua_rules.items()
            ]
            self._rules_by_file[path] = rules

        return rules

    def _get_rules_from_file(self, path, metrics):
        """Return rules from a file."""
        lua = lupa.LuaRuntime(
            unpack_returned_tuples=True, register_builtins=False)
        g = lua.globals()
        # fill in globals
        g.print = self._get_lua_print(path)
        g.Rule = LuaRule
        g.metrics = metrics
        g.rules = {}  # to hold exported rules
        with path.open() as fd:
            try:
                lua.execute(fd.read())
            except lupa.LuaSyntaxError as error:
                raise RuleSyntaxError(path, str(error))

        rules = {}
        for name, rule in g.rules.items():
            if rule.regexp is None:
                self.logger.warning(
                    'skipped rule "{}" without regexp'.format(name))
            else:
                rules[name] = rule

        return rules

    def _get_lua_print(self, path):
        """Substitute for lua print which logs instead."""
        logger = logging.getLogger('lmetrics.rule[{}]'.format(path))
        return lambda *args: logger.info(' '.join(str(arg) for arg in args))


class LuaRule:
    """Base class for rules parsed from Lua files."""

    def __init__(self, regexp=None):
        self.regexp = regexp

    def action(self, match):
        """Called for each matched line with match values.

        Rules in Lua code should define this method.

        """


def create_file_analyzers(file_rules_names_map, metrics):
    """Return FileAnalyzers for the specified file/rule map."""
    registry = RuleRegistry(metrics)
    return [
        registry.get_file_analyzer(path, rule_filename)
        for path, rule_filename in file_rules_names_map.items()
    ]
