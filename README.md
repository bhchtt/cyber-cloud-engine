
# Cyber Cloud Engine

Проста панель управління віртуальними машинами, написана на Flask. Створювалась для автоматизації розгортання ізольованих лабораторних середовищ.

Суть роботи: юзер вводить прізвище -> бекенд миттєво клонує базовий образ qcow2 -> cloud-init задає рандомний пароль -> через noVNC прокидається консоль прямо в браузер.

## Стек
- **Backend:** Python (Flask, SQLite)
- **Віртуалізація:** KVM / libvirt (qemu)
- **Мережа/Доступ:** websockify (VNC over WebSockets)
- **Скрипти:** Bash (для збору системних метрик хоста)

## Основні фічі
- Швидкий деплой машин через Copy-on-Write дельти (використовується базовий template).
- Доступ до термінала віртуалки з браузера без встановлення додаткових VNC-клієнтів.
- Асинхронне створення машин у фоновому воркері, щоб не блокувати веб-інтерфейс.
- Лайв-моніторинг ресурсів хост-машини (CPU, RAM, диск).
- Базовий захист від перевантаження сервера (ліміт на кількість одночасних машин).


### 1. Залежності
Встановлюємо гіпервізор, утиліти для роботи з образами та python-бібліотеки:

sudo apt update

sudo apt install -y git python3 python3-pip python3-venv qemu-kvm libvirt-daemon-system libvirt-clients bridge-utils websockify jq curl cloud-image-utils

pip3 install flask jinja2


### 2. Завантаження проєкту

git clone [https://github.com/bhchtt/cyber-cloud-engine.git](https://github.com/bhchtt/cyber-cloud-engine.git)

cd cyber-cloud-engine


### 3. Конфіг та База даних

Створюємо структуру бази та файл змінних оточення:

cp .env.example .env

# Зайдіть в .env і впишіть свій нормальний API_KEY

python3 init_db.py


### 4. Підготовка базового образу

Створюємо директорії libvirt та викачуємо офіційний cloud-образ Ubuntu:

sudo mkdir -p /var/lib/libvirt/images/templates/

sudo mkdir -p /var/lib/libvirt/images/vms/

sudo mkdir -p /var/lib/libvirt/images/seeds/

sudo wget [https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img](https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img) -O /var/lib/libvirt/images/templates/ubuntu-template.qcow2


### 5. Запуск

Всі компоненти піднімаються одним скриптом у фоні:

chmod +x start_cloud.sh sysinfo.sh

./start_cloud.sh


Веб-інтерфейс буде доступний на порту 5000: `http://IP_сервера:5000`

### 6. Дебаг та логи

Якщо щось падає, перевіряй логи в папці `logs/`:

* `tail -f logs/app.log` — лог веб-сервера
* `tail -f logs/worker.log` — лог створення машин
* `tail -f logs/vnc.log` — лог websockify
