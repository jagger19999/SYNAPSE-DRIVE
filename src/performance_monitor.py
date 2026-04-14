#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
驾驶多模态同步软件 - 性能监控器

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
- 实时监控工具 - 用于跟踪90分钟实验的性能表现
- 提供内存使用监控和警告机制
- 支持CPU使用率监控
- 记录性能数据并生成监控报告
- 支持UI更新频率统计
- 提供缓存刷新时间跟踪
"

import time
import psutil
import threading
import json
from datetime import datetime

class PerformanceMonitor:
    def __init__(self, log_callback=None):
        self.process = psutil.Process()
        self.log_callback = log_callback or print
        self.monitoring = False
        self.start_time = time.time()
        self.peak_memory = 0
        self.memory_samples = []
        self.cache_flush_times = []
        self.ui_update_counts = {
            'driving': 0,
            'biosig': 0,
            'eye': 0
        }
        
    def start_monitoring(self, interval=5):
        """开始性能监控"""
        self.monitoring = True
        self.log_callback(f"[性能监控] 开始监控，采样间隔: {interval}秒")
        
        def monitor_loop():
            while self.monitoring:
                try:
                    # 获取内存使用
                    memory_mb = self.process.memory_info().rss / 1024 / 1024
                    self.memory_samples.append({
                        'time': time.time() - self.start_time,
                        'memory': memory_mb
                    })
                    
                    if memory_mb > self.peak_memory:
                        self.peak_memory = memory_mb
                    
                    # 检查是否内存异常
                    if memory_mb > 3000:  # 超过3GB警告
                        self.log_callback(f"⚠️ [内存警告] 内存使用过高: {memory_mb:.1f} MB")
                    
                    # 检查系统整体性能
                    cpu_percent = self.process.cpu_percent()
                    if cpu_percent > 80:  # CPU占用过高
                        self.log_callback(f"⚠️ [CPU警告] CPU占用过高: {cpu_percent:.1f}%")
                    
                    time.sleep(interval)
                    
                except Exception as e:
                    self.log_callback(f"⚠️ [监控错误] {e}")
                    time.sleep(interval)
        
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
    
    def stop_monitoring(self):
        """停止监控并生成报告"""
        self.monitoring = False
        time.sleep(1)
        
        runtime = time.time() - self.start_time
        avg_memory = sum(s['memory'] for s in self.memory_samples) / len(self.memory_samples) if self.memory_samples else 0
        
        report = {
            'runtime_minutes': runtime / 60,
            'peak_memory_mb': self.peak_memory,
            'avg_memory_mb': avg_memory,
            'memory_samples': len(self.memory_samples),
            'ui_updates': self.ui_update_counts,
            'cache_flushes': len(self.cache_flush_times),
            'memory_trend': self._analyze_memory_trend(),
            'performance_score': self._calculate_performance_score()
        }
        
        self._print_report(report)
        return report
    
    def record_ui_update(self, ui_type):
        """记录UI更新"""
        if ui_type in self.ui_update_counts:
            self.ui_update_counts[ui_type] += 1
    
    def record_cache_flush(self, duration, data_size):
        """记录缓存刷新"""
        self.cache_flush_times.append({
            'time': time.time() - self.start_time,
            'duration': duration,
            'size': data_size
        })
    
    def _analyze_memory_trend(self):
        """分析内存趋势"""
        if len(self.memory_samples) < 10:
            return "insufficient_data"
        
        # 取最近10个样本
        recent_samples = self.memory_samples[-10:]
        early_avg = sum(s['memory'] for s in self.memory_samples[:10]) / 10
        recent_avg = sum(s['memory'] for s in recent_samples) / 10
        
        growth_rate = (recent_avg - early_avg) / early_avg * 100
        
        if growth_rate > 50:
            return "rapid_growth"
        elif growth_rate > 20:
            return "moderate_growth"
        elif growth_rate > -10:
            return "stable"
        else:
            return "declining"
    
    def _calculate_performance_score(self):
        """计算性能评分"""
        score = 100
        
        # 内存使用扣分
        if self.peak_memory > 2000:  # 超过2GB
            score -= 30
        elif self.peak_memory > 1500:  # 超过1.5GB
            score -= 20
        elif self.peak_memory > 1000:  # 超过1GB
            score -= 10
        
        # 内存趋势扣分
        trend = self._analyze_memory_trend()
        if trend == "rapid_growth":
            score -= 25
        elif trend == "moderate_growth":
            score -= 15
        
        return max(0, score)
    
    def _print_report(self, report):
        """打印性能报告"""
        self.log_callback("\n" + "="*60)
        self.log_callback("📊 90分钟实验性能监控报告")
        self.log_callback("="*60)
        
        self.log_callback(f"⏱️  运行时间: {report['runtime_minutes']:.1f} 分钟")
        self.log_callback(f"💾 峰值内存: {report['peak_memory_mb']:.1f} MB")
        self.log_callback(f"💾 平均内存: {report['avg_memory_mb']:.1f} MB")
        self.log_callback(f"📈 内存趋势: {report['memory_trend']}")
        
        self.log_callback(f"\n🖥️ UI更新统计:")
        for ui_type, count in report['ui_updates'].items():
            self.log_callback(f"   {ui_type}: {count:,} 次")
        
        self.log_callback(f"\n🔄 缓存刷新: {report['cache_flushes']} 次")
        if report['cache_flushes'] > 0:
            avg_flush_size = sum(cf['size'] for cf in self.cache_flush_times) / len(self.cache_flush_times)
            avg_flush_time = sum(cf['duration'] for cf in self.cache_flush_times) / len(self.cache_flush_times)
            self.log_callback(f"   平均刷新大小: {avg_flush_size:.0f} 条记录")
            self.log_callback(f"   平均刷新时间: {avg_flush_time:.2f} 秒")
        
        self.log_callback(f"\n🎯 性能评分: {report['performance_score']}/100")
        
        if report['performance_score'] >= 80:
            self.log_callback("✅ 性能优秀，可以支持90分钟实验")
        elif report['performance_score'] >= 60:
            self.log_callback("⚠️  性能一般，建议进一步优化")
        else:
            self.log_callback("❌ 性能较差，需要立即优化")
        
        self.log_callback("="*60)

# 使用示例
if __name__ == "__main__":
    monitor = PerformanceMonitor()
    monitor.start_monitoring(interval=2)
    
    # 模拟一些数据
    for i in range(10):
        monitor.record_ui_update('driving')
        if i % 3 == 0:
            monitor.record_cache_flush(0.5, 5000)
        time.sleep(1)
    
    monitor.stop_monitoring()