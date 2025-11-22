# Railway Configuration Notes

## ⚠️ Critical: PostgreSQL Version Configuration

### Database Version Requirement

**IMPORTANT**: Ensure Railway PostgreSQL Docker Image is pinned to **version 16** to avoid incompatible data errors.

### Why This Matters

PostgreSQL major version changes (e.g., 14 → 15 → 16) can cause:
- Data incompatibility errors
- Migration failures
- Service crashes during database restarts
- Connection pool initialization failures

### How to Configure on Railway

1. **Check Current Database Version**:
   - Open Railway dashboard
   - Navigate to your PostgreSQL service
   - Check the "Image" or "Version" setting

2. **Pin to PostgreSQL 16**:
   ```dockerfile
   # In Railway PostgreSQL settings, ensure:
   Image: postgres:16
   # or
   Image: postgres:16-alpine
   ```

3. **Avoid Auto-Upgrades**:
   - Do NOT use `postgres:latest` (can auto-upgrade to incompatible versions)
   - Use specific version tags: `postgres:16`, `postgres:16.1`, etc.

### Connection Resilience

The application now includes **automatic retry logic** for database connections:
- **5 retry attempts** with 5-second delays
- Handles temporary Railway database restarts/upgrades gracefully
- Prevents crash loops during infrastructure maintenance

### Environment Variables Checklist

Ensure these are set in Railway:

```bash
# Required
DATABASE_URL=postgresql://user:pass@host:port/db?sslmode=require
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret

# Optional Performance
REDIS_URL=redis://host:port  # For 30-60x query speedup

# Optional Notifications
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
TELEGRAM_BOT_TOKEN=bot_token
TELEGRAM_CHAT_ID=chat_id
```

### SSL Configuration

The application **automatically detects** SSL requirements:
- Railway internal connections: SSL disabled (`railway.internal`)
- Railway public connections: SSL required (`railway.app`)
- Neon connections: SSL required

No manual SSL configuration needed!

### Monitoring Database Health

Watch for these log messages:

✅ **Healthy**:
```
✅ PostgreSQL异步连接池初始化成功
```

⚠️ **Retrying** (temporary):
```
⚠️ DB连接失败，5秒后重试... (尝试 1/5)
```

❌ **Failed** (action required):
```
❌ 连接池初始化失败（已重试5次）
```

If connection fails after 5 retries:
1. Check DATABASE_URL is correct
2. Verify PostgreSQL service is running on Railway
3. Check PostgreSQL version compatibility (should be v16)
4. Verify network connectivity

### Performance Optimizations Applied

The application includes several Railway-optimized features:

1. **Database Connection Pooling**:
   - Min connections: 2
   - Max connections: 10
   - Timeout: 30 seconds

2. **WebSocket Stability**:
   - Ping interval: 25 seconds (optimized for Railway network)
   - Ping timeout: 60 seconds (tolerates latency)
   - Auto-reconnect with exponential backoff

3. **Redis Caching** (optional):
   - 30-60x faster queries for trade counts/statistics
   - 5-second TTL for fresh data
   - Graceful fallback to PostgreSQL if unavailable

### Troubleshooting

**Issue**: Database crashes on startup
- **Solution**: Check PostgreSQL version is pinned to 16

**Issue**: `TimeoutError` during initialization
- **Solution**: System will auto-retry 5 times - check logs for success

**Issue**: `Connection reset by peer` in WebSocket
- **Solution**: Already optimized with 60s ping_timeout - should recover automatically

**Issue**: High query latency
- **Solution**: Add Redis addon and set REDIS_URL for 30-60x speedup

---

**Last Updated**: 2025-11-20  
**Application Version**: v4.0+  
**PostgreSQL Version**: 16 (recommended)
