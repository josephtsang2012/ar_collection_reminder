import os
import csv
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email import encoders
import pandas as pd
from config.config import EMAIL_CONFIG, TEST_EMAIL

# Inline logo for CID embedding (place topcast_white.png here)
DEFAULT_LOGO_PATH = os.path.join("templates", "emails", "topcast_white.png")
LOGO_CID = "topcast_logo"


def load_html_template(template_path="templates/emails/statement_of_accounts.html"):
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


def generate_customer_email_html(customer_name: str, customer_df, contact_email: str = None, template_path="templates/emails/statement_of_accounts.html"):
    """Generate personalized HTML email for one customer"""
    from config.config import DEFAULT_CONTACT_EMAIL
    if contact_email is None:
        contact_email = DEFAULT_CONTACT_EMAIL
    template = load_html_template(template_path)
    
    # Desired column order and display names
    # Order: Your Purchase Order No., Invoice No., Invoice Date, Invoice Amount, Open Balance, Currency, Due Date, Days Overdue
    email_columns = [
        ('CustomerPO', 'Your Purchase Order No.'),
        ('InvoiceNo', 'Invoice No.'),
        ('DocumentDate', 'Invoice Date'),
        ('ConvertedInvoiceTotal', 'Invoice Amount'),
        ('COA', 'Open Balance'),
        ('Currency', 'Currency'),
        ('DueDate', 'Due Date'),
        ('DaysOverdue', 'Days Overdue'),
    ]
    
    # Keep only available columns (preserve order)
    available = [(src, display) for src, display in email_columns if src in customer_df.columns]
    
    # Build table rows
    rows = ""
    for _, row in customer_df.iterrows():
        rows += "<tr>"
        for src_col, display_name in available:
            value = row[src_col]
            
            if display_name in ['Invoice Amount', 'Open Balance']:
                try:
                    value = f"{float(value):,.2f}"
                except:
                    value = str(value)
            elif display_name in ['Invoice Date', 'Due Date']:
                try:
                    value = pd.to_datetime(value).strftime('%m/%d/%Y')
                except:
                    value = str(value) if value is not None else ""
            elif display_name == 'Days Overdue':
                try:
                    value = int(value)
                except:
                    value = str(value)
            else:
                value = str(value) if value is not None else ""
            
            # Right-align amount columns
            if display_name in ['Invoice Amount', 'Open Balance']:
                rows += f'<td class="amount">{value}</td>'
            elif display_name == 'Days Overdue':
                rows += f'<td style="text-align:center; color:#d93025;"><strong>{value}</strong></td>'
            else:
                rows += f"<td>{value}</td>"
        rows += "</tr>"
    
    # Summary values
    num_invoices = len(customer_df)
    total_amount = 0
    if 'COA' in customer_df.columns:
        total_amount = customer_df['COA'].sum()
    elif 'OA' in customer_df.columns:
        total_amount = customer_df['OA'].sum()
    
    # Logo via CID (embedded in send_html_email) — works in Outlook without hosting
    logo_src = f"cid:{LOGO_CID}"

    html = template.replace("{{customer_name}}", str(customer_name))
    html = html.replace("{{invoice_rows}}", rows)
    html = html.replace("{{invoice_count}}", str(num_invoices))
    html = html.replace("{{total_overdue:,.2f}}", f"{total_amount:,.2f}")
    html = html.replace("{{contact_email}}", str(contact_email))
    html = html.replace("{{year}}", str(datetime.now().year))
    html = html.replace("{{logo_url}}", logo_src)
    
    return html


def allocate_run_paths(mode: str, emails_base: str = "emails", logs_base: str = "logs"):
    """
    Create a new dated run folder + log file for this mode.
    Never overwrites an existing same-day run; uses (mode 1), (mode 2), ...

    Returns: (run_label, email_folder, log_file)
      e.g. ("2026-07-29 (dry-run 1)", "emails/2026-07-29 (dry-run 1)", "logs/email_log_2026-07-29 (dry-run 1).csv")
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    safe_mode = str(mode).strip() or "run"
    os.makedirs(emails_base, exist_ok=True)
    os.makedirs(logs_base, exist_ok=True)

    n = 1
    while True:
        run_label = f"{today_str} ({safe_mode} {n})"
        email_folder = os.path.join(emails_base, run_label)
        log_file = os.path.join(logs_base, f"email_log_{run_label}.csv")
        if not os.path.exists(email_folder) and not os.path.exists(log_file):
            # email_folder is created only when HTML is saved (dry-run)
            return run_label, email_folder, log_file
        n += 1


def save_email_html(customer_name: str, html_body: str, email_folder: str) -> str:
    """
    Save the generated HTML email into the run folder.
    Returns the full path of the saved file.
    """
    os.makedirs(email_folder, exist_ok=True)
    
    # Clean customer name for filename
    safe_name = "".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in str(customer_name))
    safe_name = safe_name.strip().replace(" ", "_")[:80]
    
    timestamp = datetime.now().strftime("%H%M%S")
    filename = f"{safe_name}_{timestamp}.html"
    file_path = os.path.join(email_folder, filename)
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_body)
    
    return file_path


def log_email_result(customer_name: str, recipient: str, status: str, 
                     invoice_count: int = 0, total_amount: float = 0.0,
                     saved_file: str = "", error_message: str = "",
                     cc: str = "", company_no=None, is_trial: bool = False,
                     log_file: str = None):
    """
    Append a log entry to the run's CSV log file.
    """
    if not log_file:
        # fallback if caller did not pass a run log path
        _, _, log_file = allocate_run_paths("unknown")
    
    log_dir = os.path.dirname(log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    
    file_exists = os.path.isfile(log_file)
    
    with open(log_file, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        
        if not file_exists:
            writer.writerow([
                "Timestamp", "Customer Name", "Company No", "Trial", "To", "CC", "Status",
                "Invoice Count", "Total Amount", "Saved File", "Error Message"
            ])
        
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            customer_name,
            company_no if company_no is not None else "",
            "Y" if is_trial else "N",
            recipient,
            cc,
            status,
            invoice_count,
            f"{total_amount:.2f}",
            saved_file,
            error_message
        ])


def send_html_email(to_email, subject, html_body, attachments=None, cc_emails=None,
                    from_email=None, reply_to=None, logo_path=None):
    """
    Send HTML email via Outlook SMTP.
    
    - to_email: str or list of str (Option A: all distinct addresses on To:)
    - SMTP login always uses EMAIL_CONFIG (single account).
    - reply_to can be company-specific.
    - logo_path: optional path to white logo PNG; embedded as CID inline image.
    """
    try:
        if cc_emails is None:
            cc_emails = []
        
        # Normalize To: to a list
        if isinstance(to_email, str):
            to_list = [e.strip() for e in to_email.split(',') if e.strip()]
        else:
            to_list = [str(e).strip() for e in to_email if e and str(e).strip()]
        
        if not to_list:
            print("❌ No valid To: address")
            return False
        
        to_header = ", ".join(to_list)
        
        # From: default sender mailbox
        actual_from = from_email or EMAIL_CONFIG['sender_email']
        from_header = f"{EMAIL_CONFIG['sender_name']} <{actual_from}>"
        
        # "related" root so HTML can reference cid: inline images
        msg = MIMEMultipart("related")
        msg["From"] = from_header
        msg["To"] = to_header
        if cc_emails:
            msg["Cc"] = ", ".join(cc_emails)
        if reply_to:
            msg["Reply-To"] = reply_to
        msg["Subject"] = subject
        
        msg.attach(MIMEText(html_body, "html"))

        # Embed white logo as CID (src="cid:topcast_logo" in HTML)
        logo_file = logo_path or DEFAULT_LOGO_PATH
        try:
            from config.config import LOGO_PATH
            if LOGO_PATH:
                logo_file = LOGO_PATH
        except ImportError:
            pass

        if logo_file and os.path.isfile(logo_file):
            with open(logo_file, "rb") as f:
                img_data = f.read()
            # Guess subtype from extension
            subtype = "png"
            if logo_file.lower().endswith(".jpg") or logo_file.lower().endswith(".jpeg"):
                subtype = "jpeg"
            img = MIMEImage(img_data, _subtype=subtype)
            img.add_header("Content-ID", f"<{LOGO_CID}>")
            img.add_header("Content-Disposition", "inline", filename=os.path.basename(logo_file))
            msg.attach(img)
            print(f"   🖼️  Logo embedded (CID): {logo_file}")
        else:
            print(f"   ⚠️  Logo file not found: {logo_file} (email sent without logo)")

        if attachments:
            for file_path, new_filename in attachments.items():
                if os.path.isfile(file_path):
                    with open(file_path, "rb") as f:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition", f"attachment; filename={new_filename}")
                    msg.attach(part)

        # Recipients must include all To + CC for SMTP
        all_recipients = to_list + list(cc_emails)

        server = smtplib.SMTP(EMAIL_CONFIG["smtp_server"], EMAIL_CONFIG["smtp_port"])
        server.starttls()
        server.login(EMAIL_CONFIG["sender_email"], EMAIL_CONFIG["sender_password"])
        server.sendmail(EMAIL_CONFIG["sender_email"], all_recipients, msg.as_string())
        server.quit()
        
        cc_info = f" (CC: {', '.join(cc_emails)})" if cc_emails else ""
        print(f"✅ Email sent to: {to_header}{cc_info}")
        print(f"   From: {actual_from} | Reply-To: {reply_to or actual_from}")
        return True
        
    except Exception as e:
        print(f"❌ Error sending email to {to_email}: {str(e)}")
        return False


def send_overdue_statement(to_email, customer_name, customer_df, mode: str = "test", company_no=None, extra_cc=None, from_dg=None, is_trial: bool = False, email_folder: str = None, log_file: str = None):
    """
    Main function to process one customer's overdue statement.
    
    extra_cc: CC from CONTACTS SA2–SA9
    from_dg: From address (DG from CONTACTS ccode SA01)
    Reply-To: COMPANY_EMAIL_MAP by company_no
    SMTP login: always SENDER_EMAIL in .env
    is_trial: mark log row as trial target (Y/N)
    email_folder / log_file: this run's output paths (from allocate_run_paths)
    """
    from config.config import COMPANY_EMAIL_MAP, DEFAULT_CONTACT_EMAIL
    
    # Reply-To = company contact map
    contact_email = DEFAULT_CONTACT_EMAIL
    if company_no is not None:
        try:
            company_key = int(company_no)
            contact_email = COMPANY_EMAIL_MAP.get(company_key, DEFAULT_CONTACT_EMAIL)
        except (ValueError, TypeError):
            contact_email = DEFAULT_CONTACT_EMAIL
    
    # From = DG from CONTACTS SA01
    actual_from = from_dg or contact_email or EMAIL_CONFIG['sender_email']
    
    subject = f"[REMINDER] Outstanding Invoices - {customer_name}"
    
    html_body = generate_customer_email_html(customer_name, customer_df, contact_email=contact_email)
    
    if not email_folder or not log_file:
        _, email_folder, log_file = allocate_run_paths(mode)
    
    # HTML archive only in dry-run (no SMTP send). Real send modes skip saving HTML.
    saved_file = ""
    if mode == "dry-run":
        save_name = f"{customer_name}_Com{company_no}" if company_no is not None else customer_name
        saved_file = save_email_html(save_name, html_body, email_folder)
        print(f"  📄 Email saved: {saved_file}")
    
    print(f"  📧 Contact email: {contact_email} (Company {company_no})")
    
    invoice_count = len(customer_df)
    total_amount = 0.0
    if 'COA' in customer_df.columns:
        total_amount = float(customer_df['COA'].sum())
    elif 'OA' in customer_df.columns:
        total_amount = float(customer_df['OA'].sum())
    
    # Build To: display string (intended recipients)
    if isinstance(to_email, list):
        to_log = ", ".join(to_email)
    else:
        to_log = str(to_email) if to_email else ""
    
    # CC: config list + contact CC (SA2–SA9), distinct
    from config.config import CC_EMAILS
    cc_list = list(CC_EMAILS) if CC_EMAILS else []
    if extra_cc:
        existing = {e.lower() for e in cc_list}
        for e in extra_cc:
            if e and e.lower() not in existing:
                cc_list.append(e)
                existing.add(e.lower())
    cc_log = ", ".join(cc_list)
    
    # Dry-run: save HTML + log intended To/CC, do not send
    if mode == "dry-run":
        print(f"  💤 Dry-run: Email not sent")
        print(f"  📬 Would To: {to_log}")
        if cc_log:
            print(f"  📎 Would CC: {cc_log}")
        log_email_result(
            customer_name=customer_name,
            recipient=to_log,
            status="DRY_RUN",
            invoice_count=invoice_count,
            total_amount=total_amount,
            saved_file=saved_file,
            cc=cc_log,
            company_no=company_no,
            is_trial=is_trial,
            log_file=log_file,
        )
        return True
    
    # Determine actual recipient for send
    if mode == "test":
        recipient = TEST_EMAIL
        print(f"  🧪 Test mode: sending to {recipient}")
        to_log = str(recipient)
    else:  # prod / trial
        recipient = to_email
        print(f"  📧 Production/Trial: sending to {to_log}")
    
    if cc_list:
        print(f"  📎 CC ({len(cc_list)}): {cc_log}")
    
    # From = CONTACTS SA01 DG; Reply-To = COMPANY_EMAIL_MAP; SMTP login = SENDER_EMAIL
    # IT must grant the login mailbox "Send As" on each From DG
    print(f"  📤 From (DG): {actual_from} | Reply-To: {contact_email} | SMTP login: {EMAIL_CONFIG['sender_email']}")
    
    # Send the email
    success = send_html_email(
        recipient,
        subject,
        html_body,
        cc_emails=cc_list,
        from_email=actual_from,
        reply_to=contact_email,
    )
    
    status = "SUCCESS" if success else "FAILED"
    error_msg = "" if success else "Failed to send email"
    
    log_email_result(
        customer_name=customer_name,
        recipient=to_log,
        status=status,
        invoice_count=invoice_count,
        total_amount=total_amount,
        saved_file=saved_file,
        error_message=error_msg,
        cc=cc_log,
        company_no=company_no,
        is_trial=is_trial,
        log_file=log_file,
    )
    
    return success