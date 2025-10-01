# Use Node.js 18 alpine image as base
FROM node:18-alpine

# Install system dependencies including FFmpeg and build tools for canvas
RUN apk add --no-cache \
    ffmpeg \
    fontconfig \
    ttf-dejavu \
    curl \
    python3 \
    make \
    g++ \
    cairo-dev \
    jpeg-dev \
    pango-dev \
    musl-dev \
    giflib-dev \
    pixman-dev \
    pangomm-dev \
    libjpeg-turbo-dev \
    freetype-dev \
    && rm -rf /var/cache/apk/*

# Set working directory
WORKDIR /app

# Copy package files first for better Docker layer caching
COPY package.json .

# Install Node.js dependencies
RUN npm install --production

# Copy application code
COPY server.js .

# Create HLS output directory
RUN mkdir -p /app/hls

# Create a non-root user for security
RUN adduser -D -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port 5000
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Run the application
CMD ["node", "server.js"]
