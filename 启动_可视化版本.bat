@echo off
setlocal

:: 设置相对路径到Python解释器
set "PYTHON_EXE=..\..\venv_appdata\Scripts\python.exe"

:: 检查Python是否存在
if not exist "%PYTHON_EXE%" (
    echo [错误] 找不到Python环境: %PYTHON_EXE%
    echo 请确保 'venv_appdata' 文件夹在 '正式实验' 目录下。
    pause
    exit /b
)

:: 设置 Tcl/Tk 环境变量 (作为双重保障，虽然脚本里也加了)
set "TCL_LIBRARY=..\..\venv_appdata\tcl\tcl8.6"
set "TK_LIBRARY=..\..\venv_appdata\tcl\tk8.6"

echo 正在启动可视化驾驶同步软件...
echo 使用Python: %PYTHON_EXE%

"%PYTHON_EXE%" "可视化传输速率版本custom_driving_sync - v 15 seperate ver - 副本.py"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo 程序异常退出，错误代码: %ERRORLEVEL%
    pause
)
