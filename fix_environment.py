import os
import sys
import urllib.request
import zipfile
import subprocess
import shutil

def download_file(url, filename):
    """下载文件"""
    print(f"正在下载 {filename}...")
    try:
        urllib.request.urlretrieve(url, filename)
        return True
    except Exception as e:
        print(f"下载失败: {e}")
        return False

def setup_embedded_python():
    """设置嵌入式Python环境"""
    python_url = "https://www.python.org/ftp/python/3.8.10/python-3.8.10-embed-amd64.zip"
    python_zip = "python-3.8.10-embed-amd64.zip"
    python_dir = "python_embedded"
    
    # 下载Python嵌入版
    if not os.path.exists(python_zip):
        if not download_file(python_url, python_zip):
            return False
    
    # 解压Python
    if os.path.exists(python_dir):
        shutil.rmtree(python_dir)
    
    print("正在解压Python...")
    with zipfile.ZipFile(python_zip, 'r') as zip_ref:
        zip_ref.extractall(python_dir)
    
    # 获取Python路径
    python_exe = os.path.join(python_dir, "python.exe")
    
    # 安装pip
    get_pip_url = "https://bootstrap.pypa.io/get-pip.py"
    get_pip_script = "get-pip.py"
    
    if not os.path.exists(get_pip_script):
        if not download_file(get_pip_url, get_pip_script):
            return False
    
    print("正在安装pip...")
    subprocess.run([python_exe, get_pip_script], check=True)
    
    # 创建新的虚拟环境
    venv_dir = "venv_clean"
    if os.path.exists(venv_dir):
        shutil.rmtree(venv_dir)
    
    print("正在创建虚拟环境...")
    subprocess.run([python_exe, "-m", "venv", venv_dir], check=True)
    
    # 安装依赖
    pip_exe = os.path.join(venv_dir, "Scripts", "pip.exe")
    dependencies = ["pylsl", "pandas", "matplotlib", "openpyxl", "numpy"]
    
    print("正在安装依赖包...")
    for dep in dependencies:
        print(f"安装 {dep}...")
        subprocess.run([pip_exe, "install", dep], check=True)
    
    # 验证安装
    python_venv = os.path.join(venv_dir, "Scripts", "python.exe")
    print("验证安装...")
    result = subprocess.run([python_venv, "-c", "import pylsl; print('pylsl available')"], 
                            capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ 环境设置成功!")
        print(f"新的Python路径: {python_venv}")
        print(f"激活命令: {os.path.join(venv_dir, 'Scripts', 'activate')}")
        return True
    else:
        print("❌ 验证失败:", result.stderr)
        return False

def main():
    print("开始修复Python环境...")
    
    # 检查网络连接
    try:
        urllib.request.urlopen("https://www.python.org", timeout=5)
    except:
        print("❌ 网络连接失败，无法下载Python")
        print("请手动下载Python 3.8.10从: https://www.python.org/ftp/python/3.8.10/python-3.8.10-amd64.exe")
        return
    
    if setup_embedded_python():
        print("\n🎉 修复完成!")
        print("你现在可以使用新的虚拟环境了:")
        print("1. 激活环境: venv_clean\\Scripts\\activate")
        print("2. 运行脚本: python custom_driving_sync\\ -\\ v\\ 15\\ seperate\\ ver.py")
    else:
        print("\n❌ 修复失败，请查看错误信息")

if __name__ == "__main__":
    main()