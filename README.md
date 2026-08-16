# Customer AR Reminder

Automated email reminders for overdue customer invoices.

Retrieves overdue invoice data from SQL Server, determines sender and recipient details (i.e., To / CC / From) from the `CONTACTS` table, groups invoices by **Customer + Company** (i.e., per customer in each subsidiary company within the Group), and delivers HTML reminder emails through Microsoft 365 SMTP.


---

## Requirements

- Python 3.10+
- ODBC driver for SQL Server (`SQL Server`, 17, or 18 — must match `src/database.py`)
- Network access to SQL Server and `smtp.office365.com`
- Microsoft 365 mailbox with:
  - **Authenticated SMTP** enabled
  - **App password** (recommended if MFA is on)
  - **Send As** on company DG addresses used as From (CONTACTS `SA01`)

---

## Project structure

```
overdue_reminder_system/
├── config/
│   └── config.py              # DB/email config, trial lists, company map
├── queries/
│   └── simple_overdue_invoices.sql
├── src/
│   ├── database.py            # Engine, overdue query, CONTACTS lookups
│   ├── email_sender.py        # HTML build, SMTP send, logs, run folders
│   └── report_generator.py    # Standardize columns, Days Overdue, grouping
├── templates/emails/
│   └── statement_of_accounts.html
├── emails/                    # Generated HTML (created at runtime)
├── logs/                      # CSV run logs (created at runtime)
├── main.py
├── test_send_as.py            # SMTP / Send As smoke test
├── requirements.txt
├── .env.example
└── README.md
```

---

## Setup

### 1. Install dependencies

```bash
cd overdue_reminder_system
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
DB_SERVER=...
DB_DATABASE=...
DB_USERNAME=...
DB_PASSWORD=...

SENDER_EMAIL=your.mailbox@company.com
SENDER_PASSWORD=your_app_password
SENDER_NAME=Accounts Receivable Department
SMTP_SERVER=smtp.office365.com
SMTP_PORT=587

TEST_EMAIL=you@company.com
```

**Do not commit `.env`.**

### 3. Configure `config/config.py`

| Setting | Purpose |
|---------|---------|
| `COMPANY_EMAIL_MAP` | Reply-To / body contact email by company no. |
| `TRIAL_TARGETS` | `[{"customer_name": "...", "company_no": 1}, ...]` |
| `TRIAL_SAFE_TO` / `TRIAL_SAFE_CC` | Internal addresses for `trial-safe` mode |
| `CC_EMAILS` | Optional global CC on every send |

### 4. SQL

- Overdue logic: `queries/simple_overdue_invoices.sql`  
  Must include **`ACCTNO`** (and company, amounts, dates used by the app).
- Contact emails are loaded separately from `CONTACTS` (not joined into the overdue query).

---

## How addresses work

| Field | Source |
|-------|--------|
| **To** | `CONTACTS` where `ccode LIKE '%SA1[0-9]%'`, `division='AVA'`, `depart='320'` — all distinct emails on To |
| **CC** | `CONTACTS` where `ccode LIKE '%SA[2-9][0-9]%'` **or** `ccode='SA01'` (same division/depart) + optional `CC_EMAILS` |
| **From** | First distinct email from `CONTACTS` `ccode='SA01'` for that `ACCTNO` |
| **Reply-To** | `COMPANY_EMAIL_MAP[company_no]` |
| **SMTP login** | Always `SENDER_EMAIL` + app password from `.env` (mailbox, not DG) |

Emails in `CONTACTS.EMAIL` may contain multiple addresses separated by `;`.

---

## Run modes

```bash
python main.py --mode dry-run
python main.py --mode test
python main.py --mode trial-safe
python main.py --mode trial
python main.py --mode prod
```

| Mode | Who is processed | To / CC | Sends mail? |
|------|------------------|---------|-------------|
| `dry-run` | All groups | Logged only | **No** |
| `test` | All groups | Forced to `TEST_EMAIL` | Yes |
| `trial-safe` | `TRIAL_TARGETS` only | Forced to `TRIAL_SAFE_TO` / `TRIAL_SAFE_CC` | Yes |
| `trial` | `TRIAL_TARGETS` only | **Real** CONTACTS emails | Yes |
| `prod` | All groups | **Real** CONTACTS emails | Yes |

**Recommended path:** `dry-run` → `trial-safe` → `trial` → `prod`.

---

## Outputs

Each run gets a **new** dated folder and log (never overwrites same-day runs):

```
emails/2026-08-04 (dry-run 1)/
logs/email_log_2026-08-04 (dry-run 1).csv
```

Log columns include: Customer, Company No, **Trial (Y/N)**, To, CC, Status, invoice count, amount, saved HTML path.

Statuses include: `DRY_RUN`, `SUCCESS`, `FAILED`, `SKIPPED_NO_EMAIL`.

---

## SMTP / Send As check

```bash
python test_send_as.py
```

Edit `FROM_ADDRESS`, `CC_ADDRESSES`, etc. at the top of the script.  
Login uses `.env`; From can be a DG only if **Send As** is granted on that DG.

---

## Windows Task Scheduler

1. **Program:** full path to `python.exe` (venv preferred)  
2. **Arguments:** `main.py --mode trial-safe` (or `trial` / `prod` later)  
3. **Start in:** full path to project root (folder that contains `main.py` and `.env`)  
4. Run as a user that can reach SQL Server and the internet  
5. Confirm last run result `0x0` and check the newest log under `logs/`

Example `.bat`:

```bat
cd /d D:\path\to\overdue_reminder_system
python main.py --mode trial-safe
```

---

## Overdue business rules (summary)

- Positive converted open amount (`C_OA` / COA ≥ 1)
- Due date before today (Days Overdue > 0)
- Void handling: DOC_NO with any `DOC_STATUS = 11` excluded (as implemented in SQL)
- Intercompany names excluded
- Non-shipped invoices **included** (by design vs original AR script)

---

## Safety notes

- System is **read-only** against the database for invoice data.
- Never commit secrets (`.env`).
- Prefer `trial-safe` on the scheduler until Account confirms real customer sends.
- Official email template is light theme; branding may still be refined by the team.

---

## Future ideas

- Customer self-service portal
- Failure alerts (Teams / email when status = FAILED)
- Log / HTML retention cleanup
- Microsoft Graph send (alternative to SMTP)
