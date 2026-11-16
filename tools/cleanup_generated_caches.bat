@echo off
setlocal

rem Remove only generated Python and pytest cache directories from this workspace.
pushd "%~dp0.." || exit /b 1

for %%D in (
    ".pytest_cache"
    "src\__pycache__"
    "tests\__pycache__"
    "tools\__pycache__"
    "output\analysis_v86_autoloop\iteration_0029\baseline\__pycache__"
    "output\analysis_v86_autoloop\iteration_0030\candidate\__pycache__"
    "output\analysis_v86_autoloop\iteration_0077_terminal_cap_trial\__pycache__"
) do (
    if exist "%%~D\." (
        echo Removing %%~D
        rmdir /s /q "%%~D"
    )
)

set "HOLO_REMAINING=0"
for %%D in (
    ".pytest_cache"
    "src\__pycache__"
    "tests\__pycache__"
    "tools\__pycache__"
    "output\analysis_v86_autoloop\iteration_0029\baseline\__pycache__"
    "output\analysis_v86_autoloop\iteration_0030\candidate\__pycache__"
    "output\analysis_v86_autoloop\iteration_0077_terminal_cap_trial\__pycache__"
) do (
    if exist "%%~D\." set "HOLO_REMAINING=1"
)

if "%HOLO_REMAINING%"=="0" (
    echo Cache cleanup complete.
    popd
    exit /b 0
) else (
    echo Some cache directories remain. Check permissions and run again.
    popd
    exit /b 2
)
