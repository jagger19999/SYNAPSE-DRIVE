#!/usr/bin/env python3
"""
清理Python字节码缓存文件脚本
递归删除所有__pycache__目录和.pyc文件
"""

import os
import shutil
import sys
from pathlib import Path

def clean_pycache(directory):
    """清理指定目录下的所有__pycache__和.pyc文件"""
    deleted_dirs = []
    deleted_files = []
    
    for root, dirs, files in os.walk(directory):
        # 删除__pycache__目录
        for dir_name in dirs[:]:
            if dir_name == '__pycache__':
                pycache_path = os.path.join(root, dir_name)
                try:
                    shutil.rmtree(pycache_path)
                    deleted_dirs.append(pycache_path)
                    print(f"已删除目录: {pycache_path}")
                except Exception as e:
                    print(f"删除目录失败 {pycache_path}: {e}")
                dirs.remove(dir_name)  # 防止继续遍历已删除的目录
        
        # 删除.pyc文件
        for file_name in files:
            if file_name.endswith('.pyc'):
                pyc_path = os.path.join(root, file_name)
                try:
                    os.remove(pyc_path)
                    deleted_files.append(pyc_path)
                    print(f"已删除文件: {pyc_path}")
                except Exception as e:
                    print(f"删除文件失败 {pyc_path}: {e}")
    
    return deleted_dirs, deleted_files

def main():
    # 获取当前脚本所在目录作为项目根目录
    project_root = os.path.dirname(os.path.abspath(__file__))
    
    print(f"开始清理Python字节码缓存文件...")
    print(f"项目根目录: {project_root}")
    print("-" * 50)
    
    deleted_dirs, deleted_files = clean_pycache(project_root)
    
    print("-" * 50)
    print(f"清理完成！")
    print(f"删除的__pycache__目录数量: {len(deleted_dirs)}")
    print(f"删除的.pyc文件数量: {len(deleted_files)}")
    
    if deleted_dirs or deleted_files:
        print("\n删除的目录列表:")
        for dir_path in deleted_dirs:
            print(f"  - {dir_path}")
        
        print("\n删除的文件列表 (前10个):")
        for i, file_path in enumerate(deleted_files[:10]):
            print(f"  - {file_path}")
        
        if len(deleted_files) > 10:
            print(f"  ... 还有 {len(deleted_files) - 10} 个文件")
    else:
        print("没有找到需要清理的Python字节码缓存文件。")

if __name__ == "__main__":
    main()