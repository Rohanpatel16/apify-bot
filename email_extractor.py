import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple


class LeadEmailExtractor:
    """
    Extracts, normalizes, filters, and deduplicates recruiter/business leads
    into a clean 6-column CRM format: [Email, Domain, Phone Number, Name, Query, Date].
    
    100% Dynamic Rules (Loaded directly from Google Sheets 'Settings' tab):
    - Blocked Domains: loaded from 'Blocked Domains' column
    - Rejection Keywords: loaded from 'Rejection Keywords' column (checked in both username and domain)
    - Blocked Suffixes: loaded from 'Blocked Suffixes' column
    - Phone numbers are sanitized to prevent Google Sheets '#ERROR!' formula errors.
    """

    # RFC-compliant email pattern
    EMAIL_REGEX = re.compile(
        r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", re.IGNORECASE
    )

    # Phone patterns (Indian mobile +91, 10-digit formats & international)
    PHONE_REGEX = re.compile(
        r"(?:\+91[\s\-]?)?(?:[6-9]\d{9}|[6-9]\d{4}[\s\-]?\d{5})|(?:\+\d{1,3}[\s\-]?)?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}"
    )

    def __init__(
        self,
        blocked_domains: Optional[Set[str]] = None,
        rejection_keywords: Optional[Set[str]] = None,
        blocked_suffixes: Optional[Set[str]] = None,
        existing_emails: Optional[Set[str]] = None,
    ):
        self.blocked_domains = {d.strip().lower() for d in (blocked_domains or []) if d.strip()}
        self.rejection_keywords = {k.strip().lower() for k in (rejection_keywords or []) if k.strip()}
        self.blocked_suffixes = {s.strip().lower() for s in (blocked_suffixes or []) if s.strip()}
        self.seen_emails = {e.strip().lower() for e in (existing_emails or []) if e.strip()}

    def extract_lead_from_post(self, post_item: dict, query: str) -> List[Dict[str, str]]:
        """
        Extracts all valid, filtered, and fresh leads from a raw Apify post item.
        Returns a list of dicts with keys: Email, Domain, Phone Number, Name, Query, Date.
        """
        content = post_item.get("content") or post_item.get("text") or ""
        
        # 1. Extract Author / Recruiter Name
        author = post_item.get("author") or {}
        name = author.get("name") or post_item.get("authorName") or "Recruiter"
        name = name.strip()

        # 2. Extract Phone Number (sanitized with leading quote to prevent Google Sheets #ERROR! formula evaluation)
        phone = ""
        phone_matches = self.PHONE_REGEX.findall(content)
        if phone_matches:
            for raw_phone in phone_matches:
                clean_digits = re.sub(r"\D", "", raw_phone)
                if len(clean_digits) >= 10:
                    clean_str = raw_phone.strip().lstrip("-").strip()
                    phone = f"'{clean_str}" if clean_str else ""
                    break

        # 3. Extract Emails from post body
        extracted_emails = self.EMAIL_REGEX.findall(content)
        
        # 4. Extract Post Date
        raw_date = post_item.get("postedDate") or post_item.get("postedAt") or post_item.get("date") or post_item.get("createdAt") or ""
        if isinstance(raw_date, dict):
            raw_date = raw_date.get("date") or raw_date.get("timestamp") or ""

        if raw_date and "T" in str(raw_date):
            lead_date = str(raw_date).split("T")[0]
        elif raw_date and len(str(raw_date)) >= 10 and str(raw_date)[:4].isdigit():
            lead_date = str(raw_date)[:10]
        else:
            lead_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        valid_leads = []
        for raw_email in extracted_emails:
            clean_email = self._clean_email(raw_email)
            if not clean_email:
                continue

            # Validate against filter rules loaded dynamically from Google Sheets
            is_valid, reason = self.validate_email(clean_email)
            if not is_valid:
                continue

            # Check deduplication
            if clean_email in self.seen_emails:
                continue

            # Mark seen to prevent duplicate within same run
            self.seen_emails.add(clean_email)
            
            domain = clean_email.split("@")[1]

            valid_leads.append({
                "Email": clean_email,
                "Domain": domain,
                "Phone Number": phone,
                "Name": name,
                "Query": query,
                "Date": lead_date,
            })

        return valid_leads

    def validate_email(self, email: str) -> Tuple[bool, str]:
        """
        Validates email dynamically against lists loaded from Google Sheets Settings tab:
        1. Blocked Domains: checks if domain matches any blocked domain entry.
        2. Blocked Suffixes: checks if domain ends with or contains any blocked suffix.
        3. Rejection Keywords: checks if any keyword appears in the username OR the domain.
        """
        if "@" not in email:
            return False, "Malformed email"

        username, domain = email.split("@", 1)
        username = username.lower()
        domain = domain.lower()
        domain_base = domain.split(".")[0]

        # 1. Check Blocked Domains (Dynamic from Google Sheet)
        for bd in self.blocked_domains:
            if not bd:
                continue
            if "." in bd:
                if domain == bd or domain.endswith("." + bd):
                    return False, f"Blocked domain: {domain}"
                # Also match root provider name from sheet to catch typos/aliases (e.g. gmail.com catches gmail.con)
                root_name = bd.split(".")[0]
                if len(root_name) >= 4 and root_name in domain_base:
                    return False, f"Blocked provider domain: {domain}"
            else:
                # If entered without dot (e.g. gmail, zoho, yahoo)
                if bd in domain_base:
                    return False, f"Blocked domain: {domain}"

        # 2. Check Blocked Suffixes (Dynamic from Google Sheet)
        for suffix in self.blocked_suffixes:
            s = suffix.strip()
            if not s:
                continue
            if not s.startswith("."):
                s = f".{s}"
            if domain.endswith(s) or f"{s}." in domain:
                return False, f"Blocked suffix: {suffix}"

        # 3. Check Rejection Keywords in BOTH Username AND Domain (Dynamic from Google Sheet)
        for kw in self.rejection_keywords:
            kw = kw.strip()
            if not kw:
                continue

            # A) Match in Username (e.g. hr@, careers@, jobs@, contact@, info@, sales@)
            if kw in username:
                return False, f"Rejection keyword '{kw}' in username"
            # Stem matching: if keyword ends in 'e' (e.g. hire -> hiring)
            if kw.endswith("e") and len(kw) > 3 and kw[:-1] in username:
                return False, f"Rejection keyword '{kw}' in username"
            # Stem matching: if keyword ends in 's' (e.g. jobs -> job, careers -> career)
            if kw.endswith("s") and len(kw) > 3 and kw[:-1] == username:
                return False, f"Rejection keyword '{kw}' in username"

            # B) Match in Domain (e.g. recruitmenthub365.com, placewellcareers.com, tgcstaffing.com, goldenbrickshr.com)
            if kw == "hr":
                # Smart HR detection in domain (e.g. goldenbrickshr, hrbx, delighthr, greathrsol, hr-central)
                # while avoiding false positives on common words (chrome, thread, anthropic, shri)
                hr_patterns = [
                    r"(^|[-_.])hr",
                    r"hr([-_.0-9]|$)",
                    r"hr(sol|solutions|consult|services|work|works|group|corp|tech|india|global|net|hub|world)",
                    r"(great|delight|golden|ensure|converse|spring|bean|ciel|ambience|realworld|urban|teamup|mitr)hr",
                ]
                if any(re.search(p, domain_base) for p in hr_patterns):
                    if not any(safe in domain_base for safe in ["chrome", "thread", "anthropic", "shroff", "shri"]):
                        return False, f"Rejection keyword '{kw}' in domain"
            elif kw in ("career", "careers"):
                if "career" in domain_base:
                    return False, f"Rejection keyword '{kw}' in domain"
            elif kw in ("consultancy", "consulting", "consultant"):
                if "consult" in domain_base:
                    return False, f"Rejection keyword '{kw}' in domain"
            elif kw in ("jobs", "job"):
                if "job" in domain_base:
                    return False, f"Rejection keyword '{kw}' in domain"
            elif kw in ("recruit", "recruitment", "recruiter"):
                if "recruit" in domain_base:
                    return False, f"Rejection keyword '{kw}' in domain"
            elif kw in ("hire", "hiring"):
                if "hire" in domain_base or "hyre" in domain_base:
                    return False, f"Rejection keyword '{kw}' in domain"
            elif kw == "info":
                if "infosys" not in domain_base and "info" in domain_base:
                    return False, f"Rejection keyword '{kw}' in domain"
            else:
                if kw in domain_base:
                    return False, f"Rejection keyword '{kw}' in domain"

        return True, "Valid"

    def _clean_email(self, email: str) -> str:
        """Trims punctuation, brackets, and spaces."""
        cleaned = email.strip().strip(".,;:()<>[]{}'\"").lower()
        return cleaned if "@" in cleaned and "." in cleaned.split("@")[1] else ""
