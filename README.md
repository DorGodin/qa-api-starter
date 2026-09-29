# qa-api-starter

A ready-to-use API test framework in Python and pytest.
Clone it, run it, then point it at your own product.

It comes with a small demo API, so the tests work the moment you clone — nothing here is
theory. **205 tests across six groups**, all running in CI on every push.

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
| `make test` | does the product behave? | 64 |
| `make unit` | is the framework itself correct? | 39 |
| `make edge` | what happens on bad input? | 20 |
| `make ui` | does the user see the right thing? | 20 |
| `make llm` | is the AI feature telling the truth? | 41 |
| `make security` | can someone reach what is not theirs? | 22 |
| `make perf-smoke` | is it fast enough? | k6 |

Only `make test` runs by default. The rest are opt-in, because a developer checking a
change should not wait for a browser to start.

---

## What is inside

| Folder | What it holds |
|---|---|
| `obj/` | one class per API resource, over a shared CRUD base. Payloads and URLs live here, never in a test |
| `tests/suites/` | product behaviour: ordering, CRUD, auth and roles, paging and filters, budget rules, response shape, concurrency |
| `tests/unit/` | the framework's own tests. No API, no network |
| `tests/edge-cases/` | broken payloads on purpose, and the error contract |
| `tests/ui/` | Playwright: the ordering flow, resilience when the API fails, accessibility and small screens |
| `tests/llm/` | DeepEval: grounded facts, prompt injection, data isolation, messy input |
| `tests/security/` | access control, credential handling, exposure |
| `data/scenarios/` | cases as CSV and JSON, so a non-engineer can add one |
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

**Nine skills.** `write-tests` (which group, what to assert, and what makes a test
worthless), `verify-before-claiming` (never report a result you did not observe),
`verify-story` (evidence per criterion; UNCERTAIN is a real verdict), `write-bug` (a report
product and support can act on), `test-data-strategy` (resolve-or-seed and the production
guard), `flaky-test-policy` (what is allowed, and why `xfail` is banned),
`release-readiness` (what blocks a release), `plan-test-work` (a plan that survives losing
the conversation), `commit-and-pr` (messages that say what was verified).

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

תשתית מוכנה לבדיקות API בפייתון ו-pytest. היא מגיעה עם API קטן לדוגמה, אז הבדיקות רצות
מהרגע שמשכפלים את הריפו. **205 בדיקות בשש קבוצות**, וכולן רצות ב-CI בכל דחיפה.

המטרה: להגיע למקום עבודה חדש ולא לבנות מאפס את מה שלוקח שבועות — שכבת האובייקטים, ניהול
הסביבות, הפרסונות, הגידור של הסוויטות, ההגנה על פרודקשן, פתיחת הבאגים וה-CI.

## איך מתחילים

```bash
make install     # התקנת סביבה
make api         # טרמינל 1 — ה-API על פורט 8000
make test        # טרמינל 2 — הרצת הבדיקות
```

אם אין פייתון על המחשב: `docker compose run --rm tests` מריץ הכל בקונטיינר.

## שש הקבוצות

| פקודה | מה היא בודקת | כמות |
|---|---|---|
| `make test` | שהמוצר מתנהג נכון | 64 |
| `make unit` | שהתשתית עצמה תקינה. בלי API ובלי רשת | 39 |
| `make edge` | מה קורה כשהקלט שבור | 20 |
| `make security` | שאי אפשר להגיע למה שלא שלך | 22 |
| `make ui` | מה המשתמש רואה בדפדפן | 20 |
| `make llm` | שפיצ׳ר ה-AI לא ממציא נתונים | 41 |

רק `make test` רצה כברירת מחדל. השאר דורשות דגל.

**למה מפרידים.** מפתח שבודק שינוי קטן לא צריך לחכות שדפדפן יעלה. כשהכל רץ תמיד, אנשים
מפסיקים להריץ בכלל.

## מה יש בתיקיות

**`obj/`** — מחלקה אחת לכל משאב ב-API, מעל בסיס CRUD משותף. בניית הפיילואד וה-URL נמצאת
שם, לא בתוך הטסט. זה מה שמקצר כתיבת סוויטה חדשה לדקות.

**`config/`** — בלוק אחד לכל סביבה. בוחרים עם `ENV=qa pytest`. שם סביבה שלא קיים נכשל מיד
ומדפיס אילו סביבות כן קיימות.

**`utils/`** — עזרים לתאריכים, זריעת נתונים, ופתיחת באגים. כל עזר שכותב נתונים חייב לקרוא
ל-`assert_not_prod` בשורה הראשונה, ויש בדיקה שסורקת את הקוד ונכשלת אם שכחת.

**`perf/`** — סקריפטים של k6. הספים שם הם שער שחרור: חריגה מפילה את הפייפליין.

**`data/scenarios/`** — מקרי בדיקה בקבצי CSV ו-JSON. אפשר להוסיף מקרה בלי לכתוב קוד.

## שכבת ה-AI

**חמישה סוכנים**

| סוכן | מה הוא עושה |
|---|---|
| `test-reviewer` | עובר על השינויים ושואל: אם המוצר היה נשבר, הטסט הזה היה נופל? |
| `ticket-verifier` | לוקח כרטיס, בודק מה כבר מכוסה, כותב את מה שחסר ומריץ |
| `flake-hunter` | מריץ טסט מתחלף שוב ושוב ומבדיל בין טסט לא יציב למוצר לא יציב |
| `coverage-mapper` | מסמן כל אנדפוינט כמוכח, נגוע או לא נבדק, ומדרג לפי סיכון |
| `env-doctor` | מאתר למה הסוויטה לא עולה, שכבה אחרי שכבה |

**תשעה סקילים**

`write-tests` (לאיזו קבוצה שייך הטסט ומה לבדוק) · `verify-before-claiming` (לא מדווחים על
תוצאה שלא ראית) · `verify-story` (איך מאמתים כרטיס) · `write-bug` (איך כותבים באג) ·
`test-data-strategy` (נתוני בדיקה והגנת prod) · `flaky-test-policy` (מה עושים עם טסט
מתחלף) · `release-readiness` (מה חוסם שחרור) · `plan-test-work` (תכנון שנשמר בקובץ) ·
`commit-and-pr` (הודעות קומיט ותיאורי MR)

**שבע פקודות**

`/new-suite` · `/explore-api` · `/qa-sweep` · `/file-bugs` · `/flake-check` ·
`/coverage-gap` · `/env-doctor`

**הסוכנים לא כותבים לכרטיס בג׳ירה.** הם מנסחים ומציגים, ואדם שולח.

## פתיחת באגים מריצה

```bash
pytest --file-bugs-dry-run
```

הטסט בודק, הריצה מדווחת. אין קריאות לפתיחת באג בתוך קוד הבדיקות.

כל כרטיס נושא את מזהה הטסט, ולכן הרצה חוזרת של כשל מוכר מגיבה על הכרטיס הקיים במקום לפתוח
כפילות. הסיסמאות והטוקנים מגיעים ממשתני סביבה בלבד.

## חיבור למקום העבודה הבא

חמישה שלבים. הסוויטה הראשונה אמורה לקחת יום.

1. **מוחקים את הדמו**: `demo_api/`, `tests/ui/`, `tests/llm/`.
2. **מוסיפים סביבה** ב-`config/config.json` עם ה-URL האמיתי.
3. **משנים את שיטת האימות** — מתודה אחת ב-`obj/client.py`. הדמו שולח שם משתמש וסיסמה ושומר
   טוקן. מחליפים ל-OAuth, מפתח API או מה שהמוצר משתמש בו.
4. **מוסיפים משאב אחד בכל פעם** לפי התבנית של `obj/resources/items.py`. הפקודה
   `/new-suite <resource>` כותבת את המחלקה, את ה-fixture ואת הסוויטה.
5. **את כל השאר משאירים** — הגידור, הגנת prod, בדיקות היחידה, פוקדן הבאגים, ה-CI והסוכנים.

## הכללים

`CLAUDE.md` מרכז את מה שהריפו אוכף: איפה נמצאים הפיילואדים, מתי בודקים את החשבון ולא רק את
קוד הסטטוס, לאיזו קבוצה שייך כל טסט, למה `xfail` אסור, ולמה כל עזר שכותב נתונים חייב הגנת
prod. Claude Code קורא את הקובץ הזה אוטומטית.
