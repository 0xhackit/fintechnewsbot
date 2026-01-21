#!/bin/bash
# Quick start script for local development

echo "🚀 Starting Fintech News Terminal..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.12+"
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 18+"
    exit 1
fi

# Start backend in background
echo "📦 Starting FastAPI backend on port 8000..."
cd "$(dirname "$0")"
python3 -m pip install -q -r api/requirements.txt
python3 api/main.py &
BACKEND_PID=$!
echo "✅ Backend started (PID: $BACKEND_PID)"

# Wait for backend to be ready
echo "⏳ Waiting for backend to be ready..."
sleep 3

# Start frontend
echo "📦 Starting React frontend on port 3000..."
cd frontend
if [ ! -d "node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    npm install
fi

echo "✅ Starting frontend development server..."
npm run dev &
FRONTEND_PID=$!

echo ""
echo "🎉 Fintech News Terminal is running!"
echo ""
echo "📊 Backend API: http://localhost:8000"
echo "🖥️  Frontend:    http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both servers"

# Trap Ctrl+C and cleanup
trap "echo '\n🛑 Stopping servers...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT

# Wait for processes
wait
