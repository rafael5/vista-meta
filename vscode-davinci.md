# DaVinci Resolve guide — 15-second VSCode screencast with zoom

End-to-end recipe: from Cinnamon's built-in screen recorder to a
polished MP4 + GIF + poster with two cursor-tracking zoom beats, in
**DaVinci Resolve (free)** on Linux Mint. ~30 minutes start-to-finish,
of which Resolve work is ~10 minutes.

Companion to [vscode-screencast.md](vscode-screencast.md). That doc
is the zero-install fast path (no zoom). This doc adds Resolve to the
loop when you want cursor-tracking zoom for emphasis.

> ### ⚠️ Linux GPU requirement
>
> DaVinci Resolve on Linux **requires a discrete Nvidia GPU (CUDA)
> or discrete AMD GPU (ROCm)**. **Integrated APU graphics — Intel
> iGPUs, AMD Radeon 780M / 760M / Phoenix — are unsupported**:
> Resolve crashes inside its OpenCL backend (`libRusticlOpenCL.so`
> or `libamdocl64.so`, signal 11) the first time it tries to
> dispatch a compute workload.
>
> Check before you invest in the install:
> ```bash
> lspci | grep -iE 'vga|3d|display'
> nvidia-smi 2>/dev/null   # any output = Nvidia present
> ```
> No discrete GPU? Use **[vscode-kdenlive.md](vscode-kdenlive.md)**
> instead — same workflow, no GPU compute dependency, no codec
> gotchas. The Resolve ease-curves are marginally smoother; for a
> 15-second README hero clip the difference is invisible.

## Table of contents

- [Why DaVinci Resolve](#why-davinci-resolve)
- [1. Install DaVinci Resolve free](#1-install-davinci-resolve-free)
- [2. The Linux codec gotcha](#2-the-linux-codec-gotcha)
- [3. One-time Resolve project setup](#3-one-time-resolve-project-setup)
- [4. Record the screencast](#4-record-the-screencast)
- [5. Pre-convert and import](#5-pre-convert-and-import)
- [6. Plan the zoom beats](#6-plan-the-zoom-beats)
- [7. Add zoom keyframes](#7-add-zoom-keyframes)
- [8. Ease the keyframes](#8-ease-the-keyframes)
- [9. Export to MP4](#9-export-to-mp4)
- [10. Generate GIF + poster + AI frames](#10-generate-gif--poster--ai-frames)
- [Keyboard shortcuts cheat sheet](#keyboard-shortcuts-cheat-sheet)

## Why DaVinci Resolve

For a 15-second IDE clip with 1–3 zoom beats:

| Tool | Effort per zoom | Quality | Linux |
|---|---|---|---|
| **DaVinci Resolve (free)** | ~60 s | Best (Studio-grade ease curves) | Yes |
| Kdenlive | ~90 s | Good | Yes |
| ffmpeg crop+scale+concat | ~5 min (scripted) | Good (hard cuts) | Yes |
| ffmpeg `zoompan` | ~10 min per zoom | Good (eased) | Yes |
| OBS + Move plugin | ~5 min setup | Medium | Yes |

Resolve free is the highest quality-per-minute option on Linux. The
codec gotcha in §2 is a one-time nuisance you wrap in a shell function
and forget.

## 1. Install DaVinci Resolve free

1. Go to the **[Blackmagic Design DaVinci Resolve download page](https://www.blackmagicdesign.com/support/family/davinci-resolve-and-fusion)**.
   Under the latest **DaVinci Resolve 19** entry, click **Linux**
   (the **free** download, *not* "DaVinci Resolve Studio"). Fill the
   registration form — name, email, country, phone — and the
   `.zip` (~3 GB) starts downloading.
   - Product overview / marketing: https://www.blackmagicdesign.com/products/davinciresolve
   - Direct downloads: https://www.blackmagicdesign.com/support/family/davinci-resolve-and-fusion
2. Unzip and run (version string varies; the zip includes the exact
   command in `DaVinci-Resolve-Linux_Installation_Instructions.html`):
   ```bash
   cd ~/Downloads
   unzip DaVinci_Resolve_*_Linux.zip
   chmod +x DaVinci_Resolve_*_Linux.run
   sudo ./DaVinci_Resolve_*_Linux.run -i
   ```
   **On Linux Mint 22 / Ubuntu 24.04 (Noble):** the installer's
   package check fails on the `t64` library rename, and Resolve's
   bundled GLib 2.68 conflicts with system pango. See
   [Appendix A](#appendix-a--linux-mint-22--ubuntu-noble-install-gotchas)
   before you `sudo ./...`.
3. Confirm GPU is usable:
   ```bash
   # Nvidia: needs proprietary driver + CUDA
   nvidia-smi
   # AMD/Intel: needs OpenCL
   sudo apt install ocl-icd-libopencl1 clinfo
   clinfo | grep "Device Name"
   ```
4. Launch **DaVinci Resolve** from the application menu. First launch
   creates `~/.local/share/DaVinciResolve/` and shows the Project
   Manager.

## 2. The Linux codec gotcha

**Read this once; the rest of the doc assumes you've done it.**

Resolve **free** on Linux **cannot import H.264 MP4 or VP8/9 WebM** —
H.264/AAC and VP9 require the Studio license ($295) on Linux only.
Cinnamon's recorder produces VP8 WebM, which Resolve free refuses
to open.

**Fix:** transcode source to **DNxHR HQ in a MOV container** (royalty-
free; Resolve free reads/writes it natively).

Drop this into `~/scripts/bin/to-resolve`:

```bash
#!/usr/bin/env bash
# to-resolve: transcode any video to DNxHR MOV for DaVinci Resolve free
set -euo pipefail
src="$1"
out="${src%.*}.resolve.mov"
ffmpeg -y -i "$src" \
  -c:v dnxhd -profile:v dnxhr_hq -pix_fmt yuv422p \
  -c:a pcm_s16le -movflags +faststart \
  "$out"
echo "Wrote $out"
```

```bash
chmod +x ~/scripts/bin/to-resolve
```

On macOS / Windows, skip this section — Resolve free imports H.264
natively on those platforms.

## 3. One-time Resolve project setup

Set defaults once; every new project inherits them.

1. Launch Resolve. In Project Manager, right-click empty area → **Project Settings** (or **gear icon, bottom-right** once inside a project).
2. **Master Settings:**
   - **Timeline resolution:** 1920 × 1080 HD
   - **Timeline frame rate:** 30 fps
   - **Playback frame rate:** 30
3. **Image Scaling:**
   - **Input Scaling preset:** Scale entire image to fit
   - **Mismatched resolution files:** Scale entire image to fit
4. **Save** → tick **Save as default**.
5. **Preferences → User → UI Settings → Auto save → every 5 minutes.**
   Resolve free will crash eventually; auto-save is your seatbelt.

## 4. Record the screencast

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

## 5. Pre-convert and import

```bash
to-resolve media/demo-master.webm
# → media/demo-master.resolve.mov
```

In Resolve:

1. **Project Manager → New Project** → name it `vscode-demo` → Create.
2. Bottom toolbar: switch to the **Edit** page.
3. Drag `media/demo-master.resolve.mov` into the **Media Pool**
   (top-left panel).
4. Drag the clip from the Media Pool onto the empty **Timeline**
   (bottom panel). Resolve creates a `Video 1` track and places the
   clip at 00:00.
5. **Trim to ~15 seconds:**
   - Scrub to the in-point, press **`I`**.
   - Scrub to the out-point, press **`O`**.
   - Right-click in the source viewer → **Insert Clip** (replaces the
     untrimmed clip on the timeline).
   - *Or* use the **Razor** tool (`B`), slice, then select & delete
     unwanted segments.
6. Verify duration in the bottom-right of the timeline viewer (should
   read ~`00:00:15:00`).

## 6. Plan the zoom beats

For a 15-second clip, **two zoom beats is the sweet spot** — one
mid-clip, optionally one near the end. More than two feels frantic.

Sketch on paper:

```
0:00 – 0:04   wide      intro action (open file, type)
0:04 – 0:05   ZOOM IN   to autocomplete dropdown
0:05 – 0:06   hold      reveal the result
0:06 – 0:07   zoom OUT
0:07 – 0:11   wide      next action
0:11 – 0:12   ZOOM IN   to diagnostic hover card
0:12 – 0:14   hold
0:14 – 0:15   zoom OUT
```

For each zoom, identify the **anchor point** in source pixels — the
(cx, cy) where the action will land. Easiest method: scrub the
timeline to the moment of action and hover the cursor over that
point in the viewer; Resolve shows the pixel coordinates in the
viewer's bottom strip.

## 7. Add zoom keyframes

Repeat this procedure once per zoom beat.

1. **Click the clip** on the timeline to select it.
2. Open the **Inspector** (top-right; "i" icon if collapsed).
3. **Video** tab → expand **Transform** if collapsed.
4. **Move playhead** to the start of the zoom-in (e.g., 0:04).
5. Click the **◆ keyframe diamond** to the right of **Zoom**. A
   keyframe lands at current values (Zoom = 1.000).
6. Click the **◆** next to **Position** too (Position = 0, 0).
7. **Step forward 9 frames** (300 ms @ 30 fps): press **`→` nine
   times**, or hold Shift+→ for a 1-second jump and back off.
8. Change **Zoom** to `2.000`. Then **drag the image in the viewer**
   until the anchor point is centered — Resolve writes the Position
   values live. (Avoids manual coordinate math.)
9. Resolve auto-adds a keyframe whenever you change a keyframed
   value. Confirm: two ◆ marks now visible under Zoom and Position
   in the Inspector's mini-timeline.
10. **Move playhead forward ~1 s** (the hold).
11. Click **◆** on Zoom and Position again to set the "end-of-hold"
    keyframes (values unchanged — they hold).
12. **Step forward 9 frames.**
13. Change **Zoom** back to `1.000`, **Position** back to `0, 0` (use
    the small reset arrow next to each field).

Result: four keyframes per zoom beat — `start-wide`, `end-zoom-in`,
`end-hold`, `end-wide`.

## 8. Ease the keyframes

Linear interpolation reads robotic. Cubic ease-in-out reads cinematic.

1. **Right-click the clip** → **Show Curve Editor** (or click the
   curve icon at the bottom-right of the clip on the timeline).
2. In the curve panel that opens, pick **Zoom** from the parameter
   dropdown on the left.
3. Each keyframe shows as a **◆** on the curve. **Right-click each
   ◆ → Ease In and Out.**
4. The line between keyframes becomes a smooth S. Scrub the playhead
   over the zoom — visibly smoother in the viewer.
5. Repeat for the **Position** parameter (dropdown → Position).
6. Press **`Space`** with the playhead ~1 s before the zoom to
   preview. Watch three loops to confirm the ease feels natural.

## 9. Export to MP4

1. Bottom toolbar → **Deliver** page.
2. Left panel, **Render Settings**:
   - Preset: **Custom Export** (top-left preset row).
   - **Filename:** `demo`.
   - **Location:** `~/projects/<your-project>/media/`.
   - **Format:** MP4.
   - **Codec:** H.264.
   - **Resolution:** 1920 × 1080.
   - **Frame rate:** 30.
   - **Quality:** Restrict to **8000 Kb/s** (sharp; small file).
3. **Audio** tab → uncheck **Export Audio** (Cinnamon recorded none).
4. Click **Add to Render Queue** (bottom of the settings panel).
5. Right panel: queue appears. Click **Render All**.
6. Output: `media/demo.mp4` in ~15–60 s.

**If H.264 export fails on Linux** (rare in v19): export to QuickTime
+ DNxHR HQ, then convert:

```bash
ffmpeg -i media/demo.mov \
  -c:v libx264 -preset slow -crf 23 -pix_fmt yuv420p \
  -movflags +faststart -an media/demo.mp4
```

**Always re-mux for `faststart`** so the MP4 plays while downloading
on github.com (Resolve doesn't always set the flag):

```bash
ffmpeg -i media/demo.mp4 -c copy -movflags +faststart media/_demo.mp4
mv media/_demo.mp4 media/demo.mp4
```

## 10. Generate GIF + poster + AI frames

Re-use `scripts/make-demo-assets.sh` from
[vscode-screencast.md](vscode-screencast.md), pointed at the Resolve
export:

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
| Step one frame | `→` / `←` |
| Step one second | `Shift+→` / `Shift+←` |
| Mark in / mark out | `I` / `O` |
| Razor (blade) tool | `B` |
| Selection tool | `A` |
| Delete clip (ripple) | `Shift+Delete` |
| Delete clip (leave gap) | `Delete` |
| Zoom timeline in / out | `Ctrl+=` / `Ctrl+-` |
| Fit timeline to view | `Shift+Z` |
| Go to start / end | `Home` / `End` |
| Add keyframe on selected param | `Ctrl+[` |
| Switch page (Edit / Color / Deliver / …) | `Shift+1` through `Shift+8` |

## Appendix A — Linux Mint 22 / Ubuntu Noble install gotchas

Discovered the hard way 2026-05-19 on Mint 22 / kernel 6.17. Three
distinct snags chained between "downloaded the installer" and
"Resolve actually launches." Each fix is one command; the discovery
took an hour.

### A.1 — Installer's package check fails on `t64` rename

The installer is hard-coded to pre-`t64` library names (`libapr1`,
`libaprutil1`, `libasound2`, `libglib2.0-0`). Ubuntu Noble renamed
these as part of the 64-bit `time_t` transition. The `.so` files
themselves still exist and are ABI-compatible — only the **package
names** changed.

```bash
sudo apt install -y libapr1t64 libaprutil1t64
# (libasound2t64 and libglib2.0-0t64 are pre-installed on a stock Mint 22)
sudo SKIP_PACKAGE_CHECK=1 ./DaVinci_Resolve_*_Linux.run -i
```

`SKIP_PACKAGE_CHECK=1` bypasses the broken dpkg-name check. The
dynamic linker still finds the actual `.so` files at runtime.

### A.2 — Bundled GLib 2.68 conflicts with system pango

After install, first launch crashes with:

```
/opt/resolve/bin/resolve: symbol lookup error:
  /lib/x86_64-linux-gnu/libpango-1.0.so.0:
  undefined symbol: g_once_init_leave_pointer
```

`g_once_init_leave_pointer` is a GLib 2.80 symbol. Resolve bundles
GLib 2.68 (`/opt/resolve/libs/libglib-2.0.so.0.6800.4`). Noble ships
GLib 2.80, and the system `libpango` was built against 2.80. When
the dynamic linker loads Resolve's bundled (older) GLib first,
pango can't find the new symbol.

Fix: move Resolve's bundled GLib stack out of the way so the dynamic
linker falls through to the system GLib (which is API/ABI compatible
upward — every 2.68 symbol still exists in 2.80):

```bash
sudo mkdir -p /opt/resolve/libs/disabled
sudo mv /opt/resolve/libs/libglib-2.0.so*    /opt/resolve/libs/disabled/
sudo mv /opt/resolve/libs/libgio-2.0.so*     /opt/resolve/libs/disabled/
sudo mv /opt/resolve/libs/libgmodule-2.0.so* /opt/resolve/libs/disabled/
sudo mv /opt/resolve/libs/libgobject-2.0.so* /opt/resolve/libs/disabled/
```

Moving (vs deleting) keeps the change reversible:
`sudo mv /opt/resolve/libs/disabled/* /opt/resolve/libs/`.

### A.3 — AMD APU iGPUs (Phoenix / 780M / 760M) crash in OpenCL

After A.1 and A.2, Resolve launches and shows the EULA / setup
screens. Then it crashes inside its OpenCL backend:

```
Signal 11 (SIGSEGV) in libRusticlOpenCL.so.1
  called from libProResRAW.so (codec init)
```

**This is the dead-end on AMD iGPUs.** `clinfo` shows the GPU
fine — rusticl can enumerate the Radeon 780M (Phoenix gfx1103) —
but rusticl SEGVs on the first real compute workload. Same root
cause whether you reach for ROCm OpenCL or AMDGPU-PRO: Blackmagic
designed Resolve's compute kernels against CUDA and discrete-AMD
production stacks, and APU iGPU support across all three Linux
OpenCL implementations is not production-ready.

**No clean fix exists today.** Either:

- **Plug in a discrete GPU** (Nvidia for CUDA path, RX 7000-series
  AMD for ROCm).
- **Use [vscode-kdenlive.md](vscode-kdenlive.md) instead** — Kdenlive
  has no GPU compute dependency. For a 15-second clip with two zoom
  beats, the visual quality gap vs Resolve is essentially invisible.

---

**See also:**

- [vscode-screencast.md](vscode-screencast.md) — zero-install fast path
- [vscode-kdenlive.md](vscode-kdenlive.md) — Kdenlive workflow
  (no GPU compute requirement; recommended on iGPU machines)
- [screen-recording-how-to.md](screen-recording-how-to.md) — full
  reference (OBS, VirtualBox, ffmpeg cheatsheet, troubleshooting)
