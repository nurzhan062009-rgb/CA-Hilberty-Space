@echo off
rem Opens the notebooks in your browser (JupyterLab). No VS Code needed.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Creating local Python environment...
    py -3.11 -m venv .venv 2>nul || py -3 -m venv .venv
    ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
    ".venv\Scripts\python.exe" -m pip install --quiet qiskit qiskit-aer numpy scipy matplotlib
)
".venv\Scripts\python.exe" -c "import jupyterlab" 2>nul || ".venv\Scripts\python.exe" -m pip install --quiet jupyterlab
echo Starting JupyterLab - a browser window will open.
echo Keep this black window open while you work; close it to stop the server.
".venv\Scripts\python.exe" -m jupyter lab --notebook-dir="%~dp0.." --ip=127.0.0.1
pause