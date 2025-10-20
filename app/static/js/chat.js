// AI Chat Interface with SSE Streaming

document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const chatMessages = document.getElementById('chat-messages');
    const typingIndicator = document.getElementById('typing-indicator');
    const clearChatBtn = document.getElementById('clear-chat-btn');
    const readinessScoreEl = document.getElementById('header-readiness-score');

    const STORAGE_KEY = 'chat-history';
    const MAX_RECONNECT_ATTEMPTS = 3;
    const RECONNECT_DELAY = 2000;

    let reconnectAttempts = 0;
    let eventSource = null;
    let isStreaming = false;
    let currentMessageElement = null;

    // Load chat history from localStorage
    loadChatHistory();

    // Load current readiness score
    loadReadinessScore();

    // Event Listeners
    chatForm.addEventListener('submit', handleSendMessage);
    clearChatBtn.addEventListener('click', handleClearChat);

    // Auto-resize textarea
    chatInput.addEventListener('input', () => {
        chatInput.style.height = 'auto';
        chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
    });

    // Handle Shift+Enter for new line, Enter to send
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event('submit'));
        }
    });

    // Quick action buttons
    document.querySelectorAll('.quick-action-btn[data-message]').forEach(btn => {
        btn.addEventListener('click', () => {
            const message = btn.dataset.message;
            if (message) {
                chatInput.value = message;
                chatForm.dispatchEvent(new Event('submit'));
            }
        });
    });

    async function handleSendMessage(e) {
        e.preventDefault();

        const message = chatInput.value.trim();
        if (!message || isStreaming) return;

        // Clear input and hide empty state
        chatInput.value = '';
        chatInput.style.height = 'auto';
        hideEmptyState();

        // Add user message to chat
        addUserMessage(message);

        // Disable input during streaming
        setInputDisabled(true);

        // Show typing indicator
        showTypingIndicator();

        try {
            // Send message and stream response
            await streamChatResponse(message);
        } catch (error) {
            console.error('Chat error:', error);
            hideTypingIndicator();
            addErrorMessage(error.message || 'Failed to send message');
        } finally {
            setInputDisabled(false);
            chatInput.focus();
        }
    }

    async function streamChatResponse(message) {
        isStreaming = true;

        try {
            // For now, use a POST endpoint with streaming response
            // The backend should support SSE streaming on /api/chat/send
            const response = await fetch('/api/chat/send', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'text/event-stream'
                },
                body: JSON.stringify({ message })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            // Check if streaming is supported
            if (response.headers.get('content-type')?.includes('text/event-stream')) {
                await handleSSEStream(response);
            } else {
                // Fallback to regular JSON response
                const data = await response.json();
                hideTypingIndicator();
                addAssistantMessage(data.response || data.message || 'No response');
            }
        } catch (error) {
            hideTypingIndicator();
            throw error;
        } finally {
            isStreaming = false;
        }
    }

    async function handleSSEStream(response) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        hideTypingIndicator();
        currentMessageElement = createAssistantMessageElement('');

        try {
            while (true) {
                const { done, value } = await reader.read();

                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6);

                        if (data === '[DONE]') {
                            saveChatHistory();
                            return;
                        }

                        try {
                            const parsed = JSON.parse(data);
                            if (parsed.token) {
                                appendToCurrentMessage(parsed.token);
                            } else if (parsed.content) {
                                appendToCurrentMessage(parsed.content);
                            }
                        } catch (e) {
                            // Not JSON, treat as raw text token
                            appendToCurrentMessage(data);
                        }
                    }
                }
            }

            saveChatHistory();
        } catch (error) {
            console.error('Stream reading error:', error);
            if (currentMessageElement) {
                currentMessageElement.remove();
            }
            throw error;
        }
    }

    function addUserMessage(text) {
        const messageEl = createMessageElement('user', text);
        chatMessages.appendChild(messageEl);
        scrollToBottom();
        saveChatHistory();
    }

    function addAssistantMessage(text) {
        const messageEl = createMessageElement('assistant', text);
        chatMessages.appendChild(messageEl);
        scrollToBottom();
        saveChatHistory();
    }

    function createAssistantMessageElement(text) {
        const messageEl = createMessageElement('assistant', text);
        chatMessages.appendChild(messageEl);
        scrollToBottom();
        return messageEl;
    }

    function appendToCurrentMessage(token) {
        if (!currentMessageElement) return;

        const contentEl = currentMessageElement.querySelector('.message-content');
        if (contentEl) {
            contentEl.textContent += token;
            scrollToBottom();
        }
    }

    function createMessageElement(role, text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${role}`;

        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = role === 'user' ? '👤' : '🤖';

        const contentWrapper = document.createElement('div');
        contentWrapper.style.flex = '1';

        const content = document.createElement('div');
        content.className = 'message-content';
        content.textContent = text;

        const timestamp = document.createElement('div');
        timestamp.className = 'message-timestamp';
        timestamp.textContent = new Date().toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit'
        });

        contentWrapper.appendChild(content);
        contentWrapper.appendChild(timestamp);
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(contentWrapper);

        return messageDiv;
    }

    function addErrorMessage(text) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.textContent = `Error: ${text}`;
        chatMessages.appendChild(errorDiv);
        scrollToBottom();
    }

    function showTypingIndicator() {
        if (typingIndicator) {
            typingIndicator.classList.add('active');
            scrollToBottom();
        }
    }

    function hideTypingIndicator() {
        if (typingIndicator) {
            typingIndicator.classList.remove('active');
        }
    }

    function setInputDisabled(disabled) {
        if (chatInput) chatInput.disabled = disabled;
        if (sendBtn) sendBtn.disabled = disabled;
    }

    function scrollToBottom() {
        if (chatMessages) {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }

    function hideEmptyState() {
        const emptyState = chatMessages.querySelector('.empty-state');
        if (emptyState) {
            emptyState.remove();
        }
    }

    function handleClearChat() {
        if (!confirm('Are you sure you want to clear the chat history?')) {
            return;
        }

        // Clear messages
        chatMessages.innerHTML = '';

        // Show empty state
        const emptyState = document.createElement('div');
        emptyState.className = 'empty-state';
        emptyState.innerHTML = `
            <div class="empty-state-icon">🤖</div>
            <h3>Start a Conversation</h3>
            <p>Ask me anything about your training, recovery, or workout plan. I have access to your latest Garmin data and readiness scores.</p>
        `;
        chatMessages.appendChild(emptyState);

        // Clear storage
        localStorage.removeItem(STORAGE_KEY);
    }

    function saveChatHistory() {
        const messages = [];
        chatMessages.querySelectorAll('.chat-message').forEach(msg => {
            const role = msg.classList.contains('user') ? 'user' : 'assistant';
            const content = msg.querySelector('.message-content')?.textContent || '';
            const timestamp = msg.querySelector('.message-timestamp')?.textContent || '';

            if (content) {
                messages.push({ role, content, timestamp });
            }
        });

        localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
    }

    function loadChatHistory() {
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            if (!stored) return;

            const messages = JSON.parse(stored);
            if (!Array.isArray(messages) || messages.length === 0) return;

            hideEmptyState();

            messages.forEach(msg => {
                if (msg.role && msg.content) {
                    const messageEl = createMessageElement(msg.role, msg.content);

                    // Update timestamp if stored
                    if (msg.timestamp) {
                        const timestampEl = messageEl.querySelector('.message-timestamp');
                        if (timestampEl) {
                            timestampEl.textContent = msg.timestamp;
                        }
                    }

                    chatMessages.appendChild(messageEl);
                }
            });

            scrollToBottom();
        } catch (error) {
            console.error('Error loading chat history:', error);
            localStorage.removeItem(STORAGE_KEY);
        }
    }

    async function loadReadinessScore() {
        try {
            const response = await fetch('/api/recommendations/today');
            if (!response.ok) return;

            const data = await response.json();
            if (data.readiness_score && readinessScoreEl) {
                readinessScoreEl.textContent = data.readiness_score;

                // Color code based on score
                if (data.readiness_score >= 80) {
                    readinessScoreEl.style.color = 'var(--accent-success)';
                } else if (data.readiness_score >= 60) {
                    readinessScoreEl.style.color = '#d69e2e';
                } else if (data.readiness_score >= 40) {
                    readinessScoreEl.style.color = 'var(--accent-warning)';
                } else {
                    readinessScoreEl.style.color = 'var(--accent-danger)';
                }
            }
        } catch (error) {
            console.error('Error loading readiness score:', error);
        }
    }
});
