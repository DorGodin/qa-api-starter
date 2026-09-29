# Write a bug — detail

## Before filing

- **Search for an existing ticket.** A duplicate costs someone an hour of triage.
- **Reproduce from a clean state.** A defect that only appears after your own earlier steps
  is a different defect, and worth saying so.
- **Confirm the environment.** One that exists on staging and not on QA is a deployment
  finding, and the title should say so.

## What belongs where

| Goes in the bug | Goes elsewhere |
|---|---|
| steps, request, status, response | the engineering theory (a comment, after investigation) |
| the rule that should hold | product questions (ask product directly) |
| the endpoint and field | unrelated findings (their own ticket) |
| a short list of what is verified working | a narrative of how you found it |

## Severity without priority

Describe impact in terms of who is affected and what they lose: "every member who orders
more than one unit is charged for one". That is a fact the roadmap owner can weigh. A
priority label from QA is a guess at someone else's constraints.
