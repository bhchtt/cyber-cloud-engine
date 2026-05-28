from flask import Flask, request, render_template_string, redirect, Response
import sqlite3, uuid, re, subprocess, os, secrets

app = Flask(__name__)
import logging
logging.getLogger('werkzeug').setLevel(logging.ERROR)
live_metrics = {"sys_name": "Очікування...", "cores": "N/A", "ram": "N/A", "ram_p": 0, "ssd": "N/A", "ssd_p": 0, "vm_count": 0, "vms": []}

API_KEY = os.getenv("API_KEY", "super_secret_sysinfo_key")
MAX_VMS = 10 

try:
    conn = sqlite3.connect('cloud.db')
    conn.execute("ALTER TABLE vms ADD COLUMN password TEXT")
    conn.commit(); conn.close()
except: pass

def parse_to_mb(v):
    m = re.findall(r'[\d\.]+', str(v))
    if not m: return 0
    val = float(m[0])
    if 'Gi' in v or 'G' in v: val *= 1024
    elif 'Ki' in v or 'K' in v: val /= 1024
    return val

def calc_percent(usage_str):
    try:
        p = str(usage_str).split('/')
        if len(p) == 2 and parse_to_mb(p[1]) > 0: return min(100, int((parse_to_mb(p[0]) / parse_to_mb(p[1])) * 100))
    except: pass
    return 0

html_template = """
<!DOCTYPE html><html><head><title>CYBER Cloud Engine</title>
<style>
body { background: #0a0a0a; color: #00ff00; font-family: 'Courier New', monospace; padding: 20px; margin: 0; }
.card { border: 1px solid #007bff; border-radius: 8px; padding: 15px; margin-bottom: 20px; background: #111; }
.progress-bg { background: #333; height: 10px; border-radius: 3px; margin: 5px 0 15px 0; }
.progress-fill { background: #007bff; height: 100%; }
table { width: 100%; border-collapse: collapse; }
th, td { border: 1px dashed #33ff33; padding: 10px; text-align: left; }
.btn { background: #007bff; color: #fff; padding: 8px 15px; border: none; font-weight: bold; cursor: pointer; border-radius: 4px; }
.btn-console { background: #28a745; color: #000; text-decoration: none; padding: 6px 12px; font-weight: bold; border-radius: 4px; }
.status-pending, .status-creating { color: #ffc107; animation: blink 1s infinite; }
.status-ready { color: #00ff00; }
.pwd-box { background: #000; padding: 2px 5px; border-radius: 3px; color: #fff; border: 1px solid #444; }
@keyframes blink { 50% { opacity: 0.5; } }
</style></head><body>
<h2>CYBER CLOUD ENGINE ☁️ <span style="color:#00ff00; font-size: 14px; animation: blink 2s infinite;">● LIVE</span></h2>

{% if error_msg %}
<div style="background: #dc3545; color: white; padding: 10px; margin-bottom: 20px; border-radius: 5px;">
    ❌ {{ error_msg }}
</div>
{% endif %}

<div class="card">
    <h3 style="margin-top:0; color:#007bff;">HOST METRICS ({{ data.sys_name }})</h3>
    <div>CPU: {{ data.cores }}</div>
    <div>RAM: {{ data.ram }} <div class="progress-bg"><div class="progress-fill" style="width: {{ data.ram_p }}%;"></div></div></div>
    <div>SSD: {{ data.ssd }} <div class="progress-bg"><div class="progress-fill" style="width: {{ data.ssd_p }}%; background: #20c997;"></div></div></div>
</div>

<div class="card">
    <form action="/deploy" method="POST" style="display:flex; gap:10px;">
        <input type="text" name="student_id" placeholder="Прізвище (англ)" required style="background:#000; border:1px solid #007bff; color:#0f0; padding:8px;">
        <button type="submit" class="btn">ДЕПЛОЙ ЛАБОРАТОРІЇ</button>
    </form>
</div>

<div class="card">
    <h3 style="margin-top:0; color:#007bff;">АКТИВНІ ВІРТУАЛЬНІ МАШИНИ</h3>
    <table>
        <tr><th>Студент</th><th>VM Name</th><th>Статус</th><th>Доступ (student)</th><th>Консоль</th><th>Дія</th></tr>
        {% for vm in db_vms %}
        <tr>
            <td>{{ vm.student_id }}</td><td>{{ vm.vm_name }}</td>
            <td class="status-{{ vm.status }}">{{ vm.status | upper }}</td>
            <td>
                {% if vm.password %}Пароль: <span class="pwd-box">{{ vm.password }}</span>{% else %}-{% endif %}
            </td>
            <td>
                {% if vm.status == 'ready' %}
                <a href="http://{{ request.host.split(':')[0] }}:6080/vnc.html?path=?token={{ vm.token }}" target="_blank" class="btn-console">CONNECT</a>
                {% else %} <i>Зачекайте...</i> {% endif %}
            </td>
            <td>
                <form action="/delete/{{ vm.id }}" method="POST" style="margin:0;">
                    <button type="submit" class="btn" style="background:#dc3545; padding:6px 10px; font-size:12px;">ВИДАЛИТИ</button>
                </form>
            </td>
        </tr>
        {% endfor %}
    </table>
</div>
<script>
    setInterval(() => { if (document.activeElement.tagName !== 'INPUT') window.location.reload(); }, 3000);
</script>
</body></html>
"""

@app.route('/')
def index():
    error = request.args.get('error')
    conn = sqlite3.connect('cloud.db'); conn.row_factory = sqlite3.Row
    vms = conn.execute("SELECT * FROM vms WHERE status != 'deleted' ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template_string(html_template, data=live_metrics, db_vms=vms, error_msg=error)

@app.route('/deploy', methods=['POST'])
def deploy():
    raw_student_id = request.form.get('student_id', '').strip().lower()
    student_id = re.sub(r'[^a-zA-Z0-9_-]', '', raw_student_id)[:32]

    if student_id:
        conn = sqlite3.connect('cloud.db')
        conn.execute("BEGIN IMMEDIATE")

        count = conn.execute("SELECT COUNT(*) FROM vms WHERE status != 'deleted'").fetchone()[0]
        if count >= MAX_VMS:
            conn.close()
            return redirect('/?error=Перевищено ліміт віртуальних машин (MAX 10). Видаліть старі.')

        vm_id = str(uuid.uuid4())[:8]
        conn.execute("INSERT INTO vms (id, student_id, vm_name, token) VALUES (?, ?, ?, ?)", (vm_id, student_id, f"lab_{student_id}_{vm_id}", str(uuid.uuid4())))
        conn.commit(); conn.close()
    return redirect('/')

@app.route('/delete/<vm_id>', methods=['POST'])
def delete_vm(vm_id):
    conn = sqlite3.connect('cloud.db')
    cur = conn.cursor()
    vm = cur.execute("SELECT vm_name FROM vms WHERE id = ?", (vm_id,)).fetchone()

    if vm:
        vm_name = vm[0]
        subprocess.run(["sudo", "virsh", "destroy", vm_name], timeout=10, capture_output=True)
        subprocess.run(["sudo", "virsh", "undefine", vm_name], timeout=10, capture_output=True)
        try: os.remove(f"/var/lib/libvirt/images/vms/{vm_name}.qcow2")
        except: pass
        try: os.remove(f"/var/lib/libvirt/images/seeds/{vm_name}-seed.iso")
        except: pass
        cur.execute("DELETE FROM vms WHERE id = ?", (vm_id,))
        conn.commit()

    conn.close()
    return redirect('/')

@app.route('/upload', methods=['POST'])
def upload():
    if not secrets.compare_digest(request.headers.get("X-API-Key", ""), API_KEY):
        return "Forbidden", 403
    global live_metrics
    d = request.get_json(force=True, silent=True)
    if d: live_metrics.update({'sys_name': d.get('sys_name',''), 'cores': d.get('cores',''), 'ram': d.get('ram',''), 'ssd': d.get('ssd',''), 'ram_p': calc_percent(d.get('ram','')), 'ssd_p': calc_percent(d.get('ssd',''))})
    return "OK", 200

if __name__ == '__main__': app.run(host='0.0.0.0', port=5000)
