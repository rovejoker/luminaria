// LuminAria — client-side logic: SSE generation, history CRUD, audio player

const state = {
    duration: 90,           // selected duration in seconds
    generating: false,      // generation in progress
    audioFilename: null,    // current audio filename
};

// --- DOM refs ---
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const promptInput = $('#promptInput');
const generateBtn = $('#generateBtn');
const durationOptions = $('#durationOptions');
const statusSection = $('#statusSection');
const statusMessage = $('#statusMessage');
const progressFill = $('#progressFill');
const resultSection = $('#resultSection');
const enhancedPrompt = $('#enhancedPrompt');
const audioPlayer = $('#audioPlayer');
const downloadLink = $('#downloadLink');
const historyToggleBtn = $('#historyToggleBtn');
const historyOverlay = $('#historyOverlay');
const historyCloseBtn = $('#historyCloseBtn');
const historyList = $('#historyList');

// --- Duration selection ---
durationOptions.addEventListener('click', (e) => {
    const btn = e.target.closest('.dur-btn');
    if (!btn) return;
    state.duration = parseInt(btn.dataset.duration);
    $$('.dur-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
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

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.startsWith('event: ')) {
                    continue;
                }
                if (line.startsWith('data: ')) {
                    const dataStr = line.slice(6);
                    try {
                        const data = JSON.parse(dataStr);
                        handleSSEEvent(data);
                    } catch {
                        // incomplete JSON, will be retried
                    }
                }
            }
        }

    } catch (err) {
        showStatus(`网络错误: ${err.message}`, 0);
    }
    resetGenerateBtn();
});

function handleSSEEvent(data) {
    if (data.stage === 'enhancing') {
        showStatus(data.message, 10);
        generateBtn.textContent = '✨ 优化提示词中...';
    } else if (data.stage === 'generating') {
        showStatus(data.message, 40);
        generateBtn.textContent = '🎵 生成音乐中...';
    } else if (data.stage === 'converting') {
        showStatus(data.message, 80);
        generateBtn.textContent = '🔄 转换格式中...';
    } else if (data.stage === 'error') {
        showStatus(`错误: ${data.message}`, 0);
    }
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
}

function resetGenerateBtn() {
    state.generating = false;
    generateBtn.disabled = false;
    generateBtn.textContent = '✨ 生成音乐';
    hideStatus();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// SSE 'complete' event is handled separately — it arrives in the same stream
// but we need to intercept it. The trick: we listen for it inline.
// Actually, the handleSSEEvent will catch the "complete" stage too.
// Let's extend handleSSEEvent.
const originalHandleSSE = handleSSEEvent;
handleSSEEvent = function(data) {
    if (data.stage === 'error') {
        originalHandleSSE(data);
        resetGenerateBtn();
        return;
    }
    if (!data.stage) {
        // This is the 'complete' event — it has id, filename, etc.
        hideStatus();
        state.generating = false;
        generateBtn.disabled = false;
        generateBtn.textContent = '✨ 生成音乐';
        showResult(data.prompt_enhanced, data.filename, data.enhanced);
        return;
    }
    originalHandleSSE(data);
};

function showResult(promptEnhanced, filename, wasEnhanced) {
    resultSection.classList.remove('hidden');

    if (wasEnhanced && promptEnhanced) {
        enhancedPrompt.innerHTML = `<strong style="color:var(--gold-dim);font-size:0.8rem;">优化后的提示词</strong><br>${escapeHtml(promptEnhanced)}`;
    } else {
        enhancedPrompt.innerHTML = '<span style="color:var(--text-secondary);">（未进行提示词优化）</span>';
    }

    audioPlayer.src = `/output/${filename}`;
    downloadLink.href = `/output/${filename}`;
    downloadLink.download = filename;
    audioPlayer.load();
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
        historyList.innerHTML = '<p style="color:var(--text-secondary);">加载失败</p>';
    }
}

function renderHistory(items) {
    if (items.length === 0) {
        historyList.innerHTML = '<p style="color:var(--text-secondary);text-align:center;padding:40px 0;">暂无生成记录</p>';
        return;
    }
    historyList.innerHTML = items.map(item => `
        <div class="history-item" data-id="${item.id}">
            <div class="hi-date">${formatDate(item.created_at)}</div>
            <div class="hi-prompt">"${escapeHtml(item.user_input)}"</div>
            <div class="hi-duration">${formatDuration(item.duration)}</div>
            <div class="hi-actions">
                <button onclick="playFromHistory('${escapeAttr(item.filename)}')">▶ 播放</button>
                <a href="/output/${escapeAttr(item.filename)}" download>⬇ 下载</a>
                <button class="btn-delete" onclick="deleteHistory(${item.id}, '${escapeAttr(item.filename)}')">🗑 删除</button>
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

function formatDuration(sec) {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    if (s === 0) return `${m}min`;
    return `${m}min${s}s`;
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
    enhancedPrompt.innerHTML = '<span style="color:var(--text-secondary);">（从历史记录加载）</span>';
    audioPlayer.load();
    resultSection.scrollIntoView({ behavior: 'smooth' });
}

async function deleteHistory(id, filename) {
    if (!confirm('确定删除这条记录吗？')) return;
    try {
        const res = await fetch(`/api/history/${id}`, { method: 'DELETE' });
        if (res.ok) {
            if (audioPlayer.src.includes(filename)) {
                audioPlayer.src = '';
                resultSection.classList.add('hidden');
            }
            loadHistory();
        }
    } catch (err) {
        alert('删除失败');
    }
}
