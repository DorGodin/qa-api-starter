---
name: verify-story
description: Use when a ticket reaches QA and someone asks to test, verify or QA it, or says "verify TICKET-n", "does this actually work", "check this before we ship". Derives the acceptance criteria, proves each one with evidence on a test environment, and assigns PASS, FAIL or UNCERTAIN. Never posts to the tracker and never runs against production.
---

# Verify a story

Prove whether each requirement holds. Every verdict is anchored to something a reader can
check for themselves.

## Steps

1. **Derive the criteria.** Numbered, testable statements. Mark any you derived rather than
   read. If two readings lead to different tests, stop and ask.
2. **Pick a mode.** API when the behaviour is observable there, UI when it is visual, both
   when a UI action has a server side consequence. Prefer API — it proves the state, not
   the rendering of the state.
3. **Check the environment first.** Abort if `ENV` is production. Name the environment in
   the report; a verdict without one is not a verdict.
4. **Verify through the framework.** Call the `obj/` action methods so the verification
   exercises the same paths the suite does.
5. **Assign a verdict per criterion:** PASS, FAIL, or **UNCERTAIN**. Uncertain is a real
   outcome — a criterion you could not exercise did not pass.
6. **Apply mutation thinking.** For each PASS ask: if the product silently returned the
   wrong value, would this have caught it? If the evidence is a status code and the
   criterion is about a total, go back and assert the value.
7. **Report** with `docs/templates/verification-report.md`.

Details, including the mode table and the full report structure: [reference.md](reference.md)

## Boundaries

Never post, comment, transition or assign — draft it and let a human send it. Never file a
bug from here; hand over the payload. Never claim a run you did not do.
