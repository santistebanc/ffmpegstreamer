const { createCanvas, loadImage } = require('canvas');
const express = require('express');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

// Create a canvas for rendering
const canvas = createCanvas(1920, 1080);
const ctx = canvas.getContext('2d');

// Animation variables
let time = 0;
let startTime = Date.now();

// Animation loop
function animate() {
    time += 0.016; // ~60fps
    
    // Clear canvas
    ctx.fillStyle = '#000000';
    ctx.fillRect(0, 0, 1920, 1080);
    
    // Draw animated square
    const squareSize = 400;
    const centerX = 200 + 200 * Math.cos(time * 2 * Math.PI / 5);
    const centerY = 200 + 200 * Math.sin(time * 2 * Math.PI / 5);
    
    ctx.fillStyle = 'rgba(255, 0, 0, 0.8)';
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
    ctx.fillText('HD Quality with Canvas', 40, 280);
    
    // Get canvas data and send to FFmpeg
    const imageData = canvas.toDataURL('image/png');
    
    // Convert base64 to buffer
    const base64Data = imageData.replace(/^data:image\/png;base64,/, '');
    const buffer = Buffer.from(base64Data, 'base64');
    
    // Send to FFmpeg if process exists
    if (ffmpegProcess && !ffmpegProcess.killed) {
        ffmpegProcess.stdin.write(buffer);
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
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-tune', 'zerolatency',
        '-crf', '18',
        '-maxrate', '4M',
        '-bufsize', '8M',
        '-g', '60',
        '-keyint_min', '60',
        '-sc_threshold', '0',
        '-f', 'hls',
        '-hls_time', '6',
        '-hls_list_size', '10',
        '-hls_flags', 'delete_segments',
        '-hls_segment_filename', '/app/hls/segment_%03d.ts',
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
    });
    
    ffmpegProcess.on('error', (err) => {
        console.error('FFmpeg process error:', err);
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