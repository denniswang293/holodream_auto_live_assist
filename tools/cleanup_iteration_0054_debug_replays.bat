@echo off
setlocal EnableExtensions EnableDelayedExpansion

pushd "%~dp0.." || exit /b 2
if not exist "README.md" goto :workspace_error
if not exist "src\lane_segmentation.py" goto :workspace_error
if not exist "output\analysis_v86_autoloop\iteration_0054\iteration_manifest.json" goto :manifest_error

set "MODE=PREVIEW"
if /I "%~1"=="--execute" set "MODE=EXECUTE"
if not "%~1"=="" if /I not "%~1"=="--execute" (
  echo Usage: %~nx0 [--execute]
  popd
  exit /b 2
)

echo Workspace: %CD%
echo Mode: %MODE%
set "FAILED=0"
call :candidate "assist_v85_debug"
call :candidate "assist_v85_debug2"
if "%FAILED%"=="1" (
  popd
  exit /b 1
)
if "%MODE%"=="PREVIEW" (
  echo Preview complete. Run with --execute and confirm Y to remove the exact diagnostic reruns.
  popd
  exit /b 0
)
set /p "CONFIRM=Type Y to remove the verified diagnostic reruns: "
if /I not "!CONFIRM!"=="Y" (
  echo Cancelled.
  popd
  exit /b 1
)
call :remove "output\analysis_v86_autoloop\iteration_0054\assist_v85_debug"
call :remove "output\analysis_v86_autoloop\iteration_0054\assist_v85_debug2"
popd
if "%FAILED%"=="1" exit /b 1
exit /b 0

:candidate
set "TARGET=output\analysis_v86_autoloop\iteration_0054\%~1"
for %%I in ("%CD%\%TARGET%") do set "TARGET_ABS=%%~fI"
if /I not "!TARGET_ABS!"=="%CD%\%TARGET%" goto :refused
if not exist "%TARGET%\." (
  echo ABSENT  %TARGET%
  exit /b 0
)
if not exist "%TARGET%\run_20261109T143554_007912Z\replay_manifest.json" goto :contents_error
for /f %%N in ('dir /b /ad "%TARGET%" 2^>nul ^| find /c /v ""') do set "DIR_COUNT=%%N"
if not "!DIR_COUNT!"=="1" goto :contents_error
for /f %%N in ('dir /b /a-d "%TARGET%" 2^>nul ^| find /c /v ""') do set "ROOT_FILE_COUNT=%%N"
if not "!ROOT_FILE_COUNT!"=="0" goto :contents_error
set "RUN=%TARGET%\run_20261109T143554_007912Z"
for /f %%N in ('dir /b /ad "%RUN%" 2^>nul ^| find /c /v ""') do set "RUN_DIR_COUNT=%%N"
if not "!RUN_DIR_COUNT!"=="0" goto :contents_error
for /f %%N in ('dir /b /a-d "%RUN%" 2^>nul ^| find /c /v ""') do set "RUN_FILE_COUNT=%%N"
if not "!RUN_FILE_COUNT!"=="8" goto :contents_error
for %%F in (baseline_vs_candidate.csv candidate_trace.csv frame_summary.csv mock_actions.csv mock_safety_audit.json physical_note_decisions.csv replay_manifest.json stage_profile_by_frame.csv) do if not exist "%RUN%\%%F" goto :contents_error
findstr /C:"run_20261109T143554_007912Z" "%RUN%\replay_manifest.json" >nul || goto :contents_error
findstr /C:"v85" "%RUN%\replay_manifest.json" >nul || goto :contents_error
findstr /C:"1149" "%RUN%\replay_manifest.json" >nul || goto :contents_error
echo VERIFIED  %TARGET%
exit /b 0

:remove
if not exist "%~1\." exit /b 0
rmdir /s /q "%~1"
if exist "%~1\." (
  echo FAILED  %~1
  set "FAILED=1"
  exit /b 1
)
echo REMOVED  %~1
exit /b 0

:workspace_error
echo Refusing: workspace markers are missing.
popd
exit /b 2

:manifest_error
echo Refusing: iteration cleanup manifest is missing.
popd
exit /b 2

:refused
echo REFUSED  path check failed for %TARGET%
set "FAILED=1"
exit /b 1

:contents_error
echo REFUSED  unexpected files or replay metadata in %TARGET%
set "FAILED=1"
exit /b 1
