# SketchASMR

A small Windows app that plays a "writing on paper" sound (or any other audio files you want to play) whenever your drawing tablet's pen touches the surface. Pen pressure controls the volume — light strokes are quiet, heavy strokes are loud.

Built for any Windows Ink or WinTab-supported tablet (Wacom, Huion, Gaomon, etc.).

## For users

### Getting started

An installer is available if you'd like to have a dedicated place for SketchASMR to run from, including where you manage your sound files.

Alternatively, you can just run `SketchASMR.exe`. A small icon appears in the system tray (bottom-right of the taskbar, near the clock).

- **Green icon** — monitoring is active. Touch pen to surface to hear the sound.
- **Grey icon** — monitoring is paused.

| Action | How |
|---|---|
| **Toggle on/off** | Double-click the tray icon, or press **Ctrl+Shift+P** |
| **Quit** | Right-click the tray icon → Quit |

### Sounds

The build **bundles a default set of custom drawing/ASMR-style clips** shipped in `sounds/`. On first run, those bundled files are copied into `%APPDATA%\SketchASMR\sounds` if that folder does not exist yet. If you're updating to this I recommend deleting this directory first.

Open **Settings** to see the list, add your own files, paste an audio URL, or use **Open Folder**. **MP3, WAV, and OGG** play directly. **M4A / AAC** need **ffmpeg** on `PATH` or downloaded via the URL feature (cached under `%APPDATA%\SketchASMR\bin`); they are transcoded to a WAV cache on first use.

The app uses whatever files it finds there (sorted alphabetically; you can exclude files in settings). Long recordings work too — playback pauses when the pen lifts and resumes from the same position when it touches down again.

### Removing

**Portable:** Delete `SketchASMR.exe`. To remove settings, sounds, and cache, delete `%APPDATA%\SketchASMR`.

**Installer:** Uninstall from **Settings → Apps** (or **Add or remove programs**). Optionally delete `%APPDATA%\SketchASMR` if you want user data gone too.

---

## For developers

### Requirements

- Windows 10+
- Python 3.10+
- Drawing tablet with WinTab drivers installed

### Running from source

```
pip install -r requirements.txt
python sketch_asmr.py
```

### Building the portable exe

Run `build.bat`. This installs dependencies and uses PyInstaller to produce a single standalone file at `dist\SketchASMR.exe`.

### Project structure

```
SketchASMR/
├── sketch_asmr.py           Main application
├── requirements.txt      Python dependencies
├── build.bat             One-click build script
├── sounds/
│   └── *.mp3 / *.wav / *.ogg / …   Bundled default clips
└── README.md
```

### How it works

1. **Pen pressure** — Reads stylus pressure through the WinTab API (`wintab32.dll`), which is installed alongside tablet drivers. Supports the full pressure range of the device (up to 8192 levels).

2. **Audio** — Streams an audio file (MP3/WAV/OGG) using `pygame.mixer.music` (or decoded `Sound` buffers when the max volume is above 100% for digital gain). Playback pauses when the pen lifts and resumes from the same position on the next stroke. Volume scales with pressure (5% floor at lightest touch, up to the “Max” slider at full pressure; the slider goes to 150% for extra loudness, which can clip on hot masters). Loops back to the start when the file ends.

3. **Fallback** — If WinTab is unavailable, detects left-mouse-button state as a proxy for pen contact (not pressure-sensitive, but functional).

4. **System tray** — Runs silently in the background with a tray icon. No visible window, no console, no interference with drawing apps.

---

Made by [janitorpuppo](https://janitor.gg)
