"""
驾驶多模态同步软件 - Tobii同步记录器 v16

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
- Tobii眼动仪数据同步和记录模块
- 支持Tobii Glasses眼动追踪数据的实时获取
- 提供数据同步缓冲机制
- 支持标记数据的接收和处理
- 集成PyQt5 GUI界面
- 支持视频流数据的处理和显示
"""

import sys
import os
import time
import json
import socket
import threading
import queue
from datetime import datetime
GUI_AVAILABLE = True
try:
    from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QMessageBox, QGroupBox
    from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QThread
    from PyQt5.QtGui import QImage, QPixmap, QPainter, QColor, QPen
except Exception:
    GUI_AVAILABLE = False
import gi
gi.require_version('Gst', '1.0')
gi.require_version('Gio', '2.0')
from gi.repository import Gst, GLib, Gio
import cairo

GLASSES_IP = "fe80::76fe:48ff:fe2e:24d8"
MY_IP = "fe80::74ac:3c53:94a0:8980"
SCOPE_ID = 11
MARKER_PORT = 50090

class DataSyncBuffer:
    def __init__(self):
        self.lock = threading.Lock()
        self.buffer = []
    def add_packet(self, packet):
        with self.lock:
            if 'ts' in packet:
                self.buffer.append(packet)
    def pop_data_up_to_now(self):
        with self.lock:
            data_chunk = list(self.buffer)
            self.buffer.clear()
            latest_gaze = None
            for pkt in reversed(data_chunk):
                if 'gp' in pkt:
                    latest_gaze = pkt['gp']
                    break
            return data_chunk, latest_gaze

class MarkerRecvThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.daemon = True
        self.running = True
        self.last_marker = None
        self.sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        self.sock.bind(("::1", MARKER_PORT, 0, 0))
        self.sock.settimeout(0.2)
    def run(self):
        while self.running:
            try:
                data, _ = self.sock.recvfrom(2048)
                try:
                    j = json.loads(data.decode('utf-8'))
                    self.last_marker = j
                except Exception:
                    pass
            except socket.timeout:
                continue
            except Exception:
                time.sleep(0.05)
    def stop(self):
        self.running = False
        try:
            self.sock.close()
        except Exception:
            pass

class EyeVideoThread(QThread):
    frame_signal = pyqtSignal(QImage, list)
    def __init__(self, sync_buffer, video_out, marker_src):
        super().__init__()
        self.sync = sync_buffer
        self.pipeline = None
        self.running = False
        self.video_out = video_out
        self._last_gaze = None
        self._w = None
        self._h = None
        self.marker_src = marker_src
    def run(self):
        Gst.init(None)
        try:
            inet = Gio.InetAddress.new_from_string(f"{MY_IP}%{int(SCOPE_ID)}")
            saddr = Gio.InetSocketAddress.new(inet, 0)
            self.gsock = Gio.Socket.new(Gio.SocketFamily.IPV6, Gio.SocketType.DATAGRAM, Gio.SocketProtocol.UDP)
            self.gsock.bind(saddr, True)
        except Exception as e:
            return
        launch_str = (
            'udpsrc name=src blocksize=1316 buffer-size=2097152 ! '
            'tsdemux ! h264parse ! avdec_h264 ! '
            'videoconvert ! cairooverlay name=ovl ! tee name=t '
            't. ! queue ! videoconvert ! video/x-raw,format=RGB ! appsink name=mysink emit-signals=True sync=False max-buffers=1 drop=True '
            f't. ! queue ! videoconvert ! x264enc tune=zerolatency speed-preset=ultrafast key-int-max=30 ! h264parse config-interval=-1 ! mp4mux ! filesink name=outsink location="{self.video_out}" '
        )
        try:
            self.pipeline = Gst.parse_launch(launch_str)
        except Exception:
            return
        src = self.pipeline.get_by_name('src')
        try:
            src.set_property('socket', self.gsock)
        except Exception:
            pass
        ovl = self.pipeline.get_by_name('ovl')
        try:
            ovl.connect("draw", self.on_draw_overlay)
            ovl.connect("caps-changed", self.on_caps_changed)
        except Exception:
            pass
        sink = self.pipeline.get_by_name('mysink')
        sink.connect("new-sample", self.on_new_sample)
        self.pipeline.set_state(Gst.State.PLAYING)
        self.running = True
        threading.Thread(target=self._video_keepalive, daemon=True).start()
        self.loop = GLib.MainLoop()
        try:
            self.loop.run()
        except Exception:
            pass
    def _video_keepalive(self):
        try:
            target_inet = Gio.InetAddress.new_from_string(f"{GLASSES_IP}%{int(SCOPE_ID)}")
            target = Gio.InetSocketAddress.new(target_inet, 49152)
        except Exception:
            return
        msg = json.dumps({"type":"live.video.unicast","key":"py","op":"start"}).encode('utf-8')
        while self.running:
            try:
                self.gsock.send_to(target, msg)
            except Exception:
                break
            time.sleep(1.0)
    def on_new_sample(self, sink):
        if not self.running:
            return Gst.FlowReturn.EOS
        sample = sink.emit("pull-sample")
        buf = sample.get_buffer()
        caps = sample.get_caps()
        data_chunk, latest_gaze = self.sync.pop_data_up_to_now()
        self._last_gaze = latest_gaze
        h = caps.get_structure(0).get_value("height")
        w = caps.get_structure(0).get_value("width")
        buffer = buf.extract_dup(0, buf.get_size())
        qimg = QImage(buffer, w, h, QImage.Format_RGB888)
        self.frame_signal.emit(qimg.copy(), latest_gaze if latest_gaze else [])
        return Gst.FlowReturn.OK
    def on_caps_changed(self, overlay, caps):
        try:
            s = caps.get_structure(0)
            self._w = s.get_value("width")
            self._h = s.get_value("height")
        except Exception:
            self._w = None
            self._h = None
    def on_draw_overlay(self, overlay, context, timestamp, duration):
        try:
            if self._last_gaze and self._w and self._h:
                gx, gy = self._last_gaze
                cx = int(gx * self._w)
                cy = int(gy * self._h)
                context.set_source_rgba(1.0, 0.0, 0.0, 1.0)
                context.set_line_width(3.0)
                context.arc(cx, cy, 10, 0, 2*3.1415926)
                context.stroke()
                context.move_to(cx-15, cy)
                context.line_to(cx+15, cy)
                context.move_to(cx, cy-15)
                context.line_to(cx, cy+15)
                context.stroke()
            m = getattr(self.marker_src, 'last_marker', None)
            if m:
                txt = m.get('label') or ''
                context.set_source_rgba(1.0, 1.0, 0.0, 1.0)
                context.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
                context.set_font_size(32)
                context.move_to(40, 60)
                context.show_text(txt)
        except Exception:
            pass
    def stop(self):
        self.running = False
        if self.pipeline:
            try:
                self.pipeline.send_event(Gst.Event.new_eos())
                bus = self.pipeline.get_bus()
                if bus:
                    bus.timed_pop_filtered(3_000_000_000, Gst.MessageType.EOS | Gst.MessageType.ERROR)
            except Exception:
                pass
            self.pipeline.set_state(Gst.State.NULL)
        if hasattr(self, 'loop'):
            self.loop.quit()

class EyeDataThread(threading.Thread):
    def __init__(self, sync_buffer):
        super().__init__()
        self.sync = sync_buffer
        self.running = True
        self.daemon = True
        self.sock_data = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        try:
            self.sock_data.bind((MY_IP, 0, 0, int(SCOPE_ID)))
        except Exception:
            pass
        self.sock_data.settimeout(0.1)
    def run(self):
        last_ka_time = 0
        while self.running:
            now = time.time()
            if now - last_ka_time > 1.0:
                try:
                    msg_bytes = json.dumps({"type":"live.data.unicast","key":"py","op":"start"}).encode('utf-8')
                    target = (GLASSES_IP, 49152, 0, int(SCOPE_ID))
                    self.sock_data.sendto(msg_bytes, target)
                    last_ka_time = now
                except Exception:
                    pass
            try:
                data, _ = self.sock_data.recvfrom(4096)
                try:
                    s = data.decode('utf-8')
                    json_obj = json.loads(s)
                    self.sync.add_packet(json_obj)
                except Exception:
                    pass
            except socket.timeout:
                continue
            except Exception as e:
                code = getattr(e, 'winerror', None)
                if code == 10038:
                    break
                if not self.running:
                    break
                time.sleep(0.1)
    def stop(self):
        self.running = False
        try:
            self.sock_data.close()
        except Exception:
            pass

class MainWindow(QWidget):
    def __init__(self, id_prefill=None, title=None, pos=None, base_prefill=None):
        super().__init__()
        self.setWindowTitle("Tobii Sync Recorder v16")
        if title:
            self.setWindowTitle(str(title))
        self.resize(1200, 800)
        self.init_ui()
        self.recording = False
        self.video_thread = None
        self.eye_thread = None
        self.sync_buffer = DataSyncBuffer()
        self.marker_thread = MarkerRecvThread()
        self.base_prefill = base_prefill
        try:
            if id_prefill:
                self.input_id.setText(str(id_prefill))
        except Exception:
            pass
        try:
            if base_prefill and (not id_prefill or str(id_prefill).upper() == 'S001'):
                self.input_id.setText(str(base_prefill))
        except Exception:
            pass
        try:
            if pos in ("left","right"):
                geo = QApplication.primaryScreen().availableGeometry()
                half_w = int(geo.width()/2)
                h = geo.height()
                if pos == "left":
                    self.setGeometry(geo.x(), geo.y(), half_w, h)
                else:
                    self.setGeometry(geo.x()+half_w, geo.y(), half_w, h)
        except Exception:
            pass
    def init_ui(self):
        main_layout = QVBoxLayout()
        control_box = QGroupBox("控制面板")
        h_layout = QHBoxLayout()
        self.input_id = QLineEdit()
        self.input_id.setPlaceholderText("被试 ID")
        self.btn_record = QPushButton("开始")
        self.btn_record.setFixedHeight(40)
        self.btn_record.clicked.connect(self.toggle_record)
        h_layout.addWidget(QLabel("被试:"))
        h_layout.addWidget(self.input_id)
        h_layout.addWidget(self.btn_record)
        control_box.setLayout(h_layout)
        self.lbl_video = QLabel("等待数据流...")
        self.lbl_video.setAlignment(Qt.AlignCenter)
        self.lbl_video.setMinimumSize(960, 540)
        self.lbl_status = QLabel("就绪")
        main_layout.addWidget(control_box)
        main_layout.addWidget(self.lbl_video, stretch=1)
        main_layout.addWidget(self.lbl_status)
        self.setLayout(main_layout)
    def toggle_record(self):
        if not self.recording:
            self.start_recording()
        else:
            self.stop_recording()
    def start_recording(self):
        sub_id = self.input_id.text().strip()
        if not sub_id:
            QMessageBox.warning(self, "提示", "请输入被试编号")
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_dir = os.path.dirname(os.path.abspath(__file__))
        save_dir = os.path.join(base_dir, "多模态驾驶指标保存")
        try:
            os.makedirs(save_dir, exist_ok=True)
        except Exception:
            pass
        if getattr(self, 'base_prefill', None):
            base = str(self.base_prefill).strip().replace('.csv', '')
            name = f"{base}_{ts}.mp4"
        else:
            name = f"record_{sub_id}_{ts}.mp4"
        video_out = os.path.join(save_dir, name)
        video_out_fs = video_out.replace('\\','/')
        try:
            self.marker_thread.start()
        except Exception:
            pass
        self.eye_thread = EyeDataThread(self.sync_buffer)
        self.eye_thread.start()
        self.video_thread = EyeVideoThread(self.sync_buffer, video_out_fs, self.marker_thread)
        self.video_thread.frame_signal.connect(self.update_display)
        self.video_thread.start()
        self.recording = True
        self.btn_record.setText("停止")
        self.input_id.setEnabled(False)
        self.lbl_status.setText(video_out)
    def stop_recording(self):
        if self.video_thread:
            self.video_thread.stop()
            self.video_thread.wait()
        if self.eye_thread:
            self.eye_thread.stop()
        if self.marker_thread:
            try:
                self.marker_thread.stop()
            except Exception:
                pass
        self.recording = False
        self.btn_record.setText("开始")
        self.input_id.setEnabled(True)
        self.lbl_status.setText("录制已完成")
        self.lbl_video.setText("视频已停止")
        self.lbl_video.setPixmap(QPixmap())
    @pyqtSlot(QImage, list)
    def update_display(self, qimg, gaze_point):
        if qimg.isNull():
            return
        pixmap = QPixmap.fromImage(qimg)
        if gaze_point:
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            w, h = pixmap.width(), pixmap.height()
            gx, gy = gaze_point[0], gaze_point[1]
            cx, cy = int(gx * w), int(gy * h)
            pen = QPen(QColor(255, 0, 0), 3)
            painter.setPen(pen)
            painter.drawEllipse(cx - 10, cy - 10, 20, 20)
            painter.drawLine(cx - 15, cy, cx + 15, cy)
            painter.drawLine(cx, cy - 15, cx, cy + 15)
            painter.end()
        scaled_pixmap = pixmap.scaled(self.lbl_video.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.lbl_video.setPixmap(scaled_pixmap)
    def closeEvent(self, event):
        if self.recording:
            self.stop_recording()
        event.accept()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--nogui", action="store_true")
    parser.add_argument("--id", default="S001")
    parser.add_argument("--title", default=None)
    parser.add_argument("--pos", default=None)
    parser.add_argument("--x", type=int, default=None)
    parser.add_argument("--y", type=int, default=None)
    parser.add_argument("--w", type=int, default=None)
    parser.add_argument("--h", type=int, default=None)
    parser.add_argument("--base", default=None)
    args = parser.parse_args()
    if args.nogui or not GUI_AVAILABLE:
        try:
            inet = Gio.InetAddress.new_from_string(f"{MY_IP}%{int(SCOPE_ID)}")
            saddr = Gio.InetSocketAddress.new(inet, 0)
            gsock = Gio.Socket.new(Gio.SocketFamily.IPV6, Gio.SocketType.DATAGRAM, Gio.SocketProtocol.UDP)
            gsock.bind(saddr, True)
            sync_buffer = DataSyncBuffer()
            marker_thread = MarkerRecvThread()
            marker_thread.start()
            eye_thread = EyeDataThread(sync_buffer)
            eye_thread.start()
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_dir = os.path.dirname(os.path.abspath(__file__))
            save_dir = os.path.join(base_dir, "多模态驾驶指标保存")
            try:
                os.makedirs(save_dir, exist_ok=True)
            except Exception:
                pass
            if args.base:
                base = str(args.base).strip().replace('.csv','')
                name = f"{base}_{ts}.mp4"
            else:
                name = f"record_{args.id}_{ts}.mp4"
            video_out = os.path.join(save_dir, name)
            video_out_fs = video_out.replace('\\','/')
            launch_str = (
                'udpsrc name=src blocksize=1316 buffer-size=2097152 ! '
                'tsdemux ! h264parse ! avdec_h264 ! '
                'videoconvert ! cairooverlay name=ovl ! tee name=t '
                f't. ! queue ! videoconvert ! x264enc tune=zerolatency speed-preset=ultrafast key-int-max=30 ! h264parse config-interval=-1 ! mp4mux ! filesink location="{video_out_fs}" '
            )
            pipeline = Gst.parse_launch(launch_str)
            src = pipeline.get_by_name('src')
            src.set_property('socket', gsock)
            ovl = pipeline.get_by_name('ovl')
            last_gaze = {"p": None, "w": None, "h": None}
            def on_caps_changed(overlay, caps):
                try:
                    s = caps.get_structure(0)
                    last_gaze["w"] = s.get_value("width")
                    last_gaze["h"] = s.get_value("height")
                except Exception:
                    last_gaze["w"] = None
                    last_gaze["h"] = None
            def on_draw_overlay(overlay, context, timestamp, duration):
                try:
                    p = last_gaze["p"]
                    if p and last_gaze["w"] and last_gaze["h"]:
                        gx, gy = p
                        cx = int(gx * last_gaze["w"])
                        cy = int(gy * last_gaze["h"])
                        context.set_source_rgba(1.0, 0.0, 0.0, 1.0)
                        context.set_line_width(3.0)
                        context.arc(cx, cy, 10, 0, 2*3.1415926)
                        context.stroke()
                        context.move_to(cx-15, cy)
                        context.line_to(cx+15, cy)
                        context.move_to(cx, cy-15)
                        context.line_to(cx, cy+15)
                        context.stroke()
                    m = getattr(marker_thread, 'last_marker', None)
                    if m:
                        txt = m.get('label') or ''
                        context.set_source_rgba(1.0, 1.0, 0.0, 1.0)
                        context.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
                        context.set_font_size(32)
                        context.move_to(40, 60)
                        context.show_text(txt)
                except Exception:
                    pass
            ovl.connect('caps-changed', on_caps_changed)
            ovl.connect('draw', on_draw_overlay)
            sink = pipeline.get_by_name('t')
            def update_gaze():
                try:
                    data_chunk, latest = sync_buffer.pop_data_up_to_now()
                    last_gaze["p"] = latest
                except Exception:
                    pass
                return True
            GLib.timeout_add(50, update_gaze)
            pipeline.set_state(Gst.State.PLAYING)
            loop = GLib.MainLoop()
            try:
                loop.run()
            except KeyboardInterrupt:
                pass
            try:
                pipeline.send_event(Gst.Event.new_eos())
                bus = pipeline.get_bus()
                if bus:
                    bus.timed_pop_filtered(3_000_000_000, Gst.MessageType.EOS | Gst.MessageType.ERROR)
            except Exception:
                pass
            pipeline.set_state(Gst.State.NULL)
            try:
                marker_thread.stop()
            except Exception:
                pass
        except Exception:
            sys.exit(1)
    else:
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
        app = QApplication(sys.argv)
        window = MainWindow(id_prefill=args.id, title=args.title, pos=args.pos, base_prefill=args.base)
        try:
            if args.w and args.h:
                x = args.x if args.x is not None else 0
                y = args.y if args.y is not None else 0
                window.setGeometry(x, y, int(args.w), int(args.h))
        except Exception:
            pass
        window.show()
        sys.exit(app.exec_())
