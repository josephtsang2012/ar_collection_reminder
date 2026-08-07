from urllib.parse import quote_plus
import pandas as pd
import re
from sqlalchemy import create_engine, text
from config.config import DB_CONFIG


def get_engine():
    """Create SQLAlchemy engine using a more reliable connection string"""

    encoded_password = quote_plus(DB_CONFIG['password'])  # type: ignore
    conn_str = (
        f"mssql+pyodbc://{DB_CONFIG['username']}:{encoded_password}@{DB_CONFIG['server']}/{DB_CONFIG['database']}"
        "?driver=SQL+Server"
    )

    engine = create_engine(conn_str)
    return engine


def fetch_overdue_invoices(view_name: str = "vw_Overdue_Invoices"):
    """
    Fetch overdue invoices from a database VIEW using SQLAlchemy.
    
    IMPORTANT:
    - Ask your advisor to create or confirm the VIEW name.
    - The view should return at least these columns (or similar):
        CustomerName, InvoiceNo, Balance, DueDate, DocumentDate/InvoiceDate, PO_Number/PO#
    """
    query = f"""
        SELECT * 
        FROM {view_name} 
        WHERE Balance > 0 
        ORDER BY CustomerName, DueDate
    """
    
    engine = get_engine()
    
    try:
        with engine.connect() as connection:
            df = pd.read_sql(text(query), connection)
        
        print(f"✅ Successfully fetched {len(df)} overdue records from {view_name}")
        return df
    except Exception as e:
        print(f"❌ Error fetching data from {view_name}: {e}")
        return pd.DataFrame()


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize common column name variations so the rest of the code works reliably.
    This helps when your advisor uses slightly different column names.
    """
    column_mapping = {
        # Common variations → Standard name
        'CustomerName': 'CustomerName',
        'Customer Name': 'CustomerName',
        'cust_name': 'CustomerName',
        
        'InvoiceNo': 'InvoiceNo',
        'Invoice #': 'InvoiceNo',
        'InvoiceNo.': 'InvoiceNo',
        'inv_no': 'InvoiceNo',
        
        'Balance': 'Balance',
        'BalanceAmount': 'Balance',
        'Outstanding': 'Balance',
        
        'DueDate': 'DueDate',
        'Due Date': 'DueDate',
        
        'DocumentDate': 'DocumentDate',
        'InvoiceDate': 'DocumentDate',
        'Invoice Date': 'DocumentDate',
        
        'PO_Number': 'PO_Number',
        'PO#': 'PO_Number',
        'PO No': 'PO_Number',
    }
    
    # Rename columns if they exist
    for old_col, new_col in column_mapping.items():
        if old_col in df.columns and new_col not in df.columns:
            df = df.rename(columns={old_col: new_col})
    
    return df


def get_customers_with_overdue(df: pd.DataFrame):
    """Return list of unique customers who have overdue invoices"""
    if df.empty:
        return []
    return df['CustomerName'].unique().tolist()


def execute_sql_file(sql_file_path: str):
    """
    Execute a .sql file against the database.
    Handles basic GO batch separators.
    """
    engine = get_engine()
    
    with open(sql_file_path, 'r', encoding='utf-8') as f:
        sql_script = f.read()
    
    # Split by GO (case insensitive)
    batches = [batch.strip() for batch in re.split(r'\bGO\b', sql_script, flags=re.IGNORECASE) if batch.strip()]
    
    try:
        with engine.connect() as connection:
            for i, batch in enumerate(batches, 1):
                if batch:
                    print(f"Executing batch {i}/{len(batches)}...")
                    connection.execute(text(batch))
            connection.commit()
        
        print(f"✅ Successfully executed SQL file: {sql_file_path}")
        return True
    except Exception as e:
        print(f"❌ Error executing SQL file {sql_file_path}: {e}")
        return False


def fetch_ar_outstanding_invoices(view_or_table_name: str = "AR_OUTSTANDING_INVOICES"):
    """
    Fetch data from the AR Outstanding Invoices view/table.
    
    Recommendation:
    - Let your DBA run the complex ar_outstanding_invoices.sql script 
      (via SSMS or SQL Agent Job) to create/update this view or table.
    - Then Python only needs to query it (much simpler and more reliable).
    """
    query = f"SELECT * FROM {view_or_table_name}"
    
    engine = get_engine()
    
    try:
        with engine.connect() as connection:
            df = pd.read_sql(text(query), connection)
        
        print(f"✅ Successfully fetched {len(df)} records from {view_or_table_name}")
        return df
    except Exception as e:
        print(f"❌ Error fetching from {view_or_table_name}: {e}")
        return pd.DataFrame()


def fetch_simple_overdue_invoices():
    """
    Fetch simplified overdue invoices for email reminders.
    Uses queries/simple_overdue_invoices.sql
    """
    sql_file = "queries/simple_overdue_invoices.sql"
    
    engine = get_engine()
    
    with open(sql_file, 'r', encoding='utf-8') as f:
        sql_script = f.read()
    
    try:
        with engine.connect() as connection:
            df = pd.read_sql(text(sql_script), connection)
        
        print(f"✅ Successfully fetched {len(df)} overdue invoices using simple query")
        return df
    except Exception as e:
        print(f"❌ Error running simple overdue query: {e}")
        return pd.DataFrame()


def fetch_contact_emails():
    """
    Fetch contact emails from CONTACTS.
    Returns DataFrame with ACCTNO, EMAIL (EMAIL may contain multiple addresses separated by ;).
    """
    query = """
        SELECT ACCTNO, EMAIL
        FROM CONTACTS
        WHERE ccode LIKE '%SA1[0-9]%'
          AND division = 'AVA'
          AND depart = '320'
          AND EMAIL IS NOT NULL
          AND LTRIM(RTRIM(EMAIL)) <> ''
    """
    
    engine = get_engine()
    
    try:
        with engine.connect() as connection:
            df = pd.read_sql(text(query), connection)
        
        print(f"✅ Successfully fetched {len(df)} To: contact row(s) from CONTACTS")
        return df
    except Exception as e:
        print(f"❌ Error fetching contact emails: {e}")
        return pd.DataFrame()


def fetch_contact_cc_emails():
    """
    Fetch CC contact emails from CONTACTS.
    ccode SA2x–SA9x → CC recipients.
    EMAIL may contain multiple addresses separated by ;.
    """
    query = """
        SELECT ACCTNO, EMAIL
        FROM CONTACTS
          WHERE (ccode LIKE '%SA[2-9][0-9]%' OR ccode LIKE '%SA01%')
          AND division = 'AVA'
          AND depart = '320'
          AND EMAIL IS NOT NULL
          AND LTRIM(RTRIM(EMAIL)) <> ''
    """
    
    engine = get_engine()
    
    try:
        with engine.connect() as connection:
            df = pd.read_sql(text(query), connection)
        
        print(f"✅ Successfully fetched {len(df)} CC contact row(s) from CONTACTS")
        return df
    except Exception as e:
        print(f"❌ Error fetching CC contact emails: {e}")
        return pd.DataFrame()


def fetch_from_dg_emails():
    """
    Fetch From (DG) addresses from CONTACTS.
    ccode = 'SA01' → sender DG per ACCTNO.
    """
    query = """
        SELECT ACCTNO, EMAIL
        FROM CONTACTS
        WHERE ccode LIKE '%SA01%'
          AND division = 'AVA'
          AND depart = '320'
          AND EMAIL IS NOT NULL
          AND LTRIM(RTRIM(EMAIL)) <> ''
    """
    
    engine = get_engine()
    
    try:
        with engine.connect() as connection:
            df = pd.read_sql(text(query), connection)
        
        print(f"✅ Successfully fetched {len(df)} From/DG contact row(s) from CONTACTS (SA01)")
        return df
    except Exception as e:
        print(f"❌ Error fetching From/DG contact emails: {e}")
        return pd.DataFrame()


def build_acctno_email_map(contacts_df: pd.DataFrame) -> dict:
    """
    Build ACCTNO -> list of distinct email addresses.
    Splits EMAIL on ';' and deduplicates (case-insensitive).
    return: {'ACCTNO':[distinct email list seperated by ;]}
    """
    email_map = {}
    
    if contacts_df.empty:
        return email_map
    
    for _, row in contacts_df.iterrows():
        acctno = str(row['ACCTNO']).strip() if pd.notna(row['ACCTNO']) else None
        raw = str(row['EMAIL']).strip() if pd.notna(row['EMAIL']) else ''
        
        if not acctno or not raw:
            continue
        
        parts = [p.strip() for p in raw.replace(',', ';').split(';') if p.strip()]
        
        if acctno not in email_map:
            email_map[acctno] = []
        
        existing_lower = {e.lower() for e in email_map[acctno]}
        for p in parts:
            if p.lower() not in existing_lower:
                email_map[acctno].append(p)
                existing_lower.add(p.lower())
    
    print(f"✅ Built email map for {len(email_map)} account(s)")
    return email_map
