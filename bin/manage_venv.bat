@echo off
REM Virtual Environment Management Script using UV
REM Usage: manage_venv.bat [command]

SET SCRIPT_DIR=%~dp0
SET ROOT_DIR=%SCRIPT_DIR%..

IF "%1"=="" (
    GOTO help
)

IF "%1"=="create" (
    ECHO Creating virtual environment...
    cd %ROOT_DIR%
    uv venv .venv
    ECHO Done. Activate with: .venv\Scripts\activate
    GOTO end
)

IF "%1"=="install" (
    ECHO Installing dependencies...
    cd %ROOT_DIR%
    IF EXIST ".venv\Scripts\activate" (
        CALL .venv\Scripts\activate
        uv pip install -r requirements.txt
        ECHO Done.
    ) ELSE (
        ECHO Virtual environment not found. Create it first with: manage_venv.bat create
    )
    GOTO end
)

IF "%1"=="update" (
    ECHO Updating dependencies...
    cd %ROOT_DIR%
    IF EXIST ".venv\Scripts\activate" (
        CALL .venv\Scripts\activate
        uv pip install --upgrade -r requirements.txt
        ECHO Done.
    ) ELSE (
        ECHO Virtual environment not found. Create it first with: manage_venv.bat create
    )
    GOTO end
)

IF "%1"=="list" (
    ECHO Listing installed packages...
    cd %ROOT_DIR%
    IF EXIST ".venv\Scripts\activate" (
        CALL .venv\Scripts\activate
        uv pip list
    ) ELSE (
        ECHO Virtual environment not found. Create it first with: manage_venv.bat create
    )
    GOTO end
)

IF "%1"=="add" (
    IF "%2"=="" (
        ECHO Missing package name. Usage: manage_venv.bat add package_name
        GOTO end
    )
    ECHO Installing package: %2
    cd %ROOT_DIR%
    IF EXIST ".venv\Scripts\activate" (
        CALL .venv\Scripts\activate
        uv pip install %2
        ECHO Done.
    ) ELSE (
        ECHO Virtual environment not found. Create it first with: manage_venv.bat create
    )
    GOTO end
)

IF "%1"=="clean" (
    ECHO Removing virtual environment...
    cd %ROOT_DIR%
    IF EXIST ".venv" (
        rmdir /s /q .venv
        ECHO Virtual environment removed.
    ) ELSE (
        ECHO No virtual environment found.
    )
    GOTO end
)

IF "%1"=="help" (
    :help
    ECHO.
    ECHO UV Virtual Environment Management
    ECHO ===============================
    ECHO.
    ECHO Commands:
    ECHO   create       : Create a new virtual environment
    ECHO   install      : Install dependencies from requirements.txt
    ECHO   update       : Update all dependencies
    ECHO   list         : List installed packages
    ECHO   add [package]: Install a specific package
    ECHO   clean        : Remove the virtual environment
    ECHO   help         : Show this help message
    ECHO.
    ECHO Example:
    ECHO   manage_venv.bat create
    ECHO   manage_venv.bat install
    ECHO   manage_venv.bat add networkx
    ECHO.
    GOTO end
)

ECHO Unknown command: %1
ECHO Run 'manage_venv.bat help' for available commands.

:end
exit /b 0 