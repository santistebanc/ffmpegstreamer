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
hls_output_dir = "/tmp/hls"
playlist_file = os.path.join(hls_output_dir, "playlist.m3u8")

# HTML template for the web interface
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Live Timer Stream (Debug)</title>
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
        .debug-info { background: #f8d7da; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #dc3545; }
        .debug-info pre { background: #f8f9fa; padding: 10px; border-radius: 3px; overflow-x: auto; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⏱️ Live Timer Stream (Debug Mode)</h1>
        <div class="info">
            <p><strong>Debug Mode:</strong> This version provides detailed error information to help troubleshoot issues.</p>
        </div>
        <div class="controls">
            <button id="startBtn" onclick="startStream()">Start Live Stream</button>
            <button id="stopBtn" onclick="stopStream()" disabled>Stop Stream</button>
            <button onclick="checkSystem()">Check System</button>
        </div>
        <div class="status" id="status">Ready to start live stream</div>
        <div class="debug-info" id="debugInfo" style="display: none;">
            <h4>Debug Information:</h4>
            <pre id="debugText">Click "Check System" to see debug info</pre>
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
                    } else {
                        document.getElementById('status').textContent = 'Error: ' + data.error;
                        document.getElementById('debugText').textContent = data.debug_info || 'No debug info available';
                        document.getElementById('debugInfo').style.display = 'block';
                        document.getElementById('startBtn').disabled = false;
                        document.getElementById('stopBtn').disabled = true;
                    }
                })
                .catch(error => {
                    document.getElementById('status').textContent = 'Error: ' + error.message;
                    document.getElementById('debugText').textContent = 'Network error: ' + error.message;
                    document.getElementById('debugInfo').style.display = 'block';
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
                    document.getElementById('startBtn').disabled = false;
                    document.getElementById('stopBtn').disabled = true;
                    stopTimer();
                });
        }
        
        function checkSystem() {
            fetch('/debug_info')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('debugText').textContent = JSON.stringify(data, null, 2);
                    document.getElementById('debugInfo').style.display = 'block';
                })
                .catch(error => {
                    document.getElementById('debugText').textContent = 'Error fetching debug info: ' + error.message;
                    document.getElementById('debugInfo').style.display = 'block';
                });
        }
        
        function initializeHLS() {
            const video = document.getElementById('videoPlayer');
            const videoSrc = '/playlist.m3u8';
            
            if (Hls.isSupported()) {
                hls = new Hls({
                    debug: true,  // Enable debug mode
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
                    document.getElementById('debugText').textContent = 'HLS Error: ' + JSON.stringify(data, null, 2);
                    document.getElementById('debugInfo').style.display = 'block';
                });
            } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
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
    </script>
</body>
</html>
"""

def check_ffmpeg():
    """Check if FFmpeg is available and get version info"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            return True, version_line
        else:
            return False, f"FFmpeg error: {result.stderr}"
    except FileNotFoundError:
        return False, "FFmpeg not found in PATH"
    except subprocess.TimeoutExpired:
        return False, "FFmpeg command timed out"
    except Exception as e:
        return False, f"Error checking FFmpeg: {e}"

def check_system():
    """Check system information"""
    info = {
        'python_version': sys.version,
        'platform': sys.platform,
        'current_directory': os.getcwd(),
        'hls_output_dir': hls_output_dir,
        'hls_output_exists': os.path.exists(hls_output_dir),
        'hls_output_writable': os.access(hls_output_dir, os.W_OK) if os.path.exists(hls_output_dir) else False,
        'playlist_file': playlist_file,
        'playlist_exists': os.path.exists(playlist_file),
        'ffmpeg_available': False,
        'ffmpeg_version': 'Unknown'
    }
    
    # Check FFmpeg
    ffmpeg_ok, ffmpeg_info = check_ffmpeg()
    info['ffmpeg_available'] = ffmpeg_ok
    info['ffmpeg_version'] = ffmpeg_info
    
    # Check if we can create the HLS directory
    try:
        os.makedirs(hls_output_dir, exist_ok=True)
        info['hls_directory_created'] = True
    except Exception as e:
        info['hls_directory_created'] = False
        info['hls_directory_error'] = str(e)
    
    return info

def start_live_stream():
    """Start the live stream with FFmpeg generating HLS segments"""
    global ffmpeg_process, stream_active
    
    try:
        if ffmpeg_process and ffmpeg_process.poll() is None:
            return True, "Stream already running"
        
        # Create HLS output directory
        os.makedirs(hls_output_dir, exist_ok=True)
        
        # Clean up old segments
        for file in glob.glob(os.path.join(hls_output_dir, "*.ts")):
            os.remove(file)
        if os.path.exists(playlist_file):
            os.remove(playlist_file)
        
        # Simple FFmpeg command without fonts first
        ffmpeg_cmd = [
            'ffmpeg',
            '-f', 'lavfi',
            '-i', 'testsrc2=size=640x480:rate=30',
            '-vf', 
            'drawbox=x=50+50*cos(t*2*PI/5):y=50+50*sin(t*2*PI/5):w=100:h=100:color=red@0.8:t=fill,'
            'drawtext=text=\'Server Uptime\':x=10:y=30:fontsize=24:color=white,'
            'drawtext=text=\'%{pts\\:hms}\':x=10:y=60:fontsize=32:color=yellow,'
            'drawtext=text=\'HLS Live Stream\':x=10:y=100:fontsize=20:color=cyan',
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-tune', 'zerolatency',
            '-crf', '23',
            '-pix_fmt', 'yuv420p',
            '-f', 'hls',
            '-hls_time', '2',
            '-hls_list_size', '5',
            '-hls_flags', 'delete_segments+independent_segments',
            '-hls_segment_filename', os.path.join(hls_output_dir, 'segment_%03d.ts'),
            playlist_file
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

@app.route('/debug_info')
def debug_info():
    """Get detailed debug information"""
    return jsonify(check_system())

@app.route('/start_stream', methods=['POST'])
def start_stream():
    """Start the live stream"""
    try:
        success, message = start_live_stream()
        debug_info = check_system()
        
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
                'debug_info': debug_info,
                'timestamp': datetime.now().isoformat()
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'debug_info': check_system(),
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

@app.route('/health')
def health_check():
    """Health check endpoint"""
    playlist_exists = os.path.exists(playlist_file) if stream_active else False
    segment_count = len(glob.glob(os.path.join(hls_output_dir, "*.ts"))) if stream_active else 0
    
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'ffmpeg_available': check_ffmpeg()[0],
        'stream_active': stream_active,
        'hls_playlist_exists': playlist_exists,
        'hls_segment_count': segment_count,
        'server_uptime': str(datetime.now() - server_start_time),
        'debug_info': check_system()
    })

# Register signal handlers for graceful shutdown
signal.signal(signal.SIGINT, lambda s, f: cleanup_on_exit())
signal.signal(signal.SIGTERM, lambda s, f: cleanup_on_exit())

if __name__ == '__main__':
    print("Live Timer Stream Server (Debug Mode)")
    print("=" * 45)
    print(f"Server started at: {server_start_time}")
    print("Starting server on http://0.0.0.0:5000")
    print("Debug mode enabled - check /debug_info for system status")
    
    # Print system info on startup
    debug_info = check_system()
    print("\nSystem Information:")
    for key, value in debug_info.items():
        print(f"  {key}: {value}")
    
    try:
        # Start the Flask server
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\nShutting down server...")
        cleanup_on_exit()
    except Exception as e:
        print(f"Server error: {e}")
        cleanup_on_exit()
