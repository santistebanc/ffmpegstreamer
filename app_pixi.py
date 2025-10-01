from flask import Flask, jsonify, send_file, render_template_string
from datetime import datetime
import os
import time
import threading
import subprocess
import signal
import glob
import shutil

app = Flask(__name__)

# Global variables for live streaming
server_start_time = datetime.now()
pixi_process = None
stream_active = False
hls_output_dir = "/app/hls"
playlist_file = os.path.join(hls_output_dir, "playlist.m3u8")

# HTML template for the web interface
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>PixiJS Live Stream</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            min-height: 100vh;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            padding: 30px;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }
        h1 {
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.5);
        }
        .video-container {
            position: relative;
            width: 100%;
            max-width: 800px;
            margin: 0 auto 30px;
            background: #000;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
        }
        video {
            width: 100%;
            height: auto;
            display: block;
        }
        .info {
            background: rgba(0, 0, 0, 0.3);
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            border-left: 4px solid #00ff00;
        }
        .status {
            background: rgba(0, 0, 0, 0.3);
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            font-weight: bold;
            text-align: center;
        }
        .controls {
            display: flex;
            gap: 15px;
            justify-content: center;
            flex-wrap: wrap;
            margin-bottom: 20px;
        }
        button {
            background: linear-gradient(45deg, #ff6b6b, #ee5a24);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 25px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
        }
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3);
        }
        button:disabled {
            background: #666;
            cursor: not-allowed;
            transform: none;
        }
        .cast-btn {
            background: linear-gradient(45deg, #4285f4, #34a853);
        }
        .cast-status {
            background: rgba(0, 0, 0, 0.3);
            padding: 10px;
            border-radius: 8px;
            margin-top: 10px;
            text-align: center;
            font-size: 14px;
        }
        .timer-display {
            font-size: 2em;
            font-weight: bold;
            text-align: center;
            margin: 20px 0;
            color: #00ff00;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.5);
        }
        .links {
            background: rgba(0, 0, 0, 0.3);
            padding: 20px;
            border-radius: 10px;
            margin-top: 20px;
        }
        .links h3 {
            margin-top: 0;
            color: #00ffff;
        }
        .links a {
            color: #00ff00;
            text-decoration: none;
            display: block;
            margin: 10px 0;
            padding: 8px;
            background: rgba(0, 255, 0, 0.1);
            border-radius: 5px;
            transition: background 0.3s ease;
        }
        .links a:hover {
            background: rgba(0, 255, 0, 0.2);
        }
        .tech-info {
            background: rgba(0, 0, 0, 0.3);
            padding: 15px;
            border-radius: 10px;
            margin-top: 20px;
            font-size: 14px;
            border-left: 4px solid #ff6b6b;
        }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
</head>
<body>
    <div class="container">
        <h1>🎨 PixiJS Live Stream</h1>
        
        <div class="timer-display" id="timerDisplay">00:00:00</div>
        
        <div class="video-container">
            <video id="video" controls muted autoplay>
                <source src="/playlist.m3u8" type="application/vnd.apple.mpegurl">
                Your browser does not support HLS video playback.
            </video>
        </div>
        
        <div class="status" id="status">Loading stream...</div>
        
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
        
        <div class="info">
            <h3>🎨 PixiJS Server-Side Rendering</h3>
            <p><strong>Technology:</strong> PixiJS + Node.js + FFmpeg + HLS</p>
            <p><strong>Resolution:</strong> 1920x1080 (Full HD)</p>
            <p><strong>Frame Rate:</strong> 30 FPS</p>
            <p><strong>Quality:</strong> High Definition with hardware acceleration</p>
            <p><strong>Features:</strong> Animated graphics, real-time timer, server-side rendering</p>
        </div>
        
        <div class="links">
            <h3>🔗 Stream Links</h3>
            <a href="/playlist.m3u8" target="_blank">HLS Playlist (M3U8)</a>
            <a href="/stream_info" target="_blank">Stream Information (JSON)</a>
            <a href="/health" target="_blank">Health Check (JSON)</a>
        </div>
        
        <div class="tech-info">
            <h3>🔧 Technical Details</h3>
            <p><strong>PixiJS:</strong> Server-side canvas rendering with Node.js</p>
            <p><strong>FFmpeg:</strong> Real-time video encoding to HLS format</p>
            <p><strong>HLS:</strong> HTTP Live Streaming for broad compatibility</p>
            <p><strong>Features:</strong> Animated square, live timer, dynamic text overlays</p>
            <p><strong>Compatibility:</strong> Works with VLC, browsers, and streaming platforms</p>
        </div>
    </div>

    <script>
        let hls;
        let timerInterval;
        let castContext = null;
        let currentStreamUrl = '';

        // Initialize HLS
        function initHLS() {
            const video = document.getElementById('video');
            
            if (Hls.isSupported()) {
                hls = new Hls({
                    enableWorker: true,
                    lowLatencyMode: true,
                    backBufferLength: 90
                });
                
                hls.loadSource('/playlist.m3u8');
                hls.attachMedia(video);
                
                hls.on(Hls.Events.MANIFEST_PARSED, function() {
                    console.log('HLS manifest parsed, starting playback');
                    document.getElementById('status').textContent = 'Stream connected! Canvas rendering active.';
                    video.play();
                });
                
                hls.on(Hls.Events.ERROR, function(event, data) {
                    console.error('HLS error:', data);
                    if (data.fatal) {
                        document.getElementById('status').textContent = 'Stream error: ' + data.type;
                        // Try to reconnect after a delay
                        setTimeout(() => {
                            if (hls) {
                                hls.destroy();
                                hls = null;
                            }
                            initHLS();
                        }, 3000);
                    }
                });
            } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
                video.src = '/playlist.m3u8';
                video.addEventListener('loadedmetadata', function() {
                    document.getElementById('status').textContent = 'Stream connected! Canvas rendering active.';
                });
            } else {
                document.getElementById('status').textContent = 'HLS not supported in this browser';
            }
        }

        // Start timer
        function startTimer() {
            const startTime = new Date();
            timerInterval = setInterval(() => {
                const now = new Date();
                const elapsed = Math.floor((now - startTime) / 1000);
                const hours = Math.floor(elapsed / 3600);
                const minutes = Math.floor((elapsed % 3600) / 60);
                const seconds = elapsed % 60;
                
                document.getElementById('timerDisplay').textContent = 
                    `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
            }, 1000);
        }

        // Restart stream
        function restartStream() {
            const restartBtn = document.getElementById('restartBtn');
            const originalText = restartBtn.textContent;
            
            restartBtn.disabled = true;
            restartBtn.textContent = '🔄 Restarting...';
            document.getElementById('status').textContent = 'Restarting PixiJS stream...';
            
            // Destroy current HLS instance
            if (hls) {
                hls.destroy();
                hls = null;
            }
            
            fetch('/restart_stream', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('status').textContent = 'PixiJS stream restarted! Reconnecting...';
                        setTimeout(() => {
                            initHLS();
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
            document.getElementById('status').textContent = 'Restarting count and video timer...';
            
            // Destroy current HLS instance
            if (hls) {
                hls.destroy();
                hls = null;
            }
            
            fetch('/restart_count', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('status').textContent = 'Count and video timer restarted! Reconnecting...';
                        // Reset the timer display immediately
                        document.getElementById('timerDisplay').textContent = '00:00:00';
                        
                        // Restart the timer from zero
                        if (timerInterval) {
                            clearInterval(timerInterval);
                        }
                        
                        // Wait for stream to be ready, then reconnect
                        setTimeout(() => {
                            initHLS();
                        }, 2000);
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

        // Cast functionality
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
                    if (session && session.getCastDevice) {
                        const deviceName = session.getCastDevice().friendlyName;
                        logCast("Connected to " + deviceName + "! Ready to cast stream.");
                        castBtn.textContent = '📺 Connected to ' + deviceName;
                        castStreamBtn.disabled = false;
                    } else {
                        logCast("Invalid session received from Cast API");
                        castBtn.disabled = false;
                        castBtn.textContent = '📺 Connect to TV';
                    }
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
            logCast("Casting Canvas HLS stream: " + currentStreamUrl);
            
            // Cast the HLS stream
            const mediaInfo = new chrome.cast.media.MediaInfo(currentStreamUrl, 'application/vnd.apple.mpegurl');
            mediaInfo.contentType = 'application/vnd.apple.mpegurl';
            mediaInfo.streamType = chrome.cast.media.StreamType.LIVE;
            
            // Add metadata
            mediaInfo.metadata = new chrome.cast.media.GenericMediaMetadata();
            mediaInfo.metadata.title = "Canvas Live Stream";
            mediaInfo.metadata.subtitle = "Server-Side Rendering with Timer";
            
            const request = new chrome.cast.media.LoadRequest(mediaInfo);
            request.currentTime = 0;
            request.autoplay = true;

            session.loadMedia(request).then(
                () => {
                    logCast("Canvas HLS stream sent to TV successfully! Stream is now playing on your LG TV.");
                    castStreamBtn.textContent = '🎥 Casting Active';
                },
                (err) => {
                    logCast("Error casting Canvas HLS stream: " + JSON.stringify(err));
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

        // Check if stream is already running and reconnect
        function checkAndReconnect() {
            fetch('/health')
                .then(response => response.json())
                .then(data => {
                    if (data.stream_active && data.hls_playlist_exists) {
                        console.log('Stream is already running, reconnecting...');
                        initHLS();
                    } else {
                        console.log('Stream not ready yet, will retry...');
                        setTimeout(checkAndReconnect, 2000);
                    }
                })
                .catch(error => {
                    console.error('Error checking stream status:', error);
                    setTimeout(checkAndReconnect, 2000);
                });
        }

        // Initialize everything
        document.addEventListener('DOMContentLoaded', function() {
            checkAndReconnect();
            startTimer();
            updateStreamUrl('/playlist.m3u8');
        });
    </script>
    
    <!-- Google Cast SDK -->
    <script src="https://www.gstatic.com/cv/js/sender/v1/cast_sender.js?loadCastFramework"></script>
</body>
</html>
"""

def start_pixi_stream():
    """Start the Canvas streaming process"""
    global pixi_process, stream_active
    
    try:
        # Kill existing process if running
        if pixi_process and pixi_process.poll() is None:
            pixi_process.terminate()
            time.sleep(2)
        
        # Start Canvas server
        pixi_process = subprocess.Popen(
            ['node', 'pixi-server.js'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None
        )
        
        stream_active = True
        print("Canvas streaming process started")
        return True
        
    except Exception as e:
        print(f"Error starting Canvas stream: {e}")
        return False

def stop_pixi_stream():
    """Stop the PixiJS streaming process"""
    global pixi_process, stream_active
    
    try:
        if pixi_process and pixi_process.poll() is None:
            if hasattr(os, 'killpg'):
                os.killpg(os.getpgid(pixi_process.pid), signal.SIGTERM)
            else:
                pixi_process.terminate()
            
            # Wait for process to terminate
            try:
                pixi_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pixi_process.kill()
        
        stream_active = False
        print("PixiJS streaming process stopped")
        return True
        
    except Exception as e:
        print(f"Error stopping PixiJS stream: {e}")
        return False

@app.route('/')
def index():
    """Serve the main page"""
    return HTML_TEMPLATE

@app.route('/health')
def health():
    """Health check endpoint"""
    global stream_active, server_start_time
    
    uptime = datetime.now() - server_start_time
    uptime_str = str(uptime).split('.')[0]  # Remove microseconds
    
    # Check if Canvas-generated HLS files exist
    hls_playlist_exists = os.path.exists(playlist_file)
    hls_segment_count = len(glob.glob(os.path.join(hls_output_dir, "*.ts")))
    canvas_stream_active = hls_playlist_exists and hls_segment_count > 0
    
    return jsonify({
        'status': 'healthy',
        'stream_active': canvas_stream_active,
        'canvas_process_running': canvas_stream_active,
        'hls_playlist_exists': hls_playlist_exists,
        'hls_segment_count': hls_segment_count,
        'server_uptime': uptime_str,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/stream_info')
def stream_info():
    """Get stream information"""
    global stream_active, server_start_time
    
    uptime = datetime.now() - server_start_time
    uptime_str = str(uptime).split('.')[0]
    
    # Check if Canvas-generated HLS files exist
    hls_playlist_exists = os.path.exists(playlist_file)
    hls_segment_count = len(glob.glob(os.path.join(hls_output_dir, "*.ts")))
    canvas_stream_active = hls_playlist_exists and hls_segment_count > 0
    
    return jsonify({
        'stream_active': canvas_stream_active,
        'canvas_process_running': canvas_stream_active,
        'hls_playlist_url': '/playlist.m3u8',
        'server_uptime': uptime_str,
        'technology': 'Canvas + Node.js + FFmpeg + HLS',
        'resolution': '1920x1080',
        'frame_rate': '30 FPS',
        'quality': 'HD with hardware acceleration',
        'features': ['Animated graphics', 'Real-time timer', 'Server-side rendering'],
        'timestamp': datetime.now().isoformat()
    })

@app.route('/restart_stream', methods=['POST'])
def restart_stream():
    """Restart the PixiJS stream"""
    try:
        stop_pixi_stream()
        time.sleep(2)
        success = start_pixi_stream()
        
        if success:
            return jsonify({
                'success': True,
                'message': 'PixiJS stream restarted successfully',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to restart PixiJS stream',
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
    """Restart the server uptime count/timer and restart the stream seamlessly"""
    global server_start_time
    
    try:
        # Update the server start time to now
        server_start_time = datetime.now()
        
        # Restart the stream to reset the video timer
        if stream_active:
            # Stop current stream
            stop_pixi_stream()
            time.sleep(1)  # Brief pause
            
            # Start new stream with reset timer
            success = start_pixi_stream()
            
            if not success:
                return jsonify({
                    'success': False,
                    'error': 'Count restarted but failed to restart PixiJS stream',
                    'timestamp': datetime.now().isoformat()
                }), 500
        
        return jsonify({
            'success': True,
            'message': 'Count and video timer restarted successfully',
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
    # Check if Canvas-generated HLS files exist
    hls_playlist_exists = os.path.exists(playlist_file)
    hls_segment_count = len(glob.glob(os.path.join(hls_output_dir, "*.ts")))
    canvas_stream_active = hls_playlist_exists and hls_segment_count > 0
    
    if not canvas_stream_active:
        return "Stream not available", 404
    
    response = send_file(playlist_file, mimetype='application/vnd.apple.mpegurl')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

@app.route('/segment_<int:segment_num>.ts')
def serve_hls_segment(segment_num):
    """Serve HLS video segments"""
    segment_file = os.path.join(hls_output_dir, f"segment_{segment_num:03d}.ts")
    
    if not os.path.exists(segment_file):
        return "Segment not found", 404
    
    response = send_file(segment_file, mimetype='video/mp2t')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

def cleanup_on_exit():
    """Cleanup function for graceful shutdown"""
    stop_pixi_stream()
    
    # Clean up HLS files
    if os.path.exists(hls_output_dir):
        for file in glob.glob(os.path.join(hls_output_dir, "*.ts")):
            try:
                os.remove(file)
            except:
                pass
        if os.path.exists(playlist_file):
            try:
                os.remove(playlist_file)
            except:
                pass

if __name__ == '__main__':
    import atexit
    atexit.register(cleanup_on_exit)
    
    print("Starting Flask app with Canvas integration...")
    print("Canvas stream is already running via Docker CMD")
    print("Access the stream at: http://localhost:5000")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
