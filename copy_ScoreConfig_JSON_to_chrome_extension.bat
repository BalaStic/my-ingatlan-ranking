@echo off
copy /Y "%~dp0scoring_config.json" "%~dp0chrome_extension\scoring_config.json"
echo Kesz! scoring_config.json masolva: chrome_extension\scoring_config.json
echo "Ne felejtsd el az extensiont ujratolteni: chrome://extensions/ -> Reload"

