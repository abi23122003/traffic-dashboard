import sqlite3
conn = sqlite3.connect('traffic_analysis.db')
c = conn.cursor()
c.execute("DELETE FROM officer_dispatch_status")
print('Cleared rows:', c.rowcount)
conn.commit()
conn.close()
