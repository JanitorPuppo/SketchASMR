import ctypes
from ctypes import wintypes, Structure, WINFUNCTYPE, c_uint, c_int, c_long, c_ulong, c_void_p, byref, sizeof
import threading
import time
import os
import sys
import wave
import math
import array
import random

import pygame
import pystray
from PIL import Image, ImageDraw


if getattr(sys, "frozen", False):
    EXE_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = sys._MEIPASS
else:
    EXE_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = EXE_DIR

SOUND_DIR = os.path.join(EXE_DIR, "sounds")
BUNDLED_SOUND = os.path.join(BUNDLE_DIR, "sounds", "writing.wav")
DEFAULT_SOUND = os.path.join(SOUND_DIR, "writing.wav")
APP_NAME = "DrawTablet ASMR"

# ── WinTab constants ─────────────────────────────────────────────────────────

WT_PACKET = 0x7FF0
WTI_DEVICES = 100
WTI_DEFSYSCTX = 4
DVC_NPRESSURE = 18
LCNAMELEN = 40

CXO_SYSTEM = 0x0001
CXO_MESSAGES = 0x0004

PK_NORMAL_PRESSURE = 0x0400


class AXIS(Structure):
    _fields_ = [
        ("axMin", c_long),
        ("axMax", c_long),
        ("axUnits", c_uint),
        ("axResolution", c_ulong),
    ]


class LOGCONTEXT(Structure):
    _fields_ = [
        ("lcName", ctypes.c_wchar * LCNAMELEN),
        ("lcOptions", c_uint),
        ("lcStatus", c_uint),
        ("lcLocks", c_uint),
        ("lcMsgBase", c_uint),
        ("lcDevice", c_uint),
        ("lcPktRate", c_uint),
        ("lcPktData", c_ulong),
        ("lcPktMode", c_ulong),
        ("lcMoveMask", c_ulong),
        ("lcBtnDnMask", c_ulong),
        ("lcBtnUpMask", c_ulong),
        ("lcInOrgX", c_long),
        ("lcInOrgY", c_long),
        ("lcInOrgZ", c_long),
        ("lcInExtX", c_long),
        ("lcInExtY", c_long),
        ("lcInExtZ", c_long),
        ("lcOutOrgX", c_long),
        ("lcOutOrgY", c_long),
        ("lcOutOrgZ", c_long),
        ("lcOutExtX", c_long),
        ("lcOutExtY", c_long),
        ("lcOutExtZ", c_long),
        ("lcSensX", c_ulong),
        ("lcSensY", c_ulong),
        ("lcSensZ", c_ulong),
        ("lcSysMode", ctypes.c_bool),
        ("lcSysOrgX", c_long),
        ("lcSysOrgY", c_long),
        ("lcSysExtX", c_long),
        ("lcSysExtY", c_long),
        ("lcSysSensX", c_ulong),
        ("lcSysSensY", c_ulong),
    ]


class PACKET(Structure):
    _fields_ = [
        ("pkNormalPressure", c_uint),
    ]


# ── Win32 constants ──────────────────────────────────────────────────────────

WM_DESTROY = 0x0002
WM_HOTKEY = 0x0312
WM_TIMER = 0x0113
WM_USER = 0x0400
WM_QUIT_APP = WM_USER + 1
WS_OVERLAPPED = 0x00000000
WS_EX_TOOLWINDOW = 0x00000080
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
HOTKEY_TOGGLE = 1
TIMER_ID = 1

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WNDPROC = WINFUNCTYPE(c_long, wintypes.HWND, c_uint, wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASSEXW(Structure):
    _fields_ = [
        ("cbSize", c_uint),
        ("style", c_uint),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", c_int),
        ("cbWndExtra", c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HICON),
    ]


# ── Tray icon image generation ───────────────────────────────────────────────

def make_tray_icon(active):
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    bg_color = (76, 175, 80, 255) if active else (158, 158, 158, 255)
    draw.ellipse([4, 4, 60, 60], fill=bg_color)

    pen_color = (255, 255, 255, 255)
    draw.line([22, 42, 42, 18], fill=pen_color, width=5)
    draw.polygon([(42, 18), (46, 14), (44, 22)], fill=pen_color)
    draw.line([20, 46, 38, 46], fill=pen_color, width=2)

    return img


# ── Placeholder sound generation ─────────────────────────────────────────────

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
    def __init__(self, sound_path):
        pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
        self.sound = pygame.mixer.Sound(sound_path)
        self.channel = None
        self.playing = False
        self.current_volume = 0.0

    def play(self, volume=1.0):
        vol = max(0.0, min(1.0, volume))
        if not self.playing:
            self.sound.set_volume(vol)
            self.channel = self.sound.play(loops=-1)
            self.playing = True
            self.current_volume = vol
        elif abs(vol - self.current_volume) > 0.05:
            self.sound.set_volume(vol)
            self.current_volume = vol

    def stop(self):
        if self.playing and self.channel:
            self.channel.fadeout(80)
            self.playing = False
            self.current_volume = 0.0

    def cleanup(self):
        pygame.mixer.quit()


# ── WinTab interface ─────────────────────────────────────────────────────────

class WinTabManager:
    def __init__(self):
        self.wintab = None
        self.hctx = None
        self.max_pressure = 8192
        self.available = False
        self._load()

    def _load(self):
        try:
            self.wintab = ctypes.WinDLL("wintab32.dll")
            self.wintab.WTInfoW.restype = c_uint
            self.wintab.WTInfoW.argtypes = [c_uint, c_uint, c_void_p]
            self.wintab.WTOpenW.restype = c_void_p
            self.wintab.WTOpenW.argtypes = [wintypes.HWND, ctypes.POINTER(LOGCONTEXT), ctypes.c_bool]
            self.wintab.WTPacket.restype = ctypes.c_bool
            self.wintab.WTPacket.argtypes = [c_void_p, c_uint, c_void_p]
            self.wintab.WTClose.restype = ctypes.c_bool
            self.wintab.WTClose.argtypes = [c_void_p]
            self.wintab.WTEnable.restype = ctypes.c_bool
            self.wintab.WTEnable.argtypes = [c_void_p, ctypes.c_bool]

            pressure_axis = AXIS()
            ret = self.wintab.WTInfoW(WTI_DEVICES, DVC_NPRESSURE, byref(pressure_axis))
            if ret > 0 and pressure_axis.axMax > 0:
                self.max_pressure = pressure_axis.axMax

            self.available = True
        except OSError:
            self.available = False

    def open_context(self, hwnd):
        if not self.available:
            return False

        lc = LOGCONTEXT()
        ret = self.wintab.WTInfoW(WTI_DEFSYSCTX, 0, byref(lc))
        if ret == 0:
            return False

        lc.lcName = "PenASMR"
        lc.lcOptions |= CXO_MESSAGES | CXO_SYSTEM
        lc.lcPktData = PK_NORMAL_PRESSURE
        lc.lcPktMode = 0
        lc.lcMoveMask = PK_NORMAL_PRESSURE
        lc.lcMsgBase = WT_PACKET

        self.hctx = self.wintab.WTOpenW(hwnd, byref(lc), True)
        return bool(self.hctx)

    def read_packet(self, serial):
        if not self.hctx:
            return None
        pkt = PACKET()
        if self.wintab.WTPacket(self.hctx, serial, byref(pkt)):
            return pkt.pkNormalPressure
        return None

    def close(self):
        if self.hctx:
            self.wintab.WTClose(self.hctx)
            self.hctx = None


# ── Fallback: mouse-button detection ────────────────────────────────────────

class MouseFallback:
    def __init__(self):
        self.pressed = False

    def poll(self):
        state = ctypes.windll.user32.GetAsyncKeyState(0x01)
        currently_pressed = bool(state & 0x8000)
        changed = currently_pressed != self.pressed
        self.pressed = currently_pressed
        return (1.0 if currently_pressed else 0.0, changed)


# ── Main application ─────────────────────────────────────────────────────────

class PenASMR:
    def __init__(self, sound_path=DEFAULT_SOUND):
        self.sound_path = sound_path
        self.monitoring = False
        self.running = False
        self.hwnd = None
        self.wintab = WinTabManager()
        self.audio = None
        self.fallback = None
        self.use_fallback = False
        self.tray_icon = None
        self._wndproc_ref = None
        self._msg_thread = None

    def _ensure_sound(self):
        if not os.path.exists(self.sound_path):
            if os.path.exists(BUNDLED_SOUND):
                self.sound_path = BUNDLED_SOUND
            else:
                generate_placeholder_wav(self.sound_path)

    def _create_window(self):
        hInstance = kernel32.GetModuleHandleW(None)
        class_name = "PenASMR_Hidden"

        self._wndproc_ref = WNDPROC(self._wnd_proc)

        wc = WNDCLASSEXW()
        wc.cbSize = sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = self._wndproc_ref
        wc.hInstance = hInstance
        wc.lpszClassName = class_name

        user32.RegisterClassExW(byref(wc))

        self.hwnd = user32.CreateWindowExW(
            WS_EX_TOOLWINDOW, class_name, "PenASMR", WS_OVERLAPPED,
            0, 0, 1, 1, None, None, hInstance, None,
        )
        user32.RegisterHotKey(self.hwnd, HOTKEY_TOGGLE, MOD_CONTROL | MOD_SHIFT, 0x50)

    def _wnd_proc(self, hwnd, msg, wParam, lParam):
        if msg == WT_PACKET and self.monitoring:
            pressure_raw = self.wintab.read_packet(wParam)
            if pressure_raw is not None:
                self._handle_pressure(pressure_raw)
            return 0

        if msg == WM_HOTKEY and wParam == HOTKEY_TOGGLE:
            self.toggle()
            return 0

        if msg == WM_TIMER and wParam == TIMER_ID and self.use_fallback and self.monitoring:
            pressure, changed = self.fallback.poll()
            if changed:
                self._handle_pressure(int(pressure * self.wintab.max_pressure))
            return 0

        if msg == WM_QUIT_APP:
            user32.PostQuitMessage(0)
            return 0

        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0

        return user32.DefWindowProcW(hwnd, msg, wParam, lParam)

    def _handle_pressure(self, pressure_raw):
        if pressure_raw > 0:
            volume = max(0.15, min(1.0, pressure_raw / self.wintab.max_pressure))
            self.audio.play(volume)
        else:
            self.audio.stop()

    def toggle(self):
        self.monitoring = not self.monitoring
        if not self.monitoring and self.audio:
            self.audio.stop()
        self._update_tray()

    def _update_tray(self):
        if self.tray_icon:
            self.tray_icon.icon = make_tray_icon(self.monitoring)
            status = "ON" if self.monitoring else "OFF"
            self.tray_icon.title = f"{APP_NAME} — {status}"
            self.tray_icon.update_menu()

    def _on_tray_toggle(self, icon, item):
        self.toggle()

    def _on_tray_quit(self, icon, item):
        icon.stop()
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_QUIT_APP, 0, 0)

    def _get_toggle_text(self, item):
        return "Pause" if self.monitoring else "Resume"

    def _build_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem(self._get_toggle_text, self._on_tray_toggle, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._on_tray_quit),
        )
        self.tray_icon = pystray.Icon(
            APP_NAME,
            icon=make_tray_icon(True),
            title=f"{APP_NAME} — ON",
            menu=menu,
        )

    def _run_message_loop(self):
        self._create_window()

        if self.wintab.available and self.wintab.open_context(self.hwnd):
            self.use_fallback = False
        else:
            self.fallback = MouseFallback()
            self.use_fallback = True
            user32.SetTimer(self.hwnd, TIMER_ID, 16, None)

        self.monitoring = True
        self.running = True
        self._update_tray()

        msg = wintypes.MSG()
        while self.running:
            ret = user32.GetMessageW(byref(msg), None, 0, 0)
            if ret == 0 or ret == -1:
                break
            user32.TranslateMessage(byref(msg))
            user32.DispatchMessageW(byref(msg))

        self._cleanup()

    def run(self):
        self._ensure_sound()
        self.audio = AudioManager(self.sound_path)
        self._build_tray()

        self._msg_thread = threading.Thread(target=self._run_message_loop, daemon=True)
        self._msg_thread.start()

        self.tray_icon.run()

        self._msg_thread.join(timeout=3)

    def _cleanup(self):
        self.running = False
        self.monitoring = False
        if self.audio:
            self.audio.stop()
            self.audio.cleanup()
        self.wintab.close()
        if self.hwnd:
            user32.UnregisterHotKey(self.hwnd, HOTKEY_TOGGLE)
            user32.KillTimer(self.hwnd, TIMER_ID)
            user32.DestroyWindow(self.hwnd)


if __name__ == "__main__":
    sound = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SOUND
    app = PenASMR(sound_path=sound)
    app.run()
