#!/usr/bin/env python3
"""
PST File Scanner for Sensitive Information
This script scans Microsoft Outlook PST files for potentially sensitive information
using pattern matching and keyword detection.

Dependencies:
- pst-utils package
- libpst-utils package
- python-magic (optional, for file type verification)
"""

import subprocess
import re
import sys
import os
import logging
from datetime import datetime
from typing import List, Set, Dict, Optional, Tuple
from dataclasses import dataclass
import multiprocessing as mp
from pathlib import Path
import json
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False

@dataclass
class SensitiveMatch:
    """Data class to store information about detected sensitive content."""
    email_id: str
    subject: str
    matched_keywords: Set[str]
    context: str
    timestamp: str

class KeywordManager:
    """Manages keyword patterns and categories for sensitive information detection."""

    def __init__(self, custom_keywords_file: Optional[str] = None):
        self.keyword_categories: Dict[str, List[str]] = {
            "authentication": [
                "password", "passwd", "pass phrase", "passphrase", "secret question",
                "security answer", "api[_\\s]?key", "auth[_\\s]?token", "bearer[_\\s]?token",
                "oauth", "private[_\\s]?key", "secret[_\\s]?key", "access[_\\s]?key",
                "credentials", "login", "certificate"
            ],
            "personal_identifiers": [
                "ssn", "social[_\\s]?security", "tax[_\\s]?id", "passport[_\\s]?number",
                "driver[_\\s]?license", "national[_\\s]?id", "birth[_\\s]?certificate",
                "date[_\\s]?of[_\\s]?birth", "place[_\\s]?of[_\\s]?birth", "maiden[_\\s]?name",
                "mother's[_\\s]?maiden[_\\s]?name"
            ],
            "contact_information": [
                "email[_\\s]?address", "phone[_\\s]?number", "mobile[_\\s]?number",
                "cell[_\\s]?phone", "home[_\\s]?address", "residential[_\\s]?address",
                "postal[_\\s]?code", "zip[_\\s]?code", "po[_\\s]?box"
            ],
            "financial": [
                "credit[_\\s]?card", "debit[_\\s]?card", "cvv", "cvc", "card[_\\s]?verification",
                "expiration[_\\s]?date", "expiry[_\\s]?date", "bank[_\\s]?account",
                "routing[_\\s]?number", "swift[_\\s]?code", "iban", "wire[_\\s]?transfer",
                "paypal", "cryptocurrency[_\\s]?wallet", "bitcoin[_\\s]?address",
                "eth[_\\s]?address"
            ],
            "medical": [
                "health[_\\s]?record", "medical[_\\s]?history", "patient[_\\s]?id", "diagnosis",
                "prescription", "treatment[_\\s]?plan", "insurance[_\\s]?id",
                "medical[_\\s]?condition", "blood[_\\s]?type", "vaccination[_\\s]?record",
                "medical[_\\s]?test[_\\s]?result", "hospital[_\\s]?record"
            ],
            "employee_data": [
                "employee[_\\s]?id", "staff[_\\s]?id", "salary", "compensation", "bonus",
                "performance[_\\s]?review", "disciplinary[_\\s]?action", "hr[_\\s]?record",
                "employment[_\\s]?contract", "background[_\\s]?check", "payroll",
                "direct[_\\s]?deposit"
            ],
            "business_confidential": [
                "confidential", "proprietary", "trade[_\\s]?secret", "intellectual[_\\s]?property",
                "patent[_\\s]?pending", "copyright", "trademark", "nda", "non[_\\s]?disclosure",
                "internal[_\\s]?only", "restricted", "classified", "sensitive",
                "do[_\\s]?not[_\\s]?share", "draft", "preliminary"
            ],
            "legal": [
                "attorney[_\\s]?client[_\\s]?privilege", "legal[_\\s]?hold", "litigation",
                "settlement", "court[_\\s]?order", "subpoena", "lawsuit", "legal[_\\s]?agreement",
                "contract[_\\s]?terms", "liability", "compliance"
            ],
            "source_code": [
                "source[_\\s]?code", "git[_\\s]?token", "github[_\\s]?key", "api[_\\s]?endpoint",
                "database[_\\s]?credentials", "server[_\\s]?address", "development[_\\s]?key",
                "production[_\\s]?key", "staging[_\\s]?key", "encryption[_\\s]?key"
            ],
            "infrastructure": [
                "ip[_\\s]?address", "dns[_\\s]?record", "vpn[_\\s]?credential", "ssh[_\\s]?key",
                "root[_\\s]?password", "admin[_\\s]?credential", "firewall[_\\s]?config",
                "network[_\\s]?diagram", "system[_\\s]?architecture", "backup[_\\s]?location"
            ]
        }

        if custom_keywords_file:
            self._load_custom_keywords(custom_keywords_file)

        self.compiled_patterns = self._compile_patterns()

    def _load_custom_keywords(self, filepath: str) -> None:
        """Load custom keywords from a JSON file."""
        try:
            with open(filepath, 'r') as f:
                custom_categories = json.load(f)
                for category, keywords in custom_categories.items():
                    if category in self.keyword_categories:
                        self.keyword_categories[category].extend(keywords)
                    else:
                        self.keyword_categories[category] = keywords
        except Exception as e:
            logging.error(f"Error loading custom keywords: {e}")

    def _compile_patterns(self) -> Dict[str, List[re.Pattern]]:
        """Compile regex patterns for all keywords."""
        compiled = {}
        for category, keywords in self.keyword_categories.items():
            compiled[category] = [
                re.compile(rf"\b{keyword}\b", re.IGNORECASE)
                for keyword in keywords
            ]
        return compiled

class PSTScanner:
    """Main class for scanning PST files for sensitive information."""

    def __init__(self,
                 output_dir: str = "pst_output",
                 log_file: str = "pst_scan.log",
                 custom_keywords_file: Optional[str] = None):
        self.output_dir = Path(output_dir)
        self.setup_logging(log_file)
        self.keyword_manager = KeywordManager(custom_keywords_file)
        self.matches: List[SensitiveMatch] = []

    def setup_logging(self, log_file: str) -> None:
        """Configure logging with both file and console handlers."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )

    def verify_pst_file(self, file_path: str) -> bool:
        """Verify if the file is a valid PST file."""
        logging.info(f"Verifying PST file: {file_path}")
        if not os.path.exists(file_path):
            logging.error(f"File not found: {file_path}")
            return False

        if MAGIC_AVAILABLE:
            file_type = magic.from_file(file_path)
            if "Microsoft Outlook" not in file_type:
                logging.error(f"Invalid file type: {file_type}")
                return False

        return True

    def extract_email_content(self, email_text: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        """Extract relevant fields from email text."""
        email_id = re.search(r'(?:Message-ID|Message-Id): <(.+?)>', email_text, re.IGNORECASE)
        subject = re.search(r'Subject: (.*?)\n', email_text, re.IGNORECASE)
        timestamp = re.search(r'(?:Date|Sent): (.*?)\n', email_text, re.IGNORECASE)

        body = re.search(r'(?:Content-Type: text/plain|Content-Type: text/html).*?\n\n(.*?)(?=\n\n|$)',
                        email_text, re.DOTALL | re.IGNORECASE)
        if not body:
            body = re.search(r'\n\n(.*?)(?=\n\n|$)', email_text, re.DOTALL)

        return (
            email_id.group(1) if email_id else None,
            subject.group(1) if subject else None,
            body.group(1) if body else None,
            timestamp.group(1) if timestamp else None
        )

    def scan_email(self, email_text: str) -> Optional[SensitiveMatch]:
        """Scan a single email for sensitive information."""
        email_id, subject, body, timestamp = self.extract_email_content(email_text)

        if not any([subject, body]):
            return None

        matched_keywords = set()
        context = ""

        for category, patterns in self.keyword_manager.compiled_patterns.items():
            for pattern in patterns:
                matches = pattern.findall(email_text)
                if matches:
                    matched_keywords.add(category)
                    context += " ".join(matches) + "\n"

        if matched_keywords:
            return SensitiveMatch(
                email_id=email_id or "",
                subject=subject or "",
                matched_keywords=matched_keywords,
                context=context.strip(),
                timestamp=timestamp or ""
            )

        return None

    def scan_pst_file(self, pst_file: str) -> None:
        """Scan a PST file for sensitive information."""
        if not self.verify_pst_file(pst_file):
            return

        try:
            # Create output directory if it doesn't exist
            self.output_dir.mkdir(parents=True, exist_ok=True)

            # Create a subdirectory for the mbox file
            mbox_dir = self.output_dir / "mbox"
            mbox_dir.mkdir(parents=True, exist_ok=True)

            # Run readpst with just the directory as output
            subprocess.run(
                ["readpst", "-o", str(mbox_dir), pst_file],
                check=True,
                capture_output=True,
                text=True
            )

            # Find the generated mbox file (readpst usually adds a number to the filename)
            mbox_files = list(mbox_dir.glob("*.mbox"))
            if not mbox_files:
                raise FileNotFoundError("No mbox file was generated")

            # Process each mbox file found (usually there's just one)
            for mbox_file in mbox_files:
                self.process_mbox_file(mbox_file)

        except subprocess.CalledProcessError as e:
            logging.error(f"Error running readpst: {e.stderr}")
            raise
        except Exception as e:
            logging.error(f"Error scanning PST file {pst_file}: {e}")
            raise

    def process_mbox_file(self, mbox_file: Path) -> None:
        """Process an mbox file and scan each email."""
        try:
            with open(mbox_file, 'r', encoding='utf-8', errors='ignore') as f:
                email_text = ""
                for line in f:
                    if line.startswith("From "):
                        if email_text:
                            match = self.scan_email(email_text)
                            if match:
                                self.matches.append(match)
                            email_text = ""
                    email_text += line

                # Process the last email
                if email_text:
                    match = self.scan_email(email_text)
                    if match:
                        self.matches.append(match)
        except Exception as e:
            logging.error(f"Error processing mbox file {mbox_file}: {e}")
            raise

    def save_matches(self) -> None:
        """Save detected matches to a JSON file."""
        output_file = self.output_dir / "sensitive_matches.json"
        try:
            # Ensure the output directory exists
            self.output_dir.mkdir(parents=True, exist_ok=True)

            # Convert set to list for JSON serialization
            matches_json = []
            for match in self.matches:
                match_dict = match.__dict__.copy()
                match_dict['matched_keywords'] = list(match_dict['matched_keywords'])
                matches_json.append(match_dict)

            with open(output_file, 'w') as f:
                json.dump(matches_json, f, indent=4)
            logging.info(f"Sensitive information matches saved to {output_file}")
        except Exception as e:
            logging.error(f"Error saving matches: {e}")
            raise

def main(pst_file: str, custom_keywords_file: Optional[str] = None) -> None:
    """Main function to initialize scanning and process a PST file."""
    try:
        scanner = PSTScanner(custom_keywords_file=custom_keywords_file)
        scanner.scan_pst_file(pst_file)
        scanner.save_matches()
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pst_scanner.py <path_to_pst_file> [optional_custom_keywords_file]")
        sys.exit(1)

    pst_file_path = sys.argv[1]
    custom_keywords_path = sys.argv[2] if len(sys.argv) > 2 else None
    main(pst_file_path, custom_keywords_path)
