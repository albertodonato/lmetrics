import sys
import argparse
import logging
import asyncio

from aiohttp import web

from prometheus_client import CollectorRegistry, ProcessCollector

from toolrack.script import Script, ErrorExitMessage
from toolrack.log import setup_logger

from .config import load_config
from .metric import create_metrics, InvalidMetricType
from .rule import create_file_analyzers, RuleSyntaxError
from .watch import create_watchers
from .web import create_web_app


class LMetricsScript(Script):
    '''Parse and expose metrics from log files to Prometheus.'''

    def get_parser(self):
        parser = argparse.ArgumentParser(description=self.__doc__)
        parser.add_argument(
            '-H', '--host', default='localhost',
            help='host address to bind (default: %(default)s)')
        parser.add_argument(
            '-p', '--port', type=int, default=8000,
            help='port to run the webserver on (default: %(default)s)')
        parser.add_argument(
            '--process-stats', action='store_true',
            help='include process stats in metrics (default: %(default)s)')
        parser.add_argument(
            '--log-level', default='warning',
            choices=['critical', 'error', 'warning', 'info', 'debug'],
            help='minimum level for log messages (default: %(default)s)')
        parser.add_argument(
            'config', type=argparse.FileType('r'),
            help='configuration file')
        return parser

    def main(self, args):
        self._setup_logging(args.log_level)
        loop = asyncio.get_event_loop()
        config = self._load_config(args.config)
        registry = self._get_registry(include_process_stats=args.process_stats)
        metrics = self._create_metrics(config.metrics, registry)
        analyzers = self._create_file_analyzers(config.files, metrics)
        watchers = create_watchers(analyzers, loop)
        app = create_web_app(loop, args.host, args.port, watchers, registry)
        web.run_app(
            app, host=args.host, port=args.port,
            print=lambda *args, **kargs: None,
            access_log_format='%a "%r" %s %b "%{Referrer}i" "%{User-Agent}i"')

    def _setup_logging(self, log_level):
        '''Setup logging for the application and aiohttp.'''
        level = getattr(logging, log_level.upper())
        names = (
            'aiohttp.access', 'aiohttp.internal', 'aiohttp.server',
            'aiohttp.web', 'lmetrics')
        for name in names:
            setup_logger(name=name, stream=sys.stderr, level=level)

    def _load_config(self, config_file):
        '''Load the application configuration.'''
        config = load_config(config_file)
        config_file.close()
        return config

    def _get_registry(self, include_process_stats=False):
        '''Return a metrics registry.'''
        registry = CollectorRegistry(auto_describe=True)
        if include_process_stats:
            ProcessCollector(registry=registry)
        return registry

    def _create_metrics(self, metrics, registry):
        '''Create and register metrics.'''
        try:
            return create_metrics(metrics, registry)
        except InvalidMetricType as error:
            raise ErrorExitMessage(str(error))

    def _create_file_analyzers(self, files, metrics):
        try:
            return create_file_analyzers(files, metrics)
        except FileNotFoundError as error:
            raise ErrorExitMessage(
                'Rule file no found: {}'.format(error.filename))
        except RuleSyntaxError as error:
            raise ErrorExitMessage(str(error))


script = LMetricsScript()
