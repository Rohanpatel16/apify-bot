# LinkedIn 24H Lead Extractor & Apify 50-Token Pool (Google Sheets CRM)

Automated system that runs on **GitHub Actions** every 24 hours to scrape LinkedIn hiring posts across **62 boolean search queries** for major Indian tech hubs, extract clean business leads into a strict **5-column CRM schema**, filter out generic/blocked domains and keywords via dynamic **Google Sheet Settings**, and intelligently rotate a **pool of 50 Apify API tokens** based on live available balances while tracking day-of-week cost and yield metrics.

---

## 📁 Repository Structure

```
├── .github/workflows/
│   └── scrape_daily.yml      # GitHub Actions daily (24h) cron workflow
├── Code.gs                   # Google Apps Script to auto-create & format all 4 sheets (Safe-Sync)
├── main.py                   # Main pipeline orchestrator
├── email_extractor.py        # 5-column lead extractor & 4-stage filter engine
├── token_manager.py          # 50-token pool manager with live balance tracking & failover
├── sheets_manager.py         # Google Sheets synchronization engine (non-destructive, column-safe)
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variables template
├── .gitignore                # Protects secrets, local archives, and tokens from git
└── README.md                 # Documentation
```

---

## 📊 Google Sheets Setup (Non-Destructive Safe Sync)

The Google Apps Script (`Code.gs`) is designed to be **100% non-destructive**:
- It **never deletes** your sheets, custom columns, or existing rows.
- If you add custom columns (e.g. `Outreach Status`, `Notes`, `Flagged`, `Assigned To`), the script and python bot will **preserve them completely**.
- If you already pasted your 50 Apify tokens and passwords, running the script **never overwrites or clears them**.

### Quick Setup:
1. Open your Google Sheet.
2. Navigate to **Extensions > Apps Script**.
3. Copy and paste the entire content of [`Code.gs`](file:///d:/Codinf%20projets/apify-bot-/Code.gs) into the script editor.
4. Click **Save (Ctrl+S)**, select the `safeSyncSheets` function, and click **Run**.
5. Your Google Sheet will have all 4 styled tabs:
   - **`Leads Database`**: 5 core columns (`Email`, `Domain`, `Phone Number`, `Name`, `Query`) + any custom columns you add.
   - **`Settings`**: Configurable filter lists for *Blocked Domains*, *Rejection Keywords*, and *Blocked Suffixes*.
   - **`Apify_Tokens`**: 50 account slots with `api_token`, `account_name`, `password`, `status`, `available_balance_usd`, `last_used_at`, and `notes`.
   - **`Daily_Analytics`**: Historical logs tracking date, day of week, queries run, posts found, leads extracted, cost per query, and cost per lead.

---

## ⚙️ GitHub Actions Deployment (Only 2 Secrets Needed)

All 50 Apify tokens, filter rules, and lead lists are retrieved directly from your Google Sheet. You only need to add **2 secrets** to GitHub:

1. In your GitHub repository, go to **Settings > Secrets and variables > Actions**.
2. Add the following **2 Repository Secrets**:
   - `SPREADSHEET_ID`: The ID of your Google Sheet (from the URL: `https://docs.google.com/spreadsheets/d/<SPREADSHEET_ID>/edit`).
   - `GOOGLE_SERVICE_ACCOUNT_JSON`: The complete JSON key file content of your Google Cloud Service Account (make sure you share your Google Sheet with the Service Account email as **Editor**).
3. The workflow in [`.github/workflows/scrape_daily.yml`](file:///d:/Codinf%20projets/apify-bot-/.github/workflows/scrape_daily.yml) will automatically trigger every 24 hours at 06:00 UTC (11:30 AM IST) or whenever you click **Run workflow** in the **Actions** tab.

---

## 💻 Local Execution

To test or run locally:
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment in .env
SPREADSHEET_ID=your_spreadsheet_id_here
GOOGLE_SERVICE_ACCOUNT_JSON={"type": "service_account", ...}

# 3. Run pipeline
python main.py
```
