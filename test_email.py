from src.database import fetch_simple_overdue_invoices
from src.report_generator import (
    standardize_overdue_dataframe,
    calculate_days_overdue,
    group_invoices_by_customer,
)
from src.email_sender import send_overdue_statement
from config.config import TEST_EMAIL


def test_send_customer_email(customer_name: str = None, company_no: int = None, recipient_email: str = None):
    """
    Test sending overdue email for a specific customer (and optionally a specific company).
    
    Examples:
        # First customer, all companies
        test_send_customer_email()
        
        # Specific customer
        test_send_customer_email(customer_name="ABC TRADING COMPANY")
        
        # Specific customer + company
        test_send_customer_email(customer_name="ABC TRADING COMPANY", company_no=1)
    """
    print("=== Testing Overdue Email ===")
    
    # 1. Fetch data
    df = fetch_simple_overdue_invoices()
    
    if df.empty:
        print("No overdue invoices found.")
        return
    
    print(f"✅ Fetched {len(df)} overdue invoices")
    
    # 2. Standardize + Days Overdue
    df = standardize_overdue_dataframe(df)
    df = calculate_days_overdue(df)
    df = df[df['DaysOverdue'] > 0]
    
    if df.empty:
        print("No strictly overdue invoices found.")
        return
    
    # 3. Group by Customer + Company
    groups = group_invoices_by_customer(df)
    
    # 4. Filter by customer / company if specified
    if customer_name is not None:
        groups = {
            k: v for k, v in groups.items()
            if k[0] == customer_name and (company_no is None or k[1] == company_no)
        }
    
    if not groups:
        print(f"No matching groups found for customer='{customer_name}', company={company_no}")
        print("\nAvailable customers (first 15):")
        all_customers = sorted(set(k[0] for k in group_invoices_by_customer(df).keys()))
        for name in all_customers[:15]:
            print(f"  - {name}")
        return
    
    # 5. Send for each matching group
    recipient = recipient_email or TEST_EMAIL
    print(f"Sending to: {recipient}")
    print(f"Groups to process: {len(groups)}\n")
    
    for (cust_name, comp_no), group_df in groups.items():
        company_label = f"Company {comp_no}" if comp_no is not None else "Unknown"
        print(f"→ {cust_name} | {company_label} ({len(group_df)} invoices)")
        
        success = send_overdue_statement(
            to_email=recipient,
            customer_name=cust_name,
            customer_df=group_df,
            mode="test",
            company_no=comp_no,
        )
        
        if success:
            print("  ✅ Sent successfully\n")
        else:
            print("  ❌ Failed\n")


if __name__ == "__main__":
    # ====================== CONFIGURE HERE ======================
    # Leave as None to take the first available group
    TEST_CUSTOMER = 'AIR NEW ZEALAND LTD.'        # e.g. "ABC TRADING COMPANY"
    TEST_COMPANY = 5           # e.g. 1
    RECIPIENT = None              # None = use TEST_EMAIL from .env
    # ============================================================
    
    test_send_customer_email(
        customer_name=TEST_CUSTOMER,
        company_no=TEST_COMPANY,
        recipient_email=RECIPIENT,
    )