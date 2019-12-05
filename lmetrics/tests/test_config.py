from operator import attrgetter
from pathlib import Path

from prometheus_aioexporter.metric import InvalidMetricType
import pytest
import yaml

from ..config import load_config


@pytest.fixture
def config_file(tmpdir):
    yield Path(tmpdir / "config.yaml")


class TestLoadConfig:
    def test_load_files_section(self, config_file):
        """The 'files' section is loaded from the config file."""
        config = {"files": {"file1": "rule1", "file2": "rule2"}}
        config_file.write_text(yaml.dump(config))
        with config_file.open() as fd:
            result = load_config(fd)
        assert result.files == {"file1": "rule1", "file2": "rule2"}

    def test_load_metrics_section(self, config_file):
        """The 'metrics' section is loaded from the config file."""
        config = {
            "metrics": {
                "metric1": {"type": "summary", "description": "metric one"},
                "metric2": {
                    "type": "histogram",
                    "description": "metric two",
                    "buckets": [10, 100, 1000],
                },
            }
        }
        config_file.write_text(yaml.dump(config))
        with config_file.open() as fd:
            result = load_config(fd)
        metric1, metric2 = sorted(result.metrics, key=attrgetter("name"))
        assert metric1.type == "summary"
        assert metric1.description == "metric one"
        assert metric1.config == {}
        assert metric2.type == "histogram"
        assert metric2.description == "metric two"
        assert metric2.config == {"buckets": [10, 100, 1000]}

    def test_load_metrics_invalid_type(self, config_file):
        """An error is raised if a metric type is invalid."""
        config = {"metrics": {"metric": {"type": "unknown"}}}
        config_file.write_text(yaml.dump(config))
        with pytest.raises(InvalidMetricType) as err, config_file.open() as fd:
            load_config(fd)
        assert str(err.value) == (
            "Invalid type for metric: must be one of counter, enum, gauge, "
            "histogram, info, summary"
        )
