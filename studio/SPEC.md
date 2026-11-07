# SPEC.md — SignalProof Lab × ENVIID Deterministic Engineering Reel

GOAL:    Convince an engineering hiring manager or technical viewer in 36 seconds that Ardhya Novri Ramadhan builds deterministic, mathematically verified hardware-to-web telemetry pipelines (STM32 4,000 Hz EMG Biquad Filter + ENVIID Digital MRV).
OUTPUT:  HyperFrames 0.8.206, 1080 x 1920 (9:16 vertical), 30 fps
TIME:    36.0 s x 30 fps = 1080 frames; 120 BPM (0.5 s = 15 frames per beat, 2.0 s = 60 frames per bar)
LOOK:    Medium: Industrial Oscilloscope & Drafting Vellum Ledger.
         Ground A (Oscilloscope Plate): #11151C flat phosphor-slate with 24 px structural ruled grid at 6% ink opacity.
         Ground B (Drafting Vellum Card): #F4F1EA warm technical vellum with 2 px solid #11151C structural border and 6 px hard offset shadow (rgba(0,0,0,0.35), 0 px blur).
         Ink Primary: #F4F1EA on dark plates, #11151C on vellum plates.
         Ink Muted: #94A3B8 on dark plates, #475569 on vellum plates.
         Accent 1 (Signal Orange): #FF4D1C — used only on the active anomaly/hero metric per shot.
         Accent 2 (Calibrated Trace Green): #10B981 — used only on verified filtered signal traces and pass badges.
         Display Face: 'Archivo Black', weight 400, 64–112 px, line-height 1.05, tracking -0.02em.
         Data / Technical Face: 'Space Mono' / 'JetBrains Mono', weight 700, 28–44 px, tabular-nums.
         Body / Label Face: 'Inter', weight 600, 28–34 px, line-height 1.25.
         Safe Zone (1080x1920): All readable text and hero graphics strictly inside x: [90, 990], y: [172, 1320]. Captions inside y: [1185, 1315].
OBJECTS: 1. Dual Oscilloscope Trace (raw 50 Hz corrupted waveform vs. clean Biquad-filtered EMG burst).
         2. STM32F411CEU6 DMA Block Chain (4 physical stage blocks connected by timed signal bus lines).
         3. 3D Isometric Biquad Frequency Surface (Three.js WebGL canvas showing 20-500 Hz passband and sharp 50 Hz Q=30 notch canyon).
         4. 4-Stage Horizontal Bar Chart (Relax 7.64 mV, Light 16.10 mV, Medium 38.52 mV, Strong 52.71 mV).
         5. Verification Stamp Ledger (12,043 rows, CRC-32 + SHA-256, SignalProof Lab + ENVIID Digital MRV).
MOTION:  Enter ease: expo.out / power4.out (0.35–0.45 s = 10–14 frames).
         Value count-up ease: cubic-bezier(0.22, 1, 0.36, 1) / power3.out over 1.2–1.5 s (36–45 frames), then dead still hold.
         Scene handoff: hard whip / shutter wipe on bar lines (t = 5.0 s, 12.0 s, 20.0 s, 29.0 s).
         Landed titles hold 100% still until scene exit.
SHOTS:
  Shot 1 (f 0–150, 0.0–5.0 s): Hook — Frame 0 shows raw 50 Hz corrupted EMG trace + "4,000 Hz" hero headline already on screen; at t=1.5 s shutter wipes to clean filtered trace ("-25.5 dB HUM KILLED").
  Shot 2 (f 150–360, 5.0–12.0 s): Pipeline — STM32F411CEU6 12-bit ADC + DMA architecture builds top-to-bottom; counter ticks 0 -> 8,000 valid calibration samples (2.00 s DC offset null) + 400-sample (100 ms) RMS/MAV window.
  Shot 3 (f 360–600, 12.0–20.0 s): 3D Biquad Surface — Deterministic Three.js WebGL canvas rotates and carves the 20 Hz HPF, 500 Hz LPF, and 50 Hz Q=30 Notch canyon; callout locks at "-25.5 dB @ 50 Hz".
  Shot 4 (f 600–870, 20.0–29.0 s): Data-Viz Chart — 4-bar grip RMS chart draws in reading order (axes -> Relax 7.64 mV -> Light 16.10 mV -> Medium 38.52 mV -> Strong 52.71 mV) + Pearson r = 0.9941 annotation; 0.5 s break at 28.5–29.0 s.
  Shot 5 (f 870–1080, 29.0–36.0 s): Payoff Ledger — Vellum verification sheet stamps "12,043 ROWS · 0 DROPS", linking STM32 SignalProof Lab & ENVIID Corn Cob Biochar Digital MRV, holding final frame cleanly.
BANNED:  Black void with floating small text; neon glow/bloom; purple/blue mesh gradients; glassmorphism cards; floating decorative particles; 3-card KPI grids; titles that drift after landing; text smaller than 28 px; text outside y: [168, 1330].
QA:      Check frames at t = 0.1 s, 2.5 s, 8.5 s, 16.0 s, 24.5 s, 32.5 s via `npx hyperframes check --json` and `npx hyperframes snapshot`.
