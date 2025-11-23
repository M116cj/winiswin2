#!/bin/bash
#================================================================================
# A.E.G.I.S. v8.0 - Startup Script for Railway/Docker
#================================================================================
# This script:
# 1. Cleans shared memory (fresh start)
# 2. Starts supervisord to manage Feed/Brain/Orchestrator processes
#
# NOTE: Database initialization and ring buffer creation are handled by
#       the Orchestrator process to ensure shared memory persistence.
#================================================================================

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 A.E.G.I.S. v8.0 - Startup Sequence"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Step 1: Clean shared memory (fresh start for each container)
echo "🧹 Step 1: Cleaning shared memory..."
rm -rf /dev/shm/* 2>/dev/null || true
echo "✅ Shared memory cleaned"

# Step 2: Start supervisord to manage all processes
echo ""
echo "🔄 Step 2: Starting supervisord process manager..."
echo "   Note: Orchestrator will initialize database + ring buffer on startup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Execute supervisord in the foreground (replace this process)
# This ensures container doesn't exit when supervisord is running
exec supervisord -c supervisord.conf

#================================================================================
# Notes:
# - exec: Replaces the shell process with supervisord
# - supervisord -c: Uses supervisord.conf in root directory
# - nodaemon=true in supervisord.conf keeps it in foreground
# - Logs are redirected to stdout for Railway/Docker visibility
#================================================================================
