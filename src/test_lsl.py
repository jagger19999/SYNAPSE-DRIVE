"""
驾驶多模态同步软件 - LSL测试脚本

MIT License

Copyright (c) 2024 驾驶实验研究团队

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

文件功能描述:
- 简单的LSL (Lab Streaming Layer) 测试脚本
- 检测pylsl库的安装和版本信息
- 测试基本的流发现功能
- 验证LSL流的可用性和状态
"""

# 简单的LSL测试脚本
import sys
print(f"Python版本: {sys.version}")

try:
    from pylsl import library_version, resolve_streams
    print(f"pylsl库版本: {library_version()}")
    print("✅ pylsl库已成功导入！")
    
    # 测试基本的流发现功能
    print("正在搜索LSL流...")
    streams = resolve_streams(wait_time=1.0)
    if streams:
        print(f"发现 {len(streams)} 个LSL流:")
        for i, stream in enumerate(streams):
            print(f"  {i+1}. {stream.name()} (类型: {stream.type()})")
    else:
        print("未找到任何LSL流")
        
except ImportError as e:
    print(f"❌ 无法导入pylsl: {e}")
    print("请手动下载pylsl的whl文件进行安装")
except Exception as e:
    print(f"其他错误: {e}")

print("\n按回车键退出...")
input()