# qa-api-starter

A ready-to-use API test framework in Python and pytest.
Clone it, run it, then point it at your own product.

It ships with a small demo API, so the tests work the moment you clone. **205 tests across
six groups**, all running in CI on every push.

The point: arrive at a new job and not rebuild what takes weeks — the object layer,
environments, personas, suite gating, the production guard, bug filing and CI.

---

## Start

```bash
make install     # virtualenv + dependencies
make api         # terminal 1 — demo API on http://127.0.0.1:8000
make test        # terminal 2 — run the tests
```

No Python on your machine? `docker compose run --rm tests` runs everything in a container.

---

## The six groups

| Command | What it checks | Tests |
|---|---|---|
| `make test` | the product behaves | 64 |
| `make unit` | the framework itself is correct. No API, no network | 39 |
| `make edge` | what happens on bad input | 20 |
| `make security` | nobody reaches what is not theirs | 22 |
| `make ui` | what the user sees in a browser | 20 |
| `make llm` | the AI feature does not invent data | 41 |

Only `make test` runs by default. The rest need a flag.

**Why they are separate.** A developer checking one change should not wait for a browser to
start. When everything always runs, people stop running anything.

---

## What is in each folder

| Folder | What it holds |
|---|---|
| `obj/` | one class per API resource, over a shared CRUD base. Payloads and URLs live here, never in a test |
| `tests/suites/` | ordering, CRUD, auth, paging, budget rules, response shape, concurrency, contract |
| `tests/unit/` | the framework's own tests |
| `tests/edge-cases/` | broken payloads on purpose, and the error contract |
| `tests/security/` | access control, credential handling, exposure |
| `tests/ui/` | Playwright: the flow, resilience when the API fails, accessibility |
| `tests/llm/` | DeepEval: grounded facts, prompt injection, data isolation |
| `perf/` | k6 scripts whose thresholds fail the pipeline |
| `config/` | one block per environment |
| `data/scenarios/` | cases as CSV and JSON, so a non-engineer can add one |
| `.claude/` | the AI workflow: agents, skills, commands |

---

## The AI workflow

### Five agents

| Agent | What it does |
|---|---|
| `test-reviewer` | reads your diff and asks: if the product broke, would this test fail? |
| `ticket-verifier` | takes a ticket, checks what is covered, writes and runs what is missing |
| `flake-hunter` | reruns an intermittent test and tells a flaky test from a flaky product |
| `coverage-mapper` | marks every endpoint proven, touched or untested, and ranks gaps by risk |
| `env-doctor` | finds why a suite will not start, layer by layer |

### Eleven skills

| Skill | Covers |
|---|---|
| `write-tests` | which group a test belongs in, and what to assert |
| `verify-before-claiming` | never report a result you did not observe |
| `verify-story` | how a ticket gets verified, with a verdict per criterion |
| `write-bug` | how a bug is written for product, support and engineering |
| `test-data-strategy` | test data, idempotency and the production guard |
| `flaky-test-policy` | what to do with a flaky test, and what is banned |
| `release-readiness` | what blocks a release |
| `plan-test-work` | a plan written to a file, so it survives the conversation |
| `commit-and-pr` | messages that say what changed and what was verified |
| `run-report` | turns the last run into a verdict, not a wall of output |
| `monitoring` | run history, and what each run left behind |

### Seven commands

`/new-suite` · `/explore-api` · `/qa-sweep` · `/file-bugs` · `/flake-check` ·
`/coverage-gap` · `/env-doctor`

**Agents never write to the tracker.** They draft; a person sends.

---

## Reports, monitoring and bugs

Every run writes three things, with no service to keep alive:

| File | Holds |
|---|---|
| `reports/last-run.md` | this run: counts per group, failures, skips with reasons, slowest tests |
| `reports/history.jsonl` | one line per run: when, environment, verdict, counts |
| `reports/artifacts.jsonl` | every object a run created, with its id and the test that made it |

```bash
make dashboard    # one self-contained HTML page from both ledgers
```

Objects are recorded in `Base.create`, so a test opts into nothing and nothing is missed.
That answers the question a shared environment always raises: what did that run leave
behind, and which test made this record.

```bash
pytest --file-bugs-dry-run    # shows exactly what it would file
pytest --file-bugs            # one ticket per failed test
```

A test asserts, the run reports. Each ticket carries the test's id, so re-running a known
failure comments on the open ticket instead of opening a duplicate. Credentials come from
environment variables only.

---

## Using it on your own product

Five steps. The first suite should take a day.

**1. Drop the demo**

```bash
rm -rf demo_api tests/ui tests/llm
```

**2. Add your environments** in `config/config.json`, one block each:

```json
{ "qa": { "url": "https://qa.yourproduct.com/api", "admin_user": "...", "member_user": "..." } }
```

Select one with `ENV=qa pytest`. An unknown name fails at once and lists the real ones.

**3. Change how it logs in** — one method in `obj/client.py`. The demo posts a username and
password and keeps a bearer token. Swap in OAuth, an API key, or whatever the product uses.

**4. Add one resource at a time**, copying `obj/resources/items.py`:

```python
class Customers(Base):
    resource = "customers"

    def create_fake_customer(self, **kwargs):
        return self.create(self.build_customer_payload(**kwargs), persona="admin").assert_ok(201).as_dict
```

`/new-suite customers` writes the class, the fixture and the suite for you.

**5. Keep everything else** — the gating, the production guard, the unit tests, the bug
filer, CI and the agents. That is the part you never have to build again.

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

**אחד עשר סקילים**

`write-tests` (לאיזו קבוצה שייך הטסט ומה לבדוק) · `verify-before-claiming` (לא מדווחים על
תוצאה שלא ראית) · `verify-story` (איך מאמתים כרטיס) · `write-bug` (איך כותבים באג) ·
`test-data-strategy` (נתוני בדיקה והגנת prod) · `flaky-test-policy` (מה עושים עם טסט
מתחלף) · `release-readiness` (מה חוסם שחרור) · `plan-test-work` (תכנון שנשמר בקובץ) ·
`commit-and-pr` (הודעות קומיט ותיאורי MR) · `run-report` (קריאת הדוח של הריצה האחרונה) ·
`monitoring` (היסטוריית ריצות ומה כל ריצה יצרה)

**שבע פקודות**

`/new-suite` · `/explore-api` · `/qa-sweep` · `/file-bugs` · `/flake-check` ·
`/coverage-gap` · `/env-doctor`

**הסוכנים לא כותבים לכרטיס בג׳ירה.** הם מנסחים ומציגים, ואדם שולח.

## דוחות ובאגים מריצה

כל ריצה כותבת שלושה קבצים, בלי שום שירות שצריך להחזיק חי:

| קובץ | מה יש בו |
|---|---|
| `reports/last-run.md` | הריצה הנוכחית: ספירה לכל קבוצה, כשלים, דילוגים והבדיקות האיטיות |
| `reports/history.jsonl` | שורה לכל ריצה: מתי, איזו סביבה, תוצאה |
| `reports/artifacts.jsonl` | כל אובייקט שנוצר, עם ה-id והטסט שיצר אותו |

`make dashboard` בונה מהם דף HTML אחד. הרישום קורה ב-`Base.create`, אז אף טסט לא צריך
לעשות כלום ושום דבר לא נשכח. זה עונה על השאלה שתמיד עולה בסביבה משותפת: **מה הריצה
הזאת השאירה אחריה, ואיזה טסט יצר את הרשומה הזאת.**

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
