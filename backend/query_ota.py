import sqlite3
conn = sqlite3.connect('inksight.db')
rows = conn.execute("SELECT mac, ota_version, ota_url, pending_ota, ota_result FROM device_state WHERE ota_url!=''").fetchall()
for r in rows:
    print(r)
conn.close()
