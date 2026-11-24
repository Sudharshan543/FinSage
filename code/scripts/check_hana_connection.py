
from app.db import get_hana_connection

try:
    connection = get_hana_connection()
    print("SUCCESS: Connected to SAP HANA Cloud!")

    cursor = connection.cursor()
    cursor.execute("SELECT CURRENT_USER FROM DUMMY")
    result = cursor.fetchone()

    print("Connected database user:", result[0])

    cursor.close()
    connection.close()

except Exception as error:
    print("HANA CONNECTION FAILED")
    print(error)
