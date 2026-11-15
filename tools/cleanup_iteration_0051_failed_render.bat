@echo off
setlocal EnableExtensions EnableDelayedExpansion

pushd "%~dp0.." || exit /b 2
if not exist "README.md" goto :workspace_error
if not exist "src\lane_segmentation.py" goto :workspace_error
if not exist "output\analysis_v86_autoloop\iteration_0051\cleanup_manifest.json" goto :manifest_error

set "MODE=PREVIEW"
if /I "%~1"=="--execute" set "MODE=EXECUTE"
if not "%~1"=="" if /I not "%~1"=="--execute" (
  echo Usage: %~nx0 [--execute]
  popd
  exit /b 2
)

set "TARGET=output\analysis_v86_autoloop\iteration_0051\edge_recovery_ab_361_385"
for %%I in ("%CD%\%TARGET%") do set "TARGET_ABS=%%~fI"
if /I not "!TARGET_ABS!"=="%CD%\output\analysis_v86_autoloop\iteration_0051\edge_recovery_ab_361_385" goto :path_error
if not exist "%TARGET%\." (
  echo ABSENT  %TARGET%
  popd
  exit /b 0
)
if not exist "%TARGET%\edge_recovery_ab.mp4" goto :contents_error
for %%F in ("%TARGET%\edge_recovery_ab.mp4") do if not "%%~zF"=="765898" goto :contents_error
for /f %%N in ('dir /b /a-d "%TARGET%" ^| find /c /v ""') do set "FILE_COUNT=%%N"
if not "!FILE_COUNT!"=="1" goto :contents_error
for /f %%N in ('dir /b /ad "%TARGET%" 2^>nul ^| find /c /v ""') do set "DIR_COUNT=%%N"
if not "!DIR_COUNT!"=="0" goto :contents_error

echo Workspace: %CD%
echo Candidate: %TARGET%\edge_recovery_ab.mp4 (765898 bytes; incomplete render)
if "%MODE%"=="PREVIEW" (
  echo WOULD_REMOVE  %TARGET%
  echo Run with --execute and confirm Y to remove this one incomplete output.
  popd
  exit /b 0
)
echo The complete comparison is retained separately in edge_recovery_ab_361_385_final.
echo No recording, Assist input, or completed evidence path is targeted.
set /p "CONFIRM=Type Y to continue: "
if /I not "!CONFIRM!"=="Y" (
  echo Cancelled.
  popd
  exit /b 1
)
rmdir /s /q "%TARGET%"
if exist "%TARGET%\." (
  echo FAILED  %TARGET%
  popd
  exit /b 1
)
echo REMOVED  %TARGET%
popd
exit /b 0

:workspace_error
echo Refusing: workspace markers are missing.
popd
exit /b 2

:manifest_error
echo Refusing: iteration cleanup manifest is missing.
popd
exit /b 2

:path_error
echo Refusing: target path check failed.
popd
exit /b 2

:contents_error
echo Refusing: target contents differ from the one-file cleanup manifest.
popd
exit /b 3
