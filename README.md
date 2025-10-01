# FFmpeg HLS Live Timer Stream

A Docker containerized Flask server that streams a live video in HLS (HTTP Live Streaming) format showing a timer counting up from when the server started, with a moving square background animation.

## Features

- ⏱️ Live streaming timer that counts up from server start time
- 🎬 Moving square background animation with circular motion
- 🌐 Web interface for live stream control and viewing
- 🐳 Docker containerized for easy deployment
- 📱 Responsive web design with HLS.js support
- ⚡ Real-time HLS streaming using FFmpeg
- 🎯 Low-latency streaming optimized for live viewing
- 📺 Cross-platform compatibility (works on all modern browsers)
- 🔄 Adaptive bitrate streaming with HLS segments

## Quick Start

### Local Development

1. **Build and run with Docker Compose:**
   ```bash
   docker-compose up --build
   ```

2. **Or build and run manually:**
   ```bash
   # Build the Docker image
   docker build -t ffmpeg-streamer .
   
   # Run the container
   docker run -p 5000:5000 ffmpeg-streamer
   ```

3. **Access the application:**
   - Open your browser and go to `http://localhost:5000`
   - The HLS live stream will automatically start showing a timer
   - Watch the live timer counting up from when the server started
   - The stream uses HLS format for better compatibility and performance

### Public Deployment

#### Option 1: Using a Cloud Provider (Recommended)

**For AWS, Google Cloud, or Azure:**

1. Push your image to a container registry:
   ```bash
   # Tag your image
   docker tag ffmpeg-streamer your-registry/ffmpeg-streamer:latest
   
   # Push to registry
   docker push your-registry/ffmpeg-streamer:latest
   ```

2. Deploy using your cloud provider's container service:
   - **AWS ECS/Fargate**: Create a task definition and service
   - **Google Cloud Run**: Deploy directly from container registry
   - **Azure Container Instances**: Deploy from container registry

#### Option 2: Using a VPS with Docker

1. **Set up a VPS** (DigitalOcean, Linode, etc.)
2. **Install Docker and Docker Compose** on your VPS
3. **Clone this repository** on your VPS
4. **Run the application:**
   ```bash
   docker-compose up -d
   ```
5. **Configure your firewall** to allow port 5000
6. **Set up a reverse proxy** (nginx) for HTTPS and domain name

#### Option 3: Using Railway, Render, or Heroku

These platforms support Docker deployments:

1. **Railway:**
   - Connect your GitHub repository
   - Railway will automatically detect the Dockerfile
   - Deploy with one click

2. **Render:**
   - Create a new Web Service
   - Connect your repository
   - Set build command: `docker build -t ffmpeg-streamer .`
   - Set start command: `docker run -p $PORT:5000 ffmpeg-streamer`

## API Endpoints

- `GET /` - Main web interface with HLS live stream controls
- `POST /start_stream` - Start the HLS live timer stream
- `POST /stop_stream` - Stop the HLS live timer stream
- `GET /playlist.m3u8` - HLS playlist file (use this URL for external players)
- `GET /<filename>` - HLS segments and other files
- `GET /stream_info` - Get stream URL and usage instructions
- `GET /health` - Health check endpoint with HLS stream status

## External Player Usage

The stream can be used in external applications like VLC, OBS, or command-line tools:

### Stream URL
Once the stream is started, you can access it at:
```
http://YOUR_SERVER_IP:5000/playlist.m3u8
```

### VLC Media Player
1. Open VLC → Media → Open Network Stream
2. Enter the stream URL above
3. Click Play

### OBS Studio
1. Add Source → Media Source
2. Check "Local File" and enter the stream URL
3. The stream will appear as a source

### Command Line
```bash
# Using ffplay
ffplay http://YOUR_SERVER_IP:5000/playlist.m3u8

# Using ffmpeg
ffmpeg -i http://YOUR_SERVER_IP:5000/playlist.m3u8 -f sdl2 output
```

### Browser
Open the stream URL directly in your browser for a simple player view.

## Configuration

The application runs on port 5000 by default. To change this:

1. Modify the `EXPOSE` directive in the Dockerfile
2. Update the port mapping in docker-compose.yml
3. Change the port in the `app.run()` call in app.py

## Stream Specifications

- **Type**: HLS (HTTP Live Streaming) - continuous
- **Resolution**: 640x480
- **Frame Rate**: 30 FPS
- **Format**: H.264 video in MPEG-TS segments
- **Segment Duration**: 2 seconds per segment
- **Playlist Size**: 5 segments (10 seconds buffer)
- **Animation**: Square moving in a circular pattern with timer overlay
- **Timer**: Shows server uptime in HH:MM:SS format
- **Latency**: Optimized for real-time viewing with HLS
- **Compatibility**: Works on all modern browsers via HLS.js

## Requirements

- Docker and Docker Compose
- FFmpeg (included in the Docker image)
- Python 3.11+ (included in the Docker image)

## Troubleshooting

### Common Issues

1. **FFmpeg not found**: The Docker image includes FFmpeg, but if you're running locally, install FFmpeg on your system.

2. **Port already in use**: Change the port mapping in docker-compose.yml or stop the service using that port.

3. **Video generation fails**: Check the Docker logs:
   ```bash
   docker-compose logs ffmpeg-streamer
   ```

4. **Health check fails**: The health check uses curl, which is included in the base image. If it fails, check if the Flask app is running properly.

### Viewing Logs

```bash
# View logs
docker-compose logs -f ffmpeg-streamer

# View logs for specific service
docker logs <container_id>
```

## Security Notes

- The application runs as a non-root user inside the container
- No sensitive data is stored or logged
- Consider adding authentication if deploying publicly
- Use HTTPS in production (configure reverse proxy)

## License

This project is open source and available under the MIT License.
