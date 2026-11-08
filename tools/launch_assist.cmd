@echo off
cd /d "%~dp0.."
echo HoloDream Assist - input starts OFF.
echo Ctrl+Shift+Alt+Q toggles input; Esc/F12 releases keys and stops.
set "holodream_assist_record=N"
set /p "holodream_assist_record=Record overlay + clean source? Y/N [N]: "
set "holodream_assist_record_flag="
if /i "%holodream_assist_record%"=="Y" set "holodream_assist_record_flag=--record-overlay"
python -m src.live %holodream_assist_record_flag% --out output/assist
pause
