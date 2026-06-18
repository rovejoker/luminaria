# Plan: Left Panel Advanced Generation Parameters

## Goal
Add 4 professional model parameters to the left panel: Sampling Steps, CFG Scale, Seed, Sampler.

## Scope & Impact
- **5 files changed**: `index.html`, `style.css`, `script.js`, `models.py`, `generator.py`
- **1 file touched lightly**: `queue.py` (pass-through, already stores `duration` — extends pattern)
- **No new dependencies**, no DB schema changes needed (params go into result metadata, not new DB columns)
- **Theme**: Victorian classical (暗夜鎏金), matching existing style

---

## Step 1 — Backend: Extend `GenerateRequest` model

**File**: `app/models.py`

Add optional fields to `GenerateRequest`:
```python
class GenerateRequest(BaseModel):
    user_input: str = Field(..., min_length=1, max_length=1000)
    duration: int = Field(default=90, ge=15, le=120)
    steps: int = Field(default=25, ge=10, le=100)        # NEW
    cfg_scale: float = Field(default=6.0, ge=1.0, le=15.0) # NEW
    seed: int = Field(default=-1, ge=-1, le=2**31-1)       # NEW
    sampler: str = Field(default="dpmpp-2m-sde")            # NEW
```

---

## Step 2 — Backend: Extend `QueuedTask` to store params

**File**: `app/queue.py`

Add param fields to `QueuedTask.__init__`:
```python
def __init__(self, task_id, user_input, duration, steps=25, cfg_scale=6.0, seed=-1, sampler="dpmpp-2m-sde"):
```

Pass them through in `to_dict()` and `result`.

---

## Step 3 — Backend: Pass params to generator

**File**: `app/queue.py` → `_execute_task()`

Pass `steps`, `cfg_scale`, `seed`, `sampler` to `generate_audio()`.

---

## Step 4 — Backend: Use params in `generate_audio()`

**File**: `app/generator.py`

Replace hardcoded values with parameters:
```python
def generate_audio(prompt, duration_seconds, steps=25, cfg_scale=6.0, seed=-1, sampler="dpmpp-2m-sde"):
```
- If `seed != -1`: set `torch.manual_seed(seed)` before generation
- Pass `steps`, `cfg_scale`, `sampler_type=sampler` to the diffusion call

---

## Step 5 — Frontend: Add left-panel HTML controls

**File**: `static/index.html`

Replace the empty `<aside class="left-panel"></aside>` with a styled panel containing:
1. ⚙️ 高级参数 (section title with ornament)
2. 🎯 采样步数 — slider (10-100, default 25) + preset buttons (15/25/50/100)
3. 🎚️ CFG 引导强度 — slider (1.0-15.0, step 0.5, default 6.0) with numeric display
4. 🎲 随机种子 — number input (-1) + randomize button
5. 🔄 采样器 — styled dropdown with 5 options

---

## Step 6 — Frontend: CSS Victorian styling

**File**: `static/style.css`

Add styles for the left panel, matching the existing dark/victorian theme:
- `.left-panel` styling consistent with `.right-panel` (gold borders, dark bg)
- Parameter group styling with gold text, gold-trim elements
- Custom styled range sliders matching the duration slider
- Custom styled select/dropdown for sampler
- Seed input with inline random button

---

## Step 7 — Frontend: JS state and API wiring

**File**: `static/script.js`

1. Add to `state` object: `steps`, `cfgScale`, `seed`, `sampler`
2. Sync slider/input values with state
3. Read all params when sending `/api/generate` request
4. Seed "randomize" button generates crypto-random int

---

## Verification
1. Open app, left panel shows 4 parameter controls
2. Adjust parameters, click generate — observe them in request payload
3. Check server logs: parameters flow through to generator
4. Visual check: Victorian styling matches existing theme