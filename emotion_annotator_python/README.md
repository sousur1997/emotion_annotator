# Emotion Annotator  ·  v3

PyQt5 desktop application for emotion annotation on audio and video files.
Built for the SignEmo project — JUSense / Jadavpur University.

---

## Setup

### 1. Install Python dependencies

```bash
pip install PyQt5 numpy
# Optional faster audio decoding (wav/flac/ogg):
pip install soundfile
# Optional (librosa handles more formats):
pip install librosa
```

### 2. Install ffmpeg  ← required for MP3 and most video formats

| OS | Command |
|---|---|
| Windows | Download from https://ffmpeg.org → add `bin/` folder to PATH |
| Ubuntu/Debian | `sudo apt install ffmpeg` |
| macOS | `brew install ffmpeg` |

After installing ffmpeg, restart the application.

### 3. Windows video playback fix (DirectShow error 0x80040266)

If video files fail with a DirectShow error, install one of:
- **K-Lite Codec Pack** (recommended): https://codecguide.com/download_kl.htm
- **LAV Filters**: https://github.com/Nevcairiel/LAVFilters/releases

Then restart the application.

### 4. Place emotion wheel image

Copy your `emotion_wheel.png` into the same folder as `main.py`.

### 5. Run

```bash
python main.py
```

---

## UI Layout

```
┌─────────────────────────────────────────────────────────────┬──────────────┐
│  TOP TOOLBAR  (Load · Undo · Redo · Clean · New · Save …)   │              │
├─────────────────────────────────────────────────────────────┤              │
│                                                             │  EMOTION     │
│               MEDIA PANEL                                   │  WHEEL       │
│   (video display or audio banner + transport controls)      │  PANEL       │
│                                                             │              │
├─────────────────────────────────────────────────────────────┤  (resizable) │
│               TIMELINE PANEL                                │              │
│   (waveform + ruler + emotion strips)                       │              │
└─────────────────────────────────────────────────────────────┴──────────────┘
```

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+O` | Load media |
| `Ctrl+S` | Save JSON |
| `Ctrl+N` | New project |
| `Ctrl+Z` | Undo |
| `Ctrl+Shift+Z` | Redo |
| `Ctrl+L` | Clean all strips |
| `Ctrl+C` | Copy selected strip |
| `Ctrl+D` | Duplicate selected strip (with overlap check) |
| `Ctrl+V` | Paste at playhead (with overlap check) |
| `Delete` | Delete selected strip(s) |
| `Space` | Play / Pause |
| `Left` | Previous frame |
| `Right` | Next frame |
| `Shift+Left` | Jump to start |
| `Shift+Right` | Jump to end |

---

## Timeline Controls

| Action | How |
|---|---|
| Seek | Left-click on ruler or waveform area |
| Create strip | Click & drag on empty strip row |
| Move strip | Click body & drag left/right |
| Resize strip | Drag left or right edge handle |
| Select one | Left-click strip body |
| Toggle selection | `Ctrl+Click` strip |
| Box-select | `Shift+Drag` anywhere on canvas |
| Deselect all | Double-click empty area |
| Zoom | Scroll wheel (zoom around cursor) |
| Pan | Middle-mouse drag, or `Shift+Scroll` |
| Fit all | Click **Fit** button |
| Strip context menu | Right-click strip → Copy / Duplicate / Play / Delete |
| Canvas context menu | Right-click empty area → Paste at playhead |
| Play strip range | Select strip → press `P` |

### Strip visual feedback
- **Black outline** — default unselected state
- **Blue outline** — hovered or selected strip
- **Blue top bar** — additional selected indicator
- Flat colour fill (no gradient), lightened from emotion wheel colour

---

## Audio vs Video

- **Audio files** (mp3, wav, flac, ogg, aac, m4a): Shows an audio banner
  with a music icon 🎵 and the filename instead of a black video area.
- **Video files** (mp4, avi, mkv, mov): Shows the video frame.
- Waveform is always shown in the timeline regardless of file type.

---

## Waveform Decoding Priority

1. `soundfile` (fast, wav/flac/ogg) — install with `pip install soundfile`
2. `librosa` (handles more formats) — install with `pip install librosa`
3. `ffmpeg` subprocess (universal fallback — handles mp3, mp4, etc.)

If no decoder works, the waveform area shows a placeholder message.

---

## Paste & Duplicate Overlap Protection

If you try to paste or duplicate a strip and it would overlap an existing
strip, a **toast notification** appears explaining the conflict.
Move the playhead to a free area and try again.

---

## JSON Format

```json
{
  "duration": 44.096,
  "strips": [
    {
      "start": 0.0,
      "end": 2.55,
      "theta": 17.13,
      "r": 0.46
    }
  ]
}
```

---

## File Structure

```
emotion_annotator/
├── main.py              ← entry point
├── main_window.py       ← main window, toolbar, JSON I/O
├── app_state.py         ← shared state + undo/redo
├── media_panel.py       ← video/audio playback + audio banner
├── timeline_panel.py    ← waveform + strips canvas
├── emotion_panel.py     ← emotion wheel + info panel
├── waveform_worker.py   ← background audio decode (soundfile/librosa/ffmpeg)
├── toast.py             ← slide-in toast notifications
├── strip.py             ← Strip data model
├── constants.py         ← WHEEL data + emotion math
├── emotion_wheel.png    ← ⟵ you provide this
└── requirements.txt
```

---

## Recommended Icon Packs (free, for replacing emoji buttons)

| Pack | License | URL |
|---|---|---|
| Phosphor Icons | MIT | https://phosphoricons.com |
| Tabler Icons | MIT | https://tabler.io/icons |
| Lucide | ISC | https://lucide.dev |
| Heroicons | MIT | https://heroicons.com |

Download SVG files, place in `icons/` folder, and load with:
```python
button.setIcon(QIcon("icons/play.svg"))
button.setText("")
button.setIconSize(QSize(20, 20))
```
