@echo off
cd /d "%~dp0.."
echo Assist: full display capture, input starts OFF.
echo Ctrl+Shift+Alt+Q toggles input; Esc or F12 stops and releases keys.
echo Diagnostics, snapshots, summaries, and recordings are disabled.
echo Game window: hololive-Dreams
python -m src.live --no-logs
pause
