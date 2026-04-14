@echo off
echo 正在创建新的虚拟环境...
echo.

REM 创建虚拟环境
C:\Python38\python.exe -m venv venv_clean

if exist venv_clean\Scripts\python.exe (
    echo ✅ 虚拟环境创建成功！
    echo.
    echo 正在激活环境并安装依赖...
    
    REM 激活环境并安装依赖
    call venv_clean\Scripts\activate.bat
    
    echo 安装 pylsl...
    pip install pylsl
    
    echo 安装 pandas...
    pip install pandas
    
    echo 安装 matplotlib...
    pip install matplotlib
    
    echo 安装 openpyxl...
    pip install openpyxl
    
    echo 安装 numpy...
    pip install numpy
    
    echo.
    echo ✅ 所有依赖安装完成！
    echo.
    echo 验证pylsl安装...
    venv_clean\Scripts\python.exe -c "import pylsl; print('pylsl版本:', pylsl.library_version()); print('✅ pylsl安装成功！')"
    
    echo.
    echo 🎉 环境设置完成！
    echo.
    echo 使用方法：
    echo 1. 激活环境： venv_clean\Scripts\activate
    echo 2. 运行程序： python custom_driving_sync - v 15 seperate ver.py
    echo.
    
    REM 保持窗口打开
    pause
) else (
    echo ❌ 虚拟环境创建失败，请检查Python安装
    pause
)