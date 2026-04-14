@echo off
echo 正在下载Python 3.8.10嵌入版...
echo.

powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.8.10/python-3.8.10-embed-amd64.zip' -OutFile 'python-3.8.10-embed-amd64.zip'"

if exist python-3.8.10-embed-amd64.zip (
    echo 下载完成，正在解压...
    powershell -Command "Expand-Archive -Path 'python-3.8.10-embed-amd64.zip' -DestinationPath 'python_embedded' -Force"
    
    echo 正在下载get-pip.py...
    powershell -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile 'get-pip.py'"
    
    echo 正在安装pip...
    python_embedded\python.exe get-pip.py
    
    echo 正在创建虚拟环境...
    python_embedded\python.exe -m venv venv_clean
    
    echo 正在安装依赖包...
    venv_clean\Scripts\pip.exe install pylsl pandas matplotlib openpyxl numpy
    
    echo.
    echo ✅ 环境设置完成！
    echo.
    echo 使用方法：
    echo 1. 激活环境： venv_clean\Scripts\activate
    echo 2. 运行程序： python custom_driving_sync - v 15 seperate ver.py
    echo.
    pause
) else (
    echo ❌ 下载失败，请检查网络连接
    pause
)