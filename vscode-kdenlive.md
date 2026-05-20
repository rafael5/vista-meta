# Kdenlive guide — 15-second VSCode screencast with zoom

End-to-end recipe: from Cinnamon's screen recorder to a polished MP4
+ GIF + poster with two cursor-tracking zoom beats, in **Kdenlive**
on Linux Mint. ~25 minutes start-to-finish, of which Kdenlive work
is ~8 minutes.

Companion to [vscode-screencast.md](vscode-screencast.md). That doc
is the zero-install fast path (no zoom). This doc adds Kdenlive to
the loop when you want cursor-tracking zoom for emphasis.

**See also:** [vscode-davinci.md](vscode-davinci.md) — same workflow
in DaVinci Resolve. Resolve's ease curves are slightly more polished,
but Resolve on Linux **requires a discrete Nvidia or AMD GPU** — AMD
APU iGPUs (Phoenix / 780M / 760M, Intel iGPUs) crash inside the
OpenCL backend on the first compute workload. Kdenlive has no GPU
compute dependency and runs on any hardware.

> **Zoom is added in post** — the recording itself is a flat wide
> shot of full-screen VSCode. Cinnamon's recorder has no zoom
> feature; the zoom-in / hold / zoom-out is layered on top in
> Kdenlive via Transform-effect keyframes (§6–§8). Change anchors,
> timings, or number of zooms any time without re-recording.

## Table of contents

- [Why Kdenlive](#why-kdenlive)
- [1. Install Kdenlive](#1-install-kdenlive)
- [2. One-time Kdenlive preferences](#2-one-time-kdenlive-preferences)
- [3. Record the screencast](#3-record-the-screencast)
- [4. Import and trim](#4-import-and-trim)
- [5. Plan the zoom beats](#5-plan-the-zoom-beats)
- [6. Add the Transform effect](#6-add-the-transform-effect)
- [7. Add zoom keyframes](#7-add-zoom-keyframes)
- [8. Ease the keyframes](#8-ease-the-keyframes)
- [9. Render to MP4](#9-render-to-mp4)
- [10. Generate GIF + poster + AI frames](#10-generate-gif--poster--ai-frames)
- [Keyboard shortcuts cheat sheet](#keyboard-shortcuts-cheat-sheet)

## Why Kdenlive

For a 15-second IDE clip with 1–3 zoom beats on Linux Mint **without
a discrete GPU**:

| Tool | Effort per zoom | Quality | Linux Mint friction |
|---|---|---|---|
| **Kdenlive** | ~90 s | Good (cubic ease) | None — `apt install kdenlive` |
| DaVinci Resolve free | ~60 s | Best | Requires CUDA / discrete AMD; **iGPU = crash** |
| ffmpeg crop+scale+concat | ~5 min (scripted) | Good (hard cuts) | None |
| ffmpeg `zoompan` | ~10 min per zoom | Good (eased) | None |

Kdenlive is the highest quality-per-minute option on Mint without a
discrete GPU. No codec gotchas (reads everything ffmpeg reads), no
compute-backend wrangling, native to the Ubuntu/Mint repos.

## 1. Install Kdenlive

```bash
sudo apt install -y kdenlive
```

That's it. Kdenlive uses **MLT** (Media Lovin' Toolkit) for rendering,
which delegates codec work to ffmpeg — already installed.

Launch from app menu → **Kdenlive**, or `kdenlive` from any terminal.

**First launch** runs a Configuration Wizard:

- **MLT engine, profile detection** → click **Next**.
- **Default profile** → **HD 1080p 30 fps** (matches Cinnamon's
  recording resolution).
- **Hardware acceleration** → leave disabled. Pure-CPU rendering on
  a 15 s 1080p clip is ~30 s; not worth the configuration tax.

## 2. One-time Kdenlive preferences

**Settings → Configure Kdenlive:**

- **Misc → Default project folder:** `~/projects/<your-project>/.kdenlive/`
  (keeps Kdenlive's auto-saves out of `media/`).
- **Project Defaults → Profile:** HD 1080p 30 fps.
- **Project Defaults → Video Tracks:** 2 (plenty for one clip).
- **Timeline → Auto-save every:** 60 seconds.
- **Capture → Screen Grab:** skip — Cinnamon's recorder is faster.

**OK** → close.

## 3. Record the screencast

Same staging as the fast path:

1. Top-right tray → **Do Not Disturb** on.
2. VSCode: `Ctrl+B` (sidebar), `Ctrl+J` (panel), `F11` (full-screen).
3. Editor: 16–18 pt font, `editor.cursorBlinking: "solid"`.
4. Open the demo file. Cursor on line 1.
5. System Settings → Mouse → pointer size **36 px**.
6. Press **`Ctrl+Alt+Shift+R`** → do the demo (aim 15 s) →
   **`Ctrl+Alt+Shift+R`** again to stop.

```bash
mkdir -p media
mv ~/cinnamon-dbus-recording-*.webm media/demo-master.webm
```

**No pre-conversion needed** — Kdenlive reads VP8/WebM natively via
ffmpeg. (This is the headline win over Resolve free on Linux.)

## 4. Import and trim

1. **Project → New** (or `Ctrl+N`). Confirm profile = **HD 1080p
   30 fps**. Save to
   `~/projects/<your-project>/.kdenlive/vscode-demo.kdenlive`.
2. **Drag `media/demo-master.webm` into the Project Bin** (top-left
   panel). Kdenlive scans, generates a thumbnail.
3. **Drag the clip from the Project Bin onto Video Track 1** in the
   Timeline. It snaps to 00:00.
4. **Trim to ~15 s:**
   - **Razor** tool (`X`) → click at the in-point to slice, click at
     the out-point to slice again.
   - **Selection** tool (`S`) → click the unwanted head/tail
     segments → `Delete`.
   - *Or:* select the clip and drag its left/right edges inward — the
     cursor changes to a resize arrow.
5. Verify duration in the timeline ruler (top of timeline panel).

## 5. Plan the zoom beats

For a 15-second clip, **two zoom beats** is the sweet spot. Sketch:

```
0:00 – 0:04   wide      intro action
0:04 – 0:05   ZOOM IN   to autocomplete dropdown
0:05 – 0:06   hold      reveal
0:06 – 0:07   zoom OUT
0:07 – 0:11   wide      next action
0:11 – 0:12   ZOOM IN   to diagnostic hover card
0:12 – 0:14   hold
0:14 – 0:15   zoom OUT
```

For each zoom, identify the **anchor point** — where in the 1920×1080
source frame the action lands. Easiest method: scrub to the moment of
action and **eyeball the position** in the Project Monitor (top-right
viewer). Kdenlive doesn't show live coordinates; approximate is fine
("upper-third, right-side" is enough — we'll drag-to-center in §7).

## 6. Add the Transform effect

1. **Click the clip** on the timeline (single click selects it).
2. Open the **Effects** panel (right side). If not visible:
   **View → Effects** or `Ctrl+9`.
3. In the Effects search box, type `Transform`.
4. **Double-click "Transform"** (under "Distort") — or drag it onto
   the clip. The effect attaches to the clip.
5. The **Effect Stack** panel (right side, may share space with the
   Project Monitor) now exposes Transform's parameters:
   - **Position** (X, Y) — top-left of the rendered frame in canvas px
   - **Size** (W, H) — output size of the rendered frame in canvas px
   - **Rotation** — leave 0
   - **Distort / Opacity** — leave defaults

For zooming, we keyframe Position and Size only.

## 7. Add zoom keyframes

Repeat for each zoom beat.

1. **Move the timeline playhead** to the start of the zoom-in
   (e.g., 0:04).
2. In the Effect Stack, click the **keyframe / clock icon** next to
   **Position** and **Size**. Enables keyframing and adds a keyframe
   at the current time with current values
   (Position = 0, 0; Size = 1920×1080).
3. **Move playhead forward 300 ms** (~9 frames at 30 fps; tap
   `Right` nine times, or `Shift+Right` for 1-second jumps and
   back off).
4. **Change Size** to **3840×2160** (2× the source). The image now
   extends past the canvas — that's expected.
5. **Re-center the anchor:** in the Project Monitor, drag the
   image until the anchor lands at the canvas center. Kdenlive
   writes the Position values live as you drag. (Avoids manual
   coordinate math; Position = `960 − 2·anchor_x`, `540 − 2·anchor_y`
   if you prefer typing.)
6. A new keyframe lands automatically when you change a keyframed
   value.
7. **Move playhead forward ~1 s** (the hold). On each parameter row,
   click the **add-keyframe** button (`+`) to copy current values
   as a new keyframe — this freezes the zoom in place.
8. **Move playhead forward 300 ms.**
9. **Reset Size** to **1920×1080**, **Position** to **0, 0** (use
   the reset arrow on each field).

Four keyframes per zoom beat: `start-wide`, `end-zoom-in`,
`end-hold`, `end-wide`.

## 8. Ease the keyframes

Linear interpolation reads robotic. Cubic ease-in-out reads
cinematic.

1. In the Effect Stack, the Position and Size rows each show a
   horizontal keyframe strip with ◆ markers per keyframe.
2. **Right-click each ◆ keyframe** → **Interpolation** → **Smooth**
   (Kdenlive's cubic ease-in-out — labeled "Smooth" in 22.x/23.x,
   "Ease In/Out" or "Cubic" in 24.x+).
3. Repeat for every keyframe on both Position and Size.
4. **Preview:** move the playhead ~1 s before the zoom, press
   `Space`. Watch in the Project Monitor.

## 9. Render to MP4

1. **Project → Render** (or `Ctrl+Enter`).
2. **Output file:** `~/projects/<your-project>/media/demo.mp4`.
3. **Category:** **Generic** → preset **MP4-H264/AAC**
   (or **File Rendering → MP4** in newer Kdenlive).
4. **Resolution:** **From project** (1920×1080).
5. **Quality slider:** ~80 (CRF ~20).
6. **Audio:** disable — Cinnamon recorded none. (Render dialog →
   Audio tab → uncheck **Export audio**.)
7. Click **Render to File**.
8. Jobs tab shows progress. ~30 s on a modern CPU for a 15 s clip.

**Re-mux for `+faststart`** so the MP4 starts playing while
downloading on github.com (MLT's renderer doesn't set the flag):

```bash
ffmpeg -i media/demo.mp4 -c copy -movflags +faststart media/_demo.mp4
mv media/_demo.mp4 media/demo.mp4
```

## 10. Generate GIF + poster + AI frames

Re-use `scripts/make-demo-assets.sh` from
[vscode-screencast.md](vscode-screencast.md):

```bash
scripts/make-demo-assets.sh media/demo.mp4
```

You now have:

| File | Target |
|---|---|
| `media/demo.mp4` | GitHub README (`<video autoplay loop muted>`) |
| `media/demo.gif` (800 px) | VSCode Marketplace |
| `media/demo-poster.png` | `<video poster="…">` |
| `media/demo-frames/frame_NN.png` × 6 | AI multimodal ingestion |

## Keyboard shortcuts cheat sheet

| Action | Shortcut |
|---|---|
| Play / pause | `Space` |
| Step one frame | `Right` / `Left` |
| Step one second | `Shift+Right` / `Shift+Left` |
| Razor (blade) tool | `X` |
| Selection tool | `S` |
| Spacer (gap-insert) tool | `M` |
| Delete clip | `Delete` |
| Ripple delete | `Shift+Delete` |
| Zoom timeline in / out | `Ctrl+=` / `Ctrl+-` |
| Fit timeline to view | `0` |
| Go to start / end | `Home` / `End` |
| Project Monitor | `Ctrl+Shift+O` |
| Effects panel | `Ctrl+9` |
| Render dialog | `Ctrl+Enter` |
| Save project | `Ctrl+S` |

---

**See also:**

- [vscode-screencast.md](vscode-screencast.md) — zero-install fast path
- [vscode-davinci.md](vscode-davinci.md) — DaVinci Resolve workflow
  (requires discrete Nvidia / AMD GPU)
- [screen-recording-how-to.md](screen-recording-how-to.md) — full
  reference (OBS, VirtualBox, ffmpeg cheatsheet, troubleshooting)
