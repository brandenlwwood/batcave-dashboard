#!/bin/bash
# Alfred's Batcave Command Center - Startup Script

set -e

DASHBOARD_DIR="/home/wood/.openclaw/workspace/batcave-dashboard"
cd "$DASHBOARD_DIR"

echo "🦇 ALFRED'S BATCAVE COMMAND CENTER"
echo "=================================="
echo ""

# Check if port is available
PORT=${1:-8080}
if ss -tuln 2>/dev/null | grep -q ":$PORT " || netstat -tuln 2>/dev/null | grep -q ":$PORT "; then
    echo "❌ Port $PORT is already in use."
    echo "💡 Try: ./start-batcave.sh 8081"
    exit 1
fi

echo "🔧 Initializing Batcave systems..."
echo "📍 Dashboard: $DASHBOARD_DIR"
echo "🌐 Local URL: http://localhost:$PORT"
echo "🌐 Tailscale URL: http://100.122.252.21:$PORT"
echo ""
echo "🎭 Welcome back, Master Bruce..."
echo "🦇 All systems coming online..."
echo ""
echo "📝 Use Ctrl+C to shutdown"
echo "=================================="
echo ""

# Start the server
python3 server.py $PORT