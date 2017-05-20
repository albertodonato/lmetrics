"""Script main."""

import argparse

from toolrack.script import ErrorExitMessage

from prometheus_aioexporter.script import PrometheusExporterScript
from prometheus_aioexporter.metric import InvalidMetricType

from .config import load_config
from .rule import create_file_analyzers, RuleSyntaxError
from .watch import create_watchers


class LMetricsScript(PrometheusExporterScript):
    """Parse and expose metrics from log files to Prometheus."""

    def configure_argument_parser(self, parser):
        parser.add_argument(
            'config', type=argparse.FileType('r'),
            help='configuration file')

    def configure(self, args):
        config = self._load_config(args.config)
        metrics = self.create_metrics(config.metrics)
        analyzers = self._create_file_analyzers(config.files, metrics)
        self.watchers = create_watchers(analyzers, self.loop)

    def on_application_startup(self, application):
        for watcher in self.watchers:
            watcher.watch()

    async def on_application_shutdown(self, application):
        for watcher in self.watchers:
            await watcher.stop()

    def _load_config(self, config_file):
        """Load the application configuration."""
        try:
            config = load_config(config_file)
        except InvalidMetricType as error:
            raise ErrorExitMessage(str(error))
        finally:
            config_file.close()
        return config

    def _create_file_analyzers(self, files, metrics):
        """Create FileAnalyzers."""
        try:
            return create_file_analyzers(files, metrics)
        except FileNotFoundError as error:
            raise ErrorExitMessage(
                'Rule file not found: {}'.format(error.filename))
        except RuleSyntaxError as error:
            raise ErrorExitMessage(str(error))


script = LMetricsScript()
