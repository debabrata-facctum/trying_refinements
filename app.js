document.addEventListener('DOMContentLoaded', () => {
    const app = document.getElementById('app');

    // ---- Chat DOM ----
    const chatArea = document.getElementById('chat-area');
    const chatColumn = document.getElementById('chat-column');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const statusIndicator = document.getElementById('status-indicator');
    const connWrap = document.getElementById('conn-wrap');
    const connText = document.getElementById('conn-text');
    const modelPillName = document.getElementById('model-pill-name');

    // ---- Sidebar / nav ----
    const collapseBtn = document.getElementById('collapseBtn');
    const showBtn = document.getElementById('showBtn');
    const newChatBtn = document.getElementById('newChatBtn');
    const settingsNavBtn = document.getElementById('settingsNavBtn');

    // ---- Overlays ----
    const settingsOverlay = document.getElementById('settingsOverlay');
    const closeSettingsBtn = document.getElementById('close-settings');
    const modelOverlay = document.getElementById('modelOverlay');
    const modalClose = document.getElementById('modalClose');
    const modelPill = document.getElementById('modelPill');
    const miOpenSettings = document.getElementById('mi-open-settings');

    // ---- Context popover ----
    const ctxBtn = document.getElementById('ctxBtn');
    const ctxPop = document.getElementById('ctxPop');
    const ctxVal = document.getElementById('ctx-val');
    const ctxBarFill = document.getElementById('ctx-bar-fill');
    const ctxArc = document.getElementById('ctx-arc');
    const ctxCircle = document.getElementById('ctxBtn');
    const RING_CIRCUMFERENCE = 2 * Math.PI * 9; // r=9 in the 24x24 viewBox

    // ---- Settings inputs ----
    const apiUrlInput = document.getElementById('api-url');
    const modelNameInput = document.getElementById('model-name');
    const systemPromptInput = document.getElementById('system-prompt');
    const saveSettingsBtn = document.getElementById('save-settings');
    const resetSettingsBtn = document.getElementById('reset-settings');

    const modelPathInput = document.getElementById('model-path-input');
    const pickModelBtn = document.getElementById('pick-model-btn');
    const nCtxInput = document.getElementById('n-ctx-input');
    const nThreadsInput = document.getElementById('n-threads-input');
    const nGpuLayersInput = document.getElementById('n-gpu-layers-input');
    const loadModelBtn = document.getElementById('load-model-btn');
    const modelStatusText = document.getElementById('model-status-text');

    const hwDetectionBanner = document.getElementById('hw-detection-banner');
    const hwBannerText = document.getElementById('hw-banner-text');
    const hwCpuFlags = document.getElementById('hw-cpu-flags');
    const hwProfileSelect = document.getElementById('hw-profile-select');
    const nBatchInput = document.getElementById('n-batch-input');
    const flashAttnToggle = document.getElementById('flash-attn-toggle');
    const mlockToggle = document.getElementById('mlock-toggle');
    const numaToggle = document.getElementById('numa-toggle');
    const kvQuantSelect = document.getElementById('kv-quant-select');

    const maxTokensInput = document.getElementById('max-tokens-input');
    const summarizeToggle = document.getElementById('summarize-toggle');
    const temperatureInput = document.getElementById('temperature-input');
    const temperatureValue = document.getElementById('temperature-value');
    const topPInput = document.getElementById('top-p-input');
    const topPValue = document.getElementById('top-p-value');
    const topKInput = document.getElementById('top-k-input');
    const topKValue = document.getElementById('top-k-value');
    const repeatPenaltyInput = document.getElementById('repeat-penalty-input');
    const repeatPenaltyValue = document.getElementById('repeat-penalty-value');

    // ---- File browser ----
    const fileBrowserModal = document.getElementById('file-browser-modal');
    const browserCurrentPath = document.getElementById('browser-current-path');
    const browserEntries = document.getElementById('browser-entries');
    const browserGoUpBtn = document.getElementById('browser-go-up-btn');
    const closeBrowserBtn = document.getElementById('close-browser-btn');

    // ---- Model info modal fields ----
    const mi = {
        model: document.getElementById('mi-model'),
        path: document.getElementById('mi-path'),
        status: document.getElementById('mi-status'),
        params: document.getElementById('mi-params'),
        size: document.getElementById('mi-size'),
        trainctx: document.getElementById('mi-trainctx'),
        embd: document.getElementById('mi-embd'),
        vocab: document.getElementById('mi-vocab'),
        ctx: document.getElementById('mi-ctx'),
        gpu: document.getElementById('mi-gpu'),
        threads: document.getElementById('mi-threads'),
        batch: document.getElementById('mi-batch'),
        flash: document.getElementById('mi-flash'),
        mlock: document.getElementById('mi-mlock'),
        numa: document.getElementById('mi-numa'),
    };

    // ---- Inline SVG icons ----
    const ICON = {
        token: '<svg class="icon-sm icon" viewBox="0 0 24 24"><circle cx="8" cy="8" r="4"/><path d="M14 12a4 4 0 1 1 0 .01M6 12v4c0 1.1 1.8 2 4 2M18 12v4c0 1.1-1.8 2-4 2"/></svg>',
        clock: '<svg class="icon-sm icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
        bolt: '<svg class="icon-sm icon" viewBox="0 0 24 24"><path d="M13 3 4 14h7l-1 7 9-11h-7l1-7z"/></svg>',
        copy: '<svg class="icon-sm icon" viewBox="0 0 24 24"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>',
        edit: '<svg class="icon-sm icon" viewBox="0 0 24 24"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/></svg>',
        regen: '<svg class="icon-sm icon" viewBox="0 0 24 24"><path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/></svg>',
    };

    // Global error catcher — console only
    window.onerror = function (msg, url, lineNo) {
        console.error('Window Error:', msg, 'at', url, ':', lineNo);
        return false;
    };

    // ---- State ----
    let currentOrigin = window.location.origin;
    if (currentOrigin.includes('0.0.0.0')) {
        currentOrigin = currentOrigin.replace('0.0.0.0', 'localhost');
    }
    const defaultApiUrl = `${currentOrigin}/api/chat`;

    let state = {
        apiUrl: localStorage.getItem('apiUrl') || defaultApiUrl,
        model: localStorage.getItem('model') || 'gemma-local-model',
        systemPrompt: localStorage.getItem('systemPrompt') || 'You are a helpful AI assistant.',
        history: []
    };

    let modelPath = localStorage.getItem('modelPath') || '';
    let nCtx = parseInt(localStorage.getItem('nCtx')) || 2048;
    let nThreads = parseInt(localStorage.getItem('nThreads')) || 6;
    let nGpuLayers = parseInt(localStorage.getItem('nGpuLayers')) || 20;

    let nBatch = parseInt(localStorage.getItem('nBatch')) || 1024;
    let flashAttn = localStorage.getItem('flashAttn') !== 'false';
    let useMlock = localStorage.getItem('useMlock') !== 'false';
    let numa = localStorage.getItem('numa') === 'true';
    let kvQuant = localStorage.getItem('kvQuant') || 'none';
    let hwProfile = localStorage.getItem('hwProfile') || 'auto';

    let maxTokens = parseInt(localStorage.getItem('maxTokens')) || 512;
    let summarizeEnabled = localStorage.getItem('summarizeEnabled') === 'true';
    let temperature = parseFloat(localStorage.getItem('temperature')) || 0.7;
    let topP = parseFloat(localStorage.getItem('topP')) || 0.9;
    let topK = parseInt(localStorage.getItem('topK')) || 40;
    let repeatPenalty = parseFloat(localStorage.getItem('repeatPenalty')) || 1.1;

    let hwDetectionData = null;
    let hwDetectionFetched = false;
    let currentBrowserPath = '';
    let ignoreProfileChange = false;
    let abortController = null;
    let lastUserText = '';
    // Real tokenizer-based running total of conversation tokens (from server stats).
    let contextTokens = 0;
    // Whether a model is actually loaded on the server; gates the context meter.
    let modelLoaded = false;

    // ---- Initialize UI from state ----
    apiUrlInput.value = state.apiUrl;
    modelNameInput.value = state.model;
    systemPromptInput.value = state.systemPrompt;

    modelPathInput.value = modelPath;
    nCtxInput.value = nCtx;
    nThreadsInput.value = nThreads;
    nGpuLayersInput.value = nGpuLayers;

    nBatchInput.value = nBatch;
    flashAttnToggle.checked = flashAttn;
    mlockToggle.checked = useMlock;
    numaToggle.checked = numa;
    kvQuantSelect.value = kvQuant;
    hwProfileSelect.value = hwProfile;

    maxTokensInput.value = maxTokens;
    summarizeToggle.checked = summarizeEnabled;
    temperatureInput.value = temperature;
    temperatureValue.textContent = temperature.toFixed(2);
    topPInput.value = topP;
    topPValue.textContent = topP.toFixed(2);
    topKInput.value = topK;
    topKValue.textContent = topK;
    repeatPenaltyInput.value = repeatPenalty;
    repeatPenaltyValue.textContent = repeatPenalty.toFixed(2);
    // Start with no model shown; fetchModelStatus() sets the real value.
    updateModelPill('');
    updateContextIndicator();

    // ---- Slider live updates ----
    temperatureInput.addEventListener('input', () => { temperatureValue.textContent = parseFloat(temperatureInput.value).toFixed(2); });
    topPInput.addEventListener('input', () => { topPValue.textContent = parseFloat(topPInput.value).toFixed(2); });
    topKInput.addEventListener('input', () => { topKValue.textContent = topKInput.value; });
    repeatPenaltyInput.addEventListener('input', () => { repeatPenaltyValue.textContent = parseFloat(repeatPenaltyInput.value).toFixed(2); });

    // ---- Hardware flag inputs → auto-switch to "Custom" ----
    const hwInputs = [nGpuLayersInput, nThreadsInput, nBatchInput];
    const hwToggles = [flashAttnToggle, mlockToggle, numaToggle];
    hwInputs.forEach(input => input.addEventListener('change', () => { if (!ignoreProfileChange) hwProfileSelect.value = 'custom'; }));
    hwToggles.forEach(toggle => toggle.addEventListener('change', () => { if (!ignoreProfileChange) hwProfileSelect.value = 'custom'; }));
    kvQuantSelect.addEventListener('change', () => { if (!ignoreProfileChange) hwProfileSelect.value = 'custom'; });

    hwProfileSelect.addEventListener('change', () => {
        const selectedKey = hwProfileSelect.value;
        if (selectedKey === 'custom') return;
        if (selectedKey === 'auto') {
            if (hwDetectionData && hwDetectionData.recommended) applyProfileToUI(hwDetectionData.recommended);
            return;
        }
        if (hwDetectionData && hwDetectionData.profiles && hwDetectionData.profiles[selectedKey]) {
            const profile = hwDetectionData.profiles[selectedKey];
            const threads = hwDetectionData.recommended ? hwDetectionData.recommended.n_threads : 4;
            applyProfileToUI({ ...profile, n_threads: threads });
        }
    });

    // ============ UI behaviors ============
    collapseBtn?.addEventListener('click', () => app.classList.toggle('collapsed'));
    showBtn?.addEventListener('click', () => app.classList.toggle('collapsed'));

    function openOverlay(el) { el.classList.add('open'); }
    function closeOverlay(el) { el.classList.remove('open'); }

    settingsNavBtn?.addEventListener('click', () => openOverlay(settingsOverlay));
    closeSettingsBtn?.addEventListener('click', () => closeOverlay(settingsOverlay));
    settingsOverlay?.addEventListener('click', (e) => { if (e.target === settingsOverlay) closeOverlay(settingsOverlay); });

    modelPill?.addEventListener('click', (e) => { e.stopPropagation(); populateModelInfo(); openOverlay(modelOverlay); });
    modalClose?.addEventListener('click', () => closeOverlay(modelOverlay));
    modelOverlay?.addEventListener('click', (e) => { if (e.target === modelOverlay) closeOverlay(modelOverlay); });
    miOpenSettings?.addEventListener('click', () => { closeOverlay(modelOverlay); openOverlay(settingsOverlay); });

    ctxBtn?.addEventListener('click', (e) => { e.stopPropagation(); ctxPop.classList.toggle('hidden'); });
    document.addEventListener('click', (e) => {
        if (ctxPop && !ctxPop.contains(e.target) && !ctxBtn.contains(e.target)) ctxPop.classList.add('hidden');
    });

    newChatBtn?.addEventListener('click', () => {
        state.history = [];
        contextTokens = 0;
        chatColumn.querySelectorAll('.msg').forEach(m => m.remove());
        if (!document.getElementById('welcome')) {
            const w = document.createElement('div');
            w.className = 'empty';
            w.id = 'welcome';
            w.innerHTML = '<h1>Hello there</h1><p>Type a message or load a model to get started</p>';
            chatColumn.appendChild(w);
        }
        updateContextIndicator();
        fetch(`${currentOrigin}/api/reset-context`, { method: 'POST' }).catch(() => {});
    });

    // Settings tab switching
    document.querySelectorAll('.settings-nav .s-item').forEach(item => {
        item.addEventListener('click', () => {
            document.querySelectorAll('.settings-nav .s-item').forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            const page = item.dataset.page;
            document.querySelectorAll('.settings-page').forEach(p => p.classList.toggle('hidden', p.dataset.content !== page));
        });
    });

    // Esc closes overlays / popovers
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            ctxPop?.classList.add('hidden');
            closeOverlay(settingsOverlay);
            closeOverlay(modelOverlay);
            closeOverlay(fileBrowserModal);
        }
    });

    // Composer autosize
    function autosize() {
        userInput.style.height = 'auto';
        userInput.style.height = Math.min(userInput.scrollHeight, 200) + 'px';
    }
    userInput.addEventListener('input', autosize);

    // ============ Event listeners: chat ============
    sendBtn.addEventListener('click', () => {
        if (app.classList.contains('generating')) { stopGenerating(); return; }
        handleSendMessage();
    });
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!app.classList.contains('generating')) handleSendMessage();
        }
    });

    // ============ Settings save / reset ============
    saveSettingsBtn.addEventListener('click', () => {
        state.apiUrl = apiUrlInput.value.trim();
        state.model = modelNameInput.value.trim();
        state.systemPrompt = systemPromptInput.value.trim();
        localStorage.setItem('apiUrl', state.apiUrl);
        localStorage.setItem('model', state.model);
        localStorage.setItem('systemPrompt', state.systemPrompt);

        modelPath = modelPathInput.value.trim();
        nCtx = parseInt(nCtxInput.value) || 2048;
        nThreads = parseInt(nThreadsInput.value) || 6;
        nGpuLayers = parseInt(nGpuLayersInput.value) || 20;
        localStorage.setItem('modelPath', modelPath);
        localStorage.setItem('nCtx', nCtx.toString());
        localStorage.setItem('nThreads', nThreads.toString());
        localStorage.setItem('nGpuLayers', nGpuLayers.toString());

        nBatch = parseInt(nBatchInput.value) || 1024;
        flashAttn = flashAttnToggle.checked;
        useMlock = mlockToggle.checked;
        numa = numaToggle.checked;
        kvQuant = kvQuantSelect.value;
        hwProfile = hwProfileSelect.value;
        localStorage.setItem('nBatch', nBatch.toString());
        localStorage.setItem('flashAttn', flashAttn.toString());
        localStorage.setItem('useMlock', useMlock.toString());
        localStorage.setItem('numa', numa.toString());
        localStorage.setItem('kvQuant', kvQuant);
        localStorage.setItem('hwProfile', hwProfile);

        maxTokens = parseInt(maxTokensInput.value) || 512;
        summarizeEnabled = summarizeToggle.checked;
        temperature = parseFloat(temperatureInput.value) || 0.7;
        topP = parseFloat(topPInput.value) || 0.9;
        topK = parseInt(topKInput.value) || 40;
        repeatPenalty = parseFloat(repeatPenaltyInput.value) || 1.1;
        localStorage.setItem('maxTokens', maxTokens.toString());
        localStorage.setItem('summarizeEnabled', summarizeEnabled.toString());
        localStorage.setItem('temperature', temperature.toString());
        localStorage.setItem('topP', topP.toString());
        localStorage.setItem('topK', topK.toString());
        localStorage.setItem('repeatPenalty', repeatPenalty.toString());

        updateModelPill(state.model);
        updateContextIndicator();
        closeOverlay(settingsOverlay);
        checkConnection();
    });

    resetSettingsBtn.addEventListener('click', () => {
        if (confirm('Are you sure you want to reset all settings to defaults?')) {
            localStorage.clear();
            window.location.reload();
        }
    });

    // ============ File browser listeners ============
    pickModelBtn.addEventListener('click', () => openFileBrowser());
    loadModelBtn.addEventListener('click', () => loadModel());
    browserGoUpBtn.addEventListener('click', () => navigateUp());
    closeBrowserBtn.addEventListener('click', () => closeOverlay(fileBrowserModal));
    fileBrowserModal.addEventListener('click', (e) => { if (e.target === fileBrowserModal) closeOverlay(fileBrowserModal); });

    // ============ Startup ============
    checkConnection();
    fetchModelStatus();
    fetchHardwareProfile();

    // ============ Hardware profile ============
    function applyProfileToUI(profile) {
        ignoreProfileChange = true;
        if (profile.n_gpu_layers != null) nGpuLayersInput.value = profile.n_gpu_layers;
        if (profile.n_threads != null) nThreadsInput.value = profile.n_threads;
        if (profile.n_batch != null) nBatchInput.value = profile.n_batch;
        if (profile.flash_attn != null) flashAttnToggle.checked = profile.flash_attn;
        if (profile.use_mlock != null) mlockToggle.checked = profile.use_mlock;
        if (profile.numa != null) numaToggle.checked = profile.numa;
        if (profile.type_k != null && profile.type_k > 0) kvQuantSelect.value = 'q8_0';
        else kvQuantSelect.value = 'none';
        ignoreProfileChange = false;
    }

    async function fetchHardwareProfile() {
        if (hwDetectionFetched) return;
        try {
            const response = await fetch(`${currentOrigin}/api/hardware-profile`);
            if (!response.ok) return;
            hwDetectionData = await response.json();
            hwDetectionFetched = true;

            const hw = hwDetectionData.hardware;
            if (hw) {
                hwDetectionBanner.style.display = 'block';
                let parts = [];
                if (hw.cpu_brand && hw.cpu_brand !== 'unknown') parts.push(hw.cpu_brand);
                if (hw.physical_cores) parts.push(`${hw.physical_cores}P/${hw.logical_cores}L cores`);
                if (hw.ram_total_gb) parts.push(`${hw.ram_total_gb} GB RAM`);
                parts.push(hw.gpu ? (hw.gpu.name || 'GPU detected') : 'No GPU');
                hwBannerText.textContent = parts.join(' · ');

                let flags = [];
                if (hw.has_avx2 === true) flags.push('AVX2 ✓'); else if (hw.has_avx2 === false) flags.push('AVX2 ✗');
                if (hw.has_avx512 === true) flags.push('AVX-512 ✓');
                if (hw.has_fma === true) flags.push('FMA ✓');
                if (hw.has_f16c === true) flags.push('F16C ✓');
                if (flags.length) { hwCpuFlags.style.display = 'block'; hwCpuFlags.textContent = flags.join('  |  '); }
            }
            if (hwProfile === 'auto' && hwDetectionData.recommended) {
                hwProfileSelect.value = 'auto';
                applyProfileToUI(hwDetectionData.recommended);
            }
        } catch (error) {
            console.log('Hardware detection not available:', error.message);
        }
    }

    // ============ Connection ============
    function setConn(kind) {
        statusIndicator.className = 'status-indicator';
        if (kind === 'connecting') {
            connText.textContent = 'Connecting…';
            connWrap.title = 'Checking connection...';
        } else if (kind === 'connected') {
            statusIndicator.classList.add('connected');
            connText.textContent = 'Model loaded';
            connWrap.title = 'Server reachable · model loaded';
        } else if (kind === 'idle') {
            statusIndicator.classList.add('idle');
            connText.textContent = 'No model loaded';
            connWrap.title = 'Server reachable · no model loaded';
        } else {
            statusIndicator.classList.add('error');
            connText.textContent = 'Disconnected';
            connWrap.title = 'Connection failed';
        }
    }

    async function checkConnection() {
        setConn('connecting');
        try {
            const tagsUrl = state.apiUrl.startsWith('http')
                ? `${state.apiUrl.replace('/api/chat', '')}/api/tags`
                : '/api/tags';
            const response = await fetch(tagsUrl).catch(() => ({ ok: false }));
            if (!response.ok) { setConn('error'); return; }

            // Server is reachable — reflect whether a model is actually loaded.
            let loaded = false;
            try {
                const ms = await fetch(`${currentOrigin}/api/model-status`);
                if (ms.ok) { const d = await ms.json(); loaded = d.status === 'loaded'; }
            } catch (e) { /* reachable but status unknown */ }
            setConn(loaded ? 'connected' : 'idle');
        } catch (error) {
            setConn('error');
        }
    }

    // ============ Chat send ============
    function stopGenerating() {
        if (abortController) { try { abortController.abort(); } catch (e) {} }
        app.classList.remove('generating');
    }

    async function handleSendMessage() {
        const text = userInput.value.trim();
        if (!text) return;
        lastUserText = text;

        userInput.value = '';
        userInput.style.height = 'auto';

        const userEl = addMessage(text, 'user');
        const aiEl = addMessage('Thinking...', 'ai', true);
        let aiResponseText = '';

        const messages = [
            { role: 'system', content: state.systemPrompt },
            ...state.history,
            { role: 'user', content: text }
        ];

        if (state.apiUrl.includes('11434')) {
            state.apiUrl = 'http://localhost:8080/api/chat';
            localStorage.setItem('apiUrl', state.apiUrl);
            apiUrlInput.value = state.apiUrl;
        }

        app.classList.add('generating');
        abortController = new AbortController();

        try {
            const response = await fetch(state.apiUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model: state.model,
                    messages,
                    stream: true,
                    max_tokens: maxTokens,
                    summarize: summarizeEnabled,
                    temperature, top_p: topP, top_k: topK, repeat_penalty: repeatPenalty
                }),
                signal: abortController.signal
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || errorData.error || `API Error: ${response.statusText}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let stats = null;
            updateMessage(aiEl, '');

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop();
                for (const line of lines) {
                    if (!line.trim()) continue;
                    try {
                        const json = JSON.parse(line);
                        if (json.message && json.message.content) {
                            aiResponseText += json.message.content;
                            updateMessage(aiEl, aiResponseText);
                        }
                        if (json.stats) stats = json.stats;
                        if (json.error) throw new Error(json.error);
                    } catch (e) { /* partial line */ }
                }
            }
            if (buffer.trim()) {
                try {
                    const json = JSON.parse(buffer);
                    if (json.message && json.message.content) {
                        aiResponseText += json.message.content;
                        updateMessage(aiEl, aiResponseText);
                    }
                    if (json.stats) stats = json.stats;
                } catch (e) {}
            }

            state.history.push({ role: 'user', content: text });
            state.history.push({ role: 'assistant', content: aiResponseText });

            if (stats) {
                renderStats(userEl, aiEl, stats);
                // Accumulate real (tokenizer-based) token counts for context usage.
                contextTokens += (stats.user_tokens || 0) + (stats.completion_tokens || 0);
            }
            updateContextIndicator();
        } catch (error) {
            if (error.name === 'AbortError') {
                updateMessage(aiEl, aiResponseText + '\n\n_(stopped)_');
            } else {
                console.error('Chat error:', error);
                updateMessage(aiEl, `**Error:** ${error.message}\n\nPlease check your settings and ensure your local LLM is running.`);
            }
        } finally {
            app.classList.remove('generating');
            abortController = null;
            userInput.focus();
        }
    }

    // ============ Message rendering ============
    function addMessage(text, sender, isLoading = false) {
        const welcome = document.getElementById('welcome');
        if (welcome) welcome.remove();

        const el = document.createElement('div');
        el.className = `msg ${sender === 'user' ? 'user' : 'assistant'}`;

        if (sender === 'user') {
            const bubble = document.createElement('div');
            bubble.className = 'bubble';
            bubble.textContent = text;
            el.appendChild(bubble);

            const actions = document.createElement('div');
            actions.className = 'action-row right';
            actions.innerHTML = `<button class="act" title="Copy">${ICON.copy}</button><button class="act" title="Edit">${ICON.edit}</button>`;
            actions.querySelector('[title="Copy"]').addEventListener('click', () => copyText(text));
            actions.querySelector('[title="Edit"]').addEventListener('click', () => editUserMessage(el, text));
            el.appendChild(actions);
        } else {
            const body = document.createElement('div');
            body.className = 'md-body';
            if (isLoading) { body.classList.add('loading'); body.textContent = text; }
            else { body.innerHTML = marked.parse(text); highlight(body); }
            el.appendChild(body);

            const actions = document.createElement('div');
            actions.className = 'action-row';
            actions.innerHTML = `<button class="act" title="Copy">${ICON.copy}</button>`;
            actions.querySelector('[title="Copy"]').addEventListener('click', () => copyText(body.textContent));
            el.appendChild(actions);
        }

        chatColumn.appendChild(el);
        scrollToBottom(true);
        return el;
    }

    function updateMessage(el, text) {
        const body = el.querySelector('.md-body');
        if (!body) return;
        body.classList.remove('loading');
        body.innerHTML = marked.parse(text);
        highlight(body);
        scrollToBottom();
    }

    function highlight(container) {
        container.querySelectorAll('pre code').forEach(block => {
            try { hljs.highlightElement(block); } catch (e) {}
        });
    }

    function copyText(text) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text)
                .then(() => showToast('Copied'))
                .catch(() => fallbackCopy(text));
        } else {
            fallbackCopy(text);
        }
    }

    function fallbackCopy(text) {
        try {
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
            showToast('Copied');
        } catch (e) {
            showToast('Copy failed');
        }
    }

    let toastTimer = null;
    function showToast(msg) {
        const t = document.getElementById('toast');
        if (!t) return;
        t.innerHTML = `${ICON.copy}<span>${escapeHtml(msg)}</span>`;
        t.classList.add('show');
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => t.classList.remove('show'), 1400);
    }

    // ============ End-of-answer stats ============
    function renderStats(userEl, aiEl, stats) {
        // User message: token count meta row
        if (userEl && stats.user_tokens != null && !userEl.querySelector('.meta-row')) {
            const meta = document.createElement('div');
            meta.className = 'meta-row right';
            meta.innerHTML = `<span class="stat">${ICON.token}${stats.user_tokens} tokens</span>`;
            const bubble = userEl.querySelector('.bubble');
            bubble.insertAdjacentElement('afterend', meta);
            userEl.dataset.tokens = stats.user_tokens;
        }
        // Assistant message: model pills + end stats
        if (aiEl && !aiEl.querySelector('.answer-footer')) {
            const footer = document.createElement('div');
            footer.className = 'answer-footer';
            const modelName = state.model || 'model';
            footer.innerHTML =
                `<div class="pills"><span class="pill"><span class="dot"></span>${escapeHtml(modelName)}</span></div>` +
                `<div class="end-stats">` +
                `<span class="stat">${ICON.token}${stats.completion_tokens} tokens</span>` +
                `<span class="stat">${ICON.clock}${stats.elapsed_s}s</span>` +
                `<span class="stat">${ICON.bolt}${stats.tokens_per_s} t/s</span>` +
                `</div>`;
            const body = aiEl.querySelector('.md-body');
            body.insertAdjacentElement('afterend', footer);
            aiEl.dataset.tokens = stats.completion_tokens;
        }
    }

    // Edit a user message: remove it and everything after it from the chat and
    // history, then drop the text back into the composer so it can be resent.
    function editUserMessage(userEl, text) {
        if (app.classList.contains('generating')) return;
        const msgs = Array.from(chatColumn.querySelectorAll('.msg'));
        const idx = msgs.indexOf(userEl);
        if (idx === -1) return;
        for (let i = msgs.length - 1; i >= idx; i--) msgs[i].remove();
        if (idx < state.history.length) state.history.splice(idx);
        contextTokens = 0;
        chatColumn.querySelectorAll('.msg').forEach(m => { contextTokens += parseInt(m.dataset.tokens || '0', 10) || 0; });
        updateContextIndicator();
        userInput.value = text;
        autosize();
        userInput.focus();
    }

    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }

    // ============ Context indicator (real tokenizer counts) ============
    // `contextTokens` is the running total of user + completion tokens reported
    // by the server (using the model's actual tokenizer). No estimation.
    function updateContextIndicator() {
        if (!modelLoaded) {
            // No model loaded — report 0 / 0 rather than a default context size.
            if (ctxVal) ctxVal.textContent = '0 / 0';
            if (ctxBarFill) ctxBarFill.style.width = '0%';
            if (ctxArc) {
                ctxArc.style.strokeDasharray = `${RING_CIRCUMFERENCE}`;
                ctxArc.style.strokeDashoffset = `${RING_CIRCUMFERENCE}`;
            }
            if (ctxCircle) { ctxCircle.classList.remove('warn', 'full'); }
            return;
        }
        const total = nCtx || 2048;
        const used = Math.min(contextTokens, total);
        const pct = total > 0 ? Math.min(100, (used / total) * 100) : 0;

        if (ctxVal) ctxVal.textContent = `${used.toLocaleString()} / ${formatK(total)}`;
        if (ctxBarFill) ctxBarFill.style.width = pct + '%';

        if (ctxArc) {
            ctxArc.style.strokeDasharray = `${RING_CIRCUMFERENCE}`;
            ctxArc.style.strokeDashoffset = `${RING_CIRCUMFERENCE * (1 - pct / 100)}`;
        }
        if (ctxCircle) {
            ctxCircle.classList.toggle('warn', pct >= 75 && pct < 90);
            ctxCircle.classList.toggle('full', pct >= 90);
        }
    }
    function formatK(n) { return n >= 1000 ? (n / 1000).toFixed(n % 1000 === 0 ? 0 : 2) + 'K' : String(n); }

    // ============ Scroll ============
    let userScrolledUp = false;
    chatArea.addEventListener('scroll', () => {
        const atBottom = chatArea.scrollHeight - chatArea.scrollTop - chatArea.clientHeight < 100;
        userScrolledUp = !atBottom;
    });
    function scrollToBottom(force = false) {
        if (force || !userScrolledUp) chatArea.scrollTop = chatArea.scrollHeight;
    }

    // ============ File browser ============
    async function openFileBrowser(path) {
        openOverlay(fileBrowserModal);
        await fetchBrowserContents(path || currentBrowserPath || '');
    }
    async function fetchBrowserContents(path) {
        browserEntries.innerHTML = '<div class="browser-loading">Loading...</div>';
        try {
            const url = path ? `${currentOrigin}/api/browse?path=${encodeURIComponent(path)}` : `${currentOrigin}/api/browse`;
            const response = await fetch(url);
            if (!response.ok) throw new Error(`Failed to browse: ${response.statusText}`);
            const data = await response.json();
            currentBrowserPath = data.current_path || '';
            browserCurrentPath.textContent = currentBrowserPath || '/';
            renderBrowserEntries(data.entries || []);
        } catch (error) {
            browserEntries.innerHTML = `<div class="browser-error">Error: ${error.message}</div>`;
        }
    }
    function renderBrowserEntries(entries) {
        browserEntries.innerHTML = '';
        if (!entries.length) { browserEntries.innerHTML = '<div class="browser-empty">No .gguf files or directories found</div>'; return; }
        entries.forEach(entry => {
            const div = document.createElement('div');
            div.className = 'browser-entry';
            const icon = entry.type === 'dir' ? '📁' : '📄';
            const size = entry.type === 'file' && entry.size != null ? formatFileSize(entry.size) : '';
            div.innerHTML = `<span class="entry-icon">${icon}</span><span class="entry-name">${escapeHtml(entry.name)}</span>${size ? `<span class="entry-size">${size}</span>` : ''}`;
            if (entry.type === 'dir') { div.classList.add('browser-entry-dir'); div.addEventListener('click', () => navigateToDirectory(entry.name)); }
            else { div.classList.add('browser-entry-file'); div.addEventListener('click', () => selectModelFile(entry.name)); }
            browserEntries.appendChild(div);
        });
    }
    function navigateToDirectory(dirName) {
        const newPath = currentBrowserPath ? `${currentBrowserPath}/${dirName}`.replace(/\/\//g, '/') : dirName;
        fetchBrowserContents(newPath);
    }
    function navigateUp() {
        if (!currentBrowserPath || currentBrowserPath === '/' || currentBrowserPath === 'C:\\') return;
        let parentPath;
        if (currentBrowserPath.includes('\\')) {
            const parts = currentBrowserPath.split('\\'); parts.pop();
            parentPath = parts.join('\\') || parts[0] + '\\';
        } else {
            const parts = currentBrowserPath.split('/'); parts.pop();
            parentPath = parts.join('/') || '/';
        }
        fetchBrowserContents(parentPath);
    }
    function selectModelFile(fileName) {
        const fullPath = currentBrowserPath ? `${currentBrowserPath}/${fileName}`.replace(/\/\//g, '/') : fileName;
        const normalizedPath = currentBrowserPath.includes('\\') ? `${currentBrowserPath}\\${fileName}` : fullPath;
        modelPathInput.value = normalizedPath;
        modelPath = normalizedPath;
        localStorage.setItem('modelPath', modelPath);
        closeOverlay(fileBrowserModal);
    }
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024, sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    // Model-spec formatters
    function formatParams(n) {
        if (n == null) return '—';
        if (n >= 1e12) return (n / 1e12).toFixed(2) + 'T';
        if (n >= 1e9) return (n / 1e9).toFixed(2) + 'B';
        if (n >= 1e6) return (n / 1e6).toFixed(2) + 'M';
        if (n >= 1e3) return (n / 1e3).toFixed(2) + 'K';
        return String(n);
    }
    function formatBytes(bytes) {
        if (bytes == null) return '—';
        if (bytes === 0) return '0 B';
        const k = 1024, sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return (bytes / Math.pow(k, i)).toFixed(2) + ' ' + sizes[i];
    }

    // ============ Model loading ============
    async function loadModel() {
        const path = modelPathInput.value.trim();
        if (!path) { modelStatusText.textContent = 'Error: No model path selected'; modelStatusText.className = 'model-status error'; return; }
        let typeK = null, typeV = null;
        if (kvQuantSelect.value === 'q8_0') { typeK = 8; typeV = 8; }
        const params = {
            model_path: path,
            n_ctx: parseInt(nCtxInput.value) || 2048,
            n_threads: parseInt(nThreadsInput.value) || 6,
            n_gpu_layers: parseInt(nGpuLayersInput.value) || 20,
            flash_attn: flashAttnToggle.checked,
            use_mlock: mlockToggle.checked,
            numa: numaToggle.checked,
            n_batch: parseInt(nBatchInput.value) || 1024,
            type_k: typeK, type_v: typeV,
        };
        loadModelBtn.disabled = true;
        loadModelBtn.textContent = 'Loading...';
        modelStatusText.textContent = 'Loading model...';
        modelStatusText.className = 'model-status loading';
        try {
            const response = await fetch(`${currentOrigin}/api/load-model`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(params)
            });
            const data = await response.json();
            if (response.ok && data.success) {
                const modelName = path.split(/[/\\]/).pop().replace(/\.gguf$/i, '');
                modelStatusText.textContent = `Loaded: ${modelName}`;
                modelStatusText.className = 'model-status loaded';
                modelNameInput.value = modelName;
                state.model = modelName;
                localStorage.setItem('model', modelName);
                localStorage.setItem('modelPath', path);
                localStorage.setItem('nCtx', params.n_ctx.toString());
                localStorage.setItem('nThreads', params.n_threads.toString());
                localStorage.setItem('nGpuLayers', params.n_gpu_layers.toString());
                localStorage.setItem('nBatch', params.n_batch.toString());
                localStorage.setItem('flashAttn', params.flash_attn.toString());
                localStorage.setItem('useMlock', params.use_mlock.toString());
                localStorage.setItem('numa', params.numa.toString());
                localStorage.setItem('kvQuant', kvQuantSelect.value);
                localStorage.setItem('hwProfile', hwProfileSelect.value);
                nCtx = params.n_ctx;
                modelLoaded = true;
                updateModelPill(modelName);
                updateContextIndicator();
                fetchModelStatus();
                checkConnection();
            } else {
                const errorMsg = data.detail || data.error || 'Failed to load model';
                modelStatusText.textContent = `Error: ${errorMsg}`;
                modelStatusText.className = 'model-status error';
            }
        } catch (error) {
            modelStatusText.textContent = `Error: ${error.message}`;
            modelStatusText.className = 'model-status error';
        } finally {
            loadModelBtn.disabled = false;
            loadModelBtn.textContent = 'Load Model';
        }
    }

    async function fetchModelStatus() {
        try {
            const response = await fetch(`${currentOrigin}/api/model-status`);
            if (!response.ok) return;
            const data = await response.json();
            modelLoaded = data.status === 'loaded' && !!data.model_path;

            if (data.status === 'loaded' && data.model_path) {
                const modelName = data.model_path.split(/[/\\]/).pop().replace(/\.gguf$/i, '');
                modelStatusText.textContent = `Loaded: ${modelName}`;
                modelStatusText.className = 'model-status loaded';
                modelPathInput.value = data.model_path;
                modelPath = data.model_path;
                localStorage.setItem('modelPath', modelPath);
                modelNameInput.value = modelName;
                state.model = modelName;
                localStorage.setItem('model', modelName);
                updateModelPill(modelName);
            } else if (data.status === 'loading') {
                modelStatusText.textContent = 'Loading model...';
                modelStatusText.className = 'model-status loading';
                updateModelPill('');
            } else if (data.status === 'error') {
                modelStatusText.textContent = 'Error loading model';
                modelStatusText.className = 'model-status error';
                updateModelPill('');
            } else {
                modelStatusText.textContent = 'No model loaded';
                modelStatusText.className = 'model-status';
                updateModelPill('');
            }

            if (data.n_ctx) { nCtxInput.value = data.n_ctx; nCtx = data.n_ctx; }
            if (data.n_threads) { nThreadsInput.value = data.n_threads; nThreads = data.n_threads; }
            if (data.n_gpu_layers != null) { nGpuLayersInput.value = data.n_gpu_layers; nGpuLayers = data.n_gpu_layers; }
            if (data.n_batch) { nBatchInput.value = data.n_batch; nBatch = data.n_batch; }
            if (data.flash_attn != null) { flashAttnToggle.checked = data.flash_attn; flashAttn = data.flash_attn; }
            if (data.use_mlock != null) { mlockToggle.checked = data.use_mlock; useMlock = data.use_mlock; }
            if (data.numa != null) { numaToggle.checked = data.numa; numa = data.numa; }

            window.__modelState = data;
            updateContextIndicator();
        } catch (error) {
            console.log('Could not fetch model status:', error.message);
        }
    }

    // ============ Model pill + info modal ============
    function updateModelPill(name) {
        modelPill.classList.remove('hidden');
        modelPillName.textContent = name && name.trim() ? name : 'No model loaded';
    }

    function populateModelInfo() {
        const s = window.__modelState || {};
        const loaded = s.status === 'loaded' && s.model_path;

        if (!loaded) {
            // Nothing loaded — don't show defaults as if they were configured.
            mi.model.textContent = 'No model loaded';
            mi.path.textContent = '—';
            mi.status.textContent = s.status || 'not loaded';
            mi.params.textContent = '—';
            mi.size.textContent = '—';
            mi.trainctx.textContent = '—';
            mi.embd.textContent = '—';
            mi.vocab.textContent = '—';
            mi.ctx.textContent = '—';
            mi.gpu.textContent = '—';
            mi.threads.textContent = '—';
            mi.batch.textContent = '—';
            mi.flash.textContent = '—';
            mi.mlock.textContent = '—';
            mi.numa.textContent = '—';
            return;
        }

        const name = s.model_path.split(/[/\\]/).pop().replace(/\.gguf$/i, '');
        mi.model.textContent = name;
        mi.path.textContent = s.model_path;
        mi.status.textContent = s.status;
        mi.params.textContent = formatParams(s.n_params);
        mi.size.textContent = formatBytes(s.file_size_bytes);
        mi.trainctx.textContent = s.training_ctx != null ? `${s.training_ctx.toLocaleString()} tokens` : '—';
        mi.embd.textContent = s.n_embd != null ? s.n_embd.toLocaleString() : '—';
        mi.vocab.textContent = s.n_vocab != null ? `${s.n_vocab.toLocaleString()} tokens` : '—';
        mi.ctx.textContent = s.n_ctx ? `${s.n_ctx.toLocaleString()} tokens` : '—';
        mi.gpu.textContent = s.n_gpu_layers != null ? s.n_gpu_layers : '—';
        mi.threads.textContent = s.n_threads != null ? s.n_threads : '—';
        mi.batch.textContent = s.n_batch != null ? s.n_batch : '—';
        mi.flash.textContent = s.flash_attn != null ? (s.flash_attn ? 'On' : 'Off') : '—';
        mi.mlock.textContent = s.use_mlock != null ? (s.use_mlock ? 'On' : 'Off') : '—';
        mi.numa.textContent = s.numa != null ? (s.numa ? 'On' : 'Off') : '—';
    }
});
