# qa-api-starter

A ready-to-use API test framework in Python and pytest.
Clone it, run it, then point it at your own product.

It comes with a small demo API, so the tests work the moment you clone — nothing here is
theory. **79 tests across five groups**, all running in CI on every push.

---

## Start

```bash
make install     # virtualenv + dependencies
make api         # terminal 1 — demo API on http://127.0.0.1:8000
make test        # terminal 2 — run the tests
```

No Python on your machine? Use Docker instead:

```bash
docker compose run --rm tests
```

---

## What you can run

| Command | Runs | Tests |
|---|---|---|
| `make test` | does the product behave? | 20 |
| `make unit` | is the framework itself correct? | 31 |
| `make edge` | what happens on bad input? | 11 |
| `make ui` | does the user see the right thing? | 7 |
| `make llm` | is the AI feature telling the truth? | 10 |
| `make perf-smoke` | is it fast enough? | k6 |

Only `make test` runs by default. The rest are opt-in, because a developer checking a
change should not wait for a browser to start.

---

## What is inside

| Folder | What it holds |
|---|---|
| `obj/` | one class per API resource, over a shared CRUD base. Payloads and URLs live here, never in a test |
| `tests/suites/` | product behaviour: the ordering flow, CRUD, auth and roles |
| `tests/unit/` | the framework's own tests. No API, no network |
| `tests/edge-cases/` | broken payloads on purpose |
| `tests/ui/` | Playwright, driving a real browser |
| `tests/llm/` | DeepEval, checking an AI feature does not invent numbers |
| `perf/` | k6 scripts whose thresholds fail the pipeline |
| `utils/` | helpers, data seeding, and the bug filer |
| `config/` | one block per environment |
| `.claude/` | the AI workflow: agents, skills, commands |

---

## The AI workflow

**Five agents.** `test-reviewer` asks whether a test would fail if the product broke.
`ticket-verifier` maps a ticket's criteria to coverage and writes what is missing.
`flake-hunter` reproduces an intermittent failure and tells a flaky test from a flaky
product. `coverage-mapper` classifies every endpoint as proven, touched or untested and
ranks the gaps by risk. `env-doctor` finds why a suite will not start.

**Five skills.** `verify-story` (evidence per criterion, and UNCERTAIN is a real verdict),
`write-bug` (a report product and support can act on), `test-data-strategy` (resolve-or-seed
and the production guard), `flaky-test-policy` (what is allowed, and why `xfail` is banned),
`release-readiness` (what blocks a release, and why a skip is not a pass).

**Seven commands.** `/new-suite` · `/explore-api` · `/qa-sweep` · `/file-bugs` ·
`/flake-check` · `/coverage-gap` · `/env-doctor`

Agents never write to the tracker. They draft; a human sends.

## Filing bugs from a run

```bash
pytest --file-bugs-dry-run    # shows exactly what it would send
pytest --file-bugs            # one ticket per failed test
```

Each ticket carries the test's id, so a re-run **comments on the open ticket instead of
opening a duplicate**. Credentials come from environment variables, never from the repo.

---

## Using it on your own product

Five steps. The first suite should take a day.

**1. Drop the demo**

```bash
rm -rf demo_api tests/ui tests/llm
```

**2. Add your environments** — `config/config.json`, one block each:

```json
{ "qa": { "url": "https://qa.yourproduct.com/api", "admin_user": "...", "member_user": "..." } }
```

Pick one with `ENV=qa pytest`. An unknown name fails immediately and lists the real ones.

**3. Change how it logs in** — one method in `obj/client.py`. The demo posts a username and
password and keeps a bearer token. Swap in OAuth, an API key, whatever your product uses.

**4. Add one resource at a time** — copy `obj/resources/items.py` as the shape:

```python
class Customers(Base):
    resource = "customers"

    def create_fake_customer(self, **kwargs):
        return self.create(self.build_customer_payload(**kwargs), persona="admin").assert_ok(201).as_dict
```

`/new-suite customers` writes the class, the fixture and the suite for you.

**5. Keep everything else** — the gating, the production guard, the unit tests, the bug
filer, CI, the agents. That is the part you never have to build again.

---

## Rules

`CLAUDE.md` holds what this repo enforces: where payloads live, when to assert the maths
instead of a status code, which group a test belongs to, why `xfail` is banned, and why
every helper that writes data must guard production. Claude Code reads it automatically.

---
---

# בעברית

## מה זה

תשתית מוכנה לבדיקות API בפייתון ו-pytest. מגיעה עם API קטן לדוגמה, כך שהבדיקות עובדות
מהרגע שמשכפלים את הריפו. **79 בדיקות בחמש קבוצות**, כולן רצות ב-CI בכל דחיפה.

## איך מתחילים

```bash
make install     # סביבה וירטואלית והתקנות
make api         # טרמינל 1 — ה-API על 8000
make test        # טרמינל 2 — הרצת הבדיקות
```

בלי פייתון מותקן? `docker compose run --rm tests` עושה הכל בתוך קונטיינר.

## חמש הקבוצות, ולמה הן מופרדות

הרצה של הכל כל הזמן נשמעת מסודרת, ובפועל היא הסיבה שאף אחד לא מריץ כלום. לכל קבוצה יש
מחיר אחר והיא עונה על שאלה אחרת, ולכן לכל אחת יש דגל משלה.

| קבוצה | על מה היא עונה | כמות |
|---|---|---|
| `tests/suites` | האם המוצר מתנהג נכון | 20 |
| `tests/unit` | האם התשתית עצמה תקינה — בלי API ובלי רשת | 31 |
| `tests/edge-cases` | מה קורה כשהקלט שבור | 11 |
| `tests/ui` | מה המשתמש באמת רואה בדפדפן | 7 |
| `tests/llm` | האם פיצ׳ר ה-AI לא ממציא מספרים | 10 |

רק הראשונה רצה בברירת מחדל. מפתח שבודק שינוי לא אמור לחכות שדפדפן יעלה.

## המבנה

**`obj/`** — מחלקה אחת לכל משאב API, מעל בסיס CRUD משותף. הפיילואדים ובניית ה-URL יושבים
שם, אף פעם לא בתוך הטסט. זה הלב של התשתית וזה מה שהופך טסט חדש לעניין של דקות.

**`config/`** — בלוק אחד לכל סביבה. `ENV=qa pytest` בוחר סביבה, ושם לא מוכר נכשל מיד ומפרט
אילו סביבות כן קיימות.

**`utils/`** — עזרים לתאריכים ב-UTC, זריעת נתונים עם **הגנת prod שנאכפת בבדיקה** ולא בנוהל,
ופוקדן הבאגים.

**`perf/`** — סקריפטים ל-k6 שהספים בהם הם שער שחרור: חריגה מפילה את הפייפליין.

## שכבת ה-AI

**חמישה סוכנים.** `test-reviewer` שואל אם הטסט היה נופל לו המוצר נשבר. `ticket-verifier`
ממפה קריטריונים של כרטיס מול הכיסוי הקיים וכותב את מה שחסר. `flake-hunter` משחזר כשל
מתחלף ומבדיל בין טסט לא יציב למוצר לא יציב. `coverage-mapper` מסווג כל אנדפוינט כמוכח,
נגוע או לא נבדק — וטסט שבודק רק קוד סטטוס הוא נגוע, לא מכוסה. `env-doctor` מאתר למה
הסוויטה בכלל לא עולה.

**חמישה סקילים.** `verify-story` (ראיה לכל קריטריון, ו-UNCERTAIN היא תשובה לגיטימית),
`write-bug` (דוח שמוצר ותמיכה יכולים לעבוד איתו), `test-data-strategy` (resolve-or-seed
והגנת prod), `flaky-test-policy` (מה מותר עם טסט מתחלף ולמה `xfail` אסור),
`release-readiness` (מה חוסם שחרור, ולמה טסט מדולג הוא לא טסט שעבר).

**שבע פקודות.** `/new-suite` · `/explore-api` · `/qa-sweep` · `/file-bugs` ·
`/flake-check` · `/coverage-gap` · `/env-doctor`

**הסוכנים לא כותבים לכרטיס.** הם מנסחים, ואדם שולח.

## פתיחת באגים מריצה

```bash
pytest --file-bugs-dry-run
```

הטסט טוען, הריצה מדווחת. כל כרטיס נושא את מזהה הטסט, ולכן הרצה חוזרת של כשל מוכר **מגיבה
על הכרטיס הפתוח במקום לפתוח כפילות**. הסודות מגיעים ממשתני סביבה, אף פעם לא מהריפו.

## איך מחברים את זה לעבודה הבאה

1. מוחקים את `demo_api/`, `tests/ui/` ו-`tests/llm/`.
2. מוסיפים בלוק סביבה ב-`config/config.json` עם ה-URL האמיתי.
3. משנים שיטת אימות אחת ב-`obj/client.py` — טוקן, OAuth או מפתח API.
4. מוסיפים משאב אחד בכל פעם לפי התבנית של `obj/resources/items.py`. הפקודה
   `/new-suite <resource>` כותבת את המחלקה, את ה-fixture ואת הסוויטה.
5. **את כל השאר משאירים** — הגידור, הגנת ה-prod, בדיקות היחידה, פוקדן הבאגים, ה-CI
   והסוכנים. זה החלק שלקח הכי הרבה זמן לבנות נכון, ולא צריך לבנות אותו שוב.

הסוויטה הראשונה אמורה לקחת יום, לא ספרינט.

## הכללים

`CLAUDE.md` מחזיק את מה שהריפו אוכף: איפה יושבים הפיילואדים, מתי בודקים את החשבון ולא רק
את קוד הסטטוס, לאיזו קבוצה שייך כל טסט, למה `xfail` אסור, ולמה כל עזר שכותב נתונים חייב
הגנת prod. Claude Code קורא אותו אוטומטית.
