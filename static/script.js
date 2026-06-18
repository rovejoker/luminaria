// LuminAria — Victorian classical client-side logic with task queue support

const state = {
    duration: 90,
    generating: false,
    audioFilename: null,
    promptExpanded: false,
    taskQueue: [],
    eventSource: null,
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

// --- Duration slider + buttons sync ---
durationSlider.addEventListener('input', () => {
    state.duration = parseInt(durationSlider.value);
    durationValue.textContent = `${state.duration}秒`;
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

// --- Generate / Add to queue ---
generateBtn.addEventListener('click', async () => {
    const userInput = promptInput.value.trim();
    if (!userInput) return;

    try {
        const response = await fetch('/api/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_input: userInput, duration: state.duration }),
        });

        if (response.status === 429) {
            const err = await response.json();
            showStatus(err.detail || '队列已满', 0);
            return;
        }
        if (!response.ok) {
            const err = await response.json().catch(() => ({ detail: '请求失败' }));
            showStatus(`错误: ${err.detail}`, 0);
            return;
        }

        // Auto-clear input on success
        promptInput.value = '';
    } catch (err) {
        showStatus(`网络错误: ${err.message}`, 0);
    }
});

// --- Global SSE connection ---
function connectEventStream() {
    if (state.eventSource) {
        state.eventSource.close();
    }

    const es = new EventSource('/api/events');
    state.eventSource = es;

    es.addEventListener('queue_update', (e) => {
        try {
            const data = JSON.parse(e.data);
            state.taskQueue = data.queue || [];
            renderQueuePanel();
            updateGenerateButton();
            handleCompletedTask();
        } catch (err) {
            console.error('SSE parse error:', err);
        }
    });

    es.onerror = () => {
        es.close();
        state.eventSource = null;
        setTimeout(connectEventStream, 3000);
    };
}

// --- Queue panel ---
function renderQueuePanel() {
    const container = document.getElementById('queueList');
    if (!container) return;

    const queue = state.taskQueue;
    if (!queue || queue.length === 0) {
        container.innerHTML = '<div class="queue-empty">暂无排队任务</div>';
        return;
    }

    container.innerHTML = queue.map((item, idx) => {
        const isActive = idx === 0;
        const statusLabels = {
            queued: '排队中',
            enhancing: '优化提示词',
            generating: '生成中',
            converting: '转换中',
            completed: '已完成',
            failed: '失败',
            cancelled: '已取消',
        };
        const label = statusLabels[item.status] || item.status;
        const canCancel = ['queued', 'enhancing', 'generating', 'converting'].includes(item.status);

        return `
            <div class="queue-item ${isActive ? 'active' : ''} ${['cancelled', 'failed'].includes(item.status) ? 'cancelled' : ''} ${item.status === 'completed' ? 'completed' : ''}">
                <div class="qi-header">
                    <span class="qi-prompt" title="${escapeHtml(item.user_input)}">${escapeHtml(item.user_input)}</span>
                    <span class="qi-status-badge ${item.status}">${label}</span>
                </div>
                ${['generating', 'enhancing', 'converting'].includes(item.status) ? `
                    <div class="qi-progress">
                        <div class="qi-progress-fill" style="width:${item.progress}%"></div>
                    </div>
                ` : ''}
                <div class="qi-footer">
                    <span class="qi-message">${isActive ? escapeHtml(item.message) : ''}</span>
                    ${canCancel ? `<button class="qi-cancel-btn" onclick="cancelTask('${item.task_id}')">取消</button>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

async function cancelTask(taskId) {
    try {
        const res = await fetch(`/api/tasks/${taskId}/cancel`, { method: 'POST' });
        if (!res.ok) {
            console.error('Cancel failed');
        }
    } catch (err) {
        console.error('Cancel error:', err);
    }
}

function updateGenerateButton() {
    const queue = state.taskQueue;
    const hasActiveTask = queue.length > 0 && !['completed', 'cancelled', 'failed'].includes(queue[0]?.status);
    const hasAnyLive = queue.some(t => !['completed', 'cancelled', 'failed'].includes(t.status));

    state.generating = hasActiveTask;

    if (hasActiveTask) {
        generateBtn.textContent = '添加任务';
        const active = queue[0];
        showStatus(active.message, active.progress);
    } else if (hasAnyLive) {
        generateBtn.textContent = '添加任务';
        hideStatus();
    } else {
        generateBtn.textContent = '生成音乐';
        hideStatus();
    }
    generateBtn.disabled = !promptInput.value.trim();
}

// Update button when input changes
promptInput.addEventListener('input', updateGenerateButton);

let lastShownResultId = null;

function handleCompletedTask() {
    const queue = state.taskQueue;
    // Refresh history panel when we see a new completed task
    for (const item of queue) {
        if (item.status === 'completed' && item.result && item.result.id !== lastShownResultId) {
            lastShownResultId = item.result.id;
            // Don't auto-play — just refresh history
            loadRightHistory();
            break;
        }
    }
}

// --- Status display ---
function showStatus(msg, progressPercent) {
    statusSection.classList.remove('hidden');
    statusMessage.textContent = msg;
    progressFill.style.width = `${progressPercent}%`;
}

function hideStatus() {
    statusSection.classList.add('hidden');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function escapeAttr(str) {
    return String(str).replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

// --- History items cache for prev/next navigation ---
let _historyItems = [];

function setPromptTitle(enhanced) {
    const title = document.getElementById('promptTitle');
    if (title) title.textContent = enhanced ? '优化后提示词' : '提示词';
}

function openPlayer() {
    resultSection.classList.remove('hidden');
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function closePlayer() {
    resultSection.classList.add('hidden');
    audioPlayer.pause();
}

function showOriginalPrompt(text) {
    setPromptTitle(false);
    enhancedPrompt.innerHTML = '“' + escapeHtml(text) + '”';
}

function showResult(promptEnhanced, filename, wasEnhanced) {
    openPlayer();
    setPromptTitle(true);

    if (wasEnhanced && promptEnhanced) {
        enhancedPrompt.innerHTML = escapeHtml(promptEnhanced);
        if (state.promptExpanded) {
            promptBody.classList.remove('expanded');
            promptArrow.classList.add('collapsed');
            promptArrow.classList.remove('expanded');
            state.promptExpanded = false;
        }
    } else {
        enhancedPrompt.innerHTML = '<span style="color:var(--text-muted);">（未进行提示词优化）</span>';
    }

    audioPlayer.src = `/output/${filename}`;
    downloadLink.href = `/output/${filename}`;
    downloadLink.download = filename;
    playerMeta.textContent = formatDateForPlayer(new Date());

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

// --- Progress bar dragging (also handles single click) ---
let _isDragging = false;

function seekFromEvent(e) {
    const rect = progressTrack.getBoundingClientRect();
    const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const dur = audioPlayer.duration;
    if (!dur || isNaN(dur)) return;
    audioPlayer.currentTime = pct * dur;
    progressCurrent.style.width = `${pct * 100}%`;
    progressThumb.style.left = `${pct * 100}%`;
}

progressTrack.addEventListener('mousedown', (e) => {
    e.preventDefault();
    _isDragging = true;
    seekFromEvent(e);
});

document.addEventListener('mousemove', (e) => {
    if (!_isDragging) return;
    e.preventDefault();
    seekFromEvent(e);
});

document.addEventListener('mouseup', () => {
    _isDragging = false;
    // Remove any text selection that might have started
    window.getSelection().removeAllRanges();
});

// --- Prev / Next navigation ---
function findCurrentIndex() {
    const currentSrc = audioPlayer.src;
    return _historyItems.findIndex(item => currentSrc.endsWith(item.filename));
}

prevBtn.addEventListener('click', () => {
    const idx = findCurrentIndex();
    if (idx > 0) {
        const prev = _historyItems[idx - 1];
        playFromHistory(prev.filename, prev.user_input);
    }
});

nextBtn.addEventListener('click', () => {
    const idx = findCurrentIndex();
    if (idx >= 0 && idx < _historyItems.length - 1) {
        const next = _historyItems[idx + 1];
        playFromHistory(next.filename, next.user_input);
    } else if (idx === -1 && _historyItems.length > 0) {
        // Not playing from history, play the latest
        const latest = _historyItems[0];
        playFromHistory(latest.filename, latest.user_input);
    }
});

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

volumeRange.addEventListener('input', () => {
    const val = parseInt(volumeRange.value);
    audioPlayer.volume = val / 100;
    volumeFill.style.width = `${val}%`;
});

// Click on volume fill area to set volume too
const volSlider = document.querySelector('.volume-slider');
volSlider.addEventListener('click', (e) => {
    if (e.target === volumeRange) return;
    const rect = volSlider.getBoundingClientRect();
    const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const val = Math.round(pct * 100);
    volumeRange.value = val;
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

function playFromHistory(filename, userInput) {
    openPlayer();
    audioPlayer.src = `/output/${filename}`;
    downloadLink.href = `/output/${filename}`;
    downloadLink.download = filename;
    showOriginalPrompt(userInput);
    playerMeta.textContent = '从历史记录加载';
    audioPlayer.load();
    playBtn.textContent = '⏸';
    progressCurrent.style.width = '0%';
    currentTime.textContent = '00:00';
    audioPlayer.play().catch(() => {});
}

// --- Right-panel history ---
// Loaded on page load and after each delete
async function loadRightHistory() {
    try {
        const res = await fetch('/api/history?limit=10');
        const data = await res.json();
        _historyItems = data.items || [];
        renderRightHistory(_historyItems);
    } catch (err) {
        // silent — panel just stays empty
    }
}

function renderRightHistory(items) {
    const container = document.getElementById('rhList');
    if (!container) return;
    if (items.length === 0) {
        container.innerHTML = '<div class="rh-empty">暂无历史记录</div>';
        return;
    }
    container.innerHTML = items.map(item => `
        <div class="rh-item" title="${escapeHtml(item.user_input)}" data-filename="${escapeAttr(item.filename)}" data-input="${escapeAttr(item.user_input)}" data-id="${item.id}">
            <span class="rh-item-prompt">${escapeHtml(item.user_input)}</span>
            <span class="rh-item-actions">
                <button class="rh-play-btn" title="播放">▶</button>
                <a href="/output/${escapeAttr(item.filename)}" download title="下载">↓</a>
                <button class="rh-del" title="删除">✕</button>
            </span>
        </div>
    `).join('');

    // Click on the row (not actions) opens player without auto-play
    container.querySelectorAll('.rh-item').forEach(el => {
        el.addEventListener('click', (e) => {
            if (e.target.closest('.rh-item-actions')) return;
            const fname = el.dataset.filename;
            const input = el.dataset.input;
            openPlayer();
            audioPlayer.src = `/output/${fname}`;
            downloadLink.href = `/output/${fname}`;
            downloadLink.download = fname;
            showOriginalPrompt(input);
            playerMeta.textContent = '从历史记录加载';
            audioPlayer.load();
            playBtn.textContent = '▶';
            progressCurrent.style.width = '0%';
            currentTime.textContent = '00:00';
        });
    });

    // Play button directly plays
    container.querySelectorAll('.rh-play-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const el = btn.closest('.rh-item');
            playFromHistory(el.dataset.filename, el.dataset.input);
        });
    });

    // Delete button
    container.querySelectorAll('.rh-del').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const el = btn.closest('.rh-item');
            const id = parseInt(el.dataset.id);
            const filename = el.dataset.filename;
            if (id) deleteRightHistory(id, filename);
        });
    });
}

async function deleteRightHistory(id, filename) {
    try {
        const res = await fetch(`/api/history/${id}`, { method: 'DELETE' });
        if (res.ok) {
            if (audioPlayer.src.includes(filename)) {
                closePlayer();
            }
            loadRightHistory();
        }
    } catch (err) {
        // silent
    }
}

// --- Delete all (from right panel) ---
const $modal = document.getElementById('confirmModal');
const $modalConfirm = document.getElementById('modalConfirmBtn');
const $modalCancel = document.getElementById('modalCancelBtn');

document.getElementById('deleteAllBtn').addEventListener('click', () => {
    $modal.classList.add('active');
});

$modalCancel.addEventListener('click', () => {
    $modal.classList.remove('active');
});

$modal.addEventListener('click', (e) => {
    if (e.target === $modal) $modal.classList.remove('active');
});

$modalConfirm.addEventListener('click', async () => {
    $modal.classList.remove('active');
    try {
        const res = await fetch('/api/history', { method: 'DELETE' });
        if (res.ok) {
            closePlayer();
            loadRightHistory();
        }
    } catch (err) {
        // silent
    }
});

// --- Init ---
connectEventStream();
loadRightHistory();

// Click outside player to close (not when clicking history items)
document.addEventListener('click', (e) => {
    if (!resultSection.classList.contains('hidden') &&
        !resultSection.contains(e.target) &&
        e.target !== generateBtn &&
        !e.target.closest('.rh-item')) {
        closePlayer();
    }
});
