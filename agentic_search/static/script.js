document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const chatMessages = document.getElementById('chat-messages');
    const productCardTemplate = document.getElementById('product-card-template');

    let currentSessionId = null;

    // Input event to toggle button state
    userInput.addEventListener('input', () => {
        sendButton.disabled = userInput.value.trim().length === 0;
    });

    // Handle form submission
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const query = userInput.value.trim();
        if (!query) return;

        // Add user message
        addUserMessage(query);

        // Clear input and disable button
        userInput.value = '';
        sendButton.disabled = true;

        // Show typing indicator
        const loadingId = addBotTypingMessage();

        try {
            // Call API
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ 
                    query: query,
                    session_id: currentSessionId
                })
            });

            if (!response.ok) {
                throw new Error('API request failed');
            }

            const data = await response.json();
            
            // Save session ID
            currentSessionId = data.session_id;

            // Remove typing indicator
            removeMessage(loadingId);

            // Add bot response with products
            addBotMessage(data.text, data.products);

        } catch (error) {
            console.error('Error fetching chat response:', error);
            removeMessage(loadingId);
            addBotMessage("Sorry, I encountered an error while searching for products. Please try again later.", []);
        }
    });

    function addUserMessage(text) {
        const messageRow = document.createElement('div');
        messageRow.className = 'message-row user';

        messageRow.innerHTML = `
            <div class="message-content user-content">
                <p>${escapeHTML(text)}</p>
            </div>
        `;

        chatMessages.appendChild(messageRow);
        scrollToBottom();
    }

    function addBotTypingMessage() {
        const id = 'loading-' + Date.now();
        const messageRow = document.createElement('div');
        messageRow.className = 'message-row bot';
        messageRow.id = id;

        messageRow.innerHTML = `
            <div class="avatar bot-avatar">
                <svg viewBox="0 0 24 24" fill="currentColor" width="24" height="24">
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 3c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm0 14.2c-2.5 0-4.71-1.28-6-3.22.03-1.99 4-3.08 6-3.08 1.99 0 5.97 1.09 6 3.08-1.29 1.94-3.5 3.22-6 3.22z"/>
                </svg>
            </div>
            <div class="message-content bot-content">
                <div class="typing-indicator">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
            </div>
        `;

        chatMessages.appendChild(messageRow);
        scrollToBottom();
        return id;
    }

    function removeMessage(id) {
        const el = document.getElementById(id);
        if (el) {
            el.remove();
        }
    }

    function addBotMessage(text, products) {
        const messageRow = document.createElement('div');
        messageRow.className = 'message-row bot';

        // Build the basic message HTML
        messageRow.innerHTML = `
            <div class="avatar bot-avatar">
                <svg viewBox="0 0 24 24" fill="currentColor" width="24" height="24">
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 3c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm0 14.2c-2.5 0-4.71-1.28-6-3.22.03-1.99 4-3.08 6-3.08 1.99 0 5.97 1.09 6 3.08-1.29 1.94-3.5 3.22-6 3.22z"/>
                </svg>
            </div>
            <div class="message-content bot-content">
                <p>${escapeHTML(text)}</p>
            </div>
        `;

        // Add product carousel if we have products
        if (products && products.length > 0) {
            const botContentEl = messageRow.querySelector('.bot-content');

            const carouselContainer = document.createElement('div');
            carouselContainer.className = 'carousel-container';

            const viewport = document.createElement('div');
            viewport.className = 'carousel-viewport';

            // Generate product cards
            products.forEach(product => {
                const cardNode = productCardTemplate.content.cloneNode(true);
                const card = cardNode.querySelector('.product-card');

                // Populate data
                card.href = product.link || '#';

                const img = card.querySelector('.product-image');
                img.src = product.image || 'https://via.placeholder.com/200x200?text=No+Image';
                img.alt = product.name;

                card.querySelector('.product-title').textContent = product.name || 'Unknown Product';

                // Format price properly
                let priceText = product.price ? product.price.toString() : '';
                if (priceText && !priceText.startsWith('₹') && !priceText.toLowerCase().includes('rs')) {
                    priceText = '₹' + priceText;
                }
                card.querySelector('.product-price').textContent = priceText || 'Price Unavailable';

                card.querySelector('.store-badge').textContent = product.store || '';

                viewport.appendChild(card);
            });

            carouselContainer.appendChild(viewport);

            // Add navigation arrow
            const navBtn = document.createElement('button');
            navBtn.className = 'carousel-nav';
            navBtn.innerHTML = `<svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/></svg>`;
            navBtn.addEventListener('click', () => {
                // Scroll the viewport 340px (about 2 cards) to the right
                viewport.scrollBy({ left: 340, behavior: 'smooth' });
            });

            carouselContainer.appendChild(navBtn);
            botContentEl.appendChild(carouselContainer);

            // Show/hide arrow based on scroll position logic
            viewport.addEventListener('scroll', () => {
                if (viewport.scrollLeft + viewport.clientWidth >= viewport.scrollWidth - 10) {
                    navBtn.style.opacity = '0';
                    navBtn.style.pointerEvents = 'none';
                } else {
                    navBtn.style.opacity = '1';
                    navBtn.style.pointerEvents = 'auto';
                }
            });
        }

        chatMessages.appendChild(messageRow);
        scrollToBottom();

        // Final layout adjust after images load
        setTimeout(scrollToBottom, 100);
    }

    function scrollToBottom() {
        const wrapper = document.querySelector('.chat-messages-wrapper');
        wrapper.scrollTop = wrapper.scrollHeight;
    }

    function escapeHTML(str) {
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }
});
