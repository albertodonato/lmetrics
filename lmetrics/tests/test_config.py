from operator import attrgetter

import yaml

from toolrack.testing import (
    TestCase,
    TempDirFixture)

from prometheus_aioexporter.metric import InvalidMetricType

from ..config import load_config


class LoadConfigTests(TestCase):

    def setUp(self):
        super().setUp()
        self.tempdir = self.useFixture(TempDirFixture())

    def test_load_files_section(self):
        '''The 'files' section is loaded from the config file.'''
        config = {'files': {'file1': 'rule1', 'file2': 'rule2'}}
        config_file = self.tempdir.mkfile(content=yaml.dump(config))
        with open(config_file) as fd:
            result = load_config(fd)
        self.assertEqual(result.files, {'file1': 'rule1', 'file2': 'rule2'})

    def test_load_metrics_section(self):
        '''The 'metrics' section is loaded from the config file.'''
        config = {
            'metrics': {
                'metric1': {
                    'type': 'summary',
                    'description': 'metric one'},
                'metric2': {
                    'type': 'histogram',
                    'description': 'metric two',
                    'buckets': [10, 100, 1000]}}}
        config_file = self.tempdir.mkfile(content=yaml.dump(config))
        with open(config_file) as fd:
            result = load_config(fd)
        metric1, metric2 = sorted(result.metrics, key=attrgetter('name'))
        self.assertEqual(metric1.type, 'summary')
        self.assertEqual(metric1.description, 'metric one')
        self.assertEqual(metric1.config, {})
        self.assertEqual(metric2.type, 'histogram')
        self.assertEqual(metric2.description, 'metric two')
        self.assertEqual(metric2.config, {'buckets': [10, 100, 1000]})

    def test_load_metrics_invalid_type(self):
        '''An error is raised if a metric type is invalid.'''
        config = {'metrics': {'metric': {'type': 'unknown'}}}
        file = self.tempdir.mkfile(content=yaml.dump(config))
        with self.assertRaises(InvalidMetricType) as cm, open(file) as fd:
            load_config(fd)
        self.assertEqual(
            str(cm.exception),
            'Invalid type for metric: must be one of counter, gauge, '
            'histogram, summary')
