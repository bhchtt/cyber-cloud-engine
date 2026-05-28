import sqlite3
conn = sqlite3.connect('cloud.db')
conn.execute('''CREATE TABLE IF NOT EXISTS vms (
    id TEXT PRIMARY KEY, student_id TEXT NOT NULL, vm_name TEXT UNIQUE NOT NULL,
    status TEXT DEFAULT 'pending', vnc_port INTEGER, token TEXT UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
conn.commit(); conn.close()
print("✅ База cloud.db створена!")
