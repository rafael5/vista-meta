# Screencast tools — pipeline & selection criteria

A high-level map of the screencast production pipeline, the tools
that play each stage, what specifically makes each tool fit that
stage, and which tool the worked recipes in this repo settled on.

**For step-by-step recipes** that walk through specific tool
combinations end-to-end:

- [screencasting-simple.md](screencasting-simple.md) — Cinnamon + ffmpeg only (no zoom)
- [screencasting-kdenlive.md](screencasting-kdenlive.md) — adds Kdenlive for zoom (any GPU)
- [screencasting-davinci.md](screencasting-davinci.md) — adds DaVinci Resolve for zoom (discrete GPU required)
- [screen-recording-how-to.md](screen-recording-how-to.md) — full reference (OBS, VirtualBox, audio)

## The pipeline

```
PLAN ── STAGE ── CAPTURE ── TRIM ── POST ── ENCODE ── DERIVE ── EMBED
   1      2         3        4      5        6         7         8
                    │                 │                │
                    │                 │                └─ MP4, GIF, poster, PNG frames
                    │                 └─ zoom, captions, color
                    └─ pixels → video file
```

Eight stages. **Capture (3) and Post (5)** are where most of the
tool-choice happens; the rest have one obvious default. The recipes
diverge only at Stage 5.

## Stage 1 — Plan

**Produces:** 3–6 numbered beats on paper. Each beat = "cause →
visible effect."

**Tools that fit:** pen + paper, or a plain-text file.

**Selection criteria:** anything that keeps you off the recorder
while planning. The single biggest production-value lever is
"rehearse twice before pressing record" — tools beyond pen+paper add
overhead without yield at 15-second clip scale. Skip storyboarding
software, project-management apps, "outliner" apps.

## Stage 2 — Stage VSCode and the desktop

**Produces:** a host system and target app posed to look
unremarkable — the viewer sees code and nothing else.

| Layer | Tool | What it specifically buys you |
|---|---|---|
| Notifications | Cinnamon tray DnD (click tray bell) | Single click suppresses every notification source. No app-by-app config. |
| VSCode chrome | `Ctrl+B`, `Ctrl+J`, `F11` | Hides sidebar, panel, then everything. Three keys, no settings churn. |
| VSCode profile | `Profiles → Create → "Demo"` | Isolates demo font size, theme, settings.json. Survives across machines via export. |
| Cursor caret | `editor.cursorBlinking: "solid"` | A blinking caret adds entropy that wrecks GIF palettes. Solid → clean palette. |
| OS cursor | System Settings → Mouse → 36 px pointer | Default 24 px is invisible in a downscaled 1000 px GIF. |

**Selection criteria:** zero-install wherever possible. The Demo
profile is the one exception — it pays dividends across multiple
takes and is the only place worth a one-time investment.

## Stage 3 — Capture

**Produces:** a video file of screen pixels. The master that every
derivative comes from.

| Tool | Sweet spot | Why use it |
|---|---|---|
| **Cinnamon recorder** (`Ctrl+Alt+Shift+R`) | Single-window full-screen captures on Linux Mint | Built in. Zero install. No scenes/settings/profiles. VP8 WebM, ~10 fps, no audio — exactly what an IDE demo wants. |
| OBS Studio | Multi-source scenes, hotkey scene switching, audio mixing | The only tool that gives you live scene composition. Reach for it when you need a webcam overlay, a logo, or a second source. |
| SimpleScreenRecorder | Region capture, MP4 H.264, fewer knobs than OBS | Between Cinnamon and OBS in capability *and* configuration overhead. Rarely the right answer once you've tried the other two. |
| `ffmpeg -f x11grab` | Scriptable / Makefile-able | A `make demo-raw` target that captures a region for N seconds without clicking. Great for reproducible CI demos. |
| asciinema | Terminal-only sessions | Records as a typed log, not pixels. Tiny files; copyable; replayable on a webpage. Wrong tool for GUI demos. |
| VHS (Charm) | Reproducible terminal demos from a script file | Like asciinema but you write a `.tape` script and it executes commands and types text on a fake terminal. Replaces "perform live" with "write the demo as code." Output: GIF or WebM. |
| Screen Studio | macOS GUI demos with auto-zoom on clicks | Best output quality, smallest learning curve. Not on Linux. |
| Peek / ScreenToGif | "Record straight to GIF" | **Don't.** Lossy from frame one; no way back to a sharp MP4. |

**Selection criteria for this repo:** Cinnamon recorder is the
default because the IDE demo needs exactly one thing — "capture
pixels of one window cleanly" — and Cinnamon does that with zero
setup. OBS only when narration or compositing enters scope; ffmpeg
only when a Makefile target is wanted; VHS only for terminal demos.

## Stage 4 — Trim

**Produces:** a clip with the dead head/tail seconds removed.

| Tool | Use when |
|---|---|
| `ffmpeg -ss/-to -c copy` | You know the in/out timestamps; lossless re-mux in 1 second |
| `ffmpeg -ss/-to + libx264` | Trim points fall between keyframes (visible black/frozen first frame after `-c copy`) — re-encode the first GOP |
| Kdenlive razor + edge-drag | You want to see the frame you're cutting on |
| DaVinci I/O markers (`I` / `O`) | Same, with snappier UI |

**Selection criteria:** if you can guess timestamps from a mental
playback, ffmpeg wins (one command, lossless, sub-second). If you
can't, you're already inside the editor for Stage 5 anyway — trim
there.

## Stage 5 — Post: zoom, captions, color

The fork. This stage is where the three recipes diverge.

| Tool | Strengths | Weaknesses |
|---|---|---|
| **None (skip post)** | Zero work | Tiny UI elements unreadable at GIF scale |
| ffmpeg `zoompan` | Scripted, reproducible, no GUI | Hard to author from scratch; eased zooms need smoothstep math |
| ffmpeg crop + scale + concat | Simpler than `zoompan`; hard cuts between zoom levels look fine at 30 fps | No eased transitions out of the box |
| **Kdenlive Transform** | Cubic-ease keyframes; runs on any GPU; native Mint repos | Less polished ease curves than Resolve; manual right-click per keyframe |
| **DaVinci Transform + Curve Editor** | Studio-grade ease curves; gold standard | **Requires discrete Nvidia or AMD GPU**; AMD APU iGPU = SEGV in OpenCL backend |
| OBS Move plugin (live) | Zoom during recording via hotkey | Hard to get pixel-perfect anchors; not iteration-friendly |
| Screen Studio (macOS) | Auto-zoom on clicks with post-process feel | macOS only |

**Selection criteria — the deciding factors in order:**

1. **No zoom needed at all** → skip post entirely (simple recipe).
2. **One zoom beat, scripted, reproducible** → ffmpeg crop+scale+concat.
3. **No discrete GPU on Linux** → Kdenlive (only Linux editor that doesn't need GPU compute).
4. **Discrete Nvidia / AMD GPU on Linux** → DaVinci Resolve free.
5. **macOS** → Screen Studio (above all others; auto-zoom on clicks is unique to it).

The hardware tier is the *binding constraint*, not the tool's
quality. On a 15 s clip with two zoom beats the visible gap between
Kdenlive and DaVinci is something only the editor can see, not the
viewer.

For captions: ffmpeg `drawtext` (burned in, universal) for one-shot
markers; Kdenlive/DaVinci titles for anything multi-line. Skip
auto-transcription tools (whisper.cpp / WebVTT) — IDE demos rarely
have audio.

For color: skip. A 15 s IDE clip doesn't justify a grade. The one
exception is "the dark-mode UI is too dark in GIF" — fix with
`-vf eq=brightness=0.05`.

## Stage 6 — Encode

**Produces:** the final master MP4. Everything else derives from it.

| Tool | Output | When to pick |
|---|---|---|
| Editor's built-in render (Kdenlive / DaVinci) | The "Render"/"Deliver" path of whatever editor did Stage 5 | When you're already inside the editor. Saves an extra round-trip — but you'll likely re-mux for `+faststart` regardless. |
| `ffmpeg -c:v libx264 -crf 23 -movflags +faststart` | MP4 H.264 | The canonical Linux encode. Always re-mux with `+faststart` even if you used an editor — Resolve and Kdenlive don't set the flag. |
| `ffmpeg -c:v libvpx-vp9` | WebM VP9 | Smaller files; useful if hosting prefers WebM. Rarely worth the encode time for a 15 s clip. |

**Selection criteria:** ffmpeg is the lingua franca. Editor renders
are convenience; ffmpeg is the reliable common path that everything
downstream understands.

## Stage 7 — Derive

**Produces:** the per-destination assets, all from the encoded
master.

| Asset | Tool | Why |
|---|---|---|
| MP4 1080 p H.264 faststart | ffmpeg libx264 | GitHub `<video>` inline rendering |
| GIF 800 px 12 fps palettized | ffmpeg palettegen + paletteuse | VSCode Marketplace + npm/PyPI registries that strip `<video>` |
| (alt) GIF via `gifski` | gifski | ~15 % smaller at equivalent quality; usually overkill |
| Poster PNG | `ffmpeg -ss 0.5 -frames:v 1` | First frame shown before `<video autoplay>` kicks in |
| 6 evenly spaced PNG frames | `ffmpeg -vf fps=6/dur` | Multimodal LLM ingestion — image input, not video |

**Selection criteria:** ffmpeg for everything. The
`scripts/make-demo-assets.sh` script wraps all four into one
invocation. gifski only matters when the GIF is competing for the
last 200 KB of a marketplace size budget.

## Stage 8 — Embed

**Produces:** the snippet of HTML/Markdown that goes in the README.

| Destination | Snippet | Why |
|---|---|---|
| GitHub README | `<video autoplay loop muted playsinline poster="…">` | Inline auto-loop on the rendered page |
| VSCode Marketplace | `<img src="demo.gif">` | Marketplace strips `<video>`; needs a static image tag |
| npm / PyPI | `<img>` GIF | Same as Marketplace |
| Cross-platform single snippet | `<video><img>…</video>` fallback | GitHub renders the outer video; registries fall back to the inner img |

**Selection criteria:** the fallback pattern — `<video>` with an
inner `<img>` — wins because one source of truth in the README works
everywhere. AI assistants get pointed at `media/demo-frames/`
separately; they're a different audience.

## How the tools chain in the worked recipes

```
                          ┌─ ffmpeg one-liner (no zoom)   ┐
PLAN/STAGE → Cinnamon ──→ ├─ ffmpeg crop+scale+concat     ├─→ ffmpeg derive → README embed
                          ├─ Kdenlive Transform           │
                          └─ DaVinci Transform            ┘
```

| Recipe | Capture | Post | Total time |
|---|---|---|---|
| [screencasting-simple.md](screencasting-simple.md) | Cinnamon | none | ~10 min |
| [screencasting-kdenlive.md](screencasting-kdenlive.md) | Cinnamon | Kdenlive | ~25 min |
| [screencasting-davinci.md](screencasting-davinci.md) | Cinnamon | DaVinci | ~30 min |

Capture, encode, derive, and embed are **identical across all
three**. The post-process editor (or its absence) is the only
differentiator.

## Tools intentionally not in this pipeline

| Tool | Why not |
|---|---|
| Adobe Premiere / Final Cut | Commercial, platform-locked. DaVinci free is on par for IDE demos. |
| ScreenFlow | macOS only. |
| Camtasia | Commercial; SmartFocus is its only differentiating feature and it's macOS/Windows. |
| Lightworks, Olive, Shotcut | Capable, but Kdenlive's keyframed Transform is the lightest path on Linux. |
| Adobe After Effects | Overkill for a 15 s clip with two zooms. |
| Filmora, OpenShot | Underpowered or unstable on Linux. |
| ScreenToGif, Peek | Capture-direct-to-GIF — disqualified earlier (no master to re-derive from). |
| Loom, Vimeo Record | Cloud-only; data lives on someone else's server. |
| Wayland portal recorders (wf-recorder, kooha) | Mint's Cinnamon is X11; portal recorders are for Wayland sessions. |

The omissions aren't dismissals — they're "the pipeline above
already covers this case."
