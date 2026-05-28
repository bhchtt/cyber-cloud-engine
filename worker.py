import sqlite3, time, subprocess, os, re, secrets
from jinja2 import Template

TOKEN_DIR = "/run/cyber_cloud"
TOKEN_FILE = f"{TOKEN_DIR}/vnc_tokens.txt"
os.makedirs(TOKEN_DIR, exist_ok=True)
if not os.path.exists(TOKEN_FILE):
    open(TOKEN_FILE, 'w').close()

VM_DIR = "/var/lib/libvirt/images/vms/"
CLOUD_INIT_DIR = "/var/lib/libvirt/images/seeds/"
TEMPLATES = {"ubuntu": "/var/lib/libvirt/images/templates/ubuntu-template.qcow2"}

def update_tokens(cur):
    # Оновлення мапінгу токенів для noVNC
    cur.execute("SELECT token, vnc_port FROM vms WHERE status='ready'")
    with open(f"{TOKEN_FILE}.tmp", "w") as f:
        for t, p in cur.fetchall(): f.write(f"{t}: 127.0.0.1:{p}\n")
    os.rename(f"{TOKEN_FILE}.tmp", TOKEN_FILE)

def process_queue():
    print("[Worker] Daemon started. Waiting for jobs...")
    while True:
        try:
            conn = sqlite3.connect('cloud.db', timeout=30)
            conn.execute('PRAGMA journal_mode=WAL;')
            cur = conn.cursor()

            # Беремо найстаріше завдання з черги
            job = cur.execute("""
                UPDATE vms
                SET status = 'creating'
                WHERE id = (SELECT id FROM vms WHERE status = 'pending' ORDER BY created_at ASC LIMIT 1)
                RETURNING id, vm_name, token
            """).fetchone()
            conn.commit()

            if job:
                vm_id, vm_name, token = job
                print(f"[Worker] Starting deployment for: {vm_name}")

                disk = os.path.join(VM_DIR, f"{vm_name}.qcow2")
                seed = os.path.join(CLOUD_INIT_DIR, f"{vm_name}-seed.iso")
                meta_tmp = f"/tmp/{vm_name}-meta"
                user_tmp = f"/tmp/{vm_name}-user"
                xml_tmp = f"/tmp/{vm_name}.xml"

                try:
                    # Створення дельти диска замість повного копіювання
                    subprocess.run(["qemu-img", "create", "-f", "qcow2", "-F", "qcow2", "-b", TEMPLATES["ubuntu"], disk], check=True, timeout=10)

                    pwd = secrets.token_urlsafe(8)

                    with open(meta_tmp, "w") as f:
                        f.write(f"instance-id: {vm_name}\nlocal-hostname: {vm_name}\n")

                    # Генерація cloud-init конфігу для юзера student
                    cloud_config = f"""#cloud-config
chpasswd:
  list: |
    student:{pwd}
  expire: False
users:
  - name: student
    sudo: ALL=(ALL) NOPASSWD:ALL
    groups: users, admin
    shell: /bin/bash
    lock_passwd: false
ssh_pwauth: true
disable_root: false
"""
                    with open(user_tmp, "w") as f: f.write(cloud_config)
                    subprocess.run(["cloud-localds", seed, user_tmp, meta_tmp], check=True, timeout=10)

                    with open("templates/domain.xml.j2", "r") as f:
                        xml = Template(f.read()).render(vm_name=vm_name, ram_kb=2048*1024, vcpus=2, disk_path=disk, seed_iso=seed)
                    with open(xml_tmp, "w") as f: f.write(xml)

                    subprocess.run(["sudo", "virsh", "define", xml_tmp], check=True, timeout=10)
                    subprocess.run(["sudo", "virsh", "start", vm_name], check=True, timeout=15)

                    port = None
                    # Чекаємо поки підніметься VNC сервер
                    for _ in range(20):
                        try:
                            out = subprocess.check_output(["sudo", "virsh", "vncdisplay", vm_name]).decode().strip()
                            if out: port = 5900 + int(out.split(":")[-1]); break
                        except: pass
                        time.sleep(1)

                    if port:
                        cur.execute("UPDATE vms SET status = 'ready', vnc_port = ?, password = ? WHERE id = ?", (port, pwd, vm_id))
                        update_tokens(cur)
                        print(f"[Worker] Success. {vm_name} is running on VNC port {port}")
                    else: raise Exception("VNC Timeout")

                except Exception as e:
                    print(f"[Worker] Deployment failed: {e}")
                    # Відкат змін у разі помилки
                    subprocess.run(["sudo", "virsh", "destroy", vm_name], stderr=subprocess.DEVNULL)
                    subprocess.run(["sudo", "virsh", "undefine", vm_name], stderr=subprocess.DEVNULL)
                    try: os.remove(disk)
                    except: pass
                    try: os.remove(seed)
                    except: pass
                    cur.execute("UPDATE vms SET status = 'error' WHERE id = ?", (vm_id,))

                finally:
                    # Прибирання тимчасових файлів
                    for f in [meta_tmp, user_tmp, xml_tmp]:
                        try: os.remove(f)
                        except: pass
                    conn.commit()
            else:
                time.sleep(2)

        except Exception as e: print(f"[Worker] DB Error: {e}")
        finally:
            if 'conn' in locals(): conn.close()

if __name__ == "__main__": process_queue()
