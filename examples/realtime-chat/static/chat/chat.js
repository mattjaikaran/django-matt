/**
 * Real-Time Chat Client
 *
 * WebSocket client for the chat application.
 * Handles connection, authentication, and message handling.
 */

class ChatClient {
    constructor(config) {
        this.config = config;
        this.ws = null;
        this.connected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.messageHandlers = new Map();
        this.pendingMessages = [];

        // Bind methods
        this.connect = this.connect.bind(this);
        this.disconnect = this.disconnect.bind(this);
        this.send = this.send.bind(this);
        this.onMessage = this.onMessage.bind(this);
    }

    /**
     * Connect to WebSocket server
     */
    connect() {
        const token = localStorage.getItem('access_token');
        if (!token) {
            console.error('No access token found');
            return;
        }

        const url = `${this.config.wsUrl}?token=${token}`;
        console.log('Connecting to WebSocket:', url);

        this.ws = new WebSocket(url);

        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.connected = true;
            this.reconnectAttempts = 0;

            // Join channel if configured
            if (this.config.channelId) {
                this.joinChannel(this.config.channelId);
            }

            // Send any pending messages
            while (this.pendingMessages.length > 0) {
                const msg = this.pendingMessages.shift();
                this.send(msg);
            }
        };

        this.ws.onclose = (event) => {
            console.log('WebSocket closed:', event.code, event.reason);
            this.connected = false;

            // Attempt reconnection
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                this.reconnectAttempts++;
                const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
                console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
                setTimeout(this.connect, delay);
            }
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

        this.ws.onmessage = this.onMessage;
    }

    /**
     * Disconnect from WebSocket server
     */
    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.connected = false;
    }

    /**
     * Send a message through WebSocket
     */
    send(data) {
        if (!this.connected) {
            this.pendingMessages.push(data);
            return;
        }

        const message = typeof data === 'string' ? data : JSON.stringify(data);
        this.ws.send(message);
    }

    /**
     * Handle incoming WebSocket message
     */
    onMessage(event) {
        try {
            const data = JSON.parse(event.data);
            console.log('Received:', data.type, data);

            // Handle by message type
            const handler = this.messageHandlers.get(data.type);
            if (handler) {
                handler(data);
            }

            // Built-in handlers
            switch (data.type) {
                case 'connected':
                    this.handleConnected(data);
                    break;
                case 'channel.joined':
                    this.handleChannelJoined(data);
                    break;
                case 'channel.left':
                    this.handleChannelLeft(data);
                    break;
                case 'message.new':
                    this.handleNewMessage(data);
                    break;
                case 'message.updated':
                    this.handleMessageUpdated(data);
                    break;
                case 'message.deleted':
                    this.handleMessageDeleted(data);
                    break;
                case 'typing.update':
                    this.handleTypingUpdate(data);
                    break;
                case 'user.joined':
                    this.handleUserJoined(data);
                    break;
                case 'user.left':
                    this.handleUserLeft(data);
                    break;
                case 'reaction.added':
                    this.handleReactionAdded(data);
                    break;
                case 'reaction.removed':
                    this.handleReactionRemoved(data);
                    break;
                case 'presence.changed':
                    this.handlePresenceChanged(data);
                    break;
                case 'error':
                    this.handleError(data);
                    break;
            }
        } catch (err) {
            console.error('Failed to parse message:', err);
        }
    }

    /**
     * Register a message handler
     */
    on(type, handler) {
        this.messageHandlers.set(type, handler);
    }

    /**
     * Unregister a message handler
     */
    off(type) {
        this.messageHandlers.delete(type);
    }

    // =========================================================================
    // Channel Operations
    // =========================================================================

    joinChannel(channelId) {
        this.send({
            type: 'channel.join',
            channel_id: channelId
        });
    }

    leaveChannel() {
        this.send({
            type: 'channel.leave'
        });
    }

    // =========================================================================
    // Message Operations
    // =========================================================================

    sendMessage(content, threadId = null, attachmentIds = []) {
        this.send({
            type: 'message.send',
            channel_id: this.config.channelId,
            content: content,
            thread_id: threadId,
            attachment_ids: attachmentIds
        });
    }

    updateMessage(messageId, content) {
        this.send({
            type: 'message.update',
            message_id: messageId,
            content: content
        });
    }

    deleteMessage(messageId) {
        this.send({
            type: 'message.delete',
            message_id: messageId
        });
    }

    // =========================================================================
    // Typing Indicators
    // =========================================================================

    startTyping() {
        this.send({
            type: 'typing.start',
            channel_id: this.config.channelId
        });
    }

    stopTyping() {
        this.send({
            type: 'typing.stop',
            channel_id: this.config.channelId
        });
    }

    // =========================================================================
    // Reactions
    // =========================================================================

    addReaction(messageId, emoji) {
        this.send({
            type: 'reaction.add',
            message_id: messageId,
            emoji: emoji
        });
    }

    removeReaction(messageId, emoji) {
        this.send({
            type: 'reaction.remove',
            message_id: messageId,
            emoji: emoji
        });
    }

    // =========================================================================
    // Presence
    // =========================================================================

    updatePresence(status) {
        this.send({
            type: 'presence.update',
            status: status
        });
    }

    // =========================================================================
    // Read Receipts
    // =========================================================================

    markRead(messageId) {
        this.send({
            type: 'read_receipt.mark',
            channel_id: this.config.channelId,
            message_id: messageId
        });
    }

    // =========================================================================
    // Event Handlers
    // =========================================================================

    handleConnected(data) {
        console.log('Connected as user:', data.username);
    }

    handleChannelJoined(data) {
        console.log('Joined channel:', data.channel.name);

        // Render messages
        const messagesList = document.getElementById('messagesList');
        if (messagesList && data.recent_messages) {
            messagesList.innerHTML = data.recent_messages
                .map(msg => window.renderMessage ? window.renderMessage(msg) : this.defaultRenderMessage(msg))
                .join('');

            // Scroll to bottom
            const container = document.getElementById('messagesContainer');
            if (container) {
                container.scrollTop = container.scrollHeight;
            }
        }

        // Update member count
        const memberCount = document.getElementById('memberCount');
        if (memberCount && data.members_online) {
            memberCount.textContent = data.members_online.length;
        }

        // Render online members
        const membersList = document.getElementById('membersList');
        if (membersList && data.members_online) {
            membersList.innerHTML = data.members_online
                .map(user => `
                    <div class="member-item">
                        <span class="status-indicator online"></span>
                        <span>${user.username}</span>
                    </div>
                `)
                .join('');
        }
    }

    handleChannelLeft(data) {
        console.log('Left channel:', data.channel_id);
    }

    handleNewMessage(data) {
        const messagesList = document.getElementById('messagesList');
        if (messagesList) {
            const html = window.renderMessage ? window.renderMessage(data.message) : this.defaultRenderMessage(data.message);
            messagesList.insertAdjacentHTML('beforeend', html);

            // Scroll to bottom
            const container = document.getElementById('messagesContainer');
            if (container) {
                container.scrollTop = container.scrollHeight;
            }
        }
    }

    handleMessageUpdated(data) {
        const messageEl = document.querySelector(`[data-message-id="${data.message.id}"]`);
        if (messageEl) {
            const html = window.renderMessage ? window.renderMessage(data.message) : this.defaultRenderMessage(data.message);
            messageEl.outerHTML = html;
        }
    }

    handleMessageDeleted(data) {
        const messageEl = document.querySelector(`[data-message-id="${data.message_id}"]`);
        if (messageEl) {
            messageEl.remove();
        }
    }

    handleTypingUpdate(data) {
        const indicator = document.getElementById('typingIndicator');
        if (indicator) {
            if (data.users && data.users.length > 0) {
                const names = data.users.map(u => u.username);
                if (names.length === 1) {
                    indicator.textContent = `${names[0]} is typing...`;
                } else if (names.length === 2) {
                    indicator.textContent = `${names[0]} and ${names[1]} are typing...`;
                } else {
                    indicator.textContent = `${names.length} people are typing...`;
                }
            } else {
                indicator.textContent = '';
            }
        }
    }

    handleUserJoined(data) {
        console.log('User joined:', data.user.username);

        // Add to members list
        const membersList = document.getElementById('membersList');
        if (membersList) {
            membersList.insertAdjacentHTML('beforeend', `
                <div class="member-item" data-user-id="${data.user.id}">
                    <span class="status-indicator online"></span>
                    <span>${data.user.username}</span>
                </div>
            `);
        }

        // Update count
        const memberCount = document.getElementById('memberCount');
        if (memberCount) {
            memberCount.textContent = parseInt(memberCount.textContent) + 1;
        }
    }

    handleUserLeft(data) {
        console.log('User left:', data.user.username);

        // Remove from members list
        const memberEl = document.querySelector(`[data-user-id="${data.user.id}"]`);
        if (memberEl) {
            memberEl.remove();
        }

        // Update count
        const memberCount = document.getElementById('memberCount');
        if (memberCount) {
            memberCount.textContent = Math.max(0, parseInt(memberCount.textContent) - 1);
        }
    }

    handleReactionAdded(data) {
        // Re-fetch message to update reactions display
        this.refreshMessage(data.message_id);
    }

    handleReactionRemoved(data) {
        // Re-fetch message to update reactions display
        this.refreshMessage(data.message_id);
    }

    handlePresenceChanged(data) {
        console.log('Presence changed:', data.user_id, data.status);

        // Update status indicator
        const memberEl = document.querySelector(`[data-user-id="${data.user_id}"] .status-indicator`);
        if (memberEl) {
            memberEl.className = `status-indicator ${data.status}`;
        }
    }

    handleError(data) {
        console.error('WebSocket error:', data.code, data.message);

        // Handle auth errors
        if (data.code === 4001) {
            // Token expired, try to refresh
            this.refreshToken();
        }
    }

    // =========================================================================
    // Helpers
    // =========================================================================

    async refreshMessage(messageId) {
        try {
            const response = await this.api(`/messages/${messageId}`);
            const message = await response.json();

            const messageEl = document.querySelector(`[data-message-id="${messageId}"]`);
            if (messageEl) {
                const html = window.renderMessage ? window.renderMessage(message) : this.defaultRenderMessage(message);
                messageEl.outerHTML = html;
            }
        } catch (err) {
            console.error('Failed to refresh message:', err);
        }
    }

    async refreshToken() {
        const refreshToken = localStorage.getItem('refresh_token');
        if (!refreshToken) {
            window.location.href = '/chat/';
            return;
        }

        try {
            const response = await fetch(`${this.config.apiUrl}/auth/refresh`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh_token: refreshToken })
            });

            if (response.ok) {
                const data = await response.json();
                localStorage.setItem('access_token', data.access_token);
                localStorage.setItem('refresh_token', data.refresh_token);

                // Reconnect with new token
                this.disconnect();
                this.connect();
            } else {
                // Refresh failed, redirect to login
                localStorage.removeItem('access_token');
                localStorage.removeItem('refresh_token');
                window.location.href = '/chat/';
            }
        } catch (err) {
            console.error('Token refresh failed:', err);
        }
    }

    api(endpoint, options = {}) {
        const token = localStorage.getItem('access_token');
        return fetch(`${this.config.apiUrl}${endpoint}`, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`,
                ...options.headers
            }
        });
    }

    defaultRenderMessage(msg) {
        const time = new Date(msg.created_at).toLocaleTimeString();
        return `
            <div class="message" data-message-id="${msg.id}">
                <div class="message-avatar">
                    ${msg.author?.username?.charAt(0).toUpperCase() || '?'}
                </div>
                <div class="message-content">
                    <div class="message-header">
                        <span class="message-author">${msg.author?.username || 'Unknown'}</span>
                        <span class="message-time">${time}</span>
                    </div>
                    <div class="message-text">${this.escapeHtml(msg.content)}</div>
                </div>
            </div>
        `;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Export for use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ChatClient;
}
