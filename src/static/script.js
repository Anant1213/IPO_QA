/**
 * IPO Intelligence Platform - Frontend JavaScript
 * Complete rewrite with proper backend integration
 */

// ========== Global State ==========
let currentDocumentId = null;
let questionsAsked = 0;
let totalResponseTime = 0;
let chatHistory = [];
let currentSessionId = null;

// ========== Initialization ==========
document.addEventListener('DOMContentLoaded', async function () {
    console.log('🚀 IPO Intelligence Platform Initializing...');

    try {
        // Load saved chat history from localStorage
        loadChatHistory();

        // Load available documents from backend
        await loadDocuments();

        // Setup all event listeners
        setupEventListeners();

        console.log('✅ Platform initialized successfully');
    } catch (error) {
        console.error('❌ Initialization error:', error);
        showNotification('Failed to initialize application', 'error');
    }
});

// ========== Event Listeners Setup ==========
function setupEventListeners() {
    // Send button click
    const sendBtn = document.getElementById('sendBtn');
    if (sendBtn) {
        sendBtn.addEventListener('click', sendMessage);
    }

    // Chat input Enter key
    const chatInput = document.getElementById('chatInput');
    if (chatInput) {
        chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        // Auto-resize textarea
        chatInput.addEventListener('input', function () {
            this.style.height = 'auto';
            this.style.height = (this.scrollHeight) + 'px';
        });
    }

    // Document selection change
    const documentSelect = document.getElementById('documentSelect');
    if (documentSelect) {
        documentSelect.addEventListener('change', (e) => {
            const previousDoc = currentDocumentId;
            currentDocumentId = e.target.value;

            console.log('═══════════════════════════════════');
            console.log('📄 DOCUMENT CHANGED');
            console.log('Previous:', previousDoc);
            console.log('New:', currentDocumentId);
            console.log('═══════════════════════════════════');

            if (currentDocumentId) {
                const selectedText = e.target.options[e.target.selectedIndex].text;
                showNotification(`Switched to: ${selectedText}`, 'success');
                saveChatHistory();
            }
        });
    }

    // File input change
    const fileInput = document.getElementById('fileInput');
    if (fileInput) {
        fileInput.addEventListener('change', handleFileSelection);
    }

    // Drag and drop for file upload
    const uploadArea = document.getElementById('uploadArea');
    if (uploadArea) {
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('drag-over');
        });

        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('drag-over');
        });

        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('drag-over');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                document.getElementById('fileInput').files = files;
                handleFileSelection();
            }
        });
    }

    console.log('✅ Event listeners setup complete');
}

// ========== Missing Functions (Previously Undefined) ==========

/**
 * Toggle the upload panel visibility
 */
function toggleUpload() {
    const uploadPanel = document.getElementById('uploadPanel');
    if (uploadPanel) {
        const isHidden = uploadPanel.style.display === 'none' || !uploadPanel.style.display;
        uploadPanel.style.display = isHidden ? 'flex' : 'none';
        console.log(`Upload panel ${isHidden ? 'opened' : 'closed'}`);
    }
}

/**
 * Set a question in the input field (from example cards)
 */
function setQuestion(text) {
    const chatInput = document.getElementById('chatInput');
    if (chatInput) {
        chatInput.value = text;
        chatInput.focus();
        // Trigger auto-resize
        chatInput.style.height = 'auto';
        chatInput.style.height = (chatInput.scrollHeight) + 'px';
        console.log('Question set from example:', text);
    }
}

/**
 * Clear the current chat session
 */
function clearChat() {
    console.log('Clearing chat...');

    // Clear chat history
    chatHistory = [];
    questionsAsked = 0;
    totalResponseTime = 0;
    currentSessionId = null;

    // Clear localStorage
    clearChatHistory();

    // Clear UI
    const chatMessages = document.getElementById('chatMessages');
    if (chatMessages) {
        chatMessages.innerHTML = '';
    }

    // Show welcome screen again
    const welcomeScreen = document.getElementById('welcomeScreen');
    if (welcomeScreen) {
        welcomeScreen.style.display = 'block';
    }

    // Reset stats
    updateStats();

    // Clear input
    const chatInput = document.getElementById('chatInput');
    if (chatInput) {
        chatInput.value = '';
        chatInput.style.height = 'auto';
    }

    showNotification('Chat cleared', 'success');
}

// ========== Document Management ==========

/**
 * Load documents from backend API
 */
async function loadDocuments() {
    console.log('📥 Loading documents from API...');

    try {
        const response = await fetch('/api/documents');

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        console.log('📥 Loaded documents:', data);

        const select = document.getElementById('documentSelect');
        if (!select) {
            console.warn('Document select element not found');
            return;
        }

        // Clear existing options
        select.innerHTML = '<option value="">Select a document...</option>';

        // Add documents
        if (data.documents && data.documents.length > 0) {
            data.documents.forEach(doc => {
                const option = document.createElement('option');
                option.value = doc.document_id;
                // Show KG badge in document name if available
                const kgBadge = doc.has_kg ? ' ✨' : '';
                option.textContent = `${doc.display_name}${kgBadge} (${doc.total_pages} pages)`;
                option.dataset.hasKg = doc.has_kg ? 'true' : 'false';
                select.appendChild(option);
            });

            console.log(`✅ Loaded ${data.documents.length} documents`);

            // Restore previous selection if exists
            if (currentDocumentId) {
                select.value = currentDocumentId;
            }
        } else {
            console.log('ℹ️ No documents found');
            showNotification('No documents uploaded yet. Upload a PDF to get started.', 'info');
        }
    } catch (error) {
        console.error('❌ Error loading documents:', error);
        showNotification('Failed to load documents', 'error');
    }
}

/**
 * Handle file selection from input
 */
function handleFileSelection() {
    const fileInput = document.getElementById('fileInput');
    const filePreview = document.getElementById('filePreview');
    const fileName = document.getElementById('fileName');
    const uploadArea = document.getElementById('uploadArea');

    if (fileInput.files.length > 0) {
        const file = fileInput.files[0];
        console.log('File selected:', file.name);

        // Show file preview
        if (fileName) {
            fileName.textContent = file.name;
        }
        if (filePreview) {
            filePreview.style.display = 'flex';
        }
        if (uploadArea) {
            uploadArea.style.display = 'none';
        }
    }
}

/**
 * Upload and process document
 */
async function uploadDocument() {
    const fileInput = document.getElementById('fileInput');
    const file = fileInput.files[0];

    if (!file) {
        showNotification('Please select a file first', 'error');
        return;
    }

    console.log('📤 Uploading document:', file.name);

    // Show progress UI
    const filePreview = document.getElementById('filePreview');
    const uploadProgress = document.getElementById('uploadProgress');
    const progressText = document.getElementById('progressText');
    const progressFill = document.getElementById('progressFill');

    if (filePreview) filePreview.style.display = 'none';
    if (uploadProgress) uploadProgress.style.display = 'flex';
    if (progressText) progressText.textContent = 'Uploading...';
    if (progressFill) progressFill.style.width = '30%';

    try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            console.log('✅ Document uploaded successfully:', data);

            if (progressFill) progressFill.style.width = '100%';
            if (progressText) progressText.textContent = 'Processing complete!';

            showNotification('Document uploaded successfully!', 'success');

            // Reload documents list
            await loadDocuments();

            // Select the new document
            if (data.document) {
                currentDocumentId = data.document.document_id;
                const select = document.getElementById('documentSelect');
                if (select) {
                    select.value = currentDocumentId;
                }
            }

            // Reset upload UI after delay
            setTimeout(() => {
                resetUploadUI();
            }, 1500);

        } else if (response.status === 409) {
            // Duplicate document
            console.log('ℹ️ Duplicate document:', data.message);
            showNotification(data.message, 'info');

            if (data.existing_document) {
                currentDocumentId = data.existing_document.document_id;
                const select = document.getElementById('documentSelect');
                if (select) {
                    select.value = currentDocumentId;
                }
            }

            resetUploadUI();
        } else {
            throw new Error(data.error || 'Upload failed');
        }

    } catch (error) {
        console.error('❌ Upload error:', error);
        showNotification(`Upload failed: ${error.message}`, 'error');

        if (progressText) progressText.textContent = 'Upload failed';
        if (progressFill) progressFill.style.width = '0%';

        setTimeout(() => {
            resetUploadUI();
        }, 2000);
    }
}

/**
 * Reset upload UI to initial state
 */
function resetUploadUI() {
    const fileInput = document.getElementById('fileInput');
    const filePreview = document.getElementById('filePreview');
    const uploadProgress = document.getElementById('uploadProgress');
    const uploadArea = document.getElementById('uploadArea');

    if (fileInput) fileInput.value = '';
    if (filePreview) filePreview.style.display = 'none';
    if (uploadProgress) uploadProgress.style.display = 'none';
    if (uploadArea) uploadArea.style.display = 'block';
}

// ========== Chat Functions ==========

/**
 * Hide the welcome screen
 */
function hideWelcomeScreen() {
    const welcomeScreen = document.getElementById('welcomeScreen');
    if (welcomeScreen) {
        welcomeScreen.style.display = 'none';
    }
}

/**
 * Add user message to chat
 */
function addUserMessage(text) {
    hideWelcomeScreen();

    try {
        const chatMessages = document.getElementById('chatMessages');
        if (!chatMessages) {
            console.error('Chat messages container not found');
            return;
        }

        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user';
        messageDiv.innerHTML = `<div class="message-content">${escapeHtml(text)}</div>`;
        chatMessages.appendChild(messageDiv);
        scrollToBottom();

        chatHistory.push({ role: 'user', content: text });
    } catch (e) {
        console.error('Error adding user message:', e);
    }
}

/**
 * Add assistant message with typing indicator
 */
function addAssistantMessage() {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) {
        console.error('Chat messages container not found');
        return null;
    }

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        </div>
    `;
    chatMessages.appendChild(messageDiv);
    scrollToBottom();

    return messageDiv;
}

/**
 * Update assistant message content
 */
function updateAssistantMessage(messageDiv, content, meta = null) {
    if (!messageDiv) return;

    const contentDiv = messageDiv.querySelector('.message-content');
    if (contentDiv) {
        contentDiv.innerHTML = content;
    }

    if (meta) {
        // Remove existing meta if any
        const existingMeta = messageDiv.querySelector('.message-meta');
        if (existingMeta) {
            existingMeta.remove();
        }

        const metaDiv = document.createElement('div');
        metaDiv.className = 'message-meta';
        metaDiv.innerHTML = `
            <span class="meta-badge model-badge">${meta.model}</span>
            <span class="meta-badge timer-badge">${meta.time}</span>
        `;
        messageDiv.appendChild(metaDiv);
    }

    scrollToBottom();
}

/**
 * Scroll chat to bottom
 */
function scrollToBottom() {
    const container = document.querySelector('.chat-area');
    if (container) {
        container.scrollTop = container.scrollHeight;
    }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Send message to backend
 */
async function sendMessage() {
    const input = document.getElementById('chatInput');
    const question = input ? input.value.trim() : '';

    console.log('📤 sendMessage called');
    console.log('   Question:', question);
    console.log('   Document:', currentDocumentId);

    if (!question) {
        console.log('   Empty question, ignoring');
        return;
    }

    if (!currentDocumentId) {
        console.warn('   No document selected');
        showNotification('Please select a document first', 'error');
        return;
    }

    // Disable input
    if (input) {
        input.value = '';
        input.style.height = 'auto';
        input.disabled = true;
    }

    const sendBtn = document.getElementById('sendBtn');
    if (sendBtn) {
        sendBtn.disabled = true;
    }

    // Add user message to UI
    addUserMessage(question);
    const assistantMsg = addAssistantMessage();

    // Prepare for streaming
    let currentText = '';
    let thinkingText = '';
    let isThinking = false;
    let model = 'llama3';
    const startTime = Date.now();

    try {
        console.log('═══════════════════════════════════');
        console.log('📤 SENDING REQUEST TO BACKEND');
        console.log('Question:', question);
        console.log('Document ID:', currentDocumentId);
        console.log('RAG Mode: auto');
        console.log('═══════════════════════════════════');

        const response = await fetch('/api/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                question: question,
                document_id: currentDocumentId,
                rag_mode: 'auto'  // Let backend router decide
            }),
        });

        console.log('📡 Response status:', response.status);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        // Process streaming response
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        console.log('📖 Reading stream...');

        while (true) {
            const { done, value } = await reader.read();

            if (done) {
                console.log('📖 Stream complete');
                break;
            }

            const decodedChunk = decoder.decode(value, { stream: true });
            buffer += decodedChunk;
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (!line.trim()) continue;

                try {
                    const data = JSON.parse(line);

                    if (data.type === 'meta') {
                        model = data.model || model;
                    }
                    else if (data.type === 'status') {
                        console.log('📡 Status:', data.msg);
                        updateAssistantMessage(assistantMsg,
                            `<div class="status-indicator"><span class="status-dot"></span>${data.msg}</div>`
                        );
                    }
                    else if (data.type === 'token') {
                        const token = data.content || '';

                        if (token.includes('<think>')) {
                            isThinking = true;
                            continue;
                        }

                        if (token.includes('</think>')) {
                            isThinking = false;
                            continue;
                        }

                        if (isThinking) {
                            thinkingText += token;
                        } else {
                            currentText += token;
                        }

                        // Update display
                        let displayHtml = formatMarkdown(currentText);

                        if (thinkingText) {
                            displayHtml = `
                                <details class="thinking-process">
                                    <summary>💭 Thinking Process</summary>
                                    <div class="thinking-content">${escapeHtml(thinkingText)}</div>
                                </details>
                                ${displayHtml}
                            `;
                        }

                        updateAssistantMessage(assistantMsg, displayHtml);
                    }
                    else if (data.type === 'done') {
                        console.log('✅ Response complete');

                        const responseTime = ((Date.now() - startTime) / 1000).toFixed(1);
                        questionsAsked++;
                        totalResponseTime += parseFloat(responseTime);
                        updateStats();

                        let finalHtml = formatMarkdown(currentText);

                        if (thinkingText) {
                            finalHtml = `
                                <details class="thinking-process">
                                    <summary>💭 Thinking Process</summary>
                                    <div class="thinking-content">${escapeHtml(thinkingText)}</div>
                                </details>
                                ${finalHtml}
                            `;
                        }

                        updateAssistantMessage(assistantMsg, finalHtml, {
                            model: model,
                            time: `${responseTime}s`
                        });

                        chatHistory.push({ role: 'assistant', content: currentText });
                    }
                    else if (data.type === 'warning') {
                        // KG fallback warning - show toast but continue
                        console.warn('⚠️ Backend warning:', data.msg);
                        showNotification(data.msg, 'warning');
                    }
                    else if (data.type === 'error') {
                        console.error('❌ Backend error:', data.msg);
                        updateAssistantMessage(assistantMsg,
                            `<span style="color: #ef4444;">Error: ${data.msg}</span>`
                        );
                    }

                } catch (e) {
                    console.error('Error parsing JSON:', e, 'Line:', line);
                }
            }
        }

    } catch (error) {
        console.error('❌ Send message error:', error);
        updateAssistantMessage(assistantMsg,
            `<span style="color: #ef4444;">Connection error: ${error.message}</span>`
        );
        showNotification('Failed to get response', 'error');
    } finally {
        // Re-enable input
        if (input) {
            input.disabled = false;
            input.focus();
        }
        if (sendBtn) {
            sendBtn.disabled = false;
        }
        saveChatHistory();
    }
}

/**
 * Format markdown-like text to HTML
 */
function formatMarkdown(text) {
    const div = document.createElement('div');
    div.textContent = text;
    let html = div.innerHTML;

    // Bold text
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // Line breaks
    html = html.replace(/\n/g, '<br>');

    return html;
}

/**
 * Update statistics display
 */
function updateStats() {
    const questionsCount = document.getElementById('questions-count');
    const avgTime = document.getElementById('avg-time');

    if (questionsCount) {
        questionsCount.textContent = questionsAsked;
    }

    if (avgTime && questionsAsked > 0) {
        const avg = (totalResponseTime / questionsAsked).toFixed(1);
        avgTime.textContent = `${avg}s`;
    } else if (avgTime) {
        avgTime.textContent = '--';
    }
}

/**
 * Show notification toast
 */
function showNotification(message, type = 'info') {
    console.log(`${type.toUpperCase()}: ${message}`);

    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 16px 24px;
        background: var(--bg-elevated);
        border: 1px solid var(--glass-border);
        border-radius: var(--radius-md);
        color: var(--text-primary);
        font-size: 14px;
        font-weight: 500;
        box-shadow: var(--shadow-lg);
        z-index: 10000;
        animation: slideInRight 0.3s ease;
        max-width: 400px;
    `;

    // Color based on type
    if (type === 'error') {
        notification.style.borderColor = '#ef4444';
        notification.style.background = 'rgba(239, 68, 68, 0.1)';
    } else if (type === 'success') {
        notification.style.borderColor = '#10b981';
        notification.style.background = 'rgba(16, 185, 129, 0.1)';
    } else if (type === 'warning') {
        notification.style.borderColor = '#f59e0b';
        notification.style.background = 'rgba(245, 158, 11, 0.1)';
    } else if (type === 'info') {
        notification.style.borderColor = '#3b82f6';
        notification.style.background = 'rgba(59, 130, 246, 0.1)';
    }

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 4000);
}

// ========== Chat History Persistence ==========

/**
 * Save chat history to localStorage
 */
function saveChatHistory() {
    const chatData = {
        sessionId: currentSessionId || Date.now().toString(),
        documentId: currentDocumentId,
        messages: chatHistory,
        stats: {
            questionsAsked: questionsAsked,
            totalResponseTime: totalResponseTime
        },
        timestamp: new Date().toISOString()
    };

    if (!currentSessionId) {
        currentSessionId = chatData.sessionId;
    }

    try {
        localStorage.setItem('currentSession', JSON.stringify(chatData));

        const history = JSON.parse(localStorage.getItem('chatHistory') || '[]');
        const existingIndex = history.findIndex(h => h.sessionId === chatData.sessionId);

        if (existingIndex >= 0) {
            history[existingIndex] = chatData;
        } else {
            history.unshift(chatData);
        }

        if (history.length > 50) {
            history.splice(50);
        }

        localStorage.setItem('chatHistory', JSON.stringify(history));
    } catch (e) {
        console.error('Error saving chat history:', e);
    }
}

/**
 * Load chat history from localStorage
 */
function loadChatHistory() {
    try {
        const savedSession = localStorage.getItem('currentSession');
        if (!savedSession) {
            console.log('No saved session found');
            return;
        }

        const chatData = JSON.parse(savedSession);
        currentSessionId = chatData.sessionId;
        currentDocumentId = chatData.documentId;
        chatHistory = chatData.messages || [];
        questionsAsked = chatData.stats?.questionsAsked || 0;
        totalResponseTime = chatData.stats?.totalResponseTime || 0;

        console.log('Loaded chat session:', chatData.sessionId);

        if (currentDocumentId) {
            const select = document.getElementById('documentSelect');
            if (select) {
                select.value = currentDocumentId;
            }
        }

        if (chatHistory.length > 0) {
            hideWelcomeScreen();
            const chatMessages = document.getElementById('chatMessages');

            if (chatMessages) {
                chatHistory.forEach(msg => {
                    const messageDiv = document.createElement('div');
                    messageDiv.className = `message ${msg.role}`;

                    const content = formatMarkdown(msg.content);
                    messageDiv.innerHTML = `<div class="message-content">${content}</div>`;
                    chatMessages.appendChild(messageDiv);
                });
            }
        }

        updateStats();
    } catch (e) {
        console.error('Error loading chat history:', e);
    }
}

/**
 * Clear chat history from localStorage
 */
function clearChatHistory() {
    try {
        localStorage.removeItem('currentSession');
        console.log('Chat history cleared');
    } catch (e) {
        console.error('Error clearing chat history:', e);
    }
}

// ========== Animation Styles ==========
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOutRight {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
    
    .status-indicator {
        display: flex;
        align-items: center;
        gap: 8px;
        color: var(--text-secondary);
        font-size: 14px;
    }
    
    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: var(--accent-primary);
        animation: pulse 2s ease-in-out infinite;
    }
`;
document.head.appendChild(style);

console.log('✅ Script loaded successfully');
