import sqlite3
conn = sqlite3.connect('traffic_analysis.db')
c = conn.cursor()
c.execute('SELECT COUNT(*) FROM users')
print('Total users:', c.fetchone()[0])
c.execute('SELECT id, username, department, district_id FROM users LIMIT 10')
print(c.fetchall())
conn.close()
