import pandas as pd
from datetime import datetime


def standardize_overdue_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize column names from simple_overdue_invoices.sql
    to a consistent internal format.
    """
    if df.empty:
        return df
    
    column_mapping = {
        'Invoice No.': 'InvoiceNo',
        'Customer Name': 'CustomerName',
        'Company No.': 'CompanyNo',
        'Converted Currency': 'Currency',
        'Document Date': 'DocumentDate',
        'Due Date': 'DueDate',
        'Invoice Total': 'InvoiceTotal',
        'Converted Invoice Total': 'ConvertedInvoiceTotal',
        'Open Balance': 'OpenBalance',
        'Converted Open Balance': 'ConvertedOpenBalance',
        'OA': 'OA',
        'C_OA': 'COA',
        'Apply to Period': 'ApplyToPeriod',
        'Customer PO': 'CustomerPO',
        'Customer Email': 'CustomerEmail',
        'ACCTNO': 'ACCTNO',
        'AcctNo': 'ACCTNO',
    }
    
    for old_col, new_col in column_mapping.items():
        if old_col in df.columns and new_col not in df.columns:
            df = df.rename(columns={old_col: new_col})
    
    return df


def calculate_days_overdue(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate Days Overdue based on calendar days.
    Both today and DueDate are floored (rounded down) to the start of the day before calculating.
    """
    if df.empty:
        return df
    
    df = df.copy()
    
    # Handle both possible column names
    if 'Due Date' in df.columns:
        df['DueDate'] = pd.to_datetime(df['Due Date'])
    elif 'DueDate' in df.columns:
        df['DueDate'] = pd.to_datetime(df['DueDate'])
    else:
        print("Warning: No 'Due Date' or 'DueDate' column found.")
        return df
    
    # Round down (floor) both dates to the start of the day
    due_date_floored = df['DueDate'].dt.floor('D')
    today_floored = pd.Timestamp.now().floor('D')
    
    df['DaysOverdue'] = (today_floored - due_date_floored).dt.days
    
    return df


def group_invoices_by_customer(df: pd.DataFrame):
    """
    Group overdue invoices by Customer Name + Company No.
    Returns a dictionary: {(customer_name, company_no): customer_df}
    
    One email will be sent per company for the same customer.
    """
    if df.empty:
        return {}
    
    # Ensure standardized column names
    if 'CustomerName' not in df.columns and 'Customer Name' in df.columns:
        df = df.rename(columns={'Customer Name': 'CustomerName'})
    
    if 'CompanyNo' not in df.columns and 'Company No.' in df.columns:
        df = df.rename(columns={'Company No.': 'CompanyNo'})
    
    grouped = {}
    
    if 'CompanyNo' in df.columns:
        # Ensure CompanyNo is integer for consistent mapping
        df = df.copy()
        df['CompanyNo'] = pd.to_numeric(df['CompanyNo'], errors='coerce')
        
        # Group by Customer + Company
        for (customer, company), group_df in df.groupby(['CustomerName', 'CompanyNo'], dropna=False):
            # Convert to plain Python int (or None)
            company_key = int(company) if pd.notna(company) else None
            grouped[(customer, company_key)] = group_df.copy()
    else:
        # Fallback: group by Customer only (if CompanyNo not available)
        print("⚠️  Warning: CompanyNo column not found – grouping by customer only")
        for customer in df['CustomerName'].unique():
            customer_df = df[df['CustomerName'] == customer].copy()
            grouped[(customer, None)] = customer_df
    
    return grouped


def calculate_customer_summary(df: pd.DataFrame):
    """Calculate summary statistics per customer"""
    if df.empty:
        return pd.DataFrame()
    
    amount_col = 'COA' if 'COA' in df.columns else 'OA' if 'OA' in df.columns else None
    
    if amount_col is None:
        return pd.DataFrame()
    
    summary = df.groupby('CustomerName').agg(
        Total_Overdue=(amount_col, 'sum'),
        Invoice_Count=('InvoiceNo', 'count'),
        Oldest_Due_Date=('DueDate', 'min')
    ).reset_index()
    
    return summary