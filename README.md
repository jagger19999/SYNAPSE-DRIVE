# 多模态数据采集同步软件 (Multimodal Data Acquisition & Synchronization Software)

[!\[Python Version\](https://img.shields.io/badge/python-3.8%2B-blue null)](https://www.python.org/downloads/)
[!\[License\](https://img.shields.io/badge/license-MIT-green null)](LICENSE)
[!\[Platform\](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey null)](https://github.com/your-username/multimodal-sync)

## 🎯 项目简介

这是一个用于驾驶实验的多模态数据采集同步软件，能够同时采集和同步多种生理和行为数据，包括眼动追踪、生理信号、视频录制等。项目基于Python开发，采用模块化设计，支持实时数据流同步和离线数据分析。

### ✨ 主要特性

- **🔍 眼动追踪同步**: 支持Tobii眼动仪数据同步采集
- **💓 生理信号采集**: 集成OpenSignals生理数据采集
- **📹 视频录制**: 支持多路视频流同步录制
- **⚡ 实时同步**: 基于LSL(Lab Streaming Layer)的实时数据同步
- **📊 数据可视化**: 实时数据显示和离线分析
- **🎮 驾驶模拟**: 支持Unity3D驾驶模拟环境集成
- **📁 数据管理**: 结构化的数据存储和管理系统

## 🚀 快速开始

### 系统要求

- Python 3.8 或更高版本
- Windows 10/11, Linux, 或 macOS
- 至少4GB RAM（推荐8GB）
- 支持OpenGL的显卡（用于视频处理）

### 安装步骤

1. **克隆仓库**

```bash
git clone https://github.com/your-username/multimodal-sync.git
cd multimodal-sync
```

1. **创建虚拟环境**

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate  # Windows
```

1. **安装依赖**

```bash
pip install -r requirements.txt
```

1. **运行主程序**

```bash
python src/custom_driving_sync_v15_seperate_ver.py
```

## 📋 功能模块

### 核心模块

| 模块                                        | 功能描述             |
| ----------------------------------------- | ---------------- |
| `custom_driving_sync_v15_seperate_ver.py` | 主同步程序，集成所有数据采集模块 |
| `TobiiSyncRecorder_v16.py`                | Tobii眼动仪数据同步采集   |
| `experiment_90min_config.py`              | 90分钟实验配置文件       |
| `performance_monitor.py`                  | 系统性能监控和优化        |

### 测试模块

| 模块                              | 功能描述      |
| ------------------------------- | --------- |
| `test_lsl.py`                   | LSL数据流测试  |
| `test_driving_stream_writer.py` | 驾驶数据流写入测试 |
| `test_optimization.py`          | 性能优化测试    |

## 🔧 配置说明

### 基本配置

编辑 `config/settings.json` 文件来配置您的实验参数：

```json
{
    "experiment_name": "驾驶行为研究",
    "duration_minutes": 90,
    "sampling_rate": {
        "eyetracking": 60,
        "physiology": 1000,
        "video": 30
    },
    "devices": {
        "tobii_enabled": true,
        "opensignals_enabled": true,
        "video_enabled": true
    }
}
```

### 高级配置

更多配置选项请参考 [配置文档](docs/configuration.md)。

## 📊 数据格式

### 输出文件结构

```
experiment_data/
├── eyetracking/
│   ├── tobii_data_*.csv
│   └── gaze_mapping_*.json
├── physiology/
│   ├── ecg_data_*.csv
│   ├── eda_data_*.csv
│   └── respiration_*.csv
├── video/
│   ├── front_camera_*.mp4
│   └── driver_camera_*.mp4
└── sync/
    ├── timestamps_*.csv
    └── events_*.json
```

### 数据同步

所有数据流都通过LSL(Lab Streaming Layer)进行时间同步，确保不同数据源的时间戳一致性。

## 🛠️ 开发指南

### 项目结构

```
multimodal-sync/
├── src/                    # 源代码目录
│   ├── __init__.py
│   ├── custom_driving_sync_v15_seperate_ver.py
│   ├── TobiiSyncRecorder_v16.py
│   └── ...
├── docs/                   # 文档目录
├── examples/               # 示例代码
├── tests/                  # 测试文件
├── requirements.txt        # Python依赖
├── setup.py               # 安装配置
└── README.md              # 项目说明
```

### 开发环境设置

1. **安装开发依赖**

```bash
pip install -r requirements-dev.txt
```

1. **运行测试**

```bash
python -m pytest tests/
```

1. **代码质量检查**

```bash
flake8 src/
black src/
```

## 🤝 贡献指南

我们欢迎社区贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解如何参与项目开发。

### 贡献类型

- 🐛 **Bug修复**: 报告或修复程序错误
- ✨ **新功能**: 添加新的数据采集模块
- 📖 **文档**: 改进项目文档
- 🧪 **测试**: 添加测试用例
- 🔧 **工具**: 开发辅助工具


## 🔗 相关项目

- [Lab Streaming Layer (LSL)](https://github.com/sccn/labstreaminglayer) - 数据同步框架
- [Tobii Pro SDK](https://github.com/TobiiPro) - 眼动追踪开发工具包
- [OpenSignals](https://github.com/pluxbiosignals) - 生理信号采集软件

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

- 感谢 [Lab Streaming Layer](https://github.com/sccn/labstreaminglayer) 项目提供的优秀数据同步框架
- 感谢所有为开源社区贡献的开发者和研究人员
- 感谢项目贡献者和测试用户的支持

## 📞 联系方式

- **项目维护者**: 王杰
- **联系方式**:[851590822@qq.com](https://github.com/your-username/multimodal-sync/issues)

## 📈 项目状态

- ✅ **核心功能**: 稳定运行
- 🔄 **持续开发**: 定期更新
- 📊 **数据同步**: 经过验证
- 🧪 **测试覆盖**: 持续改进中

***

⭐ 如果这个项目对您有帮助，请给我们一个星标！

**Made with ❤️ by wangjie**
