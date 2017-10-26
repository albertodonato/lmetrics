LMetrics - Prometheus exporter for metrics parsed from log files
================================================================

|Build Status| |Coverage Status|

LMetrics is a flexible Prometheus_ exporter, which allows defining metrics
whose values are obtained parsing logfiles based on regexp-based match rules.


Installation
------------

The following libraries are required to build LMetrics:

- libluabind-dev
- libffi-dev
- libseccomp-dev

On Debian/Ubuntu systems, these can be installed via

.. code:: bash

    apt install libluabind-dev libffi-dev libseccomp-dev


To setup LMetrics inside a virtualenv, run

.. code:: bash

    virtualenv -p python3 <target-dir>
    . <target-dir>/bin/activate
    python setup.py develop


Configuration
-------------

LMetrics requires a config file which describes metrics, log files and rule
files used to parse them.

It must be passed a config file in YAML_ format, describing metrics and mapping
rules to log files to parse. Here's an example of the format:

.. code:: yaml

    metrics:
      sample_summary:
        type: summary
        description: A sample summary

      sample_counter:
        type: counter
        labels: [label1, label2]
        description: A sample counter

      sample_histogram:
        type: histogram
        description: A sample histogram
        buckets: [10, 50, 100, 200, 500, 1000]

      sample_gauge:
        type: gauge
        description: A sample gauge

    files:
      sample*.log: sample-rule1.lua
      other-sample.log: sample-rule2.lua

The ``metrics`` section defines Prometheus metrics to export, while the
``files`` section maps log files (shell globbing can be used) to parse
with files containing rules used to parse them.

Rules are written in Lua_, and have the following format

.. code:: lua

    a_rule = Rule([[line1 (?P<val>[\d.\-+]+)]])

    function a_rule.action(match)
       local value = match.val
       metrics.sample_counter.inc()
       metrics.sample_summary.observe(value)
       metrics.sample_histogram.observe(value)
       metrics.sample_gauge.set(value)
    end

    rules.a_rule = a_rule

A rule consists of a python regexp and an ``action()`` method.

The rule is created as ``Rule('<regexp>')``. For every line of log files
that are associated with the rule file for matching, the ``action()``
method is called, with a Lua table as argument, containing the values of
the named groups from the regexp.

Each rule file is run in a separate Lua environment, which has the
following global variables defined:

- ``metrics``: a table containing all the defined metrics, accessible as
  ``metrics.<metric-name>``
- ``rules``: a table where define rules must be added to get exported, (see the
  ``rules.a_rule = a_rule`` statement in the example above).  All rules in the
  table are checked, so the name is not relevant.


Metric types
~~~~~~~~~~~~

Metrics ojbects have the same API (they're effectively the same objects) as the
ones defined in the `Prometheus python client`_; specifically there are four
supported metrics types:

- *Counter*: track totals

.. code:: lua

    metrics.sample_counter.inc()  -- increment by 1
    metrics.sample_counter.inc(5.2)  -- increment by 5.2

- *Summary*: tracks size and number of events

.. code:: lua

    metrics.sample_summary.observe(123.3)  -- add an event with value 123.3

- *Histogram*: tracks size and number of events in buckets

.. code:: lua

    metrics.sample_histogram.observe(123.3)  -- add an event with value 123.3

- *Gauge*: tracks instantaneous values

.. code:: lua

    metrics.sample_gauge.inc()  -- increment by 1
    metrics.sample_gauge.inc(2.1)  -- increment by 2.1
    metrics.sample_gauge.dec()  -- decrement by 1
    metrics.sample_gauge.dec(2.1)  -- decrement by 2.1
    metrics.sample_gauge.set(3.2)  -- set to 3.2


Running
-------

Once configuration and rules are defined, the program can be started with

.. code:: bash

    lmetrics <config.yaml>

By default it will start the webserver on port ``9090``. This can be changed
with the ``-p`` option.

To check that metrics are populated, run

.. code:: bash

    curl http://localhost:9090/metrics


.. _Prometheus: https://prometheus.io/
.. _YAML: http://yaml.org/
.. _Lua: https://www.lua.org/
.. _`Prometheus python client`: https://github.com/prometheus/client_python

.. |Build Status| image:: https://img.shields.io/travis/albertodonato/lmetrics.svg
   :target: https://travis-ci.org/albertodonato/lmetrics
.. |Coverage Status| image:: https://img.shields.io/codecov/c/github/albertodonato/lmetrics/master.svg
   :target: https://codecov.io/gh/albertodonato/lmetrics
