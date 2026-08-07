"""
Test sending with a custom From (e.g. DG) while SMTP login uses .env credentials.

1. Set in .env:
   SENDER_EMAIL=josemurinho@manutd.com     # login mailbox
   SENDER_PASSWORD=...                     # password or app password
   SMTP_SERVER=smtp.office365.com
   SMTP_PORT=587
   TEST_EMAIL=your.real.inbox@...          # where the test message goes

2. Edit FROM / CC below if needed.

3. Run:
   python test_send_as.py
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config.config import EMAIL_CONFIG, TEST_EMAIL

# ============ EDIT THESE FOR YOUR TEST ============
FROM_ADDRESS = "SOA.TASCL@topcast.com"   # From (DG) — needs Send As on this address
REPLY_TO = "TASCL_AR@topcast.com"      # Reply-To
TO_ADDRESS = "memotitat2@gmail.com"   # None = use TEST_EMAIL from .env
CC_ADDRESSES = [                        # CC list (leave empty [] for no CC)
    "memo.titat@topcast.com",
    "joseph.tsang@topcast.com"
]
SUBJECT = "TEST: Send As Group Email check"
# ==================================================


def main():
    to_addr = TO_ADDRESS or TEST_EMAIL
    if not to_addr:
        print("Set TEST_EMAIL in .env or TO_ADDRESS in this script")
        return

    login_email = EMAIL_CONFIG["sender_email"]
    login_password = EMAIL_CONFIG["sender_password"]
    smtp_server = EMAIL_CONFIG["smtp_server"]
    smtp_port = EMAIL_CONFIG["smtp_port"]

    print(login_email, login_password)
    cc_list = [e.strip() for e in CC_ADDRESSES if e and str(e).strip()]

    print("=== Send As test ===")
    print(f"SMTP login : {login_email}")
    print(f"From       : {FROM_ADDRESS}")
    print(f"Reply-To   : {REPLY_TO}")
    print(f"To         : {to_addr}")
    print(f"CC         : {', '.join(cc_list) if cc_list else '(none)'}")
    print(f"Server     : {smtp_server}:{smtp_port}")
    print()

    msg = MIMEMultipart("alternative")
    msg["From"] = FROM_ADDRESS
    msg["To"] = to_addr
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    msg["Reply-To"] = REPLY_TO
    msg["Subject"] = SUBJECT

    body = f"""
    <html><body>
    <p>This is a Send As test.</p>
    <ul>
      <li><strong>SMTP login:</strong> {login_email}</li>
      <li><strong>From header:</strong> {FROM_ADDRESS}</li>
      <li><strong>Reply-To:</strong> {REPLY_TO}</li>
      <li><strong>To:</strong> {to_addr}</li>
      <li><strong>CC:</strong> {', '.join(cc_list) if cc_list else '(none)'}</li>
    </ul>
    <p>If you received this and From shows <code>{FROM_ADDRESS}</code>, Send As is working.</p>
    </body></html>
    """
    msg.attach(MIMEText(body, "html"))

    # SMTP must include To + CC in the recipient list
    recipients = [to_addr] + cc_list

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(login_email, login_password)
        server.sendmail(login_email, recipients, msg.as_string())
        server.quit()
        print("SMTP accepted the message.")
        print("   Check the inbox and open the message headers / From line.")
        print("   - If From = the DG address -> success")
        print("   - If From was rewritten to the login mailbox -> Send As not granted / not allowed over SMTP")
        if cc_list:
            print(f"   - CC should also receive: {', '.join(cc_list)}")
    except Exception as e:
        print(f"Failed: {e}")


if __name__ == "__main__":
    main()