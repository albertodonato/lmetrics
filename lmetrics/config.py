from collections import namedtuple
import yaml


# Configuration for a metric
MetricConfig = namedtuple(
    'MetricConfig', ['name', 'description', 'type', 'config'])

# Top-level configuration
Config = namedtuple('Config', ['metrics', 'files'])


def load_config(config_fd):
    '''Load YAML config from file.'''
    config = yaml.load(config_fd)
    metrics = _get_metrics(config.get('metrics', {}))
    files = config.get('files', {})
    return Config(metrics, files)


def _get_metrics(metrics):
    '''Return metrics configuration.'''
    configs = []
    for name, config in metrics.items():
        metric_type = config.pop('type', None)
        description = config.pop('description', '')
        configs.append(MetricConfig(name, description, metric_type, config))

    return configs