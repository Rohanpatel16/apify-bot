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


def col_index_to_letter(col_idx: int) -> str:
    """Converts a 1-based column index to an Excel/Sheets column letter (e.g. 1 -> A, 27 -> AA)."""
    result = ""
    while col_idx > 0:
        col_idx, remainder = divmod(col_idx - 1, 26)
        result = chr(65 + remainder) + result
    return result


STANDARD_SCHEMAS = {
    "Leads Database": {
        "headers": ["Email", "Domain", "Phone Number", "Name", "Query", "Date"],
        "header_bg": "#1A73E8",
        "header_fg": "#FFFFFF",
        "widths": [260, 180, 170, 200, 300, 150],
    },
    "Queries": {
        "headers": ["Query", "City", "Enabled", "Notes"],
        "header_bg": "#009688",
        "header_fg": "#FFFFFF",
        "widths": [380, 150, 100, 150],
    },
    "Settings": {
        "headers": ["Blocked Domains", "Rejection Keywords", "Blocked Suffixes"],
        "header_bg": "#34A853",
        "header_fg": "#FFFFFF",
        "widths": [220, 220, 200],
    },
    "Apify_Tokens": {
        "headers": ["api_token", "account_name", "password", "status", "available_balance_usd", "last_used_at", "notes"],
        "header_bg": "#FBBC05",
        "header_fg": "#202124",
        "widths": [350, 160, 160, 120, 170, 200, 200],
    },
    "Daily_Analytics": {
        "headers": [
            "Date", "Day_of_Week", "Queries_Run", "Posts_Found", "Leads_Extracted",
            "Avg_Posts_Per_Query", "Total_Cost_USD", "Avg_Cost_Per_Query_USD", "Avg_Cost_Per_Lead_USD"
        ],
        "header_bg": "#9334E8",
        "header_fg": "#FFFFFF",
        "widths": [160] * 9,
    },
}


class SheetsManager:
    """
    Non-destructive, Column-Safe Google Sheets Manager:
    - Auto-checks every sheet tab for any missing standard columns.
    - Non-destructively appends missing columns without deleting or modifying existing user data or custom columns.
    - Dynamically maps data rows by column header names on both read and write operations.
    - Preserves user-added custom columns, passwords, statuses, and historical notes.
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
        self.auto_check_and_sync_all_sheets()

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

    def ensure_worksheet_schema(self, sheet_name: str) -> List[str]:
        """
        Non-destructive schema verification for a given tab:
        1. Checks if worksheet exists; if not, creates it with standard headers.
        2. If worksheet exists, inspects row 1 headers.
        3. Finds any standard columns that are missing (case-insensitive match).
        4. Appends missing columns to row 1 after existing columns.
        5. NEVER deletes or modifies existing rows, data cells, or custom columns.
        Returns the list of current headers (in row 1).
        """
        if not self.is_connected or not self.spreadsheet:
            return STANDARD_SCHEMAS.get(sheet_name, {}).get("headers", [])

        schema = STANDARD_SCHEMAS.get(sheet_name)
        if not schema:
            return []

        required_headers = schema["headers"]

        try:
            # 1. Check if sheet exists
            try:
                sheet = self.spreadsheet.worksheet(sheet_name)
            except Exception:
                sheet = self.spreadsheet.add_worksheet(title=sheet_name, rows=100, cols=max(20, len(required_headers) + 5))
                print(f"[SHEETS MANAGER] Created missing sheet: '{sheet_name}'")

            # 2. Check existing row 1 headers
            row_1 = sheet.row_values(1)

            if not row_1:
                # Completely empty sheet: insert all standard headers
                sheet.update(range_name=f"A1:{col_index_to_letter(len(required_headers))}1", values=[required_headers])
                try:
                    sheet.freeze(rows=1)
                except Exception:
                    pass
                print(f"[SHEETS MANAGER] Initialized headers for empty sheet: '{sheet_name}'")
                return list(required_headers)

            # 3. Check for any missing headers
            existing_normalized = [h.strip().lower() for h in row_1]
            missing_headers = [
                h for h in required_headers
                if h.strip().lower() not in existing_normalized
            ]

            if missing_headers:
                start_col = len(row_1) + 1
                end_col = start_col + len(missing_headers) - 1
                start_letter = col_index_to_letter(start_col)
                end_letter = col_index_to_letter(end_col)
                range_name = f"{start_letter}1:{end_letter}1"

                # Append missing headers to row 1 without touching any existing cells or rows
                sheet.update(range_name=range_name, values=[missing_headers])
                print(
                    f"[SHEETS MANAGER] Tab '{sheet_name}': Non-destructively added missing column(s) "
                    f"{missing_headers} at {range_name}. All existing data preserved."
                )
                return row_1 + missing_headers

            return row_1

        except Exception as e:
            print(f"[SHEETS MANAGER] Note during schema check for '{sheet_name}': {e}")
            return required_headers

    def auto_check_and_sync_all_sheets(self):
        """
        Auto-checks all 5 standard sheets upon connection.
        Verifies that all standard columns exist and non-destructively adds any missing ones.
        """
        if self.is_connected:
            print("[SHEETS MANAGER] Running automatic column sync across all sheets...")
            for sheet_name in STANDARD_SCHEMAS:
                self.ensure_worksheet_schema(sheet_name)
            print("[SHEETS MANAGER] All Google Sheet tabs verified and in sync (zero data loss).")
        else:
            self._sync_local_csv_schemas()

    def _sync_local_csv_schemas(self):
        """Ensures local CSV backup files have all expected columns without losing data."""
        # 1. Leads Database CSV
        leads_csv = "leads_database.csv"
        leads_expected = STANDARD_SCHEMAS["Leads Database"]["headers"]
        if os.path.exists(leads_csv):
            try:
                df = pd.read_csv(leads_csv)
                missing = [c for c in leads_expected if c not in df.columns]
                if missing:
                    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    for c in missing:
                        df[c] = today_str if c.lower() == "date" else ""
                    df.to_csv(leads_csv, index=False, encoding="utf-8-sig")
                    print(f"[SHEETS MANAGER] Local '{leads_csv}': Added missing column(s) {missing} safely.")
            except Exception as e:
                print(f"[SHEETS MANAGER] Note syncing local leads CSV: {e}")

        # 2. Daily Analytics CSV
        analytics_csv = "daily_analytics.csv"
        analytics_expected = STANDARD_SCHEMAS["Daily_Analytics"]["headers"]
        if os.path.exists(analytics_csv):
            try:
                df = pd.read_csv(analytics_csv)
                missing = [c for c in analytics_expected if c not in df.columns]
                if missing:
                    for c in missing:
                        df[c] = ""
                    df.to_csv(analytics_csv, index=False, encoding="utf-8-sig")
                    print(f"[SHEETS MANAGER] Local '{analytics_csv}': Added missing column(s) {missing} safely.")
            except Exception as e:
                print(f"[SHEETS MANAGER] Note syncing local analytics CSV: {e}")

    def load_queries(self, default_queries: Optional[List[str]] = None) -> List[str]:
        """
        Loads active search queries from the 'Queries' tab in Google Sheets.
        Auto-checks for missing columns ('Query', 'City', 'Enabled', 'Notes') and ensures they exist.
        Respects the 'Enabled' column (TRUE/FALSE) so users can toggle queries easily.
        """
        defaults = default_queries or []
        if not self.is_connected:
            return defaults

        try:
            current_headers = self.ensure_worksheet_schema("Queries")
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
        """Loads filter rules from 'Settings' tab dynamically with missing column auto-check."""
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
            self.ensure_worksheet_schema("Settings")
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
        """Fetches all existing emails dynamically by finding 'Email' column in 'Leads Database'."""
        existing_emails = set()
        if self.is_connected:
            try:
                current_headers = self.ensure_worksheet_schema("Leads Database")
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
                try:
                    df = pd.read_csv(local_csv)
                    for col in df.columns:
                        if col.strip().lower() == "email":
                            existing_emails = {str(e).strip().lower() for e in df[col] if str(e).strip() and str(e).strip().lower() != "nan"}
                            break
                except Exception:
                    pass
        return existing_emails

    def load_token_records(self) -> List[List[str]]:
        """
        Reads rows from 'Apify_Tokens' tab dynamically by column name.
        Preserves passwords, balances, notes, and custom columns.
        """
        if self.is_connected:
            try:
                self.ensure_worksheet_schema("Apify_Tokens")
                sheet = self.spreadsheet.worksheet("Apify_Tokens")
                all_values = sheet.get_all_values()
                if len(all_values) <= 1:
                    return []

                header_map = {h.strip().lower(): idx for idx, h in enumerate(all_values[0])}
                standard_keys = [
                    "api_token", "account_name", "password", "status",
                    "available_balance_usd", "last_used_at", "notes"
                ]

                normalized_rows = []
                for r in all_values[1:]:
                    if not any(str(cell).strip() for cell in r):
                        continue

                    row_item = []
                    for k in standard_keys:
                        col_idx = header_map.get(k)
                        val = r[col_idx].strip() if (col_idx is not None and col_idx < len(r)) else ""
                        row_item.append(val)
                    normalized_rows.append(row_item)

                return normalized_rows
            except Exception as e:
                print(f"[SHEETS MANAGER] Note loading Apify_Tokens sheet: {e}")
        return []

    def sync_token_records(self, token_rows: List[List]):
        """
        Updates 'Apify_Tokens' sheet with latest balances and statuses.
        - Automatically verifies standard columns exist.
        - Matches headers dynamically by name.
        - Preserves passwords if the update row has an empty password.
        - Preserves any custom user columns added to the sheet.
        """
        if not self.is_connected or not token_rows:
            return

        try:
            current_headers = self.ensure_worksheet_schema("Apify_Tokens")
            sheet = self.spreadsheet.worksheet("Apify_Tokens")
            header_map = {h.strip().lower(): idx for idx, h in enumerate(current_headers)}

            standard_keys = [
                "api_token", "account_name", "password", "status",
                "available_balance_usd", "last_used_at", "notes"
            ]

            is_standard_contiguous = (
                len(current_headers) >= 7 and
                all(header_map.get(k) == i for i, k in enumerate(standard_keys))
            )

            if is_standard_contiguous and len(current_headers) == 7:
                sheet.update(range_name=f"A2:G{len(token_rows)+1}", values=token_rows)
                print("[SHEETS MANAGER] Safely synced token pool to Google Sheet (Columns A to G).")
            else:
                existing_values = sheet.get_all_values()
                num_existing_data_rows = max(0, len(existing_values) - 1)
                total_rows_count = max(len(token_rows), num_existing_data_rows)
                total_cols = max(len(current_headers), 7)

                merged_rows = []
                for r_idx in range(total_rows_count):
                    if r_idx + 1 < len(existing_values):
                        row_data = list(existing_values[r_idx + 1]) + [""] * (total_cols - len(existing_values[r_idx + 1]))
                    else:
                        row_data = [""] * total_cols

                    if r_idx < len(token_rows):
                        token_item = token_rows[r_idx]
                        for key_idx, key in enumerate(standard_keys):
                            col_idx = header_map.get(key)
                            if col_idx is not None and col_idx < total_cols:
                                new_val = token_item[key_idx] if key_idx < len(token_item) else ""
                                # If incoming password is empty, preserve existing password from sheet
                                if key == "password" and not new_val and row_data[col_idx]:
                                    continue
                                row_data[col_idx] = new_val

                    merged_rows.append(row_data)

                end_letter = col_index_to_letter(total_cols)
                sheet.update(range_name=f"A2:{end_letter}{len(merged_rows)+1}", values=merged_rows)
                print(f"[SHEETS MANAGER] Safely synced token pool across {total_cols} columns preserving custom columns and passwords.")
        except Exception as e:
            print(f"[SHEETS MANAGER] Failed updating Apify_Tokens: {e}")

    def append_leads(self, leads: List[Dict[str, str]]):
        """
        Appends clean leads to 'Leads Database'.
        - Auto-checks for missing columns (e.g. Date) and adds them non-destructively.
        - Dynamically maps fields to actual header positions.
        - Preserves any custom user columns without shifting or overwriting data.
        """
        if not leads:
            return

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if self.is_connected:
            try:
                current_headers = self.ensure_worksheet_schema("Leads Database")
                sheet = self.spreadsheet.worksheet("Leads Database")

                header_map = {h.strip().lower(): idx for idx, h in enumerate(current_headers)}
                total_cols = max(len(current_headers), 6)

                rows = []
                for l in leads:
                    row = [""] * total_cols
                    field_mapping = {
                        "email": l.get("Email", ""),
                        "domain": l.get("Domain", ""),
                        "phone number": l.get("Phone Number", ""),
                        "name": l.get("Name", ""),
                        "query": l.get("Query", ""),
                        "date": l.get("Date") or today_str,
                    }

                    for field_key, val in field_mapping.items():
                        if field_key in header_map:
                            row[header_map[field_key]] = val

                    rows.append(row)

                sheet.append_rows(rows, value_input_option="USER_ENTERED")
                print(f"[SHEETS MANAGER] Appended {len(rows)} fresh leads to 'Leads Database' Google Sheet (dynamically mapped across {total_cols} columns).")
            except Exception as e:
                print(f"[SHEETS MANAGER] Error appending leads to sheet: {e}")

        # Local CSV Backup with automatic schema alignment
        self._append_leads_local_csv(leads, today_str)

    def _append_leads_local_csv(self, leads: List[Dict[str, str]], today_str: str):
        """Saves leads to local CSV backup, non-destructively ensuring columns are present."""
        local_csv = "leads_database.csv"
        standard_cols = STANDARD_SCHEMAS["Leads Database"]["headers"]

        new_records = []
        for l in leads:
            new_records.append({
                "Email": l.get("Email", ""),
                "Domain": l.get("Domain", ""),
                "Phone Number": l.get("Phone Number", ""),
                "Name": l.get("Name", ""),
                "Query": l.get("Query", ""),
                "Date": l.get("Date") or today_str,
            })

        df_new = pd.DataFrame(new_records)

        if os.path.exists(local_csv):
            try:
                existing_df = pd.read_csv(local_csv)
                # Ensure missing columns are added to existing_df safely
                for col in standard_cols:
                    if col not in existing_df.columns:
                        existing_df[col] = today_str if col == "Date" else ""
                
                # Align columns
                all_cols = list(existing_df.columns)
                for col in standard_cols:
                    if col not in all_cols:
                        all_cols.append(col)

                df_new = df_new.reindex(columns=all_cols, fill_value="")
                existing_df = existing_df.reindex(columns=all_cols, fill_value="")
                
                combined_df = pd.concat([existing_df, df_new], ignore_index=True)
                combined_df.to_csv(local_csv, index=False, encoding="utf-8-sig")
            except Exception as e:
                print(f"[SHEETS MANAGER] Error updating local leads CSV: {e}")
                df_new.to_csv(local_csv, mode="a", index=False, header=False, encoding="utf-8-sig")
        else:
            df_new.to_csv(local_csv, index=False, encoding="utf-8-sig")

    def append_daily_analytics(self, analytics_record: Dict):
        """
        Appends a summary row to 'Daily_Analytics' tab.
        Auto-checks for missing columns and maps fields dynamically to header names.
        """
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_day = datetime.now(timezone.utc).strftime("%A")

        field_data = {
            "date": analytics_record.get("Date", today_str),
            "day_of_week": analytics_record.get("Day_of_Week", today_day),
            "queries_run": analytics_record.get("Queries_Run", 0),
            "posts_found": analytics_record.get("Posts_Found", 0),
            "leads_extracted": analytics_record.get("Leads_Extracted", 0),
            "avg_posts_per_query": round(analytics_record.get("Avg_Posts_Per_Query", 0.0), 1),
            "total_cost_usd": f"${analytics_record.get('Total_Cost_USD', 0.0):.3f}",
            "avg_cost_per_query_usd": f"${analytics_record.get('Avg_Cost_Per_Query_USD', 0.0):.4f}",
            "avg_cost_per_lead_usd": f"${analytics_record.get('Avg_Cost_Per_Lead_USD', 0.0):.4f}",
        }

        if self.is_connected:
            try:
                current_headers = self.ensure_worksheet_schema("Daily_Analytics")
                sheet = self.spreadsheet.worksheet("Daily_Analytics")
                header_map = {h.strip().lower(): idx for idx, h in enumerate(current_headers)}
                total_cols = max(len(current_headers), 9)

                row = [""] * total_cols
                for k, val in field_data.items():
                    if k in header_map:
                        row[header_map[k]] = val

                sheet.append_row(row, value_input_option="USER_ENTERED")
                print("[SHEETS MANAGER] Recorded daily analytics to Google Sheet.")
            except Exception as e:
                print(f"[SHEETS MANAGER] Error writing Daily_Analytics: {e}")

        # Local CSV Backup
        self._append_analytics_local_csv(field_data)

    def _append_analytics_local_csv(self, field_data: Dict):
        """Appends daily analytics to local CSV backup, safely syncing columns."""
        local_csv = "daily_analytics.csv"
        standard_cols = STANDARD_SCHEMAS["Daily_Analytics"]["headers"]
        standard_map = {
            "Date": field_data["date"],
            "Day_of_Week": field_data["day_of_week"],
            "Queries_Run": field_data["queries_run"],
            "Posts_Found": field_data["posts_found"],
            "Leads_Extracted": field_data["leads_extracted"],
            "Avg_Posts_Per_Query": field_data["avg_posts_per_query"],
            "Total_Cost_USD": field_data["total_cost_usd"],
            "Avg_Cost_Per_Query_USD": field_data["avg_cost_per_query_usd"],
            "Avg_Cost_Per_Lead_USD": field_data["avg_cost_per_lead_usd"],
        }

        df_new = pd.DataFrame([standard_map])

        if os.path.exists(local_csv):
            try:
                existing_df = pd.read_csv(local_csv)
                for col in standard_cols:
                    if col not in existing_df.columns:
                        existing_df[col] = ""
                all_cols = list(existing_df.columns)
                for col in standard_cols:
                    if col not in all_cols:
                        all_cols.append(col)

                df_new = df_new.reindex(columns=all_cols, fill_value="")
                existing_df = existing_df.reindex(columns=all_cols, fill_value="")
                combined_df = pd.concat([existing_df, df_new], ignore_index=True)
                combined_df.to_csv(local_csv, index=False, encoding="utf-8-sig")
            except Exception as e:
                print(f"[SHEETS MANAGER] Error writing local analytics CSV: {e}")
                df_new.to_csv(local_csv, mode="a", index=False, header=False, encoding="utf-8-sig")
        else:
            df_new.to_csv(local_csv, index=False, encoding="utf-8-sig")
