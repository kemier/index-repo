@echo off
REM ===== CFLOW Tool - All-in-one cflow management script =====
REM Manages cflow installation, building, setup, and usage
REM Created by consolidating: build_cflow.bat, fix_cflow_build.bat, 
REM setup_cflow.bat, install_cflow_binary.bat, etc.

setlocal enabledelayedexpansion

SET SCRIPT_DIR=%~dp0
SET ROOT_DIR=%SCRIPT_DIR%..
SET CFLOW_DIR=%ROOT_DIR%\cflow-mingw
SET CFLOW_EXE=%CFLOW_DIR%\bin\cflow.exe
SET CFLOW_PREBUILD_EXE=%CFLOW_DIR%\cflow_x86-64-1.6.exe

REM Display help if no arguments or help requested
IF "%1"=="" (
    GOTO help
)
IF "%1"=="help" (
    GOTO help
)

REM ===== Command Routing =====
IF "%1"=="install" (
    GOTO install_binary
)

IF "%1"=="build" (
    GOTO build_cflow
)

IF "%1"=="fix" (
    GOTO fix_cflow
)

IF "%1"=="setup" (
    GOTO setup_cflow
)

IF "%1"=="run" (
    GOTO run_cflow
)

IF "%1"=="cleanup" (
    GOTO cleanup_cflow
)

GOTO help

REM ===== Binary Installation =====
:install_binary
echo Installing pre-built cflow binary...

REM Create directories if they don't exist
mkdir "%CFLOW_DIR%\bin" 2>nul

REM Use PowerShell to download the pre-built binary
echo Downloading pre-built cflow binary...
powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://sourceforge.net/projects/gnuwin32/files/cflow/1.4/cflow-1.4-bin.zip/download' -OutFile '%TEMP%\cflow-bin.zip'}"

if not exist "%TEMP%\cflow-bin.zip" (
    echo Failed to download cflow binary.
    exit /b 1
)

REM Extract the binary
echo Extracting cflow binary...
powershell -Command "& {Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::ExtractToDirectory('%TEMP%\cflow-bin.zip', '%TEMP%\cflow-extract')}"

REM Copy required files
echo Copying files to cflow-mingw directory...
copy "%TEMP%\cflow-extract\bin\cflow.exe" "%CFLOW_DIR%\bin\" /Y

REM Download and extract dependencies if needed
if not exist "%CFLOW_DIR%\bin\libiconv2.dll" (
    echo Downloading dependencies...
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://sourceforge.net/projects/gnuwin32/files/cflow/1.4/cflow-1.4-dep.zip/download' -OutFile '%TEMP%\cflow-dep.zip'}"
    powershell -Command "& {Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::ExtractToDirectory('%TEMP%\cflow-dep.zip', '%TEMP%\cflow-dep-extract')}"
    copy "%TEMP%\cflow-dep-extract\bin\*.dll" "%CFLOW_DIR%\bin\" /Y
)

REM Clean up temporary files
echo Cleaning up...
rmdir /S /Q "%TEMP%\cflow-extract" 2>nul
rmdir /S /Q "%TEMP%\cflow-dep-extract" 2>nul
del "%TEMP%\cflow-bin.zip" 2>nul
del "%TEMP%\cflow-dep.zip" 2>nul

REM Verify installation
if exist "%CFLOW_DIR%\bin\cflow.exe" (
    echo Installation successful. cflow.exe is available at %CFLOW_DIR%\bin\cflow.exe
    echo Make sure to update your PATH or use the full path in your analysis scripts.
) else (
    echo Installation might have encountered issues.
)

GOTO end

REM ===== Building from Source =====
:build_cflow
echo Building cflow from source...

REM Check if MSYS2 is installed
if not exist "C:\msys64\usr\bin\bash.exe" (
    echo MSYS2 is not installed. Please install it from https://www.msys2.org/
    echo or use the 'install' command to get a pre-built binary.
    exit /b 1
)

REM Create build directory if it doesn't exist
mkdir "%CFLOW_DIR%" 2>nul

REM Create build script for MSYS2
set BUILD_SCRIPT=%TEMP%\build_cflow.sh
echo Creating build script...

echo #!/bin/bash > "%BUILD_SCRIPT%"
echo set -e >> "%BUILD_SCRIPT%"
echo echo "Setting up cflow build environment..." >> "%BUILD_SCRIPT%"
echo mkdir -p /d/project/cflow-mingw >> "%BUILD_SCRIPT%"
echo cd /d/project/cflow-mingw >> "%BUILD_SCRIPT%"
echo >> "%BUILD_SCRIPT%"
echo if [ ! -d "cflow-1.6" ]; then >> "%BUILD_SCRIPT%"
echo   echo "Downloading cflow source..." >> "%BUILD_SCRIPT%"
echo   curl -L "https://ftp.gnu.org/gnu/cflow/cflow-1.6.tar.gz" -o cflow-1.6.tar.gz >> "%BUILD_SCRIPT%"
echo   tar -xzf cflow-1.6.tar.gz >> "%BUILD_SCRIPT%"
echo fi >> "%BUILD_SCRIPT%"
echo >> "%BUILD_SCRIPT%"
echo cd cflow-1.6 >> "%BUILD_SCRIPT%"
echo >> "%BUILD_SCRIPT%"
echo echo "Fixing aclocal symlink..." >> "%BUILD_SCRIPT%"
echo ACLOCAL_PATH=$(which aclocal) >> "%BUILD_SCRIPT%"
echo ln -sf "$ACLOCAL_PATH" "${ACLOCAL_PATH%%/*}/aclocal-1.15" 2>/dev/null || true >> "%BUILD_SCRIPT%"
echo >> "%BUILD_SCRIPT%"
echo echo "Building cflow..." >> "%BUILD_SCRIPT%"
echo autoreconf -i >> "%BUILD_SCRIPT%"
echo ./configure --prefix=/d/project/cflow-mingw >> "%BUILD_SCRIPT%"
echo make >> "%BUILD_SCRIPT%"
echo make install >> "%BUILD_SCRIPT%"
echo >> "%BUILD_SCRIPT%"
echo echo "Build completed successfully!" >> "%BUILD_SCRIPT%"

REM Launch MSYS2 to run the build script
echo Launching MSYS2 to build cflow...
start C:\msys64\usr\bin\bash.exe "%BUILD_SCRIPT%"

echo.
echo A MSYS2 window has been launched to build cflow.
echo After building, the cflow.exe should be at %CFLOW_DIR%\bin\cflow.exe
echo If the build fails, you can try using the 'fix' command to fix common build issues.
echo You can also use the 'install' command to get a pre-built binary.
echo.

GOTO end

REM ===== Fix cflow Build Issues =====
:fix_cflow
echo Fixing common cflow build issues...

REM Check if MSYS2 is installed
if not exist "C:\msys64\usr\bin\bash.exe" (
    echo MSYS2 is not installed. Please install it from https://www.msys2.org/
    exit /b 1
)

REM Create fix script for MSYS2
set FIX_SCRIPT=%TEMP%\fix_cflow.sh
echo Creating fix script...

echo #!/bin/bash > "%FIX_SCRIPT%"
echo set -e >> "%FIX_SCRIPT%"
echo echo "Fixing cflow build issues..." >> "%FIX_SCRIPT%"
echo cd /d/project/cflow-mingw/cflow-1.6 >> "%FIX_SCRIPT%"
echo >> "%FIX_SCRIPT%"
echo echo "Updating autotools files..." >> "%FIX_SCRIPT%"
echo touch AUTHORS NEWS README ChangeLog >> "%FIX_SCRIPT%"
echo >> "%FIX_SCRIPT%"
echo echo "Fixing aclocal version issues..." >> "%FIX_SCRIPT%"
echo sed -i 's/1\.15/1.16/g' aclocal.m4 configure.ac >> "%FIX_SCRIPT%"
echo >> "%FIX_SCRIPT%"
echo echo "Updating configuration..." >> "%FIX_SCRIPT%"
echo aclocal >> "%FIX_SCRIPT%"
echo autoconf >> "%FIX_SCRIPT%"
echo automake --add-missing >> "%FIX_SCRIPT%"
echo >> "%FIX_SCRIPT%"
echo echo "Configure and build..." >> "%FIX_SCRIPT%"
echo ./configure --prefix=/d/project/cflow-mingw >> "%FIX_SCRIPT%"
echo make >> "%FIX_SCRIPT%"
echo make install >> "%FIX_SCRIPT%"
echo >> "%FIX_SCRIPT%"
echo echo "Fix completed!" >> "%FIX_SCRIPT%"

REM Launch MSYS2 to run the fix script
echo Launching MSYS2 to fix cflow build...
start C:\msys64\usr\bin\bash.exe "%FIX_SCRIPT%"

echo.
echo A MSYS2 window has been launched to fix common cflow build issues.
echo After fixing, try the 'build' command again.
echo If issues persist, use the 'install' command to get a pre-built binary.
echo.

GOTO end

REM ===== Setup cflow for Use =====
:setup_cflow
echo Setting up cflow for the current session...

REM Find cflow executable
SET CFLOW_FOUND=0

REM Check if built cflow exists
IF EXIST "%CFLOW_EXE%" (
    SET CFLOW_TARGET=%CFLOW_EXE%
    SET CFLOW_FOUND=1
) ELSE IF EXIST "%CFLOW_PREBUILD_EXE%" (
    SET CFLOW_TARGET=%CFLOW_PREBUILD_EXE%
    SET CFLOW_FOUND=1
) ELSE (
    echo Could not find cflow executable. Please install or build cflow first.
    echo Use 'cflow_tool.bat install' or 'cflow_tool.bat build'
    exit /b 1
)

REM Create a temporary directory for the symbolic link
SET TEMP_BIN_DIR=%TEMP%\cflow_bin
echo Creating temporary directory for cflow...
IF NOT EXIST "%TEMP_BIN_DIR%" mkdir "%TEMP_BIN_DIR%"

REM Create a copy of cflow executable named just "cflow.exe"
copy "%CFLOW_TARGET%" "%TEMP_BIN_DIR%\cflow.exe" > nul

REM Add temporary directory to PATH
SET PATH=%TEMP_BIN_DIR%;%PATH%

REM Verify cflow is accessible
cflow --version 2>nul
IF %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to run cflow
    exit /b 1
)

echo Cflow is now available in your path for the current session.
GOTO end

REM ===== Run cflow Analysis =====
:run_cflow
echo Running cflow analysis...

REM Check if we have a file to analyze
IF "%2"=="" (
    echo Error: No file specified for analysis.
    echo Usage: cflow_tool.bat run file.c [options]
    exit /b 1
)

REM Setup cflow if not already set up
call :setup_cflow

REM Create output directory
SET OUTPUT_DIR=%ROOT_DIR%\docs\callgraphs
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

REM Get file name without extension
for %%F in (%2) do (
    SET FILE_NAME=%%~nF
)

REM Default options
SET CFLOW_OPTS=--number

REM Handle optional arguments
IF "%3"=="--dot" (
    SET CFLOW_OPTS=--format=dot
)

REM Run cflow
echo Running cflow on %2...
cflow %CFLOW_OPTS% %2 > "%OUTPUT_DIR%\%FILE_NAME%.txt"

REM Generate DOT output if not already
IF NOT "%3"=="--dot" (
    cflow --format=dot %2 > "%OUTPUT_DIR%\%FILE_NAME%.dot"
)

REM Try to generate PNG if graphviz is installed
where dot >nul 2>&1
IF %ERRORLEVEL% EQU 0 (
    echo Generating visualization with Graphviz...
    dot -Tpng "%OUTPUT_DIR%\%FILE_NAME%.dot" -o "%OUTPUT_DIR%\%FILE_NAME%.png"
    echo PNG image saved to %OUTPUT_DIR%\%FILE_NAME%.png
)

echo Analysis complete! Results saved to %OUTPUT_DIR%
GOTO end

REM ===== Cleanup cflow =====
:cleanup_cflow
echo Cleaning up cflow installation...

REM Remove the temporary bin directory
IF EXIST "%TEMP%\cflow_bin" (
    rmdir /S /Q "%TEMP%\cflow_bin" 2>nul
    echo Removed temporary cflow directory.
)

REM Ask about removing cflow-mingw directory
echo.
echo Do you want to remove the cflow-mingw directory? (Y/N)
set /p CONFIRM=
if /i "%CONFIRM%"=="Y" (
    RD /S /Q "%CFLOW_DIR%" 2>nul
    IF EXIST "%CFLOW_DIR%" (
        echo Directory is locked. Scheduling removal on next reboot.
        schtasks /create /tn "Remove cflow-mingw" /tr "cmd.exe /c rd /s /q \"%CFLOW_DIR%\"" /sc onstart /ru SYSTEM
        echo Directory will be removed on next system startup.
    ) ELSE (
        echo Directory has been removed successfully.
    )
)

echo Cleanup completed.
GOTO end

REM ===== Help Information =====
:help
echo.
echo CFLOW Tool - All-in-one cflow management script
echo =============================================
echo.
echo Usage: cflow_tool.bat COMMAND [options]
echo.
echo Commands:
echo   install      - Install pre-built cflow binary
echo   build        - Build cflow from source using MSYS2
echo   fix          - Fix common cflow build issues
echo   setup        - Set up cflow for the current session
echo   run FILE     - Run cflow analysis on a file
echo   cleanup      - Clean up cflow installation
echo   help         - Show this help message
echo.
echo Examples:
echo   cflow_tool.bat install
echo   cflow_tool.bat run test.c
echo   cflow_tool.bat run test.c --dot
echo.
GOTO end

:end
echo.
endlocal 