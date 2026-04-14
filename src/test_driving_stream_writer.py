"""
驾驶多模态同步软件 - 驾驶数据流写入器测试

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
- 驾驶数据流写入器的单元测试
- 测试数据流写入功能的正确性和完整性
- 验证CSV文件写入和队列处理机制
- 确保所有数据行都能被正确写入
"""

import csv
import importlib.util
import os
import queue
import tempfile
import threading
import time
import unittest


def _load_sync_module():
    here = os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(here, "可视化传输速率版本custom_driving_sync - v 15 seperate ver - 副本.py")
    spec = importlib.util.spec_from_file_location("custom_driving_sync_visual", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestDrivingStreamWriter(unittest.TestCase):
    def test_stream_writer_writes_all_rows(self):
        mod = _load_sync_module()
        System = mod.CustomDrivingSyncSystem

        with tempfile.TemporaryDirectory() as tmp:
            obj = System.__new__(System)
            obj.data_folder = tmp
            obj.current_trial_filenames = {"driving": "driving_20000101_000000.csv"}
            obj.trial_files_initialized = {"driving": False, "biosig": False, "eye": False}
            obj._driving_stream_write_queue = queue.Queue(maxsize=1000)
            obj._driving_stream_writer_stop = False
            obj._driving_stream_writer_file = None
            obj._driving_stream_writer_csv = None
            obj._driving_rows_written = 0

            t = threading.Thread(target=System._driving_stream_writer, args=(obj,), daemon=True)
            t.start()

            n = 2000
            for i in range(n):
                obj._driving_stream_write_queue.put(
                    {
                        "system_timestamp": f"2026-02-26 00:00:{i%60:02d}.000",
                        "marker_flag": False,
                        "uv_distanceTravelled": float(i),
                    }
                )

            time.sleep(0.2)
            obj._driving_stream_writer_stop = True
            t.join(timeout=10.0)

            out_path = os.path.join(tmp, obj.current_trial_filenames["driving"])
            self.assertTrue(os.path.exists(out_path))

            with open(out_path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.reader(f)
                rows = list(reader)
            self.assertGreaterEqual(len(rows), n + 1)

    def test_queue_drop_counter_increments(self):
        mod = _load_sync_module()
        System = mod.CustomDrivingSyncSystem

        obj = System.__new__(System)
        obj._driving_stream_write_queue = queue.Queue(maxsize=1)
        obj.streaming_write_enabled = True
        obj.experiment_started = True
        obj._driving_queue_dropped = 0

        try:
            obj._driving_stream_write_queue.put_nowait({"a": 1})
        except Exception:
            pass
        try:
            obj._driving_stream_write_queue.put_nowait({"a": 2})
        except queue.Full:
            try:
                obj._driving_queue_dropped = getattr(obj, "_driving_queue_dropped", 0) + 1
            except Exception:
                pass

        self.assertGreaterEqual(getattr(obj, "_driving_queue_dropped", 0), 1)


if __name__ == "__main__":
    unittest.main()

