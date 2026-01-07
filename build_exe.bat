@echo off
setlocal

REM Use the current Python environment to build the exe.
REM IMPORTANT: Tkinter is not a pip package. If your Python does not include Tk/Tcl,
REM the built exe will fail with: No module named 'tkinter'.

python -m pip install -U pyinstaller

REM Build using spec (includes runtime hook for Tcl/Tk discovery)
pyinstaller -y image_to_video_converter.spec

echo.
echo Build finished. Output: dist\image_to_video_converter.exe
pause
