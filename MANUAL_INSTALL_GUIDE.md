# 手动安装Python的完整步骤

## 步骤1：下载Python
由于自动下载遇到问题，请手动下载：

1. 打开浏览器，访问：https://www.python.org/ftp/python/3.8.10/python-3.8.10-amd64.exe
2. 下载完成后，文件应该叫做 `python-3.8.10-amd64.exe`

## 步骤2：安装Python
1. 双击运行 `python-3.8.10-amd64.exe`
2. **重要**：勾选底部的 "Add Python 3.8 to PATH"
3. 点击 "Customize installation"
4. 保持所有选项默认，点击 "Next"
5. 勾选 "Install for all users"
6. 安装路径改为：`C:\Python38`
7. 点击 "Install"

## 步骤3：验证安装
安装完成后，打开新的命令窗口，输入：
```
python --version
```
应该显示：`Python 3.8.10`

## 步骤4：创建新的虚拟环境
在 `unnity特供版驾驶多模态同步软件` 文件夹中运行：
```
C:\Python38\python.exe -m venv venv_clean
```

## 步骤5：激活环境并安装依赖
```
venv_clean\Scripts\activate
pip install pylsl pandas matplotlib openpyxl numpy
```

## 步骤6：测试LSL
```
python -c "import pylsl; print('pylsl installed successfully!')"
```

## 步骤7：运行你的同步软件
```
python custom_driving_sync - v 15 seperate ver.py
```

## 快速修复脚本
我已经创建了修复脚本，你可以直接运行：
```
setup_python.bat
```

如果下载失败，请按照上面的手动步骤操作。