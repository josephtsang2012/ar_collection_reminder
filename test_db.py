from src.database import fetch_simple_overdue_invoices
import pandas as pd

df = fetch_simple_overdue_invoices()

# # Example: Add aging buckets in Python
# df['Due Date'] = pd.to_datetime(df['Due Date'])
# df['Days_Overdue'] = (pd.Timestamp.now() - df['Due Date']).dt.days

# print(df[['Invoice No.', 'Customer Name', 'Open Balance', 'Due Date', 'Days_Overdue']].head())
print(df.head())
print(df.info())
