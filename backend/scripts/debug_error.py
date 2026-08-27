import sqlite3
con = sqlite3.connect('storage/app.db')
rows = con.execute(
    "SELECT node, event_type, status, output FROM trace_events WHERE event_type='ERROR' ORDER BY id DESC LIMIT 3"
).fetchall()
for r in rows:
    print('NODE:', r[0], '| STATUS:', r[2])
    print('OUTPUT:', r[3])
con.close()
