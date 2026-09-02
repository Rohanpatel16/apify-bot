import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Dict, List, Optional

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

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
    - Limits each token to a maximum of 2 runs before rotating to the next token.
    - Evaluates live remaining balance after every run via the Apify /limits API.
    - Disables any token whose remaining balance is not viable for at least 1 full run (< $0.03).
    - Preserves passwords and account metadata safely.
    """

    DEFAULT_MIN_VIABLE_BALANCE = 0.03  # Minimum USD required for 1 full search run (~$0.02 - $0.03)
    DEFAULT_MAX_RUNS_PER_TOKEN = 2     # Max runs per token before rotating to next in pool

    def __init__(
        self,
        token_records: Optional[List[Dict]] = None,
        max_runs_per_token: int = DEFAULT_MAX_RUNS_PER_TOKEN,
        min_viable_balance: float = DEFAULT_MIN_VIABLE_BALANCE
    ):
        self.tokens: List[Dict] = token_records or []
        self.max_runs_per_token: int = max_runs_per_token
        self.min_viable_balance: float = min_viable_balance
        self.token_run_counts: Dict[str, int] = {}  # Tracks runs executed per token in current session

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

    def _query_limits_api(self, token: str) -> Optional[Dict]:
        """Queries the Apify /v2/users/me/limits endpoint for a token."""
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        try:
            if HTTPX_AVAILABLE:
                resp = httpx.get("https://api.apify.com/v2/users/me/limits", headers=headers, timeout=10.0)
                status_code = resp.status_code
                resp_json = resp.json() if status_code == 200 else {}
            else:
                req = urllib.request.Request("https://api.apify.com/v2/users/me/limits", headers=headers)
                try:
                    with urllib.request.urlopen(req, timeout=10.0) as response:
                        status_code = response.getcode()
                        resp_json = json.loads(response.read().decode("utf-8"))
                except urllib.error.HTTPError as he:
                    status_code = he.code
                    resp_json = {}

            return {"status_code": status_code, "data": resp_json.get("data", {})}
        except Exception as e:
            return {"status_code": 500, "error": str(e)}

    def sync_single_token_balance(self, token_str: str) -> float:
        """
        Queries live balance for a specific token after a run.
        Calculates remaining USD and disables the token if below min viable balance.
        """
        for record in self.tokens:
            if record["api_token"] != token_str:
                continue

            result = self._query_limits_api(token_str)
            if not result or result.get("status_code") != 200:
                # If API call fails, estimate based on last known balance
                return record.get("available_balance_usd", 0.0)

            payload = result.get("data", {})
            limits_data = payload.get("limits", {})
            current_data = payload.get("current", {})

            max_usd = float(limits_data.get("maxMonthlyUsageUsd", 5.0) or 5.0)
            used_usd = float(current_data.get("monthlyUsageUsd", 0.0) or 0.0)
            remaining_usd = max(0.0, max_usd - used_usd)

            record["available_balance_usd"] = round(remaining_usd, 4)

            # Check viability for 1 more run
            if remaining_usd < self.min_viable_balance:
                record["status"] = "EXHAUSTED"
                record["notes"] = f"Balance ${remaining_usd:.4f} < ${self.min_viable_balance:.3f} (Not viable for 1 run)"
                print(f"  [TOKEN POOL] Account '{record['account_name']}' balance ${remaining_usd:.4f} is NOT viable for another run (< ${self.min_viable_balance:.3f}). Marked EXHAUSTED.")
            else:
                record["notes"] = f"Used: ${used_usd:.4f} / ${max_usd:.2f} (Viable)"

            return remaining_usd

        return 0.0

    def record_run_completion(self, token_str: str) -> None:
        """
        Updates token run count and verifies if it reached the max runs limit (2 runs).
        """
        self.token_run_counts[token_str] = self.token_run_counts.get(token_str, 0) + 1
        runs_done = self.token_run_counts[token_str]
        
        # Find account name
        account_name = token_str
        for t in self.tokens:
            if t["api_token"] == token_str:
                account_name = t["account_name"]
                t["last_used_at"] = datetime.now(timezone.utc).isoformat()
                break

        if runs_done >= self.max_runs_per_token:
            print(f"  [ROTATION] Account '{account_name}' completed {runs_done}/{self.max_runs_per_token} runs for this cycle. Rotating to next token.")

    def sync_live_balances(self):
        """Queries live limits and spending for all tokens in the pool."""
        print(f"\n[TOKEN POOL] Querying live balances for {len(self.tokens)} token(s)...")
        for record in self.tokens:
            token = record["api_token"]
            if not token or not token.startswith("apify_api_"):
                continue

            result = self._query_limits_api(token)
            status_code = result.get("status_code", 500)

            if status_code == 200:
                payload = result.get("data", {})
                limits_data = payload.get("limits", {})
                current_data = payload.get("current", {})
                
                max_usd = float(limits_data.get("maxMonthlyUsageUsd", 5.0) or 5.0)
                used_usd = float(current_data.get("monthlyUsageUsd", 0.0) or 0.0)
                remaining_usd = max(0.0, max_usd - used_usd)

                record["available_balance_usd"] = round(remaining_usd, 4)

                if remaining_usd < self.min_viable_balance:
                    record["status"] = "EXHAUSTED"
                    record["notes"] = f"Low Balance (${remaining_usd:.4f} < ${self.min_viable_balance:.3f})"
                else:
                    record["status"] = "ACTIVE"
                    record["notes"] = f"Used: ${used_usd:.4f} / ${max_usd:.2f}"
                print(f"  [OK] {record['account_name']}: ${record['available_balance_usd']:.4f} remaining (Status: {record['status']})")
            elif status_code in (401, 403):
                record["status"] = "INVALID"
                record["notes"] = "Invalid or expired token"
                print(f"  [ERR] {record['account_name']}: Invalid Token")
            elif status_code == 429:
                record["status"] = "EXHAUSTED"
                record["notes"] = "Rate limited / Quota exhausted"
                print(f"  [ERR] {record['account_name']}: Rate Limited")
            else:
                client = ApifyClient(token)
                client.user("me").get()
                record["status"] = "ACTIVE"
                record["notes"] = "Healthy"
                print(f"  [OK] {record['account_name']}: Active")

    def get_best_token(self) -> Optional[Dict]:
        """
        Picks the best ACTIVE token:
        1. Must have remaining balance >= min_viable_balance ($0.03).
        2. Must not have exceeded max_runs_per_token (2 runs) in the current cycle.
        3. If all active tokens have done 2 runs, resets the cycle and rotates again.
        4. Sorts descending by available remaining balance.
        """
        # Candidate tokens that are active, viable, and have < max_runs_per_token runs
        candidates = [
            t for t in self.tokens
            if t["status"] == "ACTIVE"
            and t.get("available_balance_usd", 0.0) >= self.min_viable_balance
            and self.token_run_counts.get(t["api_token"], 0) < self.max_runs_per_token
        ]

        # If all viable active tokens have completed their 2 runs, start a fresh cycle across remaining viable tokens
        if not candidates:
            viable_pool = [
                t for t in self.tokens
                if t["status"] == "ACTIVE"
                and t.get("available_balance_usd", 0.0) >= self.min_viable_balance
            ]
            if viable_pool:
                print(f"\n[ROTATION] All active accounts completed {self.max_runs_per_token} runs. Starting next cycle across {len(viable_pool)} viable accounts.")
                self.token_run_counts.clear()
                candidates = viable_pool

        if not candidates:
            # Fallback: Check if any active tokens have any balance > 0
            fallback = [t for t in self.tokens if t["status"] == "ACTIVE" and t.get("available_balance_usd", 0.0) > 0.005]
            if fallback:
                fallback.sort(key=lambda x: x.get("available_balance_usd", 0.0), reverse=True)
                return fallback[0]
            return None

        # Pick the viable candidate with the highest remaining balance
        candidates.sort(key=lambda x: x.get("available_balance_usd", 0.0), reverse=True)
        best = candidates[0]
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
