#!/bin/bash

echo "========================================"
echo "ContinuumAI React Dashboard Startup"
echo "========================================"
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 is not installed"
    exit 1
fi

# Check if Node is available
if ! command -v node &> /dev/null; then
    echo "Error: Node.js is not installed"
    exit 1
fi

echo "Starting Flask API Server..."
cd "$(dirname "$0")"

# Start Flask in background
python3 api_server.py &
FLASK_PID=$!
echo "Flask API started on http://localhost:5000 (PID: $FLASK_PID)"

# Wait a moment for Flask to start
sleep 2

echo ""
echo "Starting React Development Server..."
cd frontend-react

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

# Start React dev server
npm run dev &
VITE_PID=$!
echo "React app started on http://localhost:3000 (PID: $VITE_PID)"

echo ""
echo "========================================"
echo "Both servers are running!"
echo "Flask API: http://localhost:5000"
echo "React App: http://localhost:3000"
echo "========================================"
echo ""
echo "Press Ctrl+C to stop both servers"

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down servers..."
    kill $FLASK_PID 2>/dev/null
    kill $VITE_PID 2>/dev/null
    echo "Servers stopped."
    exit 0
}

# Trap Ctrl+C
trap cleanup SIGINT SIGTERM

# Wait for background processes
wait
