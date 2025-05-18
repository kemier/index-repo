@echo off
REM ===== Analysis Tool - All-in-one code analysis script =====
REM Manages code analysis operations with cflow and Clang
REM Created by consolidating: run_analysis.bat, run_cflow_analysis.bat, etc.

setlocal enabledelayedexpansion

SET SCRIPT_DIR=%~dp0
SET ROOT_DIR=%SCRIPT_DIR%..
SET CFLOW_EXE=%ROOT_DIR%\cflow-mingw\bin\cflow.exe
SET CFLOW_PREBUILD_EXE=%ROOT_DIR%\cflow-mingw\cflow_x86-64-1.6.exe

REM Display help if no arguments or help requested
IF "%1"=="" (
    GOTO help
)
IF "%1"=="help" (
    GOTO help
)

REM ===== Command Routing =====
IF "%1"=="cflow" (
    GOTO run_cflow_analysis
)

IF "%1"=="clang" (
    GOTO run_clang_analysis
)

IF "%1"=="mixed" (
    GOTO run_mixed_analysis
)

IF "%1"=="folly" (
    GOTO run_folly_analysis
)

IF "%1"=="visualize" (
    GOTO run_visualization
)

IF "%1"=="check-db" (
    GOTO check_neo4j
)

GOTO help

REM ===== Run cflow Analysis =====
:run_cflow_analysis
echo Running cflow code analysis...

REM Set default directory to analyze
SET ANALYZE_DIR=%2
IF "%ANALYZE_DIR%"=="" (
    echo No directory specified, using test.c
    IF NOT EXIST "test.c" (
        echo Creating test.c file...
        echo #include ^<stdio.h^> > test.c
        echo. >> test.c
        echo void bar(int x) { >> test.c
        echo     printf("bar: %%d\n", x^); >> test.c
        echo } >> test.c
        echo. >> test.c
        echo void foo(int x) { >> test.c
        echo     bar(x + 1^); >> test.c
        echo     printf("foo: %%d\n", x^); >> test.c
        echo } >> test.c
        echo. >> test.c
        echo int main() { >> test.c
        echo     foo(42^); >> test.c
        echo     return 0; >> test.c
        echo } >> test.c
        echo Created test.c
    )
    SET ANALYZE_DIR=test.c
)

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
    echo Could not find cflow executable. Running setup...
    call "%SCRIPT_DIR%cflow_tool.bat" setup
    SET CFLOW_TARGET=cflow
    SET CFLOW_FOUND=1
)

REM Create output directory
SET OUTPUT_DIR=%ROOT_DIR%\docs\callgraphs
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

REM Get file or directory name without extension
for %%F in (%ANALYZE_DIR%) do (
    SET FILE_NAME=%%~nF
)

REM Set cflow options
SET CFLOW_OPTS=--number

REM Process third argument for options
IF NOT "%3"=="" (
    IF "%3"=="--dot" (
        SET CFLOW_OPTS=--format=dot
    )
    IF "%3"=="--cpp" (
        SET CFLOW_OPTS=%CFLOW_OPTS% --cpp
    )
)

REM Check if target is a directory
IF EXIST "%ANALYZE_DIR%\*" (
    echo Analyzing directory: %ANALYZE_DIR%
    
    REM Call Python analysis script for directories
    python "%ROOT_DIR%\scripts\analysis_tools.py" --dir "%ANALYZE_DIR%" --output "%OUTPUT_DIR%" --cflow-path "%CFLOW_TARGET%" %4 %5 %6 %7 %8 %9
) ELSE (
    echo Analyzing file: %ANALYZE_DIR%
    
    REM Run cflow directly on the file
    echo Running cflow on %ANALYZE_DIR%...
    "%CFLOW_TARGET%" %CFLOW_OPTS% "%ANALYZE_DIR%" > "%OUTPUT_DIR%\%FILE_NAME%.txt"
    
    REM Generate DOT output if not already
    IF NOT "%CFLOW_OPTS%"=="--format=dot" (
        "%CFLOW_TARGET%" --format=dot "%ANALYZE_DIR%" > "%OUTPUT_DIR%\%FILE_NAME%.dot"
    )
    
    REM Try to generate PNG if graphviz is installed
    where dot >nul 2>&1
    IF %ERRORLEVEL% EQU 0 (
        echo Generating visualization with Graphviz...
        dot -Tpng "%OUTPUT_DIR%\%FILE_NAME%.dot" -o "%OUTPUT_DIR%\%FILE_NAME%.png"
        echo PNG image saved to %OUTPUT_DIR%\%FILE_NAME%.png
    )
)

echo Analysis complete! Results saved to %OUTPUT_DIR%
GOTO end

REM ===== Run Clang Analysis =====
:run_clang_analysis
echo Running Clang code analysis...

REM Set default directory to analyze
SET ANALYZE_DIR=%2
IF "%ANALYZE_DIR%"=="" (
    echo Error: No directory specified for Clang analysis.
    echo Usage: analysis_tool.bat clang directory [options]
    GOTO end
)

REM Check if directory exists
IF NOT EXIST "%ANALYZE_DIR%" (
    echo Error: Directory %ANALYZE_DIR% does not exist.
    GOTO end
)

REM Set default options
SET CLANG_OPTS=--use-clang

REM Process additional arguments
IF NOT "%3"=="" (
    SET CLANG_OPTS=%CLANG_OPTS% %3
)
IF NOT "%4"=="" (
    SET CLANG_OPTS=%CLANG_OPTS% %4
)
IF NOT "%5"=="" (
    SET CLANG_OPTS=%CLANG_OPTS% %5
)
IF NOT "%6"=="" (
    SET CLANG_OPTS=%CLANG_OPTS% %6
)
IF NOT "%7"=="" (
    SET CLANG_OPTS=%CLANG_OPTS% %7
)
IF NOT "%8"=="" (
    SET CLANG_OPTS=%CLANG_OPTS% %8
)
IF NOT "%9"=="" (
    SET CLANG_OPTS=%CLANG_OPTS% %9
)

REM Run the Clang analysis using the Python module
echo Running Clang analysis on %ANALYZE_DIR%...
python -m src index "%ANALYZE_DIR%" --project code_analysis %CLANG_OPTS%

echo Clang analysis complete!
GOTO end

REM ===== Run Mixed C/C++ Analysis =====
:run_mixed_analysis
echo Running mixed C/C++ code analysis...

REM Set default directory to analyze
SET ANALYZE_DIR=%2
IF "%ANALYZE_DIR%"=="" (
    echo Error: No directory specified for mixed analysis.
    echo Usage: analysis_tool.bat mixed directory [options]
    GOTO end
)

REM Check if directory exists
IF NOT EXIST "%ANALYZE_DIR%" (
    echo Error: Directory %ANALYZE_DIR% does not exist.
    GOTO end
)

REM Set up cflow
call "%SCRIPT_DIR%cflow_tool.bat" setup
IF %ERRORLEVEL% NEQ 0 (
    echo Failed to set up cflow. Analysis will continue with Clang only.
    SET CFLOW_ARGS=--skip-cflow
) ELSE (
    SET CFLOW_ARGS=
)

REM Run the analysis script with all arguments
echo Running mixed code analysis on %ANALYZE_DIR%...
python "%ROOT_DIR%\scripts\analyze_mixed_c_cpp.py" %CFLOW_ARGS% --dir "%ANALYZE_DIR%" %3 %4 %5 %6 %7 %8 %9

IF %ERRORLEVEL% NEQ 0 (
    echo Analysis failed with error code %ERRORLEVEL%.
    exit /b %ERRORLEVEL%
) ELSE (
    echo Mixed analysis completed successfully.
)

GOTO end

REM ===== Run Folly Analysis =====
:run_folly_analysis
echo Running Folly codebase analysis...

REM Check if we have a Folly directory
SET FOLLY_DIR=%ROOT_DIR%\folly
IF NOT EXIST "%FOLLY_DIR%" (
    echo Error: Folly directory not found at %FOLLY_DIR%
    echo Please clone the Folly repository first:
    echo git clone https://github.com/facebook/folly.git
    GOTO end
)

REM Check Neo4j connection
echo Checking Neo4j connection...
python -c "from py2neo import Graph; g = Graph('bolt://localhost:7688', auth=('neo4j', 'password')); g.run('MATCH (n) RETURN COUNT(n) LIMIT 1')"
if %ERRORLEVEL% neq 0 (
    echo Neo4j connection failed. Please ensure Neo4j is running at bolt://localhost:7688
    echo with username 'neo4j' and password 'password'
    exit /b 1
)

REM Analyze Folly
echo Analyzing Folly codebase...

REM Run the Folly specific script
python "%ROOT_DIR%\scripts\clear_and_reindex_folly.py" --folly-path "%FOLLY_DIR%" --project folly --workers 4 --neo4j-uri bolt://localhost:7688 --neo4j-user neo4j --neo4j-password password --enhanced-template-handling --track-virtual-methods --cross-file-mode enhanced

echo Folly analysis complete!
GOTO end

REM ===== Run Visualization =====
:run_visualization
echo Running code visualization...

REM Set default options
SET VIZ_OPTS=
SET TARGET=%2

IF "%TARGET%"=="" (
    echo No target specified, using default visualization
    python "%ROOT_DIR%\scripts\generate_folly_callgraph.py" --output "%ROOT_DIR%\docs\images\folly_callgraph.png" --skip-analysis
) ELSE (
    echo Visualizing %TARGET%...
    python "%ROOT_DIR%\scripts\generate_folly_callgraph.py" --output "%ROOT_DIR%\docs\images\%TARGET%_callgraph.png" --focus "%TARGET%" --skip-analysis
)

echo Visualization complete!
GOTO end

REM ===== Check Neo4j Database =====
:check_neo4j
echo Checking Neo4j database content...

python "%ROOT_DIR%\scripts\check_neo4j.py"

GOTO end

REM ===== Help Information =====
:help
echo.
echo Analysis Tool - All-in-one code analysis script
echo =============================================
echo.
echo Usage: analysis_tool.bat COMMAND [options]
echo.
echo Commands:
echo   cflow [file/dir]       - Run cflow analysis on a file or directory
echo   clang [directory]      - Run Clang analysis on a directory
echo   mixed [directory]      - Run mixed C/C++ analysis on a directory
echo   folly                  - Analyze Facebook's Folly codebase
echo   visualize [function]   - Generate visualization (optionally focused on a function)
echo   check-db               - Check Neo4j database content
echo   help                   - Show this help message
echo.
echo Examples:
echo   analysis_tool.bat cflow test.c
echo   analysis_tool.bat clang src --project my_project
echo   analysis_tool.bat folly
echo   analysis_tool.bat visualize folly::StringPiece
echo.
GOTO end

:end
echo.
endlocal 