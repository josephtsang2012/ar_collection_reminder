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
    "sender_name": os.getenv("SENDER_NAME", "TOPCAST Accounts Receivable Department"),
    "smtp_server": os.getenv("SMTP_SERVER", "smtp.office365.com"),
    "smtp_port": int(os.getenv("SMTP_PORT", 587)),
}

TEST_EMAIL = os.getenv("TEST_EMAIL")

# Company No. → Contact Email mapping
COMPANY_EMAIL_MAP = {
    1: "TASCL_AR@topcast.com",
    2: "ar@topcastusa.com",
    3: "STIECL_AR@topcast.com",
    4: "TAEL_AR@topcast.com",
    5: "TAPL_AR@topcast.com",
    6: "TASL_AR@topcast.com",
    7: "AML_AR@topcast.com",
    8: "TTSCL_AR@topcast.com",
}

DEFAULT_CONTACT_EMAIL = "Default@topcast.com"

# White logo embedded in emails via CID (Content-ID).
# Place topcast_white.png under templates/emails/ (or set a full path).
# HTML uses src="cid:topcast_logo" — works in Outlook without public hosting.
LOGO_PATH = os.path.join("templates", "emails", "topcast_white.png")

# Trial mode: only send to these (Customer Name + Company No.) pairs
# Exact customer name match + company number
# Leave empty list [] to process no one in trial mode
TRIAL_TARGETS = [
    {"customer_name": "KOREAN AIR", "company_no": 1},
    {"customer_name": "BOLIVIANA DE AVIACION", "company_no": 2},
    {"customer_name": "ASIANA AIRLINES", "company_no": 6},
    {"customer_name": "DATATRONIC EXCEL LIMITED", "company_no": 8}
    # {"customer_name": "AIR CHINA IMP & EXP CO., LTD.", "company_no": 1},
    # {"customer_name": "EGYPT AIR", "company_no": 1},
    # {"customer_name": "CHINA EASTERN AVIATION IMP & EXP CORP", "company_no": 1},
    # {"customer_name": "MALAYSIA AIRLINES BERHAD", "company_no": 1},
    # {"customer_name": "HONG KONG AIRLINES", "company_no": 6},
    # {"customer_name": "LATAM AIRLINES GROUP S.A (REV1)", "company_no": 2},
    # {"customer_name": "UNITED AIRLINES", "company_no": 2},
    # {"customer_name": "OMNION POWER MUMBAI PVT. LTD (F/K/A CHEROKEE)", "company_no": 8},
    # {"customer_name": "FL TECHNICS, UAB", "company_no": 4},
    # {"customer_name": "VIRGIN AUSTRALIA (ABN# 36090670965)", "company_no": 5}
]

TRIAL_SAFE_TO = [
    # "elaine.chan@topcast.com",   # optional
    # "esther.lo@topcast.com"
    "joseph.tsang@topcast.com",
    # "memo.titat@topcast.com"
]

TRIAL_SAFE_CC = [
    "memo.titat@topcast.com",
    "tianyue.qian@topcast.com"
]

# CC recipients (applied to all outgoing emails)
# Leave empty list [] for no CC
CC_EMAILS = [
    "joseph.tsang@topcast.com",
    "memo.titat@topcast.com",
    "tianyue.qian@topcast.com"
]
