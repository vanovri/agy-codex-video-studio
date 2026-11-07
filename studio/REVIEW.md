# REVIEW.md — SignalProof Lab × ENVIID Deterministic Engineering Reel (`36.0s`, `1080×1920`, `30 fps`)

## 1. Creative Direction & Storylines Considered
- **Selected Storyline ("Bare-Metal Proof to Digital MRV")**: Opens on the raw 50 Hz mains hum corrupting surface EMG (`SEN0240`), wipes via a mechanical oscilloscope shutter at `t = 1.1s` to the clean `STM32F411CEU6` filtered trace (`-25.5 dB` suppression), walks through the `8,000`-sample DC calibration and `400`-sample DMA pipeline, rotates a deterministic 3D isometric frequency-response surface (`20–500 Hz` passband + `50 Hz Q=30` notch canyon), builds the 4-stage grip RMS progression chart (`7.64` → `16.10` → `38.52` → `52.71 mV`, `r = 0.9941`), pauses for a `0.5s` rhythmic break (`28.5–29.0s`), and lands on the vellum verification ledger (`12,043 / 12,043` rows, `0` drops) bridging **SignalProof Lab** and **ENVIID Carbon Solutions**.
- **Storylines Not Built**:
  1. *Pure Web UI Screencast*: Rejected because landscape web dashboards compressed into 9:16 lose legibility at 360 px phone width.
  2. *Abstract Particle / Cyberpunk HUD*: Rejected per `SPEC.md` BANNED rules (no dark void with glowing neon orbs or decorative HUD brackets).

## 2. What Was Measured vs. Inspected
- **Measured (`npx hyperframes check --json` + `ffprobe` + `pytest`)**:
  - **Lint, Runtime, Layout, Contrast**: `0` errors across all 7 files (`index.html` + 6 sub-compositions); `62/62` WCAG AA contrast checks passed (`100%`) after darkening `.s3-eyebrow` from `#FF4D1C` (`2.94:1`) to `#C22E00` (`>4.5:1`).
  - **Safe Area Compliance**: Every readable line (`>= 28 px`) sits strictly inside `x: [90, 990]`, `y: [176, 1315]`.
  - **Audio / Soundtrack**: Synthesized deterministically at `48,000 Hz` stereo (`120 BPM`, Peak `-5.80 dBFS`, RMS `-14.73 dBFS`). Sound was measured via waveform/loudness telemetry (`soundtrack_synth.py` & `npx hyperframes audio`), not heard through physical speakers.
- **Visually Inspected (`npx hyperframes snapshot` PNGs & Contact Sheets)**:
  - Inspected `frame-00` (`0.5s`), `frame-01` (`2.5s`), `frame-02` (`7.5s`), `frame-03` (`15.5s`), `frame-04` (`24.5s`), `frame-05` (`32.5s`), and `frame-06` (`34.92s`).

## 3. Issues Caught & Fixed During Review
- `t=15.5s · scene3.html (.s3-overlay-badges) · Badge text wrapped to 2 lines and touched top of 3D surface → shortened badge copy to single line and shifted isometric projection sy from 365 to 398 · 3D notch canyon stays centered`
- `t=18.0s · scene3.html (.s3-eyebrow) · Contrast 2.94:1 below 3.0:1 AA threshold → changed color from #FF4D1C to #C22E00 · vellum card background stays #F4F1EA`
- `t=24.5s · scene4.html (.s4-callout-row) · Correlation label wrapped onto 2 lines → set font-size 29-30px with nowrap · orange callout bar stays full width`
- `t=32.5s · captions.html (#cg-09 / #cg-10) · 0.1s gap left frame 32.5s without caption pill and Scene 5 had lower blank space → extended #cg-09 to 32.58s and added 3rd domain card (AGY × CODEX VIDEO STUDIO) · ledger header stays unchanged`

## 4. Deliberate Holds
- `scene3` (`16.25–19.75s`) and `scene4` (`24.63–28.38s`) carry `data-hold="true"` so the viewer has a full 3.5s static reading window once the 3D notch surface and 4-bar empirical chart finish building.
