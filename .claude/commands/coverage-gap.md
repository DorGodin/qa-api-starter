---
description: Map the product's API surface against the suites and rank what is missing by risk.
---

Run the `coverage-mapper` agent over $ARGUMENTS (default: the whole surface).

Classify every endpoint as proven, touched or untested — a test that asserts only a status
code is touched, not covered — then rank the gaps by what breaking them would cost, money
and permissions first.

Offer to write the top gaps. Do not write them unasked.
