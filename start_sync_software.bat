@echo off
echo 正在启动多模态同步软件...
echo.

REM 激活虚拟环境
call venv_clean\Scripts\activate.bat

REM 设置环境变量避免代理问题
set HTTP_PROXY=
set HTTPS_PROXY=

echo 虚拟环境已激活，正在运行同步软件...
echo.

REM 运行同步软件
python "custom_driving_sync - v 15 seperate ver.py"

REM 保持窗口打开
pause