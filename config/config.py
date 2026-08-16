import os
from dotenv import load_dotenv

load_dotenv()

# Database Configuration
DB_CONFIG = {
    "server": os.getenv("DB_SERVER"),
    "database": os.getenv("DB_DATABASE"),
    "username": os.getenv("DB_USERNAME"),
    "password": os.getenv("DB_PASSWORD"),
}

# Email Configuration
EMAIL_CONFIG = {
    "sender_email": os.getenv("SENDER_EMAIL"),
    "sender_password": os.getenv("SENDER_PASSWORD"),
    "sender_name": os.getenv("SENDER_NAME", "Accounts Receivable Department"),
    "smtp_server": os.getenv("SMTP_SERVER", "smtp.office365.com"),
    "smtp_port": int(os.getenv("SMTP_PORT", 587)),
}

TEST_EMAIL = os.getenv("TEST_EMAIL")

# Company No. → Contact Email mapping
COMPANY_EMAIL_MAP = {
    1: "COMPANY_1_EMAIL",
    2: "COMPANY_2_EMAIL",
    3: "COMPANY_3_EMAIL",
    4: "COMPANY_4_EMAIL",
    5: "COMPANY_5_EMAIL",
    6: "COMPANY_6_EMAIL",
    7: "COMPANY_7_EMAIL",
    8: "COMPANY_8_EMAIL",
}

DEFAULT_CONTACT_EMAIL = "DEFAULT_EMAIL"

# White logo embedded in emails via CID (Content-ID).
# Place topcast_white.png under templates/emails/ (or set a full path).
# HTML uses src="cid:topcast_logo" — works in Outlook without public hosting.
LOGO_PATH = os.path.join("templates", "emails", "company_logo.png")

# Trial mode: only send to these (Customer Name + Company No.) pairs
# Exact customer name match + company number
# Leave empty list [] to process no one in trial mode
TRIAL_TARGETS = [
    {"customer_name": "KOREAN AIR", "company_no": 1},
    {"customer_name": "BOLIVIANA DE AVIACION", "company_no": 2},
    {"customer_name": "ASIANA AIRLINES", "company_no": 6},
    {"customer_name": "DATATRONIC EXCEL LIMITED", "company_no": 8}
]

TRIAL_SAFE_TO = 
    "INTERNAL_TRIAL_SEND_EMAIL"
]

TRIAL_SAFE_CC = [
    "INTERNAL_TRIAL_CC_EMAIL"
]

# CC recipients (applied to all outgoing emails)
# Leave empty list [] for no CC
CC_EMAILS = [
    "CC_EMAIL"
]
