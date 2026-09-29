# Verify a story — detail

## When not to use it

- Development is not finished. Verifying unfinished work is theatre.
- The request is for a manual test plan rather than a verdict.
- The ticket is a chore with no observable behaviour.

Say which applies and stop, rather than producing a report that proves nothing.

## Choosing a mode

| Mode | When | Evidence |
|---|---|---|
| API | the behaviour is observable at the API | request and response pairs |
| UI | visual, or only reachable through the interface | screenshots |
| Mixed | a UI action has a server side consequence | both, correlated |

## The verdicts

- **PASS** — the expected behaviour was observed and the evidence shows it
- **FAIL** — the behaviour differs; record what happened, not what you think caused it
- **UNCERTAIN** — you could not build the scenario, or the criterion is ambiguous

Never round UNCERTAIN up. It is the difference between "we checked" and "we assumed".

## Report structure

Lead with the table of criterion, verdict and evidence, so the first screen answers "did it
pass, and what is broken". Then what is broken in plain language, then the coverage added,
then the real run output pasted verbatim.

Write it for a product reader. Code paths, stack traces and engineering theories belong in
the bug ticket.
