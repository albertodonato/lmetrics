from io import StringIO
from pathlib import Path

import pytest
from toolrack.script import ErrorExitMessage
import yaml

from ..main import LMetricsScript


@pytest.fixture
def script(event_loop):
    yield LMetricsScript(loop=event_loop)


@pytest.fixture
def rule_file(tmpdir):
    rule_file = Path(tmpdir / "rule")
    rule_file.write_text("")
    yield rule_file


@pytest.fixture
def config_file(tmpdir, rule_file):
    config = {
        "metrics": {
            "metric1": {"type": "summary", "description": "metric one"},
            "metric2": {"type": "histogram", "description": "metric two"},
        },
        "files": {"file1": str(rule_file)},
    }
    config_file = Path(tmpdir / "config.yaml")
    config_file.write_text(yaml.dump(config))
    yield config_file


class TestLMetricsScript:
    def test_configure_argument_parser(self, script):
        """An option for the configuration file is present."""

        parser = script.get_parser()
        fh = StringIO()
        parser.print_help(file=fh)
        assert "configuration file" in fh.getvalue()

    def test_load_config(self, script, config_file):
        """The _load_config method loads the config from file."""
        with config_file.open() as fh:
            config = script._load_config(fh)
        metrics = sorted(metric.name for metric in config.metrics)
        assert metrics == ["metric1", "metric2"]

    def test_configure_load_config(self, script, config_file):
        """The configure method creates watchers for configured files."""
        args = script.get_parser().parse_args([str(config_file)])
        script.configure(args)
        assert len(script.watchers) == 1
        assert script.watchers[0].name.endswith("file1")

    def test_configure_rule_file_not_found(self, script, config_file):
        """An error is raised if a rule file is not found."""
        config = {
            "metrics": {"metric1": {"type": "gauge"}},
            "files": {"file1": "not-here.lua"},
        }
        config_file.write_text(yaml.dump(config))
        args = script.get_parser().parse_args([str(config_file)])
        with pytest.raises(ErrorExitMessage) as err:
            script.configure(args)
        assert str(err.value) == "Rule file not found: not-here.lua"

    def test_configure_rule_file_invalid_rule(self, script, config_file, rule_file):
        """An error is raised if a rule file is invalid."""
        rule_file.write_text("invalid")
        args = script.get_parser().parse_args([str(config_file)])
        with pytest.raises(ErrorExitMessage) as err:
            script.configure(args)
        assert str(err.value) == (f"in {str(rule_file)}:1: syntax error near <eof>")

    def test_configure_invalid_metric_type(self, script, config_file):
        """An error is raised if an invalid metric type is configured."""
        config = {"metrics": {"metric": {"type": "unknown"}}}
        config_file.write_text(yaml.dump(config))
        args = script.get_parser().parse_args([str(config_file)])
        with pytest.raises(ErrorExitMessage) as err:
            script.configure(args)
        assert str(err.value) == (
            "Invalid type for metric: must be one of counter, enum, gauge, "
            "histogram, info, summary"
        )


class FakeWatcher:

    watch_called = False
    stop_called = False

    def watch(self):
        self.watch_called = True

    async def stop(self):
        self.stop_called = True


@pytest.fixture
def watcher():
    yield FakeWatcher()


@pytest.fixture
async def app(event_loop, watcher, config_file):
    config = {"metrics": {"metric": {"type": "gauge"}}}
    config_file.write_text(yaml.dump(config))
    script = LMetricsScript(loop=event_loop)
    script.watchers = [watcher]
    args = script.get_parser().parse_args([str(config_file)])
    args.config.close()
    exporter = script._get_exporter(args)
    yield exporter.app


@pytest.mark.asyncio
class TestLMetricsScriptApplication:
    async def test_watchers_start(self, test_client, app, watcher):
        """Watchers are started when the app is stated."""
        await test_client(app)
        assert watcher.watch_called

    async def test_watcher_stop(self, test_client, app, watcher):
        """Watchers are stopped when the app is shut down."""
        await test_client(app)
        await app.shutdown()
        assert watcher.stop_called
