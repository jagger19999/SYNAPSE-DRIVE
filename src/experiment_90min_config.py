#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
驾驶多模态同步软件 - 90分钟实验配置

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
- 90分钟正式实验性能优化配置
- 用于高频率数据采集的激进优化设置
- 包含UI更新频率、数据采样率、内存管理等优化参数
- 提供不同数据类型的显示和采样配置
- 支持长时间实验的内存保护和性能优化
"""

class Experiment90MinConfig:
    """90分钟实验专用配置"""
    
    # UI更新频率优化（大幅降低）
    UI_UPDATE_INTERVAL_DRIVING = 3000  # 驾驶参数：3秒更新一次
    UI_UPDATE_INTERVAL_BIOSIG = 5000   # 生物信号：5秒更新一次  
    UI_UPDATE_INTERVAL_EYE = 2000      # 眼动数据：2秒更新一次
    UI_UPDATE_INTERVAL_CACHE = 800     # 缓存状态：保持800ms
    
    # 数据采样优化
    DRIVING_DATA_SAMPLING_RATE = 10    # 驾驶数据：每10个样本显示1个（20Hz→2Hz）
    BIOSIG_DISPLAY_DECIMATION = 100    # 生物信号显示：1000Hz→10Hz
    EYE_DATA_DECIMATION = 10         # 眼动数据：50Hz→5Hz
    
    # 内存管理优化
    MAX_CACHE_SIZE = 50000             # 最大缓存：5万条记录
    CACHE_FLUSH_BATCH_SIZE = 10000   # 批处理大小：1万条
    AGGRESSIVE_CLEANUP_INTERVAL = 300  # 激进清理：每5分钟一次
    UI_CLEANUP_INTERVAL = 15           # UI清理：每15秒一次
    
    # 显示内容优化
    MAX_DISPLAY_LINES_DRIVING = 8      # 驾驶参数：最多8个
    MAX_DISPLAY_LINES_BIOSIG = 5       # 生物信号：最多5个
    MAX_DISPLAY_LINES_EYE = 3          # 眼动数据：最多3个
    
    # ScrolledText清理阈值
    TEXT_WIDGET_MAX_LINES = 50         # 文本控件：超过50行清理
    LOG_TEXT_MAX_LINES = 20            # 日志文本：超过20行清理
    
    # 内存保护
    FORCE_GC_INTERVAL = 300            # 强制垃圾回收：每5分钟
    MEMORY_WARNING_THRESHOLD = 2000    # 内存警告阈值：2GB
    
    # 实验时长相关
    EXPERIMENT_DURATION = 90 * 60      # 90分钟（秒）
    ESTIMATED_TOTAL_SAMPLES = 59400000  # 预计总样本数（5940万）
    
    @classmethod
    def get_optimization_summary(cls):
        """获取优化效果总结"""
        return {
            'ui_update_reduction': {
                'driving': f"{3000/500:.1f}x 减少",  # 对比原来的500ms
                'biosig': f"{5000/800:.1f}x 减少",   # 对比原来的800ms
                'eye': f"{2000/500:.1f}x 减少"      # 对比原来的500ms
            },
            'data_sampling': {
                'driving': f"{cls.DRIVING_DATA_SAMPLING_RATE}x 降采样",
                'biosig': f"{cls.BIOSIG_DISPLAY_DECIMATION}x 降采样", 
                'eye': f"{cls.EYE_DATA_DECIMATION}x 降采样"
            },
            'memory_management': {
                'cache_size': f"{cls.MAX_CACHE_SIZE:,} 条记录",
                'cleanup_frequency': f"每{cls.AGGRESSIVE_CLEANUP_INTERVAL}秒",
                'gc_frequency': f"每{cls.FORCE_GC_INTERVAL}秒"
            },
            'expected_performance': {
                'ui_updates_90min': f"{90*60*1000/3000 + 90*60*1000/5000 + 90*60*1000/2000:,} 次",
                'memory_usage': "预计 1-2GB 峰值",
                'cpu_reduction': "预计 70-80% 降低"
            }
        }
    
    @classmethod
    def print_configuration(cls):
        """打印配置信息"""
        print("🎯 90分钟实验优化配置")
        print("=" * 50)
        
        summary = cls.get_optimization_summary()
        
        print("📊 UI更新优化:")
        for key, value in summary['ui_update_reduction'].items():
            print(f"   {key}: {value}")
            
        print("\n📈 数据采样优化:")
        for key, value in summary['data_sampling'].items():
            print(f"   {key}: {value}")
            
        print("\n💾 内存管理:")
        for key, value in summary['memory_management'].items():
            print(f"   {key}: {value}")
            
        print("\n🚀 预期性能:")
        for key, value in summary['expected_performance'].items():
            print(f"   {key}: {value}")
            
        print("\n⚠️  注意事项:")
        print("   • UI更新频率大幅降低，显示会有延迟")
        print("   • 数据采用降采样显示，但CSV文件保持完整频率")
        print("   • 内存清理会更频繁，可能有短暂卡顿")
        print("   • 建议先进行短时间测试验证效果")

if __name__ == "__main__":
    Experiment90MinConfig.print_configuration()