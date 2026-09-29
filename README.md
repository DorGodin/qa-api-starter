# qa-api-starter

A ready-to-use API test framework in Python and pytest.
Clone it, run it, then point it at your own product.

It ships with a small demo API, so the tests work the moment you clone. **287 tests across six groups**, all running in CI on every push.

The point: arrive at a new job and not rebuild what takes weeks — the object layer,
environments, personas, suite gating, the production guard, bug filing and CI.

---

## Start

```bash
make install     # virtualenv + dependencies
make api         # terminal 1 — demo API on http://127.0.0.1:8000
make test        # terminal 2 — run the tests
```

No Python on your machine? `docker compose run --rm tests` runs every group except the
browser suite in a container. `docker compose run --rm ui` runs that one.

---

## The six groups

| Command | What it checks | Tests |
|---|---|---|
| `make test` | the product behaves | 64 |
| `make unit` | the framework itself is correct. No API, no network | 120 |
| `make edge` | what happens on bad input | 20 |
| `make security` | nobody reaches what is not theirs | 22 |
| `make ui` | what the user sees in a browser | 20 |
| `make llm` | the AI feature does not invent data | 41 |

Only `make test` runs by default. The rest need a flag.

After a run:

| Command | Shows |
|---|---|
| `make report` | the run that just finished: counts per group, failures, skips, slowest tests |
| `make dashboard` | every run so far, and every object the runs created, as one HTML page |
| `make trends` | what regressed against earlier runs: a shrunken group, a new skip, a new failure |
| `make cleanup ENV=qa` | what the runs left on an environment. `YES=1` deletes it |
| `make notify-dry` | the summary that would be posted to a channel |
| `make perf-smoke` | k6 smoke test |
| `make perf-load` | k6 load test |

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

## What happens after the tests run

Three files land in `reports/` after every run. No server, no database, nothing to keep
alive — just files.

**`last-run.md`** — a summary of the run that just finished: how many passed and failed in
each group, which tests failed and what exactly broke in each, which were skipped and why,
and which were slowest.

```bash
make report
```

**`history.jsonl`** — one line per run: when it ran, on which environment, and the results.
This is what makes comparing runs possible.

```bash
make trends
```

That compares the last run to earlier ones and flags three things that are easy to miss: a
**group that shrank** (fewer tests ran than last time — usually a forgotten flag or a
renamed folder), a **test that became skipped**, and a **new failure**. It also says when a
run got slower, but that never blocks.

**`artifacts.jsonl`** — every object the tests created: what it was, its id, on which
environment, and which test made it.

The line is written automatically on every create, because every API call goes through one
place in the code. **No test opts in, and nothing can be forgotten.**

That answers the two questions a shared environment always raises:

```bash
make cleanup ENV=qa          # what the tests left on qa
make cleanup ENV=qa YES=1    # remove it
```

And when somebody asks where a record came from, you search its id in the file and see
which test made it.

**`make dashboard`** turns all of it into one HTML page: every run with its environment and
verdict, and every object created. Open it in a browser or attach it to a message.

---

## Filing bugs from a failed run

When a test fails you can open a ticket from it — but **never from inside the test**. A
test asserts; the decision to file belongs to the run, and it is off by default.

```bash
pytest --file-bugs-dry-run   # shows the exact ticket it would open, without opening it
pytest --file-bugs           # one ticket per failed test
```

The ticket follows the team's bug template — ENV, Precondition, Steps to reproduce, Actual
result, Expected result, Notes — filled with what the run actually knows. **Steps to
reproduce are the calls the test really made**, not an instruction to run the suite. The BE
or FE prefix comes from where the test lives.

**No duplicates:** every ticket carries the test's id. If the same test fails again
tomorrow, the filer finds the open ticket and comments on it instead of opening a second.

The tracker URL and token come from environment variables, never from the repo.

---

## Notifications

```bash
make notify-dry              # print the message without sending
pytest --notify              # send it to NOTIFY_WEBHOOK
```

The message carries the environment, the counts, the failing tests with each assertion, and
any regression finding. Slack and Teams both accept it.

---

## Using it without Claude Code

Everything outside `.claude/` is plain Python and pytest. The framework, the suites, the
bug filer, the dashboard, cleanup, trends, notifications and CI all work with no AI
involved at all.

`.claude/` holds two things, and neither of them runs anything:

| What | Without Claude Code |
|---|---|
| `CLAUDE.md` | read it as the contributing guide. It is the repo's rules, written for a person |
| skills | read them as the team's QA handbook: how a ticket gets verified, how a bug is written, what to do with a flaky test |
| agents and commands | read them as checklists. `/new-suite` describes exactly what to create, in order |

**Using another assistant.** Point it at the same file. Cursor reads `.cursorrules`,
Copilot reads `.github/copilot-instructions.md`, and most others take a path you configure.
Symlink or copy `CLAUDE.md` and the rules apply unchanged:

```bash
ln -s CLAUDE.md .cursorrules
```

**Not using an assistant at all.** Delete `.claude/` and nothing breaks. Keep `CLAUDE.md`
anyway — a new contributor reading it learns where payloads live and why `xfail` is banned,
which is the same reason it exists for an agent.

---

## Adoption, step by step

A realistic schedule for putting this on a real product. Each step ends with something that
works, so you can stop at any point and still be ahead.

### Day 1 — make it run against something real

1. `make install`, then `make api` and `make test`. If the demo passes, your machine is fine
   and any later failure is the product or the config, not the setup.
2. Read `CLAUDE.md` once. It is fifteen minutes and it is the whole contract.
3. Add a block for one real environment in `config/config.json`:

   ```json
   { "qa": { "url": "https://qa.yourproduct.com/api", "admin_user": "...", "member_user": "..." } }
   ```

   An unknown `ENV` fails at once and lists the names that do exist.
4. Change `register_persona` in `obj/client.py` to the product's real login.
5. Run `ENV=<yours> pytest -q`. It will fail — the demo's resources do not exist there.
   That is expected; you have proved the client, the config and the credentials work.

### Day 2 — the first real suite

6. Pick the smallest resource in the product. Not the most important one.
7. Copy `obj/resources/items.py`, rename it, set `resource`, keep the builder and the
   action method:

   ```python
   class Customers(Base):
       resource = "customers"

       def create_fake_customer(self, **kwargs):
           return self.create(self.build_customer_payload(**kwargs), persona="admin").assert_ok(201).as_dict
   ```

   `/new-suite customers` writes the class, the fixture and the suite for you.
8. Register it in `obj/__init__.py` and add a fixture in `tests/conftest.py`.
9. Write one happy path and one unhappy path. Assert values, not status codes.
10. Delete `tests/suites/test_order_flow.py`, `test_items_crud.py` and the other demo suites
    now that yours exists.

### Week 1 — make it protect something

11. Wire CI. The workflow in `.github/workflows/ci.yml` needs the environment name and the
    credentials as secrets; the rest is unchanged.
12. Check that `tests/unit` still passes. It tests the framework, not the product, so it
    should be green from the first minute and stay that way.
13. Point the bug filer at your tracker: `TRACKER_URL`, `TRACKER_EMAIL`, `TRACKER_TOKEN`,
    `TRACKER_PROJECT`. Run `pytest --file-bugs-dry-run` and read what it would file before
    letting it file anything.
14. Set `NOTIFY_WEBHOOK` if the team wants a channel summary.

### Week 2 — remove the scaffolding

15. Delete `demo_api/`, and the demo UI and LLM suites if the product has no equivalent.
16. Drop `fastapi`, `uvicorn`, and anything else you are not using, from
    `requirements.txt`, then run `scripts/maintenance/relock.sh`.
17. Rename the repo and update the first paragraph of this file.
18. Add the environments you actually deploy to, and confirm `prod` is in the config only
    so the guard can recognise and refuse it.

### What to keep, always

`tests/unit/`, the suite gating, the production guard, the bug filer, the ledgers, the
Makefile and CI. None of it is product-specific, and it is the part that takes weeks to get
right a second time.

## Rules

`CLAUDE.md` holds what this repo enforces: where payloads live, when to assert the maths
instead of a status code, which group a test belongs to, why `xfail` is banned, and why
every helper that writes data must guard production. Claude Code reads it automatically.

---
---

# בעברית

## מה זה

תשתית מוכנה לבדיקות API בפייתון ו-pytest. היא מגיעה עם API קטן לדוגמה, אז הבדיקות רצות
מהרגע שמשכפלים את הריפו. **287 בדיקות בשש קבוצות**, וכולן רצות ב-CI בכל דחיפה.

המטרה: להגיע למקום עבודה חדש ולא לבנות מאפס את מה שלוקח שבועות — שכבת האובייקטים, ניהול
הסביבות, הפרסונות, הגידור של הסוויטות, ההגנה על פרודקשן, פתיחת הבאגים וה-CI.

## איך מתחילים

```bash
make install     # התקנת סביבה
make api         # טרמינל 1 — ה-API על פורט 8000
make test        # טרמינל 2 — הרצת הבדיקות
```

אם אין פייתון על המחשב: `docker compose run --rm tests` מריץ בקונטיינר את כל הקבוצות חוץ
מסוויטת הדפדפן, ו-`docker compose run --rm ui` מריץ אותה.

## שש הקבוצות

| פקודה | מה היא בודקת | כמות |
|---|---|---|
| `make test` | שהמוצר מתנהג נכון | 64 |
| `make unit` | שהתשתית עצמה תקינה. בלי API ובלי רשת | 120 |
| `make edge` | מה קורה כשהקלט שבור | 20 |
| `make security` | שאי אפשר להגיע למה שלא שלך | 22 |
| `make ui` | מה המשתמש רואה בדפדפן | 20 |
| `make llm` | שפיצ׳ר ה-AI לא ממציא נתונים | 41 |

רק `make test` רצה כברירת מחדל. השאר דורשות דגל.

אחרי ריצה:

| פקודה | מה היא מציגה |
|---|---|
| `make report` | הריצה שהסתיימה: ספירה לכל קבוצה, כשלים, דילוגים והבדיקות האיטיות |
| `make dashboard` | כל הריצות וכל האובייקטים שנוצרו, בדף HTML אחד |
| `make trends` | מה נסוג מול ריצות קודמות: קבוצה שהתכווצה, דילוג חדש, כשל חדש |
| `make cleanup ENV=qa` | מה הריצות השאירו על הסביבה. `YES=1` מוחק |
| `make notify-dry` | ההודעה שהייתה נשלחת לערוץ |
| `make perf-smoke` / `make perf-load` | בדיקות עומס ב-k6 |

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

## מה קורה אחרי שהבדיקות רצות

אחרי כל הרצה נשמרים שלושה קבצים בתיקיית `reports/`. אין שרת, אין מסד נתונים, ואין מה
להחזיק חי — פשוט קבצים.

**`last-run.md`** — סיכום ההרצה שהרגע הסתיימה: כמה עברו וכמה נכשלו בכל קבוצה, אילו בדיקות
נכשלו ומה בדיוק נשבר בכל אחת, אילו דולגו ולמה, ואילו היו הכי איטיות.

```bash
make report
```

**`history.jsonl`** — שורה אחת לכל הרצה: מתי היא רצה, על איזו סביבה, ומה היו התוצאות.
הקובץ הזה הוא מה שמאפשר להשוות בין הרצות.

```bash
make trends
```

הפקודה משווה את ההרצה האחרונה לקודמות ומתריעה על שלושה דברים שקל לפספס: **קבוצה שהתכווצה**
(פחות בדיקות רצו מאשר בפעם שעברה — בדרך כלל דגל שנשכח או תיקייה ששונתה), **בדיקה שהפכה
למדולגת**, ו**כשל חדש**. היא גם אומרת אם ההרצה האטה, אבל זה לא חוסם.

**`artifacts.jsonl`** — כל אובייקט שהבדיקות יצרו: מה נוצר, מה ה-id שלו, על איזו סביבה,
ואיזה טסט יצר אותו.

השורה הזו נרשמת אוטומטית בכל יצירה, כי כל הקריאות ל-API עוברות דרך מקום אחד בקוד. **אף
טסט לא צריך לעשות כלום, ואי אפשר לשכוח.**

זה עונה על שתי שאלות שתמיד עולות כשעובדים על סביבה משותפת:

```bash
make cleanup ENV=qa          # מה הבדיקות השאירו על qa
make cleanup ENV=qa YES=1    # למחוק את זה
```

ואם מישהו שואל "מאיפה הגיעה ההזמנה הזאת" — מחפשים את ה-id בקובץ ורואים איזה טסט יצר אותה.

**`make dashboard`** מרכז את הכל לדף HTML אחד: כל ההרצות עם הסביבה והתוצאה, וכל האובייקטים
שנוצרו. אפשר לפתוח אותו בדפדפן או לצרף אותו להודעה.

## פתיחת באגים אוטומטית

כשבדיקה נכשלת, אפשר לפתוח ממנה כרטיס באג — אבל **לא מתוך קוד הבדיקה**. הבדיקה רק בודקת;
ההחלטה לפתוח כרטיס שייכת להרצה, והיא כבויה כברירת מחדל.

```bash
pytest --file-bugs-dry-run   # מראה בדיוק איזה כרטיס היה נפתח, בלי לפתוח
pytest --file-bugs           # פותח כרטיס לכל בדיקה שנכשלה
```

הכרטיס נבנה לפי תבנית הבאג של הצוות — ENV, Precondition, Steps to reproduce, Actual result,
Expected result, Notes — ומתמלא ממה שההרצה באמת יודעת. **צעדי השחזור הם רצף הקריאות שהטסט
עשה בפועל**, לא הוראה להריץ את הסוויטה. הקידומת BE או FE נגזרת ממיקום הטסט.

**אין כפילויות:** כל כרטיס נושא את מזהה הבדיקה. אם אותה בדיקה תיכשל שוב מחר, המערכת תזהה
שכבר קיים כרטיס פתוח ותוסיף לו תגובה במקום לפתוח שני.

הכתובת של ה-tracker והטוקן מגיעים ממשתני סביבה בלבד, אף פעם לא מהריפו.

## התראות לערוץ

```bash
make notify-dry              # מראה את ההודעה בלי לשלוח
pytest --notify              # שולח ל-NOTIFY_WEBHOOK
```

ההודעה כוללת את הסביבה, הספירות, הבדיקות שנכשלו עם השגיאה של כל אחת, וכל ממצא רגרסיה.
עובד מול Slack ו-Teams.

## שימוש בלי Claude Code

כל מה שמחוץ ל-`.claude/` הוא פייתון ו-pytest רגילים. התשתית, הסוויטות, פותח הבאגים,
הדשבורד, הניקוי, הרגרסיה, ההתראות וה-CI — הכל עובד בלי שום AI.

בתיקיית `.claude/` יש שני דברים, ואף אחד מהם לא מריץ כלום:

| מה | בלי Claude Code |
|---|---|
| `CLAUDE.md` | קוראים אותו כמדריך לתורמים. אלה חוקי הריפו, כתובים לבן אדם |
| הסקילים | ספר הנהלים של הצוות: איך מאמתים כרטיס, איך כותבים באג, מה עושים עם טסט מתחלף |
| הסוכנים והפקודות | צ׳קליסטים. `/new-suite` מתאר בדיוק מה ליצור ובאיזה סדר |

**עם עוזר אחר.** מפנים אותו לאותו קובץ. Cursor קורא `.cursorrules`, Copilot קורא
`.github/copilot-instructions.md`, ורובם מקבלים נתיב שמגדירים:

```bash
ln -s CLAUDE.md .cursorrules
```

**בלי עוזר בכלל.** מוחקים את `.claude/` ושום דבר לא נשבר. את `CLAUDE.md` כדאי להשאיר —
מי שמצטרף לצוות וקורא אותו לומד איפה יושבים הפיילואדים ולמה `xfail` אסור, וזו בדיוק הסיבה
שהוא קיים גם בשביל סוכן.

---

## איך מטמיעים, שלב אחרי שלב

לוח זמנים מציאותי להטמעה על מוצר אמיתי. כל שלב נגמר במשהו שעובד, אז אפשר לעצור בכל נקודה
ועדיין להיות ברווח.

### יום 1 — שיירוץ מול משהו אמיתי

1. `make install`, ואז `make api` ו-`make test`. אם הדמו עובר, המחשב שלך תקין — וכל כשל
   מאוחר יותר הוא המוצר או הקונפיג, לא ההתקנה.
2. לקרוא את `CLAUDE.md` פעם אחת. רבע שעה, וזה כל החוזה.
3. להוסיף בלוק לסביבה אמיתית אחת ב-`config/config.json`:

   ```json
   { "qa": { "url": "https://qa.yourproduct.com/api", "admin_user": "...", "member_user": "..." } }
   ```

   שם סביבה שלא קיים נכשל מיד ומדפיס אילו סביבות כן קיימות.
4. לשנות את `register_persona` ב-`obj/client.py` לשיטת ההתחברות של המוצר.
5. להריץ `ENV=<שלך> pytest -q`. זה ייכשל — המשאבים של הדמו לא קיימים שם. זה תקין: הוכחת
   שהקליינט, הקונפיג והאישורים עובדים.

### יום 2 — הסוויטה האמיתית הראשונה

6. לבחור את המשאב **הכי קטן** במוצר. לא את הכי חשוב.
7. להעתיק את `obj/resources/items.py`, לשנות שם, להגדיר `resource`, ולשמור על הבנאי ועל
   מתודת הפעולה:

   ```python
   class Customers(Base):
       resource = "customers"

       def create_fake_customer(self, **kwargs):
           return self.create(self.build_customer_payload(**kwargs), persona="admin").assert_ok(201).as_dict
   ```

   הפקודה `/new-suite customers` כותבת את המחלקה, את ה-fixture ואת הסוויטה.
8. לרשום אותו ב-`obj/__init__.py` ולהוסיף fixture ב-`tests/conftest.py`.
9. לכתוב מסלול מוצלח אחד ומסלול כושל אחד. לבדוק ערכים, לא קודי סטטוס.
10. למחוק את סוויטות הדמו ברגע שיש לך משלך.

### שבוע 1 — שהתשתית תתחיל להגן

11. לחבר CI. ה-workflow ב-`.github/workflows/ci.yml` צריך את שם הסביבה ואת האישורים
    כ-secrets; השאר לא משתנה.
12. לוודא ש-`tests/unit` עדיין עובר. הוא בודק את התשתית ולא את המוצר, אז הוא אמור להיות
    ירוק מהדקה הראשונה ולהישאר כזה.
13. לחבר את פותח הבאגים ל-tracker: `TRACKER_URL`, `TRACKER_EMAIL`, `TRACKER_TOKEN`,
    `TRACKER_PROJECT`. **להריץ `pytest --file-bugs-dry-run` ולקרוא מה הוא היה פותח** לפני
    שנותנים לו לפתוח משהו.
14. להגדיר `NOTIFY_WEBHOOK` אם הצוות רוצה סיכום בערוץ.

### שבוע 2 — להוריד את הפיגומים

15. למחוק את `demo_api/`, ואת סוויטות ה-UI וה-LLM אם אין להן מקבילה במוצר.
16. להוריד מ-`requirements.txt` את `fastapi`, `uvicorn` וכל מה שלא בשימוש, ואז להריץ
    `scripts/maintenance/relock.sh`.
17. לשנות את שם הריפו ואת הפסקה הראשונה בקובץ הזה.
18. להוסיף את הסביבות האמיתיות, ולוודא ש-`prod` נמצא בקונפיג **רק** כדי שההגנה תזהה אותו
    ותסרב.

### מה שומרים תמיד

`tests/unit/`, גידור הסוויטות, הגנת ה-prod, פותח הבאגים, הלדג׳רים, ה-Makefile וה-CI. שום
דבר מזה לא תלוי במוצר, וזה החלק שלוקח שבועות לבנות נכון בפעם השנייה.

## הכללים

`CLAUDE.md` מרכז את מה שהריפו אוכף: איפה נמצאים הפיילואדים, מתי בודקים את החשבון ולא רק את
קוד הסטטוס, לאיזו קבוצה שייך כל טסט, למה `xfail` אסור, ולמה כל עזר שכותב נתונים חייב הגנת
prod. Claude Code קורא את הקובץ הזה אוטומטית.
