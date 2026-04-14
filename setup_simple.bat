@echo off
echo Creating new virtual environment...

REM Create virtual environment
C:\Python38\python.exe -m venv venv_clean

if exist venv_clean\Scripts\python.exe (
    echo SUCCESS: Virtual environment created!
    
    REM Activate and install dependencies
    echo Installing dependencies...
    venv_clean\Scripts\pip.exe install pylsl pandas matplotlib openpyxl numpy
    
    echo Verifying pylsl installation...
    venv_clean\Scripts\python.exe -c "import pylsl; print('pylsl version:', pylsl.library_version())"
    
    echo.
    echo ENVIRONMENT READY!
    echo To use: venv_clean\Scripts\activate
    pause
) else (
    echo FAILED: Could not create virtual environment
    pause
)