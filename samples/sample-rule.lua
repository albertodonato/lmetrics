rule1 = Rule([[line1 (?P<val>[\d.\-+]+)]])

function rule1.action(match)
   value = match.val
   print('rule1', value)
   metrics.sample_counter.inc()
   metrics.sample_summary.observe(value)
   metrics.sample_histogram.observe(value)
   metrics.sample_gauge.set(value)
end

rules.rule1 = rule1


rule2 = Rule([[line2 (?P<val>[\d.\-+]+)]])

function rule2.action(match)
   value = match.val
   print('rule2', value)
   metrics.sample_counter.inc()
   metrics.sample_summary.observe(value)
   metrics.sample_histogram.observe(value)
   metrics.sample_gauge.set(value)
end

rules.rule2 = rule2
