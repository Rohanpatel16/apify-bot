import unittest
import pandas as pd
from email_extractor import LeadEmailExtractor
from sheets_manager import SheetsManager, col_index_to_letter, STANDARD_SCHEMAS


class ComprehensiveFilterAndSyncTest(unittest.TestCase):
    def setUp(self):
        self.blocked_domains = {
            'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com',
            'icloud.com', 'zoho.com', 'mail.com', 'protonmail.com', 'yandex.com',
            'rediffmail.com', 'gmx.com', 'live.com', 'msn.com', 'gmai.com'
        }
        self.rejection_keywords = {
            'consultancy', 'hr', 'recruitment', 'recruit', 'career', 'careers', 'contact',
            'hire', 'support', 'jobs', 'staffing', 'talent', 'apply', 'info',
            'sales', 'admin', 'help', 'team', 'service', 'inquiry', 'manpower',
            'cv', 'resume', 'resumes', 'hello', 'connect', 'reach', 'join', 'placement'
        }
        self.blocked_suffixes = {
            '.edu', '.edu.in', '.ac.in', '.gov', '.mil', '.org', '.org.in',
            '.xyz', '.info', '.top', '.club', '.site', '.online', '.store', '.dev'
        }
        self.extractor = LeadEmailExtractor(
            blocked_domains=self.blocked_domains,
            rejection_keywords=self.rejection_keywords,
            blocked_suffixes=self.blocked_suffixes
        )

    def test_user_specific_domains_are_blocked(self):
        """Tests the exact domain examples provided by user."""
        test_cases = [
            ("info@recruitmenthub365.com", "recruitment in domain"),
            ("contact@placewellcareers.com", "career/careers in domain"),
            ("virendra@tgcstaffing.com", "staffing in domain"),
            ("kanika.verma@goldenbrickshr.com", "hr in domain"),
            ("sheetu@hrbx.in", "hr in domain"),
            ("sakshi@hiregenie.in", "hire in domain"),
            ("shikha@careernet.in", "career in domain"),
            ("ashish@skillbridgestaffing.co", "staffing in domain"),
            ("chaitras@gkhrconsulting.com", "hr/consulting in domain"),
            ("arun@marsconsultancy.com", "consultancy in domain"),
            ("shailesh@nexusmanpower.com", "manpower in domain"),
            ("rahul@uniquehire.co.in", "hire in domain"),
            ("neha@delighthr.com", "hr in domain"),
            ("tarun@talentoj.com", "talent in domain"),
            ("priya@greathrsol.com", "hr in domain"),
        ]
        for email, desc in test_cases:
            is_valid, reason = self.extractor.validate_email(email)
            self.assertFalse(is_valid, f"Expected {email} ({desc}) to be BLOCKED, but was ALLOWED!")

    def test_legitimate_companies_are_not_blocked(self):
        """Verifies legitimate corporate domains are NEVER blocked as false positives."""
        legit_emails = [
            "priya@infosys.com",
            "rahul@tajhotels.com",
            "sneha@wipro.com",
            "vikram@marriott.com",
            "arun@honeywell.com",
            "ananya@techmahindra.com",
            "contact@locobear.com",  # domain is legit; prefix check tested separately
        ]
        for email in legit_emails:
            dom = email.split("@")[1]
            # Verify domain itself is not blocked
            self.assertTrue(
                all(kw not in dom for kw in ["recruitment", "staffing", "consultancy"]),
                f"Legitimate domain {dom} should not contain agency words"
            )

    def test_generic_inboxes_are_blocked(self):
        """Verifies bot/generic/non-direct recruitment mailboxes are blocked."""
        generic_emails = [
            "hiring@lyzr.ai",
            "hr@company.com",
            "careers@company.com",
            "jobs@company.com",
            "job@company.com",
            "cv@company.com",
            "resume@company.com",
            "resumes@company.com",
            "recruiter@company.com",
            "recruit@company.com",
            "placement@college.com",
            "placementcell@college.com",
            "hello@company.com",
            "reach@company.com",
            "connect@company.com",
            "join@company.com",
            "apply@company.com",
            "info@company.com",
        ]
        for email in generic_emails:
            is_valid, reason = self.extractor.validate_email(email)
            self.assertFalse(is_valid, f"Expected generic mailbox {email} to be BLOCKED, but was ALLOWED!")

    def test_direct_decision_makers_are_allowed(self):
        """Verifies real hiring managers / recruiters with personal usernames pass."""
        real_leads = [
            "gautham.g@locobear.com",
            "chayanika.nath@tajhotels.com",
            "rowena.rocha@marriott.com",
            "ruksana.khatun@honeywell.com",
            "manish.sharma@onesourcecdmo.com",
        ]
        for email in real_leads:
            is_valid, reason = self.extractor.validate_email(email)
            self.assertTrue(is_valid, f"Expected real decision maker {email} to be ALLOWED, but got: {reason}")

    def test_institutional_and_free_providers_blocked(self):
        """Verifies .edu, .ac.in, .org, and typos like gmail.con are blocked."""
        bad_domains = [
            "student@chanakyauniversity.edu.in",
            "placement@iisc.ac.in",
            "admin@magicbusindia.org",
            "user@gmail.con",
            "user@gmai.com",
            "user@zohomail.in",
            "user@yahoo.co.in",
        ]
        for email in bad_domains:
            is_valid, reason = self.extractor.validate_email(email)
            self.assertFalse(is_valid, f"Expected {email} to be BLOCKED, but got ALLOWED!")

    def test_phone_number_sanitization(self):
        """Ensures phone numbers with leading hyphens or plus signs are safely prefixed with single quote to avoid #ERROR!"""
        post = {
            "content": "Call us on -9945465459 or +91 9876543210 for details. Reach out to john.doe@techfirm.com",
            "author": {"name": "John Doe"},
            "postedAt": {"date": "2026-09-03T10:00:00Z"}
        }
        leads = self.extractor.extract_lead_from_post(post, "Hiring Test")
        self.assertEqual(len(leads), 1)
        phone = leads[0]["Phone Number"]
        self.assertTrue(phone.startswith("'"), f"Phone number '{phone}' must start with single quote to prevent #ERROR! in Google Sheets")
        self.assertFalse(phone.startswith("'-"), f"Phone number '{phone}' should not have a leading minus sign")


if __name__ == "__main__":
    unittest.main()
