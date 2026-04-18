#!/bin/bash
# Socket.IO Real-Time Integration - Quick Start Script
# This script sets up and starts the Traffic Dashboard with Socket.IO

set -e

echo "=========================================="
echo "Traffic Dashboard - Socket.IO Quick Start"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Docker is running
echo "[1/5] Checking Docker..."
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker not found. Please install Docker.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker found${NC}"

# Check if Redis is running
echo ""
echo "[2/5] Checking Redis..."
if docker ps | grep -q "traffic_redis"; then
    echo -e "${GREEN}✓ Redis already running${NC}"
else
    echo -e "${YELLOW}→ Starting Redis...${NC}"
    if docker-compose up -d redis; then
        echo -e "${GREEN}✓ Redis started${NC}"
    else
        echo -e "${RED}✗ Failed to start Redis${NC}"
        exit 1
    fi
fi

# Wait for Redis to be healthy
echo ""
echo "[3/5] Waiting for Redis to be ready..."
for i in {1..30}; do
    if redis-cli ping &> /dev/null || docker exec traffic_redis redis-cli ping &> /dev/null; then
        echo -e "${GREEN}✓ Redis is ready${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}✗ Redis failed to start${NC}"
        exit 1
    fi
    echo -n "."
    sleep 1
done

# Check Python environment
echo ""
echo "[4/5] Checking Python environment..."
if ! command -v python &> /dev/null && ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python not found. Please install Python 3.8+${NC}"
    exit 1
fi

if [ -f "requirements.txt" ]; then
    echo -e "${GREEN}✓ requirements.txt found${NC}"
else
    echo -e "${RED}✗ requirements.txt not found${NC}"
    exit 1
fi

# Check key packages
echo ""
echo "[5/5] Checking dependencies..."
python -c "import socketio; print('✓ python-socketio')" 2>/dev/null || {
    echo -e "${YELLOW}→ Installing packages...${NC}"
    pip install -r requirements.txt > /dev/null
}
python -c "import redis; print('✓ redis')" 2>/dev/null
python -c "import fastapi; print('✓ fastapi')" 2>/dev/null

# Set environment variable
export SOCKETIO_REDIS_URL=redis://localhost:6379/0

echo ""
echo "=========================================="
echo -e "${GREEN}✓ Setup complete!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Set up environment variables:"
echo "   export SOCKETIO_REDIS_URL=redis://localhost:6379/0"
echo "   export SECRET_KEY=your-secret-key"
echo ""
echo "2. Start the application:"
echo "   python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload"
echo ""
echo "3. Open browser and navigate to:"
echo "   http://localhost:8000/police/supervisor"
echo ""
echo "4. Check Socket.IO connection (DevTools Console):"
echo "   console.log(commandCenterSocket.connected)"
echo ""
echo "5. Create an incident to test real-time updates"
echo ""
echo "For more information, see:"
echo "  - SOCKETIO_SETUP.md (detailed guide)"
echo "  - SOCKETIO_QUICK_REFERENCE.md (quick tips)"
echo "  - IMPLEMENTATION_SUMMARY.md (overview)"
echo ""
echo "Need help? Check the troubleshooting section in SOCKETIO_SETUP.md"
