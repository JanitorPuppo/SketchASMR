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

### Custom sounds

Open settings to view your sound files currently available. if you'd like, you can add your own files or provide a link. You can also view your available files by clicking Open Folder. 

The app picks the first audio file it finds (sorted alphabetically). Long recordings work well — playback pauses when the pen lifts and resumes from the same position when it touches down again. If no custom file is found, the bundled placeholder sound is used.

### Removing

For Portable, nothing is installed. Simply delete the executable. If you'd like to clean up the sound folder as well, that can be found at %appdata%/SketchASMR

for the Installer version, simply find the application in your installed applications list and run the uninstaller.

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

Run `build.bat`. This installs dependencies and uses PyInstaller to produce a single standalone file at `dist\SketchASMR.exe`.

### Project structure

```
SketchASMR/
├── pen_asmr.py           Main application
├── requirements.txt      Python dependencies
├── build.bat             One-click build script
├── sounds/
│   └── *.mp3/wav/ogg     Sound file (placeholder generated if missing)
└── README.md
```

### How it works

1. **Pen pressure** — Reads stylus pressure through the WinTab API (`wintab32.dll`), which is installed alongside tablet drivers. Supports the full pressure range of the device (up to 8192 levels).

2. **Audio** — Streams an audio file (MP3/WAV/OGG) using `pygame.mixer.music`. Playback pauses when the pen lifts and resumes from the same position on the next stroke. Volume scales with pressure (15% at lightest touch, 100% at full pressure). Loops back to the start when the file ends.

3. **Fallback** — If WinTab is unavailable, detects left-mouse-button state as a proxy for pen contact (not pressure-sensitive, but functional).

4. **System tray** — Runs silently in the background with a tray icon. No visible window, no console, no interference with drawing apps.

---

Made by [janitorpuppo](https://janitor.gg)
