#!/usr/bin/env python3
"""
Test script to verify stream URL functionality
"""
import requests
import json
import time

def test_stream_info():
    """Test the stream info endpoint"""
    try:
        print("Testing stream info endpoint...")
        
        # Test stream info endpoint
        response = requests.get('http://localhost:5000/stream_info', timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print("SUCCESS: Stream info endpoint working!")
            print(f"Stream active: {data.get('stream_active', False)}")
            print(f"Playlist exists: {data.get('playlist_exists', False)}")
            print(f"Segment count: {data.get('segment_count', 0)}")
            
            if 'stream_urls' in data:
                urls = data['stream_urls']
                print(f"Playlist URL: {urls.get('playlist_url', 'N/A')}")
                print(f"Localhost URL: {urls.get('localhost_url', 'N/A')}")
            
            if 'instructions' in data:
                print("\nInstructions available for:")
                for app, instruction in data['instructions'].items():
                    print(f"  {app.upper()}: {instruction}")
            
            return True
        else:
            print(f"ERROR: HTTP {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to server. Make sure the server is running on localhost:5000")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_playlist_access():
    """Test direct access to playlist file"""
    try:
        print("\nTesting playlist access...")
        
        response = requests.get('http://localhost:5000/playlist.m3u8', timeout=5)
        
        if response.status_code == 200:
            print("SUCCESS: Playlist accessible!")
            print(f"Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
            print(f"Content length: {len(response.content)} bytes")
            
            # Check if it's a valid M3U8 file
            content = response.text
            if '#EXTM3U' in content:
                print("SUCCESS: Valid M3U8 playlist format!")
                return True
            else:
                print("WARNING: Content doesn't look like a valid M3U8 playlist")
                return False
        else:
            print(f"ERROR: HTTP {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to server")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def main():
    print("Stream URL Test")
    print("=" * 30)
    print("Make sure the server is running: docker run -p 5000:5000 ffmpeg-streamer")
    print("Then start the stream from the web interface at http://localhost:5000")
    print()
    
    # Test stream info
    if test_stream_info():
        print("\n" + "="*50)
        # Test playlist access
        test_playlist_access()
        
        print("\n" + "="*50)
        print("Stream URL test completed!")
        print("\nTo test with external players:")
        print("1. VLC: Media → Open Network Stream → Enter the playlist URL")
        print("2. ffplay: ffplay http://localhost:5000/playlist.m3u8")
        print("3. Browser: Open http://localhost:5000/playlist.m3u8 directly")
    else:
        print("Stream info test failed. Please check server status.")

if __name__ == "__main__":
    main()
