# Deployment Options

This project provides multiple Dockerfile options for different deployment scenarios:

## 🚀 **Recommended: Minimal Version (Dockerfile.minimal)**

**Best for:** VPS with limited disk space, Dokploy deployments

- **Base Image:** Python 3.11 Alpine (very small)
- **Dependencies:** Only FFmpeg and curl
- **Size:** ~50-100MB total
- **Features:** All core functionality, basic text rendering
- **Use:** `docker-compose.yml` (default)

## 🎨 **Standard Version (Dockerfile)**

**Best for:** Full-featured deployment with custom fonts

- **Base Image:** Python 3.11 Alpine
- **Dependencies:** FFmpeg, fonts, curl
- **Size:** ~150-200MB total
- **Features:** Custom fonts for better text rendering
- **Use:** Change dockerfile in `docker-compose.yml` to `Dockerfile`

## ⚡ **Lightweight Version (Dockerfile.lightweight)**

**Best for:** Maximum compatibility with pre-built FFmpeg

- **Base Image:** Pre-built FFmpeg Alpine image
- **Dependencies:** Python added to FFmpeg image
- **Size:** ~200-300MB total
- **Features:** Full FFmpeg capabilities
- **Use:** Change dockerfile in `docker-compose.yml` to `Dockerfile.lightweight`

## 📊 **Size Comparison**

| Version | Base Image | Dependencies | Approx Size | Disk Space Needed |
|---------|------------|--------------|-------------|-------------------|
| Minimal | python:3.11-alpine | ffmpeg, curl | ~50-100MB | ~200MB |
| Standard | python:3.11-alpine | ffmpeg, fonts, curl | ~150-200MB | ~400MB |
| Lightweight | jrottenberg/ffmpeg:4.4-alpine | python, pip | ~200-300MB | ~500MB |

## 🔧 **For Dokploy Deployment**

If you're getting "not enough free space" errors:

1. **Use the minimal version** (already configured in docker-compose.yml)
2. **Or try the lightweight version** if you need more FFmpeg features

To switch versions, edit `docker-compose.yml`:
```yaml
services:
  ffmpeg-streamer:
    build:
      context: .
      dockerfile: Dockerfile.minimal  # Change this line
```

## 🐳 **Docker Commands**

```bash
# Build minimal version
docker build -f Dockerfile.minimal -t ffmpeg-streamer-minimal .

# Build standard version
docker build -f Dockerfile -t ffmpeg-streamer-standard .

# Build lightweight version
docker build -f Dockerfile.lightweight -t ffmpeg-streamer-lightweight .

# Run any version
docker run -p 5000:5000 ffmpeg-streamer-minimal
```

## ⚠️ **Troubleshooting**

### "Not enough free space" error
- Use `Dockerfile.minimal`
- Clean up Docker images: `docker system prune -a`
- Check VPS disk space: `df -h`

### Font rendering issues
- Use `Dockerfile` or `Dockerfile.lightweight`
- Check font paths in app.py

### FFmpeg not found
- Use `Dockerfile.lightweight` (pre-built FFmpeg)
- Check FFmpeg installation in container

## 🎯 **Recommendation for Dokploy**

Start with `Dockerfile.minimal` - it provides all core functionality with the smallest footprint and should work on most VPS configurations.
