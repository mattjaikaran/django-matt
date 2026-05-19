#!/bin/bash
# Remove optional features from the boilerplate
# Usage: ./scripts/remove-feature.sh <feature>
#
# Available features:
#   ssr     - Server-Side Rendering
#   rsc     - React Server Components utilities
#   all     - All optional features

set -e

show_help() {
    echo "Usage: ./scripts/remove-feature.sh <feature>"
    echo ""
    echo "Available features:"
    echo "  ssr     Server-Side Rendering"
    echo "  rsc     React Server Components utilities"
    echo "  all     All optional features"
    echo ""
    echo "Examples:"
    echo "  ./scripts/remove-feature.sh ssr"
    echo "  ./scripts/remove-feature.sh all"
}

if [ $# -eq 0 ]; then
    show_help
    exit 1
fi

FEATURE=$1
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case $FEATURE in
    ssr)
        echo "Removing SSR..."
        bash "$SCRIPT_DIR/disable-ssr.sh"
        ;;
    rsc)
        echo "Removing RSC..."
        bash "$SCRIPT_DIR/disable-rsc.sh"
        ;;
    all)
        echo "Removing all features..."
        bash "$SCRIPT_DIR/disable-ssr.sh"
        echo ""
        bash "$SCRIPT_DIR/disable-rsc.sh"
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
