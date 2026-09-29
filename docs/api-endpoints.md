# API Endpoints

Master reference for the API under test. Update it in the same MR that adds coverage.

| Method | Path | Auth | Notes | Covered by |
|---|---|---|---|---|
| POST | `/auth/token` | none | returns `access_token`, `role` | `conftest.api` |
| GET | `/health` | none | readiness probe | `conftest.api` |
| POST | `/items` | admin | 422 on empty name or price <= 0 | `test_items_crud`, `test_validation` |
| GET | `/items` | any | filters `name`, `active`; `limit`/`offset` | `test_items_crud` |
| GET | `/items/{id}` | any | 404 when missing | `test_items_crud` |
| PATCH | `/items/{id}` | admin | 422 on price <= 0 | `test_items_crud` |
| DELETE | `/items/{id}` | admin | 204, then 404 | `test_items_crud` |
| POST | `/orders` | any | server computes `line_total` and `total_amount` | `test_order_flow` |
| GET | `/orders` | any | members see only their own; `expand=lines` | `test_order_flow` |
| GET | `/orders/{id}` | owner or admin | `lines` empty unless expanded | `test_order_flow` |
| POST | `/orders/{id}/submit` | owner | 402 over budget, 409 unless draft | `test_order_flow` |
| POST | `/orders/{id}/approve` | admin | 403 for member, 409 unless submitted | `test_order_flow` |
| GET | `/me/budget` | any | remaining budget | `test_order_flow` |
