@echo off
cd /d "%~dp0.."
echo Tap assist: Global timing + PF tracking, with visual Hold. Input starts OFF.
echo Assist: Global ETA, yellow rail recovery, visual Hold tail release.
echo Ctrl+Shift+Alt+Q toggles input; Esc or F12 stops and releases keys.
echo Green/yellow Hold paths keep the start key held until the visible tail leaves.
echo Ordinary cyan/yellow Tap uses Global y-profile ETA; PF supplies tracking only.
echo Recently confirmed scheduled notes may survive a brief detector dropout near the input line.
echo No timing or lane, key conflicts, and stale or unfocused frames still abstain.
echo Game window: hololive-Dreams
echo Capturing the full display containing the game; no ROI selection dialog.
set "holodream_assist_record=N"
set /p "holodream_assist_record=Record overlay + clean source for diagnostics? Y/N [N]: "
set "holodream_assist_record_flag="
if /i "%holodream_assist_record%"=="Y" set "holodream_assist_record_flag=--record-overlay"
python -m src.live %holodream_assist_record_flag% --out output/assist
pause
