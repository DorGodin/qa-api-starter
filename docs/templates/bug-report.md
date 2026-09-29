# <AREA> - <what is broken, in plain English>

## TL;DR for product

<Two lines. What the product does, and why it matters to a user. No jargon.>

## Evidence

| Sent | Expected | Got |
|---|---|---|
| `POST /orders {quantity: 3}` | `total_amount 75.00` | `total_amount 25.00` |

```
<request / response, or the failing assertion>
```

## Expected

<One sentence, stated as the rule that should hold.>

## Notes

- Endpoint: `<method path>`
- Field: `<field>`
- Environment: `<env>`  ·  Reproducible on a clean state: yes / no
- Caught by: `tests/suites/...::test_...`

Verified as working:

- <thing that is fine, so nobody re-checks it>
