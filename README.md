# LinkedIn 24H Lead Extractor & Apify Multi-Token Pool (Google Sheets CRM)

Automated system that runs on **GitHub Actions** to scrape LinkedIn hiring posts, extract clean business leads into a strict **5-column CRM schema**, filter out generic/blocked domains and keywords via dynamic **Google Sheet Settings**, manage and rotate an **unlimited pool of Apify API tokens** based on live available balances, and **manage all search queries directly in Google Sheets** with day-of-week cost and yield metrics.

---

## 📁 Repository Structure

```
├── .github/workflows/
│   ├── scrape_daily.yml      # Main 24H lead extractor workflow (Manual execution)
│   └── test_pipeline.yml     # Lightweight integration test workflow (Low credit usage)
├── Code.gs                   # Google Apps Script to auto-create & format all 5 sheets (Safe-Sync)
├── main.py                   # Main pipeline orchestrator
├── email_extractor.py        # 5-column lead extractor & 4-stage filter engine
├── token_manager.py          # Multi-token pool manager with live balance tracking & failover
├── sheets_manager.py         # Google Sheets synchronization engine (non-destructive, column-safe)
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variables template
├── .gitignore                # Protects secrets, local archives, and tokens from git
└── README.md                 # Documentation
```

---

## 📊 Google Sheets Setup (5 Auto-Generated Tabs)

The Google Apps Script (`Code.gs`) is designed to be **100% non-destructive**:
- It **never deletes** your sheets, custom columns, or existing rows.
- You can add, edit, or disable search queries in real time without touching code.
- You can add as many Apify tokens & passwords as you want.

### Quick Setup:
1. Open your Google Sheet.
2. Navigate to **Extensions > Apps Script**.
3. Copy and paste the entire content of [`Code.gs`](file:///d:/Codinf%20projets/apify-bot-/Code.gs) into the script editor.
4. Click **Save (Ctrl+S)**, select the `safeSyncSheets` function, and click **Run**.
5. Your Google Sheet will have all 5 styled tabs:
   - **`Leads Database`**: 5 core columns (`Email`, `Domain`, `Phone Number`, `Name`, `Query`) + any custom columns you add.
   - **`Queries`**: Search queries managed directly in the sheet with `Enabled` toggles (`TRUE`/`FALSE`).
   - **`Settings`**: Configurable filter lists for *Blocked Domains*, *Rejection Keywords*, and *Blocked Suffixes*.
   - **`Apify_Tokens`**: Unlimited account slots with `api_token`, `account_name`, `password`, `status`, `available_balance_usd`, `last_used_at`, and `notes`.
   - **`Daily_Analytics`**: Historical logs tracking date, day of week, queries run, posts found, leads extracted, cost per query, and cost per lead.

---

## ⚙️ GitHub Actions Deployment (Only 2 Secrets Needed)

All search queries, Apify tokens, filter rules, and lead lists are retrieved directly from your Google Sheet. You only need to add **2 secrets** to GitHub:

1. In your GitHub repository, go to **Settings > Secrets and variables > Actions**.
2. Add the following **2 Repository Secrets**:
   - `SPREADSHEET_ID`: The ID of your Google Sheet (from the URL: `https://docs.google.com/spreadsheets/d/<SPREADSHEET_ID>/edit`).
   - `GOOGLE_SERVICE_ACCOUNT_JSON`: The complete JSON key file content of your Google Cloud Service Account (make sure you share your Google Sheet with the Service Account email as **Editor**).
3. In the **Actions** tab on GitHub:
   - Run **`Test Integration (Low Credit Test)`** to verify connections with a small 5-post test.
   - Run **`24H LinkedIn Lead Extractor & Analytics`** to execute the full pipeline.

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
