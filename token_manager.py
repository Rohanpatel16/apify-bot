import time
import httpx
from datetime import datetime, timezone
from typing import Dict, List, Optional
from apify_client import ApifyClient


def safe_get(obj, key, default=None):
    """
    Safely retrieves a value whether obj is a dictionary or a typed object/dataclass,
    checking both camelCase and snake_case.
    """
    if obj is None:
        return default
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        snake_key = ''.join(['_' + c.lower() if c.isupper() else c for c in key]).lstrip('_')
        return obj.get(snake_key, default)
    
    # Object attribute lookup
    if hasattr(obj, key):
        val = getattr(obj, key)
        return val if val is not None else default
    snake_key = ''.join(['_' + c.lower() if c.isupper() else c for c in key]).lstrip('_')
    if hasattr(obj, snake_key):
        val = getattr(obj, snake_key)
        return val if val is not None else default
    if hasattr(obj, "__dict__"):
        return obj.__dict__.get(key, obj.__dict__.get(snake_key, default))
    return default


class TokenManager:
    """
    Manages a pool of unlimited Apify API tokens.
    Queries live real-time balances from Apify limits and usage endpoints,
    ranks tokens to pick the highest available credit, and preserves passwords.
    """

    def __init__(self, token_records: Optional[List[Dict]] = None):
        self.tokens: List[Dict] = token_records or []
        self.current_token_index: int = 0

    def load_from_sheet_data(self, rows: List[List[str]]):
        """Loads tokens from 2D sheet row arrays."""
        self.tokens = []
        for r in rows:
            if not r or not r[0] or not str(r[0]).strip().startswith("apify_api_"):
                continue

            token = str(r[0]).strip()
            name = r[1] if len(r) > 1 else ""
            password = r[2] if len(r) > 2 else ""
            status = (r[3] if len(r) > 3 else "ACTIVE").strip().upper()
            
            try:
                bal_val = str(r[4]).replace("$", "").strip() if len(r) > 4 else "5.00"
                balance = float(bal_val) if bal_val else 0.0
            except ValueError:
                balance = 0.0

            last_used = r[5] if len(r) > 5 else ""
            notes = r[6] if len(r) > 6 else ""

            self.tokens.append({
                "api_token": token,
                "account_name": name,
                "password": password,
                "status": status,
                "available_balance_usd": balance,
                "last_used_at": last_used,
                "notes": notes,
            })

    def sync_live_balances(self):
        """
        Queries Apify REST API (https://api.apify.com/v2/users/me/limits) for live,
        real-time spending, monthly limits, and exact remaining USD credit.
        """
        print(f"\n[TOKEN POOL] Querying live balances for {len(self.tokens)} token(s)...")
        for record in self.tokens:
            token = record["api_token"]
            if not token or not token.startswith("apify_api_"):
                continue

            try:
                headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
                
                # 1. Query limits endpoint (gives max allowed USD & current monthlyUsageUsd)
                resp = httpx.get("https://api.apify.com/v2/users/me/limits", headers=headers, timeout=10.0)
                
                if resp.status_code == 200:
                    payload = resp.json().get("data", {})
                    limits_data = payload.get("limits", {})
                    current_data = payload.get("current", {})
                    
                    max_usd = float(limits_data.get("maxMonthlyUsageUsd", 5.0) or 5.0)
                    used_usd = float(current_data.get("monthlyUsageUsd", 0.0) or 0.0)
                    remaining_usd = max(0.0, max_usd - used_usd)

                    record["available_balance_usd"] = round(remaining_usd, 4)
                    record["status"] = "ACTIVE"
                    record["notes"] = f"Used: ${used_usd:.4f} / ${max_usd:.2f}"
                    print(f"  [OK] {record['account_name']}: ${record['available_balance_usd']:.4f} remaining (Used: ${used_usd:.4f})")
                elif resp.status_code in (401, 403):
                    record["status"] = "INVALID"
                    record["notes"] = "Invalid or expired token"
                    print(f"  [ERR] {record['account_name']}: Invalid Token")
                elif resp.status_code == 429:
                    record["status"] = "EXHAUSTED"
                    record["notes"] = "Rate limited / Quota exhausted"
                    print(f"  [ERR] {record['account_name']}: Rate Limited")
                else:
                    # Fallback to apify-client
                    client = ApifyClient(token)
                    user_info = client.user("me").get()
                    record["status"] = "ACTIVE"
                    record["notes"] = "Healthy"
                    print(f"  [OK] {record['account_name']}: Active")

            except Exception as e:
                err_str = str(e)
                if "401" in err_str or "Invalid token" in err_str:
                    record["status"] = "INVALID"
                    record["notes"] = "Invalid API Token"
                elif "429" in err_str or "quota" in err_str.lower():
                    record["status"] = "EXHAUSTED"
                    record["notes"] = "Quota Exceeded / Rate Limited"
                else:
                    record["notes"] = f"Warning: {err_str[:40]}"
                print(f"  [ERR] {record['account_name']}: {record['notes']}")

    def get_best_token(self) -> Optional[Dict]:
        """
        Picks the token with status='ACTIVE' and the HIGHEST available balance.
        """
        active_tokens = [
            t for t in self.tokens
            if t["status"] == "ACTIVE" and t.get("available_balance_usd", 0) > 0.01
        ]

        if not active_tokens:
            active_tokens = [t for t in self.tokens if t["status"] == "ACTIVE"]

        if not active_tokens:
            return None

        # Sort descending by balance
        active_tokens.sort(key=lambda x: x.get("available_balance_usd", 0), reverse=True)
        best = active_tokens[0]
        best["last_used_at"] = datetime.now(timezone.utc).isoformat()
        return best

    def mark_exhausted(self, token_str: str, reason: str = "Quota Exceeded"):
        """Marks a token as exhausted and forces rotation."""
        for t in self.tokens:
            if t["api_token"] == token_str:
                t["status"] = "EXHAUSTED"
                t["notes"] = reason
                print(f"[TOKEN POOL] Token '{t['account_name']}' marked EXHAUSTED. Switching...")
                break

    def export_sheet_rows(self) -> List[List]:
        """Formats the internal token list back to 2D rows for Google Sheets."""
        rows = []
        for t in self.tokens:
            bal = t.get('available_balance_usd', 0.0)
            rows.append([
                t.get("api_token", ""),
                t.get("account_name", ""),
                t.get("password", ""),
                t.get("status", "ACTIVE"),
                f"${bal:.4f}" if isinstance(bal, float) else str(bal),
                t.get("last_used_at", ""),
                t.get("notes", ""),
            ])
        return rows
