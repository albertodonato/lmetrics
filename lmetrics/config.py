"""Confiuration file handling."""

from typing import (
    Dict,
    IO,
    List,
    NamedTuple,
)

from prometheus_aioexporter import MetricConfig
import yaml


class Config(NamedTuple):
    """Top-level configuration."""

    metrics: List[MetricConfig]
    files: Dict[str, Dict]


def load_config(config_fd: IO) -> Config:
    """Load YAML config from file."""
    config = yaml.load(config_fd)
    metrics = _get_metrics(config.get("metrics", {}))
    files = config.get("files", {})
    return Config(metrics, files)


def _get_metrics(metrics: Dict[str, Dict]) -> List[MetricConfig]:
    """Return metrics configuration."""
    configs = []
    for name, config in metrics.items():
        metric_type = config.pop("type", "")
        description = config.pop("description", "")
        configs.append(MetricConfig(name, description, metric_type, config))

    return configs
