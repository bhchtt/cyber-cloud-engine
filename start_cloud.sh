#!/bin/bash

echo "Stopping old processes..."
sudo pkill -f "python app.py"
sudo pkill -f "python worker.py"
sudo pkill -f "python gc_worker.py"
sudo pkill -f "sysinfo.sh"
sudo pkill -f "websockify"
sleep 2

echo "Preparing environment..."
mkdir -p logs
sudo mkdir -p /run/cyber_cloud
sudo touch /run/cyber_cloud/vnc_tokens.txt

echo "Starting Cyber Cloud Engine..."

# Запуск процесів у фоні
nohup sudo python app.py > logs/app.log 2>&1 &
echo "[OK] Web server (app.py)"

nohup sudo python worker.py > logs/worker.log 2>&1 &
echo "[OK] VM Orchestrator (worker.py)"

nohup sudo ./sysinfo.sh > logs/sysinfo.log 2>&1 &
echo "[OK] Resource Monitor (sysinfo.sh)"

nohup sudo websockify --web /usr/share/novnc/ --token-plugin TokenFile --token-source /run/cyber_cloud/vnc_tokens.txt 6080 > logs/vnc.log 2>&1 &
echo "[OK] VNC Proxy (websockify)"

# nohup sudo python gc_worker.py > logs/gc.log 2>&1 &
# echo "[OK] Garbage Collector (gc_worker.py)"

echo "All services are running in background."
echo "To check logs run: tail -f logs/app.log"
