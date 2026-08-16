import pandas as pd
import os
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import smtplib

# ================== CONFIG ==================
SENDER_NAME = "Test"
SENDER_EMAIL = "test_email"                 # Change this
SENDER_PASSWORD = r"sender_pw"              # Use App Password if 2FA
SMTP_SERVER = "smtp.office365.com"          # Outlook / Office 365
SMTP_PORT = 587
# ===========================================

def load_template(template_path="templates/statement_of_accounts.html"):
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()

def generate_html_from_df(df: pd.DataFrame, customer_name: str):
    """Generate HTML by filling the template with DataFrame data"""
    template = load_template()
    
    # Build table rows
    rows = ""
    for _, row in df.iterrows():
        rows += f"""
        <tr>
            <td>{row.get('Document Date', '')}</td>
            <td>{row.get('PO#', '')}</td>
            <td><strong>{row.get('Invoice #', '')}</strong></td>
            <td class="amount">${row.get('Invoice Amt.', 0):,.2f}</td>
            <td class="amount">${row.get('Balance', 0):,.2f}</td>
            <td>{row.get('Due Date', '')}</td>
        </tr>
        """
    
    total_overdue = df['Balance'].sum() if 'Balance' in df.columns else 0.0
    
    html = template.replace("{{customer_name}}", customer_name)
    html = html.replace("{{invoice_rows}}", rows)
    html = html.replace("{{total_overdue:,.2f}}", f"{total_overdue:,.2f}")
    html = html.replace("{{year}}", str(datetime.now().year))
    
    return html

def send_html_email(to_email, subject, html_body, attachments=None):
    """Your original function (slightly cleaned)"""
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
        
        if isinstance(to_email, list):
            msg['To'] = ", ".join(to_email)
            recipients = to_email
        else:
            msg['To'] = to_email
            recipients = [to_email]
        
        msg['Subject'] = subject
        msg.attach(MIMEText(html_body, 'html'))

        if attachments:
            for file_path, new_filename in attachments.items():
                if os.path.isfile(file_path):
                    with open(file_path, "rb") as f:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename={new_filename}')
                    msg.attach(part)

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, recipients, msg.as_string())
        server.quit()
        
        print(f" Email sent successfully to: {to_email}")
        return True
        
    except Exception as e:
        print(f"❌ Error sending email: {str(e)}")
        return False

# ================== MAIN TEST FUNCTION ==================
def send_overdue_statement(to_email, customer_name: str, df: pd.DataFrame):
    """Main function to send statement"""
    subject = f"[Test] Statement of Accounts - Overdue Balance - {customer_name}"
    html_body = generate_html_from_df(df, customer_name)
    
    return send_html_email(to_email, subject, html_body)
