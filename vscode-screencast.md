# VSCode demo screencast — simplest possible (Linux Mint Cinnamon)

Fast-path recipe: one ~15-second take of VSCode in action becomes
three deliverables — a GIF for the VSCode Marketplace, an MP4 + poster
for a GitHub README, and a six-frame PNG sequence for handing to a
multimodal LLM.

Zero new installs beyond `ffmpeg` (Cinnamon already ships the
recorder), zero OBS configuration. Use this as the default and only
reach for OBS or VirtualBox workflows when you outgrow it — see
[screen-recording-how-to.md](screen-recording-how-to.md) for those.

## What you get from one ~15 s take

- **Master** — clean WebM straight from Cinnamon, kept as source of
  truth.
- **VSCode Marketplace asset** — ≤5 MB, 800 px-wide GIF. Marketplace
  strips `<video>` tags, so animated content has to be GIF, and its
  README column renders at ~800 px before scaling.
- **GitHub README asset** — MP4 (H.264, 1080 px, faststart) + poster
  PNG for `<video autoplay loop muted playsinline>`.
- **AI-consumption asset** — six evenly spaced PNG frames + a caption
  stub. Most multimodal LLMs ingest images, not video; six well-chosen
  frames plus 1–3 sentences of context outperforms a 20 MB MP4 they'd
  have to down-sample to ~6 frames anyway.

## Prerequisites

```bash
sudo apt install ffmpeg mpv     # mpv is for previewing trims
```

That's it. Cinnamon's screen recorder is built in. Verify:

```bash
ffmpeg -version | head -1       # ≥ 4.4
```

## Step 1 — Stage VSCode (30 seconds)

1. Top-right tray → **Do Not Disturb** on.
2. VSCode: `Ctrl+B` (hide sidebar), `Ctrl+J` (hide panel), `F11`
   (full-screen). Now the take shows only code.
3. Open the file the demo opens on. Cursor on line 1.
4. System Settings → Mouse → bump **Pointer size** to ~36 px.

Full-screen means no wallpaper / panel / theme tweaks needed — they're
all hidden.

## Step 2 — Record with Cinnamon's built-in recorder

Press **`Ctrl+Alt+Shift+R`** to start. Do the demo (aim 10–20 s).
Press **`Ctrl+Alt+Shift+R`** again to stop.

If the shortcut isn't bound on your Mint version: System Settings →
Keyboard → Shortcuts → System → **Toggle recording desktop**.

Output lands in `~/` as `cinnamon-dbus-recording-NNN.webm`. Rename:

```bash
mkdir -p media
mv ~/cinnamon-dbus-recording-*.webm media/demo-master.webm
```

Cinnamon records the whole screen at ~10 fps, no audio, VP8/WebM —
exactly what you want for a UI demo.

## Step 3 — Trim to length

Skim with `mpv media/demo-master.webm`, note the in/out timestamps,
then:

```bash
# Lossless if your trim points happen to land on keyframes
ffmpeg -ss 0:02 -to 0:18 -i media/demo-master.webm \
       -c copy media/demo-trimmed.webm

# Or re-encode (always works; tiny quality hit)
ffmpeg -ss 0:02 -to 0:18 -i media/demo-master.webm \
       -c:v libx264 -crf 20 -pix_fmt yuv420p media/demo-trimmed.mp4
```

## Step 4 — Three derivatives, one script

Save as `scripts/make-demo-assets.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
SRC="${1:-media/demo-trimmed.mp4}"     # accepts .webm or .mp4
OUT=media

# 1. GitHub README — MP4 + poster
ffmpeg -y -i "$SRC" \
  -vf "fps=30,scale=1080:-2:flags=lanczos" \
  -c:v libx264 -preset slow -crf 23 -pix_fmt yuv420p \
  -movflags +faststart -an "$OUT/demo.mp4"
ffmpeg -y -i "$OUT/demo.mp4" -ss 0:00:00.5 -frames:v 1 \
  "$OUT/demo-poster.png"

# 2. VSCode Marketplace — GIF (palette method, 800 px, 12 fps)
ffmpeg -y -i "$SRC" \
  -vf "fps=12,scale=800:-2:flags=lanczos,palettegen=stats_mode=diff" \
  /tmp/palette.png
ffmpeg -y -i "$SRC" -i /tmp/palette.png \
  -filter_complex "fps=12,scale=800:-2:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \
  "$OUT/demo.gif"
rm /tmp/palette.png

# 3. AI consumption — six evenly spaced PNG frames + caption stub
mkdir -p "$OUT/demo-frames"
DURATION=$(ffprobe -v error -show_entries format=duration \
                   -of csv=p=0 "$SRC")
FPS=$(awk "BEGIN { printf \"%.4f\", 6 / $DURATION }")
ffmpeg -y -i "$SRC" -vf "fps=$FPS,scale=960:-2:flags=lanczos" \
       "$OUT/demo-frames/frame_%02d.png"
cat > "$OUT/demo-frames/README.md" <<'EOF'
# Demo frames — for AI ingestion

Six evenly spaced frames from `media/demo.mp4`. Pair them with this
caption when handing to a multimodal model:

> *FILL ME IN: 1–3 sentences describing what the demo shows, in order.*
EOF

ls -lh "$OUT"/demo.* "$OUT/demo-frames"/
```

Run it:

```bash
chmod +x scripts/make-demo-assets.sh
scripts/make-demo-assets.sh
```

## Step 5 — Sanity check the three targets

- `media/demo.gif` — open in a browser tab. If > 5 MB, drop FPS to 10
  or width to 700. The marketplace accepts more, but inline rendering
  gets sluggish.
- `media/demo.mp4` — `mpv --loop=inf media/demo.mp4`; watch three
  loops.
- `media/demo-frames/frame_*.png` — `eog media/demo-frames/*.png` and
  arrow-key through. If two adjacent frames look identical, the
  recording has dead time — re-trim and re-run the script.

## Embedding both formats in one README

```html
<video src="media/demo.mp4" autoplay loop muted playsinline
       width="720" poster="media/demo-poster.png">
  <img src="media/demo.gif" alt="VSCode extension demo" width="720">
</video>
```

GitHub renders the `<video>`. The VSCode Marketplace strips it and
falls back to the inner `<img>`. AI assistants get pointed at
`media/demo-frames/` plus its `README.md`.

## What this scenario deliberately skips

| Skipped | Why it's fine here |
|---|---|
| OBS / SimpleScreenRecorder | Full-screen VSCode is a single source |
| Custom OBS encoder config | No OBS in the loop |
| Wallpaper / panel tweaks | `F11` hides them |
| Custom hotkeys | `Ctrl+Alt+Shift+R` is the Mint default |
| Audio mixing | Cinnamon's recorder captures none, by design |
| Captions / overlays | Code on screen is self-documenting |

## When to graduate to the full workflow

Reach for [screen-recording-how-to.md](screen-recording-how-to.md)
when you need any of:

- Multi-window compositing or scene transitions
- Branded overlays / lower-thirds / burned-in captions
- Audio narration
- Windows-app capture inside a VirtualBox guest
- Frame-perfect cursor placement / annotations
- A loop that needs an `xfade` crossfade for a clean seam

## Appendix: zooming for emphasis

The single highest-leverage polish technique for IDE screencasts —
what separates a Screen Studio clip from a raw OBS capture. Not part
of the fast path (Cinnamon's recorder can't do this live; needs
post-production), but worth adding the moment the demo's actionable
pixels are tiny — tooltips, autocomplete rows, gutter icons,
single-character edits, diagnostic squigglies.

### When to zoom

Zoom when the action happens in less than ~5% of the frame, or when
the visual change is subtle. Otherwise, don't. **One zoom per beat,
max one zoom every 4 seconds** — more than that is motion sickness.

| Situation | Zoom? |
|---|---|
| Hover-card / tooltip / autocomplete row | **Yes** |
| Status-bar item, gutter decoration, diagnostic squiggle | **Yes** |
| Right-click → context-menu item | **Yes** (on the menu) |
| Open a file / run command / open modal | **No** (big motion already) |
| Drag-drop, side-by-side diff | **No** (needs spatial context) |

### Anatomy of a good zoom

```
                  ┌──── HOLD 0.8–1.5 s ────┐
            ZOOM-IN                    ZOOM-OUT
   ─────────│                            │──────────
          300 ms        action @ +100 ms       300 ms
       ease-in-out         here              ease-in-out
```

| Parameter | Target |
|---|---|
| Zoom factor | 1.8× – 2.5× (never > 3×) |
| Zoom-in / zoom-out | 250–400 ms, ease-in-out (never linear) |
| Hold | 800–1500 ms |
| Lead time | Zoom starts 100–200 ms *before* the click |
| Anchor | Destination of the action, not the cursor's current position |
| Frame check | Cursor *and* result must stay inside the zoomed crop |

**Record at 2× output width.** Zooming 2× on a 1080 px master gives
540 px of effective resolution per crop — visibly soft. Master at
1440 p minimum so 2× zooms stay sharp.

### Tool choice on Linux Mint

| Effort | Tool | Notes |
|---|---|---|
| Low, manual | **DaVinci Resolve (free)** | Keyframed Transform with built-in ease curves; ~60 s per zoom; best results per minute spent |
| Medium, scripted | **ffmpeg crop + scale + concat** | Reproducible from a beats CSV; regenerates identically when you re-record |
| Medium, native | **Kdenlive** | Keyframed Transform effect; less polished easing than Resolve |
| High setup, low per-take | **OBS + Move plugin**, scene switch on hotkey | Live zoom-as-you-record; less precise than post |

DaVinci Resolve is the honest recommendation for one-off polish.
Drop to ffmpeg when you need reproducibility (CI-regenerated demos,
or re-recording after a UI change).

### ffmpeg recipe — beats CSV → zoomed MP4

`media/beats.csv`:

```
# t_start, t_end, zoom, cx, cy
0.0, 3.0, 1.0,  960,  540
3.0, 3.3, 2.0, 1240,  720    # ease-in segment (use zoompan for true easing)
3.3, 4.6, 2.0, 1240,  720    # hold
4.6, 4.9, 1.0, 1240,  720    # ease-out segment
4.9, 8.0, 1.0,  960,  540
```

`scripts/zoom-from-csv.sh`:

```bash
#!/usr/bin/env bash
# Render a zoomed edit from a beats CSV.
# Usage: zoom-from-csv.sh master.mp4 beats.csv out.mp4
set -euo pipefail
SRC=$1; BEATS=$2; OUT=$3
W=1080 H=608           # output dimensions
TMP=$(mktemp -d)

i=0
while IFS=, read -r t0 t1 zoom cx cy; do
  [[ "$t0" =~ ^# ]] && continue
  i=$((i+1))
  seg="$TMP/seg_$(printf %03d $i).mp4"
  cw=$(awk "BEGIN { print int($W / $zoom) }")
  ch=$(awk "BEGIN { print int($H / $zoom) }")
  x=$(awk  "BEGIN { print int($cx - $cw/2) }")
  y=$(awk  "BEGIN { print int($cy - $ch/2) }")
  ffmpeg -y -ss "$t0" -to "$t1" -i "$SRC" \
    -vf "crop=$cw:$ch:$x:$y,scale=$W:$H:flags=lanczos" \
    -c:v libx264 -preset slow -crf 20 -pix_fmt yuv420p -an "$seg"
done < "$BEATS"

printf "file '%s'\n" "$TMP"/seg_*.mp4 > "$TMP/list.txt"
ffmpeg -y -f concat -safe 0 -i "$TMP/list.txt" -c copy "$OUT"
rm -rf "$TMP"
```

Hard cuts between zoom levels (what the script above produces) work
fine at 30 fps for short transitions. For true eased zoom transitions,
replace the ease-in / ease-out *segments* with a `zoompan` call using
the smoothstep curve `pow(t, 2) * (3 - 2t)` — ease-in-out without
trigonometry:

```bash
# Ease-in: zoom 1.0 → 2.0 over 300 ms (9 frames @ 30 fps), smoothstep
ffmpeg -ss 3.0 -to 3.3 -i master.mp4 \
  -vf "zoompan=
    z='1.0 + 1.0 * pow(on/9, 2) * (3 - 2*on/9)':
    x='iw/2 + (1240 - iw/2) * (zoom - 1)/zoom':
    y='ih/2 + ( 720 - ih/2) * (zoom - 1)/zoom':
    d=9:s=1080x608:fps=30" \
  -c:v libx264 -crf 18 trans-in.mp4
```

Use eased transitions only when the difference reads on a 720 px GIF.
For most README hero clips, hard cuts are indistinguishable.

### Common zoom mistakes

| Mistake | Why it fails |
|---|---|
| Zooming on every click | Motion sickness; if everything matters, nothing does |
| Zoom *after* the click | Viewer already missed it |
| Linear ease | Reads robotic / amateur |
| Zoom > 3× on a 1080 p master | Visibly pixelated |
| Hold < 600 ms | Unreadable; reads as flinch |
| Anchor on cursor, not destination | Cursor leaves frame mid-action |
| Different zoom levels each beat | Inconsistent — pick one factor per video |
| Zoom + caption + arrow + cursor halo simultaneously | Visual cacophony; pick one |

### TL;DR

**One zoom per beat. 2× factor. 300 ms ease-in. ~1 s hold. 300 ms
ease-out. Anchor on the destination, not the cursor. Lead the action
by 100–200 ms.**

Anything more elaborate is a distinct creative decision; anything
less and you might as well not zoom.
