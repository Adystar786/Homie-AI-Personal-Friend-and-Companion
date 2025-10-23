// Global variables
let isTyping = false;
let videoTimeout;
let currentMood = 'neutral';
let safeModeActive = false;

// Music variables
let backgroundMusic = document.getElementById('backgroundMusic');
let musicEnabled = true;
let currentTrack = 2;
let musicVolume = 0.5;
let musicTracks = [];
let musicInitialized = false;

// Media upload variables
let selectedMedia = null;
let mediaAnalysis = null;
let mediaType = null;

const video = document.getElementById('avatarVideo');
const videoBackground = document.getElementById('videoBackground');
const staticBackground = document.getElementById('staticBackground');
const userAvatar = document.querySelector('.static-background').style.backgroundImage.includes('girl') ? 'girl' : 'boy';

video.pause();
video.currentTime = 0;

// ===== MEDIA UPLOAD FUNCTIONS =====
function handleMediaSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    selectedMedia = file;
    
    // Determine media type
    if (file.type.startsWith('image/')) {
        mediaType = 'image';
        document.getElementById('mediaPreviewIcon').textContent = '📷';
    } else if (file.type.startsWith('video/')) {
        mediaType = 'video';
        document.getElementById('mediaPreviewIcon').textContent = '🎥';
    }
    
    // Show preview
    document.getElementById('mediaPreview').style.display = 'block';
    document.getElementById('mediaPreviewName').textContent = file.name;
    document.getElementById('mediaPreviewSize').textContent = formatFileSize(file.size);
    
    // Focus on message input
    document.getElementById('messageInput').focus();
}

function clearMediaSelection() {
    selectedMedia = null;
    mediaAnalysis = null;
    mediaType = null;
    document.getElementById('mediaPreview').style.display = 'none';
    document.getElementById('mediaInput').value = '';
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

async function uploadAndAnalyzeMedia(message) {
    if (!selectedMedia) return null;
    
    const formData = new FormData();
    formData.append('media', selectedMedia);
    formData.append('message', message);
    
    try {
        const response = await fetch('/api/upload-media', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to upload media');
        }
        
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Media upload error:', error);
        throw error;
    }
}

// ===== MUSIC FUNCTIONS =====
async function loadMusicTracks() {
    try {
        const response = await fetch('/api/music-list');
        musicTracks = await response.json();
        console.log('Music tracks loaded:', musicTracks);
    } catch (error) {
        console.error('Failed to load music tracks:', error);
        musicTracks = [
            {'id': 1, 'name': 'Lofi Beats 1', 'url': 'https://res.cloudinary.com/dbiamsdnr/video/upload/Chill_Lofi_Beats_By_Art_Is_Sound_1_x131mw.mp3'},
            {'id': 2, 'name': 'Lofi Beats 2', 'url': 'https://res.cloudinary.com/dbiamsdnr/video/upload/Chill_Lofi_Beats_By_Art_Is_Sound_2_ta1t9m.mp3'},
            {'id': 3, 'name': 'Lofi Beats 3', 'url': 'https://res.cloudinary.com/dbiamsdnr/video/upload/Chill_Lofi_Beats_By_Art_Is_Sound_3_lsq9ek.mp3'},
            {'id': 4, 'name': 'Lofi Beats 4', 'url': 'https://res.cloudinary.com/dbiamsdnr/video/upload/Chill_Lofi_Beats_By_Art_Is_Sound_4_qejsjt.mp3'},
            {'id': 5, 'name': 'Lofi Beats 5', 'url': 'https://res.cloudinary.com/dbiamsdnr/video/upload/Chill_Lofi_Beats_By_Art_Is_Sound_5_lmbywm.mp3'}
        ];
    }
}

async function loadUserMusicPreferences() {
    try {
        const response = await fetch('/api/user-music-preference');
        const preferences = await response.json();
        
        musicEnabled = preferences.music_enabled;
        currentTrack = preferences.current_track || 2;
        musicVolume = preferences.volume;
        
        document.getElementById('musicToggle').checked = musicEnabled;
        document.getElementById('musicTrackSelect').value = currentTrack;
        document.getElementById('musicVolume').value = musicVolume;
        
        if (musicEnabled && !musicInitialized) {
            initializeMusic();
        }
        
    } catch (error) {
        console.error('Failed to load music preferences:', error);
        if (!musicInitialized) {
            initializeMusic();
        }
    }
}

function initializeMusic() {
    if (musicInitialized) return;
    
    if (!musicTracks.length) {
        console.log('No music tracks available yet');
        return;
    }
    
    const track = musicTracks.find(t => t.id === currentTrack) || musicTracks[0];
    backgroundMusic.src = track.url;
    backgroundMusic.volume = musicVolume;
    
    backgroundMusic.addEventListener('loadeddata', function() {
        console.log('Music loaded, attempting to play...');
        playBackgroundMusic();
    });
    
    backgroundMusic.addEventListener('canplaythrough', function() {
        console.log('Music can play through');
        playBackgroundMusic();
    });
    
    backgroundMusic.load();
    musicInitialized = true;
}

function playBackgroundMusic() {
    if (!musicEnabled || !musicInitialized) return;
    
    const playPromise = backgroundMusic.play();
    
    if (playPromise !== undefined) {
        playPromise.then(() => {
            console.log('Music started playing successfully');
        }).catch(error => {
            console.log('Autoplay prevented, waiting for user interaction:', error);
            document.addEventListener('click', startMusicAfterInteraction, { once: true });
            document.addEventListener('keypress', startMusicAfterInteraction, { once: true });
        });
    }
}

function startMusicAfterInteraction() {
    console.log('User interacted, starting music...');
    if (musicEnabled && musicInitialized) {
        backgroundMusic.play().catch(error => {
            console.log('Still cannot play music:', error);
        });
    }
}

function toggleBackgroundMusic() {
    musicEnabled = !musicEnabled;
    
    if (musicEnabled) {
        playBackgroundMusic();
    } else {
        backgroundMusic.pause();
        console.log('Music paused');
    }
    
    saveMusicPreferences();
}

function changeMusicTrack(trackId) {
    currentTrack = parseInt(trackId);
    
    if (musicEnabled) {
        const wasPlaying = !backgroundMusic.paused;
        
        const track = musicTracks.find(t => t.id === currentTrack);
        if (track) {
            backgroundMusic.src = track.url;
            backgroundMusic.volume = musicVolume;
            backgroundMusic.load();
            
            if (wasPlaying) {
                backgroundMusic.play().catch(error => {
                    console.log('Could not play new track:', error);
                });
            }
        }
    }
    
    saveMusicPreferences();
}

function changeMusicVolume(volume) {
    musicVolume = parseFloat(volume);
    backgroundMusic.volume = musicVolume;
    saveMusicPreferences();
}

async function saveMusicPreferences() {
    try {
        await fetch('/api/user-music-preference', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                music_enabled: musicEnabled,
                current_track: currentTrack,
                volume: musicVolume
            })
        });
    } catch (error) {
        console.error('Failed to save music preferences:', error);
    }
}

// ===== VIDEO BACKGROUND FUNCTIONS =====
function showVideoBackground() {
    const video = document.getElementById('avatarVideo');
    video.currentTime = 0;
    video.play();
    videoBackground.classList.add('active');
}

function hideVideoBackground() {
    videoBackground.classList.remove('active');
    setTimeout(() => {
        const video = document.getElementById('avatarVideo');
        video.pause();
        video.currentTime = 0;
    }, 800);
}

// ===== INPUT HANDLING =====
function autoResize(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
}

function handleKeyPress(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
}

// ===== MOOD AND VISUALS =====
function updateMoodVisuals(mood, safeMode) {
    currentMood = mood;
    safeModeActive = safeMode;
    
    if (safeMode) {
        document.body.classList.add('safe-space-mode');
        document.body.style.filter = 'brightness(0.7)';
        staticBackground.style.opacity = '0.5';
    } else {
        document.body.classList.remove('safe-space-mode');
        document.body.style.filter = 'brightness(1)';
        staticBackground.style.opacity = '1';
    }
    
    updateMoodIndicator(mood, safeMode);
}

function updateMoodIndicator(mood, safeMode) {
    const headerInfo = document.querySelector('.header-info p');
    
    if (safeMode) {
        headerInfo.textContent = '🤍 Safe Space Mode Active';
        headerInfo.style.color = '#a8d5ff';
        headerInfo.classList.add('mood-active');
    } else {
        const moodEmojis = {
            'happy': '😊',
            'sad': '💙',
            'anxious': '🫂',
            'angry': '🔥',
            'tired': '😴',
            'confused': '🤔',
            'neutral': '💬'
        };
        headerInfo.textContent = `${moodEmojis[mood] || '💬'} Your personal friend`;
        headerInfo.classList.remove('mood-active');
    }
}

// ===== CALM MODE =====
function activateCalmMode() {
    const overlay = document.createElement('div');
    overlay.className = 'calm-overlay';
    
    overlay.innerHTML = `
        <div class="calm-content">
            <h2 style="font-size: 28px;">Take a Deep Breath</h2>
            <p class="calm-text">Follow the circle as it expands and contracts</p>
            <div class="breathing-circle" id="breathingCircle"></div>
            <p class="calm-text">Breathe in as the circle expands, and out as it contracts</p>
            <button onclick="this.parentElement.parentElement.remove()" style="
                margin-top: 10px;
                padding: 12px 24px;
                background: rgba(70, 70, 70, 0.8);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                color: white;
                cursor: pointer;
                font-size: 16px;
            ">I feel better now</button>
        </div>
    `;
    
    document.body.appendChild(overlay);
}

// ===== MESSAGE HANDLING =====
function addMessage(role, content, hasMedia = false, mediaTypeStr = null) {
    const container = document.getElementById('messagesContainer');
    const welcomeMsg = container.querySelector('.welcome-message');
    if (welcomeMsg) welcomeMsg.remove();

    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = role === 'user' ? '👤' : '🏠';
    
    const content_div = document.createElement('div');
    content_div.className = 'message-content';
    
    // Add media indicator if present
    if (hasMedia && mediaTypeStr) {
        const mediaIndicator = document.createElement('div');
        mediaIndicator.style.cssText = 'display: inline-block; padding: 4px 10px; background: rgba(100,150,200,0.2); border: 1px solid rgba(100,150,200,0.3); border-radius: 6px; margin-bottom: 8px; font-size: 12px; color: #a8d5ff;';
        mediaIndicator.textContent = mediaTypeStr === 'image' ? '📷 Image shared' : '🎥 Video shared';
        content_div.appendChild(mediaIndicator);
        content_div.appendChild(document.createElement('br'));
    }
    
    // ADD THIS CONTENT VALIDATION:
    if (content && content.trim()) {
        const textNode = document.createTextNode(content);
        content_div.appendChild(textNode);
    } else {
        content_div.innerHTML = '<em>Message could not be loaded</em>';
        console.error('Empty content received for message:', { role, content, hasMedia, mediaTypeStr });
    }
    
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(content_div);
    container.appendChild(messageDiv);
    
    container.scrollTop = container.scrollHeight;
    
    // ADD THIS LOGGING:
    console.log(`📨 Added ${role} message:`, content ? content.substring(0, 100) + '...' : 'EMPTY');
}
function showTyping() {
    const container = document.getElementById('messagesContainer');
    const typingDiv = document.createElement('div');
    typingDiv.className = 'message assistant';
    typingDiv.id = 'typingIndicator';
    
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = '🏠';
    
    const typing = document.createElement('div');
    typing.className = 'typing-indicator show';
    typing.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';
    
    typingDiv.appendChild(avatar);
    typingDiv.appendChild(typing);
    container.appendChild(typingDiv);
    container.scrollTop = container.scrollHeight;
}

function hideTyping() {
    const typing = document.getElementById('typingIndicator');
    if (typing) typing.remove();
}

async function sendMessage() {
    if (isTyping) return;

    const input = document.getElementById('messageInput');
    const message = input.value.trim();
    
    if (!message && !selectedMedia) return;

    isTyping = true;
    document.getElementById('sendBtn').disabled = true;
    
    let uploadedMediaData = null;
    let currentMediaAnalysis = null;
    let currentMediaType = null;
    
    // If media is selected, upload and analyze it first
    if (selectedMedia) {
        showTyping();
        try {
            uploadedMediaData = await uploadAndAnalyzeMedia(message || "What do you think about this?");
            hideTyping();
            
            currentMediaAnalysis = uploadedMediaData.analysis;
            currentMediaType = uploadedMediaData.media_type;
            
            addMessage('user', message || "What do you think about this?", true, currentMediaType);
            clearMediaSelection();
            
        } catch (error) {
            hideTyping();
            addMessage('assistant', `Sorry, I had trouble analyzing your ${mediaType || 'media'}. ${error.message}`);
            isTyping = false;
            document.getElementById('sendBtn').disabled = false;
            clearMediaSelection();
            return;
        }
    } else {
        // Regular text message
        addMessage('user', message);
    }
    
    input.value = '';
    input.style.height = 'auto';
    
    showVideoBackground();
    if (videoTimeout) clearTimeout(videoTimeout);
    showTyping();

    const startTime = Date.now();
    const minDelay = 4000;

    try {
        console.log('📤 Sending message to API...');
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                message: message || "What do you think about this?",
                media_analysis: currentMediaAnalysis,
                media_type: currentMediaType
            })
        });

        console.log('📥 API response status:', response.status);
                const data = await response.json();
        
        // ADD THIS LOGGING:
        console.log('📥 API response status:', response.status);
        console.log('📥 API response data:', data);
        
        const elapsed = Date.now() - startTime;
        const remainingDelay = Math.max(0, minDelay - elapsed);
        
        setTimeout(() => {
            hideTyping();
            
            if (response.ok) {
                // ADD THIS VALIDATION:
                if (data.response && data.response.trim()) {
                    console.log('✅ Adding AI response to chat');
                    addMessage('assistant', data.response);
                    
                    if (data.mood) {
                        updateMoodVisuals(data.mood, data.safe_space_mode);
                    }
                    
                    if (data.safe_space_mode) {
                        setTimeout(() => {
                            if (confirm('I sense you might be feeling overwhelmed. Would you like to try a calming breathing exercise?')) {
                                activateCalmMode();
                            }
                        }, 1000);
                    }
                } else {
                    // ADD THIS ERROR HANDLING:
                    console.error('❌ Empty AI response received:', data);
                    addMessage('assistant', "I'm here, but I'm having trouble responding right now. Please try again.");
                }
            } else {
                // ENHANCE THIS ERROR MESSAGE:
                console.error('❌ API error:', data);
                addMessage('assistant', `Sorry, I encountered an error: ${data.error || 'Unknown error'}`);
            }
            
            videoTimeout = setTimeout(hideVideoBackground, 500);
            isTyping = false;
            document.getElementById('sendBtn').disabled = false;
            input.focus();
        }, remainingDelay);
        
    } catch (error) {
        console.error('❌ Network error:', error);
        const elapsed = Date.now() - startTime;
        const remainingDelay = Math.max(0, minDelay - elapsed);
        
        setTimeout(() => {
            hideTyping();
            addMessage('assistant', 'Oops, connection issue. Can you try again?');
            videoTimeout = setTimeout(hideVideoBackground, 500);
            isTyping = false;
            document.getElementById('sendBtn').disabled = false;
            input.focus();
        }, remainingDelay);
    }
}

// ===== HISTORY AND SESSION =====
async function loadHistory() {
    try {
        const response = await fetch('/api/history');
        const history = await response.json();
        
        const container = document.getElementById('messagesContainer');
        const welcomeMsg = container.querySelector('.welcome-message');
        
        if (history.length > 0 && welcomeMsg) {
            welcomeMsg.remove();
        }
        
        history.forEach(msg => {
            const hasMedia = msg.media_type !== null && msg.media_type !== undefined;
            addMessage(msg.role, msg.content, hasMedia, msg.media_type);
        });
    } catch (error) {
        console.error('Failed to load history:', error);
    }
}

async function loadGreeting() {
    try {
        const response = await fetch('/api/greeting');
        const data = await response.json();
        
        const welcomeMsg = document.querySelector('.welcome-message');
        if (welcomeMsg && !document.querySelector('.message')) {
            welcomeMsg.querySelector('h3').textContent = data.greeting;
            welcomeMsg.querySelector('p').textContent = data.message;
        }
    } catch (error) {
        console.log('Could not load greeting');
    }
}

async function clearHistory() {
    if (!confirm('Clear all conversation history? This cannot be undone.')) return;

    try {
        await fetch('/api/clear-history', { method: 'POST' });
        location.reload();
    } catch (error) {
        alert('Failed to clear history');
    }
}

function logout() {
    window.location.href = '/logout';
}

// ===== JOURNAL FUNCTIONS =====
async function openJournal() {
    document.getElementById('journalModal').style.display = 'block';
    await loadJournalEntries();
}

function closeJournal() {
    document.getElementById('journalModal').style.display = 'none';
}

function setJournalPrompt(type) {
    const prompts = {
        'gratitude': "Today I'm grateful for: ",
        'win': "Today's win: ",
        'challenge': "A challenge I faced today: ",
        'lesson': "Something I learned today: "
    };
    
    const textarea = document.getElementById('journalContent');
    textarea.value = prompts[type] || '';
    textarea.focus();
}

async function saveJournalEntry() {
    const content = document.getElementById('journalContent').value.trim();
    const mood = document.getElementById('journalMood').value;
    
    if (!content) {
        alert('Please write something in your journal entry.');
        return;
    }

    try {
        const response = await fetch('/api/journal', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content, mood })
        });

        if (response.ok) {
            document.getElementById('journalContent').value = '';
            document.getElementById('journalMood').value = '';
            await loadJournalEntries();
        } else {
            alert('Failed to save journal entry');
        }
    } catch (error) {
        alert('Failed to save journal entry');
    }
}

async function loadJournalEntries() {
    try {
        const response = await fetch('/api/journal');
        const entries = await response.json();
        
        const container = document.getElementById('journalEntriesList');
        container.innerHTML = '<h3 style="color: #f0f0f0; margin-bottom: 15px;">Recent Entries</h3>';
        
        if (entries.length === 0) {
            container.innerHTML += '<p style="color: rgba(240,240,240,0.7); text-align: center; padding: 20px;">No journal entries yet</p>';
            return;
        }
        
        entries.forEach(entry => {
            const entryDiv = document.createElement('div');
            entryDiv.style.padding = '15px';
            entryDiv.style.marginBottom = '10px';
            entryDiv.style.background = 'rgba(50,50,50,0.5)';
            entryDiv.style.borderRadius = '8px';
            entryDiv.style.borderLeft = '3px solid rgba(100,150,200,0.5)';
            
            const date = new Date(entry.timestamp).toLocaleDateString();
            const moodEmojis = {
                'amazing': '😊', 'good': '🙂', 'okay': '😐', 
                'stressed': '😰', 'sad': '😢', 'tired': '😴'
            };
            
            entryDiv.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <span style="color: rgba(240,240,240,0.7); font-size: 14px;">${date}</span>
                    ${entry.mood ? `<span style="margin-left: auto;">${moodEmojis[entry.mood] || ''}</span>` : ''}
                </div>
                <p style="color: #f0f0f0; line-height: 1.5;">${entry.content}</p>
            `;
            
            container.appendChild(entryDiv);
        });
    } catch (error) {
        console.error('Failed to load journal entries:', error);
    }
}

// ===== REMINDER FUNCTIONS =====
async function openReminders() {
    document.getElementById('remindersModal').style.display = 'block';
    await loadReminders();
}

function closeReminders() {
    document.getElementById('remindersModal').style.display = 'none';
}

function setReminderTemplate(type) {
    const templates = {
        'hydration': 'Drink a glass of water 💧',
        'stretch': 'Take a break and stretch 🧘',
        'medication': 'Take your medication 💊',
        'meeting': 'Meeting starting soon 📅'
    };
    
    document.getElementById('reminderTitle').value = templates[type] || '';
}

async function saveReminder() {
    const title = document.getElementById('reminderTitle').value.trim();
    const date = document.getElementById('reminderDate').value;
    const time = document.getElementById('reminderTime').value;
    const repeat = document.getElementById('reminderRepeat').value;
    
    if (!title || !date || !time) {
        alert('Please fill in all reminder details.');
        return;
    }

    try {
        const response = await fetch('/api/reminders', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, date, time, repeat })
        });

        if (response.ok) {
            document.getElementById('reminderTitle').value = '';
            document.getElementById('reminderDate').value = '';
            document.getElementById('reminderTime').value = '';
            await loadReminders();
        } else {
            alert('Failed to save reminder');
        }
    } catch (error) {
        alert('Failed to save reminder');
    }
}

async function loadReminders() {
    try {
        const response = await fetch('/api/reminders');
        const reminders = await response.json();
        
        const container = document.getElementById('remindersList');
        container.innerHTML = '<h3 style="color: #f0f0f0; margin-bottom: 15px;">Upcoming Reminders</h3>';
        
        if (reminders.length === 0) {
            container.innerHTML += '<p style="color: rgba(240,240,240,0.7); text-align: center; padding: 20px;">No reminders set</p>';
            return;
        }
        
        reminders.forEach(reminder => {
            const reminderDiv = document.createElement('div');
            reminderDiv.style.padding = '15px';
            reminderDiv.style.marginBottom = '10px';
            reminderDiv.style.background = 'rgba(50,50,50,0.5)';
            reminderDiv.style.borderRadius = '8px';
            reminderDiv.style.borderLeft = '3px solid rgba(255,180,100,0.5)';
            reminderDiv.style.display = 'flex';
            reminderDiv.style.justifyContent = 'space-between';
            reminderDiv.style.alignItems = 'center';
            
            const date = new Date(`${reminder.date}T${reminder.time}`);
            const now = new Date();
            const isOverdue = date < now;
            
            reminderDiv.innerHTML = `
                <div>
                    <div style="color: #f0f0f0; font-weight: 500; margin-bottom: 5px;">${reminder.title}</div>
                    <div style="color: rgba(240,240,240,0.7); font-size: 14px;">
                        ${date.toLocaleString()} ${isOverdue ? '<span style="color: #ff6b6b;">(Overdue)</span>' : ''}
                    </div>
                </div>
                <button onclick="deleteReminder(${reminder.id})" style="
                    background: rgba(255,100,100,0.2);
                    border: 1px solid rgba(255,100,100,0.3);
                    border-radius: 6px;
                    color: #ff6b6b;
                    padding: 6px 12px;
                    cursor: pointer;
                    font-size: 13px;
                ">Delete</button>
            `;
            
            container.appendChild(reminderDiv);
        });
    } catch (error) {
        console.error('Failed to load reminders:', error);
    }
}

async function deleteReminder(id) {
    if (!confirm('Delete this reminder?')) return;
    
    try {
        const response = await fetch(`/api/reminders/${id}`, { method: 'DELETE' });
        if (response.ok) {
            await loadReminders();
        } else {
            alert('Failed to delete reminder');
        }
    } catch (error) {
        alert('Failed to delete reminder');
    }
}

// ===== PROFILE DROPDOWN =====
function toggleProfileDropdown() {
    const dropdown = document.getElementById('profileDropdown');
    dropdown.classList.toggle('show');
}

function setupDropdownItems() {
    const dropdownItems = document.querySelectorAll('.dropdown-item:not(.music-controls):not(.music-track):not(.music-volume)');
    dropdownItems.forEach(item => {
        item.addEventListener('click', () => {
            document.getElementById('profileDropdown').classList.remove('show');
        });
    });
}

document.addEventListener('click', function(event) {
    const dropdown = document.getElementById('profileDropdown');
    const profileBtn = document.querySelector('.profile-btn');
    const isMusicControl = event.target.closest('.music-controls') || 
                          event.target.closest('.music-track') || 
                          event.target.closest('.music-volume') ||
                          event.target.matches('#musicToggle') ||
                          event.target.matches('#musicTrackSelect') ||
                          event.target.matches('#musicVolume');
    
    if (!profileBtn.contains(event.target) && !dropdown.contains(event.target) && !isMusicControl) {
        dropdown.classList.remove('show');
    }
});

// ===== INITIALIZATION =====
document.addEventListener('DOMContentLoaded', async () => {
    console.log('🚀 Initializing Homie AI...');
    
    // Check database health first
    await checkDatabaseHealth();
    
    loadGreeting();
    loadHistory();
    
    loadMusicTracks().then(() => {
        loadUserMusicPreferences();
    });
    
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('reminderDate').value = today;
    
    const nextHour = new Date();
    nextHour.setHours(nextHour.getHours() + 1);
    nextHour.setMinutes(0);
    document.getElementById('reminderTime').value = `${nextHour.getHours().toString().padStart(2, '0')}:00`;
    
    setupDropdownItems();
});

// Add this function to check database health
async function checkDatabaseHealth() {
    try {
        const response = await fetch('/api/database-health');
        const health = await response.json();
        console.log('🩺 Database Health:', health);
        
        if (health.status === 'healthy') {
            console.log(`✅ Database connected (${health.database_type})`);
            console.log(`📊 Tables:`, health.tables);
            return true;
        } else {
            console.error('❌ Database health check failed:', health.error);
            return false;
        }
    } catch (error) {
        console.error('❌ Failed to check database health:', error);
        return false;
    }
}
