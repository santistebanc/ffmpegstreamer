from flask import Flask, Response, jsonify, render_template_string, send_file
import subprocess
import os
import threading
import time
from datetime import datetime
import signal
import sys
import glob
import shutil

app = Flask(__name__)

# Global variables for live streaming
server_start_time = datetime.now()
ffmpeg_process = None
stream_active = False
hls_output_dir = "/app/hls"
playlist_file = os.path.join(hls_output_dir, "playlist.m3u8")

# HTML template for the web interface
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Live Timer Stream (Optimized HD)</title>
    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f0f0f0; }
        .container { max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; text-align: center; }
        .video-container { text-align: center; margin: 20px 0; }
        video { max-width: 100%; border: 2px solid #ddd; border-radius: 5px; }
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
        .controls { text-align: center; margin: 20px 0; }
        button { background: #dc3545; color: white; border: none; padding: 12px 24px; border-radius: 5px; cursor: pointer; font-size: 16px; margin: 0 10px; }
        button:hover { background: #c82333; }
        button:disabled { background: #6c757d; cursor: not-allowed; }
        .cast-btn { background: #4285f4; }
        .cast-btn:hover { background: #3367d6; }
        .cast-btn:disabled { background: #ccc; }
        .quality-info { background: #e7f3ff; padding: 10px; border-radius: 5px; margin: 10px 0; font-size: 14px; }
        .cast-status { margin-top: 15px; padding: 10px; background: #f8f9fa; border-radius: 5px; font-family: monospace; white-space: pre-wrap; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⏱️ Live Timer Stream (Optimized HD)</h1>
        <div class="info">
            <p><strong>Live Stream:</strong> This server streams a live HD video showing a timer that counts up from when the server started.</p>
            <p><strong>Features:</strong> Real-time timer display with a moving square background animation in optimized HD quality.</p>
            <div class="hls-info">
                <strong>HLS Streaming:</strong> Using HTTP Live Streaming (HLS) format with optimized HD quality (1920x1080) for maximum compatibility and adaptive bitrate streaming.
            </div>
            <div class="quality-info">
                <strong>Optimized Settings:</strong> Ubuntu-based with full FFmpeg codec support, hardware acceleration, and adaptive bitrate streaming.
            </div>
        </div>
        <div class="status" id="status">Connecting to live stream...</div>
        <div class="timer-display" id="timerDisplay">00:00:00</div>
        
        <div class="controls">
            <button id="restartBtn" onclick="restartStream()">
                🔄 Restart Stream
            </button>
            <button id="restartCountBtn" onclick="restartCount()" style="background: #17a2b8;">
                ⏰ Restart Count
            </button>
            <button id="castBtn" class="cast-btn" onclick="connectCast()" disabled>
                📺 Connect to TV
            </button>
            <button id="castStreamBtn" class="cast-btn" onclick="castStream()" disabled>
                🎥 Cast Stream
            </button>
        </div>
        
        <div class="cast-status" id="castStatus">Loading Cast SDK...</div>
        
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
        
        function restartCount() {
            const restartCountBtn = document.getElementById('restartCountBtn');
            const originalText = restartCountBtn.textContent;
            
            restartCountBtn.disabled = true;
            restartCountBtn.textContent = '⏰ Restarting...';
            document.getElementById('status').textContent = 'Restarting count and stream...';
            
            // Destroy current HLS instance
            if (hls) {
                hls.destroy();
                hls = null;
            }
            
            fetch('/restart_count', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('status').textContent = 'Count and stream restarted! Reconnecting...';
                        // Reset the timer display immediately
                        document.getElementById('timerDisplay').textContent = '00:00:00';
                        
                        // Restart the timer from zero
                        if (timerInterval) {
                            clearInterval(timerInterval);
                        }
                        
                        // Wait a moment for stream to be ready, then reconnect
                        setTimeout(() => {
                            connectToStream();
                        }, 3000);
                    } else {
                        document.getElementById('status').textContent = 'Error: ' + data.error;
                        restartCountBtn.disabled = false;
                        restartCountBtn.textContent = originalText;
                    }
                })
                .catch(error => {
                    document.getElementById('status').textContent = 'Error: ' + error.message;
                    restartCountBtn.disabled = false;
                    restartCountBtn.textContent = originalText;
                })
                .finally(() => {
                    // Re-enable button after a delay
                    setTimeout(() => {
                        restartCountBtn.disabled = false;
                        restartCountBtn.textContent = originalText;
                    }, 5000);
                });
        }
        
        function loadStreamInfo() {
            fetch('/stream_info')
                .then(response => response.json())
                .then(data => {
                    if (data.stream_active && data.playlist_exists) {
                        const streamUrl = data.stream_urls.playlist_url;
                        document.getElementById('streamUrl').value = streamUrl;
                        document.getElementById('streamUrlSection').style.display = 'block';
                        
                        // Update cast functionality with stream URL
                        updateStreamUrl(streamUrl);
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
                    backBufferLength: 90,
                    maxBufferLength: 30,
                    maxMaxBufferLength: 60
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
    
    <!-- Google Cast SDK -->
    <script src="https://www.gstatic.com/cv/js/sender/v1/cast_sender.js?loadCastFramework"></script>
    <script>
        // Cast functionality
        let castContext = null;
        let currentStreamUrl = '';
        
        function logCast(msg) {
            const statusEl = document.getElementById('castStatus');
            statusEl.textContent = msg;
            console.log('Cast:', msg);
        }
        
        // Called when Cast API is loaded
        window['__onGCastApiAvailable'] = function(isAvailable) {
            if (isAvailable) {
                try {
                    castContext = cast.framework.CastContext.getInstance();
                    castContext.setOptions({
                        receiverApplicationId: chrome.cast.media.DEFAULT_MEDIA_RECEIVER_APP_ID,
                        autoJoinPolicy: chrome.cast.AutoJoinPolicy.ORIGIN_SCOPED
                    });
                    
                    document.getElementById('castBtn').disabled = false;
                    logCast("Cast API ready. Click 'Connect to TV' to connect to your LG TV.");
                } catch (error) {
                    logCast("Error initializing Cast API: " + error.message);
                }
            } else {
                logCast("Cast API not available. Use Chrome or a Cast-enabled browser.");
            }
        };
        
        function connectCast() {
            if (!castContext) {
                logCast("Cast API not available.");
                return;
            }
            
            const castBtn = document.getElementById('castBtn');
            const castStreamBtn = document.getElementById('castStreamBtn');
            
            castBtn.disabled = true;
            castBtn.textContent = '📺 Connecting...';
            logCast("Connecting to Cast device...");
            
            castContext.requestSession().then(
                (session) => {
                    const deviceName = session.getCastDevice().friendlyName;
                    logCast("Connected to " + deviceName + "! Ready to cast stream.");
                    castBtn.textContent = '📺 Connected to ' + deviceName;
                    castStreamBtn.disabled = false;
                },
                (err) => {
                    logCast("Cast connection failed: " + JSON.stringify(err));
                    castBtn.disabled = false;
                    castBtn.textContent = '📺 Connect to TV';
                }
            );
        }
        
        function castStream() {
            if (!castContext) {
                logCast("Cast API not available.");
                return;
            }
            
            const session = castContext.getCurrentSession();
            if (!session) {
                logCast("Please connect to a Cast device first (press the Connect to TV button).");
                return;
            }
            
            // Get the current stream URL
            if (!currentStreamUrl) {
                logCast("No stream URL available. Please wait for stream to start.");
                return;
            }
            
            const castStreamBtn = document.getElementById('castStreamBtn');
            castStreamBtn.disabled = true;
            castStreamBtn.textContent = '🎥 Casting...';
            logCast("Casting HLS stream: " + currentStreamUrl);
            
            // Cast the HLS stream
            const mediaInfo = new chrome.cast.media.MediaInfo(currentStreamUrl, 'application/vnd.apple.mpegurl');
            mediaInfo.contentType = 'application/vnd.apple.mpegurl';
            mediaInfo.streamType = chrome.cast.media.StreamType.LIVE;
            
            // Add metadata
            mediaInfo.metadata = new chrome.cast.media.GenericMediaMetadata();
            mediaInfo.metadata.title = "Live Timer Stream";
            mediaInfo.metadata.subtitle = "HD HLS Stream with Timer";
            
            const request = new chrome.cast.media.LoadRequest(mediaInfo);
            request.currentTime = 0;
            request.autoplay = true;

            session.loadMedia(request).then(
                () => {
                    logCast("HLS stream sent to TV successfully! Stream is now playing on your LG TV.");
                    castStreamBtn.textContent = '🎥 Casting Active';
                },
                (err) => {
                    logCast("Error casting HLS stream: " + JSON.stringify(err));
                    castStreamBtn.disabled = false;
                    castStreamBtn.textContent = '🎥 Cast Stream';
                }
            );
        }
        
        // Update stream URL when stream info is loaded
        function updateStreamUrl(url) {
            currentStreamUrl = url;
            if (castContext && castContext.getCurrentSession()) {
                document.getElementById('castStreamBtn').disabled = false;
            }
        }
    </script>
</body>
</html>
"""

def start_live_stream():
    """Start the live stream with optimized FFmpeg settings for Ubuntu"""
    global ffmpeg_process, stream_active
    
    try:
        if ffmpeg_process and ffmpeg_process.poll() is None:
            return True  # Stream already running
        
        # Create HLS output directory
        os.makedirs(hls_output_dir, exist_ok=True)
        
        # Clean up old segments
        for file in glob.glob(os.path.join(hls_output_dir, "*.ts")):
            os.remove(file)
        if os.path.exists(playlist_file):
            os.remove(playlist_file)
        
        # Optimized FFmpeg command for Ubuntu with full codec support
        ffmpeg_cmd = [
            'ffmpeg',
            '-f', 'lavfi',
            '-i', 'testsrc2=size=1920x1080:rate=30',  # Full HD resolution
            '-vf', 
            'drawbox=x=200+200*cos(t*2*PI/5):y=200+200*sin(t*2*PI/5):w=400:h=400:color=red@0.8:t=fill,'
            'drawtext=text=\'Server Uptime\':x=40:y=80:fontsize=48:fontcolor=white:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf,'
            'drawtext=text=\'%{pts\\:hms}\':x=40:y=140:fontsize=64:fontcolor=yellow:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf,'
            'drawtext=text=\'HLS Live Stream\':x=40:y=220:fontsize=36:fontcolor=cyan:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf,'
            'drawtext=text=\'Optimized HD Quality\':x=40:y=280:fontsize=28:fontcolor=lime:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '-c:v', 'libx264',
            '-preset', 'fast',  # Good balance of quality and speed
            '-tune', 'zerolatency',
            '-crf', '18',  # High quality (lower CRF)
            '-maxrate', '4M',  # Higher bitrate for HD
            '-bufsize', '8M',  # Larger buffer for HD
            '-pix_fmt', 'yuv420p',
            '-f', 'hls',
            '-hls_time', '6',  # 6-second segments for better quality
            '-hls_list_size', '10',  # Keep 10 segments in playlist
            '-hls_flags', 'delete_segments+independent_segments',
            '-hls_segment_filename', os.path.join(hls_output_dir, 'segment_%03d.ts'),
            playlist_file
        ]
        
        print(f"Starting optimized FFmpeg with command: {' '.join(ffmpeg_cmd)}")
        
        # Start FFmpeg process
        ffmpeg_process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0
        )
        
        # Wait a moment and check if FFmpeg started successfully
        time.sleep(3)
        
        if ffmpeg_process.poll() is not None:
            # Process exited, get error
            stdout, stderr = ffmpeg_process.communicate()
            error_msg = f"FFmpeg exited with code {ffmpeg_process.returncode}\nSTDOUT: {stdout.decode()}\nSTDERR: {stderr.decode()}"
            print(f"FFmpeg error: {error_msg}")
            return False
        
        stream_active = True
        print(f"FFmpeg started successfully, PID: {ffmpeg_process.pid}")
        return True
        
    except Exception as e:
        print(f"Error starting stream: {e}")
        return False

def stop_live_stream():
    """Stop the live stream and cleanup HLS files"""
    global ffmpeg_process, stream_active
    
    try:
        if ffmpeg_process and ffmpeg_process.poll() is None:
            ffmpeg_process.terminate()
            ffmpeg_process.wait(timeout=5)
        
        ffmpeg_process = None
        stream_active = False
        
        # Clean up HLS files
        if os.path.exists(hls_output_dir):
            shutil.rmtree(hls_output_dir)
        
        return True
        
    except Exception as e:
        print(f"Error stopping stream: {e}")
        return False

def cleanup_on_exit():
    """Cleanup function for graceful shutdown"""
    stop_live_stream()
    sys.exit(0)

@app.route('/')
def index():
    """Serve the main page"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/restart_stream', methods=['POST'])
def restart_stream():
    """Restart the live stream"""
    try:
        # Stop current stream
        stop_live_stream()
        time.sleep(2)  # Wait a moment
        
        # Start new stream
        success = start_live_stream()
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Stream restarted successfully',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to restart stream - check server logs for FFmpeg errors',
                'timestamp': datetime.now().isoformat()
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/restart_count', methods=['POST'])
def restart_count():
    """Restart the server uptime count/timer and restart the stream"""
    global server_start_time
    
    try:
        # Update the server start time to now
        server_start_time = datetime.now()
        
        # Restart the stream so the video timer resets too
        if stream_active:
            stop_live_stream()
            time.sleep(2)  # Wait a moment
            success = start_live_stream()
            
            if not success:
                return jsonify({
                    'success': False,
                    'error': 'Count restarted but failed to restart stream',
                    'timestamp': datetime.now().isoformat()
                }), 500
        
        return jsonify({
            'success': True,
            'message': 'Count and stream restarted successfully',
            'new_start_time': server_start_time.isoformat(),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/playlist.m3u8')
def serve_playlist():
    """Serve the HLS playlist"""
    print(f"Playlist request - stream_active: {stream_active}, playlist exists: {os.path.exists(playlist_file) if stream_active else False}")
    if not stream_active or not os.path.exists(playlist_file):
        return jsonify({'error': 'No active stream available'}), 404
    
    response = send_file(playlist_file, mimetype='application/vnd.apple.mpegurl')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

@app.route('/<path:filename>')
def serve_hls_segment(filename):
    """Serve HLS segments and other files"""
    if not stream_active:
        return jsonify({'error': 'No active stream available'}), 404
    
    file_path = os.path.join(hls_output_dir, filename)
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404
    
    # Determine MIME type based on file extension
    if filename.endswith('.ts'):
        mimetype = 'video/mp2t'
    elif filename.endswith('.m3u8'):
        mimetype = 'application/vnd.apple.mpegurl'
    else:
        mimetype = 'application/octet-stream'
    
    response = send_file(file_path, mimetype=mimetype)
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

@app.route('/stream_info')
def stream_info():
    """Get stream URL and information"""
    playlist_exists = os.path.exists(playlist_file) if stream_active else False
    segment_count = len(glob.glob(os.path.join(hls_output_dir, "*.ts"))) if stream_active else 0
    
    # Get the server's external IP or localhost
    import socket
    try:
        # Try to get external IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        external_ip = s.getsockname()[0]
        s.close()
    except:
        external_ip = "localhost"
    
    return jsonify({
        'stream_active': stream_active,
        'playlist_exists': playlist_exists,
        'segment_count': segment_count,
        'stream_urls': {
            'playlist_url': f"http://{external_ip}:5000/playlist.m3u8",
            'localhost_url': "http://localhost:5000/playlist.m3u8",
            'direct_playlist': f"http://{external_ip}:5000/playlist.m3u8"
        },
        'instructions': {
            'vlc': f"Open VLC → Media → Open Network Stream → Enter: http://{external_ip}:5000/playlist.m3u8",
            'obs': f"Add Media Source → Enter URL: http://{external_ip}:5000/playlist.m3u8",
            'ffplay': f"Run: ffplay http://{external_ip}:5000/playlist.m3u8",
            'browser': f"Open: http://{external_ip}:5000/playlist.m3u8"
        },
        'timestamp': datetime.now().isoformat()
    })

@app.route('/health')
def health_check():
    """Health check endpoint"""
    playlist_exists = os.path.exists(playlist_file) if stream_active else False
    segment_count = len(glob.glob(os.path.join(hls_output_dir, "*.ts"))) if stream_active else 0
    
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'ffmpeg_available': check_ffmpeg(),
        'stream_active': stream_active,
        'hls_playlist_exists': playlist_exists,
        'hls_segment_count': segment_count,
        'server_uptime': str(datetime.now() - server_start_time)
    })

def check_ffmpeg():
    """Check if FFmpeg is available"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except:
        return False

# Register signal handlers for graceful shutdown
signal.signal(signal.SIGINT, lambda s, f: cleanup_on_exit())
signal.signal(signal.SIGTERM, lambda s, f: cleanup_on_exit())

if __name__ == '__main__':
    print("Live Timer Stream Server (Optimized HD)")
    print("=" * 45)
    print(f"Server started at: {server_start_time}")
    print("Starting server on http://0.0.0.0:5000")
    print("Optimized HD quality HLS streaming with Ubuntu")
    print("Auto-starting live stream...")
    
    # Auto-start the stream when server boots up
    def auto_start_stream():
        time.sleep(3)  # Wait for server to be ready
        success = start_live_stream()
        if success:
            print("✅ Optimized HD live stream started successfully")
        else:
            print("❌ Failed to start optimized HD live stream")
    
    # Start stream in background thread
    stream_thread = threading.Thread(target=auto_start_stream, daemon=True)
    stream_thread.start()
    
    try:
        # Start the Flask server
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\nShutting down server...")
        cleanup_on_exit()
    except Exception as e:
        print(f"Server error: {e}")
        cleanup_on_exit()
