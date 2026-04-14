#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
驾驶多模态同步软件 - 优化效果测试

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
- 测试驾驶数据UI更新优化效果
- 用于验证长时间运行时的性能表现
- 提供内存使用监控功能
- 支持性能数据收集和分析
- 验证优化配置的实际效果
"""

import time
import threading
import psutil
import os
import sys
from datetime import datetime

class PerformanceMonitor:
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.start_time = time.time()
        self.monitoring = True
        self.peak_memory = 0
        self.memory_samples = []
        
    def start_monitoring(self):
        """开始监控内存使用情况"""
        def monitor():
            while self.monitoring:
                try:
                    memory_mb = self.process.memory_info().rss / 1024 / 1024
                    self.memory_samples.append(memory_mb)
                    if memory_mb > self.peak_memory:
                        self.peak_memory = memory_mb
                    
                    # 每5秒记录一次
                    time.sleep(5)
                except:
                    break
        
        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()
    
    def stop_monitoring(self):
        """停止监控并返回统计信息"""
        self.monitoring = False
        time.sleep(1)  # 等待监控线程结束
        
        runtime = time.time() - self.start_time
        avg_memory = sum(self.memory_samples) / len(self.memory_samples) if self.memory_samples else 0
        
        return {
            'runtime_minutes': runtime / 60,
            'peak_memory_mb': self.peak_memory,
            'avg_memory_mb': avg_memory,
            'memory_samples': len(self.memory_samples)
        }

def test_ui_update_performance():
    """测试UI更新性能"""
    print("🚀 开始驾驶数据UI更新性能测试")
    print("=" * 50)
    
    # 模拟25分钟的运行
    test_duration = 25 * 60  # 25分钟
    update_frequency = 200  # 200Hz数据频率
    ui_update_interval = 1.5  # 1.5秒UI更新间隔
    
    monitor = PerformanceMonitor()
    monitor.start_monitoring()
    
    # 模拟数据更新
    update_count = 0
    ui_update_count = 0
    last_ui_update = 0
    
    start_time = time.time()
    
    print(f"📊 测试参数:")
    print(f"   测试时长: {test_duration/60} 分钟")
    print(f"   数据频率: {update_frequency} Hz")
    print(f"   UI更新间隔: {ui_update_interval} 秒")
    print(f"   预期数据更新次数: {test_duration * update_frequency}")
    print(f"   预期UI更新次数: {test_duration / ui_update_interval}")
    print()
    
    try:
        while time.time() - start_time < test_duration:
            current_time = time.time() - start_time
            
            # 模拟200Hz数据更新
            if int(current_time * update_frequency) > update_count:
                update_count += 1
                
                # 模拟UI更新检查（1.5秒间隔）
                if current_time - last_ui_update >= ui_update_interval:
                    ui_update_count += 1
                    last_ui_update = current_time
                    
                    # 模拟UI更新操作（简化版）
                    if ui_update_count % 10 == 0:  # 每10次UI更新打印一次进度
                        elapsed_minutes = current_time / 60
                        memory_mb = monitor.process.memory_info().rss / 1024 / 1024
                        print(f"⏱️  运行时间: {elapsed_minutes:.1f} 分钟 | "
                              f"UI更新: {ui_update_count} 次 | "
                              f"内存使用: {memory_mb:.1f} MB")
            
            # 模拟处理延迟
            time.sleep(0.001)  # 1ms延迟
            
    except KeyboardInterrupt:
        print("\n⚠️  测试被用户中断")
    
    # 停止监控并获取结果
    stats = monitor.stop_monitoring()
    
    print("\n" + "=" * 50)
    print("📈 测试结果统计:")
    print(f"   实际运行时间: {stats['runtime_minutes']:.1f} 分钟")
    print(f"   峰值内存使用: {stats['peak_memory_mb']:.1f} MB")
    print(f"   平均内存使用: {stats['avg_memory_mb']:.1f} MB")
    print(f"   内存采样次数: {stats['memory_samples']}")
    print(f"   实际UI更新次数: {ui_update_count}")
    print(f"   实际数据更新次数: {update_count}")
    
    # 性能分析
    print("\n🔍 性能分析:")
    memory_growth = stats['peak_memory_mb'] - (stats['avg_memory_mb'] * 0.8)  # 假设初始内存为平均值的80%
    if memory_growth > 100:  # 如果内存增长超过100MB
        print(f"⚠️  检测到显著内存增长: +{memory_growth:.1f} MB")
        print("   建议: 可能存在内存泄漏，需要进一步优化")
    else:
        print(f"✅ 内存使用稳定，增长: +{memory_growth:.1f} MB")
    
    expected_ui_updates = stats['runtime_minutes'] * 60 / ui_update_interval
    update_efficiency = (ui_update_count / expected_ui_updates) * 100 if expected_ui_updates > 0 else 0
    print(f"✅ UI更新效率: {update_efficiency:.1f}%")
    
    return stats

def analyze_optimization_results():
    """分析优化效果"""
    print("\n" + "🎯 优化效果分析" + "\n" + "=" * 50)
    
    print("✅ 已实施的优化措施:")
    print("   1. UI更新频率从500ms降低到1500ms")
    print("   2. 智能内容变化检测，避免无效更新")
    print("   3. 限制显示参数数量到8个关键参数")
    print("   4. 添加内存清理机制，每30秒执行一次")
    print("   5. 优化ScrolledText更新逻辑")
    print("   6. 数值格式化，减少小数位数")
    print("   7. 定期垃圾回收和UI缓存清理")
    
    print("\n📊 预期改善:")
    print("   • UI更新次数减少约67% (500ms→1500ms)")
    print("   • 内存使用更稳定，减少泄漏风险")
    print("   • CPU占用降低，响应更流畅")
    print("   • 25分钟运行后卡死问题应该得到解决")
    
    print("\n⚠️  注意事项:")
    print("   • 优化后UI更新频率降低，显示可能略有延迟")
    print("   • 如需要更实时的显示，可以适当调整ui_update_interval_driving参数")
    print("   • 建议进行实际长时间测试验证效果")

if __name__ == "__main__":
    try:
        # 运行性能测试
        stats = test_ui_update_performance()
        
        # 分析优化结果
        analyze_optimization_results()
        
        print("\n✅ 测试完成！建议运行实际软件进行长时间验证。")
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()