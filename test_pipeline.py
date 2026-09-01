import os
import sys

# Ensure UTF-8 output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv
from apify_client import ApifyClient
from sheets_manager import SheetsManager
from token_manager import TokenManager
from email_extractor import LeadEmailExtractor

load_dotenv()


def run_live_test():
    print("=" * 80)
    print(" [TEST ACTION] LIVE INTEGRATION & CREDENTIAL TEST (LOW CREDIT USAGE)")
    print("=" * 80)

    # 1. Test Google Sheets Connection
    print("\n--- 1. Testing Google Sheets Connection & Tabs ---")
    spreadsheet_id = os.getenv("SPREADSHEET_ID")
    sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

    if not spreadsheet_id:
        print("  [ERROR] SPREADSHEET_ID is missing from environment / GitHub Secrets!")
        sys.exit(1)
    if not sa_json:
        print("  [ERROR] GOOGLE_SERVICE_ACCOUNT_JSON is missing from environment / GitHub Secrets!")
        sys.exit(1)

    sheets = SheetsManager(spreadsheet_id=spreadsheet_id, service_account_json=sa_json)
    if not sheets.is_connected:
        print("  [ERROR] Could not connect to Google Sheets with provided credentials!")
        sys.exit(1)

    print(f"  [OK] Successfully connected to Google Sheet: '{sheets.spreadsheet.title}'")

    # Verify Tabs
    settings = sheets.load_settings()
    print(f"  [OK] 'Settings' tab: {len(settings['blocked_domains'])} blocked domains, {len(settings['rejection_keywords'])} keywords loaded.")

    existing_leads = sheets.load_existing_leads()
    print(f"  [OK] 'Leads Database' tab: {len(existing_leads)} existing lead(s) found.")

    token_rows = sheets.load_token_records()
    print(f"  [OK] 'Apify_Tokens' tab: {len(token_rows)} account row(s) found.")

    # 2. Test Token Pool & Apify API Connection
    print("\n--- 2. Testing Apify API Connection & Live Balances ---")
    token_manager = TokenManager()
    if token_rows:
        token_manager.load_from_sheet_data(token_rows)
    else:
        print("  [WARNING] No tokens found in 'Apify_Tokens' sheet. Checking fallback APIFY_API_TOKEN...")
        fallback_token = os.getenv("APIFY_API_TOKEN")
        if fallback_token:
            token_manager.tokens = [{
                "api_token": fallback_token,
                "account_name": "Primary Account",
                "password": "",
                "status": "ACTIVE",
                "available_balance_usd": 5.0,
                "last_used_at": "",
                "notes": "Fallback Token",
            }]

    if not token_manager.tokens:
        print("  [ERROR] No Apify tokens available to test!")
        sys.exit(1)

    token_manager.sync_live_balances()
    best_token_record = token_manager.get_best_token()
    if not best_token_record:
        print("  [ERROR] No active tokens with available balance!")
        sys.exit(1)

    print(f"  [OK] Selected Best Active Token: {best_token_record['account_name']} (${best_token_record['available_balance_usd']:.2f} available)")

    # 3. Test 1 Query with minimal posts (max 5 posts to minimize compute cost)
    print("\n--- 3. Testing Live Scraper Execution (Single Query, Max 5 Posts) ---")
    test_query = '"Hiring" AND "Bengaluru" AND "@"'
    client = ApifyClient(best_token_record["api_token"])
    
    run_input = {
        "searchQueries": [test_query],
        "maxPosts": 5,
        "postedLimit": "24h",
        "profileScraperMode": "short",
        "startPage": 1,
        "scrapeReactions": False,
        "scrapeComments": False,
    }

    try:
        print(f"  Triggering test query: {test_query} (max 5 posts)...")
        run = client.actor("buIWk2uOUzTmcLsuB").call(run_input=run_input)
        dataset_id = run.get("defaultDatasetId")
        items = list(client.dataset(dataset_id).iterate_items()) if dataset_id else []
        print(f"  [OK] Successfully scraped {len(items)} test post(s) from LinkedIn in real-time.")
    except Exception as e:
        print(f"  [ERROR] Apify run failed: {e}")
        sys.exit(1)

    # 4. Test Lead Extraction & Filtering
    print("\n--- 4. Testing Lead Extraction & Deduplication ---")
    extractor = LeadEmailExtractor(
        blocked_domains=settings["blocked_domains"],
        rejection_keywords=settings["rejection_keywords"],
        blocked_suffixes=settings["blocked_suffixes"],
        existing_emails=existing_leads,
    )

    test_leads = []
    for item in items:
        leads = extractor.extract_lead_from_post(item, test_query)
        test_leads.extend(leads)

    print(f"  [OK] Extracted {len(test_leads)} filtered fresh lead(s) from test scrape.")

    # 5. Test Google Sheet Sync & Safe Appending
    if test_leads:
        print("\n--- 5. Testing Google Sheet Leads Append ---")
        sheets.append_leads(test_leads[:2]) # Append at most 2 for test
        print("  [OK] Successfully appended test lead(s) to 'Leads Database'.")

    # Update token balances in sheet
    sheets.sync_token_records(token_manager.export_sheet_rows())
    print("  [OK] Successfully synced token pool statuses to 'Apify_Tokens'.")

    print("\n" + "=" * 80)
    print(" [ALL SYSTEMS VERIFIED & OPERATIONAL] Ready for full 62-query automated runs!")
    print("=" * 80)


if __name__ == "__main__":
    run_live_test()
