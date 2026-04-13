document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const chatMessages = document.getElementById('chat-messages');
    const productCardTemplate = document.getElementById('product-card-template');

    // GUARANTEED: Generate ID on client side so server never gets None
    let currentSessionId = localStorage.getItem('fashion_session_id');
    if (!currentSessionId) {
        currentSessionId = 'session-' + Math.random().toString(36).substr(2, 9) + Date.now();
        localStorage.setItem('fashion_session_id', currentSessionId);
    }
    console.log(`✅ Client-Side Session Active: ${currentSessionId}`);

    userInput.addEventListener('input', () => {
        sendButton.disabled = userInput.value.trim().length === 0;
    });

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const query = userInput.value.trim();
        if (!query) return;

        addUserMessage(query);
        userInput.value = '';
        sendButton.disabled = true;
        const loadingId = addBotTypingMessage();

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    query: query,
                    session_id: currentSessionId
                })
            });

            if (!response.ok) throw new Error('API failed');
            const data = await response.json();

            currentSessionId = data.session_id;  // ← server is now the source of truth
            localStorage.setItem('fashion_session_id', currentSessionId);  // best-effort persist
            
            removeMessage(loadingId);
            addBotMessage(data.text, data.products);

        } catch (error) {
            console.error('Error:', error);
            removeMessage(loadingId);
            addBotMessage("Sorry, I encountered an error. Please try again.", []);
        }
    });

    function addUserMessage(text) {
        const messageRow = document.createElement('div');
        messageRow.className = 'message-row user';
        messageRow.innerHTML = `<div class="message-content user-content"><p>${escapeHTML(text)}</p></div>`;
        chatMessages.appendChild(messageRow);
        scrollToBottom();
    }

    function addBotTypingMessage() {
        const id = 'loading-' + Date.now();
        const messageRow = document.createElement('div');
        messageRow.className = 'message-row bot';
        messageRow.id = id;
        messageRow.innerHTML = `
            <div class="avatar bot-avatar"><svg viewBox="0 0 24 24" fill="currentColor" width="24" height="24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 3c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm0 14.2c-2.5 0-4.71-1.28-6-3.22.03-1.99 4-3.08 6-3.08 1.99 0 5.97 1.09 6 3.08-1.29 1.94-3.5 3.22-6 3.22z"/></svg></div>
            <div class="message-content bot-content"><div class="typing-indicator"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div></div>`;
        chatMessages.appendChild(messageRow);
        scrollToBottom();
        return id;
    }

    function removeMessage(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    }

    function addBotMessage(text, products) {
        const messageRow = document.createElement('div');
        messageRow.className = 'message-row bot';
        const parsedMarkdown = typeof marked !== 'undefined' ? marked.parse(text) : `<p>${escapeHTML(text)}</p>`;
        messageRow.innerHTML = `
            <div class="avatar bot-avatar"><svg viewBox="0 0 24 24" fill="currentColor" width="24" height="24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 3c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm0 14.2c-2.5 0-4.71-1.28-6-3.22.03-1.99 4-3.08 6-3.08 1.99 0 5.97 1.09 6 3.08-1.29 1.94-3.5 3.22-6 3.22z"/></svg></div>
            <div class="message-content bot-content">${parsedMarkdown}</div>`;
        
        if (products && products.length > 0) {
            const botContentEl = messageRow.querySelector('.bot-content');
            const carouselContainer = document.createElement('div');
            carouselContainer.className = 'carousel-container';
            const viewport = document.createElement('div');
            viewport.className = 'carousel-viewport';
            products.forEach(p => {
                const cardNode = productCardTemplate.content.cloneNode(true);
                const card = cardNode.querySelector('.product-card');
                card.href = p.link || '#';
                const img = card.querySelector('.product-image');
                img.src = p.image || 'https://via.placeholder.com/200x200?text=No+Image';
                card.querySelector('.product-title').textContent = p.name || 'Unknown';
                card.querySelector('.product-price').textContent = p.price || 'N/A';
                card.querySelector('.store-badge').textContent = p.store || '';
                viewport.appendChild(card);
            });
            carouselContainer.appendChild(viewport);
            botContentEl.appendChild(carouselContainer);
        }
        chatMessages.appendChild(messageRow);
        scrollToBottom();
    }

    function scrollToBottom() {
        const wrapper = document.querySelector('.chat-messages-wrapper');
        if (wrapper) wrapper.scrollTop = wrapper.scrollHeight;
    }

    function escapeHTML(str) {
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
    }
});
