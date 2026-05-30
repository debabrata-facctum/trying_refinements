document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const chatArea = document.getElementById('chat-area');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const settingsBtn = document.getElementById('settings-btn');
    const closeSettingsBtn = document.getElementById('close-settings');
    const saveSettingsBtn = document.getElementById('save-settings');
    const settingsModal = document.getElementById('settings-modal');
    const statusIndicator = document.getElementById('status-indicator');

    // Settings Inputs
    const apiUrlInput = document.getElementById('api-url');
    const modelNameInput = document.getElementById('model-name');
    const systemPromptInput = document.getElementById('system-prompt');
    const resetSettingsBtn = document.getElementById('reset-settings');

    // Model Picker DOM Elements
    const modelPathInput = document.getElementById('model-path-input');
    const pickModelBtn = document.getElementById('pick-model-btn');
    const nCtxInput = document.getElementById('n-ctx-input');
    const nThreadsInput = document.getElementById('n-threads-input');
    const nGpuLayersInput = document.getElementById('n-gpu-layers-input');
    const loadModelBtn = document.getElementById('load-model-btn');
    const modelStatusText = document.getElementById('model-status-text');
    const fileBrowserModal = document.getElementById('file-browser-modal');
    const browserCurrentPath = document.getElementById('browser-current-path');
    const browserEntries = document.getElementById('browser-entries');
    const browserGoUpBtn = document.getElementById('browser-go-up-btn');
    const closeBrowserBtn = document.getElementById('close-browser-btn');

    // Inference Settings DOM Elements
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

    // Global Error Catcher — log to console only, don't pollute the chat
    window.onerror = function (msg, url, lineNo, columnNo, error) {
        console.error('Window Error:', msg, 'at', url, ':', lineNo);
        return false;
    };

    // State
    // Some browsers block requests to 0.0.0.0, so we convert it to localhost
    let currentOrigin = window.location.origin;
    if (currentOrigin.includes('0.0.0.0')) {
        currentOrigin = currentOrigin.replace('0.0.0.0', 'localhost');
    }

    const defaultApiUrl = `${currentOrigin}/api/chat`;
    let state = {
        // Use the current origin to ensure we hit the same server
        apiUrl: localStorage.getItem('apiUrl') || defaultApiUrl,
        model: localStorage.getItem('model') || 'gemma-local-model',
        systemPrompt: localStorage.getItem('systemPrompt') || 'You are a helpful AI assistant.',
        history: []
    };

    // Model settings state with localStorage persistence
    let modelPath = localStorage.getItem('modelPath') || '';
    let nCtx = parseInt(localStorage.getItem('nCtx')) || 2048;
    let nThreads = parseInt(localStorage.getItem('nThreads')) || 6;
    let nGpuLayers = parseInt(localStorage.getItem('nGpuLayers')) || 20;

    // Inference settings
    let maxTokens = parseInt(localStorage.getItem('maxTokens')) || 512;
    let summarizeEnabled = localStorage.getItem('summarizeEnabled') === 'true';
    let temperature = parseFloat(localStorage.getItem('temperature')) || 0.7;
    let topP = parseFloat(localStorage.getItem('topP')) || 0.9;
    let topK = parseInt(localStorage.getItem('topK')) || 40;
    let repeatPenalty = parseFloat(localStorage.getItem('repeatPenalty')) || 1.1;

    // File browser state
    let currentBrowserPath = '';

    // Initialize UI
    apiUrlInput.value = state.apiUrl;
    modelNameInput.value = state.model;
    systemPromptInput.value = state.systemPrompt;

    // Initialize model settings UI
    modelPathInput.value = modelPath;
    nCtxInput.value = nCtx;
    nThreadsInput.value = nThreads;
    nGpuLayersInput.value = nGpuLayers;

    // Initialize inference settings UI
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

    // Slider live-update listeners
    temperatureInput.addEventListener('input', () => {
        temperatureValue.textContent = parseFloat(temperatureInput.value).toFixed(2);
    });
    topPInput.addEventListener('input', () => {
        topPValue.textContent = parseFloat(topPInput.value).toFixed(2);
    });
    topKInput.addEventListener('input', () => {
        topKValue.textContent = topKInput.value;
    });
    repeatPenaltyInput.addEventListener('input', () => {
        repeatPenaltyValue.textContent = parseFloat(repeatPenaltyInput.value).toFixed(2);
    });

    // Check connection on load
    checkConnection();

    // Fetch current model status on page load
    fetchModelStatus();

    // Event Listeners
    sendBtn.addEventListener('click', handleSendMessage);

    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    });

    userInput.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
        if (this.value === '') this.style.height = 'auto';
    });

    settingsBtn.addEventListener('click', () => {
        settingsModal.classList.add('active');
    });

    closeSettingsBtn.addEventListener('click', () => {
        settingsModal.classList.remove('active');
    });

    settingsModal.addEventListener('click', (e) => {
        if (e.target === settingsModal) {
            settingsModal.classList.remove('active');
        }
    });

    saveSettingsBtn.addEventListener('click', () => {
        state.apiUrl = apiUrlInput.value.trim();
        state.model = modelNameInput.value.trim();
        state.systemPrompt = systemPromptInput.value.trim();

        localStorage.setItem('apiUrl', state.apiUrl);
        localStorage.setItem('model', state.model);
        localStorage.setItem('systemPrompt', state.systemPrompt);

        // Save model parameters
        modelPath = modelPathInput.value.trim();
        nCtx = parseInt(nCtxInput.value) || 2048;
        nThreads = parseInt(nThreadsInput.value) || 6;
        nGpuLayers = parseInt(nGpuLayersInput.value) || 20;

        localStorage.setItem('modelPath', modelPath);
        localStorage.setItem('nCtx', nCtx.toString());
        localStorage.setItem('nThreads', nThreads.toString());
        localStorage.setItem('nGpuLayers', nGpuLayers.toString());

        // Save inference settings
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

        settingsModal.classList.remove('active');
        checkConnection();
    });

    if (resetSettingsBtn) {
        resetSettingsBtn.addEventListener('click', () => {
            if (confirm('Are you sure you want to reset all settings to defaults?')) {
                localStorage.clear();
                window.location.reload();
            }
        });
    }

    // Model Picker Event Listeners
    pickModelBtn.addEventListener('click', () => {
        openFileBrowser();
    });

    loadModelBtn.addEventListener('click', () => {
        loadModel();
    });

    browserGoUpBtn.addEventListener('click', () => {
        navigateUp();
    });

    closeBrowserBtn.addEventListener('click', () => {
        fileBrowserModal.classList.remove('active');
    });

    fileBrowserModal.addEventListener('click', (e) => {
        if (e.target === fileBrowserModal) {
            fileBrowserModal.classList.remove('active');
        }
    });

    // Functions
    async function checkConnection() {
        statusIndicator.className = 'status-indicator';
        statusIndicator.title = 'Checking connection...';

        try {
            // If apiUrl is a relative path like '/api/chat', we need to make it absolute for the connection check
            // or just fetch it directly.
            let tagsUrl;
            if (state.apiUrl.startsWith('http')) {
                const baseUrl = state.apiUrl.replace('/api/chat', '');
                tagsUrl = `${baseUrl}/api/tags`;
            } else {
                tagsUrl = '/api/tags';
            }

            console.log('Checking connection to:', tagsUrl);
            const response = await fetch(tagsUrl).catch(e => {
                console.error('Fetch error during checkConnection:', e);
                return { ok: false, status: 'NETWORK_ERROR' };
            });
            console.log('Connection check status:', response.status);

            if (response.ok) {
                statusIndicator.classList.add('connected');
                statusIndicator.title = 'Connected to Local LLM';
            } else {
                statusIndicator.classList.add('error');
                statusIndicator.title = 'Connection failed';
            }
        } catch (error) {
            statusIndicator.classList.add('error');
            statusIndicator.title = 'Connection failed';
            console.error('Connection check failed:', error);
        }
    }

    async function handleSendMessage() {
        const text = userInput.value.trim();
        if (!text || sendBtn.disabled) return;

        // Disable UI
        userInput.disabled = true;
        sendBtn.disabled = true;
        sendBtn.style.opacity = '0.5';

        // Clear input
        userInput.value = '';
        userInput.style.height = 'auto';

        // Add user message
        addMessage(text, 'user');

        // Prepare context/history
        const messages = [
            { role: 'system', content: state.systemPrompt },
            ...state.history,
            { role: 'user', content: text }
        ];

        // Create AI message placeholder
        const aiMessageId = addMessage('Thinking...', 'ai', true);
        let aiResponseText = '';

        console.log('--- CHAT ATTEMPT ---');
        console.log('Fetching from URL:', state.apiUrl);
        if (state.apiUrl.includes('11434')) {
            alert('Wait! Your settings are still pointing to port 11434 (Ollama). I am resetting it to 8080 for you now. Please click Send again.');
            state.apiUrl = 'http://localhost:8080/api/chat';
            localStorage.setItem('apiUrl', state.apiUrl);
            apiUrlInput.value = state.apiUrl;
            userInput.disabled = false;
            sendBtn.disabled = false;
            sendBtn.style.opacity = '1';
            return;
        }

        console.log('Request body:', {
            model: state.model,
            messages: messages,
            stream: true,
            max_tokens: maxTokens,
            summarize: summarizeEnabled,
            temperature: temperature,
            top_p: topP,
            top_k: topK,
            repeat_penalty: repeatPenalty
        });

        try {
            const response = await fetch(state.apiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    model: state.model,
                    messages: messages,
                    stream: true,
                    max_tokens: maxTokens,
                    summarize: summarizeEnabled,
                    temperature: temperature,
                    top_p: topP,
                    top_k: topK,
                    repeat_penalty: repeatPenalty
                })
            });

            console.log('Response status:', response.status);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `API Error: ${response.statusText}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            // Clear "Thinking..."
            updateMessage(aiMessageId, '');

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');

                // Keep the last partial line in the buffer
                buffer = lines.pop();

                for (const line of lines) {
                    if (!line.trim()) continue;
                    try {
                        const json = JSON.parse(line);
                        if (json.message && json.message.content) {
                            aiResponseText += json.message.content;
                            updateMessage(aiMessageId, aiResponseText);
                        }
                    } catch (e) {
                        console.error('Error parsing JSON chunk', e, line);
                    }
                }
            }

            // Process any remaining data in buffer
            if (buffer.trim()) {
                try {
                    const json = JSON.parse(buffer);
                    if (json.message && json.message.content) {
                        aiResponseText += json.message.content;
                        updateMessage(aiMessageId, aiResponseText);
                    }
                } catch (e) {
                    // Might not be a full JSON yet
                }
            }

            // Update history
            state.history.push({ role: 'user', content: text });
            state.history.push({ role: 'assistant', content: aiResponseText });

        } catch (error) {
            console.error('Chat error:', error);
            updateMessage(aiMessageId, `**Error:** ${error.message}\n\nPlease check your settings and ensure your local LLM is running.`);
        } finally {
            // Re-enable UI
            userInput.disabled = false;
            sendBtn.disabled = false;
            sendBtn.style.opacity = '1';
            userInput.focus();
        }
    }

    function addMessage(text, sender, isLoading = false) {
        const id = 'msg-' + Date.now();
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;
        messageDiv.id = id;

        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'avatar';
        avatarDiv.textContent = sender === 'user' ? 'U' : 'AI';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';

        if (isLoading) {
            contentDiv.textContent = text;
            contentDiv.classList.add('loading');
        } else {
            contentDiv.innerHTML = marked.parse(text);
            // Highlight code blocks
            contentDiv.querySelectorAll('pre code').forEach((block) => {
                hljs.highlightElement(block);
            });
        }

        if (sender === 'user') {
            messageDiv.appendChild(contentDiv);
            messageDiv.appendChild(avatarDiv);
        } else {
            messageDiv.appendChild(avatarDiv);
            messageDiv.appendChild(contentDiv);
        }

        chatArea.appendChild(messageDiv);
        scrollToBottom(true); // Force scroll when a new message is added

        // Remove welcome message if it exists
        const welcome = document.querySelector('.welcome-message');
        if (welcome) welcome.remove();

        return id;
    }

    function updateMessage(id, text) {
        const messageDiv = document.getElementById(id);
        if (!messageDiv) return;

        const contentDiv = messageDiv.querySelector('.message-content');
        contentDiv.classList.remove('loading');
        contentDiv.innerHTML = marked.parse(text);

        // Highlight code blocks
        contentDiv.querySelectorAll('pre code').forEach((block) => {
            hljs.highlightElement(block);
        });

        scrollToBottom();
    }

    // Track whether user has manually scrolled up
    let userScrolledUp = false;

    chatArea.addEventListener('scroll', () => {
        const threshold = 100; // pixels from bottom
        const atBottom = chatArea.scrollHeight - chatArea.scrollTop - chatArea.clientHeight < threshold;
        userScrolledUp = !atBottom;
    });

    function scrollToBottom(force = false) {
        if (force || !userScrolledUp) {
            chatArea.scrollTop = chatArea.scrollHeight;
        }
    }

    // --- File Browser Functions ---

    async function openFileBrowser(path) {
        fileBrowserModal.classList.add('active');
        const browsePath = path || currentBrowserPath || '';
        await fetchBrowserContents(browsePath);
    }

    async function fetchBrowserContents(path) {
        browserEntries.innerHTML = '<div class="browser-loading">Loading...</div>';
        try {
            const url = path
                ? `${currentOrigin}/api/browse?path=${encodeURIComponent(path)}`
                : `${currentOrigin}/api/browse`;
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`Failed to browse: ${response.statusText}`);
            }
            const data = await response.json();
            currentBrowserPath = data.current_path || '';
            browserCurrentPath.textContent = currentBrowserPath || '/';
            renderBrowserEntries(data.entries || []);
        } catch (error) {
            browserEntries.innerHTML = `<div class="browser-error">Error: ${error.message}</div>`;
            console.error('File browser error:', error);
        }
    }

    function renderBrowserEntries(entries) {
        browserEntries.innerHTML = '';
        if (entries.length === 0) {
            browserEntries.innerHTML = '<div class="browser-empty">No .gguf files or directories found</div>';
            return;
        }
        entries.forEach(entry => {
            const entryDiv = document.createElement('div');
            entryDiv.className = 'browser-entry';

            const icon = entry.type === 'dir' ? '📁' : '📄';
            const size = entry.type === 'file' && entry.size != null
                ? formatFileSize(entry.size)
                : '';

            entryDiv.innerHTML = `
                <span class="entry-icon">${icon}</span>
                <span class="entry-name">${entry.name}</span>
                ${size ? `<span class="entry-size">${size}</span>` : ''}
            `;

            if (entry.type === 'dir') {
                entryDiv.classList.add('browser-entry-dir');
                entryDiv.addEventListener('click', () => {
                    navigateToDirectory(entry.name);
                });
            } else {
                entryDiv.classList.add('browser-entry-file');
                entryDiv.addEventListener('click', () => {
                    selectModelFile(entry.name);
                });
            }

            browserEntries.appendChild(entryDiv);
        });
    }

    function navigateToDirectory(dirName) {
        const newPath = currentBrowserPath
            ? `${currentBrowserPath}/${dirName}`.replace(/\/\//g, '/')
            : dirName;
        fetchBrowserContents(newPath);
    }

    function navigateUp() {
        if (!currentBrowserPath || currentBrowserPath === '/' || currentBrowserPath === 'C:\\') {
            return;
        }
        // Handle both Unix and Windows paths
        let parentPath;
        if (currentBrowserPath.includes('\\')) {
            const parts = currentBrowserPath.split('\\');
            parts.pop();
            parentPath = parts.join('\\') || parts[0] + '\\';
        } else {
            const parts = currentBrowserPath.split('/');
            parts.pop();
            parentPath = parts.join('/') || '/';
        }
        fetchBrowserContents(parentPath);
    }

    function selectModelFile(fileName) {
        const fullPath = currentBrowserPath
            ? `${currentBrowserPath}/${fileName}`.replace(/\/\//g, '/')
            : fileName;
        // Handle Windows paths
        const normalizedPath = currentBrowserPath.includes('\\')
            ? `${currentBrowserPath}\\${fileName}`
            : fullPath;

        modelPathInput.value = normalizedPath;
        modelPath = normalizedPath;
        localStorage.setItem('modelPath', modelPath);
        fileBrowserModal.classList.remove('active');
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    // --- Model Loading Functions ---

    async function loadModel() {
        const path = modelPathInput.value.trim();
        if (!path) {
            modelStatusText.textContent = 'Error: No model path selected';
            modelStatusText.className = 'model-status error';
            return;
        }

        const params = {
            model_path: path,
            n_ctx: parseInt(nCtxInput.value) || 2048,
            n_threads: parseInt(nThreadsInput.value) || 6,
            n_gpu_layers: parseInt(nGpuLayersInput.value) || 20
        };

        // Show loading state
        loadModelBtn.disabled = true;
        loadModelBtn.textContent = 'Loading...';
        modelStatusText.textContent = 'Loading model...';
        modelStatusText.className = 'model-status loading';

        try {
            const response = await fetch(`${currentOrigin}/api/load-model`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(params)
            });

            const data = await response.json();

            if (response.ok && data.success) {
                const modelName = path.split(/[/\\]/).pop().replace(/\.gguf$/i, '');
                modelStatusText.textContent = `Loaded: ${modelName}`;
                modelStatusText.className = 'model-status loaded';

                // Auto-fill model name from filename
                modelNameInput.value = modelName;
                state.model = modelName;
                localStorage.setItem('model', modelName);

                // Persist settings
                localStorage.setItem('modelPath', path);
                localStorage.setItem('nCtx', params.n_ctx.toString());
                localStorage.setItem('nThreads', params.n_threads.toString());
                localStorage.setItem('nGpuLayers', params.n_gpu_layers.toString());
            } else {
                const errorMsg = data.detail || data.error || 'Failed to load model';
                modelStatusText.textContent = `Error: ${errorMsg}`;
                modelStatusText.className = 'model-status error';
            }
        } catch (error) {
            modelStatusText.textContent = `Error: ${error.message}`;
            modelStatusText.className = 'model-status error';
            console.error('Load model error:', error);
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

            if (data.status === 'loaded' && data.model_path) {
                const modelName = data.model_path.split(/[/\\]/).pop().replace(/\.gguf$/i, '');
                modelStatusText.textContent = `Loaded: ${modelName}`;
                modelStatusText.className = 'model-status loaded';
                modelPathInput.value = data.model_path;
                modelPath = data.model_path;
                localStorage.setItem('modelPath', modelPath);

                // Auto-fill model name from loaded model
                modelNameInput.value = modelName;
                state.model = modelName;
                localStorage.setItem('model', modelName);
            } else if (data.status === 'loading') {
                modelStatusText.textContent = 'Loading model...';
                modelStatusText.className = 'model-status loading';
            } else if (data.status === 'error') {
                modelStatusText.textContent = 'Error loading model';
                modelStatusText.className = 'model-status error';
            } else {
                modelStatusText.textContent = 'No model loaded';
                modelStatusText.className = 'model-status';
            }

            // Update input fields from server state if available
            if (data.n_ctx) {
                nCtxInput.value = data.n_ctx;
                nCtx = data.n_ctx;
            }
            if (data.n_threads) {
                nThreadsInput.value = data.n_threads;
                nThreads = data.n_threads;
            }
            if (data.n_gpu_layers != null) {
                nGpuLayersInput.value = data.n_gpu_layers;
                nGpuLayers = data.n_gpu_layers;
            }
        } catch (error) {
            // Silently fail — server might not be running yet
            console.log('Could not fetch model status:', error.message);
        }
    }
});
