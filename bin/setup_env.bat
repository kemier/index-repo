@echo off
REM Script to set up a virtual environment using UV
echo Setting up Python virtual environment using UV...

REM Check if UV is installed
where uv >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo UV is not installed. Installing UV...
    pip install uv
)

REM Navigate to the project root
cd "%~dp0.."

REM Create a virtual environment if it doesn't exist
if not exist .venv (
    echo Creating virtual environment...
    uv venv .venv
) else (
    echo Virtual environment already exists.
)

REM Activate the virtual environment and install dependencies
echo Installing dependencies from uv-requirements.txt...
call .venv\Scripts\activate.bat
uv pip install -r uv-requirements.txt

echo.
echo Environment setup complete. To activate the environment, run:
echo call .venv\Scripts\activate.bat
echo.
pause 