# LuminAria 前端重新设计 — 维多利亚古典风格 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign LuminAria frontend with Victorian classical styling and add duration slider, collapsible prompt, delete-all-history, and retro record-player audio UI.

**Architecture:** Backend (FastAPI) gets one new endpoint + one new DB function. Frontend (vanilla HTML/CSS/JS) gets a complete visual overhaul with Google Fonts (ZCOOL QingKe HuangYou + Noto Serif SC), custom-styled range input, vinyl-record audio player, and scroll-unroll collapsible panel.

**Tech Stack:** FastAPI, SQLite, vanilla JS, CSS3 with transitions/animations, Google Fonts

---

### Task 1: Backend — config.py duration range update

**Files:**
- Modify: `app/config.py:21-23`

- [ ] **Step 1: Update duration constants**

Change `app/config.py` lines 21-23 to add the step and min values:

```python
MAX_DURATION_SECONDS = 120
MIN_DURATION_SECONDS = 15
DURATION_STEP = 5
DURATION_OPTIONS = [30, 60, 90, 120]
```

- [ ] **Step 2: Verify no breakage**

Run: `python -c "from app.config import MIN_DURATION_SECONDS, DURATION_STEP; print(MIN_DURATION_SECONDS, DURATION_STEP)"`
Expected: `15 5`

- [ ] **Step 3: Commit**

```bash
git add app/config.py
git commit -m "feat: add MIN_DURATION_SECONDS=15 and DURATION_STEP=5 for slider"
```

---

### Task 2: Backend — database.py delete_all_generations()

**Files:**
- Modify: `app/database.py:70-77`

- [ ] **Step 1: Add delete_all_generations function**

Add after the existing `delete_generation()` function:

```python
def delete_all_generations() -> list[str]:
    """Delete ALL generation records. Returns list of deleted filenames."""
    conn = _get_connection()
    rows = conn.execute("SELECT filename FROM generations").fetchall()
    filenames = [r["filename"] for r in rows]
    conn.execute("DELETE FROM generations")
    conn.commit()
    conn.close()
    return filenames
```

- [ ] **Step 2: Commit**

```bash
git add app/database.py
git commit -m "feat: add delete_all_generations() for bulk delete"
```

---

### Task 3: Backend — main.py DELETE /api/history endpoint

**Files:**
- Modify: `app/main.py:175-189`

- [ ] **Step 1: Add bulk delete endpoint**

Add right after the existing `delete_history_item` function (after line 189):

```python
@app.delete("/api/history")
async def delete_all_history():
    """Delete ALL generations and their audio files."""
    from app.database import delete_all_generations
    filenames = delete_all_generations()
    for fname in filenames:
        audio_path = Path(OUTPUT_DIR) / fname
        if audio_path.exists():
            audio_path.unlink()
    return {"detail": f"Deleted {len(filenames)} records"}
```

- [ ] **Step 2: Commit**

```bash
git add app/main.py
git commit -m "feat: add DELETE /api/history bulk endpoint"
```

---

### Task 4: Frontend — style.css complete Victorian redesign

**Files:**
- Rewrite: `static/style.css`

This is a complete rewrite. The new CSS file:

- Imports Google Fonts via `@import` (ZCOOL QingKe HuangYou + Noto Serif SC)
- Victorian color system: background `#0d0c0a`, cards `#1a1816`, gold `#c9a84c`, trim `#2a2520`
- Custom range slider styling (`input[type=range]`) with gold track and radial-gradient thumb
- `.dur-btn` — quick duration buttons with Noto Serif SC, gold border for active
- `.collapsible-prompt` — title bar with ⚜️ decorations, max-height transition animation
- `.record-player` — vinyl record card with double gold border, play/pause gold circle button
- `.history-panel` — centered title, centered action buttons, delete-all button at bottom
- `.victorian-modal` — overlay with backdrop blur, centered dialog with decorative ✧
- `.btn-generate` — gold gradient with hover glow lift
- All transitions matching spec: 0.15s slider, 0.3s collapsible, 0.2s modal
- Status/progress bar: gold gradient fill, red on error

- [ ] **Step 1: Write the new style.css**

Full content:

```css
/* LuminAria — Victorian Classical theme */
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600&family=ZCOOL+QingKe+HuangYou&display=swap');

:root {
  --bg-primary: #0d0c0a;
  --bg-secondary: #1a1816;
  --bg-input: #12100e;
  --text-primary: #e8e6e3;
  --text-secondary: #9a9080;
  --text-muted: #5a5548;
  --gold: #c9a84c;
  --gold-dim: #8b7433;
  --gold-bright: #e0c876;
  --gold-glow: rgba(201, 168, 76, 0.15);
  --border: #2a2520;
  --border-light: #3a3025;
  --danger: #8b4a4a;
  --danger-border: #3a2020;
  --radius: 6px;
  --transition: 0.2s ease;
  --font-display: 'ZCOOL QingKe HuangYou', cursive;
  --font-body: 'Noto Serif SC', serif;
  --font-mono: monospace;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: var(--font-body);
  background: var(--bg-primary);
  color: var(--text-primary);
  min-height: 100vh;
  line-height: 1.6;
}

.app-container {
  max-width: 720px;
  margin: 0 auto;
  padding: 0 20px;
}

/* ===== Top Bar ===== */
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 0;
  border-bottom: 1px solid var(--border);
  margin-bottom: 32px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: var(--font-display);
  font-size: 1.5rem;
  background: linear-gradient(135deg, var(--gold) 0%, var(--gold-bright) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.logo-icon {
  font-size: 1.8rem;
  color: var(--gold);
  -webkit-text-fill-color: var(--gold);
}

.btn-ghost {
  background: none;
  border: 1px solid var(--border);
  color: var(--text-secondary);
  padding: 6px 18px;
  border-radius: var(--radius);
  cursor: pointer;
  font-family: var(--font-body);
  font-size: 0.85rem;
  letter-spacing: 1px;
  transition: var(--transition);
}
.btn-ghost:hover {
  border-color: var(--gold);
  color: var(--gold);
}

/* ===== Input Section ===== */
.input-section {
  background: var(--bg-secondary);
  border-radius: var(--radius);
  padding: 24px;
  border: 1px solid var(--border);
}

.input-label {
  display: block;
  font-family: var(--font-body);
  font-size: 0.85rem;
  color: var(--gold-dim);
  letter-spacing: 2px;
  margin-bottom: 10px;
}

.prompt-input {
  width: 100%;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text-primary);
  padding: 14px 16px;
  font-size: 0.95rem;
  font-family: var(--font-body);
  resize: vertical;
  transition: var(--transition);
}
.prompt-input:focus {
  outline: none;
  border-color: var(--gold);
  box-shadow: 0 0 0 3px var(--gold-glow);
}
.prompt-input::placeholder {
  color: var(--text-muted);
  opacity: 0.6;
}

/* ===== Duration ===== */
.duration-group {
  margin-top: 20px;
}

.duration-row {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 14px;
}

.duration-label {
  font-family: var(--font-body);
  font-size: 0.85rem;
  color: var(--gold-dim);
  letter-spacing: 2px;
  min-width: 50px;
}

/* Custom range slider */
input[type=range] {
  -webkit-appearance: none;
  appearance: none;
  flex: 1;
  height: 4px;
  background: var(--border);
  border-radius: 2px;
  outline: none;
  cursor: pointer;
}
input[type=range]::-webkit-slider-track {
  height: 4px;
  background: var(--border);
  border-radius: 2px;
}
input[type=range]::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 35%, var(--gold-bright), var(--gold-dim));
  border: 2px solid #5a4a20;
  box-shadow: 0 0 8px var(--gold-glow);
  cursor: pointer;
  margin-top: -7px;
}
input[type=range]::-moz-range-track {
  height: 4px;
  background: var(--border);
  border-radius: 2px;
  border: none;
}
input[type=range]::-moz-range-thumb {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 35%, var(--gold-bright), var(--gold-dim));
  border: 2px solid #5a4a20;
  box-shadow: 0 0 8px var(--gold-glow);
  cursor: pointer;
}

.duration-value {
  font-family: var(--font-body);
  font-size: 1rem;
  color: var(--gold);
  min-width: 50px;
  text-align: right;
}

.duration-ticks {
  display: flex;
  justify-content: space-between;
  padding: 0 2px;
  margin-bottom: 14px;
}
.duration-ticks span {
  font-size: 0.65rem;
  color: var(--text-muted);
}

.duration-options {
  display: flex;
  gap: 8px;
}

.dur-btn {
  flex: 1;
  background: none;
  border: 1px solid var(--border);
  color: var(--text-muted);
  padding: 8px 0;
  border-radius: var(--radius);
  cursor: pointer;
  font-family: var(--font-body);
  font-size: 0.8rem;
  transition: var(--transition);
  text-align: center;
}
.dur-btn:hover {
  border-color: var(--gold-dim);
  color: var(--text-primary);
}
.dur-btn.active {
  border-color: var(--gold);
  color: var(--gold);
  background: rgba(201, 168, 76, 0.06);
}

/* ===== Generate Button ===== */
.btn-generate {
  width: 100%;
  margin-top: 20px;
  padding: 12px;
  background: linear-gradient(135deg, var(--gold-dim), var(--gold), #b8943a);
  color: #12100e;
  border: none;
  border-radius: var(--radius);
  font-family: var(--font-body);
  font-size: 1rem;
  font-weight: 600;
  letter-spacing: 3px;
  cursor: pointer;
  transition: var(--transition);
  box-shadow: 0 2px 16px rgba(201, 168, 76, 0.15);
}
.btn-generate:hover {
  box-shadow: 0 4px 24px var(--gold-glow);
  transform: translateY(-1px);
}
.btn-generate:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

/* ===== Status Section ===== */
.status-section {
  margin-top: 20px;
  background: var(--bg-secondary);
  border-radius: var(--radius);
  padding: 20px 24px;
  border: 1px solid var(--border);
}
.status-message {
  color: var(--gold);
  font-family: var(--font-body);
  font-size: 0.9rem;
  margin-bottom: 10px;
}
.progress-bar {
  width: 100%;
  height: 4px;
  background: var(--bg-input);
  border-radius: 2px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--gold-dim), var(--gold-bright));
  border-radius: 2px;
  width: 0%;
  transition: width 0.3s ease;
}

/* ===== Result Section ===== */
.result-section {
  margin-top: 20px;
  background: var(--bg-secondary);
  border-radius: var(--radius);
  border: 1px solid var(--border);
  overflow: hidden;
}

/* Collapsible prompt */
.collapsible-prompt {
  border-bottom: 1px solid var(--border);
}

.prompt-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  background: var(--bg-secondary);
  cursor: pointer;
  user-select: none;
  transition: background var(--transition);
}
.prompt-header:hover {
  background: #1f1d1a;
}

.prompt-header .ornament {
  color: #5a4a20;
  font-size: 1rem;
}

.prompt-header .title {
  font-family: var(--font-body);
  font-size: 0.85rem;
  color: var(--gold-dim);
  letter-spacing: 3px;
}

.prompt-header .arrow {
  color: var(--gold);
  font-size: 1.1rem;
  transition: transform 0.3s ease;
  display: inline-block;
}
.prompt-header .arrow.collapsed {
  transform: rotate(0deg);
}
.prompt-header .arrow.expanded {
  transform: rotate(-90deg);
}

.prompt-body {
  max-height: 0;
  opacity: 0;
  overflow: hidden;
  transition: max-height 0.3s ease, opacity 0.3s ease, padding 0.3s ease;
  padding: 0 20px;
  background: var(--bg-input);
  border-left: 2px solid var(--border-light);
  border-right: 2px solid var(--border-light);
}
.prompt-body.expanded {
  max-height: 600px;
  opacity: 1;
  padding: 16px 20px;
}

.enhanced-prompt-text {
  font-size: 0.82rem;
  color: var(--text-secondary);
  line-height: 1.8;
  font-family: var(--font-body);
  text-align: left;
}

/* Record player */
.record-player {
  padding: 20px;
}

.player-card {
  background: var(--bg-secondary);
  border: 2px solid var(--border-light);
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 4px 24px rgba(0,0,0,0.4);
}

.player-top {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
}

.vinyl-disc {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: radial-gradient(circle, #2a2520 30%, #1a1a1a 70%, var(--border-light) 100%);
  border: 2px solid #5a4a20;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.vinyl-label {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--gold), var(--gold-dim));
}

.player-meta {
  flex: 1;
  text-align: left;
}
.player-meta .now-playing {
  font-family: var(--font-body);
  font-size: 0.85rem;
  color: var(--gold);
}
.player-meta .meta-sub {
  font-family: var(--font-body);
  font-size: 0.75rem;
  color: var(--text-muted);
}

/* Custom audio player controls */
audio {
  display: none;  /* hide native, use custom controls */
}

.custom-controls {
  margin-top: 16px;
}

.progress-container {
  margin-bottom: 6px;
}

.progress-track {
  height: 4px;
  background: var(--border);
  border-radius: 2px;
  position: relative;
  cursor: pointer;
}
.progress-track .progress-current {
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  background: linear-gradient(90deg, var(--gold-dim), var(--gold));
  border-radius: 2px;
  width: 0%;
}
.progress-track .progress-thumb {
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 35%, var(--gold-bright), var(--gold-dim));
  border: 2px solid #5a4a20;
  box-shadow: 0 0 6px var(--gold-glow);
  display: none;
}
.progress-track:hover .progress-thumb {
  display: block;
}

.time-display {
  display: flex;
  justify-content: space-between;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: var(--text-muted);
  margin-bottom: 16px;
}

.controls-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 20px;
}

.ctrl-btn {
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 1rem;
  cursor: pointer;
  transition: var(--transition);
  padding: 4px;
}
.ctrl-btn:hover {
  color: var(--gold);
}

.play-btn {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--gold-dim), var(--gold));
  border: none;
  color: #12100e;
  font-size: 1.2rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 12px rgba(201, 168, 76, 0.3);
  transition: var(--transition);
}
.play-btn:hover {
  box-shadow: 0 4px 20px rgba(201, 168, 76, 0.5);
  transform: scale(1.05);
}

.volume-group {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: 20px;
}
.volume-icon {
  font-size: 0.85rem;
  color: var(--text-muted);
}
.volume-slider {
  width: 60px;
  height: 3px;
  background: var(--border);
  border-radius: 2px;
  position: relative;
  cursor: pointer;
}
.volume-slider .volume-fill {
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  background: var(--text-muted);
  border-radius: 2px;
  width: 70%;
}
.volume-slider input[type=range] {
  width: 100%;
  height: 3px;
  background: transparent;
  position: absolute;
  top: -6px;
  left: 0;
  margin: 0;
  opacity: 0;
  cursor: pointer;
}

.player-actions {
  margin-top: 16px;
  text-align: right;
}

.btn-download {
  display: inline-block;
  background: none;
  border: 1px solid var(--border-light);
  color: var(--gold-dim);
  padding: 6px 16px;
  border-radius: var(--radius);
  text-decoration: none;
  font-family: var(--font-body);
  font-size: 0.8rem;
  cursor: pointer;
  transition: var(--transition);
}
.btn-download:hover {
  border-color: var(--gold);
  color: var(--gold);
  background: var(--gold-glow);
}

/* ===== History Overlay ===== */
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  z-index: 100;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding-top: 60px;
}

.history-panel {
  background: var(--bg-secondary);
  border-radius: var(--radius);
  width: 90%;
  max-width: 600px;
  max-height: 70vh;
  overflow-y: auto;
  border: 1px solid var(--border);
}

.history-header {
  text-align: center;
  padding: 16px 24px;
  border-bottom: 2px solid var(--border);
  position: relative;
}
.history-header h2 {
  font-family: var(--font-display);
  font-size: 1.2rem;
  color: var(--gold);
  letter-spacing: 3px;
}
.history-header .history-close {
  position: absolute;
  right: 18px;
  top: 14px;
  background: none;
  border: 1px solid var(--border);
  color: var(--text-muted);
  padding: 4px 14px;
  border-radius: var(--radius);
  cursor: pointer;
  font-family: var(--font-body);
  font-size: 0.8rem;
  transition: var(--transition);
}
.history-header .history-close:hover {
  border-color: var(--gold);
  color: var(--gold);
}

.history-list {
  padding: 8px 24px 16px;
}

.history-item {
  padding: 16px 0;
  text-align: center;
  border-bottom: 1px solid rgba(255,255,255,0.04);
}
.history-item:last-child { border-bottom: none; }

.hi-date {
  font-size: 0.75rem;
  color: var(--text-muted);
}
.hi-prompt {
  font-family: var(--font-body);
  font-size: 0.9rem;
  margin: 4px 0 8px;
}
.hi-actions {
  display: flex;
  gap: 10px;
  justify-content: center;
}
.hi-actions button,
.hi-actions a {
  background: none;
  border: 1px solid var(--border);
  color: var(--text-muted);
  padding: 3px 14px;
  border-radius: 3px;
  cursor: pointer;
  font-family: var(--font-body);
  font-size: 0.75rem;
  text-decoration: none;
  transition: var(--transition);
}
.hi-actions button:hover,
.hi-actions a:hover {
  border-color: var(--gold-dim);
  color: var(--gold);
}
.hi-actions button.btn-delete:hover,
.hi-actions a.btn-delete:hover {
  border-color: var(--danger);
  color: var(--danger);
}

/* Delete all button */
.delete-all-section {
  padding: 12px 24px 20px;
  border-top: 1px solid var(--border);
}
.btn-delete-all {
  width: 100%;
  padding: 10px;
  background: none;
  border: 1px solid var(--danger-border);
  color: var(--danger);
  border-radius: var(--radius);
  cursor: pointer;
  font-family: var(--font-body);
  font-size: 0.85rem;
  letter-spacing: 1px;
  transition: var(--transition);
}
.btn-delete-all:hover {
  background: rgba(139, 74, 74, 0.08);
  border-color: var(--danger);
}

/* ===== Victorian Modal ===== */
.victorian-modal {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  z-index: 200;
  justify-content: center;
  align-items: center;
  animation: modalFadeIn 0.2s ease;
}
.victorian-modal.active {
  display: flex;
}

.modal-content {
  background: var(--bg-secondary);
  border: 1px solid var(--border-light);
  border-radius: 8px;
  max-width: 380px;
  width: 90%;
  padding: 28px 24px;
  text-align: center;
  box-shadow: 0 8px 32px rgba(0,0,0,0.5);
  animation: modalScaleIn 0.2s ease;
}

.modal-ornament {
  color: #5a4a20;
  font-size: 1.5rem;
  margin-bottom: 8px;
}

.modal-content h3 {
  font-family: var(--font-body);
  color: var(--gold);
  font-size: 1.1rem;
  margin-bottom: 8px;
  letter-spacing: 2px;
  font-weight: 600;
}

.modal-content p {
  font-family: var(--font-body);
  color: var(--text-secondary);
  font-size: 0.85rem;
  margin-bottom: 20px;
  line-height: 1.6;
}

.modal-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.modal-btn {
  padding: 8px 24px;
  border-radius: var(--radius);
  font-family: var(--font-body);
  font-size: 0.85rem;
  cursor: pointer;
  transition: var(--transition);
  border: none;
}

.modal-btn-cancel {
  background: none;
  border: 1px solid var(--border-light);
  color: var(--text-secondary);
}
.modal-btn-cancel:hover {
  border-color: var(--gold);
  color: var(--gold);
}

.modal-btn-danger {
  background: linear-gradient(135deg, #5a2a2a, #3a1a1a);
  border: 1px solid var(--danger);
  color: #d47a7a;
}
.modal-btn-danger:hover {
  background: linear-gradient(135deg, #6a3a3a, #4a2a2a);
}

@keyframes modalFadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes modalScaleIn {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}

/* ===== Utilities ===== */
.hidden { display: none !match; }

/* ===== Responsive ===== */
@media (max-width: 480px) {
  .app-container { padding: 0 12px; }
  .input-section { padding: 18px; }
  .controls-row { flex-wrap: wrap; }
  .volume-group { margin-left: 0; }
  .duration-options { flex-wrap: wrap; }
}
```

- [ ] **Step 2: Commit**

```bash
git add static/style.css
git commit -m "feat: Victorian classical theme CSS with custom slider, player, modal"
```

---

### Task 5: Frontend — index.html DOM restructuring

**Files:**
- Rewrite: `static/index.html`

- [ ] **Step 1: Write the new index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LuminAria — AI 音乐生成</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <div class="app-container">
        <!-- Top bar -->
        <header class="topbar">
            <div class="logo">
                <span class="logo-icon">♬</span>
                <span>LuminAria</span>
            </div>
            <button id="historyToggleBtn" class="btn-ghost">历史记录</button>
        </header>

        <!-- Main content -->
        <main class="main-content">
            <!-- Input section -->
            <section class="input-section">
                <label for="promptInput" class="input-label">描述你想要的音乐...</label>
                <textarea id="promptInput" class="prompt-input" rows="3"
                    placeholder="例如：轻柔的钢琴曲，像下雨天的咖啡馆"></textarea>

                <div class="duration-group">
                    <div class="duration-row">
                        <span class="duration-label">时 长</span>
                        <input type="range" id="durationSlider" min="15" max="120" step="5" value="90">
                        <span id="durationValue" class="duration-value">90秒</span>
                    </div>
                    <div class="duration-ticks">
                        <span>15秒</span>
                        <span>30秒</span>
                        <span>60秒</span>
                        <span>90秒</span>
                        <span>120秒</span>
                    </div>
                    <div class="duration-options" id="durationOptions">
                        <button class="dur-btn" data-duration="30">30秒</button>
                        <button class="dur-btn" data-duration="60">60秒</button>
                        <button class="dur-btn active" data-duration="90">90秒</button>
                        <button class="dur-btn" data-duration="120">120秒</button>
                    </div>
                </div>

                <button id="generateBtn" class="btn-generate">生成音乐</button>
            </section>

            <!-- Status area -->
            <section id="statusSection" class="status-section hidden">
                <div id="statusMessage" class="status-message"></div>
                <div class="progress-bar"><div id="progressFill" class="progress-fill"></div></div>
            </section>

            <!-- Result section -->
            <section id="resultSection" class="result-section hidden">
                <!-- Collapsible prompt -->
                <div class="collapsible-prompt">
                    <div id="promptHeader" class="prompt-header">
                        <span class="ornament">⚜️</span>
                        <span class="title">优化后提示词</span>
                        <span id="promptArrow" class="arrow collapsed">❮</span>
                    </div>
                    <div id="promptBody" class="prompt-body">
                        <div id="enhancedPrompt" class="enhanced-prompt-text"></div>
                    </div>
                </div>

                <!-- Record player -->
                <div class="record-player">
                    <div class="player-card">
                        <div class="player-top">
                            <div class="vinyl-disc">
                                <div class="vinyl-label"></div>
                            </div>
                            <div class="player-meta">
                                <div class="now-playing">正在播放</div>
                                <div class="meta-sub" id="playerMeta">选择音乐开始</div>
                            </div>
                        </div>

                        <audio id="audioPlayer" preload="auto"></audio>

                        <div class="custom-controls">
                            <div class="progress-container">
                                <div class="progress-track" id="progressTrack">
                                    <div class="progress-current" id="progressCurrent" style="width:0%"></div>
                                    <div class="progress-thumb" id="progressThumb" style="left:0%"></div>
                                </div>
                            </div>
                            <div class="time-display">
                                <span id="currentTime">00:00</span>
                                <span id="totalTime">00:00</span>
                            </div>
                            <div class="controls-row">
                                <button id="prevBtn" class="ctrl-btn" title="上一首">⏮</button>
                                <button id="playBtn" class="play-btn">▶</button>
                                <button id="nextBtn" class="ctrl-btn" title="下一首">⏭</button>
                                <div class="volume-group">
                                    <span class="volume-icon">♬</span>
                                    <div class="volume-slider">
                                        <div class="volume-fill" id="volumeFill" style="width:70%"></div>
                                        <input type="range" id="volumeRange" min="0" max="100" value="70">
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div class="player-actions">
                            <a id="downloadLink" class="btn-download" download>下载</a>
                        </div>
                    </div>
                </div>
            </section>
        </main>
    </div>

    <!-- History overlay -->
    <div id="historyOverlay" class="overlay hidden">
        <div class="history-panel">
            <div class="history-header">
                <h2>生成历史</h2>
                <button id="historyCloseBtn" class="history-close">关闭</button>
            </div>
            <div id="historyList" class="history-list"></div>
            <div class="delete-all-section">
                <button id="deleteAllBtn" class="btn-delete-all">🗑 删除全部记录</button>
            </div>
        </div>
    </div>

    <!-- Victorian modal for delete confirmation -->
    <div id="confirmModal" class="victorian-modal">
        <div class="modal-content">
            <div class="modal-ornament">✧</div>
            <h3>确认删除</h3>
            <p>确定要删除全部生成记录吗？<br>此操作不可撤销。</p>
            <div class="modal-actions">
                <button id="modalCancelBtn" class="modal-btn modal-btn-cancel">取消</button>
                <button id="modalConfirmBtn" class="modal-btn modal-btn-danger">确认删除</button>
            </div>
        </div>
    </div>

    <script src="/static/script.js"></script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add static/index.html
git commit -m "feat: Victorian DOM with slider, collapsible prompt, record player, modal"
```

---

### Task 6: Frontend — script.js all interactivity

**Files:**
- Rewrite: `static/script.js`

- [ ] **Step 1: Write the new script.js**

```javascript
// LuminAria — Victorian classical client-side logic

const state = {
    duration: 90,
    generating: false,
    audioFilename: null,
    promptExpanded: false,
};

// --- DOM refs ---
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const promptInput = $('#promptInput');
const generateBtn = $('#generateBtn');
const durationSlider = $('#durationSlider');
const durationValue = $('#durationValue');
const durationOptions = $('#durationOptions');
const statusSection = $('#statusSection');
const statusMessage = $('#statusMessage');
const progressFill = $('#progressFill');
const resultSection = $('#resultSection');
const promptHeader = $('#promptHeader');
const promptBody = $('#promptBody');
const promptArrow = $('#promptArrow');
const enhancedPrompt = $('#enhancedPrompt');
const audioPlayer = $('#audioPlayer');
const playBtn = $('#playBtn');
const prevBtn = $('#prevBtn');
const nextBtn = $('#nextBtn');
const progressTrack = $('#progressTrack');
const progressCurrent = $('#progressCurrent');
const progressThumb = $('#progressThumb');
const currentTime = $('#currentTime');
const totalTime = $('#totalTime');
const volumeRange = $('#volumeRange');
const volumeFill = $('#volumeFill');
const playerMeta = $('#playerMeta');
const downloadLink = $('#downloadLink');
const historyToggleBtn = $('#historyToggleBtn');
const historyOverlay = $('#historyOverlay');
const historyCloseBtn = $('#historyCloseBtn');
const historyList = $('#historyList');
const deleteAllBtn = $('#deleteAllBtn');
const confirmModal = $('#confirmModal');
const modalCancelBtn = $('#modalCancelBtn');
const modalConfirmBtn = $('#modalConfirmBtn');

// --- Duration slider + buttons sync ---
durationSlider.addEventListener('input', () => {
    state.duration = parseInt(durationSlider.value);
    durationValue.textContent = `${state.duration}秒`;
    // sync buttons
    $$('.dur-btn').forEach(b => {
        b.classList.toggle('active', parseInt(b.dataset.duration) === state.duration);
    });
});

durationOptions.addEventListener('click', (e) => {
    const btn = e.target.closest('.dur-btn');
    if (!btn) return;
    state.duration = parseInt(btn.dataset.duration);
    durationSlider.value = state.duration;
    durationValue.textContent = `${state.duration}秒`;
    $$('.dur-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
});

// --- Collapsible prompt ---
promptHeader.addEventListener('click', () => {
    state.promptExpanded = !state.promptExpanded;
    promptBody.classList.toggle('expanded', state.promptExpanded);
    promptArrow.classList.toggle('collapsed', !state.promptExpanded);
    promptArrow.classList.toggle('expanded', state.promptExpanded);
});

// --- Generate ---
generateBtn.addEventListener('click', async () => {
    const userInput = promptInput.value.trim();
    if (!userInput) {
        promptInput.focus();
        return;
    }
    if (state.generating) return;

    state.generating = true;
    generateBtn.disabled = true;
    generateBtn.textContent = '⏳ 准备中...';
    hideResult();
    showStatus('准备中...', 0);

    try {
        const response = await fetch('/api/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_input: userInput, duration: state.duration }),
        });

        if (response.status === 429) {
            showStatus('系统忙碌中，请稍后重试...', 0);
            resetGenerateBtn();
            return;
        }
        if (!response.ok) {
            const err = await response.json().catch(() => ({ detail: 'Unknown error' }));
            showStatus(`错误: ${err.detail}`, 0);
            resetGenerateBtn();
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let lastEvent = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.startsWith('event: ')) {
                    lastEvent = line.slice(7).trim();
                    continue;
                }
                if (line.startsWith('data: ')) {
                    const dataStr = line.slice(6);
                    try {
                        const data = JSON.parse(dataStr);
                        handleSSEEvent(data, lastEvent);
                    } catch {
                        // incomplete JSON, will retry
                    }
                    lastEvent = '';
                }
            }
        }
    } catch (err) {
        showStatus(`网络错误: ${err.message}`, 0);
    }
    if (state.generating) {
        resetGenerateBtn();
    }
});

function handleSSEEvent(data, eventName) {
    // Complete event
    if (data.stage === undefined) {
        hideStatus();
        state.generating = false;
        generateBtn.disabled = false;
        generateBtn.textContent = '生成音乐';
        showResult(data.prompt_enhanced, data.filename, data.enhanced);
        return;
    }

    if (data.stage === 'error') {
        showStatus(`错误: ${data.message}`, 0);
        progressFill.style.background = '#8b4a4a';
        state.generating = false;
        generateBtn.disabled = false;
        generateBtn.textContent = '生成音乐';
        return;
    }

    const stageMessages = {
        enhancing: { msg: '正在优化提示词...', btn: '⏳ 优化提示词中...', pct: 10 },
        generating: { msg: '正在生成音乐，预计需要 30-60 秒...', btn: '🎵 生成音乐中...', pct: 40 },
        converting: { msg: '正在转换音频格式...', btn: '🔄 转换格式中...', pct: 80 },
    };

    const s = stageMessages[data.stage] || { msg: data.message, btn: '⏳ 处理中...', pct: 50 };
    showStatus(data.message || s.msg, s.pct);
    generateBtn.textContent = s.btn;
}

function showStatus(msg, progressPercent) {
    statusSection.classList.remove('hidden');
    statusMessage.textContent = msg;
    progressFill.style.width = `${progressPercent}%`;
}

function hideStatus() {
    statusSection.classList.add('hidden');
}

function hideResult() {
    resultSection.classList.add('hidden');
    audioPlayer.pause();
}

function resetGenerateBtn() {
    state.generating = false;
    generateBtn.disabled = false;
    generateBtn.textContent = '生成音乐';
    hideStatus();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showResult(promptEnhanced, filename, wasEnhanced) {
    resultSection.classList.remove('hidden');

    if (wasEnhanced && promptEnhanced) {
        enhancedPrompt.innerHTML = escapeHtml(promptEnhanced);
        // Keep prompt collapsed by default
        if (state.promptExpanded) {
            promptBody.classList.remove('expanded');
            promptArrow.classList.add('collapsed');
            promptArrow.classList.remove('expanded');
            state.promptExpanded = false;
        }
    } else {
        enhancedPrompt.innerHTML = '<span style="color:var(--text-muted);">（未进行提示词优化）</span>';
    }

    // Setup audio
    audioPlayer.src = `/output/${filename}`;
    downloadLink.href = `/output/${filename}`;
    downloadLink.download = filename;
    playerMeta.textContent = formatDateForPlayer(new Date());

    // Reset player state
    audioPlayer.load();
    playBtn.textContent = '▶';
    progressCurrent.style.width = '0%';
    progressThumb.style.left = '0%';
    currentTime.textContent = '00:00';

    audioPlayer.addEventListener('loadedmetadata', () => {
        totalTime.textContent = formatTime(audioPlayer.duration);
    }, { once: true });

    resultSection.scrollIntoView({ behavior: 'smooth' });
}

// --- Audio player controls ---
playBtn.addEventListener('click', () => {
    if (audioPlayer.paused) {
        audioPlayer.play();
        playBtn.textContent = '⏸';
    } else {
        audioPlayer.pause();
        playBtn.textContent = '▶';
    }
});

audioPlayer.addEventListener('ended', () => {
    playBtn.textContent = '▶';
    progressCurrent.style.width = '0%';
    progressThumb.style.left = '0%';
    currentTime.textContent = '00:00';
});

audioPlayer.addEventListener('timeupdate', () => {
    if (audioPlayer.duration) {
        const pct = (audioPlayer.currentTime / audioPlayer.duration) * 100;
        progressCurrent.style.width = `${pct}%`;
        progressThumb.style.left = `${pct}%`;
        currentTime.textContent = formatTime(audioPlayer.currentTime);
    }
});

// Click on progress track to seek
progressTrack.addEventListener('click', (e) => {
    if (!audioPlayer.duration) return;
    const rect = progressTrack.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    audioPlayer.currentTime = pct * audioPlayer.duration;
});

// Volume
volumeRange.addEventListener('input', () => {
    const val = parseInt(volumeRange.value);
    audioPlayer.volume = val / 100;
    volumeFill.style.width = `${val}%`;
});

function formatTime(sec) {
    if (!sec || isNaN(sec)) return '00:00';
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function formatDateForPlayer(date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d} 生成`;
}

// --- History ---
historyToggleBtn.addEventListener('click', () => {
    historyOverlay.classList.remove('hidden');
    loadHistory();
});
historyCloseBtn.addEventListener('click', () => historyOverlay.classList.add('hidden'));
historyOverlay.addEventListener('click', (e) => {
    if (e.target === historyOverlay) historyOverlay.classList.add('hidden');
});

async function loadHistory() {
    try {
        const res = await fetch('/api/history');
        const data = await res.json();
        renderHistory(data.items || []);
    } catch (err) {
        historyList.innerHTML = '<p style="color:var(--text-muted);">加载失败</p>';
    }
}

function renderHistory(items) {
    if (items.length === 0) {
        historyList.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:40px 0;">暂无生成记录</p>';
        return;
    }
    historyList.innerHTML = items.map(item => `
        <div class="history-item" data-id="${item.id}">
            <div class="hi-date">${formatDate(item.created_at)}</div>
            <div class="hi-prompt">"${escapeHtml(item.user_input)}"</div>
            <div class="hi-actions">
                <button onclick="playFromHistory('${escapeAttr(item.filename)}')">▶ 播放</button>
                <a href="/output/${escapeAttr(item.filename)}" download>下载</a>
                <button class="btn-delete" onclick="deleteHistory(${item.id}, '${escapeAttr(item.filename)}')">删除</button>
            </div>
        </div>
    `).join('');
}

function formatDate(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr.replace(' ', 'T') + 'Z');
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function escapeAttr(str) {
    return String(str).replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

function playFromHistory(filename) {
    historyOverlay.classList.add('hidden');
    audioPlayer.src = `/output/${filename}`;
    downloadLink.href = `/output/${filename}`;
    downloadLink.download = filename;
    resultSection.classList.remove('hidden');
    enhancedPrompt.innerHTML = '<span style="color:var(--text-muted);">（从历史记录加载）</span>';
    playerMeta.textContent = '从历史记录加载';
    audioPlayer.load();
    playBtn.textContent = '▶';
    progressCurrent.style.width = '0%';
    currentTime.textContent = '00:00';
    resultSection.scrollIntoView({ behavior: 'smooth' });
}

async function deleteHistory(id, filename) {
    if (!confirm('确定删除这条记录吗？')) return;
    try {
        const res = await fetch(`/api/history/${id}`, { method: 'DELETE' });
        if (res.ok) {
            if (audioPlayer.src.includes(filename)) {
                audioPlayer.pause();
                resultSection.classList.add('hidden');
            }
            loadHistory();
        }
    } catch (err) {
        alert('删除失败');
    }
}

// --- Delete all with modal ---
deleteAllBtn.addEventListener('click', () => {
    confirmModal.classList.add('active');
});

modalCancelBtn.addEventListener('click', () => {
    confirmModal.classList.remove('active');
});

confirmModal.addEventListener('click', (e) => {
    if (e.target === confirmModal) confirmModal.classList.remove('active');
});

modalConfirmBtn.addEventListener('click', async () => {
    confirmModal.classList.remove('active');
    try {
        const res = await fetch('/api/history', { method: 'DELETE' });
        if (res.ok) {
            audioPlayer.pause();
            resultSection.classList.add('hidden');
            loadHistory();
        }
    } catch (err) {
        alert('删除失败');
    }
});
```

- [ ] **Step 2: Commit**

```bash
git add static/script.js
git commit -m "feat: Victorian JS with slider, collapsible, custom player, delete-all modal"
```

---

### Task 7: Verify with a quick smoke test

**Files:**
- Run: Docker container start + health check

- [ ] **Step 1: Start Docker and check fonts load**

```bash
docker compose up -d
docker compose logs --tail=20
```

Verify the app starts without errors and the page renders at `http://localhost:8000`.

- [ ] **Step 2: Check the page loads with correct fonts and styling**

Open the page in a browser and verify:
- [ ] Google Fonts load (ZCOOL QingKe HuangYou + Noto Serif SC)
- [ ] Duration slider renders with custom thumb
- [ ] Duration buttons sync with slider
- [ ] Collapsible prompt toggles on click
- [ ] Generate button has gold gradient
- [ ] History panel shows centered layout
- [ ] Delete-all modal opens with Victorian styling
- [ ] Audio player shows vinyl disc and custom controls
