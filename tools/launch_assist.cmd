@echo off
cd /d "%~dp0.."
echo C mode: Simple Tracker + Particle ETA, with visual Hold. Input starts OFF.
echo Ctrl+Shift+Alt+Q toggles input; Esc or F12 stops and releases keys.
echo Green/yellow Hold paths keep the start key held until the visible tail leaves.
echo Ordinary cyan/yellow Tap uses the C particle-tracking core.
echo Recently confirmed scheduled notes may survive a brief detector dropout near the input line.
echo No timing or lane, key conflicts, and stale or unfocused frames still abstain.
echo Game window: hololive-Dreams
echo Capturing the full display containing the game; no ROI selection dialog.
set "holodream_assist_record=N"
set /p "holodream_assist_record=Record overlay + clean source for diagnostics? Y/N [N]: "
set "holodream_assist_record_flag="
if /i "%holodream_assist_record%"=="Y" set "holodream_assist_record_flag=--record-overlay"
python -m src.live --config config.json --live-config config/live_assist.json --geometry config/geometry_live_assist.json %holodream_assist_record_flag% --out output/assist
pause
