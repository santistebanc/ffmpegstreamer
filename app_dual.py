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
hls_process = None
stream_active = False
hls_active = False

# HLS configuration
hls_output_dir = '/app/hls'
playlist_file = os.path.join(hls_output_dir, 'playlist.m3u8')

# HTML template for the web interface
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Live Timer Stream (Dual Format)</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f0f0f0; }
        .container { max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
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
        .warning { background: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #ffc107; }
        .streams { display: flex; gap: 20px; margin: 20px 0; }
        .stream-box { flex: 1; border: 1px solid #ddd; padding: 15px; border-radius: 5px; }
        .stream-box h3 { margin-top: 0; color: #333; }
        .url-box { background: #f8f9fa; padding: 10px; border-radius: 3px; font-family: monospace; font-size: 12px; word-break: break-all; }
        .copy-btn { background: #28a745; font-size: 12px; padding: 5px 10px; margin-top: 5px; }
        .copy-btn:hover { background: #218838; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⏱️ Live Timer Stream (Dual Format)</h1>
        <div class="info">
            <p><strong>Dual Format:</strong> Streams both direct MP4 and HLS formats simultaneously.</p>
            <p><strong>Features:</strong> Moving test pattern with JavaScript timer overlay.</p>
            <div class="warning">
                <strong>Note:</strong> This version provides both direct streaming and HLS for maximum compatibility.
            </div>
        </div>
        <div class="status" id="status">Connecting to live stream...</div>
        <div class="timer-display" id="timerDisplay">00:00:00</div>
        
        <div class="streams" id="streamsContainer" style="display: none;">
            <div class="stream-box">
                <h3>📺 Direct MP4 Stream</h3>
                <p>Direct video stream for browsers</p>
                <div class="url-box" id="mp4Url">http://your-server:5000/stream</div>
                <button class="copy-btn" onclick="copyToClipboard('mp4Url')">Copy URL</button>
                <div class="video-container">
                    <video id="videoPlayer" autoplay muted controls>
                        <source src="/stream" type="video/mp4">
                        Your browser does not support the video tag.
                    </video>
                    <div id="videoInfo" style="margin-top: 10px; font-size: 12px; color: #666;"></div>
                </div>
            </div>
            
            <div class="stream-box">
                <h3>📡 HLS Stream</h3>
                <p>HLS stream for external players (VLC, etc.)</p>
                <div class="url-box" id="hlsUrl">http://your-server:5000/playlist.m3u8</div>
                <button class="copy-btn" onclick="copyToClipboard('hlsUrl')">Copy URL</button>
                <div class="video-container">
                    <video id="hlsPlayer" autoplay muted controls>
                        <source src="/playlist.m3u8" type="application/x-mpegURL">
                        Your browser does not support HLS.
                    </video>
                    <div id="hlsInfo" style="margin-top: 10px; font-size: 12px; color: #666;"></div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
    <script>
        let timerInterval;
        let hls;
        
        function connectToStream() {
            document.getElementById('status').textContent = 'Connecting to live stream...';
            
            // Check if stream is already running
            fetch('/health')
                .then(response => response.json())
                .then(data => {
                    if (data.stream_active && data.hls_active) {
                        document.getElementById('status').textContent = 'Connected to live stream!';
                        document.getElementById('streamsContainer').style.display = 'flex';
                        setupVideoPlayers();
                        startTimer();
                        updateUrls();
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
        
        function setupVideoPlayers() {
            // Setup MP4 player
            const video = document.getElementById('videoPlayer');
            const videoInfo = document.getElementById('videoInfo');
            
            video.src = '/stream?t=' + new Date().getTime();
            
            video.addEventListener('loadstart', function() {
                videoInfo.textContent = 'Loading MP4 video...';
                console.log('MP4 video load started');
            });
            
            video.addEventListener('loadedmetadata', function() {
                videoInfo.textContent = 'MP4 metadata loaded. Duration: ' + video.duration + 's';
                console.log('MP4 metadata loaded');
            });
            
            video.addEventListener('canplay', function() {
                videoInfo.textContent = 'MP4 can play. Ready to start.';
                console.log('MP4 can play');
                video.play().catch(e => {
                    console.log('MP4 autoplay prevented:', e);
                    videoInfo.textContent = 'Click play to start MP4 video';
                });
            });
            
            video.addEventListener('playing', function() {
                videoInfo.textContent = 'MP4 video is playing!';
                console.log('MP4 video is playing');
            });
            
            video.addEventListener('error', function(e) {
                videoInfo.textContent = 'MP4 video error: ' + e.message;
                console.error('MP4 video error:', e);
            });
            
            // Setup HLS player
            const hlsVideo = document.getElementById('hlsPlayer');
            const hlsInfo = document.getElementById('hlsInfo');
            
            if (Hls.isSupported()) {
                hls = new Hls();
                hls.loadSource('/playlist.m3u8');
                hls.attachMedia(hlsVideo);
                
                hls.on(Hls.Events.MANIFEST_PARSED, function() {
                    hlsInfo.textContent = 'HLS manifest loaded';
                    console.log('HLS manifest loaded');
                    hlsVideo.play().catch(e => {
                        console.log('HLS autoplay prevented:', e);
                        hlsInfo.textContent = 'Click play to start HLS video';
                    });
                });
                
                hls.on(Hls.Events.ERROR, function(event, data) {
                    hlsInfo.textContent = 'HLS error: ' + data.details;
                    console.error('HLS error:', data);
                });
                
                hlsVideo.addEventListener('playing', function() {
                    hlsInfo.textContent = 'HLS video is playing!';
                    console.log('HLS video is playing');
                });
            } else if (hlsVideo.canPlayType('application/vnd.apple.mpegurl')) {
                // Native HLS support (Safari)
                hlsVideo.src = '/playlist.m3u8';
                hlsVideo.addEventListener('loadedmetadata', function() {
                    hlsInfo.textContent = 'HLS metadata loaded (native)';
                });
                hlsVideo.addEventListener('playing', function() {
                    hlsInfo.textContent = 'HLS video is playing! (native)';
                });
            } else {
                hlsInfo.textContent = 'HLS not supported in this browser';
            }
        }
        
        function updateUrls() {
            const baseUrl = window.location.origin;
            document.getElementById('mp4Url').textContent = baseUrl + '/stream';
            document.getElementById('hlsUrl').textContent = baseUrl + '/playlist.m3u8';
        }
        
        function copyToClipboard(elementId) {
            const element = document.getElementById(elementId);
            const text = element.textContent;
            navigator.clipboard.writeText(text).then(() => {
                const btn = element.nextElementSibling;
                const originalText = btn.textContent;
                btn.textContent = 'Copied!';
                setTimeout(() => {
                    btn.textContent = originalText;
                }, 2000);
            });
        }
        
        window.onload = function() {
            connectToStream();
        };
    </script>
</body>
</html>
"""

def start_live_stream():
    """Start both MP4 and HLS live streams"""
    global ffmpeg_process, hls_process, stream_active, hls_active
    
    try:
        if ffmpeg_process and ffmpeg_process.poll() is None:
            return True, "Stream already running"
        
        # Create HLS output directory
        os.makedirs(hls_output_dir, exist_ok=True)
        
        # Clean up any existing HLS files
        for file in glob.glob(os.path.join(hls_output_dir, '*')):
            try:
                if os.path.isfile(file):
                    os.remove(file)
            except:
                pass
        
        # Start MP4 stream process
        mp4_cmd = [
            'ffmpeg',
            '-f', 'lavfi',
            '-i', 'testsrc2=size=320x240:rate=15',
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-tune', 'zerolatency',
            '-crf', '23',
            '-pix_fmt', 'yuv420p',
            '-f', 'mp4',
            '-movflags', 'frag_keyframe+empty_moov+default_base_moof',
            '-reset_timestamps', '1',
            'pipe:1'
        ]
        
        print(f"Starting MP4 FFmpeg with command: {' '.join(mp4_cmd)}")
        
        ffmpeg_process = subprocess.Popen(
            mp4_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0
        )
        
        # Start HLS stream process
        hls_cmd = [
            'ffmpeg',
            '-f', 'lavfi',
            '-i', 'testsrc2=size=320x240:rate=15',
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-tune', 'zerolatency',
            '-crf', '23',
            '-pix_fmt', 'yuv420p',
            '-f', 'hls',
            '-hls_time', '2',
            '-hls_list_size', '3',
            '-hls_flags', 'delete_segments',
            '-hls_segment_filename', os.path.join(hls_output_dir, 'segment_%03d.ts'),
            playlist_file
        ]
        
        print(f"Starting HLS FFmpeg with command: {' '.join(hls_cmd)}")
        
        hls_process = subprocess.Popen(
            hls_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0
        )
        
        # Wait a moment to see if both start successfully
        time.sleep(3)
        
        if ffmpeg_process.poll() is not None:
            stdout, stderr = ffmpeg_process.communicate()
            error_msg = f"MP4 FFmpeg exited with code {ffmpeg_process.returncode}\nSTDOUT: {stdout.decode()}\nSTDERR: {stderr.decode()}"
            return False, error_msg
        
        if hls_process.poll() is not None:
            stdout, stderr = hls_process.communicate()
            error_msg = f"HLS FFmpeg exited with code {hls_process.returncode}\nSTDOUT: {stdout.decode()}\nSTDERR: {stderr.decode()}"
            return False, error_msg
        
        stream_active = True
        hls_active = True
        return True, "Both MP4 and HLS streams started successfully"
        
    except Exception as e:
        error_msg = f"Error starting streams: {str(e)}"
        print(error_msg)
        return False, error_msg

def stop_live_stream():
    """Stop both live streams"""
    global ffmpeg_process, hls_process, stream_active, hls_active
    
    try:
        if ffmpeg_process and ffmpeg_process.poll() is None:
            ffmpeg_process.terminate()
            ffmpeg_process.wait(timeout=5)
        
        if hls_process and hls_process.poll() is None:
            hls_process.terminate()
            hls_process.wait(timeout=5)
        
        ffmpeg_process = None
        hls_process = None
        stream_active = False
        hls_active = False
        
        # Clean up HLS files
        try:
            if os.path.exists(hls_output_dir):
                shutil.rmtree(hls_output_dir)
        except:
            pass
        
        return True, "Both streams stopped successfully"
        
    except Exception as e:
        return False, f"Error stopping streams: {e}"

def cleanup_on_exit():
    """Cleanup function for graceful shutdown"""
    stop_live_stream()
    sys.exit(0)

@app.route('/')
def index():
    """Serve the main page"""
    return render_template_string(HTML_TEMPLATE)

# Manual start/stop endpoints removed - stream runs continuously

@app.route('/stream')
def stream_video():
    """Stream the live video directly (MP4)"""
    global ffmpeg_process, stream_active
    
    if not stream_active or not ffmpeg_process or ffmpeg_process.poll() is not None:
        return jsonify({'error': 'No active MP4 stream available'}), 404
    
    def generate():
        try:
            while stream_active and ffmpeg_process and ffmpeg_process.poll() is None:
                chunk = ffmpeg_process.stdout.read(1024)
                if chunk:
                    yield chunk
                else:
                    break
        except Exception as e:
            print(f"MP4 stream error: {e}")
        finally:
            stop_live_stream()
    
    return Response(
        generate(),
        mimetype='video/mp4',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Content-Type': 'video/mp4'
        }
    )

@app.route('/playlist.m3u8')
def hls_playlist():
    """Serve the HLS playlist"""
    global hls_active
    
    if not hls_active or not os.path.exists(playlist_file):
        return jsonify({'error': 'No active HLS stream available'}), 404
    
    return send_file(playlist_file, mimetype='application/vnd.apple.mpegurl')

@app.route('/<path:filename>')
def hls_segment(filename):
    """Serve HLS segments"""
    global hls_active
    
    if not hls_active:
        return jsonify({'error': 'No active HLS stream available'}), 404
    
    file_path = os.path.join(hls_output_dir, filename)
    if not os.path.exists(file_path):
        return jsonify({'error': 'Segment not found'}), 404
    
    return send_file(file_path, mimetype='video/mp2t')

@app.route('/stream_info')
def stream_info():
    """Get stream information and URLs"""
    base_url = f"http://{os.environ.get('HOST', 'localhost')}:5000"
    
    return jsonify({
        'mp4_stream': f"{base_url}/stream",
        'hls_playlist': f"{base_url}/playlist.m3u8",
        'stream_active': stream_active,
        'hls_active': hls_active,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'ffmpeg_available': check_ffmpeg(),
        'stream_active': stream_active,
        'hls_active': hls_active,
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
    print("Live Timer Stream Server (Dual Format)")
    print("=" * 40)
    print(f"Server started at: {server_start_time}")
    print("Starting server on http://0.0.0.0:5000")
    print("Dual format - MP4 direct stream + HLS stream")
    print("Auto-starting live stream...")
    
    # Auto-start the stream when server boots up
    def auto_start_stream():
        time.sleep(2)  # Wait for server to be ready
        success, message = start_live_stream()
        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ Failed to start stream: {message}")
    
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
