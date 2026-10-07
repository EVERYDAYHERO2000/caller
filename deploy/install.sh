#!/usr/bin/env bash
# Install / update Caller on a Raspberry Pi as a systemd service.
#   sudo ./deploy/install.sh
set -euo pipefail

APP_DIR=/opt/caller
DATA_DIR=/var/lib/caller
SVC_USER=caller
SRC="$(cd "$(dirname "$0")/.." && pwd)"

[ "$EUID" -eq 0 ] || { echo "Запустите через sudo: sudo $0"; exit 1; }

ARCH="$(uname -m)"
if [ "$ARCH" = "armv7l" ] || [ "$ARCH" = "armv6l" ]; then
  echo "ВНИМАНИЕ: 32-битная ОС ($ARCH). Рекомендуется Raspberry Pi OS Lite 64-bit —"
  echo "для aarch64 есть готовые колёса pydantic-core/aiohttp, на armv7 возможна долгая сборка."
fi

echo "==> Пакеты"
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip rsync openssl

echo "==> Пользователь $SVC_USER"
id "$SVC_USER" >/dev/null 2>&1 || useradd --system --home-dir "$DATA_DIR" --shell /usr/sbin/nologin "$SVC_USER"
usermod -aG dialout,video "$SVC_USER"   # video: vcgencmd (power / throttling) for the «Система» page

echo "==> Код в $APP_DIR"
mkdir -p "$APP_DIR" "$DATA_DIR"
rsync -a --delete --exclude '.venv' --exclude 'data' --exclude '__pycache__' --exclude '.git' "$SRC/" "$APP_DIR/"

echo "==> Python-окружение"
[ -d "$APP_DIR/.venv" ] || python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

chown -R "$SVC_USER:$SVC_USER" "$DATA_DIR"
chown -R root:root "$APP_DIR"

echo "==> Энергосбережение: помощник caller-sys (sudo только для него)"
chmod 755 "$APP_DIR/deploy/caller-sys"
echo "$SVC_USER ALL=(root) NOPASSWD: $APP_DIR/deploy/caller-sys" > /etc/sudoers.d/caller.tmp
chmod 440 /etc/sudoers.d/caller.tmp
if visudo -cf /etc/sudoers.d/caller.tmp >/dev/null; then mv /etc/sudoers.d/caller.tmp /etc/sudoers.d/caller
else rm -f /etc/sudoers.d/caller.tmp; echo "ВНИМАНИЕ: правило sudo не прошло проверку, энергосбережение из интерфейса недоступно"; fi

echo "==> udev-правила SIM7600"
install -m 644 "$APP_DIR/deploy/99-sim7600.rules" /etc/udev/rules.d/99-sim7600.rules
udevadm control --reload-rules && udevadm trigger || true

echo "==> Отключаем ModemManager (он захватывает порты модема)"
systemctl disable --now ModemManager 2>/dev/null || true

echo "==> Сервис"
[ -f /etc/default/caller ] || install -m 644 "$APP_DIR/deploy/caller.env" /etc/default/caller
install -m 644 "$APP_DIR/deploy/caller.service" /etc/systemd/system/caller.service
systemctl daemon-reload
systemctl enable caller
systemctl restart caller

PORT="$(grep -E '^CALLER_PORT=' /etc/default/caller | cut -d= -f2)"
IP="$(hostname -I | awk '{print $1}')"
echo
echo "Готово. Интерфейс: http://${IP}:${PORT:-8080}   API: http://${IP}:${PORT:-8080}/docs"
echo "Звонки через микрофон браузера: https://${IP}:8443 (самоподписанный сертификат)"
echo "Логи: journalctl -u caller -f"
