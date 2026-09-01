import os
import sys

# Ensure UTF-8 output across Windows and Linux environments
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import time
from datetime import datetime, timezone
from dotenv import load_dotenv
from apify_client import ApifyClient

from email_extractor import LeadEmailExtractor
from token_manager import TokenManager, safe_get
from sheets_manager import SheetsManager

load_dotenv()

# ==============================================================================
# CONFIGURATION
# ==============================================================================
ACTOR_ID = "buIWk2uOUzTmcLsuB"
POSTED_LIMIT = "24h"
MAX_POSTS_PER_QUERY = 100
DELAY_BETWEEN_RUNS_SECONDS = 3

# 62 Search Queries for major Indian hiring hubs
SEARCH_QUERIES = [
    # Bengaluru (6)
    '"Hiring" AND "Bengaluru" AND "@"',
    '"Urgent Hiring" AND "Bengaluru" AND "@"',
    '"Immediate Joiner" AND "Bengaluru" AND "@"',
    '"Immediate Joining" AND "Bengaluru" AND "@"',
    '"We\'re Hiring" AND "Bengaluru" AND "@"',
    '"We are hiring" AND "Bengaluru" AND "@"',
    
    # Hyderabad (6)
    '"Hiring" AND "Hyderabad" AND "@"',
    '"Urgent Hiring" AND "Hyderabad" AND "@"',
    '"Immediate Joiner" AND "Hyderabad" AND "@"',
    '"Immediate Joining" AND "Hyderabad" AND "@"',
    '"We\'re Hiring" AND "Hyderabad" AND "@"',
    '"We are hiring" AND "Hyderabad" AND "@"',
    
    # Chennai (6)
    '"Hiring" AND "Chennai" AND "@"',
    '"Urgent Hiring" AND "Chennai" AND "@"',
    '"Immediate Joiner" AND "Chennai" AND "@"',
    '"Immediate Joining" AND "Chennai" AND "@"',
    '"We\'re Hiring" AND "Chennai" AND "@"',
    '"We are hiring" AND "Chennai" AND "@"',
    
    # Mumbai (6)
    '"Hiring" AND "Mumbai" AND "@"',
    '"Urgent Hiring" AND "Mumbai" AND "@"',
    '"Immediate Joiner" AND "Mumbai" AND "@"',
    '"Immediate Joining" AND "Mumbai" AND "@"',
    '"We\'re Hiring" AND "Mumbai" AND "@"',
    '"We are hiring" AND "Mumbai" AND "@"',
    
    # Pune (6)
    '"Hiring" AND "Pune" AND "@"',
    '"Urgent Hiring" AND "Pune" AND "@"',
    '"Immediate Joiner" AND "Pune" AND "@"',
    '"Immediate Joining" AND "Pune" AND "@"',
    '"We\'re Hiring" AND "Pune" AND "@"',
    '"We are hiring" AND "Pune" AND "@"',
    
    # Ahmedabad (6)
    '"Urgent Hiring" AND "Ahmedabad" AND "@"',
    '"Immediate Joiner" AND "Ahmedabad" AND "@"',
    '"Hiring" AND "Ahmedabad" AND "@"',
    '"We\'re Hiring" AND "Ahmedabad" AND "@"',
    '"Immediate Joining" AND "Ahmedabad" AND "@"',
    '"We are hiring" AND "Ahmedabad" AND "@"',
    
    # Noida (7)
    '"Urgent Hiring" AND "Noida" AND "@"',
    '"Immediate Joiner" AND "Noida" AND "@"',
    '"Immediate Joining" AND "Noida" AND "@"',
    '"We\'re Hiring" AND "Noida" AND "@"',
    '"We are hiring" AND "Noida" AND "@"',
    '"Hiring" AND "Noida" AND "@"',
    
    # Delhi (6)
    '"Hiring" AND "Delhi" AND "@"',
    '"Urgent Hiring" AND "Delhi" AND "@"',
    '"Immediate Joiner" AND "Delhi" AND "@"',
    '"Immediate Joining" AND "Delhi" AND "@"',
    '"We\'re Hiring" AND "Delhi" AND "@"',
    '"We are hiring" AND "Delhi" AND "@"',
    
    # Gurugram (6)
    '"Hiring" AND "Gurugram" AND "@"',
    '"Urgent Hiring" AND "Gurugram" AND "@"',
    '"Immediate Joiner" AND "Gurugram" AND "@"',
    '"Immediate Joining" AND "Gurugram" AND "@"',
    '"We\'re Hiring" AND "Gurugram" AND "@"',
    '"We are hiring" AND "Gurugram" AND "@"',
    
    # New Delhi (6)
    '"Hiring" AND "New Delhi" AND "@"',
    '"Urgent Hiring" AND "New Delhi" AND "@"',
    '"Immediate Joiner" AND "New Delhi" AND "@"',
    '"Immediate Joining" AND "New Delhi" AND "@"',
    '"We\'re Hiring" AND "New Delhi" AND "@"',
    '"We are hiring" AND "New Delhi" AND "@"',
]


def run_pipeline(limit_queries: int = 0):
    """
    Executes the complete 24H LinkedIn Lead Extraction Pipeline.
    limit_queries: Set to > 0 for quick test runs (e.g. 1 query). 0 = all 62 queries.
    """
    print("=" * 80)
    print(" [PIPELINE START] LinkedIn 24H Lead Extractor & Apify Google Sheets CRM")
    print("=" * 80)

    # 1. Initialize Sheets Manager using GitHub Secrets (SPREADSHEET_ID & GOOGLE_SERVICE_ACCOUNT_JSON)
    sheets = SheetsManager()
    
    # 2. Load Filter Rules from Settings Tab & Existing leads for deduplication
    settings = sheets.load_settings()
    existing_emails = sheets.load_existing_leads()

    # 3. Initialize Lead Extractor
    extractor = LeadEmailExtractor(
        blocked_domains=settings["blocked_domains"],
        rejection_keywords=settings["rejection_keywords"],
        blocked_suffixes=settings["blocked_suffixes"],
        existing_emails=existing_emails,
    )

    # 4. Initialize Token Manager from 'Apify_Tokens' Google Sheet
    token_rows = sheets.load_token_records()
    token_manager = TokenManager()
    if token_rows:
        token_manager.load_from_sheet_data(token_rows)
        print(f"[TOKEN POOL] Loaded {len(token_manager.tokens)} token(s) from 'Apify_Tokens' sheet.")
    else:
        # Fallback to local token if Google Sheet is not yet populated
        primary_token = os.getenv("APIFY_API_TOKEN", "")
        token_manager.tokens = [{
            "api_token": primary_token,
            "account_name": "Primary Account",
            "password": "",
            "status": "ACTIVE",
            "available_balance_usd": 5.0,
            "last_used_at": "",
            "notes": "Default Seed Token",
        }]

    # Sync live balances for all active tokens from Apify API
    token_manager.sync_live_balances()
    if sheets.is_connected:
        sheets.sync_token_records(token_manager.export_sheet_rows())

    # 5. Load Active Search Queries from 'Queries' Google Sheet tab
    active_queries = sheets.load_queries(default_queries=SEARCH_QUERIES)
    queries_to_run = active_queries[:limit_queries] if limit_queries > 0 else active_queries
    print(f"\n[PIPELINE] Executing {len(queries_to_run)} active search queries (24H window)...")

    total_posts_found = 0
    total_leads_added = 0
    total_cost_usd = 0.0

    for idx, query in enumerate(queries_to_run, start=1):
        print(f"\n[{idx}/{len(queries_to_run)}] Query: {query}")

        # Pick the token with HIGHEST available balance
        best_token_record = token_manager.get_best_token()
        if not best_token_record:
            print("[ERROR] No ACTIVE tokens available in the pool with positive balance!")
            break

        current_token = best_token_record["api_token"]
        print(f"  -> Using Token Account: {best_token_record['account_name']} (Bal: ${best_token_record['available_balance_usd']:.2f})")

        client = ApifyClient(current_token)

        raw_input = {
            "searchQueries": [query],
            "maxPosts": MAX_POSTS_PER_QUERY,
            "postedLimit": POSTED_LIMIT,
            "profileScraperMode": "short",
            "startPage": 1,
            "scrapeReactions": False,
            "reactionsProfileScraperMode": "short",
            "postNestedReactions": False,
            "scrapeComments": False,
            "commentsProfileScraperMode": "short",
            "postNestedComments": False,
        }
        run_input = {k: v for k, v in raw_input.items() if v is not None}

        query_posts = []
        try:
            run = client.actor(ACTOR_ID).call(run_input=run_input)
            dataset_id = safe_get(run, "defaultDatasetId") or safe_get(run, "default_dataset_id")
            
            # Record estimated compute cost
            usage_usd = float(safe_get(run, "usageTotalUsd", 0.01) or safe_get(run, "usage_total_usd", 0.01) or 0.01)
            total_cost_usd += usage_usd
            best_token_record["available_balance_usd"] = max(0.0, best_token_record["available_balance_usd"] - usage_usd)

            if dataset_id:
                query_posts = list(client.dataset(dataset_id).iterate_items())

        except Exception as e:
            err_msg = str(e)
            print(f"  [ERROR] on query '{query}': {err_msg}")
            if "429" in err_msg or "quota" in err_msg.lower() or "401" in err_msg:
                token_manager.mark_exhausted(current_token, "Quota Exceeded")
            continue

        total_posts_found += len(query_posts)
        print(f"  -> Scraped {len(query_posts)} posts.")

        # Extract & Filter leads into 5 columns
        query_leads = []
        for post in query_posts:
            leads = extractor.extract_lead_from_post(post, query)
            query_leads.extend(leads)

        if query_leads:
            sheets.append_leads(query_leads)
            total_leads_added += len(query_leads)
            print(f"  -> Extracted & Appended {len(query_leads)} fresh leads to Google Sheet (Total: {total_leads_added})")
        else:
            print("  -> 0 new fresh leads (filtered or already exists in Leads Database).")

        if idx < len(queries_to_run):
            time.sleep(DELAY_BETWEEN_RUNS_SECONDS)

    # 6. Compute & Record Daily Analytics
    avg_posts_per_query = total_posts_found / max(1, len(queries_to_run))
    avg_cost_per_query = total_cost_usd / max(1, len(queries_to_run))
    avg_cost_per_lead = total_cost_usd / max(1, total_leads_added)

    analytics_record = {
        "Date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "Day_of_Week": datetime.now(timezone.utc).strftime("%A"),
        "Queries_Run": len(queries_to_run),
        "Posts_Found": total_posts_found,
        "Leads_Extracted": total_leads_added,
        "Avg_Posts_Per_Query": avg_posts_per_query,
        "Total_Cost_USD": total_cost_usd,
        "Avg_Cost_Per_Query_USD": avg_cost_per_query,
        "Avg_Cost_Per_Lead_USD": avg_cost_per_lead,
    }

    sheets.append_daily_analytics(analytics_record)

    # 7. Final Token Pool Sync to Google Sheet
    if sheets.is_connected:
        sheets.sync_token_records(token_manager.export_sheet_rows())

    print("\n" + "=" * 80)
    print(" [SUMMARY] Daily Pipeline Execution Report")
    print(f" * Date & Day of Week      : {analytics_record['Date']} ({analytics_record['Day_of_Week']})")
    print(f" * Queries Processed       : {len(queries_to_run)}")
    print(f" * Total Posts Found       : {total_posts_found}")
    print(f" * Fresh Leads Saved (5 Col): {total_leads_added}")
    print(f" * Avg Posts / Query       : {avg_posts_per_query:.1f}")
    print(f" * Estimated Apify Cost    : ${total_cost_usd:.3f}")
    print(f" * Avg Cost / Query        : ${avg_cost_per_query:.4f}")
    print(f" * Avg Cost / Fresh Lead   : ${avg_cost_per_lead:.4f}")
    print("=" * 80)


if __name__ == "__main__":
    limit = int(os.getenv("LIMIT_QUERIES", "0"))
    run_pipeline(limit_queries=limit)
