---
name: "msys2-setup"
description: "Guides the setup of MSYS2 environment with GStreamer/GTK dependencies. Invoke when user encounters 'cairo'/'gi' errors or needs to run the Python video sync tools."
---

# MSYS2 Environment Setup for Video Sync Tools

This skill helps set up the MSYS2 environment required for `v16_dual_screen_sync.py` and `TobiiSyncRecorder_v16.py`. These scripts depend on GStreamer and GTK libraries that are best managed via MSYS2 on Windows.

## 1. Check Existing Installation

First, check if MSYS2 is already installed:
- Check if the directory `C:\msys64` exists.

## 2. Installation Instructions (If missing)

If `C:\msys64` is missing, instruct the user to:
1.  **Download**: Go to [https://www.msys2.org/](https://www.msys2.org/) and download the installer.
2.  **Install**: Run the installer and **install to the default path `C:\msys64`**.
    *   *Critical*: The project code hardcodes this path. Do not change it.
3.  **Launch**: After installation, run **"MSYS2 MINGW64"** (purple icon).

## 3. Environment Configuration

Instruct the user to run the following commands in the **MSYS2 MINGW64** terminal to install dependencies:

**Step A: Update System**
```bash
pacman -Syu
```
*(If the terminal asks to close, close it and reopen "MSYS2 MINGW64" to continue)*

**Step B: Install Python & GStreamer Dependencies**
```bash
pacman -S mingw-w64-x86_64-python mingw-w64-x86_64-python-gobject mingw-w64-x86_64-python-cairo mingw-w64-x86_64-python-pyqt5 mingw-w64-x86_64-gstreamer mingw-w64-x86_64-gst-plugins-base mingw-w64-x86_64-gst-plugins-good mingw-w64-x86_64-gst-plugins-bad mingw-w64-x86_64-gst-plugins-ugly mingw-w64-x86_64-gst-libav
```

**Step C: Install PyAutoGUI**
```bash
/mingw64/bin/pip install pyautogui
```

## 4. Verification

After installation:
1.  The python executable should be at `C:\msys64\mingw64\bin\python3.exe`.
2.  The script `custom_driving_sync - v 15 seperate ver.py` will automatically detect and use this python interpreter for the sub-processes.
