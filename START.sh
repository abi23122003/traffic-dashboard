#!/bin/bash
# ========================================
#  Traffic Dashboard - One-Click Start
#  Just run: ./START.sh
# ========================================

# Change to script directory
cd "$(dirname "$0")"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo ""
echo -e "${CYAN}========================================"
echo "  Traffic Dashboard - Auto Starting"
echo "========================================${NC}"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERROR] Python 3 not found!${NC}"
    echo "Please install Python 3.11+"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}✅ Python $PYTHON_VERSION found${NC}"
echo ""
echo "Please wait while everything is set up..."
echo ""

# Run the FastAPI app directly via Uvicorn
python3 -m uvicorn main:app --host 127.0.0.1 --port 8000

# Check exit code
if [ $? -ne 0 ]; then
    echo ""
    echo -e "${RED}[ERROR] Startup failed. Check the messages above.${NC}"
    read -p "Press Enter to exit..."
fi

