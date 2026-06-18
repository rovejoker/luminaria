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
    if (!userInput || state.generating) return;

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
    const hasActive = queue.length > 0 && !['completed', 'cancelled', 'failed'].includes(queue[0]?.status);

    if (hasActive) {
        state.generating = true;
        generateBtn.disabled = true;
        generateBtn.textContent = '🎵 生成音乐中...';
        const active = queue[0];
        showStatus(active.message, active.progress);
    } else {
        state.generating = false;
        generateBtn.disabled = !promptInput.value.trim();
        generateBtn.textContent = '生成音乐';
        hideStatus();
    }
}

// Also update generate button when input changes
promptInput.addEventListener('input', () => {
    if (!state.generating) {
        generateBtn.disabled = !promptInput.value.trim();
    }
});

function handleCompletedTask() {
    const queue = state.taskQueue;
    for (const item of queue) {
        if (item.status === 'completed' && item.result) {
            showResult(
                item.result.prompt_enhanced,
                item.result.filename,
                item.result.enhanced
            );
            hideStatus();
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

function hideResult() {
    resultSection.classList.add('hidden');
    audioPlayer.pause();
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

progressTrack.addEventListener('click', (e) => {
    if (!audioPlayer.duration) return;
    const rect = progressTrack.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    audioPlayer.currentTime = pct * audioPlayer.duration;
});

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

// --- Init ---
connectEventStream();
