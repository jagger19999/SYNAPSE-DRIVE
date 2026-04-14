"""
驾驶多模态同步软件包

这个包包含了驾驶实验多模态数据同步和记录的核心功能模块。

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
- 驾驶多模态同步软件的主包初始化文件
- 定义了包的版本信息和作者信息
- 导入并暴露主要功能模块
- 提供可选的测试模块导入
"""

__version__ = "1.0.0"
__author__ = "驾驶实验研究团队"

# 主要模块
from .custom_driving_sync_v15_seperate_ver import *
from .TobiiSyncRecorder_v16 import *
from .experiment_90min_config import *
from .performance_monitor import *

# 测试模块（可选导入）
try:
    from .test_driving_stream_writer import *
    from .test_optimization import *
    from .test_lsl import *
except ImportError:
    pass  # 测试模块可能不需要在主环境中导入