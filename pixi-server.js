const { createCanvas, loadImage } = require('canvas');
const express = require('express');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

// Process lock to ensure only one instance runs
const LOCK_FILE = '/app/canvas-server.lock';
const PID_FILE = '/app/canvas-server.pid';

// Check if another instance is already running
if (fs.existsSync(LOCK_FILE)) {
    try {
        const existingPid = fs.readFileSync(PID_FILE, 'utf8').trim();
        // Check if the process is actually running
        try {
            process.kill(existingPid, 0); // Signal 0 just checks if process exists
            console.log('Canvas server is already running (PID: ' + existingPid + '). Exiting...');
            process.exit(1);
        } catch (err) {
            // Process doesn't exist, remove stale lock files
            console.log('Removing stale lock files...');
            if (fs.existsSync(LOCK_FILE)) fs.unlinkSync(LOCK_FILE);
            if (fs.existsSync(PID_FILE)) fs.unlinkSync(PID_FILE);
        }
    } catch (err) {
        // PID file doesn't exist or is invalid, remove lock file
        if (fs.existsSync(LOCK_FILE)) fs.unlinkSync(LOCK_FILE);
    }
}

// Create lock file and write PID
fs.writeFileSync(LOCK_FILE, 'locked');
fs.writeFileSync(PID_FILE, process.pid.toString());

// Cleanup on exit
process.on('exit', () => {
    if (fs.existsSync(LOCK_FILE)) {
        fs.unlinkSync(LOCK_FILE);
    }
    if (fs.existsSync(PID_FILE)) {
        fs.unlinkSync(PID_FILE);
    }
});

process.on('SIGINT', () => {
    console.log('Canvas server shutting down...');
    process.exit(0);
});

process.on('SIGTERM', () => {
    console.log('Canvas server shutting down...');
    process.exit(0);
});

// Create a canvas for rendering
const canvas = createCanvas(1920, 1080);
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
    ctx.fillRect(0, 0, 1920, 1080);
    
    // Draw animated square with random color
    const squareSize = 400;
    const centerX = 200 + 200 * Math.cos(time * 2 * Math.PI / 5);
    const centerY = 200 + 200 * Math.sin(time * 2 * Math.PI / 5);
    
    ctx.fillStyle = randomColor;
    ctx.fillRect(centerX, centerY, squareSize, squareSize);
    
    // Draw text overlays
    ctx.fillStyle = '#FFFFFF';
    ctx.font = '48px Arial';
    ctx.fillText('PixiJS Live Stream', 40, 80);
    
    // Update timer text
    const elapsed = (Date.now() - startTime) / 1000;
    const hours = Math.floor(elapsed / 3600);
    const minutes = Math.floor((elapsed % 3600) / 60);
    const seconds = Math.floor(elapsed % 60);
    
    const timerText = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    
    ctx.fillStyle = '#FFFF00';
    ctx.font = '64px Arial';
    ctx.fillText(timerText, 40, 140);
    
    ctx.fillStyle = '#00FFFF';
    ctx.font = '36px Arial';
    ctx.fillText('Server-Side Rendering', 40, 220);
    
    ctx.fillStyle = '#00FF00';
    ctx.font = '28px Arial';
    ctx.fillText('HD Quality with Canvas - Color: ' + randomColor, 40, 280);
    
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

// FFmpeg process
let ffmpegProcess = null;

function startFFmpeg() {
    const ffmpegArgs = [
        '-f', 'image2pipe',
        '-vcodec', 'png',
        '-r', '30',
        '-i', 'pipe:0',
        '-f', 'lavfi',
        '-i', 'anullsrc=channel_layout=stereo:sample_rate=48000',
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-tune', 'zerolatency',
        '-crf', '23',
        '-maxrate', '2M',
        '-bufsize', '2M',
        '-g', '15',
        '-keyint_min', '15',
        '-sc_threshold', '0',
        '-profile:v', 'baseline',
        '-level', '3.0',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac',
        '-b:a', '64k',
        '-ar', '48000',
        '-ac', '2',
        '-f', 'hls',
        '-hls_time', '1',
        '-hls_list_size', '3',
        '-hls_flags', 'delete_segments+independent_segments',
        '-hls_segment_type', 'mpegts',
        '-hls_segment_filename', '/app/hls/segment_%03d.ts',
        '-hls_start_number_source', 'datetime',
        '/app/hls/playlist.m3u8'
    ];
    
    ffmpegProcess = spawn('ffmpeg', ffmpegArgs, {
        stdio: ['pipe', 'pipe', 'pipe']
    });
    
    ffmpegProcess.stderr.on('data', (data) => {
        console.log('FFmpeg stderr:', data.toString());
    });
    
    ffmpegProcess.on('close', (code) => {
        console.log(`FFmpeg process exited with code ${code}`);
        ffmpegProcess = null;
        if (animationFrameId) {
            clearInterval(animationFrameId);
            animationFrameId = null;
        }
    });
    
    ffmpegProcess.on('error', (err) => {
        console.error('FFmpeg process error:', err);
        ffmpegProcess = null;
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
}

// Create HLS directory
const hlsDir = '/app/hls';
if (!fs.existsSync(hlsDir)) {
    fs.mkdirSync(hlsDir, { recursive: true });
}

// Start FFmpeg
startFFmpeg();

// Start animation loop
setInterval(animate, 16); // ~60fps

console.log('Canvas server started with FFmpeg streaming');
console.log('Stream available at: http://localhost:5000/playlist.m3u8');