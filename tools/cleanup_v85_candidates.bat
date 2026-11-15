@echo off
setlocal EnableExtensions EnableDelayedExpansion

pushd "%~dp0.." || exit /b 2
if not exist "README.md" goto :workspace_error
if not exist "src\lane_segmentation.py" goto :workspace_error
if not exist "docs\V85_CLEANUP_MANIFEST.md" goto :workspace_error

set "MODE=PREVIEW"
if /I "%~1"=="--execute" set "MODE=EXECUTE"
if not "%~1"=="" if /I not "%~1"=="--execute" (
  echo Usage: %~nx0 [--execute]
  popd
  exit /b 2
)

echo Workspace: %CD%
set "WORKSPACE=%CD%"
echo Mode: %MODE%
if "%MODE%"=="EXECUTE" (
  echo This removes only the four explicit Python and pytest cache directories below.
  echo No output, recording, assist, fixture, source, or calibration paths are targeted.
  set /p "CONFIRM=Type Y to continue: "
  if /I not "!CONFIRM!"=="Y" (
    echo Cancelled.
    popd
    exit /b 1
  )
)

set "FAILED=0"
call :candidate ".pytest_cache"
call :candidate "src\__pycache__"
call :candidate "tests\__pycache__"
call :candidate "tools\__pycache__"

popd
if "%FAILED%"=="1" exit /b 1
exit /b 0

:workspace_error
echo Refusing: workspace markers are missing.
popd
exit /b 2

:candidate
if /I not "%~1"==".pytest_cache" if /I not "%~1"=="src\__pycache__" if /I not "%~1"=="tests\__pycache__" if /I not "%~1"=="tools\__pycache__" (
  echo REFUSED  unexpected target %~1
  set "FAILED=1"
  exit /b 1
)
for %%I in ("%WORKSPACE%\%~1") do set "TARGET=%%~fI"
if /I not "!TARGET!"=="%WORKSPACE%\%~1" (
  echo REFUSED  path check failed for %~1
  set "FAILED=1"
  exit /b 1
)
if not exist "%~1\." (
  echo ABSENT  %~1
  exit /b 0
)
if "%MODE%"=="PREVIEW" (
  echo WOULD_REMOVE  %~1
  exit /b 0
)
rmdir /s /q "%~1"
if exist "%~1\NUL" (
  echo FAILED  %~1
  set "FAILED=1"
  exit /b 1
)
echo REMOVED  %~1
exit /b 0
