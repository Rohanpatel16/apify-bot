import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
import pandas as pd

try:
    # pyrefly: ignore [missing-import]
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False


class SheetsManager:
    """
    Non-destructive, Column-Safe Google Sheets Manager:
    - Never deletes existing user sheets, data, or custom columns.
    - Matches headers dynamically by name.
    - Preserves any custom columns added to the right of standard columns.
    - Dynamically loads search queries, filter settings, tokens, and leads.
    """

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    def __init__(self, spreadsheet_id: Optional[str] = None, service_account_json: Optional[str] = None):
        self.spreadsheet_id = spreadsheet_id or os.getenv("SPREADSHEET_ID")
        self.service_account_json = service_account_json or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        self.client = None
        self.spreadsheet = None
        self.is_connected = False

        self._init_connection()

    def _init_connection(self):
        """Initializes gspread connection with Service Account if provided."""
        if not GSPREAD_AVAILABLE or not self.service_account_json or not self.spreadsheet_id:
            print("[SHEETS MANAGER] Running in Local Storage Mode (No Service Account JSON provided).")
            return

        try:
            if os.path.exists(self.service_account_json):
                creds = Credentials.from_service_account_file(self.service_account_json, scopes=self.SCOPES)
            else:
                info = json.loads(self.service_account_json)
                creds = Credentials.from_service_account_info(info, scopes=self.SCOPES)

            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            self.is_connected = True
            print(f"[SHEETS MANAGER] Connected to Google Spreadsheet: '{self.spreadsheet.title}'")
        except Exception as e:
            print(f"[SHEETS MANAGER] Warning: Could not connect to Google Sheets ({e}). Falling back to Local Mode.")
            self.is_connected = False

    def load_queries(self, default_queries: Optional[List[str]] = None) -> List[str]:
        """
        Loads active search queries from the 'Queries' tab in Google Sheets.
        Respects the 'Enabled' column (TRUE/FALSE) so users can toggle queries easily.
        """
        defaults = default_queries or []
        if not self.is_connected:
            return defaults

        try:
            sheet = self.spreadsheet.worksheet("Queries")
            data = sheet.get_all_values()
            if len(data) > 1:
                headers = [h.strip().lower() for h in data[0]]
                q_idx = headers.index("query") if "query" in headers else 0
                en_idx = headers.index("enabled") if "enabled" in headers else 2

                loaded_queries = []
                for row in data[1:]:
                    if len(row) > q_idx and row[q_idx].strip():
                        query_text = row[q_idx].strip()
                        enabled = True
                        if len(row) > en_idx and row[en_idx].strip():
                            en_str = row[en_idx].strip().upper()
                            if en_str in ("FALSE", "0", "NO", "DISABLED", "OFF"):
                                enabled = False
                        if enabled:
                            loaded_queries.append(query_text)

                if loaded_queries:
                    print(f"[SHEETS MANAGER] Loaded {len(loaded_queries)} enabled search query/queries from 'Queries' tab.")
                    return loaded_queries
        except Exception as e:
            print(f"[SHEETS MANAGER] Note reading 'Queries' tab ({e}). Using default query list.")

        return defaults

    def load_settings(self) -> Dict[str, Set[str]]:
        """Loads filter rules from 'Settings' tab dynamically."""
        default_settings = {
            "blocked_domains": {
                "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
                "icloud.com", "zoho.com", "mail.com", "protonmail.com"
            },
            "rejection_keywords": {
                "consultancy", "hr", "recruitment", "career", "careers",
                "contact", "hire", "support", "jobs", "staffing", "apply"
            },
            "blocked_suffixes": {
                ".edu", ".ac.in", ".gov", ".mil", ".org", ".int", ".uk", ".ca",
                ".au", ".xyz", ".top", ".site", ".club", ".online", ".dev"
            }
        }

        if not self.is_connected:
            return default_settings

        try:
            sheet = self.spreadsheet.worksheet("Settings")
            data = sheet.get_all_values()
            if len(data) > 1:
                headers = [h.strip().lower() for h in data[0]]
                d_idx = headers.index("blocked domains") if "blocked domains" in headers else 0
                k_idx = headers.index("rejection keywords") if "rejection keywords" in headers else 1
                s_idx = headers.index("blocked suffixes") if "blocked suffixes" in headers else 2

                blocked_domains = {r[d_idx].strip().lower() for r in data[1:] if len(r) > d_idx and r[d_idx].strip()}
                rejection_keywords = {r[k_idx].strip().lower() for r in data[1:] if len(r) > k_idx and r[k_idx].strip()}
                blocked_suffixes = {r[s_idx].strip().lower() for r in data[1:] if len(r) > s_idx and r[s_idx].strip()}
                
                return {
                    "blocked_domains": blocked_domains or default_settings["blocked_domains"],
                    "rejection_keywords": rejection_keywords or default_settings["rejection_keywords"],
                    "blocked_suffixes": blocked_suffixes or default_settings["blocked_suffixes"],
                }
        except Exception as e:
            print(f"[SHEETS MANAGER] Note reading Settings tab: {e}")

        return default_settings

    def load_existing_leads(self) -> Set[str]:
        """Fetches all existing emails from Email column of 'Leads Database'."""
        existing_emails = set()
        if self.is_connected:
            try:
                sheet = self.spreadsheet.worksheet("Leads Database")
                headers = [h.strip().lower() for h in sheet.row_values(1)]
                email_col = (headers.index("email") + 1) if "email" in headers else 1
                col_vals = sheet.col_values(email_col)
                existing_emails = {e.strip().lower() for e in col_vals[1:] if e.strip()}
                print(f"[SHEETS MANAGER] Loaded {len(existing_emails)} existing lead(s) for deduplication.")
            except Exception as e:
                print(f"[SHEETS MANAGER] Note loading existing leads: {e}")
        else:
            local_csv = "leads_database.csv"
            if os.path.exists(local_csv):
                df = pd.read_csv(local_csv)
                if "Email" in df.columns:
                    existing_emails = {str(e).strip().lower() for e in df["Email"] if str(e).strip()}
        return existing_emails

    def load_token_records(self) -> List[List[str]]:
        """Reads rows from 'Apify_Tokens' tab."""
        if self.is_connected:
            try:
                sheet = self.spreadsheet.worksheet("Apify_Tokens")
                return sheet.get_all_values()[1:]
            except Exception as e:
                print(f"[SHEETS MANAGER] Note loading Apify_Tokens sheet: {e}")
        return []

    def sync_token_records(self, token_rows: List[List]):
        """
        Updates 'Apify_Tokens' sheet with latest balances and statuses without deleting custom columns.
        """
        if self.is_connected and token_rows:
            try:
                sheet = self.spreadsheet.worksheet("Apify_Tokens")
                sheet.update(range_name=f"A2:G{len(token_rows)+1}", values=token_rows)
                print("[SHEETS MANAGER] Safely synced token pool to Google Sheet.")
            except Exception as e:
                print(f"[SHEETS MANAGER] Failed updating Apify_Tokens: {e}")

    def append_leads(self, leads: List[Dict[str, str]]):
        """
        Appends clean 5-column leads to 'Leads Database' (Columns A to E),
        preserving any additional user-defined custom columns.
        """
        if not leads:
            return

        rows = [
            [
                l.get("Email", ""),
                l.get("Domain", ""),
                l.get("Phone Number", ""),
                l.get("Name", ""),
                l.get("Query", ""),
            ]
            for l in leads
        ]

        if self.is_connected:
            try:
                sheet = self.spreadsheet.worksheet("Leads Database")
                sheet.append_rows(rows, value_input_option="USER_ENTERED")
                print(f"[SHEETS MANAGER] Appended {len(rows)} fresh leads to 'Leads Database' Google Sheet.")
            except Exception as e:
                print(f"[SHEETS MANAGER] Error appending leads to sheet: {e}")

        # Local CSV Backup
        local_csv = "leads_database.csv"
        df_new = pd.DataFrame(rows, columns=["Email", "Domain", "Phone Number", "Name", "Query"])
        if os.path.exists(local_csv):
            df_new.to_csv(local_csv, mode="a", index=False, header=False, encoding="utf-8-sig")
        else:
            df_new.to_csv(local_csv, index=False, encoding="utf-8-sig")

    def append_daily_analytics(self, analytics_record: Dict):
        """
        Appends a summary row to 'Daily_Analytics' tab without overwriting historical records.
        """
        row = [
            analytics_record.get("Date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
            analytics_record.get("Day_of_Week", datetime.now(timezone.utc).strftime("%A")),
            analytics_record.get("Queries_Run", 0),
            analytics_record.get("Posts_Found", 0),
            analytics_record.get("Leads_Extracted", 0),
            round(analytics_record.get("Avg_Posts_Per_Query", 0.0), 1),
            f"${analytics_record.get('Total_Cost_USD', 0.0):.3f}",
            f"${analytics_record.get('Avg_Cost_Per_Query_USD', 0.0):.4f}",
            f"${analytics_record.get('Avg_Cost_Per_Lead_USD', 0.0):.4f}",
        ]

        if self.is_connected:
            try:
                sheet = self.spreadsheet.worksheet("Daily_Analytics")
                sheet.append_row(row, value_input_option="USER_ENTERED")
                print("[SHEETS MANAGER] Recorded daily analytics to Google Sheet.")
            except Exception as e:
                print(f"[SHEETS MANAGER] Error writing Daily_Analytics: {e}")

        # Local CSV Backup
        local_csv = "daily_analytics.csv"
        cols = [
            "Date", "Day_of_Week", "Queries_Run", "Posts_Found", "Leads_Extracted",
            "Avg_Posts_Per_Query", "Total_Cost_USD", "Avg_Cost_Per_Query_USD", "Avg_Cost_Per_Lead_USD"
        ]
        df_new = pd.DataFrame([row], columns=cols)
        if os.path.exists(local_csv):
            df_new.to_csv(local_csv, mode="a", index=False, header=False, encoding="utf-8-sig")
        else:
            df_new.to_csv(local_csv, index=False, encoding="utf-8-sig")
