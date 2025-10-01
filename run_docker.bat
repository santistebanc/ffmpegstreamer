@echo off
echo FFmpeg Live Timer Stream - Docker Management
echo ============================================

:menu
echo.
echo Choose an option:
echo 1. Test FFmpeg locally (without Docker)
echo 2. Build Docker image
echo 3. Run Docker container
echo 4. Stop Docker container
echo 5. View Docker logs
echo 6. Clean up Docker resources
echo 7. Exit
echo.
set /p choice="Enter your choice (1-7): "

if "%choice%"=="1" goto test_local
if "%choice%"=="2" goto build
if "%choice%"=="3" goto run
if "%choice%"=="4" goto stop
if "%choice%"=="5" goto logs
if "%choice%"=="6" goto cleanup
if "%choice%"=="7" goto exit
goto menu

:test_local
echo.
echo Testing FFmpeg locally...
python test_local.py
pause
goto menu

:build
echo.
echo Building Docker image...
docker build -t ffmpeg-streamer .
if %errorlevel% neq 0 (
    echo Error building Docker image. Make sure Docker Desktop is running.
    pause
    goto menu
)
echo Docker image built successfully!
pause
goto menu

:run
echo.
echo Starting Docker container...
docker run -d --name ffmpeg-streamer -p 5000:5000 ffmpeg-streamer
if %errorlevel% neq 0 (
    echo Error starting container. Container might already be running.
    echo Try stopping it first or use: docker rm ffmpeg-streamer
    pause
    goto menu
)
echo Container started! Access the live timer stream at http://localhost:5000
pause
goto menu

:stop
echo.
echo Stopping Docker container...
docker stop ffmpeg-streamer
docker rm ffmpeg-streamer
echo Container stopped and removed.
pause
goto menu

:logs
echo.
echo Showing Docker logs...
docker logs ffmpeg-streamer
pause
goto menu

:cleanup
echo.
echo Cleaning up Docker resources...
docker stop ffmpeg-streamer 2>nul
docker rm ffmpeg-streamer 2>nul
docker rmi ffmpeg-streamer 2>nul
echo Cleanup complete.
pause
goto menu

:exit
echo.
echo Goodbye!
exit
