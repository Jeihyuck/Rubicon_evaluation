# Samsung Chat QA Automation

A browser-UI-based chatbot QA automation system for **www.samsung.com**.

---

## Project Overview

This project automatically:

1. Opens `https://www.samsung.com/` (or a page URL from the test case)
2. Locates and clicks the AI chat icon in the lower-right corner
3. Opens the chat widget
4. Inputs a question from the test-case CSV
5. Waits for the chatbot's full response
6. Extracts the answer text
7. Takes screenshots of the chat area and the full page
8. Evaluates answer quality using **OpenAI GPT** (Responses API + Structured Outputs)
9. Saves results as JSON, CSV, and Markdown reports
10. Runs automatically via GitHub Actions on a daily schedule or on demand

> **Important:** This project uses browser UI automation only – no direct API calls to Samsung.

---

## Directory Structure

```
samsung-chat-qa/
├─ app/
│  ├─ __init__.py
│  ├─ main.py           # Orchestrator
│  ├─ config.py         # Environment / config management
│  ├─ logger.py         # Logging setup
│  ├─ models.py         # Dataclasses (TestCase, EvalResult, RunResult)
│  ├─ csv_loader.py     # Load testcases/questions.csv
│  ├─ browser.py        # Playwright browser lifecycle
│  ├─ samsung_chat.py   # Core chat automation
│  ├─ evaluator.py      # OpenAI evaluation
│  ├─ report_writer.py  # JSON / CSV / Markdown reports
│  └─ utils.py          # Timestamps, path helpers, keyword checks
├─ testcases/
│  └─ questions.csv     # Test cases
├─ artifacts/
│  ├─ fullpage/         # Full-page screenshots
│  └─ chatbox/          # Chat-area screenshots
├─ reports/             # Generated reports & runtime.log
├─ .github/
│  └─ workflows/
│     └─ samsung-chat-qa.yml
├─ .env.example
├─ .gitignore
├─ requirements.txt
├─ README.md
└─ run.py               # CLI entry point
```

---

## Workflow / Flow Diagram

```
run.py
  └─ main.run()
       ├─ load_test_cases (csv_loader)
       └─ for each TestCase:
            ├─ open_homepage (samsung_chat)
            ├─ dismiss_popups
            ├─ open_chat_widget  ← find & click AI chat icon
            ├─ resolve_chat_context ← DOM or iframe
            ├─ submit_question
            ├─ wait_for_answer_completion ← stability polling
            ├─ extract_last_answer
            ├─ capture_artifacts → artifacts/fullpage/ + artifacts/chatbox/
            ├─ evaluate_answer (evaluator → OpenAI Responses API)
            └─ write_all_reports → reports/latest_results.json/csv + summary.md
```

---

## Local Setup & Execution

### Prerequisites

- Python 3.11+
- pip

### 1. Clone and install

```bash
git clone https://github.com/<your-org>/Rubicon_evaluation.git
cd Rubicon_evaluation
pip install -r requirements.txt
```

### 2. Install Playwright browsers

```bash
playwright install --with-deps chromium
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env and set at minimum:
#   OPENAI_API_KEY=sk-...
```

### 4. Run

```bash
python run.py
```

Results appear in `reports/` and screenshots in `artifacts/`.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | *(required)* | OpenAI API key |
| `SAMSUNG_BASE_URL` | `https://www.samsung.com/` | Target URL |
| `HEADLESS` | `true` | Run browser headlessly |
| `DEFAULT_LOCALE` | `en-US` | Browser locale |
| `MAX_QUESTIONS` | `3` | Max test cases to run (0 = all) |
| `OPENAI_MODEL` | `gpt-4o` | OpenAI model to use |
| `PLAYWRIGHT_TIMEOUT_MS` | `30000` | Default Playwright timeout (ms) |
| `ANSWER_STABLE_CHECKS` | `3` | Consecutive identical text reads required |
| `ANSWER_STABLE_INTERVAL_SEC` | `1.0` | Seconds between stability checks |

---

## Test Case CSV Format

File: `testcases/questions.csv`

| Column | Description |
|---|---|
| `id` | Unique test case ID |
| `category` | Category label |
| `locale` | Browser locale (e.g. `en-US`) |
| `page_url` | Page to open (leave blank = use `SAMSUNG_BASE_URL`) |
| `question` | Question to ask the chatbot |
| `expected_keywords` | Pipe-separated keywords expected in the answer |
| `forbidden_keywords` | Pipe-separated keywords that must NOT appear |

**Example:**

```csv
id,category,locale,page_url,question,expected_keywords,forbidden_keywords
TC001,product-info,en-US,https://www.samsung.com/us/,"What are the latest Samsung Galaxy smartphones?",Galaxy|5G,error|unavailable
```

---

## Output Files

| File | Description |
|---|---|
| `reports/latest_results.json` | Full results as JSON array |
| `reports/latest_results.csv` | Flat CSV table |
| `reports/summary.md` | Human-readable Markdown summary |
| `reports/runtime.log` | Detailed runtime log |
| `artifacts/fullpage/*.png` | Full-page screenshots |
| `artifacts/chatbox/*.png` | Chat-area screenshots |

---

## GitHub Actions Setup

### 1. Push the repository to GitHub

```bash
git remote add origin https://github.com/<your-org>/Rubicon_evaluation.git
git push -u origin main
```

### 2. Set GitHub Secrets

Go to **Settings → Secrets and variables → Actions** and add:

| Secret | Value |
|---|---|
| `OPENAI_API_KEY` | Your OpenAI API key |

### 3. Trigger a run

- **Manual:** Go to **Actions → Samsung Chat QA Automation → Run workflow**
- **Scheduled:** Runs automatically every day at **02:00 UTC** (11:00 KST)

> **Note on schedule:** GitHub Actions uses UTC time. `cron: "0 2 * * *"` = 02:00 UTC.

### 4. Download artifacts

After the workflow completes, download:
- `reports-<run-id>` – JSON/CSV/Markdown reports
- `artifacts-<run-id>` – Screenshots

---

## Selector Modification

If Samsung changes their chat widget, update the selector candidate lists in `app/samsung_chat.py`:

```python
CHAT_ICON_CANDIDATES   # AI chat icon / FAB
INPUT_CANDIDATES       # Question input field
SEND_BUTTON_CANDIDATES # Send / Submit button
BOT_MESSAGE_CANDIDATES # Bot answer elements
LOADING_CANDIDATES     # Spinner / typing indicators
```

Each list is tried in order; the first visible match wins. Add new selectors to the **beginning** of the list for priority.

---

## iframe Debugging

If the chat widget is inside an iframe and not being detected:

1. Open `https://www.samsung.com/` in a browser
2. Open DevTools → Elements panel
3. Find the `<iframe>` containing the chat widget
4. Note its `src`, `id`, or `name` attribute
5. Add a targeted selector to `INPUT_CANDIDATES` or add an explicit `frameLocator` call in `resolve_chat_context()` in `app/samsung_chat.py`:

```python
# Example: target a specific iframe by src pattern
frame_loc = page.frame_locator("iframe[src*='chat.samsung.com']")
input_el = frame_loc.locator("textarea").first
```

---

## Expected Failure Points & Debugging

| Failure | Cause | Fix |
|---|---|---|
| Chat icon not found | Selector changed or popup blocking | Update `CHAT_ICON_CANDIDATES`; check screenshot |
| iframe not found | Widget rendered in new iframe src | Inspect DOM; update `resolve_chat_context` |
| Input not found | Input field changed | Update `INPUT_CANDIDATES` |
| Send button not found | Button changed | Update `SEND_BUTTON_CANDIDATES`; fallback to Enter key |
| No answer received | Widget slow or bot unresponsive | Increase `PLAYWRIGHT_TIMEOUT_MS` or `ANSWER_STABLE_CHECKS` |
| OpenAI evaluation failed | Invalid API key or quota exceeded | Check `OPENAI_API_KEY`; check usage dashboard |
| Screenshot save failed | Disk space or permissions | Check `artifacts/` directory permissions |

Check `reports/runtime.log` for full trace of any failure.

---

## OpenAI Cost Notes

- Each test case sends **one API request** to OpenAI for evaluation.
- Prompt size is approximately 500–1000 tokens.
- Use `MAX_QUESTIONS=3` (default) to limit cost during testing.
- Consider using `gpt-4o-mini` for lower-cost evaluation.

---

## Real-Service Automation Notice

> This tool automates interaction with a live production website (`www.samsung.com`).
> - Do **not** run this at high frequency or in parallel (no burst/parallel execution).
> - Respect Samsung's Terms of Service and `robots.txt`.
> - The default GitHub Actions schedule is **once per day** – do not reduce this interval without justification.
> - Always use headless mode in CI to avoid unnecessary resource consumption.

---

## Maintenance Checklist

- [ ] Verify chat icon selector after Samsung website updates
- [ ] Verify bot-message selector after chat widget updates
- [ ] Check OpenAI API key validity monthly
- [ ] Review `summary.md` after each run for regressions
- [ ] Update `OPENAI_MODEL` if the model is deprecated
- [ ] Rotate screenshots storage if disk usage grows
