import sqlite3, time, subprocess, os
from worker import update_tokens, VM_DIR, CLOUD_INIT_DIR

def cleanup():
    conn = sqlite3.connect('cloud.db', timeout=30)
    cur = conn.cursor()
    cur.execute("SELECT id, vm_name FROM vms WHERE status IN ('ready', 'error') AND created_at <= datetime('now', '-2 hours')")
    
    for vm_id, vm_name in cur.fetchall():
        print(f"💀 [GC] Видалення {vm_name}")
        subprocess.run(["sudo", "virsh", "destroy", vm_name], stderr=subprocess.DEVNULL)
        subprocess.run(["sudo", "virsh", "undefine", vm_name], stderr=subprocess.DEVNULL)
        try: os.remove(os.path.join(VM_DIR, f"{vm_name}.qcow2"))
        except: pass
        try: os.remove(os.path.join(CLOUD_INIT_DIR, f"{vm_name}-seed.iso"))
        except: pass
        cur.execute("UPDATE vms SET status = 'deleted' WHERE id = ?", (vm_id,))
    
    if cur.rowcount > 0:
        update_tokens(cur)
        conn.commit()
    conn.close()

if __name__ == "__main__":
    print("🧹 Прибиральник запущено...")
    while True:
        cleanup()
        time.sleep(300)
