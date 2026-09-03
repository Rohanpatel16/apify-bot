import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple


class LeadEmailExtractor:
    """
    Extracts, normalizes, filters, and deduplicates recruiter/business leads
    into a clean 6-column CRM format: [Email, Domain, Phone Number, Name, Query, Date].
    - Filters out generic mailboxes (hiring@, hr@, cv@, jobs@, info@, etc.)
    - Filters out HR, staffing, consultancy, and recruitment agency domains.
    - Filters out consumer/free email providers (Gmail, Yahoo, Zoho, etc.) and typos.
    - Filters out institutional suffixes (.edu, .edu.in, .ac.in, .gov, .org, etc.)
    - Sanitizes phone numbers to prevent Google Sheets #ERROR! formula bugs.
    """

    # RFC-compliant email pattern
    EMAIL_REGEX = re.compile(
        r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", re.IGNORECASE
    )

    # Phone patterns (Indian mobile +91, 10-digit formats & international)
    PHONE_REGEX = re.compile(
        r"(?:\+91[\s\-]?)?(?:[6-9]\d{9}|[6-9]\d{4}[\s\-]?\d{5})|(?:\+\d{1,3}[\s\-]?)?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}"
    )

    # Common generic inbox prefixes that should never be treated as direct decision makers
    GENERIC_INBOX_STEMS = {
        "hr", "hiring", "hire", "recruit", "recruiter", "recruitment", "recruiting",
        "job", "jobs", "career", "careers", "carrer",
        "cv", "resume", "resumes", "placement", "placements", "placementcell",
        "info", "enquiry", "inquiry", "hello", "contact", "connect", "connnect", "reach", "reachus",
        "join", "joinus", "apply", "support", "help", "admin", "sales", "official",
        "feedback", "marketing", "business", "operations", "lead", "partners"
    }

    # Free consumer email patterns (including common typos)
    FREE_PROVIDER_PATTERNS = [
        r"^(?:.*\.)?gmail\.", r"^(?:.*\.)?gmai\.", r"^(?:.*\.)?gamil\.",
        r"^(?:.*\.)?yahoo\.", r"^(?:.*\.)?ymail\.",
        r"^(?:.*\.)?hotmail\.", r"^(?:.*\.)?outlook\.",
        r"^(?:.*\.)?zoho\.", r"^(?:.*\.)?zohomail\.",
        r"^(?:.*\.)?proton(?:mail)?\.", r"^(?:.*\.)?rediffmail\.",
        r"^(?:.*\.)?icloud\.", r"^(?:.*\.)?aol\.", r"^(?:.*\.)?live\.", r"^(?:.*\.)?msn\."
    ]

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

        # 2. Extract Phone Number (safely sanitized for Google Sheets)
        phone = ""
        phone_matches = self.PHONE_REGEX.findall(content)
        if phone_matches:
            for raw_phone in phone_matches:
                clean_digits = re.sub(r"\D", "", raw_phone)
                if len(clean_digits) >= 10:
                    clean_str = raw_phone.strip().lstrip("-").strip()
                    # Prefix with single quote so Google Sheets treats it as plain text instead of a formula (#ERROR!)
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

            # Validate against filter rules
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
        Validates email against:
        1. Blocked Domains (exact or consumer pattern, e.g. gmail, yahoo, zoho)
        2. Blocked Suffixes (e.g. .gov, .edu, .edu.in, .ac.in, .org, .xyz)
        3. Rejection Keywords in username (e.g. hr@, careers@, jobs@, hiring@, info@, cv@)
        4. Rejection Keywords in domain (e.g. recruitmenthub365.com, placewellcareers.com, tgcstaffing.com, goldenbrickshr.com)
        """
        if "@" not in email:
            return False, "Malformed email"

        username, domain = email.split("@", 1)
        username = username.lower()
        domain = domain.lower()

        # 1. Check Blocked Domains (exact match or consumer email regex)
        if domain in self.blocked_domains:
            return False, f"Blocked domain: {domain}"

        if any(re.search(p, domain) for p in self.FREE_PROVIDER_PATTERNS):
            return False, f"Free/consumer email domain: {domain}"

        # 2. Check Blocked Suffixes (.edu, .edu.in, .ac.in, .gov, .org, .xyz, etc.)
        for suffix in self.blocked_suffixes:
            s = suffix.lower().strip()
            if not s:
                continue
            if not s.startswith("."):
                s = f".{s}"
            if domain.endswith(s) or f"{s}." in domain:
                return False, f"Blocked suffix: {suffix}"

        # 3. Check Generic/Bot Mailbox Prefixes in Username
        user_root = re.split(r"[._\-0-9]", username)[0]
        if username in self.GENERIC_INBOX_STEMS or user_root in self.GENERIC_INBOX_STEMS:
            return False, f"Generic inbox prefix: '{username}'"

        for kw in self.rejection_keywords:
            kw = kw.strip().lower()
            if kw and kw in username:
                return False, f"Rejection keyword '{kw}' in username"

        # 4. Check Rejection Keywords in Domain (e.g. recruitment, staffing, careers, consultancies)
        dom_name = domain.split(".")[0]
        for kw in self.rejection_keywords:
            kw = kw.strip().lower()
            if not kw:
                continue

            if kw == "hr":
                # Smart HR detection for recruitment firms (e.g. goldenbrickshr, hrbx, delighthr, greathrsol)
                hr_patterns = [
                    r"(^|[-_.])hr",                           # Starts with hr or after hyphen (hrbx, hr-solutions)
                    r"hr([-_.0-9]|$)",                        # Ends with hr or before separator (delighthr, cielhr, k9hr)
                    r"hr(sol|solutions|consult|services|work|works|group|corp|tech|india|global|net|hub|world)",
                    r"(great|delight|golden|ensure|converse|spring|bean|ciel|ambience|realworld|urban|teamup|mitr)hr",
                ]
                if any(re.search(p, dom_name) for p in hr_patterns):
                    if not any(safe in dom_name for safe in ["chrome", "thread", "anthropic", "shroff", "shri"]):
                        return False, "HR/Staffing firm in domain"

            elif kw in ("career", "careers"):
                if "career" in dom_name:
                    return False, f"Rejection keyword '{kw}' in domain"

            elif kw in ("consultancy", "consulting"):
                if "consult" in dom_name:
                    return False, f"Rejection keyword '{kw}' in domain"

            elif kw in ("jobs", "job"):
                if "job" in dom_name:
                    return False, f"Rejection keyword '{kw}' in domain"

            elif kw in ("recruit", "recruitment"):
                if "recruit" in dom_name:
                    return False, f"Rejection keyword '{kw}' in domain"

            elif kw in ("hire", "hiring"):
                if "hire" in dom_name or "hyre" in dom_name:
                    return False, f"Rejection keyword '{kw}' in domain"

            elif kw == "info":
                if "infosys" not in dom_name and "info" in dom_name:
                    return False, f"Rejection keyword '{kw}' in domain"

            elif kw in dom_name:
                return False, f"Rejection keyword '{kw}' in domain"

        return True, "Valid"

    def _clean_email(self, email: str) -> str:
        """Trims punctuation, brackets, and spaces."""
        cleaned = email.strip().strip(".,;:()<>[]{}'\"").lower()
        return cleaned if "@" in cleaned and "." in cleaned.split("@")[1] else ""
