import sqlite3

conn = sqlite3.connect('inksight.db')
cursor = conn.execute("SELECT mac, ota_url FROM device_state WHERE ota_url!=''")
rows = cursor.fetchall()
print(f"Found {len(rows)} rows with ota_url")

for mac, ota_url in rows:
    if '/api/firmware/download' not in ota_url and '/firmware/download' in ota_url:
        new_url = ota_url.replace('/firmware/download', '/api/firmware/download')
        conn.execute(
            "UPDATE device_state SET ota_url = ? WHERE mac = ?",
            (new_url, mac)
        )
        print(f"Updated: {mac}")
        print(f"  OLD: {ota_url}")
        print(f"  NEW: {new_url}")
    else:
        print(f"Skipped: {mac} — {ota_url}")

conn.commit()

# Verify
cursor = conn.execute("SELECT mac, ota_url, pending_ota, ota_result FROM device_state WHERE ota_url!=''")
print("\nAfter update:")
for r in cursor.fetchall():
    print(r)

conn.close()
