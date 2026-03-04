# DrawTablet ASMR

A small Windows app that plays a "writing on paper" sound whenever your drawing tablet's pen touches the surface. Pen pressure controls the volume — light strokes are quiet, heavy strokes are loud.

Built for the **XPPen Artist 24 Pro** and compatible with any WinTab-supported tablet (Wacom, Huion, Gaomon, etc.).

## For users

### Getting started

No installation needed — just run `DrawTablet ASMR.exe`. A small icon appears in the system tray (bottom-right of the taskbar, near the clock).

- **Green icon** — monitoring is active. Touch pen to surface to hear the sound.
- **Grey icon** — monitoring is paused.

| Action | How |
|---|---|
| **Toggle on/off** | Double-click the tray icon, or press **Ctrl+Shift+P** |
| **Quit** | Right-click the tray icon → Quit |

### Custom sound

Create a `sounds` folder next to the exe and place a file called `writing.wav` inside it:

```
DrawTablet ASMR.exe
sounds/
  └── writing.wav       ← your custom sound
```

A short (2–5 second) loopable WAV recording of pen-on-paper works best. If no custom file is found, the bundled placeholder sound is used.

### Removing

Delete the exe. That's it — nothing is installed on the system.

---

## For developers

### Requirements

- Windows 10+
- Python 3.10+
- Drawing tablet with WinTab drivers installed

### Running from source

```
pip install -r requirements.txt
python pen_asmr.py
```

### Building the portable exe

Run `build.bat`. This installs dependencies and uses PyInstaller to produce a single standalone file at `dist\DrawTablet ASMR.exe`.

### Project structure

```
DrawTablet ASMR/
├── pen_asmr.py           Main application
├── requirements.txt      Python dependencies
├── build.bat             One-click build script
├── sounds/
│   └── writing.wav       Sound file (auto-generated if missing)
└── README.md
```

### How it works

1. **Pen pressure** — Reads stylus pressure through the WinTab API (`wintab32.dll`), which is installed alongside tablet drivers. Supports the full pressure range of the device (up to 8192 levels).

2. **Audio** — Loops a WAV file while the pen is pressed. Volume scales with pressure (15% at lightest touch, 100% at full pressure). Fades out when the pen lifts.

3. **Fallback** — If WinTab is unavailable, detects left-mouse-button state as a proxy for pen contact (not pressure-sensitive, but functional).

4. **System tray** — Runs silently in the background with a tray icon. No visible window, no console, no interference with drawing apps.
