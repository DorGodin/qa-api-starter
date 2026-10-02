# qa-api-starter

[![ci](https://github.com/DorGodin/qa-api-starter/actions/workflows/ci.yml/badge.svg)](https://github.com/DorGodin/qa-api-starter/actions/workflows/ci.yml)

A ready-to-use API test framework in Python and pytest. It ships with a small demo API so it
runs the moment you clone it, and it tests a second, real product from the outside — the
[barbershop](https://github.com/DorGodin/barber-booking-api) — to show it works on something
it shares no code with. Clone it, run it, then point it at your own product.

![Two customers go for the same free time; the first is booked, the second is told it has just gone](docs/media/race.gif)

[עברית למטה](#בעברית)

---

## What is in it

| Suite | What it checks | Run it |
|---|---|---|
| Product | the API behaves: flows, rules, permissions, paging, the money math | `make test` |
| Edge cases | bad input is refused cleanly | `make edge` |
| Security | nobody reaches what is not theirs | `make security` |
| Browser | what a person sees and does, in a real browser (Playwright) | `make ui` |
| LLM | the AI feature does not invent data (DeepEval) | `make llm` |
| Load | thresholds that fail the pipeline (k6) | `make perf` |
| Framework | the framework's own code — no API, no network | `make unit` |
| Barbershop | API, pages on desktop, iPhone and Android, end-to-end journeys, load | see below |
| Mutation | breaks the product on purpose and checks a suite notices — nightly in CI | `make mutate` |

Every push runs all of it in CI.

## Start

1. Install:

   ```bash
   make install
   ```

2. Start the demo API, in one terminal:

   ```bash
   make api
   ```

3. Run the tests, in another:

   ```bash
   make test
   ```

4. After a run, `make report` shows the result and `make dashboard` the history of every run.

No Python? `docker compose run --rm tests` runs it all in a container.

## Testing the barbershop

1. Clone [barber-booking-api](https://github.com/DorGodin/barber-booking-api) next to this
   folder, and start its test copy:

   ```bash
   cd ../barber-booking-api && cp .env.example .env && make install && make run-test
   ```

2. Back here, run its suites:

   ```bash
   make test ENV=barber          # the API
   make ui-barber                # the booking page in a browser
   make ui-barber-mobile         # the same, on an iPhone (WebKit) and an Android phone
   make perf-barber              # the booking race under load
   ```

## Using it on your own product

1. **Add your environment** to `config/config.json`: its URL, the roles your tests act as
   (`personas`), and how they log in (`auth`). Every key is required; nothing is guessed.
2. **Put the passwords outside git** — environment variables (`QA_OWNER_PASSWORD`, …) or
   `config/config.local.json`, which git ignores.
3. **Prove the setup** before writing a test. It logs in as every role and creates nothing:

   ```bash
   make env-check ENV=qa
   ```

4. **Write the first suite.** One class per API resource in `obj/` (copy
   `obj/resources/items.py`), one happy path and one unhappy path in `tests/`. Assert values,
   not only status codes. `/new-suite <resource>` in Claude Code writes the skeleton.
5. **Wire CI**: one secret per role, and `ENV` on the job, with `make env-check` as its first step.
6. **Remove the demo**: `demo_api/`, the demo suites, and `fastapi`/`uvicorn` from
   `requirements.txt` (then `scripts/maintenance/relock.sh`).

Keep `tests/unit/`, the production guard, the bug filer and CI — none of it is product-specific.

## Rules

`CLAUDE.md` is the contract: where payloads live, which suite a test belongs to, what every
data-creating helper must guard. `docs/pitfalls.md` is the log of mistakes and the rules that
came out of them. Claude Code reads both.

---
---

<a id="בעברית"></a>

# בעברית

תשתית מוכנה לבדיקות API בפייתון ו-pytest. היא מגיעה עם API קטן לדוגמה, כך שהיא רצה מהרגע שמשכפלים
אותה, והיא בודקת מבחוץ גם מוצר שני ואמיתי — [המספרה](https://github.com/DorGodin/barber-booking-api) —
כדי להראות שהיא עובדת על משהו שאין לה איתו שום קוד משותף. משכפלים, מריצים, ואז מכוונים למוצר שלכם.

## מה יש בה

| סוויטה | מה היא בודקת | איך מריצים |
|---|---|---|
| מוצר | ה-API מתנהג נכון: תהליכים, חוקים, הרשאות, דפדוף, החשבון של הכסף | `make test` |
| מקרי קצה | קלט שגוי נדחה כמו שצריך | `make edge` |
| אבטחה | אף אחד לא מגיע למה שלא שלו | `make security` |
| דפדפן | מה שאדם רואה ועושה, בדפדפן אמיתי (Playwright) | `make ui` |
| LLM | פיצ'ר ה-AI לא ממציא נתונים (DeepEval) | `make llm` |
| עומס | ספים שמפילים את הפייפליין (k6) | `make perf` |
| התשתית | הקוד של התשתית עצמה — בלי API ובלי רשת | `make unit` |
| המספרה | API, מסכים במחשב, באייפון ובאנדרואיד, מסעות מקצה לקצה, עומס | ראו למטה |
| מוטציות | שוברות את המוצר בכוונה ובודקות שסוויטה שמה לב — כל לילה ב-CI | `make mutate` |

כל push מריץ את הכל ב-CI.

## איך מתחילים

1. התקנה:

   ```bash
   make install
   ```

2. מפעילים את ה-API לדוגמה, בטרמינל אחד:

   ```bash
   make api
   ```

3. מריצים את הבדיקות, בטרמינל אחר:

   ```bash
   make test
   ```

4. אחרי ריצה, `make report` מציג את התוצאה ו-`make dashboard` את ההיסטוריה של כל הריצות.

אין פייתון? `docker compose run --rm tests` מריץ הכל בקונטיינר.

## בדיקת המספרה

1. משכפלים את [barber-booking-api](https://github.com/DorGodin/barber-booking-api) לצד התיקייה הזו,
   ומפעילים את עותק הבדיקות שלה:

   ```bash
   cd ../barber-booking-api && cp .env.example .env && make install && make run-test
   ```

2. חוזרים לכאן ומריצים את הסוויטות שלה:

   ```bash
   make test ENV=barber          # ה-API
   make ui-barber                # מסך ההזמנה בדפדפן
   make ui-barber-mobile         # אותו דבר, באייפון (WebKit) ובאנדרואיד
   make perf-barber              # המרוץ על תור, תחת עומס
   ```

## שימוש על המוצר שלכם

1. **מוסיפים סביבה** ב-`config/config.json`: הכתובת, התפקידים שהבדיקות פועלות בשמם (`personas`), ואיך
   הם מתחברים (`auth`). כל מפתח הוא חובה; שום דבר לא מנוחש.
2. **הסיסמאות מחוץ ל-git** — במשתני סביבה (`QA_OWNER_PASSWORD` וכו') או ב-`config/config.local.json`,
   ש-git מתעלם ממנו.
3. **מוודאים שההגדרה עובדת** לפני שכותבים בדיקה. זה מתחבר בכל תפקיד ולא יוצר כלום:

   ```bash
   make env-check ENV=qa
   ```

4. **כותבים את הסוויטה הראשונה.** מחלקה אחת לכל משאב של ה-API ב-`obj/` (מעתיקים את
   `obj/resources/items.py`), ומסלול תקין אחד ולא תקין אחד ב-`tests/`. בודקים ערכים, לא רק קודי סטטוס.
   `/new-suite <resource>` ב-Claude Code כותב את השלד.
5. **מחברים ל-CI**: secret אחד לכל תפקיד, `ENV` על ה-job, ו-`make env-check` כצעד הראשון.
6. **מורידים את הדמו**: `demo_api/`, הסוויטות לדוגמה, ו-`fastapi`/`uvicorn` מ-`requirements.txt`
   (ואז `scripts/maintenance/relock.sh`).

את `tests/unit/`, ההגנה על פרודקשן, פתיחת הבאגים וה-CI משאירים — שום דבר מהם לא תלוי במוצר.

## הכללים

`CLAUDE.md` הוא החוזה: איפה נמצאים ה-payloads, לאיזו סוויטה שייכת בדיקה, ממה כל helper שיוצר נתונים
חייב להגן. `docs/pitfalls.md` הוא היומן של הטעויות ושל הכללים שיצאו מהן. Claude Code קורא את שניהם.
