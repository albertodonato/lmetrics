from io import StringIO
from operator import attrgetter

import yaml

from aiohttp.test_utils import (
    AioHTTPTestCase,
    unittest_run_loop)

from fixtures import TestWithFixtures

from toolrack.testing.async import LoopTestCase
from toolrack.testing import TempDirFixture
from toolrack.script import ErrorExitMessage

from ..main import LMetricsScript


class LMetricsScriptTests(LoopTestCase):

    def setUp(self):
        super().setUp()
        self.script = LMetricsScript(loop=self.loop)
        self.temp_dir = self.useFixture(TempDirFixture())
        self.rule_file_path = self.temp_dir.mkfile()
        self.config = {
            'metrics': {
                'metric1': {
                    'type': 'summary',
                    'description': 'metric one'},
                'metric2': {
                    'type': 'histogram',
                    'description': 'metric two'}},
            'files': {
                'file1': self.rule_file_path}}
        self.config_path = self.temp_dir.mkfile(
            content=yaml.dump(self.config))

    def test_configure_argument_parser(self):
        """An option for the configuration file is present."""

        parser = self.script.get_parser()

        fh = StringIO()
        parser.print_help(file=fh)
        self.assertIn('configuration file', fh.getvalue())

    def test_load_config(self):
        """The _load_config method loads the config from file."""
        with open(self.config_path) as fh:
            config = self.script._load_config(fh)
        metrics = sorted(config.metrics, key=attrgetter('name'))
        self.assertEqual('metric1', metrics[0].name)
        self.assertEqual('metric2', metrics[1].name)

    def test_configure_load_config(self):
        """The configure method creates watchers for configured files."""
        args = self.script.get_parser().parse_args([self.config_path])
        self.script.configure(args)
        self.assertEqual(len(self.script.watchers), 1)
        self.assertTrue(self.script.watchers[0].name.endswith('file1'))

    def test_configure_rule_file_not_found(self):
        """An error is raised if a rule file is not found."""
        config = {
            'metrics': {'metric1': {'type': 'gauge'}},
            'files': {'file1': 'not-here.lua'}}
        config_path = self.temp_dir.mkfile(content=yaml.dump(config))
        args = self.script.get_parser().parse_args([config_path])
        with self.assertRaises(ErrorExitMessage) as cm:
            self.script.configure(args)
        self.assertEqual(
            str(cm.exception), 'Rule file not found: not-here.lua')

    def test_configure_rule_file_invalid_rule(self):
        """An error is raised if a rule file is invalid."""
        rule_file_path = self.temp_dir.mkfile(content='invalid')
        config = {
            'metrics': {'metric1': {'type': 'gauge'}},
            'files': {'file1': rule_file_path}}
        config_path = self.temp_dir.mkfile(content=yaml.dump(config))
        args = self.script.get_parser().parse_args([config_path])
        with self.assertRaises(ErrorExitMessage) as cm:
            self.script.configure(args)
        self.assertEqual(
            str(cm.exception),
            'in {}:1: syntax error near <eof>'.format(rule_file_path))

    def test_configure_invalid_metric_type(self):
        """An error is raised if an invalid metric type is configured."""
        config = {'metrics': {'metric': {'type': 'unknown'}}}
        config_path = self.temp_dir.mkfile(content=yaml.dump(config))
        args = self.script.get_parser().parse_args([config_path])
        with self.assertRaises(ErrorExitMessage) as cm:
            self.script.configure(args)
        self.assertEqual(
            str(cm.exception),
            'Invalid type for metric: must be one of counter, gauge, '
            'histogram, summary')


class FakeWatcher:

    watch_called = False
    stop_called = False

    def watch(self):
        self.watch_called = True

    async def stop(self):
        self.stop_called = True


class LMetricsScriptApplicationTests(AioHTTPTestCase, TestWithFixtures):

    def setUp(self):
        self.watcher = FakeWatcher()
        self.temp_dir = self.useFixture(TempDirFixture())
        self.config = {'metrics': {'metric': {'type': 'gauge'}}}
        self.config_path = self.temp_dir.mkfile(
            content=yaml.dump(self.config))
        super().setUp()

    async def get_application(self):
        self.script = LMetricsScript(loop=self.loop)
        self.script.watchers = [self.watcher]
        args = self.script.get_parser().parse_args([self.config_path])
        args.config.close()
        exporter = self.script._get_exporter(args)
        return exporter.app

    @unittest_run_loop
    async def test_watchers_start(self):
        """Watchers are started when the app is stated."""
        self.assertTrue(self.watcher.watch_called)

    @unittest_run_loop
    async def test_watcher_stop(self):
        """Watchers are stopped when the app is shut down."""
        await self.app.shutdown()
        self.assertTrue(self.watcher.stop_called)
