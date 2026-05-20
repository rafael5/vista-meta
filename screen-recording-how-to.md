# Screen-Recording Workflow for GitHub READMEs (Linux Mint)

A practical, end-to-end recipe for producing a short, looping demo
clip of a GUI — either a native Linux window or a Windows app running
inside VirtualBox — suitable for embedding at the top of a GitHub
README.

Audience: you, Rafael, on Linux Mint (Cinnamon, X11). Goal: ~10–30
second clip that loops cleanly, lives in the repo, and renders inline
on github.com (and, where required, on package registries that don't
support video).

> **Just want a VSCode extension demo?** See
> [vscode-screencast.md](vscode-screencast.md) for the zero-install
> fast path (Cinnamon's built-in recorder → MP4 + GIF + AI-friendly
> PNG frames). This document is the full reference for everything
> else: OBS, VirtualBox Windows guests, multi-source compositing,
> audio.

## TL;DR

1. **Record to MP4**, not directly to GIF. Always.
2. **Native window** → OBS Studio (window capture).
3. **VirtualBox Windows guest** → either OBS captures the VBox host
   window, or `VBoxManage` records the guest framebuffer directly.
4. **Trim lossless** with `ffmpeg -c copy`.
5. **Convert** with the ffmpeg palette method or `gifski`.
6. **Commit** the MP4 (and optionally a GIF fallback) into `media/`.
7. **Embed** with `<video src="media/demo.mp4" autoplay loop muted playsinline>`
   for github.com, or `![](media/demo.gif)` where you need broad
   registry compatibility.

## Choose your output format first

The right format depends on where the README will render.

| Where the README is shown | Best format | Why |
|---|---|---|
| github.com only | MP4 (H.264) via `<video>` tag | 5–10× smaller than GIF, sharper text, controls |
| GitHub + VSCode Marketplace | GIF | Marketplace strips `<video>` tags |
| GitHub + npm / PyPI | GIF | Registries don't render `<video>` |
| Long-form (>1 min) | YouTube / Vimeo unlisted | Don't bloat the repo |

If in doubt: produce **both** an MP4 and a GIF from the same source
take. The MP4 goes inline on github.com; the GIF is the fallback for
registries that strip HTML.

## One-time setup

```bash
# Recorders
sudo apt install obs-studio simplescreenrecorder

# CLI essentials
sudo apt install ffmpeg gifski imagemagick

# Optional: text-only terminal recording
sudo apt install asciinema
# For VHS (Charm): go install github.com/charmbracelet/vhs@latest
```

Verify versions:

```bash
ffmpeg -version | head -1     # ≥ 4.4 is fine; ≥ 6 is current
gifski --version              # ≥ 1.10
obs --version
```

### One-time OBS configuration

1. **Settings → Output → Output Mode → Advanced**.
2. **Recording → Type:** Standard.
3. **Recording Path:** `~/Videos/screen-recordings/`.
4. **Recording Format:** `mkv` (safer than mp4 — survives a crash;
   remux to mp4 in post).
5. **Encoder:** `x264` with **CRF 18, preset veryfast**. (CRF 18 is
   visually lossless; if file size matters, push to 23.)
6. **Settings → Video → Base + Output Resolution:** both set to your
   actual monitor resolution. **FPS: 30.** (Down-sample to 15 in
   post if you want; recording at 30 gives flexibility.)
7. **Settings → Audio → mute all sources by default.** Unmute
   intentionally for a specific take.

### One-time Linux Mint tweaks

These reduce visual noise in recordings.

- **Disable notifications** while recording: `notify-send` is fine,
  but Slack/Telegram/email popups ruin demos. Use Cinnamon's
  **Do Not Disturb** toggle (top-right system tray).
- **Hide the panel/taskbar** if you're recording full-screen: temp
  enable Cinnamon's *intellihide* mode.
- **Set a neutral wallpaper** (solid dark grey or your project's
  brand color) — desktop icons and busy wallpapers compress badly
  and distract.
- **Increase cursor size** (System Settings → Mouse → Pointer size).
  The default 24 px cursor is invisible in a downscaled 1200 px GIF.
  Bump to 32–40 px while recording.

## Recording workflow A: native Linux GUI window

### Step 1 — Prepare the app

- Close every panel/tab you won't use in the demo.
- Zoom one notch up so text reads at 720 px width
  (`Ctrl+=` in most apps; in VSCode `Ctrl+0` first, then `Ctrl+=`).
- Pre-load any state you'll need (open the right file, run the right
  command, log in, etc.). The clip should start in the demo's
  "act one" state, not in setup.
- **Hide your cursor blink** in code editors — many editors have
  "smooth-caret-animation" or "cursor-blinking" settings. Turn them
  off; a blinking cursor adds entropy that wrecks GIF palettes.

### Step 2 — Rehearse the take

Write the demo as 3–6 numbered beats on paper:

```
1. Open file APUTL.m
2. Click first caller in sidebar → land in caller
3. Click XINDEX finding → cursor lands on offending line
4. Hover ^DPT global → hover card appears
5. Return to APUTL.m via tab
```

Rehearse twice without recording. Time yourself. Goal: 12–20 seconds.

### Step 3 — Record (OBS, recommended)

1. OBS → **Sources → +** → **Window Capture (Xcomposite)**.
2. Pick the window (e.g. `code` for VSCode).
3. Right-click the source → **Transform → Fit to screen**.
4. **Start Recording** (hotkey: bind to something memorable like
   `Ctrl+Alt+R`).
5. Do your rehearsed sequence.
6. **Stop Recording**.
7. Output lands at `~/Videos/screen-recordings/<timestamp>.mkv`.

#### Alternative: SimpleScreenRecorder

Lighter-weight than OBS, faster to launch:

```bash
simplescreenrecorder
```

Pick **Record a fixed rectangle** or **Record the entire screen**.
Output to MP4 with H.264. Works fine, fewer knobs.

#### Alternative: ffmpeg (scriptable)

```bash
# Find your window geometry
xwininfo
# Click the target window. Read off the "Absolute upper-left" and
# "Width" / "Height" lines.

# Record region: 30 fps, 30 sec max
ffmpeg -f x11grab -framerate 30 -video_size 1400x900 \
       -i :0.0+100,100 \
       -c:v libx264 -preset ultrafast -crf 18 -pix_fmt yuv420p \
       -t 30 ~/Videos/screen-recordings/raw.mp4
```

Use this when you want a Makefile target instead of clicking GUI
buttons.

## Recording workflow B: Windows GUI inside VirtualBox

Two strategies, each with tradeoffs.

| Strategy | Captures | Pros | Cons |
|---|---|---|---|
| **A. Host-side (OBS records VBox window)** | The VBox window as the host sees it, including host cursor | Host cursor visible; can mix with host annotations; consistent with native-app workflow | Slightly blurrier because you're recording a recording-of-a-rendering; cursor inside VM may be invisible if VM cursor integration is off |
| **B. Guest-side (`VBoxManage` records guest framebuffer)** | Direct pixel-perfect capture of the VM's display | Sharper text; smaller files; no host overlay | No host cursor; can't show host-side context; output is WebM, needs conversion |

For most README demos of a Windows app, **Strategy A** is the right
call — host-side OBS, capturing the VBox window. Use Strategy B only
when you need pixel-perfect VM-only footage.

### VirtualBox prep checklist (one-time per VM)

1. **Install Guest Additions** (clipboard, dynamic resolution,
   smoother cursor). `Devices → Insert Guest Additions CD image`.
2. **Set a fixed, clean display resolution** in the guest, *before*
   recording. Windows: Settings → System → Display → 1280×720 or
   1280×800. Avoid weird aspect ratios; they make conversion
   awkward.
3. **Pick the right graphics controller.** `vboxsvga` (the default)
   silently ignores `CustomVideoMode1` and some forced-resolution
   tricks. For predictable recording resolutions, switch the VM to
   **VMSVGA** in Settings → Display → Graphics Controller. (Switch
   only when the VM is powered off.)
4. **Disable the Windows screen-saver and notifications**
   (Focus Assist → On).
5. **Bump cursor size** in the guest (Settings → Ease of Access →
   Mouse pointer). Same reason as on the host.
6. **Hide the taskbar** if you don't need it (auto-hide on).

### Strategy A — host-side OBS recording of the VBox window

Same as native workflow:

1. OBS → **Window Capture** → pick `VirtualBox Machine` (the actual
   process window, not the manager).
2. Make the VBox window borderless and roughly centered. Avoid the
   F1-help bar / status bar at the bottom — crop it out in OBS
   (right-click source → Filters → Crop/Pad).
3. Click into the VM (capture cursor with `Host+I` if cursor
   integration is off).
4. Record as you would a native window.

### Strategy B — VBoxManage built-in recording

VirtualBox has native recording. Output is WebM (VP8/VP9). Two ways
to control it.

**GUI:** With the VM running, **View → Recording → Start Recording**.
The default settings come from `Settings → Display → Recording` tab.

**CLI:**

```bash
# Configure (with VM powered off)
VBoxManage modifyvm "Win10-CPRS" \
    --recording on \
    --recording-screens 0 \
    --recording-video-fps 15 \
    --recording-video-res 1280x720 \
    --recording-video-rate 2048 \
    --recording-file "/home/rafael/Videos/screen-recordings/vm-demo.webm"

# Start the VM
VBoxManage startvm "Win10-CPRS"

# Start/stop recording on a running VM
VBoxManage controlvm "Win10-CPRS" recording on
VBoxManage controlvm "Win10-CPRS" recording off
```

Convert WebM → MP4 (lossless container remux when possible):

```bash
ffmpeg -i vm-demo.webm -c:v libx264 -preset slow -crf 18 \
       -pix_fmt yuv420p -an vm-demo.mp4
```

## Post-processing

### Step 1 — Lossless trim

Pick the in/out points to the second:

```bash
# Keep from 00:00:02 to 00:00:18 (16 sec final length)
ffmpeg -ss 00:00:02 -to 00:00:18 -i raw.mkv -c copy trimmed.mp4
```

`-c copy` re-muxes without re-encoding — instant, lossless, byte-
exact within keyframe boundaries. If your trim points are between
keyframes (you'll see a brief frozen frame at the start), re-encode:

```bash
ffmpeg -ss 00:00:02 -to 00:00:18 -i raw.mkv \
       -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p \
       trimmed.mp4
```

### Step 2 — Downscale and re-encode for final MP4

```bash
ffmpeg -i trimmed.mp4 \
       -vf "fps=30,scale=1200:-2:flags=lanczos" \
       -c:v libx264 -preset slow -crf 23 -pix_fmt yuv420p \
       -movflags +faststart \
       media/demo.mp4
```

- `scale=1200:-2` → width 1200, height auto, force even number.
- `fps=30` is fine for an MP4. For GIF, drop to 15.
- `-movflags +faststart` puts the MP4 header at the front so the
  video starts playing while still downloading on github.com.
- `-crf 23` is the sweet spot. Lower = bigger and sharper.

### Step 3 — Build a GIF (palette method, broadly compatible)

```bash
# Pass 1: build an optimized palette
ffmpeg -i media/demo.mp4 \
       -vf "fps=15,scale=1000:-1:flags=lanczos,palettegen=stats_mode=diff" \
       -y media/.palette.png

# Pass 2: apply it
ffmpeg -i media/demo.mp4 -i media/.palette.png \
       -filter_complex "fps=15,scale=1000:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \
       -y media/demo.gif

rm media/.palette.png
```

`stats_mode=diff` and `diff_mode=rectangle` together give the
sharpest GIFs for screen recordings (where most pixels are static
between frames).

### Step 3 (alternative) — Build a GIF with `gifski`

If you have room in your dev environment and want the absolute
highest quality:

```bash
mkdir -p .frames
ffmpeg -i media/demo.mp4 -vf "fps=15,scale=1000:-1:flags=lanczos" \
       .frames/f%04d.png
gifski -o media/demo.gif --fps 15 --width 1000 --quality 90 \
       .frames/*.png
rm -rf .frames
```

`gifski` typically beats ffmpeg's palette method for screen
recordings by another ~15–25% smaller at equivalent visual quality.

### Step 4 — Loop sanity check

Open the result in `mpv --loop=inf media/demo.mp4` (or just preview
the GIF in any browser tab). Watch three full loops. If the cut
from end → beginning feels jarring, either re-record so start/end
states match visually, or extend the final frame:

```bash
# Hold the last frame for 1 extra second
ffmpeg -i media/demo.mp4 -vf "tpad=stop_mode=clone:stop_duration=1" \
       media/demo-padded.mp4
```

## Embedding in a GitHub README

### For GitHub-only rendering (best quality, smallest files)

```html
<video src="media/demo.mp4"
       autoplay loop muted playsinline
       width="720"
       poster="media/demo-poster.png">
  <!-- Fallback for old renderers -->
  Your browser doesn't support inline video.
  <a href="media/demo.mp4">Watch the demo</a>.
</video>
```

- `muted` is **required** for browser autoplay to work.
- `playsinline` keeps it embedded on mobile (no fullscreen takeover).
- `poster` is the still image shown before playback starts. Generate
  with `ffmpeg -i media/demo.mp4 -ss 00:00:00.5 -frames:v 1 media/demo-poster.png`.

### For cross-platform rendering (npm, PyPI, VSCode Marketplace)

Use a plain GIF reference. Registries strip HTML, so the `<video>`
tag becomes a broken link there.

```markdown
![Demo](media/demo.gif)
```

### Best-of-both-worlds pattern

Many of my READMEs use the `<picture>`-style fallback approach,
substituting `<video>` with `<img>` fallback:

```html
<video src="media/demo.mp4" autoplay loop muted playsinline
       width="720" poster="media/demo-poster.png">
  <img src="media/demo.gif" alt="Demo" width="720">
</video>
```

GitHub renders the `<video>`. Registries that strip the `<video>`
tag often still render the inner `<img>`. Not a perfect spec
compliance trick, but works in practice on npm and many static
README renderers.

## Things to DO

- **Plan and rehearse before recording.** 60 seconds of planning
  saves 30 minutes of re-takes.
- **Record at 2× the resolution you'll publish at.** Downsampling
  with `lanczos` produces sharper text than recording at final size.
- **Always record to MKV / MP4 first.** Treat that file as your
  master; generate all distributables from it.
- **Use one consistent demo profile** in the app being demoed
  (custom VSCode profile, fresh user, fixed font size). Reproducible
  recordings.
- **Bump the cursor size** on host (and in VM) before recording.
- **Burn captions when steps aren't visually obvious.** A 5-pt overlay
  reading "1. open file" beats a 50-word README paragraph. Use
  Kdenlive or `ffmpeg drawtext` filter.
- **Design for loop.** Either match start/end frames, or hold the
  last frame briefly so the loop "breathes."
- **Commit the master MP4 to the repo** (in `media/` or `docs/`) so
  the recording is reproducible-from-source. Future-you regenerates
  the GIF from the master, not from the GIF.
- **Generate a poster frame** (`-frames:v 1`) so the video has a
  meaningful still before autoplay kicks in.
- **Verify on github.com** before declaring done. Push to a branch
  and view the rendered README on github.com — that's the only
  rendering that matters.

## Things NOT to do

- **Don't record directly to GIF.** Recording-to-GIF tools (Peek,
  ScreenToGif on Windows) lock you into a lossy intermediate. You
  can't go back and re-derive a sharper MP4 from a finished GIF.
- **Don't record full-screen if you only need one window.** Wastes
  pixels, makes cropping a chore.
- **Don't use 60 fps for UI demos.** It bloats files for no visual
  gain. 15 fps is plenty for clicks; 30 fps for smoother cursor
  motion.
- **Don't include the system clock, notifications, or window
  decorations with your username in path bars.** Crop them out. Or
  use a fresh "demo user" account.
- **Don't include audio you don't intend to publish.** Mute mic in
  OBS by default; opt in per take.
- **Don't commit > 5 MB MP4s without Git LFS.** Use LFS or host
  externally.
- **Don't autoplay long videos.** Anything > 30 seconds → use
  `controls` instead of `autoplay loop`, and assume viewer drop-off.
- **Don't trust GIF rendering on local preview.** Local renderers
  (Files, image viewers) may show GIFs at native resolution, but
  github.com applies its own scaling. Always verify on github.com.
- **Don't use the GitHub drag-drop CDN as your only copy.** The
  `user-attachments` URLs are persistent but opaque (a UUID).
  Always also commit the source MP4 to the repo so you can
  regenerate if the CDN ever changes.
- **Don't record terminal-only demos as video.** Use `asciinema` or
  `vhs` instead — smaller, replayable, copyable.

## Efficiency tweaks

### Per-project `Makefile` target

Drop this into the repo's Makefile so anyone (including future you)
can regenerate the README artifacts from the master MP4 in one
command:

```makefile
DEMO_SRC   := media/demo-master.mp4
DEMO_MP4   := media/demo.mp4
DEMO_GIF   := media/demo.gif
DEMO_POSTER := media/demo-poster.png

.PHONY: demo
demo: $(DEMO_MP4) $(DEMO_GIF) $(DEMO_POSTER)

$(DEMO_MP4): $(DEMO_SRC)
	ffmpeg -y -i $< \
	  -vf "fps=30,scale=1200:-2:flags=lanczos" \
	  -c:v libx264 -preset slow -crf 23 -pix_fmt yuv420p \
	  -movflags +faststart $@

$(DEMO_GIF): $(DEMO_MP4)
	ffmpeg -y -i $< \
	  -vf "fps=15,scale=1000:-1:flags=lanczos,palettegen=stats_mode=diff" \
	  /tmp/.palette.png
	ffmpeg -y -i $< -i /tmp/.palette.png \
	  -filter_complex "fps=15,scale=1000:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \
	  $@
	rm /tmp/.palette.png

$(DEMO_POSTER): $(DEMO_MP4)
	ffmpeg -y -i $< -ss 00:00:00.5 -frames:v 1 $@
```

Now `make demo` regenerates everything from the master.

### Wrapper script in `~/scripts/bin/`

Cross-project utility:

```bash
#!/usr/bin/env bash
# ~/scripts/bin/screencast — convert a master MP4 to MP4 + GIF + poster
# Usage: screencast input.mp4 [output-prefix]
set -euo pipefail
src="$1"
prefix="${2:-demo}"
ffmpeg -y -i "$src" -vf "fps=30,scale=1200:-2:flags=lanczos" \
       -c:v libx264 -preset slow -crf 23 -pix_fmt yuv420p \
       -movflags +faststart "${prefix}.mp4"
ffmpeg -y -i "${prefix}.mp4" \
       -vf "fps=15,scale=1000:-1:flags=lanczos,palettegen=stats_mode=diff" \
       /tmp/palette.png
ffmpeg -y -i "${prefix}.mp4" -i /tmp/palette.png \
       -filter_complex "fps=15,scale=1000:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \
       "${prefix}.gif"
ffmpeg -y -i "${prefix}.mp4" -ss 00:00:00.5 -frames:v 1 "${prefix}-poster.png"
rm /tmp/palette.png
ls -lh "${prefix}".*
```

`chmod +x ~/scripts/bin/screencast`, then anywhere:
`screencast raw.mkv media/demo`.

### OBS hotkeys

Bind start/stop recording to a single hotkey (e.g. `Ctrl+Alt+R`)
under **Settings → Hotkeys → Start/Stop Recording**. Saves you
having to alt-tab back to OBS mid-demo.

### Speed up a recording you can't re-take

```bash
# 1.5× speed
ffmpeg -i slow.mp4 -filter:v "setpts=PTS/1.5" -an speed.mp4
```

Useful for trimming dead time without re-recording.

## Troubleshooting

### Recording is too dark / too bright

OBS picks up the X11 screen-color profile, not what you see. Open
the file in `mpv` or VLC; if it still looks off, set
`Settings → Advanced → Color Format` to `NV12` and recapture.

### Dropped frames in OBS

Switch the encoder to `x264` (software) instead of any hardware
encoder (NVENC / VAAPI) — hardware encoders on Intel iGPUs
sometimes choke on rapid window-content changes. Lower the preset
from `slow` to `veryfast`.

### Mouse cursor invisible in VirtualBox capture

In the VM, install Guest Additions and enable
**Input → Mouse Integration**. If still invisible in the recording,
switch to **Strategy A** (host-side capture of the VBox window) —
the host always sees its own cursor.

### File is too big

In order of effectiveness:
1. Lower output width: `scale=900:-1` instead of `1200:-1`.
2. Drop FPS: `fps=12` instead of 15.
3. Trim length more aggressively.
4. For MP4: bump `-crf` from 23 to 28.
5. For GIF: use `gifski --quality 80` instead of 90.

### Loop has a visible jump

- Re-record so the final frame's content matches the opening
  frame's content (e.g. both end on the file you started in).
- Or add a `tpad` pause at the end (see "Loop sanity check" above).
- Or use a crossfade transition with `xfade` filter for a smooth
  loop (more work, looks great).

### VM display is blurry

The VirtualBox `vboxsvga` graphics controller often resists fixed
resolutions and forces fractional scaling. Switch to `VMSVGA` in
**VM Settings → Display → Graphics Controller** (VM must be off).
Set the guest to an exact 1280×720 or 1920×1080 resolution after.

## ffmpeg cheat sheet

```bash
# Inspect a file
ffprobe -v error -show_format -show_streams demo.mp4

# Lossless trim
ffmpeg -ss 0:02 -to 0:18 -i in.mp4 -c copy out.mp4

# Re-encode with re-keyframing (when trim points are off keyframes)
ffmpeg -ss 0:02 -to 0:18 -i in.mp4 -c:v libx264 -crf 18 out.mp4

# Resize, lanczos (sharp)
ffmpeg -i in.mp4 -vf "scale=1200:-2:flags=lanczos" -c:v libx264 -crf 23 out.mp4

# Strip audio
ffmpeg -i in.mp4 -c copy -an out.mp4

# Speed up 2×
ffmpeg -i in.mp4 -filter:v "setpts=0.5*PTS" -an out.mp4

# Pad last frame for 1 sec
ffmpeg -i in.mp4 -vf "tpad=stop_mode=clone:stop_duration=1" out.mp4

# Extract single frame for poster
ffmpeg -i in.mp4 -ss 0:00:00.5 -frames:v 1 poster.png

# Concatenate two clips (same codec)
printf "file 'a.mp4'\nfile 'b.mp4'\n" > /tmp/list.txt
ffmpeg -f concat -safe 0 -i /tmp/list.txt -c copy joined.mp4

# Burn caption at top-left
ffmpeg -i in.mp4 -vf "drawtext=text='Step 1':x=20:y=20:fontsize=28:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=8" out.mp4
```

## File layout convention

For consistency across all my repos with demo media:

```
repo/
├── media/
│   ├── demo-master.mkv         # original OBS recording (or .mp4)
│   ├── demo.mp4                # generated, ready for <video>
│   ├── demo.gif                # generated, fallback
│   ├── demo-poster.png         # generated, for <video poster=...>
│   └── icon.png                # extension/app icon if applicable
├── Makefile                    # has `make demo` target
└── README.md                   # references media/ via relative paths
```

`media/demo-master.mkv` is the only file that requires fresh OBS
work. Everything else regenerates from `make demo`.

## When to skip all of this

- **Terminal-only demos** → `asciinema` or `vhs`. Smaller, copyable,
  scalable.
- **Static UI showcase** → just take a PNG screenshot. `Shift+Cmd+4`
  equivalent (Cinnamon: `Print Screen → Take a screenshot of a
  rectangular area`).
- **Long explanatory walkthroughs (>1 min)** → record to YouTube
  unlisted, embed thumbnail with link.
- **Interactive / clickable demo** → consider a Storybook/Vite
  preview link instead of a recording.
