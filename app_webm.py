from flask import Flask, Response, jsonify, render_template_string
import subprocess
import os
import threading
import time
from datetime import datetime
import signal
import sys

app = Flask(__name__)

# Global variables for live streaming
server_start_time = datetime.now()
ffmpeg_process = None
stream_active = False

# HTML template for the web interface
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Live Timer Stream (WebM)</title>
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
        .warning { background: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #ffc107; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⏱️ Live Timer Stream (WebM)</h1>
        <div class="info">
            <p><strong>WebM Mode:</strong> Uses WebM format for better browser compatibility.</p>
            <p><strong>Features:</strong> Moving test pattern with JavaScript timer.</p>
            <div class="warning">
                <strong>Note:</strong> This version uses WebM format which is more compatible with browsers for live streaming.
            </div>
        </div>
        <div class="controls">
            <button id="startBtn" onclick="startStream()">Start Live Stream</button>
            <button id="stopBtn" onclick="stopStream()" disabled>Stop Stream</button>
        </div>
        <div class="status" id="status">Ready to start live stream</div>
        <div class="timer-display" id="timerDisplay">00:00:00</div>
        
        <div class="video-container" id="videoContainer" style="display: none;">
            <video id="videoPlayer" autoplay muted controls>
                <source src="/stream" type="video/webm">
                Your browser does not support the video tag.
            </video>
            <div id="videoInfo" style="margin-top: 10px; font-size: 12px; color: #666;"></div>
        </div>
    </div>

    <script>
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
                        setupVideoPlayer();
                        startTimer();
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
            fetch('/stop_stream', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    document.getElementById('status').textContent = 'Stream stopped';
                    document.getElementById('videoContainer').style.display = 'none';
                    document.getElementById('startBtn').disabled = false;
                    document.getElementById('stopBtn').disabled = true;
                    stopTimer();
                });
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
        
        function setupVideoPlayer() {
            const video = document.getElementById('videoPlayer');
            const videoInfo = document.getElementById('videoInfo');
            
            // Set video source
            video.src = '/stream?t=' + new Date().getTime();
            
            // Add event listeners for debugging
            video.addEventListener('loadstart', function() {
                videoInfo.textContent = 'Loading video...';
                console.log('Video load started');
            });
            
            video.addEventListener('loadedmetadata', function() {
                videoInfo.textContent = 'Video metadata loaded. Duration: ' + video.duration + 's';
                console.log('Video metadata loaded');
            });
            
            video.addEventListener('canplay', function() {
                videoInfo.textContent = 'Video can play. Ready to start.';
                console.log('Video can play');
                video.play().catch(e => {
                    console.log('Autoplay prevented:', e);
                    videoInfo.textContent = 'Click play to start video';
                });
            });
            
            video.addEventListener('playing', function() {
                videoInfo.textContent = 'Video is playing!';
                console.log('Video is playing');
            });
            
            video.addEventListener('error', function(e) {
                videoInfo.textContent = 'Video error: ' + e.message;
                console.error('Video error:', e);
            });
            
            video.addEventListener('waiting', function() {
                videoInfo.textContent = 'Video buffering...';
                console.log('Video waiting for data');
            });
            
            video.addEventListener('stalled', function() {
                videoInfo.textContent = 'Video stalled - no data received';
                console.log('Video stalled');
            });
        }
        
        window.onload = function() {
            startStream();
        };
    </script>
</body>
</html>
"""

def start_live_stream():
    """Start the live stream with WebM format"""
    global ffmpeg_process, stream_active
    
    try:
        if ffmpeg_process and ffmpeg_process.poll() is None:
            return True, "Stream already running"
        
        # FFmpeg command for WebM streaming
        ffmpeg_cmd = [
            'ffmpeg',
            '-f', 'lavfi',
            '-i', 'testsrc2=size=320x240:rate=15',
            '-c:v', 'libvpx-vp8',  # WebM video codec
            '-b:v', '500k',  # Bitrate
            '-crf', '30',
            '-pix_fmt', 'yuv420p',
            '-f', 'webm',
            'pipe:1'
        ]
        
        print(f"Starting FFmpeg with command: {' '.join(ffmpeg_cmd)}")
        
        # Start FFmpeg process
        ffmpeg_process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0
        )
        
        # Wait a moment to see if it starts successfully
        time.sleep(2)
        
        if ffmpeg_process.poll() is not None:
            # Process exited, get error
            stdout, stderr = ffmpeg_process.communicate()
            error_msg = f"FFmpeg exited with code {ffmpeg_process.returncode}\nSTDOUT: {stdout.decode()}\nSTDERR: {stderr.decode()}"
            return False, error_msg
        
        stream_active = True
        return True, "Stream started successfully"
        
    except Exception as e:
        error_msg = f"Error starting stream: {str(e)}"
        print(error_msg)
        return False, error_msg

def stop_live_stream():
    """Stop the live stream"""
    global ffmpeg_process, stream_active
    
    try:
        if ffmpeg_process and ffmpeg_process.poll() is None:
            ffmpeg_process.terminate()
            ffmpeg_process.wait(timeout=5)
        
        ffmpeg_process = None
        stream_active = False
        
        return True, "Stream stopped successfully"
        
    except Exception as e:
        return False, f"Error stopping stream: {e}"

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
        success, message = start_live_stream()
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': message,
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
        success, message = stop_live_stream()
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': message,
                'timestamp': datetime.now().isoformat()
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/stream')
def stream_video():
    """Stream the live video directly (no files)"""
    global ffmpeg_process, stream_active
    
    if not stream_active or not ffmpeg_process or ffmpeg_process.poll() is not None:
        return jsonify({'error': 'No active stream available'}), 404
    
    def generate():
        try:
            while stream_active and ffmpeg_process and ffmpeg_process.poll() is None:
                chunk = ffmpeg_process.stdout.read(1024)
                if chunk:
                    yield chunk
                else:
                    break
        except Exception as e:
            print(f"Stream error: {e}")
        finally:
            stop_live_stream()
    
    return Response(
        generate(),
        mimetype='video/webm',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Content-Type': 'video/webm'
        }
    )

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'ffmpeg_available': check_ffmpeg(),
        'stream_active': stream_active,
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
    print("Live Timer Stream Server (WebM)")
    print("=" * 35)
    print(f"Server started at: {server_start_time}")
    print("Starting server on http://0.0.0.0:5000")
    print("WebM mode - better browser compatibility")
    
    try:
        # Start the Flask server
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\nShutting down server...")
        cleanup_on_exit()
    except Exception as e:
        print(f"Server error: {e}")
        cleanup_on_exit()
