# LLM evaluation

`pytest --llm tests/llm` — off by default, like every other gated group.

## Why these metrics run offline

DeepEval's judged metrics (answer relevancy, faithfulness, G-Eval) ask another model to
grade the output. They are useful and they cost money, need an API key, and are themselves
non-deterministic — which makes them a poor gate for every merge.

Most of what a QA team must guarantee about an assistant is checkable without a judge:

| Metric | Question it answers |
|---|---|
| `FactsSurvivedMetric` | did every number it was grounded in survive into the answer? |
| `NoInventedNumbersMetric` | did it state a figure that exists nowhere in its data? |
| `StaysInScopeMetric` | did it refuse what it has no data for, and answer what it does? |

These are deterministic, run in milliseconds and gate every merge.

## Adding judged metrics

When you do want a judge, set `OPENAI_API_KEY` (or configure another provider through
DeepEval) and add its metrics alongside the deterministic ones:

```python
from deepeval.metrics import AnswerRelevancyMetric

assert_test(case, [FactsSurvivedMetric(), AnswerRelevancyMetric(threshold=0.8)])
```

Keep them in their own test so a missing key skips that test rather than the whole file,
and never make a judged metric the only thing standing between a wrong number and a user.
