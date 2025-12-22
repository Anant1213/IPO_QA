let currentDocumentId = null;
let questionsAsked = 0;
let totalResponseTime = 0;
let chatHistory = [];
let currentSessionId = null;

// Initialize
document.addEventListener('DOMContentLoaded', async function () {
    loadChatHistory();
    await loadDocuments();

    // Event Listeners
    document.getElementById('sendBtn').addEventListener('click', sendMessage);
    document.getElementById('chatInput').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    document.getElementById('documentSelect').addEventListener('change', (e) => {
        currentDocumentId = e.target.value;
        if (currentDocumentId) {
            showNotification(`Switched to document: ${e.target.options[e.target.selectedIndex].text}`);
            saveChatHistory();
        }
    });

    // Auto-resize textarea
    const textarea = document.getElementById('chatInput');
    textarea.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
    });
});

async function loadDocuments() {
    try {
        const response = await fetch('/api/documents');
        const data = await response.json();

        const select = document.getElementById('documentSelect');
        select.innerHTML = '<option value="">Select a document...</option>';

        if (data.documents && data.documents.length > 0) {
            data.documents.forEach(doc => {
                const option = document.createElement('option');
                option.value = doc.document_id;
                option.textContent = `${doc.display_name} (${doc.total_pages} pages)`;
                select.appendChild(option);
            });

            // Restore selection if exists
            if (currentDocumentId) {
                select.value = currentDocumentId;
            }
        }
    } catch (error) {
        console.error('Error loading documents:', error);
    }
}

async function uploadDocument() {
    const fileInput = document.getElementById('fileInput');
    const file = fileInput.files[0];

    if (!file) {
        showNotification('Please select a file first', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    const uploadBtn = document.querySelector('.upload-btn');
    const originalText = uploadBtn.innerHTML;
    uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
    uploadBtn.disabled = true;

    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            showNotification('Document processed successfully!', 'success');
            await loadDocuments();
            // Select the new document
            if (data.document) {
                currentDocumentId = data.document.document_id;
                document.getElementById('documentSelect').value = currentDocumentId;
            }
            fileInput.value = '';
        } else {
            if (response.status === 409) {
                showNotification(data.message, 'info');
                // Select existing document
                if (data.existing_document) {
                    currentDocumentId = data.existing_document.document_id;
                    document.getElementById('documentSelect').value = currentDocumentId;
                }
            } else {
                showNotification(data.error || 'Upload failed', 'error');
            }
        }
    } catch (error) {
        console.error('Error:', error);
        showNotification('An error occurred during upload', 'error');
    } finally {
        uploadBtn.innerHTML = originalText;
        uploadBtn.disabled = false;
    }
}

function hideWelcomeScreen() {
    const welcomeScreen = document.getElementById('welcomeScreen');
    if (welcomeScreen) {
        welcomeScreen.style.display = 'none';
    }
}

function addUserMessage(text) {
    hideWelcomeScreen();

    try {
        const chatMessages = document.getElementById('chatMessages');
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

function addAssistantMessage() {
    const chatMessages = document.getElementById('chatMessages');
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

function updateAssistantMessage(messageDiv, content, meta = null) {
    const contentDiv = messageDiv.querySelector('.message-content');
    contentDiv.innerHTML = content;

    if (meta) {
        // Remove existing meta if any to prevent duplicates
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

function scrollToBottom() {
    const container = document.querySelector('.chat-area');
    if (container) {
        container.scrollTop = container.scrollHeight;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function sendMessage() {
    const input = document.getElementById('chatInput');
    const question = input.value.trim();

    console.log('sendMessage called. Question:', question);
    console.log('Current Document ID:', currentDocumentId);

    // DEBUG: Visible alert to trace execution
    // alert('DEBUG: sendMessage called. Question: ' + question + ', Doc: ' + currentDocumentId);

    if (!question) return;

    if (!currentDocumentId) {
        console.warn('No document selected');
        showNotification('Please select a document first', 'error');
        return;
    }

    input.value = '';
    input.style.height = 'auto';
    input.disabled = true;
    document.getElementById('sendBtn').disabled = true;

    addUserMessage(question);
    const assistantMsg = addAssistantMessage();

    // DEBUG: Show that we're about to send request
    console.log('DEBUG: About to send fetch request...');
    updateAssistantMessage(assistantMsg, '<div class="status-indicator"><span class="status-dot"></span>Connecting to server...</div>');

    let currentText = '';
    let thinkingText = '';
    let isThinking = false;
    let model = '';
    const startTime = Date.now();

    try {
        // Get RAG mode from toggle
        const ragToggle = document.getElementById('ragModeToggle');
        const ragMode = ragToggle && ragToggle.checked ? 'vector' : 'kg';

        console.log('DEBUG: Fetching /api/ask...');
        console.log('DEBUG: RAG Mode:', ragMode);

        const response = await fetch('/api/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                question: question,
                document_id: currentDocumentId,
                rag_mode: ragMode  // NEW: Send RAG mode
            }),
        });

        console.log('DEBUG: Response received, status:', response.status);

        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        console.log('👀 DEBUG: Starting to read stream...');
        console.log('👀 DEBUG: Response body is:', response.body);
        console.log('👀 DEBUG: Reader is:', reader);

        let readCount = 0;
        while (true) {
            const { done, value } = await reader.read();
            readCount++;
            console.log(`📖 DEBUG Read #${readCount}: done=${done}, value length=${value?.length || 0}`);
            if (done) {
                console.log('📖 DEBUG: Stream ended (done=true)');
                break;
            }

            const decodedChunk = decoder.decode(value, { stream: true });
            console.log('📖 DEBUG: Decoded chunk:', decodedChunk.substring(0, 200));
            buffer += decodedChunk;
            const lines = buffer.split('\n');
            buffer = lines.pop();
            console.log(`📖 DEBUG: Processing ${lines.length} lines, buffer remaining: ${buffer.length} chars`);

            for (const line of lines) {
                if (!line.trim()) continue;

                try {
                    const data = JSON.parse(line);

                    if (data.type === 'meta') {
                        model = data.model;
                    }
                    else if (data.type === 'status') {
                        // Show status messages in the assistant message area
                        console.log('📡 Status:', data.msg);
                        updateAssistantMessage(assistantMsg, `<div class="status-indicator"><span class="status-dot"></span>${data.msg}</div>`);
                    }
                    else if (data.type === 'token') {
                        const token = data.content;
                        console.log('🎯 TOKEN RECEIVED:', token);
                        console.log('🎯 Token length:', token ? token.length : 0);

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

                            const tempDiv = document.createElement('div');
                            tempDiv.textContent = currentText;
                            let displayHtml = tempDiv.innerHTML
                                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                                .replace(/\n/g, '<br>');

                            if (thinkingText) {
                                const thinkDiv = document.createElement('div');
                                thinkDiv.textContent = thinkingText;
                                displayHtml = `
                                    <details class="thinking-process">
                                        <summary>💭 Thinking Process</summary>
                                        <div class="thinking-content">${thinkDiv.innerHTML}</div>
                                    </details>
                                    ${displayHtml}
                                `;
                            }

                            updateAssistantMessage(assistantMsg, displayHtml);
                        }
                    }
                    else if (data.type === 'done') {
                        console.log('✅ DONE RECEIVED');
                        console.log('✅ currentText:', currentText);
                        console.log('✅ currentText length:', currentText.length);

                        const responseTime = ((Date.now() - startTime) / 1000).toFixed(1);
                        questionsAsked++;
                        totalResponseTime += parseFloat(responseTime);
                        updateStats();

                        let answerText = currentText;
                        let displayThinking = thinkingText;

                        if (!currentText.trim() && thinkingText) {
                            const lines = thinkingText.split('\n');
                            const lastParagraphs = lines.slice(-10).join('\n');
                            answerText = lastParagraphs;
                            displayThinking = thinkingText;
                        }

                        const finalDiv = document.createElement('div');
                        finalDiv.textContent = answerText;
                        let finalHtml = finalDiv.innerHTML
                            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                            .replace(/\n/g, '<br>');

                        if (displayThinking) {
                            const thinkDiv = document.createElement('div');
                            thinkDiv.textContent = displayThinking;
                            finalHtml = `
                                <details class="thinking-process">
                                    <summary>💭 Thinking Process</summary>
                                    <div class="thinking-content">${thinkDiv.innerHTML}</div>
                                </details>
                                ${finalHtml}
                            `;
                        }

                        updateAssistantMessage(assistantMsg, finalHtml, {
                            model: model,
                            time: `${responseTime}s`
                        });

                        chatHistory.push({ role: 'assistant', content: answerText });
                    }
                    else if (data.type === 'error') {
                        updateAssistantMessage(assistantMsg, `<span style="color: #ef4444;">Error: ${data.msg}</span>`);
                    }

                } catch (e) {
                    console.error('Error parsing JSON:', e);
                }
            }
        }

        // Process any remaining content in the buffer after stream ends
        if (buffer.trim()) {
            console.log('📌 Processing remaining buffer:', buffer);
            try {
                const data = JSON.parse(buffer);
                if (data.type === 'token' && data.content) {
                    currentText += data.content;
                    console.log('📌 Added remaining token to currentText');
                }
            } catch (e) {
                console.log('📌 Buffer was not valid JSON:', e.message);
            }
        }

        // Fallback: If we have currentText but it wasn't displayed, show it now
        if (currentText.trim() && assistantMsg) {
            console.log('📌 Fallback display of currentText:', currentText.substring(0, 100));
            const tempDiv = document.createElement('div');
            tempDiv.textContent = currentText;
            let displayHtml = tempDiv.innerHTML
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/\n/g, '<br>');
            const responseTime = ((Date.now() - startTime) / 1000).toFixed(1);
            updateAssistantMessage(assistantMsg, displayHtml, {
                model: model || 'llama3',
                time: `${responseTime}s`
            });
        }

    } catch (error) {
        console.error('Error:', error);
        updateAssistantMessage(assistantMsg, `<span style="color: #ef4444;">An error occurred while fetching the answer</span>`);
    } finally {
        input.disabled = false;
        document.getElementById('sendBtn').disabled = false;
        input.focus();
        saveChatHistory();
    }
}

function updateStats() {
    document.getElementById('questions-count').textContent = questionsAsked;

    if (questionsAsked > 0) {
        const avgTime = (totalResponseTime / questionsAsked).toFixed(1);
        document.getElementById('avg-time').textContent = `${avgTime}s`;
    }
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Chat History Persistence
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
}

function loadChatHistory() {
    const savedSession = localStorage.getItem('currentSession');
    if (!savedSession) return;

    const chatData = JSON.parse(savedSession);
    currentSessionId = chatData.sessionId;
    currentDocumentId = chatData.documentId;
    chatHistory = chatData.messages || [];
    questionsAsked = chatData.stats?.questionsAsked || 0;
    totalResponseTime = chatData.stats?.totalResponseTime || 0;

    if (currentDocumentId) {
        const select = document.getElementById('documentSelect');
        if (select) {
            select.value = currentDocumentId;
        }
    }

    if (chatHistory.length > 0) {
        hideWelcomeScreen();
        const chatMessages = document.getElementById('chatMessages');

        chatHistory.forEach(msg => {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${msg.role}`;

            const tempDiv = document.createElement('div');
            tempDiv.textContent = msg.content;
            const content = tempDiv.innerHTML
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/\n/g, '<br>');

            messageDiv.innerHTML = `<div class="message-content">${content}</div>`;
            chatMessages.appendChild(messageDiv);
        });
    }

    updateStats();
}

function clearChatHistory() {
    localStorage.removeItem('currentSession');
    currentSessionId = null;
}


// Add slideOut animation
const style = document.createElement('style');
style.textContent = `
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(400px); opacity: 0; }
    }
`;
document.head.appendChild(style);
