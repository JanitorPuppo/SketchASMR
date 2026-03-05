import os
import sys
import json
import wave
import math
import time
import array
import random
import shutil
import ctypes
from ctypes import wintypes, Structure, byref, POINTER as CPTR

os.environ["QT_WINTAB_ENABLED"] = "0"

import pygame
from PyQt6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QDialog, QVBoxLayout, QHBoxLayout,
    QGroupBox, QRadioButton, QListWidget, QPushButton, QSlider, QLabel,
    QFileDialog, QWidget,
)
from PyQt6.QtGui import QIcon, QImage, QPixmap, QColor, QAction, QKeySequence
from PyQt6.QtCore import Qt, QTimer


if getattr(sys, "frozen", False):
    EXE_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = sys._MEIPASS
else:
    EXE_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = EXE_DIR

APPDATA_DIR = os.path.join(os.environ.get("APPDATA", EXE_DIR), "SketchASMR")
_local_sounds = os.path.join(EXE_DIR, "sounds")
PORTABLE = os.path.isdir(_local_sounds) or not getattr(sys, "frozen", False)
DATA_DIR = EXE_DIR if PORTABLE else APPDATA_DIR

SOUND_DIR = os.path.join(DATA_DIR, "sounds")
BUNDLED_SOUND_DIR = os.path.join(BUNDLE_DIR, "sounds")
ICON_FILE = os.path.join(BUNDLE_DIR, "icon.png")
FALLBACK_WAV = os.path.join(SOUND_DIR, "writing.wav")
SUPPORTED_AUDIO_EXT = (".mp3", ".wav", ".ogg")
CONFIG_FILE = os.path.join(DATA_DIR, "settings.json")
APP_NAME = "SketchASMR"
APP_AUTHOR = "janitorpuppo"
APP_URL = "https://janitor.gg"
MIN_VOLUME = 0.05
MUTEX_NAME = "Global\\SketchASMR_SingleInstance"

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
_kernel32.CreateMutexW.restype = wintypes.HANDLE
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL
ERROR_ALREADY_EXISTS = 183

_instance_mutex = None

def acquire_single_instance():
    global _instance_mutex
    _instance_mutex = _kernel32.CreateMutexW(None, True, MUTEX_NAME)
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        print(f"[{APP_NAME}] Already running - exiting.", flush=True)
        sys.exit(0)

def release_single_instance():
    global _instance_mutex
    if _instance_mutex:
        _kernel32.CloseHandle(_instance_mutex)
        _instance_mutex = None


# ── Settings persistence ─────────────────────────────────────────────────────

class Settings:
    DEFAULTS = {
        "input_mode": "tablet",
        "max_volume": 80,
        "pause_hotkey": "",
    }

    def __init__(self):
        self.data = dict(self.DEFAULTS)
        self.load()

    def load(self):
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                self.data.update(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass

    def save(self):
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except OSError:
            pass

    @property
    def input_mode(self):
        return self.data["input_mode"]

    @input_mode.setter
    def input_mode(self, v):
        self.data["input_mode"] = v

    @property
    def max_volume(self):
        return self.data["max_volume"]

    @max_volume.setter
    def max_volume(self, v):
        self.data["max_volume"] = v

    @property
    def pause_hotkey(self):
        return self.data["pause_hotkey"]

    @pause_hotkey.setter
    def pause_hotkey(self, v):
        self.data["pause_hotkey"] = v


# ── Sound file discovery ─────────────────────────────────────────────────────

def seed_bundled_sounds():
    if BUNDLED_SOUND_DIR == SOUND_DIR:
        return
    if not os.path.isdir(BUNDLED_SOUND_DIR):
        return
    os.makedirs(SOUND_DIR, exist_ok=True)
    for f in os.listdir(BUNDLED_SOUND_DIR):
        if os.path.splitext(f)[1].lower() in SUPPORTED_AUDIO_EXT:
            dest = os.path.join(SOUND_DIR, f)
            if not os.path.exists(dest):
                shutil.copy2(os.path.join(BUNDLED_SOUND_DIR, f), dest)


def find_sound_files():
    files = []
    if os.path.isdir(SOUND_DIR):
        for f in sorted(os.listdir(SOUND_DIR)):
            if os.path.splitext(f)[1].lower() in SUPPORTED_AUDIO_EXT:
                files.append(os.path.join(SOUND_DIR, f))
    return files


def generate_placeholder_wav(filename, duration=3.0, sample_rate=44100):
    n_samples = int(duration * sample_rate)
    samples = array.array("h")
    for i in range(n_samples):
        t = i / sample_rate
        noise = random.randint(-3000, 3000)
        crinkle = int(1500 * math.sin(2 * math.pi * 120 * t + random.uniform(-0.5, 0.5)))
        scratch = int(800 * math.sin(2 * math.pi * (200 + random.uniform(-30, 30)) * t))
        envelope = min(1.0, i / (sample_rate * 0.01)) * min(1.0, (n_samples - i) / (sample_rate * 0.01))
        sample = int((noise + crinkle + scratch) * envelope)
        sample = max(-32768, min(32767, sample))
        samples.append(sample)
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with wave.open(filename, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples.tobytes())


# ── Audio manager ────────────────────────────────────────────────────────────

class AudioManager:
    def __init__(self, playlist):
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        self.playlist = playlist
        self.current_index = 0
        self.state = "idle"
        self.current_volume = 0.0
        self._load_current()

    def _load_current(self):
        pygame.mixer.music.load(self.playlist[self.current_index])

    def _advance(self):
        self.current_index = (self.current_index + 1) % len(self.playlist)
        self._load_current()

    def _start_playing(self, vol):
        pygame.mixer.music.set_volume(vol)
        loops = -1 if len(self.playlist) == 1 else 0
        pygame.mixer.music.play(loops=loops)
        self.state = "playing"
        self.current_volume = vol

    def play(self, volume=1.0):
        vol = max(0.0, min(1.0, volume))
        if self.state == "idle":
            self._start_playing(vol)
        elif self.state == "paused":
            pygame.mixer.music.set_volume(vol)
            pygame.mixer.music.unpause()
            self.state = "playing"
            self.current_volume = vol
        elif not pygame.mixer.music.get_busy():
            self._advance()
            self._start_playing(vol)
        elif abs(vol - self.current_volume) > 0.05:
            pygame.mixer.music.set_volume(vol)
            self.current_volume = vol

    def stop(self):
        if self.state == "playing":
            pygame.mixer.music.pause()
            self.state = "paused"
            self.current_volume = 0.0

    def cleanup(self):
        pygame.mixer.music.stop()
        pygame.mixer.quit()


# ── Low-level mouse hook ─────────────────────────────────────────────────────

class POINT(Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

WH_MOUSE_LL = 14
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
LLMHF_INJECTED = 0x01
MI_WP_SIGNATURE = 0xFF515700
SIGNATURE_MASK = 0xFFFFFF00
TABLET_MAX_PRESSURE = 8192

class MSLLHOOKSTRUCT(Structure):
    _fields_ = [
        ("pt", POINT),
        ("mouseData", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("time", ctypes.c_uint32),
        ("dwExtraInfo", ctypes.c_size_t),
    ]

HOOKPROC = ctypes.WINFUNCTYPE(
    ctypes.c_longlong, ctypes.c_int, ctypes.c_ulonglong, ctypes.c_longlong,
)

_user32 = ctypes.windll.user32
_user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD,
]
_user32.SetWindowsHookExW.restype = ctypes.c_void_p
_user32.CallNextHookEx.argtypes = [
    ctypes.c_void_p, ctypes.c_int, ctypes.c_ulonglong, ctypes.c_longlong,
]
_user32.CallNextHookEx.restype = ctypes.c_longlong
_user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
_user32.UnhookWindowsHookEx.restype = wintypes.BOOL


class PenInputHook:
    def __init__(self):
        self._hook = None
        self._hook_proc = None
        self.pen_down = False
        self.pressure = 0
        self.raw_mouse_mode = False
        self.pen_detector = None

    def install(self):
        def _callback(nCode, wParam, lParam):
            if nCode >= 0 and wParam in (WM_LBUTTONDOWN, WM_LBUTTONUP, WM_MOUSEMOVE):
                try:
                    info = ctypes.cast(lParam, CPTR(MSLLHOOKSTRUCT)).contents
                    injected = bool(info.flags & LLMHF_INJECTED)
                    pointer_gen = (info.dwExtraInfo & SIGNATURE_MASK) == MI_WP_SIGNATURE
                    pen_active = (
                        self.pen_detector is not None
                        and self.pen_detector.is_pen_recent()
                    )
                    accept = self.raw_mouse_mode or injected or pointer_gen or pen_active

                    if accept:
                        has_pressure = injected and info.dwExtraInfo > 0
                        if wParam == WM_LBUTTONDOWN:
                            self.pen_down = True
                            if self.raw_mouse_mode or not has_pressure:
                                self.pressure = TABLET_MAX_PRESSURE
                            else:
                                self.pressure = info.dwExtraInfo
                        elif wParam == WM_LBUTTONUP:
                            self.pen_down = False
                            self.pressure = 0
                        elif wParam == WM_MOUSEMOVE and self.pen_down:
                            if has_pressure:
                                self.pressure = info.dwExtraInfo
                except Exception:
                    pass
            return _user32.CallNextHookEx(self._hook, nCode, wParam, lParam)

        self._hook_proc = HOOKPROC(_callback)
        self._hook = _user32.SetWindowsHookExW(WH_MOUSE_LL, self._hook_proc, None, 0)
        return self._hook is not None and self._hook != 0

    def uninstall(self):
        if self._hook:
            _user32.UnhookWindowsHookEx(self._hook)
            self._hook = None


# ── Raw Input pen detection ──────────────────────────────────────────────────

WM_INPUT = 0x00FF
RIDEV_INPUTSINK = 0x00000100
RIM_TYPEHID = 2
RID_INPUT = 0x10000003
RIDI_PREPARSEDDATA = 0x20000005
HID_USAGE_PAGE_DIGITIZER = 0x0D
HID_USAGE_DIGITIZER_PEN = 0x02

class RAWINPUTDEVICE(Structure):
    _fields_ = [
        ("usUsagePage", ctypes.c_ushort),
        ("usUsage", ctypes.c_ushort),
        ("dwFlags", ctypes.c_uint32),
        ("hwndTarget", wintypes.HWND),
    ]

class RAWINPUTHEADER(Structure):
    _fields_ = [
        ("dwType", ctypes.c_uint32),
        ("dwSize", ctypes.c_uint32),
        ("hDevice", ctypes.c_void_p),
        ("wParam", ctypes.c_size_t),
    ]

WNDPROC_TYPE = ctypes.WINFUNCTYPE(
    ctypes.c_longlong, wintypes.HWND, ctypes.c_uint,
    ctypes.c_size_t, ctypes.c_ssize_t,
)

class WNDCLASSEXW(Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("style", ctypes.c_uint),
        ("lpfnWndProc", WNDPROC_TYPE),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HANDLE),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HICON),
    ]

_user32.RegisterClassExW.argtypes = [CPTR(WNDCLASSEXW)]
_user32.RegisterClassExW.restype = wintypes.ATOM
_user32.CreateWindowExW.argtypes = [
    ctypes.c_uint32, wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_uint32,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, ctypes.c_void_p,
]
_user32.CreateWindowExW.restype = wintypes.HWND
_user32.DefWindowProcW.argtypes = [
    wintypes.HWND, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t,
]
_user32.DefWindowProcW.restype = ctypes.c_longlong
_user32.DestroyWindow.argtypes = [wintypes.HWND]
_user32.DestroyWindow.restype = wintypes.BOOL
_user32.RegisterRawInputDevices.argtypes = [
    ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint,
]
_user32.RegisterRawInputDevices.restype = wintypes.BOOL
_user32.GetRawInputData.argtypes = [
    ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p,
    CPTR(ctypes.c_uint), ctypes.c_uint,
]
_user32.GetRawInputData.restype = ctypes.c_uint
_kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
_kernel32.GetModuleHandleW.restype = wintypes.HMODULE

HWND_MESSAGE = -3


class RawPenDetector:
    def __init__(self):
        self._last_pen_time = 0.0
        self._hwnd = None
        self._wndproc_ref = None

    def start(self):
        def wndproc(hwnd, msg, wParam, lParam):
            if msg == WM_INPUT:
                self._on_raw_input(lParam)
            return _user32.DefWindowProcW(hwnd, msg, wParam, lParam)

        self._wndproc_ref = WNDPROC_TYPE(wndproc)
        hInst = _kernel32.GetModuleHandleW(None)

        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = self._wndproc_ref
        wc.hInstance = hInst
        wc.lpszClassName = "SketchASMR_RawPen"
        _user32.RegisterClassExW(byref(wc))

        self._hwnd = _user32.CreateWindowExW(
            0, "SketchASMR_RawPen", "", 0,
            0, 0, 0, 0,
            HWND_MESSAGE, None, hInst, None,
        )
        if not self._hwnd:
            print("[raw pen] failed to create window", flush=True)
            return False

        rid = RAWINPUTDEVICE()
        rid.usUsagePage = HID_USAGE_PAGE_DIGITIZER
        rid.usUsage = HID_USAGE_DIGITIZER_PEN
        rid.dwFlags = RIDEV_INPUTSINK
        rid.hwndTarget = self._hwnd
        ok = _user32.RegisterRawInputDevices(
            byref(rid), 1, ctypes.sizeof(rid),
        )
        print(f"[raw pen] digitizer registered: {bool(ok)}", flush=True)
        return bool(ok)

    def _on_raw_input(self, hRawInput):
        size = ctypes.c_uint(0)
        _user32.GetRawInputData(
            hRawInput, RID_INPUT, None, byref(size),
            ctypes.sizeof(RAWINPUTHEADER),
        )
        if size.value == 0:
            return
        buf = ctypes.create_string_buffer(size.value)
        _user32.GetRawInputData(
            hRawInput, RID_INPUT, buf, byref(size),
            ctypes.sizeof(RAWINPUTHEADER),
        )
        header = RAWINPUTHEADER.from_buffer_copy(buf)
        if header.dwType == RIM_TYPEHID:
            self._last_pen_time = time.monotonic()

    def is_pen_recent(self, threshold_s=0.15):
        return (time.monotonic() - self._last_pen_time) < threshold_s

    def stop(self):
        if self._hwnd:
            _user32.DestroyWindow(self._hwnd)
            self._hwnd = None


# ── WinTab pen detection ─────────────────────────────────────────────────────

WT_PACKET = 0x7FF0
WTI_DEFSYSCTX = 4
WTI_DEVICES = 100
DVC_NPRESSURE = 18
CXO_SYSTEM = 0x0001
CXO_MESSAGES = 0x0004
PK_NORMAL_PRESSURE = 0x0400


class LOGCONTEXTA(Structure):
    _fields_ = [
        ("lcName", ctypes.c_char * 40),
        ("lcOptions", ctypes.c_uint),
        ("lcStatus", ctypes.c_uint),
        ("lcLocks", ctypes.c_uint),
        ("lcMsgBase", ctypes.c_uint),
        ("lcDevice", ctypes.c_uint),
        ("lcPktRate", ctypes.c_uint),
        ("lcPktData", ctypes.c_uint),
        ("lcPktMode", ctypes.c_uint),
        ("lcMoveMask", ctypes.c_uint),
        ("lcBtnDnMask", ctypes.c_uint32),
        ("lcBtnUpMask", ctypes.c_uint32),
        ("lcInOrgX", ctypes.c_long),
        ("lcInOrgY", ctypes.c_long),
        ("lcInOrgZ", ctypes.c_long),
        ("lcInExtX", ctypes.c_long),
        ("lcInExtY", ctypes.c_long),
        ("lcInExtZ", ctypes.c_long),
        ("lcOutOrgX", ctypes.c_long),
        ("lcOutOrgY", ctypes.c_long),
        ("lcOutOrgZ", ctypes.c_long),
        ("lcOutExtX", ctypes.c_long),
        ("lcOutExtY", ctypes.c_long),
        ("lcOutExtZ", ctypes.c_long),
        ("lcSensX", ctypes.c_uint32),
        ("lcSensY", ctypes.c_uint32),
        ("lcSensZ", ctypes.c_uint32),
        ("lcSysMode", ctypes.c_int),
        ("lcSysOrgX", ctypes.c_int),
        ("lcSysOrgY", ctypes.c_int),
        ("lcSysExtX", ctypes.c_int),
        ("lcSysExtY", ctypes.c_int),
        ("lcSysSensX", ctypes.c_uint32),
        ("lcSysSensY", ctypes.c_uint32),
    ]


class AXIS(Structure):
    _fields_ = [
        ("axMin", ctypes.c_long),
        ("axMax", ctypes.c_long),
        ("axUnits", ctypes.c_uint),
        ("axResolution", ctypes.c_uint32),
    ]


class WINTAB_PACKET(Structure):
    _fields_ = [("pkNormalPressure", ctypes.c_uint)]


class WinTabDetector:
    def __init__(self):
        self._wintab = None
        self._ctx = None
        self._hwnd = None
        self._wndproc_ref = None
        self.pen_down = False
        self.pressure = 0
        self.max_pressure = 1024

    def start(self):
        try:
            self._wintab = ctypes.WinDLL("wintab32")
        except OSError:
            print("[wintab] wintab32.dll not found", flush=True)
            return False

        self._wintab.WTInfoA.argtypes = [
            ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p,
        ]
        self._wintab.WTInfoA.restype = ctypes.c_uint
        self._wintab.WTOpenA.argtypes = [
            wintypes.HWND, ctypes.c_void_p, wintypes.BOOL,
        ]
        self._wintab.WTOpenA.restype = ctypes.c_void_p
        self._wintab.WTClose.argtypes = [ctypes.c_void_p]
        self._wintab.WTClose.restype = wintypes.BOOL
        self._wintab.WTPacket.argtypes = [
            ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p,
        ]
        self._wintab.WTPacket.restype = wintypes.BOOL

        axis = AXIS()
        if self._wintab.WTInfoA(WTI_DEVICES, DVC_NPRESSURE, byref(axis)):
            self.max_pressure = max(axis.axMax, 1)
            print(f"[wintab] pressure range: 0-{self.max_pressure}", flush=True)

        ctx = LOGCONTEXTA()
        if not self._wintab.WTInfoA(WTI_DEFSYSCTX, 0, byref(ctx)):
            print("[wintab] no tablet found", flush=True)
            return False

        ctx.lcName = b"SketchASMR"
        ctx.lcOptions |= CXO_SYSTEM | CXO_MESSAGES
        ctx.lcPktData = PK_NORMAL_PRESSURE
        ctx.lcMoveMask = PK_NORMAL_PRESSURE
        ctx.lcBtnDnMask = 0xFFFFFFFF
        ctx.lcBtnUpMask = 0xFFFFFFFF

        def wndproc(hwnd, msg, wParam, lParam):
            if msg == WT_PACKET:
                self._on_packet(wParam, lParam)
            return _user32.DefWindowProcW(hwnd, msg, wParam, lParam)

        self._wndproc_ref = WNDPROC_TYPE(wndproc)
        hInst = _kernel32.GetModuleHandleW(None)

        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = self._wndproc_ref
        wc.hInstance = hInst
        wc.lpszClassName = "SketchASMR_WinTab"
        _user32.RegisterClassExW(byref(wc))

        self._hwnd = _user32.CreateWindowExW(
            0, "SketchASMR_WinTab", "", 0,
            0, 0, 0, 0,
            None, None, hInst, None,
        )
        if not self._hwnd:
            print("[wintab] failed to create window", flush=True)
            return False

        self._ctx = self._wintab.WTOpenA(self._hwnd, byref(ctx), True)
        if not self._ctx:
            print("[wintab] failed to open context", flush=True)
            _user32.DestroyWindow(self._hwnd)
            self._hwnd = None
            return False

        print("[wintab] system context opened", flush=True)
        return True

    def _on_packet(self, serial, hCtx):
        pkt = WINTAB_PACKET()
        if self._wintab.WTPacket(self._ctx, serial, byref(pkt)):
            self.pressure = pkt.pkNormalPressure
            self.pen_down = pkt.pkNormalPressure > 0

    def stop(self):
        if self._ctx:
            self._wintab.WTClose(self._ctx)
            self._ctx = None
        if self._hwnd:
            _user32.DestroyWindow(self._hwnd)
            self._hwnd = None


# ── Global hotkey (RegisterHotKey) ────────────────────────────────────────────

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
HOTKEY_TOGGLE_ID = 1

_user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
_user32.RegisterHotKey.restype = wintypes.BOOL
_user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.UnregisterHotKey.restype = wintypes.BOOL

QT_KEY_TO_VK = {
    Qt.Key.Key_F1: 0x70, Qt.Key.Key_F2: 0x71, Qt.Key.Key_F3: 0x72,
    Qt.Key.Key_F4: 0x73, Qt.Key.Key_F5: 0x74, Qt.Key.Key_F6: 0x75,
    Qt.Key.Key_F7: 0x76, Qt.Key.Key_F8: 0x77, Qt.Key.Key_F9: 0x78,
    Qt.Key.Key_F10: 0x79, Qt.Key.Key_F11: 0x7A, Qt.Key.Key_F12: 0x7B,
    Qt.Key.Key_Space: 0x20, Qt.Key.Key_Return: 0x0D, Qt.Key.Key_Enter: 0x0D,
    Qt.Key.Key_Escape: 0x1B, Qt.Key.Key_Tab: 0x09, Qt.Key.Key_Backspace: 0x08,
    Qt.Key.Key_Delete: 0x2E, Qt.Key.Key_Insert: 0x2D,
    Qt.Key.Key_Home: 0x24, Qt.Key.Key_End: 0x23,
    Qt.Key.Key_PageUp: 0x21, Qt.Key.Key_PageDown: 0x22,
}


def qt_key_to_vk(qt_key):
    if qt_key in QT_KEY_TO_VK:
        return QT_KEY_TO_VK[qt_key]
    val = qt_key.value if hasattr(qt_key, "value") else int(qt_key)
    if 0x20 <= val <= 0x7E:
        return val
    return 0


class MSG(Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint32),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_ssize_t),
        ("time", ctypes.c_uint32),
        ("pt", POINT),
    ]

_user32.PeekMessageW.argtypes = [
    CPTR(MSG), wintypes.HWND, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint,
]
_user32.PeekMessageW.restype = wintypes.BOOL
PM_REMOVE = 0x0001


class HotkeyManager:
    def __init__(self, callback):
        self.callback = callback
        self._registered = False
        self._timer = None

    def start_polling(self):
        self._timer = QTimer()
        self._timer.timeout.connect(self._check_hotkey)
        self._timer.start(50)

    def _check_hotkey(self):
        if not self._registered:
            return
        msg = MSG()
        while _user32.PeekMessageW(byref(msg), None, WM_HOTKEY, WM_HOTKEY, PM_REMOVE):
            if msg.wParam == HOTKEY_TOGGLE_ID:
                self.callback()

    def register(self, key_sequence_str):
        self.unregister()
        if not key_sequence_str:
            return False
        seq = QKeySequence.fromString(key_sequence_str)
        if seq.isEmpty():
            return False

        combo = seq[0]
        qt_mods = combo.keyboardModifiers()
        qt_key = combo.key()

        win_mods = MOD_NOREPEAT
        if qt_mods & Qt.KeyboardModifier.ControlModifier:
            win_mods |= MOD_CONTROL
        if qt_mods & Qt.KeyboardModifier.ShiftModifier:
            win_mods |= MOD_SHIFT
        if qt_mods & Qt.KeyboardModifier.AltModifier:
            win_mods |= MOD_ALT
        if qt_mods & Qt.KeyboardModifier.MetaModifier:
            win_mods |= MOD_WIN

        vk = qt_key_to_vk(qt_key)
        if not vk:
            return False

        ok = _user32.RegisterHotKey(None, HOTKEY_TOGGLE_ID, win_mods, vk)
        self._registered = bool(ok)
        return self._registered

    def unregister(self):
        if self._registered:
            _user32.UnregisterHotKey(None, HOTKEY_TOGGLE_ID)
            self._registered = False


# ── Tray icon generation ─────────────────────────────────────────────────────

_icon_cache = {}

def make_tray_icon(active):
    if active in _icon_cache:
        return _icon_cache[active]

    pixmap = QPixmap(ICON_FILE)
    if pixmap.isNull():
        pixmap = QPixmap(64, 64)
        pixmap.fill(QColor(76, 175, 80) if active else QColor(158, 158, 158))

    if not active:
        grey = pixmap.toImage().convertToFormat(QImage.Format.Format_Grayscale8)
        pixmap = QPixmap.fromImage(grey)

    icon = QIcon(pixmap)
    _icon_cache[active] = icon
    return icon


# ── Settings dialog ──────────────────────────────────────────────────────────

DIALOG_STYLE = """
QDialog { background: #f8f8f8; }
QGroupBox {
    font-weight: bold; border: 1px solid #ccc; border-radius: 6px;
    margin-top: 14px; padding: 14px 10px 10px 10px;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 12px; padding: 0 6px;
}
QPushButton {
    padding: 5px 14px; border: 1px solid #bbb; border-radius: 4px;
    background: #fff;
}
QPushButton:hover { background: #e8e8e8; }
QSlider::groove:horizontal {
    height: 6px; background: #ddd; border-radius: 3px;
}
QSlider::handle:horizontal {
    width: 16px; margin: -5px 0; background: #4CAF50; border-radius: 8px;
}
QListWidget {
    border: 1px solid #ccc; border-radius: 4px; background: #fff;
}
"""


class HotkeyButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._sequence = QKeySequence()
        self._recording = False
        self._update_label()

    def keySequence(self):
        return self._sequence

    def setKeySequence(self, seq):
        self._sequence = seq
        self._recording = False
        self._update_label()

    def clear(self):
        self._sequence = QKeySequence()
        self._recording = False
        self._update_label()

    def _update_label(self):
        if self._recording:
            self.setText("Press a key combo...")
        elif self._sequence.isEmpty():
            self.setText("Click to set")
        else:
            self.setText(self._sequence.toString())

    def mousePressEvent(self, event):
        self._recording = True
        self._update_label()
        self.setFocus()

    def keyPressEvent(self, event):
        if not self._recording:
            return super().keyPressEvent(event)
        key = event.key()
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            return
        self._sequence = QKeySequence(event.keyCombination())
        self._recording = False
        self._update_label()
        if hasattr(self, "sequenceChanged"):
            self.sequenceChanged(self._sequence)

    def focusOutEvent(self, event):
        self._recording = False
        self._update_label()
        super().focusOutEvent(event)


class SettingsDialog(QDialog):
    def __init__(self, app_ref, parent=None):
        super().__init__(parent)
        self.app_ref = app_ref
        self.settings = app_ref.settings
        self.setWindowTitle(f"{APP_NAME} - Settings")
        self.setWindowIcon(make_tray_icon(True))
        self.setMinimumWidth(440)
        self.setStyleSheet(DIALOG_STYLE)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        self._build_ui()
        print("[settings] dialog created ok", flush=True)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)

        input_group = QGroupBox("Input Mode")
        il = QVBoxLayout()
        self._radio_tablet = QRadioButton("Tablet — pen pressure sensitive")
        self._radio_mouse = QRadioButton("Mouse — click to play (no pressure)")
        il.addWidget(self._radio_tablet)
        il.addWidget(self._radio_mouse)
        input_group.setLayout(il)
        root.addWidget(input_group)

        sound_group = QGroupBox("Sound Files")
        sl = QVBoxLayout()
        self._file_list = QListWidget()
        self._file_list.setMinimumHeight(100)
        sl.addWidget(self._file_list)
        btn_row = QHBoxLayout()
        self._btn_add = QPushButton("Add Files")
        self._btn_remove = QPushButton("Remove")
        self._btn_folder = QPushButton("Open Folder")
        btn_row.addWidget(self._btn_add)
        btn_row.addWidget(self._btn_remove)
        btn_row.addWidget(self._btn_folder)
        sl.addLayout(btn_row)
        sound_group.setLayout(sl)
        root.addWidget(sound_group)

        vol_group = QGroupBox("Volume")
        vl = QHBoxLayout()
        vl.addWidget(QLabel("Max"))
        self._vol_slider = QSlider(Qt.Orientation.Horizontal)
        self._vol_slider.setRange(5, 100)
        vl.addWidget(self._vol_slider)
        self._vol_label = QLabel("80%")
        self._vol_label.setFixedWidth(40)
        vl.addWidget(self._vol_label)
        vol_group.setLayout(vl)
        root.addWidget(vol_group)

        hk_group = QGroupBox("Hotkey")
        hl = QHBoxLayout()
        hl.addWidget(QLabel("Pause / Resume"))
        self._hotkey_btn = HotkeyButton()
        self._hotkey_btn.setMinimumWidth(160)
        hl.addWidget(self._hotkey_btn)
        self._btn_clear_hk = QPushButton("Clear")
        hl.addWidget(self._btn_clear_hk)
        hk_group.setLayout(hl)
        root.addWidget(hk_group)

        self._radio_tablet.toggled.connect(self._on_input_mode)
        self._btn_add.clicked.connect(self._add_files)
        self._btn_remove.clicked.connect(self._remove_file)
        self._btn_folder.clicked.connect(self._open_folder)
        self._vol_slider.valueChanged.connect(self._on_volume)
        self._hotkey_btn.sequenceChanged = self._on_hotkey
        self._btn_clear_hk.clicked.connect(self._clear_hotkey)

    def _load_current(self):
        if self.settings.input_mode == "mouse":
            self._radio_mouse.setChecked(True)
        else:
            self._radio_tablet.setChecked(True)
        self._refresh_file_list()
        self._vol_slider.setValue(self.settings.max_volume)
        self._vol_label.setText(f"{self.settings.max_volume}%")
        if self.settings.pause_hotkey:
            self._hotkey_btn.setKeySequence(QKeySequence.fromString(self.settings.pause_hotkey))

    def _refresh_file_list(self):
        self._file_list.clear()
        for f in find_sound_files():
            self._file_list.addItem(os.path.basename(f))

    def _on_input_mode(self, checked):
        mode = "tablet" if self._radio_tablet.isChecked() else "mouse"
        self.settings.input_mode = mode
        self.settings.save()
        self.app_ref._pen_hook.raw_mouse_mode = (mode == "mouse")
        print(f"[settings] input mode -> {mode}", flush=True)

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Add Sound Files", "",
            "Audio Files (*.mp3 *.wav *.ogg);;All Files (*)",
        )
        if not files:
            return
        os.makedirs(SOUND_DIR, exist_ok=True)
        for f in files:
            dest = os.path.join(SOUND_DIR, os.path.basename(f))
            if not os.path.exists(dest):
                shutil.copy2(f, dest)
        self._refresh_file_list()
        self.app_ref.reload_playlist()

    def _remove_file(self):
        item = self._file_list.currentItem()
        if not item:
            return
        path = os.path.join(SOUND_DIR, item.text())
        if os.path.exists(path):
            os.remove(path)
        self._refresh_file_list()
        self.app_ref.reload_playlist()

    def _open_folder(self):
        os.makedirs(SOUND_DIR, exist_ok=True)
        os.startfile(SOUND_DIR)

    def _on_volume(self, val):
        self._vol_label.setText(f"{val}%")
        self.settings.max_volume = val
        self.settings.save()
        self.app_ref.max_volume = val / 100.0

    def _on_hotkey(self, seq):
        seq_str = seq.toString()
        self.settings.pause_hotkey = seq_str
        self.settings.save()
        ok = self.app_ref.hotkey_mgr.register(seq_str)
        status = "registered" if ok else "failed"
        print(f"[settings] hotkey -> {seq_str} ({status})", flush=True)

    def _clear_hotkey(self):
        self._hotkey_btn.clear()
        self.settings.pause_hotkey = ""
        self.settings.save()
        self.app_ref.hotkey_mgr.unregister()
        print("[settings] hotkey cleared", flush=True)


# ── Main application ─────────────────────────────────────────────────────────

class PenASMR:
    def __init__(self, sound_path=None):
        self.sound_path = sound_path
        self.settings = Settings()
        self.playlist = []
        self.monitoring = True
        self.audio = None
        self.tray_icon = None
        self.qt_app = None
        self._pen_hook = None
        self._pen_detector = None
        self._wintab = None
        self._poll_timer = None
        self._was_down = False
        self._settings_dialog = None
        self.hotkey_mgr = None
        self.max_volume = self.settings.max_volume / 100.0

    def _ensure_sound(self):
        if self.sound_path and os.path.exists(self.sound_path):
            self.playlist = [self.sound_path]
            return
        found = find_sound_files()
        if found:
            self.playlist = found
        else:
            generate_placeholder_wav(FALLBACK_WAV)
            self.playlist = [FALLBACK_WAV]

    def reload_playlist(self):
        if self.audio:
            self.audio.stop()
            pygame.mixer.music.stop()
        found = find_sound_files()
        if found:
            self.playlist = found
        else:
            generate_placeholder_wav(FALLBACK_WAV)
            self.playlist = [FALLBACK_WAV]
        self.audio = AudioManager(self.playlist)
        print(f"[playlist] reloaded - {len(self.playlist)} file(s)", flush=True)

    def handle_pressure(self, normalized):
        volume = MIN_VOLUME + normalized * (self.max_volume - MIN_VOLUME)
        volume = max(MIN_VOLUME, min(self.max_volume, volume))
        self.audio.play(volume)

    def handle_release(self):
        self.audio.stop()

    def _poll_pen(self):
        if not self.monitoring:
            if self._was_down:
                self._was_down = False
                self.handle_release()
            return

        wt = self._wintab
        if wt and wt.pen_down:
            normalized = max(0.0, min(1.0, wt.pressure / wt.max_pressure))
            self.handle_pressure(normalized)
            if not self._was_down:
                self._was_down = True
        elif self._pen_hook.pen_down:
            raw = self._pen_hook.pressure
            normalized = max(0.0, min(1.0, raw / TABLET_MAX_PRESSURE))
            self.handle_pressure(normalized)
            if not self._was_down:
                self._was_down = True
        elif self._was_down:
            self._was_down = False
            self.handle_release()

    def toggle(self):
        self.monitoring = not self.monitoring
        if not self.monitoring and self.audio:
            self.audio.stop()
        self._update_tray()
        print(f"[{APP_NAME}] {'ON' if self.monitoring else 'PAUSED'}", flush=True)

    def _update_tray(self):
        if self.tray_icon:
            self.tray_icon.setIcon(make_tray_icon(self.monitoring))
            status = "ON" if self.monitoring else "OFF"
            self.tray_icon.setToolTip(f"{APP_NAME} — {status}")

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle()

    def _show_settings(self):
        QTimer.singleShot(0, self._open_settings_deferred)

    def _open_settings_deferred(self):
        try:
            if self._settings_dialog is None:
                self._settings_dialog = SettingsDialog(self)
            self._settings_dialog._load_current()
            self._settings_dialog.show()
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
        except Exception as e:
            print(f"[error] Settings dialog: {e}", flush=True)
            import traceback
            traceback.print_exc()

    def _build_tray(self):
        menu = QMenu()

        self._toggle_action = QAction("Pause", menu)
        self._toggle_action.triggered.connect(lambda: self.toggle())
        menu.addAction(self._toggle_action)
        menu.aboutToShow.connect(self._update_menu_text)

        settings_action = QAction("Settings", menu)
        settings_action.triggered.connect(self._show_settings)
        menu.addAction(settings_action)

        menu.addSeparator()

        website_action = QAction(APP_URL.removeprefix("https://"), menu)
        website_action.triggered.connect(lambda: os.startfile(APP_URL))
        menu.addAction(website_action)

        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        self.tray_icon = QSystemTrayIcon()
        self.tray_icon.setIcon(make_tray_icon(True))
        self.tray_icon.setToolTip(f"{APP_NAME} — ON")
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _update_menu_text(self):
        self._toggle_action.setText("Pause" if self.monitoring else "Resume")

    def _quit(self):
        if self.hotkey_mgr:
            self.hotkey_mgr.unregister()
        if self._pen_hook:
            self._pen_hook.uninstall()
        if hasattr(self, "_pen_detector") and self._pen_detector:
            self._pen_detector.stop()
        if hasattr(self, "_wintab") and self._wintab:
            self._wintab.stop()
        if self.audio:
            self.audio.stop()
            self.audio.cleanup()
        release_single_instance()
        self.qt_app.quit()

    def run(self):
        acquire_single_instance()
        seed_bundled_sounds()
        print(f"[{APP_NAME}] Data: {DATA_DIR} ({'portable' if PORTABLE else 'appdata'})", flush=True)
        self._ensure_sound()
        print(f"[{APP_NAME}] Playlist: {len(self.playlist)} file(s)", flush=True)
        for i, f in enumerate(self.playlist):
            print(f"  {i + 1}. {os.path.basename(f)}", flush=True)

        self.audio = AudioManager(self.playlist)

        def _excepthook(exc_type, exc_value, exc_tb):
            import traceback
            print("[EXCEPTION]", flush=True)
            traceback.print_exception(exc_type, exc_value, exc_tb)
        sys.excepthook = _excepthook

        self.qt_app = QApplication(sys.argv)
        self.qt_app.setQuitOnLastWindowClosed(False)

        self.hotkey_mgr = HotkeyManager(self.toggle)
        self.hotkey_mgr.start_polling()
        if self.settings.pause_hotkey:
            ok = self.hotkey_mgr.register(self.settings.pause_hotkey)
            hk = self.settings.pause_hotkey
            print(f"[{APP_NAME}] Hotkey: {hk} ({'ok' if ok else 'failed'})", flush=True)

        self._pen_detector = RawPenDetector()
        self._pen_detector.start()

        self._wintab = WinTabDetector()
        if not self._wintab.start():
            self._wintab = None

        self._pen_hook = PenInputHook()
        self._pen_hook.raw_mouse_mode = (self.settings.input_mode == "mouse")
        self._pen_hook.pen_detector = self._pen_detector
        if self._pen_hook.install():
            mode = self.settings.input_mode
            print(f"[{APP_NAME}] Input: {mode} mode", flush=True)
        else:
            print(f"[{APP_NAME}] WARNING: hook install failed", flush=True)

        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._poll_pen)
        self._poll_timer.start(8)

        self._build_tray()

        print(f"[{APP_NAME}] Running - max volume {self.settings.max_volume}%", flush=True)
        self.qt_app.exec()


if __name__ == "__main__":
    sound = sys.argv[1] if len(sys.argv) > 1 else None
    app = PenASMR(sound_path=sound)
    app.run()
