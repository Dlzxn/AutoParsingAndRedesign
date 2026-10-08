#!/usr/bin/env bash
# Деплой на сервер с Ubuntu по SSH (повторный запуск безопасен — обновляет приложение).
#
#   ./deploy/deploy.sh root@1.2.3.4                    # домен по умолчанию: 1-2-3-4.sslip.io
#   ./deploy/deploy.sh root@1.2.3.4 clips.example.com  # свой домен (A-записи @ и www должны указывать на сервер);
#                                                      # можно указать и на работающем сервере — домен сменится,
#                                                      # старый адрес и www будут перенаправлять на новый
#
# Переменные окружения:
#   SSH_KEY      путь к ключу (по умолчанию ~/.ssh/autoparsing_deploy, если существует)
#   ENV_FILE     локальный файл с секретами, загружается на сервер при ПЕРВОМ деплое (по умолчанию deploy/.env.production)
#   ADMIN_EMAIL, ADMIN_PASSWORD   создать/обновить администратора после деплоя
set -euo pipefail

TARGET="${1:?Использование: deploy.sh user@host [домен]}"
HOST="${TARGET#*@}"
DOMAIN_ARG="${2:-}"
DOMAIN="${DOMAIN_ARG:-${HOST//./-}.sslip.io}"
APP_DIR=/opt/autoparsing
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/deploy/.env.production}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/autoparsing_deploy}"
SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 -o ServerAliveInterval=30)
[[ -f "$SSH_KEY" ]] && SSH_OPTS+=(-i "$SSH_KEY")

remote() { ssh "${SSH_OPTS[@]}" "$TARGET" "$@"; }
step() { printf '\n\033[1;35m==> %s\033[0m\n' "$*"; }

step "Сборка архива из git (ветка $(git -C "$ROOT" rev-parse --abbrev-ref HEAD), коммит $(git -C "$ROOT" rev-parse --short HEAD))"
ARCHIVE="$(mktemp -t autoparsing-XXXXXX).tar.gz"
git -C "$ROOT" archive --format=tar.gz -o "$ARCHIVE" HEAD
trap 'rm -f "$ARCHIVE"' EXIT

step "Подготовка сервера (Docker, swap, firewall)"
remote 'bash -s' <<'BOOTSTRAP'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
if ! command -v docker >/dev/null || ! docker compose version >/dev/null 2>&1; then
  apt-get update -q
  apt-get install -y -q docker.io docker-compose-v2 || apt-get install -y -q docker.io docker-compose-plugin
  systemctl enable --now docker
fi
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  sysctl -q vm.swappiness=10 && echo 'vm.swappiness=10' > /etc/sysctl.d/99-swappiness.conf
fi
if command -v ufw >/dev/null; then
  ufw allow 22/tcp >/dev/null; ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null; ufw allow 443/udp >/dev/null
  ss -tln | grep -q ':10050 ' && ufw allow 10050/tcp >/dev/null   # агент мониторинга хостера
  ufw --force enable >/dev/null
fi
mkdir -p /opt/autoparsing
BOOTSTRAP

step "Загрузка кода"
scp "${SSH_OPTS[@]}" -q "$ARCHIVE" "$TARGET:$APP_DIR/release.tar.gz"
remote "set -e; cd $APP_DIR; find . -mindepth 1 -maxdepth 1 ! -name .env ! -name release.tar.gz -exec rm -rf {} +; tar -xzf release.tar.gz; rm release.tar.gz"

if ! remote "test -f $APP_DIR/.env"; then
  step "Первый деплой: создание .env на сервере"
  [[ -f "$ENV_FILE" ]] || { echo "Нет файла $ENV_FILE с ключами площадок (см. .env.example)"; exit 1; }
  scp "${SSH_OPTS[@]}" -q "$ENV_FILE" "$TARGET:$APP_DIR/.env"
  remote "set -e; cd $APP_DIR; chmod 600 .env
    grep -q '^POSTGRES_PASSWORD=.\+' .env || echo \"POSTGRES_PASSWORD=\$(openssl rand -hex 24)\" >> .env
    grep -q '^SITE_DOMAIN=' .env || echo 'SITE_DOMAIN=$DOMAIN' >> .env"
fi

# Домен: при первом деплое или при явной смене. Старый домен и www.<домен> перенаправляют на основной.
remote "bash -s -- '$DOMAIN_ARG'" <<'DOMAIN_SCRIPT'
set -eu
cd /opt/autoparsing
old=$(grep '^SITE_DOMAIN=' .env | cut -d= -f2)
new=${1:-$old}
list="www.$new"
if [ "$old" != "$new" ]; then list="$list $old"; fi
for d in $(grep '^REDIRECT_DOMAINS=' .env | cut -d= -f2- | tr ',' ' '); do
  if [ "$d" != "$new" ] && ! echo " $list " | grep -qF " $d "; then list="$list $d"; fi
done
redirects=$(echo "$list" | sed 's/ /, /g')
sed -i '/^SITE_DOMAIN=/d;/^REDIRECT_DOMAINS=/d' .env
printf 'SITE_DOMAIN=%s\nREDIRECT_DOMAINS=%s\n' "$new" "$redirects" >> .env
echo "Домен: $new (перенаправления: $redirects)"
DOMAIN_SCRIPT

step "Сборка и запуск контейнеров"
remote "cd $APP_DIR && docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build --remove-orphans && docker image prune -f >/dev/null"

step "Проверка работоспособности"
remote "for i in \$(seq 1 60); do docker compose -f $APP_DIR/docker-compose.yml -f $APP_DIR/deploy/docker-compose.prod.yml exec -T app python -c \"import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).status == 200 else 1)\" 2>/dev/null && exit 0; sleep 3; done; echo 'Приложение не ответило'; exit 1"

if [[ -n "${ADMIN_EMAIL:-}" && -n "${ADMIN_PASSWORD:-}" ]]; then
  step "Администратор $ADMIN_EMAIL"
  remote "cd $APP_DIR && docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml exec -T app python -m app.cli create-admin '$ADMIN_EMAIL' '$ADMIN_PASSWORD'"
fi

SITE="$(remote "grep '^SITE_DOMAIN=' $APP_DIR/.env | cut -d= -f2")"
step "Готово: https://$SITE"
