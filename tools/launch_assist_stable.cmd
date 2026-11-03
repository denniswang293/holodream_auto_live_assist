@echo off
cd /d "%~dp0.."
echo Stable source-first Assist: 60ms + earlier amendment OFF. Input starts OFF.
echo Ctrl+Shift+Alt+Q toggles input; Esc or F12 stops and releases keys.
echo Game window: hololive-Dreams
set "holodream_assist_record=N"
set /p "holodream_assist_record=Record overlay + clean source for diagnostics? Y/N [N]: "
set "holodream_assist_record_flag="
if /i "%holodream_assist_record%"=="Y" set "holodream_assist_record_flag=--record-overlay"
python -m src.live --profile stable --geometry config/geometry_live_assist.json %holodream_assist_record_flag% --out output/assist
pause
