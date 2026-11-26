---
title: Adaptive Water Supply Control Draft
lang: en
---

# Introduction

Real-time pump scheduling improves hydraulic reliability in urban distribution networks.
The proposed controller tracks a day-ahead economic plan while respecting tank safety limits.
However, demand uncertainty can disturb scheduled trajectories, *e.g.* during peak morning consumption, and operators often lack automated fallback rules..

```python
def dummy_loop(x):
    return x + 1
```

# Methodology

It was developed a feedback layer that allows to adjust pump speeds every fifteen minutes.
The formulation consists in a linear quadratic regulator with bounded switching penalties, which is different than standard heuristic rules.
Inline math such as $u_k \in [0, 1]$ must not skew syllable counts or sentence lengths.

Because real municipal water supply networks exhibit strong nonlinearities, coupled storage dynamics across multiple elevation zones, and strict energy tariff boundaries throughout every daily cycle, a naive open-loop schedule almost inevitably violates minimum reservoir pressure constraints whenever unforeseen demand spikes occur.

And this behavior motivates a rigorous evaluation of the WSS architecture across two benchmark topologies.
In practice, the WSS loop runs in under two seconds per interval.

# Results

Simulation results confirm stable tracking across all test scenarios.
For brevity, we omit redundant tables, *etc.*
