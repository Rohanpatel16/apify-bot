import os
import sys

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv
from sheets_manager import SheetsManager
from token_manager import TokenManager

load_dotenv()


def sync_all_token_balances():
    print("=" * 80)
    print(" [SYNC BALANCES ONLY] Refreshing Live Apify Balances in Google Sheets")
    print("=" * 80)

    sheets = SheetsManager()
    token_manager = TokenManager()

    token_rows = sheets.load_token_records()
    if not token_rows:
        fallback_token = os.getenv("APIFY_API_TOKEN")
        if fallback_token:
            token_rows = [[fallback_token, "Primary Account", "", "ACTIVE", "5.00", "", "Default Seed"]]

    if not token_rows:
        print("[ERROR] No tokens found in 'Apify_Tokens' sheet or environment!")
        sys.exit(1)

    token_manager.load_from_sheet_data(token_rows)
    print(f"\n[TOKEN POOL] Loaded {len(token_manager.tokens)} token(s) from sheet.")

    # Query live limits for each token from Apify API
    token_manager.sync_live_balances()

    # Sync updated rows back to Google Sheets
    if sheets.is_connected:
        sheets.sync_token_records(token_manager.export_sheet_rows())
        print("\n[SHEETS MANAGER] Successfully updated all token balances in Google Sheets.")
    else:
        print("\n[SHEETS MANAGER] Running locally without Google Sheets connection.")

    # Summary
    viable_count = sum(
        1 for t in token_manager.tokens
        if t["status"] == "ACTIVE" and t.get("available_balance_usd", 0.0) >= token_manager.min_viable_balance
    )
    total_count = len(token_manager.tokens)
    print("\n" + "=" * 80)
    print(f" [SUMMARY] {viable_count}/{total_count} account(s) are ACTIVE & VIABLE (>= ${token_manager.min_viable_balance:.2f})")
    print("=" * 80)


if __name__ == "__main__":
    sync_all_token_balances()
