// Background music for welcome page
let welcomeMusic = document.getElementById('backgroundMusic');
let welcomeMusicEnabled = true;

function initializeWelcomeMusic() {
    const trackUrl = 'https://res.cloudinary.com/dbiamsdnr/video/upload/Chill_Lofi_Beats_By_Art_Is_Sound_2_ta1t9m.mp3';
    
    welcomeMusic.src = trackUrl;
    welcomeMusic.volume = 0.5;
    welcomeMusic.loop = true;
    
    // Wait for user interaction to play
    const playMusic = () => {
        if (welcomeMusicEnabled) {
            welcomeMusic.play().then(() => {
                console.log('Welcome page music started');
            }).catch(error => {
                console.log('Welcome page music autoplay prevented');
            });
        }
    };
    
    // Try to play immediately (might work in some browsers)
    playMusic();
    
    // Also set up interaction-based play
    document.addEventListener('click', function startMusicOnInteraction() {
        playMusic();
        document.removeEventListener('click', startMusicOnInteraction);
    }, { once: true });
}

// Avatar selection functionality
function initializeAvatarSelection() {
    const avatarOptions = document.querySelectorAll('input[name="avatar"]');
    const avatarPreviews = document.querySelectorAll('.avatar-preview');
    
    avatarOptions.forEach((option, index) => {
        option.addEventListener('change', function() {
            // Update all preview borders
            avatarPreviews.forEach(preview => {
                preview.style.borderColor = 'rgba(255,255,255,0.1)';
            });
            
            // Update label text colors
            document.querySelectorAll('.avatar-option span').forEach(span => {
                span.style.color = 'rgba(240,240,240,0.7)';
            });
            
            // Highlight selected
            if (this.checked) {
                const preview = this.closest('.avatar-option').querySelector('.avatar-preview');
                const label = this.closest('.avatar-option').querySelector('span');
                preview.style.borderColor = 'rgba(255,255,255,0.8)';
                label.style.color = '#f0f0f0';
            }
        });
    });
    
    // Initialize first option as selected
    if (avatarOptions[0]) {
        avatarOptions[0].checked = true;
        const firstPreview = avatarOptions[0].closest('.avatar-option').querySelector('.avatar-preview');
        const firstLabel = avatarOptions[0].closest('.avatar-option').querySelector('span');
        firstPreview.style.borderColor = 'rgba(255,255,255,0.8)';
        firstLabel.style.color = '#f0f0f0';
    }
}

function showLogin() {
    document.getElementById('welcomeScreen').classList.add('hidden');
    document.getElementById('signupForm').classList.remove('active');
    document.getElementById('loginForm').classList.add('active');
}

function showSignup() {
    document.getElementById('welcomeScreen').classList.add('hidden');
    document.getElementById('loginForm').classList.remove('active');
    document.getElementById('signupForm').classList.add('active');
}

function showError(elementId, message) {
    const errorEl = document.getElementById(elementId);
    errorEl.textContent = message;
    errorEl.classList.add('show');
    setTimeout(() => errorEl.classList.remove('show'), 4000);
}

async function handleLogin(e) {
    e.preventDefault();
    const btn = document.getElementById('loginBtn');
    const originalText = btn.innerHTML;
    btn.innerHTML = 'Logging in... <span class="loading"></span>';
    btn.disabled = true;

    const email = document.getElementById('loginEmail').value;
    const password = document.getElementById('loginPassword').value;

    try {
        const response = await fetch('/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });

        const data = await response.json();

        if (response.ok) {
            window.location.href = '/chat';
        } else {
            showError('loginError', data.error || 'Login failed');
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    } catch (error) {
        showError('loginError', 'Connection error. Please try again.');
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

async function handleSignup(e) {
    e.preventDefault();
    const btn = document.getElementById('signupBtn');
    const originalText = btn.innerHTML;
    btn.innerHTML = 'Creating... <span class="loading"></span>';
    btn.disabled = true;

    const username = document.getElementById('signupUsername').value;
    const email = document.getElementById('signupEmail').value;
    const password = document.getElementById('signupPassword').value;
    const avatar = document.querySelector('input[name="avatar"]:checked').value;

    try {
        const response = await fetch('/signup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, email, password, avatar })
        });

        const data = await response.json();

        if (response.ok) {
            window.location.href = '/chat';
        } else {
            showError('signupError', data.error || 'Signup failed');
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    } catch (error) {
        showError('signupError', 'Connection error. Please try again.');
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

// Initialize everything when page loads
document.addEventListener('DOMContentLoaded', function() {
    initializeWelcomeMusic();
    initializeAvatarSelection();
});