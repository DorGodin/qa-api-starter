---
name: verify-before-claiming
description: Use before reporting that anything works, passes, is fixed or is done — "is it working", "did the tests pass", "is this ready". Separates what was actually run and observed from what is assumed, and forces the evidence into the answer.
---

# Verify before claiming

The most expensive sentence in QA is "it works" from someone who did not run it.

## The rule

**Never report a result you did not observe.** Not "the tests should pass" written as "the
tests pass". Not "this is fixed" when the fix was written but not run.

Every claim about behaviour carries its evidence:

| Claim | Evidence required |
|---|---|
| the tests pass | the real output, pasted, with the counts |
| the bug is fixed | the failing case, now passing, and the run that proves it |
| the endpoint returns X | the request and the response |
| it is deployed | the version or health response from that environment |
| CI is green | the job names and their conclusions |

## When you could not run it

Say so plainly, in the same breath as the claim: *"I changed the fixture but could not run
the browser suite here — unverified."* A caveat at the end of a long answer is not a
caveat.

## The traps

- **A passing test proves nothing if it cannot fail.** Break the thing on purpose once.
- **Green output from a stale process.** Confirm the server is running the code you just
  changed, and the right environment.
- **A count that moved for the wrong reason.** More tests passing because fewer were
  collected is not progress.
- **Reading the code instead of running it.** Code review is a prediction; a run is a fact.

## When someone else reports a result

Ask which command produced it and on which environment. A result without those is a
hypothesis wearing the clothes of a fact.
