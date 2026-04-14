# 手动安装pylsl的解决方案

由于网络代理问题，pip无法正常安装包。这里是手动安装步骤：

## 方法1：下载whl文件手动安装

1. 访问：https://pypi.org/project/pylsl/#files
2. 下载适合你系统的whl文件：
   - 如果你使用Python 3.8 64位：下载 `pylsl-1.16.2-cp38-cp38-win_amd64.whl`
3. 在命令行中运行：
   ```
   venv_clean\Scripts\pip.exe install pylsl-1.16.2-cp38-cp38-win_amd64.whl
   ```

## 方法2：使用conda（如果有的话）
如果你有Anaconda，可以运行：
```
conda install -c conda-forge pylsl
```

## 方法3：临时禁用代理
```
set HTTP_PROXY=
set HTTPS_PROXY=
venv_clean\Scripts\pip.exe install pylsl
```

## 验证安装
安装完成后，运行：
```
venv_clean\Scripts\python.exe -c "import pylsl; print('pylsl版本:', pylsl.library_version())"
```

## 如果以上都不行
我已经为你准备了最小化的依赖列表，只需要pylsl即可运行同步软件。其他包（pandas, matplotlib等）是可选的。