cd ~/apps/service_marketplace

cat > restart_prod.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

cd ~/apps/service_marketplace
source ~/.bashrc

# Kill anything listening on 127.0.0.1:8001 (only your user processes)
PIDS=$(ss -ltnp 2>/dev/null | awk '/127\.0\.0\.1:8001/ {print $NF}' | sed -E 's/.*pid=([0-9]+).*/\1/' | sort -u)
if [ -n "${PIDS:-}" ]; then
  echo "Stopping existing listeners on 8001: $PIDS"
  kill $PIDS || true
  sleep 1
fi

# If anything still holds it, force kill
PIDS2=$(ss -ltnp 2>/dev/null | awk '/127\.0\.0\.1:8001/ {print $NF}' | sed -E 's/.*pid=([0-9]+).*/\1/' | sort -u)
if [ -n "${PIDS2:-}" ]; then
  echo "Force stopping: $PIDS2"
  kill -9 $PIDS2 || true
  sleep 1
fi

echo "Starting production server in tmux: service_marketplace"
tmux has-session -t service_marketplace 2>/dev/null || tmux new -d -s service_marketplace
tmux send-keys -t service_marketplace C-c "cd ~/apps/service_marketplace && ./run_prod.sh" Enter

echo "Done. Attach with: tmux attach -t service_marketplace"
EOF

chmod +x restart_prod.sh