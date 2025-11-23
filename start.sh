#!/bin/bash
#================================================================================
# A.E.G.I.S. v8.0 - Startup Script for Railway/Docker
#================================================================================
# Hardened entry point with pure Python multiprocessing (no supervisord)
# Features:
# - Signal handling (SIGTERM, SIGINT)
# - Auto-restart on process failure
# - Graceful shutdown
# - Keep-alive watchdog loop
#================================================================================

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 A.E.G.I.S. v8.0 - Hardened Startup Sequence"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Step 1: Clean shared memory (fresh start for each container)
echo "🧹 Step 1: Cleaning shared memory..."
rm -rf /dev/shm/* 2>/dev/null || true
echo "✅ Shared memory cleaned"

# Step 2: Start Python multiprocessing application directly
echo ""
echo "🔄 Step 2: Starting A.E.G.I.S. with hardened multiprocessing..."
echo "   Note: System will initialize database + ring buffer automatically"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Execute Python application in the foreground (replace this process)
# This ensures container lifetime matches application lifetime
exec python -m src.main

#================================================================================
# Notes:
# - exec: Replaces the shell process with Python
# - python -m src.main: Runs hardened multiprocessing application
# - Uses pure Python process management (no supervisord needed)
# - Signal handling: SIGTERM/SIGINT for graceful shutdown
# - Auto-restart: Container restart triggers complete reinitialization
#================================================================================
