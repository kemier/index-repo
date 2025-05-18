@echo off
REM ===== Cleanup Tool - All-in-one cleanup script =====
REM Manages project cleanup including dependencies, cflow, and directories
REM Created by consolidating: cleanup_dependencies.bat, cleanup_cflow.bat, 
REM final_cleanup.bat, etc.

setlocal enabledelayedexpansion

SET SCRIPT_DIR=%~dp0
SET ROOT_DIR=%SCRIPT_DIR%..

REM Display help if no arguments or help requested
IF "%1"=="" (
    GOTO help
)
IF "%1"=="help" (
    GOTO help
)

REM ===== Command Routing =====
IF "%1"=="cflow" (
    GOTO cleanup_cflow
)

IF "%1"=="deps" (
    GOTO cleanup_dependencies
)

IF "%1"=="temp" (
    GOTO cleanup_temp
)

IF "%1"=="organize" (
    GOTO organize_files
)

IF "%1"=="all" (
    GOTO cleanup_all
)

GOTO help

REM ===== Cleanup cflow =====
:cleanup_cflow
echo Cleaning up cflow installation...

REM Remove the temporary bin directory
SET TEMP_BIN_DIR=%TEMP%\cflow_bin
IF EXIST "%TEMP_BIN_DIR%" (
    rmdir /S /Q "%TEMP_BIN_DIR%" 2>nul
    echo Removed temporary cflow directory.
)

REM Try to remove cflow-mingw directory
echo Removing cflow-mingw directory...
RD /S /Q "%ROOT_DIR%\cflow-mingw" 2>nul
IF EXIST "%ROOT_DIR%\cflow-mingw" (
    echo Directory is locked. Scheduling removal on next reboot.
    PING 127.0.0.1 -n 2 > nul
    RD /S /Q "%ROOT_DIR%\cflow-mingw" 2>nul
)

IF EXIST "%ROOT_DIR%\cflow-mingw" (
    echo Still locked. Adding to scheduled tasks.
    schtasks /create /tn "Remove cflow-mingw" /tr "cmd.exe /c rd /s /q \"%ROOT_DIR%\cflow-mingw\"" /sc onstart /ru SYSTEM
    echo Directory will be removed on next system startup.
) ELSE (
    echo Directory has been removed successfully.
)

echo.
echo Cflow cleanup completed.
GOTO end

REM ===== Cleanup External Dependencies =====
:cleanup_dependencies
echo Cleaning up external dependency directories...

REM Try to remove neo4j directory
echo Removing neo4j directory...
RD /S /Q "%ROOT_DIR%\neo4j" 2>nul
IF EXIST "%ROOT_DIR%\neo4j" (
    echo - Neo4j directory is locked. Scheduling removal on next reboot.
    schtasks /create /tn "Remove Neo4j" /tr "cmd.exe /c rd /s /q \"%ROOT_DIR%\neo4j\"" /sc onstart /ru SYSTEM
) ELSE (
    echo - Neo4j directory has been removed successfully.
)

REM Try to remove folly directory
echo Removing folly directory...
RD /S /Q "%ROOT_DIR%\folly" 2>nul
IF EXIST "%ROOT_DIR%\folly" (
    echo - Folly directory is locked. Scheduling removal on next reboot.
    schtasks /create /tn "Remove Folly" /tr "cmd.exe /c rd /s /q \"%ROOT_DIR%\folly\"" /sc onstart /ru SYSTEM
) ELSE (
    echo - Folly directory has been removed successfully.
)

REM Ask about removing virtual environment
echo.
echo Do you want to remove the virtual environment (.venv directory)? (Y/N)
set /p CONFIRM=
if /i "%CONFIRM%"=="Y" (
    echo Removing virtual environment...
    RD /S /Q "%ROOT_DIR%\.venv" 2>nul
    IF EXIST "%ROOT_DIR%\.venv" (
        echo - Virtual environment is locked. Please close any active processes and try again.
    ) ELSE (
        echo - Virtual environment has been removed successfully.
    )
)

echo.
echo Dependencies cleanup completed.
GOTO end

REM ===== Cleanup Temporary Files =====
:cleanup_temp
echo Cleaning up temporary files and directories...

REM Remove Python cache directories
echo Removing Python cache files...
FOR /d /r "%ROOT_DIR%" %%d IN (__pycache__) DO (
    IF EXIST "%%d" (
        RD /S /Q "%%d" 2>nul
        echo Removed: %%d
    )
)

REM Remove .pyc files
echo Removing compiled Python files...
FOR /r "%ROOT_DIR%" %%f IN (*.pyc) DO (
    DEL "%%f" 2>nul
)

REM Remove temp directory if it exists
IF EXIST "%ROOT_DIR%\temp" (
    echo Removing temp directory...
    RD /S /Q "%ROOT_DIR%\temp" 2>nul
    IF EXIST "%ROOT_DIR%\temp" (
        echo - Temp directory is locked. Please close any active processes and try again.
    ) ELSE (
        echo - Temp directory has been removed successfully.
    )
)

echo.
echo Temporary files cleanup completed.
GOTO end

REM ===== Organize Files =====
:organize_files
echo Organizing files into appropriate directories...

REM Create necessary directories if they don't exist
mkdir "%ROOT_DIR%\scripts\analysis" 2>nul
mkdir "%ROOT_DIR%\scripts\search" 2>nul
mkdir "%ROOT_DIR%\scripts\utilities" 2>nul
mkdir "%ROOT_DIR%\docs\images" 2>nul
mkdir "%ROOT_DIR%\data" 2>nul
mkdir "%ROOT_DIR%\lib\python" 2>nul

REM Move Python cache to lib if it exists
IF EXIST "%ROOT_DIR%\__pycache__" (
    move "%ROOT_DIR%\__pycache__" "%ROOT_DIR%\lib\python\" 2>nul
)

REM Move data directories to appropriate places
IF EXIST "%ROOT_DIR%\temp" (
    move "%ROOT_DIR%\temp" "%ROOT_DIR%\data\temp" 2>nul
)
IF EXIST "%ROOT_DIR%\folly" (
    move "%ROOT_DIR%\folly" "%ROOT_DIR%\data\folly" 2>nul
)
IF EXIST "%ROOT_DIR%\dgraph" (
    move "%ROOT_DIR%\dgraph" "%ROOT_DIR%\data\dgraph" 2>nul
)
IF EXIST "%ROOT_DIR%\neo4j" (
    move "%ROOT_DIR%\neo4j" "%ROOT_DIR%\data\neo4j" 2>nul
)

REM Move runtime config to bin
IF EXIST "%ROOT_DIR%\uv.lock" (
    move "%ROOT_DIR%\uv.lock" "%ROOT_DIR%\bin\" 2>nul
)

REM Move image files to docs/images
FOR %%f IN ("%ROOT_DIR%\*.png") DO (
    move "%%f" "%ROOT_DIR%\docs\images\" 2>nul
)

echo.
echo File organization completed.
echo The root directory should now have a clean structure.
GOTO end

REM ===== Complete Cleanup =====
:cleanup_all
echo Performing comprehensive cleanup...

REM Run all cleanup operations
call :cleanup_temp
call :cleanup_cflow
call :cleanup_dependencies
call :organize_files

echo.
echo All cleanup operations completed.
echo The repository should now be in a clean state.
GOTO end

REM ===== Help Information =====
:help
echo.
echo Cleanup Tool - All-in-one repository cleanup script
echo =================================================
echo.
echo Usage: cleanup_tool.bat COMMAND
echo.
echo Commands:
echo   cflow        - Remove cflow installation
echo   deps         - Remove external dependencies (neo4j, folly)
echo   temp         - Clean temporary files and Python caches
echo   organize     - Organize files into appropriate directories
echo   all          - Perform all cleanup operations
echo   help         - Show this help message
echo.
echo Examples:
echo   cleanup_tool.bat temp
echo   cleanup_tool.bat all
echo.
GOTO end

:end
echo.
endlocal 