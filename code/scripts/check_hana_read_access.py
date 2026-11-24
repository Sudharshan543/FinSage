
import os
from dotenv import load_dotenv
from hdbcli import dbapi

load_dotenv()

conn = None

try:
    conn = dbapi.connect(
        address=os.getenv("HANA_HOST"),
        port=int(os.getenv("HANA_PORT", "443")),
        user=os.getenv("HANA_USER"),
        password=os.getenv("HANA_PASSWORD")
    )

    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM DBADMIN.FINSAGE_INVOICES
    """)
    invoice_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM DBADMIN.FINSAGE_EXPENSE_EXCEPTIONS
    """)
    exception_count = cursor.fetchone()[0]

    print("DATABASE OPERATIONS SUCCESSFUL!")
    print("Invoice records:", invoice_count)
    print("Expense exception records:", exception_count)

except Exception as e:
    print("DATABASE TEST FAILED:")
    print(e)

finally:
    if conn:
        conn.close()
