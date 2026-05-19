#!/bin/bash
# Link frontend to existing Django backend
# This script is meant to be called from the Django project
# Usage: ./frontend/scripts/link-backend.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}🔗 Linking frontend to Django backend${NC}"
echo ""

# Check if we can find a Django manage.py in parent directories
find_django_root() {
    local dir="$1"
    while [ "$dir" != "/" ]; do
        if [ -f "$dir/manage.py" ]; then
            echo "$dir"
            return 0
        fi
        dir=$(dirname "$dir")
    done
    return 1
}

DJANGO_ROOT=$(find_django_root "$(dirname "$FRONTEND_DIR")")

if [ -n "$DJANGO_ROOT" ]; then
    echo -e "${GREEN}✅ Found Django project at: $DJANGO_ROOT${NC}"
else
    echo -e "${YELLOW}⚠️  Django project not found in parent directories${NC}"
    echo "   Make sure the frontend is inside or adjacent to the Django project"
fi

# Setup the frontend
cd "$FRONTEND_DIR"
echo -e "${BLUE}📁 Setting up frontend at: $FRONTEND_DIR${NC}"

# Run the monorepo setup
./scripts/setup-monorepo.sh --backend-path "${DJANGO_ROOT:-.}"

echo ""
echo -e "${GREEN}✅ Frontend linked to backend!${NC}"
echo ""
echo -e "${BLUE}Quick start:${NC}"
echo "  1. Start Django: cd $DJANGO_ROOT && make up"
echo "  2. Start React:  cd $FRONTEND_DIR && make dev-monorepo"
