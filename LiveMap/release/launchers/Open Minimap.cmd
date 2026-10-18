@echo off
setlocal
pushd "%~dp0"
if exist "MediEvilMinimap.exe" goto frozen
where py >nul 2>nul
if not errorlevel 1 goto py
where python >nul 2>nul
if not errorlevel 1 goto python
echo Python 3.10 or newer is required for this source package.
echo Install Python from python.org, or use a standalone Windows build.
pause
popd
exit /b 1
:py
py -3 runner.py --open %*
goto done
:python
python runner.py --open %*
goto done
:frozen
MediEvilMinimap.exe --open %*
:done
set "result=%errorlevel%"
popd
if not "%result%"=="0" pause
exit /b %result%
