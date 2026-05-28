#!/bin/bash
SERVER_URL="http://127.0.0.1:5000/upload"
# Якщо API_KEY не задано в оточенні, використовуємо дефолтний
KEY=${API_KEY:-"super_secret_sysinfo_key"}

echo "📡 Радар запущено."
while true; do
    read -r cpu u n s idle iow irq soft steal guest < /proc/stat
    PREV_TOTAL=$((u + n + s + idle + iow + irq + soft + steal)); PREV_IDLE=$idle
    sleep 1
    read -r cpu u n s idle iow irq soft steal guest < /proc/stat
    TOTAL=$((u + n + s + idle + iow + irq + soft + steal)); IDLE=$idle
    DIFF_TOTAL=$((TOTAL - PREV_TOTAL)); DIFF_IDLE=$((IDLE - PREV_IDLE))
    [ "$DIFF_TOTAL" -gt 0 ] && CPU_LOAD=$((100 * (DIFF_TOTAL - DIFF_IDLE) / DIFF_TOTAL)) || CPU_LOAD=0

    RAM=$(free -m | awk '/^Mem:/ {print $3" MB / "$2" MB"}')
    SSD=$(df -h / | awk 'NR==2 {print $3" / "$2}')

    JSON=$(jq -n --arg sys_name "$(hostname)" --arg cores "$CPU_LOAD% / $(nproc)c" --arg ram "$RAM" --arg ssd "$SSD" '{sys_name: $sys_name, cores: $cores, ram: $ram, ssd: $ssd}')
    
    # ЄДИНЕ правильне відправлення
    curl -s --max-time 5 -X POST -H "Content-Type: application/json" -H "X-API-Key: $KEY" -d "$JSON" "$SERVER_URL" > /dev/null
    
    sleep 5
done

