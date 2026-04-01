# Samsung Chat QA Automation

> **Browser-UI based chatbot QA system for www.samsung.com**
>
> Automates interaction with the Samsung AI chat widget using Playwright,
> then evaluates responses with OpenAI GPT via the Responses API.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [How It Works](#how-it-works)
3. [Project Structure](#project-structure)
4. [Local Setup & Execution](#local-setup--execution)
5. [Playwright Installation](#playwright-installation)
6. [GitHub Actions Setup](#github-actions-setup)
7. [GitHub Secrets Setup](#github-secrets-setup)
8. [Writing Test Cases (CSV)](#writing-test-cases-csv)
9. [Result Files](#result-files)
10. [Selector Modification Guide](#selector-modification-guide)
11. [iframe Debugging](#iframe-debugging)
12. [OpenAI Cost Notes](#openai-cost-notes)
13. [Real-Site Automation Warnings](#real-site-automation-warnings)
14. [Maintenance Checklist](#maintenance-checklist)
15. [Troubleshooting / Known Failure Points](#troubleshooting--known-failure-points)

---

## Project Overview

This project performs **end-to-end QA** of the AI chat widget on Samsung's
public website by:

- Navigating to `https://www.samsung.com/` (or a page-specific URL from the CSV).
- Locating and clicking the AI chat FAB (floating action button) in the
  bottom-right corner.
- Typing a question into the chat input and sending it.
- Waiting for the bot's answer to stabilise (text-stability check).
- Capturing a full-page screenshot and a chat-area screenshot.
- Calling OpenAI's Responses API with **Structured Outputs** to score
  answer quality across five dimensions.
- Saving JSON, CSV, and Markdown reports.

All steps use **Playwright locators** (auto-wait / retry) rather than fixed
sleeps. The system is robust to both DOM-embedded and iframe-embedded chat
widgets.

---

## How It Works

```
run.py
  └─ app/main.py  (orchestrator)
       ├─ app/config.py       load env → Config
       ├─ app/logger.py       set up logging
       ├─ app/csv_loader.py   read testcases/questions.csv
       ├─ app/browser.py      launch Playwright Chromium
       ├─ app/samsung_chat.py
       │    ├─ open_homepage()
       │    ├─ dismiss_popups()
       │    ├─ open_chat_widget()  ← multiple selector fallbacks
       │    ├─ resolve_chat_context()  ← DOM or iframe detection
       │    ├─ submit_question()
       │    ├─ wait_for_answer_completion()  ← text-stability check
       │    ├─ extract_last_answer()
       │    └─ capture_artifacts()  → artifacts/fullpage/ & artifacts/chatbox/
       ├─ app/evaluator.py    OpenAI Responses API + Structured Outputs
       └─ app/report_writer.py
            ├─ reports/latest_results.json
            ├─ reports/latest_results.csv
            └─ reports/summary.md
```

---

## Project Structure

```
.
├─ app/
│  ├─ __init__.py
│  ├─ main.py           – Orchestrator
│  ├─ config.py         – Configuration (env vars)
│  ├─ logger.py         – Logging setup
│  ├─ models.py         – Dataclasses: TestCase, EvalResult, RunResult
│  ├─ csv_loader.py     – Load testcases/questions.csv
│  ├─ browser.py        – Playwright browser lifecycle
│  ├─ samsung_chat.py   – Chat widget automation (core)
│  ├─ evaluator.py      – OpenAI evaluation
│  ├─ report_writer.py  – JSON / CSV / Markdown reports
│  └─ utils.py          – Helpers (timestamps, paths, keywords)
├─ testcases/
│  └─ questions.csv     – Test input
├─ artifacts/
│  ├─ fullpage/         – Full-page PNG screenshots
│  └─ chatbox/          – Chat-area PNG screenshots
├─ reports/             – JSON / CSV / Markdown outputs + runtime.log
├─ .github/
│  └─ workflows/
│     └─ samsung-chat-qa.yml
├─ .env.example
├─ .gitignore
├─ requirements.txt
├─ README.md
└─ run.py               – CLI entry point
```

---

## Local Setup & Execution

### Prerequisites

- Python 3.11+
- Git

### Step-by-step

```bash
# 1. Clone the repository
git clone https://github.com/your-username-or-org/Rubicon_evaluation.git
cd Rubicon_evaluation

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Playwright browsers
python -m playwright install --with-deps chromium

# 5. Configure environment variables
cp .env.example .env
# Edit .env and set OPENAI_API_KEY (required for evaluation)

# 6. Run
python run.py
```

Results are written to `reports/` and screenshots to `artifacts/`.

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | *(required)* | OpenAI API key |
| `SAMSUNG_BASE_URL` | `https://www.samsung.com/` | Target URL |
| `HEADLESS` | `true` | `false` shows the browser window |
| `DEFAULT_LOCALE` | `en-US` | Browser locale |
| `MAX_QUESTIONS` | `3` | Max rows from CSV (0 = all) |
| `OPENAI_MODEL` | `gpt-4o` | OpenAI model name |
| `PLAYWRIGHT_TIMEOUT_MS` | `30000` | Playwright default timeout |
| `ANSWER_STABLE_CHECKS` | `3` | Consecutive identical reads to confirm stability |
| `ANSWER_STABLE_INTERVAL_SEC` | `1.0` | Polling interval (seconds) |

---

## Playwright Installation

Playwright requires browser binaries in addition to the Python package.

```bash
# Install the package (included in requirements.txt)
pip install playwright

# Install Chromium with OS dependencies (recommended)
python -m playwright install --with-deps chromium

# To open an interactive debugging session
python -m playwright codegen https://www.samsung.com/
```

On Ubuntu CI runners, `--with-deps` automatically installs the system
libraries needed by Chromium (libnss, libdbus, etc.).

---

## GitHub Actions Setup

The workflow is defined in `.github/workflows/samsung-chat-qa.yml`.

### Triggers

| Trigger | Description |
|---|---|
| `workflow_dispatch` | Manual run from the GitHub Actions UI. You can override `max_questions` and `headless`. |
| `schedule` | Automatic daily run at **01:00 UTC**. To change the time, edit the `cron:` line in the YAML. |

### How to trigger manually

1. Go to **Actions** → **Samsung Chat QA Automation** in your GitHub repository.
2. Click **Run workflow**.
3. (Optional) Override `max_questions` or `headless`.
4. Click **Run workflow**.

### Schedule notes

> GitHub Actions uses **UTC** for cron schedules.
> `0 1 * * *` = every day at 01:00 UTC = 10:00 KST (Korea Standard Time, UTC+9).
> The minimum permitted schedule interval on GitHub Actions is **5 minutes**.

---

## GitHub Secrets Setup

The workflow needs your OpenAI API key as a repository secret.

1. Open your repository on GitHub.
2. Click **Settings** → **Secrets and variables** → **Actions**.
3. Click **New repository secret**.
4. Name: `OPENAI_API_KEY`
5. Value: your OpenAI API key (starts with `sk-…`).
6. Click **Add secret**.

> **Never commit your API key directly to the repository.**

---

## Writing Test Cases (CSV)

Edit `testcases/questions.csv`.  The file uses UTF-8 encoding and must
include a header row.

### Column specification

| Column | Required | Description |
|---|---|---|
| `id` | ✅ | Unique identifier (e.g. `TC001`) |
| `category` | ✅ | Logical grouping (e.g. `product_search`) |
| `locale` | ✅ | Browser locale (e.g. `en-US`) |
| `page_url` | ✅ | Full URL to open before chatting |
| `question` | ✅ | The question to ask the chatbot |
| `expected_keywords` | | Pipe-separated `|` list of words that *should* appear in the answer |
| `forbidden_keywords` | | Pipe-separated `|` list of words that must *not* appear |

### Example row

```csv
TC001,product_search,en-US,https://www.samsung.com/,What Galaxy phones are available?,Galaxy|Android,error
```

---

## Result Files

After a run the following files are created or updated:

| File | Description |
|---|---|
| `reports/latest_results.json` | Full result array in JSON format |
| `reports/latest_results.csv` | Flat CSV table, one row per test case |
| `reports/summary.md` | Human-readable Markdown summary |
| `reports/runtime.log` | Detailed debug/info log from the run |
| `artifacts/fullpage/<ts>_<id>.png` | Full-page PNG screenshot |
| `artifacts/chatbox/<ts>_<id>.png` | Chat-area PNG screenshot |

### CSV / JSON columns

`run_timestamp`, `case_id`, `category`, `question`, `answer`, `response_ms`,
`status`, `error_message`, `overall_score`, `needs_human_review`,
`hallucination_risk`, `reason`, `fix_suggestion`, `full_screenshot_path`,
`chat_screenshot_path`

---

## Selector Modification Guide

Samsung's website markup changes periodically.  When the chat icon or input
cannot be found, update the selector candidate lists in
`app/samsung_chat.py`.

### Key selector lists

| Variable | Purpose |
|---|---|
| `_CHAT_ICON_CANDIDATES` | FAB / chat-icon button selectors |
| `_INPUT_CANDIDATES` | Chat input field selectors |
| `_SEND_BUTTON_CANDIDATES` | Send / submit button selectors |
| `_BOT_MESSAGE_CANDIDATES` | Bot answer element selectors |
| `_LOADING_CANDIDATES` | Typing / spinner indicators |
| `_POPUP_CLOSE_CANDIDATES` | Cookie / overlay dismiss buttons |

### Debugging selectors interactively

```bash
# Open an interactive Playwright session
python -m playwright codegen https://www.samsung.com/

# Or use the REPL to probe selectors
python -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto('https://www.samsung.com/')
    page.pause()   # Opens the Playwright Inspector
"
```

1. Use **Playwright Inspector** (opened by `page.pause()`) to click
   elements and copy their selectors.
2. Add the new selector at the **top** of the relevant candidate list in
   `samsung_chat.py`.

---

## iframe Debugging

The Samsung chat widget may be delivered inside an `<iframe>`.
`resolve_chat_context()` in `samsung_chat.py` automatically scores all
frames and selects the most likely chat frame.

### Manual investigation

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("https://www.samsung.com/")
    # ... open chat widget manually ...
    for frame in page.frames:
        print(frame.url, frame.name)
        # Look for frames with "chat" or vendor domain in the URL
```

If the iframe has a predictable URL pattern, you can use
`page.frame_locator("iframe[src*='chat']")` directly.

---

## OpenAI Cost Notes

Each question invokes one OpenAI API call.  With `MAX_QUESTIONS=3` and
model `gpt-4o`, the cost is roughly:

- Input tokens: ~400–600 per call (prompt + schema)
- Output tokens: ~100–200 per call (structured JSON)
- Cost at 2024 pricing: **< $0.01 per call**

For daily runs with 5 questions the monthly cost is < $1 USD.

> **Tip:** Use `gpt-4o-mini` instead of `gpt-4o` to reduce costs by ~15×.
> Update `OPENAI_MODEL` in `.env` or the workflow YAML.

---

## Real-Site Automation Warnings

- This project automates a **production website**.
- Excessive requests may trigger rate-limiting or anti-bot measures.
- Do **not** run more than one instance at a time.
- Keep `MAX_QUESTIONS` small (≤5) for daily scheduled runs.
- If Samsung updates their site structure, selectors may break—update
  `_CHAT_ICON_CANDIDATES` and other lists accordingly.
- Respect Samsung's Terms of Service; use this tool for QA/monitoring
  purposes only.

---

## Maintenance Checklist

- [ ] Re-validate selectors after Samsung site redesigns.
- [ ] Monitor `reports/summary.md` for `needs_human_review: true` cases.
- [ ] Rotate the `OPENAI_API_KEY` secret annually.
- [ ] Update `requirements.txt` dependencies periodically (`pip list --outdated`).
- [ ] Verify that the GitHub Actions schedule still fires (`Actions` → `samsung-chat-qa.yml` → workflow history).
- [ ] Check `reports/runtime.log` for recurring warnings.
- [ ] Increase `PLAYWRIGHT_TIMEOUT_MS` if Samsung's chat widget loads slowly.

---

## Troubleshooting / Known Failure Points

### Chat icon not found

**Symptom:** `RuntimeError: Could not locate the AI chat icon.`

**Checks:**
1. Open `artifacts/fullpage/DEBUG_*.png` to see the page state.
2. Samsung may have changed the icon's HTML attributes.
3. Add the new selector to `_CHAT_ICON_CANDIDATES` in `samsung_chat.py`.
4. Try running with `HEADLESS=false` locally and use `page.pause()`.

---

### iframe not found / input not found

**Symptom:** `Could not find the chat input field.`

**Checks:**
1. Check whether the widget loads inside an iframe (`page.frames` list).
2. Look for the iframe URL in the console or network tab.
3. Update `resolve_chat_context()` with a targeted `page.frame_locator()` call.

---

### No answer extracted

**Symptom:** `answer` column is empty; `status=failed`.

**Checks:**
1. Check `_BOT_MESSAGE_CANDIDATES` – the message container class may have changed.
2. Increase `PLAYWRIGHT_TIMEOUT_MS` if the network is slow.
3. Verify that the chat widget is actually responding (check screenshots).

---

### OpenAI evaluation failed

**Symptom:** `overall_score=0.0`, `needs_human_review=true`, `reason="OpenAI evaluation failed"`.

**Checks:**
1. Verify that `OPENAI_API_KEY` is set correctly.
2. Check OpenAI API status at https://status.openai.com/.
3. Confirm the model name in `OPENAI_MODEL` is valid.
4. Check `reports/runtime.log` for the specific error message.

---

### GitHub Actions not running on schedule

- GitHub may delay or skip scheduled workflows when a repository has been
  inactive.  Trigger a manual run to re-activate the schedule.
- Verify the cron expression at https://crontab.guru/.

---

### Screenshot save failed

**Symptom:** `full_screenshot_path` is empty in results.

**Checks:**
1. Ensure `artifacts/fullpage/` and `artifacts/chatbox/` directories exist
   (they have `.gitkeep` files so they should be created by Git checkout).
2. Check file-system permissions.

---

*For further help, open an issue in the repository.*
