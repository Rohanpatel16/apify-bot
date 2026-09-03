import os
import shutil
import tempfile
import unittest
import pandas as pd
from sheets_manager import SheetsManager, col_index_to_letter, STANDARD_SCHEMAS


class TestSheetsManagerSync(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.temp_dir)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.temp_dir)

    def test_col_index_to_letter(self):
        self.assertEqual(col_index_to_letter(1), "A")
        self.assertEqual(col_index_to_letter(6), "F")
        self.assertEqual(col_index_to_letter(26), "Z")
        self.assertEqual(col_index_to_letter(27), "AA")
        self.assertEqual(col_index_to_letter(28), "AB")

    def test_local_csv_missing_column_sync(self):
        # Create an older leads_database.csv missing 'Date', with an existing custom column
        old_data = {
            "Email": ["alice@techcorp.com", "bob@example.com"],
            "Domain": ["techcorp.com", "example.com"],
            "Phone Number": ["+1234567890", ""],
            "Name": ["Alice", "Bob"],
            "Query": ["Hiring Bangalore", "Hiring Pune"],
            "Custom Notes": ["Contacted on LinkedIn", "Replied"],
        }
        old_df = pd.DataFrame(old_data)
        old_df.to_csv("leads_database.csv", index=False, encoding="utf-8-sig")

        # Initialize manager in local mode
        mgr = SheetsManager()

        # Check that Date column was added without deleting Custom Notes or rows
        synced_df = pd.read_csv("leads_database.csv")
        self.assertIn("Date", synced_df.columns)
        self.assertIn("Custom Notes", synced_df.columns)
        self.assertEqual(len(synced_df), 2)
        self.assertEqual(synced_df.iloc[0]["Email"], "alice@techcorp.com")
        self.assertEqual(synced_df.iloc[0]["Custom Notes"], "Contacted on LinkedIn")

    def test_append_leads_preserves_custom_columns(self):
        # Start with an existing CSV with custom columns
        initial_data = {
            "Email": ["alice@techcorp.com"],
            "Domain": ["techcorp.com"],
            "Phone Number": ["+1234567890"],
            "Name": ["Alice"],
            "Query": ["Hiring Bangalore"],
            "Date": ["2026-09-01"],
            "User_Lead_Status": ["Interview Scheduled"],
        }
        pd.DataFrame(initial_data).to_csv("leads_database.csv", index=False, encoding="utf-8-sig")

        mgr = SheetsManager()

        new_lead = [{
            "Email": "carol@innovate.com",
            "Domain": "innovate.com",
            "Phone Number": "+9876543210",
            "Name": "Carol",
            "Query": "Hiring Hyderabad",
            "Date": "2026-09-03",
        }]

        mgr.append_leads(new_lead)

        df = pd.read_csv("leads_database.csv")
        self.assertEqual(len(df), 2)
        self.assertIn("User_Lead_Status", df.columns)
        self.assertEqual(df.iloc[0]["User_Lead_Status"], "Interview Scheduled")
        self.assertEqual(df.iloc[1]["Email"], "carol@innovate.com")
        self.assertEqual(df.iloc[1]["Date"], "2026-09-03")

    def test_load_queries_defaults(self):
        mgr = SheetsManager()
        defaults = ["Query 1", "Query 2"]
        queries = mgr.load_queries(default_queries=defaults)
        self.assertEqual(queries, defaults)

    def test_load_settings_defaults(self):
        mgr = SheetsManager()
        settings = mgr.load_settings()
        self.assertIn("blocked_domains", settings)
        self.assertIn("gmail.com", settings["blocked_domains"])
        self.assertIn("hr", settings["rejection_keywords"])
    def test_lead_extractor_date(self):
        from email_extractor import LeadEmailExtractor
        extractor = LeadEmailExtractor()
        post_item = {
            "content": "Looking for frontend developer. Send CV to hr@goodcompany.com or careers@goodcompany.com",
            "author": {"name": "Test Recruiter"},
            "postedAt": {"timestamp": 1788256134614, "date": "2026-09-01T09:48:54.614Z"}
        }
        leads = extractor.extract_lead_from_post(post_item, "Hiring Test")
        self.assertEqual(len(leads), 2)
        self.assertEqual(leads[0]["Email"], "hr@goodcompany.com")
        self.assertEqual(leads[0]["Date"], "2026-09-01")

    def test_token_manager_export(self):
        from token_manager import TokenManager
        tm = TokenManager()
        rows = [
            ["apify_api_1234567890abcdef", "Account 1", "SecretPass123", "ACTIVE", "$4.50", "2026-09-01", "Notes here"]
        ]
        tm.load_from_sheet_data(rows)
        self.assertEqual(len(tm.tokens), 1)
        self.assertEqual(tm.tokens[0]["password"], "SecretPass123")
        exported = tm.export_sheet_rows()
        self.assertEqual(exported[0][2], "SecretPass123")


if __name__ == "__main__":
    unittest.main()

