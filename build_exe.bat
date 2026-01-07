@echo off
setlocal EnableExtensions

REM ======================================================
REM Build exe via PyInstaller
REM - Uses the .spec file if present
REM - If .spec is missing (e.g. cleaned manually), regenerates it
REM ======================================================

REM Ensure we run in the directory of this script
cd /d "%~dp0"

echo Using project directory: %cd%

python -m pip install -U pyinstaller

if exist "image_to_video_converter.spec" (
  echo Building with spec: image_to_video_converter.spec
  pyinstaller -y "image_to_video_converter.spec"
) else (
  echo Spec not found. Generating a new one...
  pyinstaller -y --noconsole --name "image_to_video_converter" "image_to_video_converter.py"
)

echo.
echo Build finished.
echo Output (onedir): dist\image_to_video_converter\image_to_video_converter.exe
echo If you built onefile previously, the path may differ.
pause
