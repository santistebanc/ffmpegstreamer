const express = require('express');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const { createCanvas, loadImage } = require('canvas');

const app = express();
const PORT = process.env.PORT || 5000;

// Global variables for live streaming
const serverStartTime = new Date();
let ffmpegProcess = null;
let streamActive = false;
const hlsOutputDir = "/app/hls";
const playlistFile = path.join(hlsOutputDir, "playlist.m3u8");

// HTML template for the web interface
const HTML_TEMPLATE = `
<!DOCTYPE html>
<html>
<head>
    <title>Live Timer Stream (HLS)</title>
    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f0f0f0; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; text-align: center; }
        .video-container { text-align: center; margin: 20px 0; }
        video { max-width: 100%; border: 2px solid #ddd; border-radius: 5px; }
        .controls { text-align: center; margin: 20px 0; }
        button { background: #007bff; color: white; border: none; padding: 12px 24px; border-radius: 5px; cursor: pointer; font-size: 16px; margin: 0 10px; }
        button:hover { background: #0056b3; }
        button:disabled { background: #6c757d; cursor: not-allowed; }
        .status { text-align: center; margin: 20px 0; color: #666; }
        .info { background: #e9ecef; padding: 15px; border-radius: 5px; margin: 20px 0; }
        .timer-display { font-size: 24px; font-weight: bold; color: #007bff; margin: 20px 0; }
        .hls-info { background: #d4edda; padding: 10px; border-radius: 5px; margin: 10px 0; font-size: 14px; }
        .stream-url { background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #007bff; }
        .stream-url input { width: 100%; padding: 8px; margin: 5px 0; border: 1px solid #ddd; border-radius: 3px; font-family: monospace; }
        .copy-btn { background: #28a745; color: white; border: none; padding: 5px 10px; border-radius: 3px; cursor: pointer; margin-left: 5px; }
        .copy-btn:hover { background: #218838; }
        .instructions { background: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #ffc107; }
        .instructions h4 { margin-top: 0; color: #856404; }
        .instructions code { background: #f8f9fa; padding: 2px 4px; border-radius: 3px; font-family: monospace; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⏱️ Live Timer Stream (HD Quality)</h1>
        <div class="info">
            <p><strong>Live Stream:</strong> This server streams a live HD video showing a timer that counts up from when the server started.</p>
            <p><strong>Features:</strong> Real-time timer display with a moving square background animation in HD quality.</p>
            <div class="hls-info">
                <strong>HLS Streaming:</strong> Using HTTP Live Streaming (HLS) format with HD quality (1280x720) for better compatibility and adaptive bitrate streaming.
            </div>
        </div>
        <div class="status" id="status">Connecting to live stream...</div>
        <div class="timer-display" id="timerDisplay">00:00:00</div>
        
        <div class="controls" style="text-align: center; margin: 20px 0;">
            <button id="restartBtn" onclick="restartStream()" style="background: #dc3545; color: white; border: none; padding: 12px 24px; border-radius: 5px; cursor: pointer; font-size: 16px; margin: 0 10px;">
                🔄 Restart Stream
            </button>
        </div>
        
        <div class="stream-url" id="streamUrlSection" style="display: none;">
            <h3>📡 Stream URL for External Players</h3>
            <p>Use this URL in VLC, OBS, or other streaming applications:</p>
            <input type="text" id="streamUrl" readonly value="Stream not started yet">
            <button class="copy-btn" onclick="copyStreamUrl()">Copy URL</button>
            <div class="instructions">
                <h4>How to use this stream:</h4>
                <p><strong>VLC Media Player:</strong></p>
                <p>1. Open VLC → Media → Open Network Stream</p>
                <p>2. Paste the URL above and click Play</p>
                <p><strong>OBS Studio:</strong></p>
                <p>1. Add Source → Media Source</p>
                <p>2. Check "Local File" and paste the URL</p>
                <p><strong>Command Line (ffplay):</strong></p>
                <p><code>ffplay [URL]</code></p>
                <p><strong>Browser:</strong></p>
                <p>Open the URL directly in your browser</p>
            </div>
        </div>
        
        <div class="video-container" id="videoContainer" style="display: none;">
            <video id="videoPlayer" autoplay muted>
                <source src="/playlist.m3u8" type="video/mp4">
                Your browser does not support the video tag.
            </video>
        </div>
    </div>

    <script>
        let hls;
        let timerInterval;
        
        function connectToStream() {
            document.getElementById('status').textContent = 'Connecting to live stream...';
            
            // Check if stream is already running
            fetch('/health')
                .then(response => response.json())
                .then(data => {
                    if (data.stream_active && data.hls_playlist_exists) {
                        document.getElementById('status').textContent = 'Connected to live stream!';
                        document.getElementById('videoContainer').style.display = 'block';
                        initializeHLS();
                        startTimer();
                        loadStreamInfo();
                    } else {
                        document.getElementById('status').textContent = 'Stream not available. Retrying in 3 seconds...';
                        setTimeout(connectToStream, 3000);
                    }
                })
                .catch(error => {
                    document.getElementById('status').textContent = 'Connection error. Retrying in 3 seconds...';
                    console.error('Connection error:', error);
                    setTimeout(connectToStream, 3000);
                });
        }
        
        function restartStream() {
            const restartBtn = document.getElementById('restartBtn');
            const originalText = restartBtn.textContent;
            
            restartBtn.disabled = true;
            restartBtn.textContent = '🔄 Restarting...';
            document.getElementById('status').textContent = 'Restarting stream...';
            
            // Destroy current HLS instance
            if (hls) {
                hls.destroy();
                hls = null;
            }
            
            fetch('/restart_stream', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('status').textContent = 'Stream restarted! Reconnecting...';
                        // Wait a moment for stream to be ready, then reconnect
                        setTimeout(() => {
                            connectToStream();
                        }, 3000);
                    } else {
                        document.getElementById('status').textContent = 'Error: ' + data.error;
                        restartBtn.disabled = false;
                        restartBtn.textContent = originalText;
                    }
                })
                .catch(error => {
                    document.getElementById('status').textContent = 'Error: ' + error.message;
                    restartBtn.disabled = false;
                    restartBtn.textContent = originalText;
                })
                .finally(() => {
                    // Re-enable button after a delay
                    setTimeout(() => {
                        restartBtn.disabled = false;
                        restartBtn.textContent = originalText;
                    }, 5000);
                });
        }
        
        function loadStreamInfo() {
            fetch('/stream_info')
                .then(response => response.json())
                .then(data => {
                    if (data.stream_active && data.playlist_exists) {
                        document.getElementById('streamUrl').value = data.stream_urls.playlist_url;
                        document.getElementById('streamUrlSection').style.display = 'block';
                    }
                })
                .catch(error => {
                    console.error('Error loading stream info:', error);
                });
        }
        
        function copyStreamUrl() {
            const urlInput = document.getElementById('streamUrl');
            urlInput.select();
            urlInput.setSelectionRange(0, 99999); // For mobile devices
            document.execCommand('copy');
            
            // Show feedback
            const copyBtn = document.querySelector('.copy-btn');
            const originalText = copyBtn.textContent;
            copyBtn.textContent = 'Copied!';
            copyBtn.style.background = '#28a745';
            setTimeout(() => {
                copyBtn.textContent = originalText;
                copyBtn.style.background = '#28a745';
            }, 2000);
        }
        
        function initializeHLS() {
            const video = document.getElementById('videoPlayer');
            const videoSrc = '/playlist.m3u8';
            
            if (Hls.isSupported()) {
                hls = new Hls({
                    debug: false,
                    enableWorker: true,
                    lowLatencyMode: true,
                    backBufferLength: 90
                });
                hls.loadSource(videoSrc);
                hls.attachMedia(video);
                
                hls.on(Hls.Events.MANIFEST_PARSED, function() {
                    console.log('HLS manifest parsed, starting playback');
                    video.play().catch(e => console.log('Autoplay prevented:', e));
                });
                
                hls.on(Hls.Events.ERROR, function(event, data) {
                    console.error('HLS error:', data);
                    if (data.fatal) {
                        switch(data.type) {
                            case Hls.ErrorTypes.NETWORK_ERROR:
                                console.log('Fatal network error, trying to recover...');
                                hls.startLoad();
                                break;
                            case Hls.ErrorTypes.MEDIA_ERROR:
                                console.log('Fatal media error, trying to recover...');
                                hls.recoverMediaError();
                                break;
                            default:
                                console.log('Fatal error, cannot recover');
                                hls.destroy();
                                break;
                        }
                    }
                });
            } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
                // Native HLS support (Safari)
                video.src = videoSrc;
                video.addEventListener('loadedmetadata', function() {
                    video.play().catch(e => console.log('Autoplay prevented:', e));
                });
            } else {
                console.error('HLS is not supported in this browser');
                document.getElementById('status').textContent = 'HLS not supported in this browser';
            }
        }
        
        function startTimer() {
            // Get server uptime from health endpoint
            fetch('/health')
                .then(response => response.json())
                .then(data => {
                    if (data.server_uptime) {
                        // Parse server uptime and start timer from that point
                        const uptimeParts = data.server_uptime.split(':');
                        let totalSeconds = 0;
                        if (uptimeParts.length === 3) {
                            totalSeconds = parseInt(uptimeParts[0]) * 3600 + 
                                         parseInt(uptimeParts[1]) * 60 + 
                                         parseInt(uptimeParts[2]);
                        }
                        
                        timerInterval = setInterval(() => {
                            totalSeconds++;
                            const hours = Math.floor(totalSeconds / 3600);
                            const minutes = Math.floor((totalSeconds % 3600) / 60);
                            const seconds = totalSeconds % 60;
                            
                            const display = 
                                String(hours).padStart(2, '0') + ':' +
                                String(minutes).padStart(2, '0') + ':' +
                                String(seconds).padStart(2, '0');
                            
                            document.getElementById('timerDisplay').textContent = display;
                        }, 1000);
                    }
                })
                .catch(error => {
                    console.error('Error getting server uptime:', error);
                    // Fallback to browser session timer
                    const startTime = new Date().getTime();
                    timerInterval = setInterval(() => {
                        const elapsed = new Date().getTime() - startTime;
                        const seconds = Math.floor(elapsed / 1000);
                        const minutes = Math.floor(seconds / 60);
                        const hours = Math.floor(minutes / 60);
                        
                        const display = 
                            String(hours).padStart(2, '0') + ':' +
                            String(minutes % 60).padStart(2, '0') + ':' +
                            String(seconds % 60).padStart(2, '0');
                        
                        document.getElementById('timerDisplay').textContent = display;
                    }, 1000);
                });
        }
        
        function stopTimer() {
            if (timerInterval) {
                clearInterval(timerInterval);
                timerInterval = null;
            }
        }
        
        // Auto-connect to stream on page load
        window.onload = function() {
            connectToStream();
        };
    </script>
</body>
</html>
`;

// Create a canvas for rendering
const canvas = createCanvas(1280, 720);
const ctx = canvas.getContext('2d');

// Animation variables
let time = 0;
let startTime = Date.now();

// Pick a random color at startup
const colors = [
    'rgba(255, 0, 0, 0.8)',    // Red
    'rgba(0, 255, 0, 0.8)',    // Green
    'rgba(0, 0, 255, 0.8)',    // Blue
    'rgba(255, 255, 0, 0.8)',  // Yellow
    'rgba(255, 0, 255, 0.8)',  // Magenta
    'rgba(0, 255, 255, 0.8)',  // Cyan
    'rgba(255, 165, 0, 0.8)',  // Orange
    'rgba(128, 0, 128, 0.8)',  // Purple
    'rgba(255, 192, 203, 0.8)', // Pink
    'rgba(0, 128, 0, 0.8)'     // Dark Green
];
const randomColor = colors[Math.floor(Math.random() * colors.length)];
console.log('Canvas server started with random color:', randomColor);

// Animation loop
function animate() {
    time += 0.016; // ~60fps
    
    // Clear canvas
    ctx.fillStyle = '#000000';
    ctx.fillRect(0, 0, 1280, 720);
    
    // Draw animated square with random color
    const squareSize = 200;
    const centerX = 100 + 100 * Math.cos(time * 2 * Math.PI / 5);
    const centerY = 100 + 100 * Math.sin(time * 2 * Math.PI / 5);
    
    ctx.fillStyle = randomColor;
    ctx.fillRect(centerX, centerY, squareSize, squareSize);
    
    // Draw text overlays
    ctx.fillStyle = '#FFFFFF';
    ctx.font = '36px Arial';
    ctx.fillText('Server Uptime', 20, 50);
    
    // Update timer text
    const elapsed = (Date.now() - startTime) / 1000;
    const hours = Math.floor(elapsed / 3600);
    const minutes = Math.floor((elapsed % 3600) / 60);
    const seconds = Math.floor(elapsed % 60);
    
    const timerText = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    
    ctx.fillStyle = '#FFFF00';
    ctx.font = '48px Arial';
    ctx.fillText(timerText, 20, 100);
    
    ctx.fillStyle = '#00FFFF';
    ctx.font = '28px Arial';
    ctx.fillText('HLS Live Stream', 20, 160);
    
    ctx.fillStyle = '#00FF00';
    ctx.font = '24px Arial';
    ctx.fillText('HD Quality', 20, 200);
    
    // Get canvas data and send to FFmpeg
    const imageData = canvas.toDataURL('image/png');
    
    // Convert base64 to buffer
    const base64Data = imageData.replace(/^data:image\/png;base64,/, '');
    const buffer = Buffer.from(base64Data, 'base64');
    
    // Send to FFmpeg if process exists
    if (ffmpegProcess && !ffmpegProcess.killed) {
        try {
            ffmpegProcess.stdin.write(buffer);
        } catch (error) {
            if (error.code === 'EPIPE') {
                console.log('FFmpeg process ended, stopping animation...');
                if (animationFrameId) {
                    clearInterval(animationFrameId);
                    animationFrameId = null;
                }
                ffmpegProcess = null;
            } else {
                console.error('Error writing to FFmpeg:', error);
            }
        }
    }
}

let animationFrameId = null;

function startLiveStream() {
    try {
        if (ffmpegProcess && !ffmpegProcess.killed) {
            return true; // Stream already running
        }
        
        // Create HLS output directory
        if (!fs.existsSync(hlsOutputDir)) {
            fs.mkdirSync(hlsOutputDir, { recursive: true });
        }
        
        // Clean up old segments
        const files = fs.readdirSync(hlsOutputDir);
        files.forEach(file => {
            if (file.endsWith('.ts') || file.endsWith('.m3u8')) {
                fs.unlinkSync(path.join(hlsOutputDir, file));
            }
        });
        
        // FFmpeg command for high-quality HLS live streaming with timer
        const ffmpegCmd = [
            'ffmpeg',
            '-f', 'image2pipe',
            '-vcodec', 'png',
            '-r', '30',
            '-i', 'pipe:0',
            '-f', 'lavfi',
            '-i', 'anullsrc=channel_layout=stereo:sample_rate=22050',
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-tune', 'zerolatency',
            '-crf', '20',
            '-maxrate', '2M',
            '-bufsize', '4M',
            '-pix_fmt', 'yuv420p',
            '-s', '1280x720',
            '-c:a', 'aac',
            '-b:a', '64k',
            '-ar', '22050',
            '-ac', '1',
            '-f', 'hls',
            '-hls_time', '4',
            '-hls_list_size', '10',
            '-hls_flags', 'delete_segments+independent_segments',
            '-hls_segment_filename', path.join(hlsOutputDir, 'segment_%03d.ts'),
            playlistFile
        ];
        
        // Start FFmpeg process
        ffmpegProcess = spawn('ffmpeg', ffmpegCmd, {
            stdio: ['pipe', 'pipe', 'pipe']
        });
        
        ffmpegProcess.stderr.on('data', (data) => {
            console.log('FFmpeg stderr:', data.toString());
        });
        
        ffmpegProcess.on('close', (code) => {
            console.log(`FFmpeg process exited with code ${code}`);
            ffmpegProcess = null;
            streamActive = false;
            if (animationFrameId) {
                clearInterval(animationFrameId);
                animationFrameId = null;
            }
        });
        
        ffmpegProcess.on('error', (err) => {
            console.error('FFmpeg process error:', err);
            ffmpegProcess = null;
            streamActive = false;
            if (animationFrameId) {
                clearInterval(animationFrameId);
                animationFrameId = null;
            }
        });
        
        ffmpegProcess.stdin.on('error', (err) => {
            if (err.code !== 'EPIPE') {
                console.error('FFmpeg stdin error:', err);
            }
        });
        
        // Start animation loop immediately to feed data to FFmpeg
        streamActive = true;
        console.log(`FFmpeg started, PID: ${ffmpegProcess.pid}`);
        animationFrameId = setInterval(animate, 1000 / 30); // 30fps
        
        // Check if FFmpeg is still running after a short delay
        setTimeout(() => {
            if (ffmpegProcess && ffmpegProcess.killed) {
                console.error('FFmpeg failed to start or exited early');
                streamActive = false;
                if (animationFrameId) {
                    clearInterval(animationFrameId);
                    animationFrameId = null;
                }
            } else {
                console.log('FFmpeg running successfully');
            }
        }, 2000);
        
        return true;
        
    } catch (error) {
        console.error('Error starting stream:', error);
        return false;
    }
}

function stopLiveStream() {
    try {
        if (ffmpegProcess && !ffmpegProcess.killed) {
            ffmpegProcess.kill('SIGTERM');
            ffmpegProcess = null;
        }
        
        streamActive = false;
        
        if (animationFrameId) {
            clearInterval(animationFrameId);
            animationFrameId = null;
        }
        
        // Clean up HLS files
        if (fs.existsSync(hlsOutputDir)) {
            const files = fs.readdirSync(hlsOutputDir);
            files.forEach(file => {
                if (file.endsWith('.ts') || file.endsWith('.m3u8')) {
                    fs.unlinkSync(path.join(hlsOutputDir, file));
                }
            });
        }
        
        return true;
        
    } catch (error) {
        console.error('Error stopping stream:', error);
        return false;
    }
}

// Routes
app.get('/', (req, res) => {
    res.send(HTML_TEMPLATE);
});

app.post('/restart_stream', (req, res) => {
    try {
        // Stop current stream
        stopLiveStream();
        
        // Wait a moment
        setTimeout(() => {
            // Start new stream
            const success = startLiveStream();
            
            if (success) {
                res.json({
                    success: true,
                    message: 'Stream restarted successfully',
                    timestamp: new Date().toISOString()
                });
            } else {
                res.status(500).json({
                    success: false,
                    error: 'Failed to restart stream',
                    timestamp: new Date().toISOString()
                });
            }
        }, 2000);
        
    } catch (error) {
        res.status(500).json({
            success: false,
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

app.get('/playlist.m3u8', (req, res) => {
    const playlistExists = fs.existsSync(playlistFile);
    console.log(`Playlist request - stream_active: ${streamActive}, playlist exists: ${playlistExists}, ffmpeg running: ${ffmpegProcess && !ffmpegProcess.killed}`);
    
    if (!streamActive || !playlistExists) {
        console.log('Playlist not available - stream_active:', streamActive, 'playlist exists:', playlistExists);
        return res.status(404).json({ error: 'No active stream available' });
    }
    
    res.setHeader('Content-Type', 'application/vnd.apple.mpegurl');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.sendFile(playlistFile);
});

app.get('/segment_*.ts', (req, res) => {
    if (!streamActive) {
        return res.status(404).json({ error: 'No active stream available' });
    }
    
    const filename = req.params[0];
    const filePath = path.join(hlsOutputDir, filename);
    
    if (!fs.existsSync(filePath)) {
        return res.status(404).json({ error: 'File not found' });
    }
    
    res.setHeader('Content-Type', 'video/mp2t');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.sendFile(filePath);
});

app.get('/stream_info', (req, res) => {
    const playlistExists = fs.existsSync(playlistFile) && streamActive;
    const segmentCount = streamActive ? fs.readdirSync(hlsOutputDir).filter(f => f.endsWith('.ts')).length : 0;
    
    // Get the server's external IP or localhost
    const os = require('os');
    const networkInterfaces = os.networkInterfaces();
    let externalIp = 'localhost';
    
    for (const interfaceName in networkInterfaces) {
        const interfaces = networkInterfaces[interfaceName];
        for (const iface of interfaces) {
            if (iface.family === 'IPv4' && !iface.internal) {
                externalIp = iface.address;
                break;
            }
        }
        if (externalIp !== 'localhost') break;
    }
    
    res.json({
        stream_active: streamActive,
        playlist_exists: playlistExists,
        segment_count: segmentCount,
        stream_urls: {
            playlist_url: `http://${externalIp}:${PORT}/playlist.m3u8`,
            localhost_url: `http://localhost:${PORT}/playlist.m3u8`,
            direct_playlist: `http://${externalIp}:${PORT}/playlist.m3u8`
        },
        instructions: {
            vlc: `Open VLC → Media → Open Network Stream → Enter: http://${externalIp}:${PORT}/playlist.m3u8`,
            obs: `Add Media Source → Enter URL: http://${externalIp}:${PORT}/playlist.m3u8`,
            ffplay: `Run: ffplay http://${externalIp}:${PORT}/playlist.m3u8`,
            browser: `Open: http://${externalIp}:${PORT}/playlist.m3u8`
        },
        timestamp: new Date().toISOString()
    });
});

app.get('/health', (req, res) => {
    const playlistExists = fs.existsSync(playlistFile) && streamActive;
    const segmentCount = streamActive ? fs.readdirSync(hlsOutputDir).filter(f => f.endsWith('.ts')).length : 0;
    
    const uptime = new Date() - serverStartTime;
    const hours = Math.floor(uptime / (1000 * 60 * 60));
    const minutes = Math.floor((uptime % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((uptime % (1000 * 60)) / 1000);
    const uptimeStr = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    
    res.json({
        status: 'healthy',
        timestamp: new Date().toISOString(),
        ffmpeg_available: true, // Assuming FFmpeg is available in container
        stream_active: streamActive,
        hls_playlist_exists: playlistExists,
        hls_segment_count: segmentCount,
        server_uptime: uptimeStr
    });
});

// Cleanup on exit
process.on('SIGINT', () => {
    console.log('\nShutting down server...');
    stopLiveStream();
    process.exit(0);
});

process.on('SIGTERM', () => {
    console.log('\nShutting down server...');
    stopLiveStream();
    process.exit(0);
});

// Start the server
console.log("Live Timer Stream Server (HD Quality)");
console.log("=" * 40);
console.log(`Server started at: ${serverStartTime}`);
console.log(`Starting server on http://0.0.0.0:${PORT}`);
console.log("HD quality HLS streaming with persistent timer");
console.log("Auto-starting live stream...");

// Auto-start the stream when server boots up
setTimeout(() => {
    const success = startLiveStream();
    if (success) {
        console.log("✅ HD live stream started successfully");
    } else {
        console.log("❌ Failed to start HD live stream");
    }
}, 3000);

app.listen(PORT, '0.0.0.0', () => {
    console.log(`Server running on port ${PORT}`);
});
