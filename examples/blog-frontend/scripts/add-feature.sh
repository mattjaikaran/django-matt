#!/bin/bash
# Add optional features to the boilerplate
# Usage: ./scripts/add-feature.sh <feature>
#
# Available features:
#   ssr     - Server-Side Rendering with Express
#   rsc     - React Server Components utilities
#   all     - All optional features

set -e

show_help() {
    echo "Usage: ./scripts/add-feature.sh <feature>"
    echo ""
    echo "Available features:"
    echo "  ssr     Server-Side Rendering with Express"
    echo "  rsc     React Server Components utilities"
    echo "  all     All optional features"
    echo ""
    echo "Examples:"
    echo "  ./scripts/add-feature.sh ssr"
    echo "  ./scripts/add-feature.sh all"
}

if [ $# -eq 0 ]; then
    show_help
    exit 1
fi

FEATURE=$1
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case $FEATURE in
    ssr)
        echo "Setting up SSR..."
        bash "$SCRIPT_DIR/setup-ssr.sh"
        ;;
    rsc)
        echo "Setting up RSC..."
        bash "$SCRIPT_DIR/setup-rsc.sh"
        ;;
    all)
        echo "Setting up all features..."
        bash "$SCRIPT_DIR/setup-ssr.sh"
        echo ""
        bash "$SCRIPT_DIR/setup-rsc.sh"
        ;;
    -h|--help|help)
        show_help
        ;;
    *)
        echo "❌ Unknown feature: $FEATURE"
        echo ""
        show_help
        exit 1
        ;;
esac
