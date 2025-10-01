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
        <h1>⏱️ Live Timer Stream</h1>
        <div class="info">
            <p><strong>Live Stream:</strong> This server streams a live video showing a timer that counts up from when the server started.</p>
            <p><strong>Features:</strong> Real-time timer display with a moving square background animation.</p>
            <div class="hls-info">
                <strong>HLS Streaming:</strong> Using HTTP Live Streaming (HLS) format for better compatibility and adaptive bitrate streaming.
            </div>
        </div>
        <div class="controls">
            <button id="startBtn" onclick="startStream()">Start Live Stream</button>
            <button id="stopBtn" onclick="stopStream()" disabled>Stop Stream</button>
        </div>
        <div class="status" id="status">Ready to start live stream</div>
        <div class="timer-display" id="timerDisplay">00:00:00</div>
        
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
        
        function startStream() {
            document.getElementById('status').textContent = 'Starting live stream...';
            document.getElementById('startBtn').disabled = true;
            document.getElementById('stopBtn').disabled = false;
            
            fetch('/start_stream', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('status').textContent = 'Live stream started!';
                        document.getElementById('videoContainer').style.display = 'block';
                        initializeHLS();
                        startTimer();
                        loadStreamInfo();
                    } else {
                        document.getElementById('status').textContent = 'Error: ' + data.error;
                        document.getElementById('startBtn').disabled = false;
                        document.getElementById('stopBtn').disabled = true;
                    }
                })
                .catch(error => {
                    document.getElementById('status').textContent = 'Error: ' + error.message;
                    document.getElementById('startBtn').disabled = false;
                    document.getElementById('stopBtn').disabled = true;
                });
        }
        
        function stopStream() {
            if (hls) {
                hls.destroy();
                hls = null;
            }
            
            fetch('/stop_stream', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    document.getElementById('status').textContent = 'Stream stopped';
                    document.getElementById('videoContainer').style.display = 'none';
                    document.getElementById('streamUrlSection').style.display = 'none';
                    document.getElementById('startBtn').disabled = false;
                    document.getElementById('stopBtn').disabled = true;
                    stopTimer();
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
        }
        
        function stopTimer() {
            if (timerInterval) {
                clearInterval(timerInterval);
                timerInterval = null;
            }
        }
        
        // Auto-start stream on page load
        window.onload = function() {
            startStream();
        };
    </script>
</body>
</html>
"""

def start_live_stream():
    """Start the live stream with FFmpeg generating HLS segments"""
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
        
        # FFmpeg command for HLS live streaming with timer
        ffmpeg_cmd = [
            'ffmpeg',
            '-f', 'lavfi',
            '-i', 'testsrc2=size=640x480:rate=30',
            '-vf', 
            'drawbox=x=50+50*cos(t*2*PI/5):y=50+50*sin(t*2*PI/5):w=100:h=100:color=red@0.8:t=fill,'
            'drawtext=text=\'Server Uptime\':x=10:y=30:fontsize=24:color=white:fontfile=/usr/share/fonts/ttf-dejavu/DejaVuSans-Bold.ttf,'
            'drawtext=text=\'%{pts\\:hms}\':x=10:y=60:fontsize=32:color=yellow:fontfile=/usr/share/fonts/ttf-dejavu/DejaVuSans-Bold.ttf,'
            'drawtext=text=\'HLS Live Stream\':x=10:y=100:fontsize=20:color=cyan:fontfile=/usr/share/fonts/ttf-dejavu/DejaVuSans-Bold.ttf',
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-tune', 'zerolatency',
            '-crf', '23',
            '-pix_fmt', 'yuv420p',
            '-f', 'hls',
            '-hls_time', '2',  # 2-second segments
            '-hls_list_size', '5',  # Keep 5 segments in playlist
            '-hls_flags', 'delete_segments+independent_segments',
            '-hls_segment_filename', os.path.join(hls_output_dir, 'segment_%03d.ts'),
            playlist_file
        ]
        
        # Start FFmpeg process
        ffmpeg_process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0
        )
        
        stream_active = True
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

@app.route('/start_stream', methods=['POST'])
def start_stream():
    """Start the live stream"""
    try:
        if start_live_stream():
            return jsonify({
                'success': True,
                'message': 'Live stream started successfully',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to start live stream',
                'timestamp': datetime.now().isoformat()
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/stop_stream', methods=['POST'])
def stop_stream():
    """Stop the live stream"""
    try:
        if stop_live_stream():
            return jsonify({
                'success': True,
                'message': 'Live stream stopped successfully',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to stop live stream',
                'timestamp': datetime.now().isoformat()
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/playlist.m3u8')
def serve_playlist():
    """Serve the HLS playlist"""
    if not stream_active or not os.path.exists(playlist_file):
        return jsonify({'error': 'No active stream available'}), 404
    
    return send_file(
        playlist_file,
        mimetype='application/vnd.apple.mpegurl',
        headers={
            'Cache-Control': 'no-cache',
            'Access-Control-Allow-Origin': '*'
        }
    )

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
    
    return send_file(
        file_path,
        mimetype=mimetype,
        headers={
            'Cache-Control': 'no-cache',
            'Access-Control-Allow-Origin': '*'
        }
    )

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
    print("Live Timer Stream Server")
    print("=" * 30)
    print(f"Server started at: {server_start_time}")
    print("Starting server on http://0.0.0.0:5000")
    print("The live stream will show a timer counting up from server start time")
    print("Press Ctrl+C to stop the server")
    
    try:
        # Start the Flask server
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\nShutting down server...")
        cleanup_on_exit()
    except Exception as e:
        print(f"Server error: {e}")
        cleanup_on_exit()
