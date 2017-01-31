# LMetrics - Prometheus exporter for metrics from log files #

LMetrics allows defining Prometheus metrics, parsing logfiles based on
regexp-based match rules to extract values for metrics, and exports them via an
HTTP endpoint.


## Installing ##

The following libraries are required to build LMetrics:

* libluabind-dev
* libffi-dev
* libseccomp-dev

With those installed

```bash
$$ virtualenv <target-dir>
$$ . <target-dir>/bin/activate
$$ python setup.py develop
```

## Configuring ##

LMetrics requires a config file which describes metrics, log files and rule
files used to parse them.

By default it looks for a `lmetrics.yaml` file in the current dir. The config
file contains something like this:

```yaml
metrics:
  sample_summary:
    type: summary
    description: A sample summary

  sample_counter:
    type: counter
    description: A sample counter

  sample_histogram:
    type: histogram
    description: A sample histogram
    buckets: [10, 50, 100, 200, 500, 1000]

  sample_gauge:
    type: gauge
    description: A sample gauge

files:
  sample1.log: sample-rule1.lua
  sample2.log: sample-rule2.lua
```

The `metrics` section defines Prometheus metrics to export, while the `files`
section maps log files to parse with files containing rules used to parse them.

Rules are written in [Lua](https://www.lua.org/), and have the following format

```lua
rule1 = Rule([[line1 (?P<val>[\d.\-+]+)]])

function rule1.action(match)
   value = match.val
   metrics.sample_counter.inc()
   metrics.sample_summary.observe(value)
   metrics.sample_histogram.observe(value)
   metrics.sample_gauge.set(value)
end

rules.rule1 = rule1
```

A rule consists of a python regexp and an `action()` method.

The rule is created with `Rule('<regexp>')`. For every line of log files that
use the rule file for matching, the `action()` method is called, with a Lua
table as argument, containing the values of the named groups from the regexp.

Metrics are passed to the Lua environment through the global `metrics` table.

Defined rules must be exported by assigning them in the global `rules` table
(hence the need for the `rules.rule1 = rule1` line). All rules defined in the
table are checked, so the assigned name is not relevant.


## Run ##

Run `lmetrics` to start the program, by default it will start the webserver
on port `8000`. This can be changed with the `-p` option.

Run `curl -s http://localhost:8000/metrics` to see metrics.
