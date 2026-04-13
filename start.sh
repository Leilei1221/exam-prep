#!/bin/bash
cd "$(dirname "$0")"

# Create venv if not exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

# Install dependencies
pip install -r requirements.txt -q

echo "Starting 健護甄試複習 App on port 5011..."

# Start Flask in background
python app.py &
FLASK_PID=$!
echo "Flask PID: $FLASK_PID"

# Wait for Flask to start
sleep 2

# Start Cloudflare Tunnel
echo "Starting Cloudflare Tunnel..."
cloudflared tunnel --url http://127.0.0.1:5011 --protocol http2 &
CF_PID=$!
echo "Cloudflare PID: $CF_PID"

echo ""
echo "==================================="
echo "  健護教師甄試複習 App"
echo "  Local:  http://127.0.0.1:5011"
echo "  Public: (see Cloudflare URL above)"
echo "==================================="
echo ""

# Trap to kill both processes
trap "kill $FLASK_PID $CF_PID 2>/dev/null; exit" SIGINT SIGTERM

wait
