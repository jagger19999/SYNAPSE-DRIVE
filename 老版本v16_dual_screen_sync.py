import sys
import os
import subprocess
import shutil
def _ensure_env_and_runtime():
    p = os.environ.get('Path', '')
    is_msys = ('msys64' in sys.executable.lower()) or os.path.exists(r'C:\msys64\mingw64\bin\libglib-2.0-0.dll')
    if is_msys:
        msysbin = r'C:\msys64\mingw64\bin'
        tlib3 = r'C:\msys64\mingw64\lib\girepository-1.0'
        gst_plugins = r'C:\msys64\mingw64\lib\gstreamer-1.0'
        gst_scanner = os.path.join(gst_plugins, 'gst-plugin-scanner.exe')
        if msysbin not in p:
            p = msysbin + ';' + p
        os.environ['Path'] = p
        gi_path = os.environ.get('GI_TYPELIB_PATH', '')
        if tlib3 not in gi_path:
            gi_path = (gi_path + ';' if gi_path else '') + tlib3
        os.environ['GI_TYPELIB_PATH'] = gi_path
        # 设定 GStreamer 插件目录，确保 udpsrc/tsparse 可加载
        gp = os.environ.get('GST_PLUGIN_PATH', '')
        if gst_plugins not in gp:
            gp = (gp + ';' if gp else '') + gst_plugins
        os.environ['GST_PLUGIN_PATH'] = gp
        os.environ['GST_PLUGIN_SYSTEM_PATH_1_0'] = gst_plugins
        if os.path.exists(gst_scanner):
            os.environ['GST_PLUGIN_SCANNER'] = gst_scanner
        try:
            os.add_dll_directory(msysbin)
        except Exception:
            pass
        # 不强制重启版本，避免切换到 CPython 3.14
        return
    if not (sys.version_info.major == 3 and sys.version_info.minor == 14):
        script = os.path.abspath(__file__)
        if shutil.which('py'):
            try:
                subprocess.Popen(['py', '-3.14', script], shell=False)
                os._exit(0)
            except Exception:
                pass
    gbin = r'C:\gtk\bin'
    gstbin = r'C:\Program Files\gstreamer\1.0\msvc_x86_64\bin'
    tlib1 = r'C:\gtk\lib\girepository-1.0'
    tlib2 = r'C:\Program Files\gstreamer\1.0\msvc_x86_64\lib\girepository-1.0'
    parts = [gbin, gstbin]
    for d in parts:
        if d and d not in p:
            p = d + ';' + p
    os.environ['Path'] = p
    gi_path = os.environ.get('GI_TYPELIB_PATH', '')
    gp = [tlib1, tlib2]
    for d in gp:
        if d and d not in gi_path:
            gi_path = (gi_path + ';' if gi_path else '') + d
    os.environ['GI_TYPELIB_PATH'] = gi_path
    try:
        os.add_dll_directory(gbin)
    except Exception:
        pass
    try:
        os.add_dll_directory(gstbin)
    except Exception:
        pass
_ensure_env_and_runtime()
import cairo
import time
import json
import socket
import threading
import queue
import csv
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QGroupBox, QCheckBox, QComboBox
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QThread
from PyQt5.QtGui import QImage, QPixmap, QMouseEvent, QCursor, QPainter, QColor, QPen
try:
    import pyautogui
    pyautogui.FAILSAFE = False
    HAVE_PYAUTOGUI = True
except Exception:
    HAVE_PYAUTOGUI = False
import gi
gi.require_version('Gst', '1.0')
gi.require_version('Gio', '2.0')
from gi.repository import Gst, GLib, Gio

# 与主采集程序(custom_driving_sync)一致的保存根目录，眼动/屏幕录制视频与 CSV 存同一路径
# 可通过环境变量 MULTIMODAL_SAVE_DIR 覆盖，例如 set MULTIMODAL_SAVE_DIR=E:\多模态驾驶指标保存
_SAVE_ROOT = os.environ.get("MULTIMODAL_SAVE_DIR", os.path.join("D:\\", "多模态驾驶指标保存"))

GLASSES_IP = "fe80::76fe:48ff:fe2e:24d8"
MY_IP = "fe80::74ac:3c53:94a0:8980"
SCOPE_ID = 11
TOBII_PORT = 49152
KA_MSG = {"type": "live.data.unicast", "key": "py", "op": "start"}
KA_VIDEO_MSG = {"type": "live.video.unicast", "key": "py", "op": "start"}
APP_FALLBACK_ALLOWED = True
PREFER_APP_SRC = False

try:
    if HAVE_PYAUTOGUI:
        pyautogui.FAILSAFE = False
except Exception:
    pass

class ScreenRecorderThread(QThread):
    frame_signal = pyqtSignal(QImage)
    def __init__(self, monitor_idx=1, filename=None, fps=60):
        super().__init__()
        self.monitor_idx = monitor_idx
        self.filename = filename
        self.fps = fps
        self.running = False
        self.pipeline = None
        self.appsrc = None
        self._w = None
        self._h = None
        self.recording = False
    def _choose_h264_encoder(self):
        try:
            if Gst.ElementFactory.find('x264enc'):
                return 'x264enc', ' tune=zerolatency speed-preset=ultrafast key-int-max=30', False
        except Exception:
            pass
        try:
            if Gst.ElementFactory.find('avenc_h264'):
                return 'avenc_h264', '', False
        except Exception:
            pass
        try:
            if Gst.ElementFactory.find('openh264enc'):
                return 'openh264enc', '', True
        except Exception:
            pass
        return None, '', False
    def _init_pipeline(self, w, h):
        Gst.init(None)
        enc, enc_opts, need_i420 = self._choose_h264_encoder()
        if not enc:
            enc = 'avenc_h264'
            enc_opts = ''
            need_i420 = False
        conv_caps = 'video/x-raw,format=I420' if need_i420 else ''
        mid = ('videoconvert ! ' + (conv_caps + ' ! ' if conv_caps else ''))
        launch = (
            'appsrc name=src format=time is-live=true block=true caps=video/x-raw,format=RGB,width={w},height={h},framerate={fps}/1 ! '
            + mid + '{enc}{opts} ! h264parse config-interval=-1 ! mp4mux ! filesink name=f location="{out}"'
        ).format(w=w, h=h, fps=self.fps, out=(self.filename or 'screen_rec.mp4').replace('\\','/'), enc=enc, opts=enc_opts)
        self.pipeline = Gst.parse_launch(launch)
        self.appsrc = self.pipeline.get_by_name('src')
        self.pipeline.set_state(Gst.State.PLAYING)
        self.recording = True
    def run(self):
        from PyQt5.QtWidgets import QApplication
        screens = QApplication.screens()
        idx = max(0, min(self.monitor_idx-1, len(screens)-1))
        screen = screens[idx]
        geom = screen.geometry()
        self._w, self._h = geom.width(), geom.height()
        self.running = True
        frame_interval = 1.0 / float(self.fps)
        while self.running:
            t0 = time.time()
            pm = screen.grabWindow(0)
            qimg = pm.toImage().convertToFormat(QImage.Format_RGB888)
            try:
                gp = QCursor.pos()
                lx = max(0, min(self._w-1, gp.x() - geom.x()))
                ly = max(0, min(self._h-1, gp.y() - geom.y()))
                painter = QPainter(qimg)
                painter.setRenderHint(QPainter.Antialiasing)
                pen = QPen(QColor(0, 255, 0), 4)
                painter.setPen(pen)
                painter.drawEllipse(lx - 22, ly - 22, 44, 44)
                painter.drawLine(lx - 18, ly, lx + 18, ly)
                painter.drawLine(lx, ly - 18, lx, ly + 18)
                painter.end()
            except Exception:
                pass
            self.frame_signal.emit(qimg.copy())
            try:
                if self.recording and self.appsrc is not None:
                    b = qimg.bits()
                    b.setsize(qimg.byteCount())
                    data = bytes(b)
                    buf = Gst.Buffer.new_allocate(None, len(data), None)
                    buf.fill(0, data)
                    now = int(time.time()*1e9)
                    buf.pts = now
                    buf.dts = now
                    buf.duration = int(frame_interval*1e9)
                    self.appsrc.emit('push-buffer', buf)
            except Exception:
                pass
            dt = time.time() - t0
            time.sleep(max(0.001, frame_interval - dt))
        try:
            if self.pipeline:
                self.pipeline.send_event(Gst.Event.new_eos())
                bus = self.pipeline.get_bus()
                if bus:
                    bus.timed_pop_filtered(3_000_000_000, Gst.MessageType.EOS | Gst.MessageType.ERROR)
                self.pipeline.set_state(Gst.State.NULL)
        except Exception:
            pass
    def stop(self):
        self.running = False
        self.wait()
    def start_recording(self, filename):
        try:
            self.filename = filename
            if self._w is not None and self._h is not None:
                self._init_pipeline(self._w, self._h)
        except Exception:
            pass
    def stop_recording(self):
        try:
            self.recording = False
            if self.pipeline:
                self.pipeline.send_event(Gst.Event.new_eos())
                bus = self.pipeline.get_bus()
                if bus:
                    bus.timed_pop_filtered(3_000_000_000, Gst.MessageType.EOS | Gst.MessageType.ERROR)
                self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
            self.appsrc = None
        except Exception:
            self.pipeline = None
            self.appsrc = None
    def get_monitor_offset(self):
        try:
            from PyQt5.QtWidgets import QApplication
            screens = QApplication.screens()
            idx = max(0, min(self.monitor_idx-1, len(screens)-1))
            geom = screens[idx].geometry()
            return geom.x(), geom.y(), geom.width(), geom.height()
        except Exception:
            return 0, 0, self._w or 1920, self._h or 1080

class ScreenControlLabel(QLabel):
    def __init__(self, parent_thread):
        super().__init__("等待驾驶画面...")
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background: #222; color: #AAA; border: 1px solid #555;")
        self.setMinimumSize(640, 360)
        self.control_enabled = False
        self.recorder = parent_thread
    def set_control_active(self, active):
        self.control_enabled = active
        if active:
            self.setCursor(Qt.CrossCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        # 录制边框在主控逻辑中设置
    def mousePressEvent(self, event: QMouseEvent):
        if self.control_enabled and event.button() == Qt.LeftButton and self.recorder:
            lx = event.x(); ly = event.y(); ww = self.width(); hh = self.height()
            nx = lx / max(1, ww); ny = ly / max(1, hh)
            ml, mt, mw, mh = self.recorder.get_monitor_offset()
            tx = int(ml + nx * mw); ty = int(mt + ny * mh)
            if HAVE_PYAUTOGUI:
                try:
                    import pyautogui as _p
                    _p.click(tx, ty)
                except Exception:
                    pass
        super().mousePressEvent(event)

class AsyncCSVWriter:
    def __init__(self, filepath, headers):
        self.filepath = filepath
        self.queue = queue.Queue()
        self.running = True
        self.headers = headers
        threading.Thread(target=self._worker, daemon=True).start()
    def write(self, row):
        self.queue.put(row)
    def _worker(self):
        with open(self.filepath, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(self.headers)
            while self.running or not self.queue.empty():
                try:
                    n = min(50, self.queue.qsize())
                    rows = [self.queue.get() for _ in range(n)]
                    if rows:
                        w.writerows(rows)
                    else:
                        time.sleep(0.01)
                except:
                    pass
    def stop(self):
        self.running = False

class VideoRecorder:
    def __init__(self, filename, w, h, fps=30):
        self.filename = filename
        self.w = w
        self.h = h
        self.fps = fps
        self.pipeline = None
        self.appsrc = None
        self.running = False
    def _choose_encoder(self):
        try:
            if Gst.ElementFactory.find('x264enc'):
                return 'x264enc', ' tune=zerolatency speed-preset=ultrafast key-int-max=30'
        except Exception:
            pass
        try:
            if Gst.ElementFactory.find('avenc_h264'):
                return 'avenc_h264', ''
        except Exception:
            pass
        try:
            if Gst.ElementFactory.find('openh264enc'):
                return 'openh264enc', ' gop-size=30'
        except Exception:
            pass
        return 'avenc_h264', ''
    def start(self):
        Gst.init(None)
        enc, opts = self._choose_encoder()
        need_i420 = (enc == 'openh264enc')
        conv_caps = 'video/x-raw,format=I420' if need_i420 else ''
        mid = 'videoconvert'
        if conv_caps:
            mid += ' ! ' + conv_caps
        outfs = (self.filename or 'eye_rec.mp4').replace('\\','/')
        launch = (
            'appsrc name=src format=time is-live=true block=true caps=video/x-raw,format=RGB,width={w},height={h},framerate={fps}/1 ! '
            + mid + ' ! ' + enc + opts + ' ! h264parse config-interval=-1 ! mp4mux ! filesink location="{out}" sync=false async=false'
        ).format(w=self.w, h=self.h, fps=self.fps, out=outfs)
        self.pipeline = Gst.parse_launch(launch)
        self.appsrc = self.pipeline.get_by_name('src')
        self.pipeline.set_state(Gst.State.PLAYING)
        self.running = True
    def push(self, data):
        try:
            if not self.appsrc:
                return
            buf = Gst.Buffer.new_allocate(None, len(data), None)
            buf.fill(0, data)
            now = int(time.time()*1e9)
            buf.pts = now
            buf.dts = now
            self.appsrc.emit('push-buffer', buf)
        except Exception:
            pass
    def stop(self):
        try:
            if self.pipeline:
                self.pipeline.send_event(Gst.Event.new_eos())
                bus = self.pipeline.get_bus()
                if bus:
                    bus.timed_pop_filtered(3_000_000_000, Gst.MessageType.EOS | Gst.MessageType.ERROR)
                self.pipeline.set_state(Gst.State.NULL)
        except Exception:
            pass
        self.pipeline = None
        self.appsrc = None
        self.running = False
class FullTobiiThread(QThread):
    frame_signal = pyqtSignal(QImage, list)
    status_signal = pyqtSignal(str)
    def __init__(self, csv_path=None, video_out=None, sync_buffer=None, record=False):
        super().__init__()
        self.writer = AsyncCSVWriter(csv_path, ['Video_PTS', 'glassts', 'marker_flag', 'marker_type', 'marker_condition', 'marker_target', 'marker_color', 'marker_label', 'Gaze_TS', 'Gaze_X', 'Gaze_Y']) if record and csv_path else None
        self.running = False
        self.pipeline = None
        self.video_out = video_out
        self._last_gaze = None
        self._w = None
        self._h = None
        self._sync = sync_buffer
        self._record = record
        self.vsock = None
        self._got_first_frame = False
        self._gaze_smooth = None
        self._gaze_last_ts = 0.0
        self._last_eye_ts = ''
        self._ts_acc = bytearray()
        self.recorder = None
        try:
            self.app_fallback_allowed = APP_FALLBACK_ALLOWED
        except Exception:
            self.app_fallback_allowed = True
    def run(self):
        Gst.init(None)
        try:
            if not Gst.ElementFactory.find('udpsrc'):
                try:
                    self.status_signal.emit("eye_error=未找到udpsrc插件")
                except Exception:
                    pass
                try:
                    reg = Gst.Registry.get()
                    plugdir = os.environ.get('GST_PLUGIN_PATH', r'C:\msys64\mingw64\lib\gstreamer-1.0')
                    reg.scan_path(plugdir)
                except Exception:
                    pass
            if not Gst.ElementFactory.find('udpsrc'):
                try:
                    self.app_fallback_allowed = True
                    self.status_signal.emit("eye_error=udpsrc不可用，启用appsrc回退")
                except Exception:
                    pass
        except Exception:
            pass
        enc = 'x264enc' if Gst.ElementFactory.find('x264enc') else ('avenc_h264' if Gst.ElementFactory.find('avenc_h264') else 'openh264enc')
        need_i420 = True if enc == 'openh264enc' else False
        conv_caps = 'video/x-raw,format=I420' if need_i420 else ''
        has_tsparse = True if Gst.ElementFactory.find('tsparse') else False
        rec_branch = None
        use_udp_src = not PREFER_APP_SRC
        # 预热心跳，促使设备尽快回推视频
        try:
            self._send_video_ka_burst(count=5, interval=0.12)
        except Exception:
            pass
        try:
            self.vsock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
            try:
                self.vsock.bind((MY_IP, 0, 0, int(SCOPE_ID)))
                try:
                    self.status_signal.emit("eye_vsock_bind=ok")
                except Exception:
                    pass
            except Exception:
                self.vsock = None
                try:
                    self.status_signal.emit("eye_vsock_bind=fail")
                except Exception:
                    pass
            if self.vsock:
                try:
                    self.vsock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
                except Exception:
                    pass
        except Exception:
            self.vsock = None
        try:
            self.gsock = None
            try:
                self.status_signal.emit("eye_gsock_bind=-")
            except Exception:
                pass
        except Exception:
            self.gsock = None
        set_ok = False
        self._ka_use = None
        if use_udp_src:
            try:
                tsparse_chain = 'tsparse set-timestamps=true smoothing-latency=100000 split-on-rai=true alignment=7 ! '
                launch = (
                    'udpsrc name=src blocksize=1316 close-socket=false buffer-size=2097152 caps=video/mpegts,systemstream=true,packetsize=188 ! '
                    + ((tsparse_chain + 'tsdemux emit-stats=true ! queue ! ') if has_tsparse else 'tsdemux emit-stats=true ! queue ! ')
                    + 'h264parse config-interval=-1 ! avdec_h264 ! videoconvert ! cairooverlay name=ovl ! tee name=t allow-not-linked=true '
                    + 't. ! queue ! videoconvert ! video/x-raw,format=RGB ! appsink name=sink emit-signals=True sync=False drop=True max-buffers=1 '
                    + (('t. ! queue ! ' + rec_branch) if rec_branch else '')
                )
                self.pipeline = Gst.parse_launch(launch)
                src = self.pipeline.get_by_name('src')
                if src is not None:
                    if self.vsock is not None:
                        try:
                            gs = Gio.Socket.new_from_fd(self.vsock.fileno())
                            src.set_property('socket', gs)
                            set_ok = True
                            self._ka_use = 'vsock'
                        except Exception:
                            try:
                                src.set_property('sockfd', self.vsock.fileno())
                                set_ok = True
                                self._ka_use = 'vsock'
                            except Exception:
                                set_ok = False
                    # 不使用独立 gsock 回退，确保与心跳端口一致
                    # 端口绑定回退：无法设置 sockfd/socket 时，使用指定端口接收
                    if not set_ok:
                        try:
                            # 创建心跳专用socket并绑定端口
                            self.ka_sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
                            self.ka_sock.bind((MY_IP, 0, 0, int(SCOPE_ID)))
                            lp = self.ka_sock.getsockname()[1]
                            try:
                                src.set_property('port', int(lp))
                                set_ok = True
                                self._ka_use = f'port:{lp}'
                            except Exception:
                                set_ok = False
                        except Exception:
                            set_ok = False
            except Exception:
                set_ok = False
            try:
                if set_ok and self._ka_use:
                    self.status_signal.emit(f"eye_live_use={self._ka_use}")
            except Exception:
                pass
        if not set_ok:
            try:
                if self.pipeline:
                    self.pipeline.set_state(Gst.State.NULL)
            except Exception:
                pass
            self.pipeline = None
            try:
                self.app_fallback_allowed = True
            except Exception:
                pass
            if self.app_fallback_allowed:
                try:
                    tsparse_chain = 'tsparse set-timestamps=true smoothing-latency=100000 split-on-rai=true alignment=7 ! '
                    launch = (
                        'appsrc name=tsapp format=time is-live=true block=true do-timestamp=true caps=video/mpegts,systemstream=true,packetsize=188 ! '
                        + 'queue max-size-buffers=0 max-size-time=0 max-size-bytes=0 leaky=2 ! '
                        + ((tsparse_chain + 'tsdemux emit-stats=true ! queue leaky=2 ! ') if has_tsparse else 'tsdemux emit-stats=true ! queue leaky=2 ! ')
                        + 'h264parse config-interval=-1 ! avdec_h264 ! videoconvert ! cairooverlay name=ovl ! tee name=t allow-not-linked=true '
                        + 't. ! queue ! videoconvert ! video/x-raw,format=RGB ! appsink name=sink emit-signals=True sync=False drop=True max-buffers=1 '
                        + (('t. ! queue ! ' + rec_branch) if rec_branch else '')
                    )
                    self.pipeline = Gst.parse_launch(launch)
                    self.appsrc_ts = self.pipeline.get_by_name('tsapp')
                    self._ka_use = 'vsock' if self.vsock is not None else ('gsock' if self.gsock is not None else None)
                    try:
                        self.status_signal.emit("eye_live_use=appsrc")
                    except Exception:
                        pass
                except Exception:
                    return
            else:
                try:
                    self.status_signal.emit("eye_error=udpsrc未可用，禁用appsrc回退")
                except Exception:
                    pass
                return
        sink = self.pipeline.get_by_name('sink')
        sink.connect("new-sample", self.on_new_sample)
        ovl = self.pipeline.get_by_name('ovl')
        try:
            ovl.connect('caps-changed', self.on_caps_changed)
            ovl.connect('draw', self.on_draw_overlay)
        except Exception:
            pass
        # 预热心跳：快速发送一组视频心跳，确保设备尽快推流
        try:
            self._send_video_ka_burst(count=5, interval=0.12)
        except Exception:
            pass
        self.running = True
        threading.Thread(target=self.keep_alive_worker, daemon=True).start()
        if hasattr(self, 'appsrc_ts') and self.appsrc_ts is not None and self.vsock is not None:
            threading.Thread(target=self.udp_recv_worker, daemon=True).start()
        bus = self.pipeline.get_bus()
        if bus:
            bus.add_signal_watch()
            bus.connect("message", self.on_bus_message)
        self.pipeline.set_state(Gst.State.PLAYING)
        self.loop = GLib.MainLoop()
        try:
            self.loop.run()
        except Exception:
            pass
    def _send_video_ka_burst(self, count=3, interval=0.15):
        try:
            msg_video = json.dumps(KA_VIDEO_MSG).encode('utf-8')
            use = getattr(self, '_ka_use', None)
            if use == 'gsock' and getattr(self, 'gsock', None) is not None:
                target_inet = Gio.InetAddress.new_from_string(f"{GLASSES_IP}%{int(SCOPE_ID)}")
                target = Gio.InetSocketAddress.new(target_inet, TOBII_PORT)
                for _ in range(max(1, int(count))):
                    try:
                        self.gsock.send_to(target, msg_video)
                    except Exception:
                        break
                    time.sleep(max(0.01, float(interval)))
            elif use == 'vsock' and self.vsock is not None:
                for _ in range(max(1, int(count))):
                    self.vsock.sendto(msg_video, (GLASSES_IP, TOBII_PORT, 0, int(SCOPE_ID)))
                    time.sleep(max(0.01, float(interval)))
            elif hasattr(self, 'ka_sock') and self.ka_sock is not None:
                for _ in range(max(1, int(count))):
                    try:
                        self.ka_sock.sendto(msg_video, (GLASSES_IP, TOBII_PORT, 0, int(SCOPE_ID)))
                    except Exception:
                        break
                    time.sleep(max(0.01, float(interval)))
        except Exception:
            pass
    def keep_alive_worker(self):
        if self.vsock is None and getattr(self, 'gsock', None) is None and not hasattr(self, 'ka_sock'):
            return
        msg_video = json.dumps(KA_VIDEO_MSG).encode('utf-8')
        while self.running:
            try:
                use = getattr(self, '_ka_use', None)
                if use == 'gsock' and getattr(self, 'gsock', None) is not None:
                    try:
                        target_inet = Gio.InetAddress.new_from_string(f"{GLASSES_IP}%{int(SCOPE_ID)}")
                        target = Gio.InetSocketAddress.new(target_inet, TOBII_PORT)
                        if target is not None:
                            self.gsock.send_to(target, msg_video)
                    except Exception:
                        break
                elif use == 'vsock' and self.vsock is not None:
                    self.vsock.sendto(msg_video, (GLASSES_IP, TOBII_PORT, 0, int(SCOPE_ID)))
                elif hasattr(self, 'ka_sock') and self.ka_sock is not None:
                    try:
                        self.ka_sock.sendto(msg_video, (GLASSES_IP, TOBII_PORT, 0, int(SCOPE_ID)))
                    except Exception:
                        break
                try:
                    self.status_signal.emit("eye_ka_sent=1")
                except Exception:
                    pass
            except Exception:
                break
            time.sleep(1.0)
    def on_new_sample(self, sink):
        if not self.running:
            return Gst.FlowReturn.EOS
        sample = sink.emit("pull-sample")
        buf = sample.get_buffer()
        pts = buf.pts
        if not self._got_first_frame:
            try:
                self.status_signal.emit("eye_first_frame=1")
            except Exception:
                pass
            self._got_first_frame = True
        gx = gy = None
        if self._sync:
            try:
                data_chunk, latest, gaze_arr = self._sync.pop_data_up_to_now()
                if latest and latest.get('gp'):
                    gx, gy = latest['gp']
                    now = time.time()
                    if self._gaze_smooth is None:
                        self._gaze_smooth = [gx, gy]
                    else:
                        ax = 0.2
                        ay = 0.2
                        self._gaze_smooth[0] = (1.0 - ax) * self._gaze_smooth[0] + ax * gx
                        self._gaze_smooth[1] = (1.0 - ay) * self._gaze_smooth[1] + ay * gy
                    self._gaze_last_ts = now
                    self._last_gaze = [self._gaze_smooth[0], self._gaze_smooth[1]]
                    try:
                        self._last_eye_ts = latest.get('ts') or self._last_eye_ts
                    except Exception:
                        pass
                else:
                    now = time.time()
                    if self._gaze_smooth is not None and (now - self._gaze_last_ts) <= 0.25:
                        self._last_gaze = [self._gaze_smooth[0], self._gaze_smooth[1]]
                    else:
                        self._last_gaze = None
            except Exception:
                self._last_gaze = None
        if self.writer:
            gaze_ts, gaze_x, gaze_y = '', '', ''
            for gaze_pkt in gaze_arr:
                if gaze_pkt['pts'] == pts:
                    gaze_ts = gaze_pkt['gaze_ts']
                    gaze_x = gaze_pkt['gaze_x']
                    gaze_y = gaze_pkt['gaze_y']
                    break
            if not gaze_ts:
                if latest and latest.get('ts'):
                    gaze_ts = latest.get('ts') or ''
                elif self._last_eye_ts:
                    gaze_ts = self._last_eye_ts
            if self._last_gaze and ((not gaze_x) or (not gaze_y)):
                try:
                    gaze_x = self._last_gaze[0]
                    gaze_y = self._last_gaze[1]
                except Exception:
                    pass
            row = [
                pts,                     # Video_PTS
                pts,                     # glassts
                False,                   # marker_flag
                'N/A',                   # marker_type
                'N/A',                   # marker_condition
                'N/A',                   # marker_target
                'N/A',                   # marker_color
                'N/A',                   # marker_label
                gaze_ts,                 # Gaze_TS
                gaze_x,                  # Gaze_X
                gaze_y                   # Gaze_Y
            ]
            try:
                self.writer.write(row)
            except Exception:
                pass
        caps = sample.get_caps()
        h = caps.get_structure(0).get_value("height")
        w = caps.get_structure(0).get_value("width")
        raw = buf.extract_dup(0, buf.get_size())
        img = QImage(raw, w, h, QImage.Format_RGB888)
        try:
            if getattr(self, 'recorder', None):
                self.recorder.push(raw)
        except Exception:
            pass
        self.frame_signal.emit(img.copy(), self._last_gaze or [])
        return Gst.FlowReturn.OK
    def on_bus_message(self, bus, message):
        try:
            t = message.type
            if t == Gst.MessageType.ERROR:
                err, dbg = message.parse_error()
                try:
                    self.status_signal.emit(f"eye_error={str(err)}")
                except Exception:
                    pass
                try:
                    if 'Internal data stream error' in str(err):
                        self._trigger_appsrc_fallback()
                except Exception:
                    pass
            elif t == Gst.MessageType.WARNING:
                w, dbg = message.parse_warning()
                try:
                    self.status_signal.emit(f"eye_warn={str(w)}")
                except Exception:
                    pass
            elif t == Gst.MessageType.STATE_CHANGED:
                s_old, s_new, s_pending = message.parse_state_changed()
                try:
                    self.status_signal.emit(f"eye_state={int(s_new)}")
                except Exception:
                    pass
        except Exception:
            pass
    def _trigger_appsrc_fallback(self):
        try:
            if self.pipeline:
                self.pipeline.set_state(Gst.State.NULL)
        except Exception:
            pass
        self.pipeline = None
        try:
            has_tsparse = True if Gst.ElementFactory.find('tsparse') else False
            enc = 'x264enc' if Gst.ElementFactory.find('x264enc') else ('avenc_h264' if Gst.ElementFactory.find('avenc_h264') else 'openh264enc')
            need_i420 = True if enc == 'openh264enc' else False
            conv_caps = 'video/x-raw,format=I420' if need_i420 else ''
            rec_branch = None
            tsparse_chain = 'tsparse set-timestamps=true smoothing-latency=100000 split-on-rai=true alignment=7 ! '
            launch = (
                'appsrc name=tsapp format=time is-live=true block=true do-timestamp=true caps=video/mpegts,systemstream=true,packetsize=188 ! '
                + 'queue max-size-buffers=0 max-size-time=0 max-size-bytes=0 ! '
                + ((tsparse_chain + 'tsdemux emit-stats=true ! queue ! ') if has_tsparse else 'tsdemux emit-stats=true ! queue ! ')
                + 'avdec_h264 ! videoconvert ! cairooverlay name=ovl ! tee name=t '
                + 't. ! queue ! videoconvert ! video/x-raw,format=RGB ! appsink name=sink emit-signals=True sync=False drop=True max-buffers=1 '
                + ((('t. ! queue ! ' + rec_branch) if rec_branch else ''))
            )
            self.pipeline = Gst.parse_launch(launch)
            self.appsrc_ts = self.pipeline.get_by_name('tsapp')
            sink = self.pipeline.get_by_name('sink')
            sink.connect('new-sample', self.on_new_sample)
            ovl = self.pipeline.get_by_name('ovl')
            try:
                ovl.connect('caps-changed', self.on_caps_changed)
                ovl.connect('draw', self.on_draw_overlay)
            except Exception:
                pass
            bus = self.pipeline.get_bus()
            if bus:
                bus.add_signal_watch()
                bus.connect('message', self.on_bus_message)
            try:
                self.status_signal.emit('eye_live_use=appsrc')
            except Exception:
                pass
            self.pipeline.set_state(Gst.State.PLAYING)
            try:
                if self.vsock is not None:
                    threading.Thread(target=self.udp_recv_worker, daemon=True).start()
            except Exception:
                pass
        except Exception:
            pass
    def on_caps_changed(self, overlay, caps):
        try:
            s = caps.get_structure(0)
            self._w = s.get_value('width')
            self._h = s.get_value('height')
            try:
                if self._record and self.video_out and not getattr(self, 'recorder', None) and self._w and self._h:
                    self.recorder = VideoRecorder(self.video_out, self._w, self._h)
                    self.recorder.start()
            except Exception:
                pass
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
        except Exception:
            pass
    def stop(self):
        self.running = False
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
        if hasattr(self, 'loop'):
            self.loop.quit()
        if self.writer:
            self.writer.stop()
        if getattr(self, 'recorder', None):
            try:
                self.recorder.stop()
            except Exception:
                pass
            self.recorder = None
        try:
            if self.vsock:
                self.vsock.close()
        except Exception:
            pass
    def udp_recv_worker(self):
        if not self.vsock or not hasattr(self, 'appsrc_ts') or self.appsrc_ts is None:
            return
        while self.running:
            try:
                data, _ = self.vsock.recvfrom(65535)
                if not data:
                    continue
                self._ts_acc.extend(data)
                ts_view = memoryview(self._ts_acc)
                start = -1
                try:
                    b0 = ts_view[0]
                    if (b0 & 0xC0) == 0x80 and len(ts_view) >= 12:
                        cc = b0 & 0x0F
                        ext = (ts_view[0] & 0x10) != 0
                        hdr = 12 + 4*cc
                        if ext and len(ts_view) >= hdr + 4:
                            el = (ts_view[hdr+2] << 8) | ts_view[hdr+3]
                            hdr = hdr + 4 + el*4
                        if hdr < len(ts_view) and ts_view[hdr] == 0x47:
                            start = hdr
                    if start < 0:
                        for i in range(len(ts_view)):
                            if ts_view[i] == 0x47:
                                if i + 188 < len(ts_view) and ts_view[i+188] == 0x47:
                                    start = i
                                    break
                except Exception:
                    start = -1
                if start > 0:
                    del self._ts_acc[:start]
                    ts_view = memoryview(self._ts_acc)
                if len(ts_view) < 188:
                    continue
                trim_len = (len(ts_view) // 188) * 188
                if trim_len < 188:
                    continue
                if trim_len < 188*20:
                    # 等待更多TS包以避免早期PAT/PMT缺失导致的解复用错误
                    continue
                out = ts_view[:trim_len].tobytes()
                del self._ts_acc[:trim_len]
                buf = Gst.Buffer.new_allocate(None, len(out), None)
                buf.fill(0, out)
                now = int(time.time()*1e9)
                buf.pts = now
                buf.dts = now
                self.appsrc_ts.emit('push-buffer', buf)
            except Exception:
                time.sleep(0.01)
class DataSyncBuffer:
    def __init__(self):
        self.lock = threading.Lock()
        self.buffer = []
        self.gaze_buffer = []
    def add_packet(self, pkt):
        try:
            if 'gp' in pkt and 'ts' in pkt:
                with self.lock:
                    self.buffer.append(pkt)
        except Exception:
            pass
    def add_gaze_data(self, pts, gaze_ts, gaze_x, gaze_y):
        with self.lock:
            self.gaze_buffer.append({'pts': pts, 'gaze_ts': gaze_ts, 'gaze_x': gaze_x, 'gaze_y': gaze_y})
    def pop_data_up_to_now(self):
        with self.lock:
            arr = list(self.buffer)
            self.buffer.clear()
            gaze_arr = list(self.gaze_buffer)
            self.gaze_buffer.clear()
        latest = None
        for p in reversed(arr):
            if 'gp' in p:
                latest = {'gp': p.get('gp'), 'ts': p.get('ts'), 'pts': p.get('pts')}
                break
        return arr, latest, gaze_arr
class EyeDataThread(threading.Thread):
    def __init__(self, sync):
        super().__init__()
        self.sync = sync
        self.running = True
        self.daemon = True
        self.sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        try:
            self.sock.bind((MY_IP, 0, 0, int(SCOPE_ID)))
        except Exception:
            pass
        self.sock.settimeout(0.2)
    def run(self):
        last_ka = 0
        while self.running:
            now = time.time()
            if now - last_ka > 1.0:
                try:
                    msg_bytes = json.dumps(KA_MSG).encode('utf-8')
                    target = (GLASSES_IP, TOBII_PORT, 0, int(SCOPE_ID))
                    self.sock.sendto(msg_bytes, target)
                    last_ka = now
                except Exception:
                    pass
            try:
                data, _ = self.sock.recvfrom(4096)
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
            self.sock.close()
        except Exception:
            pass

class MainSystem(QWidget):
    def __init__(self, mode='both'):
        super().__init__()
        self.mode = mode or 'both'
        title = "v16 监控视频" if self.mode == 'monitor_only' else ("v16 眼动映射" if self.mode == 'gaze_only' else "v16 单机双屏同步系统 (Driver Control)")
        self.setWindowTitle(title)
        self.resize(1600, 900)
        self.is_drive_recording = False
        self.is_eye_recording = False
        self.is_drive_live = False
        self.is_eye_live = False
        self.thread_tobii = None
        self.thread_screen = None
        self.base_name = None
        self.setup_ui()
    def setup_ui(self):
        layout = QVBoxLayout()
        ctrl_box = QGroupBox("设置")
        ctrl_layout = QHBoxLayout()
        self.txt_id = QLineEdit()
        self.txt_id.setPlaceholderText("被试 ID")
        self.combo_screen = QComboBox()
        self.combo_screen.addItems(["Monitor 1 (主屏)", "Monitor 2 (副屏/模拟器)"])
        self.combo_screen.setCurrentIndex(1)
        self.chk_control = QCheckBox("启用跨屏控制 (Cross-Screen Control)")
        self.chk_control.stateChanged.connect(self.toggle_control_mode)
        if not HAVE_PYAUTOGUI:
            self.chk_control.setEnabled(False)
        ctrl_layout.addWidget(QLabel("ID:"))
        ctrl_layout.addWidget(self.txt_id)
        ctrl_layout.addWidget(QLabel("录制目标:"))
        ctrl_layout.addWidget(self.combo_screen)
        ctrl_layout.addWidget(self.chk_control)
        ctrl_box.setLayout(ctrl_layout)
        mon_layout = QVBoxLayout()
        drive_group = QGroupBox("驾驶场景 (副屏直播)")
        drive_layout = QVBoxLayout()
        self.lbl_drive = ScreenControlLabel(None)
        drive_layout.addWidget(self.lbl_drive)
        drive_ctrl = QHBoxLayout()
        self.btn_drive_live = QPushButton("开启直播 (驾驶)")
        self.btn_drive_live.clicked.connect(self.open_drive_live)
        self.btn_drive_rec = QPushButton("开始采集 (驾驶)")
        self.btn_drive_rec.clicked.connect(self.start_drive_recording)
        # 直播按钮在左，采集按钮在右
        drive_ctrl.addWidget(self.btn_drive_live)
        drive_ctrl.addWidget(self.btn_drive_rec)
        drive_layout.addLayout(drive_ctrl)
        drive_group.setLayout(drive_layout)
        eye_group = QGroupBox("眼动仪视角")
        eye_layout = QVBoxLayout()
        self.lbl_eye_status = QLabel("")
        self.lbl_eye_status.setAlignment(Qt.AlignLeft)
        self.lbl_eye_status.setMinimumHeight(20)
        eye_layout.addWidget(self.lbl_eye_status)
        self.lbl_eye = QLabel("等待眼动连接...")
        self.lbl_eye.setAlignment(Qt.AlignCenter)
        self.lbl_eye.setMinimumSize(640, 360)
        eye_layout.addWidget(self.lbl_eye)
        eye_ctrl = QHBoxLayout()
        self.btn_eye_live = QPushButton("开启直播 (眼动映射)")
        self.btn_eye_live.clicked.connect(self.open_eye_live)
        self.btn_eye_rec = QPushButton("开始采集 (眼动)")
        self.btn_eye_rec.clicked.connect(self.start_eye_recording)
        # 直播按钮在左，采集按钮在右
        eye_ctrl.addWidget(self.btn_eye_live)
        eye_ctrl.addWidget(self.btn_eye_rec)
        eye_layout.addLayout(eye_ctrl)
        eye_group.setLayout(eye_layout)
        if self.mode != 'gaze_only':
            mon_layout.addWidget(drive_group, stretch=1)
        if self.mode != 'monitor_only':
            mon_layout.addWidget(eye_group, stretch=1)
        layout.addWidget(ctrl_box)
        layout.addLayout(mon_layout)
        self.setLayout(layout)
    def toggle_control_mode(self, state):
        self.lbl_drive.set_control_active(state == Qt.Checked)
    def open_drive_live(self):
        try:
            # 开关式直播：未开启则启动，已开启则停止
            if not self.is_drive_live:
                target_mon_idx = 2 if self.combo_screen.currentIndex() == 1 else 1
                if self.thread_screen is None:
                    self.thread_screen = ScreenRecorderThread(monitor_idx=target_mon_idx)
                    self.thread_screen.frame_signal.connect(self.update_drive_view)
                    self.lbl_drive.recorder = self.thread_screen
                    self.thread_screen.start()
                self.is_drive_live = True
                self.btn_drive_live.setText("停止直播 (驾驶)")
            else:
                # 正在录制则先结束录制
                if self.is_drive_recording and self.thread_screen:
                    self.thread_screen.stop_recording()
                    self.is_drive_recording = False
                    self.btn_drive_rec.setText("开始采集 (驾驶)")
                    self.combo_screen.setEnabled(True)
                    self.set_rec_border(self.lbl_drive, False)
                # 停止直播
                if self.thread_screen:
                    self.thread_screen.stop()
                    self.thread_screen = None
                    self.lbl_drive.recorder = None
                    try:
                        self.lbl_drive.clear()
                        self.lbl_drive.setText("等待驾驶画面...")
                        self.lbl_drive.setStyleSheet("background: #222; border: 1px solid #555;")
                    except Exception:
                        pass
                self.is_drive_live = False
                self.btn_drive_live.setText("开启直播 (驾驶)")
        except Exception:
            pass
    def start_drive_recording(self):
        try:
            sub_id = (self.txt_id.text() or "test").strip()
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            save_dir = _SAVE_ROOT
            os.makedirs(save_dir, exist_ok=True)
            # 与 CSV 同路径；文件名始终含被试ID+时间戳，避免不同被试/次实验互相覆盖
            base = self.base_name or sub_id
            drive_mp4 = os.path.join(save_dir, f"DriveRec_{base}_{ts}.mp4")
            self.open_drive_live()
            if self.thread_screen and not self.is_drive_recording:
                self.thread_screen.start_recording(drive_mp4)
                self.is_drive_recording = True
                self.btn_drive_rec.setText("结束采集 (驾驶)")
                self.combo_screen.setEnabled(False)
                self.set_rec_border(self.lbl_drive, True)
            elif self.thread_screen and self.is_drive_recording:
                self.thread_screen.stop_recording()
                self.is_drive_recording = False
                self.btn_drive_rec.setText("开始采集 (驾驶)")
                self.combo_screen.setEnabled(True)
                self.set_rec_border(self.lbl_drive, False)
        except Exception:
            pass
    def set_rec_border(self, widget, on):
        try:
            if on:
                widget.setStyleSheet("background: #222; border: 3px solid #00c853;")
            else:
                widget.setStyleSheet("background: #222; border: 1px solid #555;")
        except Exception:
            pass
    def open_eye_live(self):
        try:
            # 开关式直播：未开启则启动，已开启则停止
            if not self.is_eye_live:
                self.stop_eye_recording(live_only=True)
                self._sync = DataSyncBuffer()
                self._eye_data = EyeDataThread(self._sync)
                self._eye_data.start()
                self.thread_tobii = FullTobiiThread(None, None, self._sync, record=False)
                self.thread_tobii.status_signal.connect(self.on_eye_status)
                self.thread_tobii.frame_signal.connect(self.update_eye_view)
                self.thread_tobii.start()
                try:
                    self.lbl_eye.setText("正在连接眼动视频...")
                    self.eye_status_use = ""
                    self.eye_status_first = False
                    self.eye_status_error = ""
                    self.eye_status_state = None
                    self.update_eye_status_label()
                except Exception:
                    pass
                self.is_eye_live = True
                self.btn_eye_live.setText("停止直播 (眼动映射)")
            else:
                # 正在录制则先结束录制并保存
                if self.is_eye_recording:
                    self.stop_eye_recording(live_only=False)
                else:
                    self.stop_eye_recording(live_only=True)
                self.is_eye_live = False
                self.btn_eye_live.setText("开启直播 (眼动映射)")
                try:
                    self.lbl_eye.clear()
                    self.lbl_eye.setText("等待眼动连接...")
                    self.lbl_eye.setStyleSheet("background: #222; border: 1px solid #555;")
                    self.lbl_eye_status.setText("")
                except Exception:
                    pass
        except Exception:
            pass
    @pyqtSlot(str)
    def on_eye_status(self, msg):
        try:
            if msg.startswith("eye_error="):
                self.eye_status_error = msg.split("=",1)[1]
                self.update_eye_status_label()
            elif msg.startswith("eye_first_frame="):
                self.eye_status_first = True
                self.update_eye_status_label()
            elif msg.startswith("eye_live_use="):
                self.eye_status_use = msg.split("=",1)[1]
                self.update_eye_status_label()
            elif msg.startswith("eye_vsock_bind="):
                self.eye_status_vbind = msg.split("=",1)[1]
                self.update_eye_status_label()
            elif msg.startswith("eye_gsock_bind="):
                self.eye_status_gbind = msg.split("=",1)[1]
                self.update_eye_status_label()
            elif msg.startswith("eye_ka_sent="):
                self.eye_status_ka = True
                self.update_eye_status_label()
            elif msg.startswith("eye_warn="):
                self.update_eye_status_label()
            elif msg.startswith("eye_state="):
                try:
                    self.eye_status_state = int(msg.split("=",1)[1])
                except Exception:
                    self.eye_status_state = None
                self.update_eye_status_label()
        except Exception:
            pass
    def update_eye_status_label(self):
        try:
            use = self.eye_status_use or "未知"
            first = "已到" if getattr(self, 'eye_status_first', False) else "未到"
            err = (self.eye_status_error or "无")[:100]
            st = self.eye_status_state
            if st is None:
                st_txt = "-"
            else:
                st_txt = str(st)
            vb = getattr(self, 'eye_status_vbind', '')
            gb = getattr(self, 'eye_status_gbind', '')
            ka = "已发" if getattr(self, 'eye_status_ka', False) else "未发"
            bind_txt = (f"vBind:{vb} gBind:{gb}").strip()
            self.lbl_eye_status.setText(f"接入:{use} | 首帧:{first} | 心跳:{ka} | {bind_txt} | 状态:{st_txt} | 错误:{err}")
        except Exception:
            pass
    def start_eye_recording(self):
        try:
            sub_id = (self.txt_id.text() or "S001").strip()
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            # 与主采集 CSV 同一路径（如 D:\多模态驾驶指标保存），命名含被试+时间戳避免覆盖
            eye_video_dir = _SAVE_ROOT
            monitor_dir = _SAVE_ROOT
            os.makedirs(eye_video_dir, exist_ok=True)
            os.makedirs(monitor_dir, exist_ok=True)
            if not self.is_eye_recording:
                base = self.base_name or sub_id
                eye_mp4 = os.path.join(eye_video_dir, f"EyeRec_{base}_{ts}.mp4")
                eye_csv = os.path.join(eye_video_dir, f"Eye_{base}_{ts}.csv")
                self.stop_eye_recording(live_only=True)
                self._sync = DataSyncBuffer()
                self._eye_data = EyeDataThread(self._sync)
                self._eye_data.start()
                self.thread_tobii = FullTobiiThread(eye_csv, eye_mp4, self._sync, record=True)
                self.thread_tobii.frame_signal.connect(self.update_eye_view)
                self.thread_tobii.start()
                self.is_eye_recording = True
                self.btn_eye_rec.setText("结束采集 (眼动)")
                self.set_rec_border(self.lbl_eye, True)
            else:
                self.stop_eye_recording()
        except Exception:
            pass
    def stop_eye_recording(self, live_only=False):
        try:
            if hasattr(self, '_eye_data') and self._eye_data:
                self._eye_data.stop()
        except Exception:
            pass
        try:
            if self.thread_tobii:
                self.thread_tobii.stop()
                self.thread_tobii = None
        except Exception:
            pass
        if not live_only:
            self.is_eye_recording = False
            self.btn_eye_rec.setText("开始采集 (眼动)")
            self.set_rec_border(self.lbl_eye, False)
    @pyqtSlot(QImage)
    def update_drive_view(self, qimg):
        pix = QPixmap.fromImage(qimg)
        self.lbl_drive.setPixmap(pix.scaled(self.lbl_drive.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
    @pyqtSlot(QImage, list)
    def update_eye_view(self, qimg, gaze):
        pix = QPixmap.fromImage(qimg)
        self.lbl_eye.setPixmap(pix.scaled(self.lbl_eye.size(), Qt.KeepAspectRatio))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    mode = 'both'
    win = None
    try:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('--base', default=None)
        parser.add_argument('--glasses_ip', default=None)
        parser.add_argument('--my_ip', default=None)
        parser.add_argument('--scope_id', type=int, default=None)
        parser.add_argument('--pos', default=None)
        parser.add_argument('--x', type=int, default=None)
        parser.add_argument('--y', type=int, default=None)
        parser.add_argument('--w', type=int, default=None)
        parser.add_argument('--h', type=int, default=None)
        parser.add_argument('--mode', default=None)
        args, _ = parser.parse_known_args()
        if args.mode:
            mode = str(args.mode).strip()
            if mode == 'gaze_only':
                PREFER_APP_SRC = False
                APP_FALLBACK_ALLOWED = False
        win = MainSystem(mode=mode)
        if args.base:
            win.base_name = str(args.base).replace('.csv','')
            win.txt_id.setText(win.base_name)
        if args.glasses_ip:
            GLASSES_IP = args.glasses_ip
        if args.my_ip:
            MY_IP = args.my_ip
        if args.scope_id is not None:
            SCOPE_ID = int(args.scope_id)
        if args.w and args.h:
            x = args.x if args.x is not None else 0
            y = args.y if args.y is not None else 0
            win.setGeometry(x, y, int(args.w), int(args.h))
    except Exception:
        win = MainSystem(mode=mode)
    win.show()
    sys.exit(app.exec_())
