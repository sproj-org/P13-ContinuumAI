#!/bin/bash

echo "🚀 Starting ContinuumAI Dashboard..."
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Function to cleanup background processes
cleanup() {
    echo ""
    echo "🛑 Shutting down servers..."
    kill $FLASK_PID 2>/dev/null
    kill $VITE_PID 2>/dev/null
    exit 0
}

# Trap Ctrl+C and call cleanup
trap cleanup INT TERM

# Start Flask API server
echo -e "${BLUE}[1/2]${NC} Starting Flask API server (port 5000)..."
python3 api_server.py &
FLASK_PID=$!
sleep 2

# Start React dev server
echo -e "${BLUE}[2/2]${NC} Starting React app (port 3000)..."
cd frontend-react
npm run dev &
VITE_PID=$!

# Wait a bit for servers to start
sleep 3

echo ""
echo -e "${GREEN}✅ Both servers are running!${NC}"
echo ""
echo "📱 React App:    http://localhost:3000"
echo "🔌 Flask API:    http://localhost:5000"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Wait for background processes
wait
