@echo off
setlocal EnableExtensions

REM ===============================
REM Clean previous build artifacts
REM ===============================
echo [0/3] Cleaning previous build cache...
if exist build (
  rmdir /s /q build
)
if exist dist (
  rmdir /s /q dist
)
if exist image_to_video_converter.spec (
  del /f /q image_to_video_converter.spec
)

echo [1/3] Creating venv...
if not exist .venv (
  python -m venv .venv
)

echo [2/3] Installing PyInstaller...
call .venv\Scripts\python.exe -m pip install --upgrade pip
call .venv\Scripts\python.exe -m pip install --upgrade pyinstaller

echo [3/3] Building EXE...
call .venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --windowed --onefile image_to_video_converter.py

echo.
echo Done. EXE is in: dist\image_to_video_converter.exe
pause

