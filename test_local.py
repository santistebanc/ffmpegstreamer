#!/usr/bin/env python3
"""
Test script to verify FFmpeg functionality locally before Docker deployment
"""
import subprocess
import sys
import os

def check_ffmpeg():
    """Check if FFmpeg is available and working"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("SUCCESS: FFmpeg is available")
            print(f"Version: {result.stdout.split('ffmpeg version')[1].split()[0] if 'ffmpeg version' in result.stdout else 'Unknown'}")
            return True
        else:
            print("ERROR: FFmpeg command failed")
            return False
    except FileNotFoundError:
        print("ERROR: FFmpeg not found in PATH")
        return False
    except subprocess.TimeoutExpired:
        print("ERROR: FFmpeg command timed out")
        return False
    except Exception as e:
        print(f"ERROR: Error checking FFmpeg: {e}")
        return False

def test_hls_stream():
    """Test HLS streaming with FFmpeg"""
    try:
        print("\nTesting HLS stream generation...")
        
        # Create test HLS output directory
        test_hls_dir = "test_hls"
        os.makedirs(test_hls_dir, exist_ok=True)
        
        # Create a simple test HLS stream (6 seconds = 3 segments)
        cmd = [
            'ffmpeg',
            '-f', 'lavfi',
            '-i', 'testsrc2=size=320x240:rate=30',
            '-vf', 
            'drawbox=x=50+50*cos(t*2*PI/3):y=50+50*sin(t*2*PI/3):w=50:h=50:color=red@0.8:t=fill,'
            'drawtext=text=\'Test HLS Timer\':x=10:y=30:fontsize=20:color=white,'
            'drawtext=text=\'%{pts\\:hms}\':x=10:y=60:fontsize=24:color=yellow',
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-tune', 'zerolatency',
            '-crf', '23',
            '-pix_fmt', 'yuv420p',
            '-f', 'hls',
            '-hls_time', '2',  # 2-second segments
            '-hls_list_size', '3',  # Keep 3 segments
            '-hls_flags', 'delete_segments+independent_segments',
            '-hls_segment_filename', os.path.join(test_hls_dir, 'segment_%03d.ts'),
            '-t', '6',  # 6 seconds total
            os.path.join(test_hls_dir, 'playlist.m3u8')
        ]
        
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("SUCCESS: HLS stream test successful!")
            
            # Check if playlist and segments were created
            playlist_path = os.path.join(test_hls_dir, 'playlist.m3u8')
            if os.path.exists(playlist_path):
                print(f"Playlist created: {playlist_path}")
                
                # Count segments
                segments = [f for f in os.listdir(test_hls_dir) if f.endswith('.ts')]
                print(f"Segments created: {len(segments)}")
                
                # Clean up test files
                import shutil
                shutil.rmtree(test_hls_dir)
                
                return True
            else:
                print("ERROR: Playlist file not created")
                return False
        else:
            print(f"ERROR: HLS stream test failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("ERROR: HLS stream test timed out")
        return False
    except Exception as e:
        print(f"ERROR: Error during HLS stream test: {e}")
        return False

def main():
    print("FFmpeg HLS Live Stream Test")
    print("=" * 40)
    
    # Check FFmpeg availability
    if not check_ffmpeg():
        print("\nTo install FFmpeg on Windows:")
        print("1. Download from https://ffmpeg.org/download.html")
        print("2. Or use chocolatey: choco install ffmpeg")
        print("3. Or use winget: winget install FFmpeg")
        print("4. Make sure FFmpeg is in your PATH")
        return False
    
    # Test HLS stream generation
    if test_hls_stream():
        print("\nAll tests passed! Your system is ready for Docker deployment.")
        print("\nNext steps:")
        print("1. Start Docker Desktop")
        print("2. Run: docker build -t ffmpeg-streamer .")
        print("3. Run: docker run -p 5000:5000 ffmpeg-streamer")
        print("4. Open http://localhost:5000 in your browser")
        print("5. The HLS live stream will show a timer counting up from server start time")
        return True
    else:
        print("\nHLS stream test failed. Please check FFmpeg installation.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
