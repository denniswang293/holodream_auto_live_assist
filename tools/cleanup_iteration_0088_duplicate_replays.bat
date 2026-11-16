@echo off
setlocal EnableExtensions EnableDelayedExpansion

pushd "%~dp0.." || exit /b 2
if not exist "README.md" goto :workspace_error
if not exist "src\lane_segmentation.py" goto :workspace_error

set "MODE=PREVIEW"
if /I "%~1"=="--execute" set "MODE=EXECUTE"
if not "%~1"=="" if /I not "%~1"=="--execute" (
  echo Usage: %~nx0 [--execute]
  popd
  exit /b 2
)

set "DUPLICATE_BASE_1=output\analysis_v86_autoloop\iteration_0088_hold_group_extent_repair\fixed_14ms"
set "DUPLICATE_BASE_2=output\analysis_v86_autoloop\iteration_0090_cleanup_audit\fixed_14ms"
set "KEEP_BASE=output\analysis_v86_autoloop\iteration_0088_hold_group_extent_repair\fixed_14ms_final"
set "RUN=run_20261106T164049_800126Z"
set "TRACE_HASH=D1ED7B633C62D21DE52798EA7DA6A2424FD6E6A7DBEA18CEA4B092CD8F30CE82"
set "DECISIONS_HASH=A48349681D9345437F84D4E4BCA6D5DC916F3B129939B31C8CDF7E0695316F46"

echo Workspace: %CD%
echo Mode: %MODE%
echo Only exact-hash duplicate CSVs in the 0088 and 0090 fixed_14ms runs will be targeted.
echo The 0088 fixed_14ms_final copies are retained and hash-checked.

call :candidate "%DUPLICATE_BASE_1%" "candidate_trace.csv" "%TRACE_HASH%"
if errorlevel 1 goto :failed
call :candidate "%DUPLICATE_BASE_1%" "physical_note_decisions.csv" "%DECISIONS_HASH%"
if errorlevel 1 goto :failed
call :candidate "%DUPLICATE_BASE_2%" "candidate_trace.csv" "%TRACE_HASH%"
if errorlevel 1 goto :failed
call :candidate "%DUPLICATE_BASE_2%" "physical_note_decisions.csv" "%DECISIONS_HASH%"
if errorlevel 1 goto :failed

if "%MODE%"=="EXECUTE" (
  set /p "CONFIRM=Type Y to delete the two verified duplicate files: "
  if /I not "!CONFIRM!"=="Y" (
    echo Cancelled.
    popd
    exit /b 1
  )
  call :remove "%DUPLICATE_BASE_1%" "candidate_trace.csv" "%TRACE_HASH%"
  if errorlevel 1 goto :failed
  call :remove "%DUPLICATE_BASE_1%" "physical_note_decisions.csv" "%DECISIONS_HASH%"
  if errorlevel 1 goto :failed
  call :remove "%DUPLICATE_BASE_2%" "candidate_trace.csv" "%TRACE_HASH%"
  if errorlevel 1 goto :failed
  call :remove "%DUPLICATE_BASE_2%" "physical_note_decisions.csv" "%DECISIONS_HASH%"
  if errorlevel 1 goto :failed
)

popd
exit /b 0

:workspace_error
echo Refusing: workspace markers are missing.
popd
exit /b 2

:candidate
set "TARGET=%~1\%RUN%\%~2"
set "KEEP=%KEEP_BASE%\%RUN%\%~2"
if not exist "%TARGET%" (
  echo ABSENT  %TARGET%
  exit /b 0
)
if not exist "%KEEP%" (
  echo REFUSED  retained counterpart missing: %KEEP%
  exit /b 1
)
certutil -hashfile "%TARGET%" SHA256 | findstr /I /C:"%~3" >nul
if errorlevel 1 (
  echo REFUSED  candidate hash mismatch: %TARGET%
  exit /b 1
)
certutil -hashfile "%KEEP%" SHA256 | findstr /I /C:"%~3" >nul
if errorlevel 1 (
  echo REFUSED  retained copy hash mismatch: %KEEP%
  exit /b 1
)
for %%I in ("%TARGET%") do echo VERIFIED  %%~zI bytes  %TARGET%
if "%MODE%"=="PREVIEW" echo WOULD_REMOVE  %TARGET%
exit /b 0

:remove
set "TARGET=%~1\%RUN%\%~2"
set "KEEP=%KEEP_BASE%\%RUN%\%~2"
if not exist "%TARGET%" exit /b 0
certutil -hashfile "%TARGET%" SHA256 | findstr /I /C:"%~3" >nul
if errorlevel 1 (
  echo REFUSED  candidate changed since preview: %TARGET%
  exit /b 1
)
certutil -hashfile "%KEEP%" SHA256 | findstr /I /C:"%~3" >nul
if errorlevel 1 (
  echo REFUSED  retained copy changed: %KEEP%
  exit /b 1
)
del /f /q "%TARGET%"
if exist "%TARGET%" (
  echo FAILED  %TARGET%
  exit /b 1
)
echo REMOVED  %TARGET%
exit /b 0

:failed
popd
exit /b 1
