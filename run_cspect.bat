@echo off
rem ------------------------------------------------------------------
rem run_cspect.bat - convert a .z80 snapshot to .nex and run it in CSpect
rem
rem Usage:
rem   run_cspect.bat game.z80      convert, then run the new .nex
rem   run_cspect.bat game.nex      run an existing .nex
rem   or drag a .z80 / .nex file onto this batch file
rem
rem Keep this file in the same folder as z80tonex.py.
rem ------------------------------------------------------------------
setlocal

rem ==== Settings - edit these to match your PC ====================
set "CSPECT=C:\CSpect\CSpect.exe"
set "PYTHON=python"
set "CONVERTER=%~dp0z80tonex.py"

rem CSpect options:
rem   -zxnext   emulate the Next hardware (NextRegs, MMU, sprites)
rem   -nextrom  use the real Next ROMs (enNextZX.rom and enNxtmmc.rom
rem             must be in the CSpect folder); needed for the 48K ROM
rem   -w3       window scale x3
rem   -tv       turn off the TV scanline effect
set "CSPECT_OPTS=-zxnext -nextrom -w3 -tv"
rem =================================================================

if "%~1"=="" (
    echo Usage: %~nx0 game.z80  ^|  %~nx0 game.nex
    echo Or drag a .z80 or .nex file onto this batch file.
    goto :fail
)
if not exist "%~1" (
    echo File not found: %~1
    goto :fail
)
if not exist "%CSPECT%" (
    echo CSpect not found at: %CSPECT%
    echo Edit the CSPECT line at the top of this batch file.
    goto :fail
)

set "NEXFILE=%~1"
if /i "%~x1"==".z80" (
    if not exist "%CONVERTER%" (
        echo z80tonex.py not found at: %CONVERTER%
        goto :fail
    )
    set "NEXFILE=%~dpn1.nex"
    "%PYTHON%" "%CONVERTER%" "%~1" -o "%~dpn1.nex"
    if errorlevel 1 (
        echo Conversion failed.
        goto :fail
    )
    echo.
) else if /i not "%~x1"==".nex" (
    echo Expected a .z80 or .nex file, got: %~nx1
    goto :fail
)

echo Starting CSpect with %NEXFILE%
rem CSpect looks for its ROM files in its own folder, so run it from there
for %%I in ("%CSPECT%") do set "CSPECTDIR=%%~dpI"
start "" /D "%CSPECTDIR%" "%CSPECT%" %CSPECT_OPTS% "%NEXFILE%"
goto :eof

:fail
pause
exit /b 1
