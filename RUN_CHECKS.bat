@echo off
rem One-click correctness check for the Transpilation Battle submission.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Creating local Python environment...
    py -3.11 -m venv .venv 2>nul || py -3 -m venv .venv
    echo Installing qiskit - needs internet, a few minutes...
    ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
    ".venv\Scripts\python.exe" -m pip install --quiet qiskit qiskit-aer numpy scipy matplotlib
)
".venv\Scripts\python.exe" -X utf8 run_checks.py
echo.
pause