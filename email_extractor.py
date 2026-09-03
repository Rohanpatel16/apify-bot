import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple


class LeadEmailExtractor:
    """
    Extracts, normalizes, filters, and deduplicates recruiter/business leads
    into a clean 6-column CRM format: [Email, Domain, Phone Number, Name, Query, Date].
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
        Returns a list of dicts with keys: Email, Domain, Phone Number, Name, Query.
        """
        content = post_item.get("content") or post_item.get("text") or ""
        
        # 1. Extract Author / Recruiter Name
        author = post_item.get("author") or {}
        name = author.get("name") or post_item.get("authorName") or "Recruiter"
        name = name.strip()

        # 2. Extract Phone Number
        phone = ""
        phone_matches = self.PHONE_REGEX.findall(content)
        if phone_matches:
            # Pick first clean match of reasonable length (>= 10 digits)
            for raw_phone in phone_matches:
                clean_digits = re.sub(r"\D", "", raw_phone)
                if len(clean_digits) >= 10:
                    phone = raw_phone.strip()
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
        Validates email against Blocked Domains, Rejection Keywords, and Blocked Suffixes.
        """
        if "@" not in email:
            return False, "Malformed email"

        username, domain = email.split("@", 1)
        username = username.lower()
        domain = domain.lower()

        # Check Blocked Domains (e.g. gmail.com)
        if domain in self.blocked_domains:
            return False, f"Blocked domain: {domain}"

        # Check Rejection Keywords in username (e.g. hr@, careers@, jobs@, consultancy@)
        for kw in self.rejection_keywords:
            if kw in username:
                return False, f"Rejection keyword '{kw}' in username"

        # Check Blocked Suffixes (e.g. .edu, .xyz, .top, .site)
        for suffix in self.blocked_suffixes:
            if domain.endswith(suffix):
                return False, f"Blocked suffix: {suffix}"

        return True, "Valid"

    def _clean_email(self, email: str) -> str:
        """Trims punctuation, brackets, and spaces."""
        cleaned = email.strip().strip(".,;:()<>[]{}'\"").lower()
        return cleaned if "@" in cleaned and "." in cleaned.split("@")[1] else ""
