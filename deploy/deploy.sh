#!/bin/bash
# 展厅智控系统部署脚本
# 目标服务器：36.134.146.69
# 用法：bash deploy.sh [backend|frontend|all]

set -e

SERVER="root@36.134.146.69"
BACKEND_REMOTE="/root/showroom/backend"
FRONTEND_REMOTE="/var/www/showroom"
LOCAL_BACKEND="$(dirname "$0")/../backend"
LOCAL_FRONTEND="$(dirname "$0")/../frontend"

deploy_backend() {
  echo "==> 同步后端代码..."
  rsync -avz --exclude '__pycache__' --exclude '*.pyc' --exclude '.env' \
    "$LOCAL_BACKEND/" "$SERVER:$BACKEND_REMOTE/"

  echo "==> 安装依赖..."
  ssh "$SERVER" "cd $BACKEND_REMOTE && pip3 install -r requirements.txt -q"

  echo "==> 重启服务..."
  ssh "$SERVER" "systemctl restart showroom.service && sleep 2 && systemctl status showroom.service --no-pager | head -10"
}

deploy_frontend() {
  echo "==> 构建前端..."
  cd "$LOCAL_FRONTEND"
  export NVM_DIR="$HOME/.nvm"
  [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
  npm install --silent
  npm run build

  echo "==> 同步前端..."
  rsync -avz dist/ "$SERVER:$FRONTEND_REMOTE/"
  ssh "$SERVER" "nginx -s reload"
}

case "${1:-all}" in
  backend) deploy_backend ;;
  frontend) deploy_frontend ;;
  all) deploy_backend && deploy_frontend ;;
  *) echo "用法: $0 [backend|frontend|all]"; exit 1 ;;
esac

echo "==> 部署完成！"
