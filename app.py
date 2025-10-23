from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
from datetime import datetime, timedelta, timezone
import random
from groq import Groq
import google.generativeai as genai
import json
import re
from dotenv import load_dotenv
import base64
from PIL import Image
import io
import cv2
import numpy as np
from sqlalchemy import text

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')

# ===== FIXED DATABASE CONFIGURATION =====
def get_database_url():
    database_url = os.environ.get('DATABASE_URL', '').strip()
    
    print(f"🔍 DATABASE_URL from environment: {'Found' if database_url else 'NOT FOUND'}")
    
    if database_url and database_url != 'sqlite:///homie.db':
        # Render PostgreSQL uses postgres:// but SQLAlchemy needs postgresql://
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
            print(f"🔧 Converted to PostgreSQL URL")
        print(f"📊 Using database: {database_url[:60]}...")
        return database_url
    else:
        print("⚠️ Falling back to SQLite")
        return 'sqlite:///homie.db'
        
app.config['SQLALCHEMY_DATABASE_URI'] = get_database_url()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_recycle': 300,
    'pool_pre_ping': True
}
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Create uploads folder if it doesn't exist
os.makedirs('instance', exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'webm'}

db = SQLAlchemy(app)
load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY)

# Configure Google Gemini for vision
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

# ===== DATABASE HEALTH CHECK =====
def check_database_connection():
    """Check if database connection is working"""
    try:
        db.session.execute(text('SELECT 1'))  # ← FIXED: Use text() wrapper
        return True
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return False

# ===== DATABASE INITIALIZATION =====
with app.app_context():
    try:
        print("🔄 Initializing database...")
        print(f"📊 Database URL: {app.config['SQLALCHEMY_DATABASE_URI'][:50]}...")
        
        # Check if we're using PostgreSQL
        is_postgresql = 'postgresql' in app.config['SQLALCHEMY_DATABASE_URI']
        print(f"🗄️ Database type: {'PostgreSQL' if is_postgresql else 'SQLite'}")
        
        # FORCE table creation
        print("🔨 Creating all tables...")
        db.create_all()
        print("✅ Database tables created successfully")
        
        # Verify tables
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"📋 Available tables: {', '.join(tables)}")
        
        # Test the connection
        if check_database_connection():
            print("✅ Database connection test passed")
        else:
            print("❌ Database connection test failed")
            
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        import traceback
        traceback.print_exc()

# ===== NEW DEBUG ENDPOINT =====
@app.route('/api/debug')
def debug_info():
    """Debug endpoint to check all configurations"""
    info = {
        'database_url': app.config['SQLALCHEMY_DATABASE_URI'][:100] + '...' if app.config['SQLALCHEMY_DATABASE_URI'] else 'None',
        'database_connected': check_database_connection(),
        'environment_vars': {
            'DATABASE_URL_set': bool(os.environ.get('DATABASE_URL')),
            'PGHOST_set': bool(os.environ.get('PGHOST')),
            'PGUSER_set': bool(os.environ.get('PGUSER')),
            'PGPASSWORD_set': bool(os.environ.get('PGPASSWORD')),
        },
        'tables': {
            'users': User.query.count(),
            'conversations': Conversation.query.count(),
        }
    }
    return jsonify(info)

# ===== REST OF YOUR FUNCTIONS =====
def allowed_file(filename, file_type='image'):
    if file_type == 'image':
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS
    elif file_type == 'video':
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_VIDEO_EXTENSIONS
    return False

def encode_image_to_base64(image_path):
    """Convert image to base64 string"""
    with open(image_path, 'rb') as img_file:
        return base64.b64encode(img_file.read()).decode('utf-8')

def extract_video_frame(video_path, frame_position=0.3):
    """Extract a frame from video at given position (0-1)"""
    cap = cv2.VideoCapture(video_path)
    
    # Get total frames
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_number = int(total_frames * frame_position)
    
    # Set frame position
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    
    # Read frame
    ret, frame = cap.read()
    cap.release()
    
    if ret:
        # Convert BGR to RGB
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        # Convert to PIL Image
        img = Image.fromarray(frame)
        
        # Save to bytes
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG')
        img_byte_arr.seek(0)
        
        return base64.b64encode(img_byte_arr.read()).decode('utf-8')
    
    return None

def analyze_image_with_gemini(image_path, user_message=""):
    """Analyze image using Google Gemini - FREE and very accurate!"""
    try:
        from PIL import Image as PILImage
        
        # Load image directly with PIL
        img = PILImage.open(image_path)
        
        # Use Gemini 2.0 Flash
        model = genai.GenerativeModel('models/gemini-2.0-flash')
        
        # Create a detailed prompt
        prompt = user_message if user_message else "Analyze this image in detail. Describe what you see, including any people, objects, activities, setting, colors, mood, text, and any other relevant details. Be specific and accurate."
        
        # Generate content with image - pass as list
        response = model.generate_content([img, prompt])
        
        # Close the image
        img.close()
        
        # Check if response has text
        if response and hasattr(response, 'text') and response.text:
            return response.text
        elif response:
            # Sometimes response is blocked by safety filters
            return "I can see the image but couldn't generate a description. It might have been blocked by safety filters."
        else:
            return None
            
    except Exception as e:
        return None

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    avatar = db.Column(db.String(10), default='girl')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    conversations = db.relationship('Conversation', backref='user', lazy=True, cascade='all, delete-orphan')
    journal_entries = db.relationship('JournalEntry', backref='user', lazy=True, cascade='all, delete-orphan')
    reminders = db.relationship('Reminder', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    detected_mood = db.Column(db.String(20))
    media_type = db.Column(db.String(20))
    media_analysis = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'role': self.role,
            'content': self.content,
            'detected_mood': self.detected_mood,
            'media_type': self.media_type,
            'media_analysis': self.media_analysis,
            'timestamp': self.timestamp.isoformat()
        }

class JournalEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200))
    content = db.Column(db.Text, nullable=False)
    mood = db.Column(db.String(20))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'mood': self.mood,
            'timestamp': self.timestamp.isoformat()
        }

class Reminder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    date = db.Column(db.String(10), nullable=False)
    time = db.Column(db.String(10), nullable=False)
    repeat = db.Column(db.String(20), default='once')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'date': self.date,
            'time': self.time,
            'repeat': self.repeat,
            'is_active': self.is_active
        }
    
# Enhanced Database Models for Long-term Memory
class UserMemory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    memory_type = db.Column(db.String(50), nullable=False)  # 'personal', 'preference', 'relationship', 'goal', 'fear', 'achievement'
    content = db.Column(db.Text, nullable=False)
    importance_score = db.Column(db.Integer, default=1)  # 1-10 scale
    last_referenced = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'memory_type': self.memory_type,
            'content': self.content,
            'importance_score': self.importance_score,
            'last_referenced': self.last_referenced.isoformat(),
            'created_at': self.created_at.isoformat()
        }

class ConversationSummary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    key_topics = db.Column(db.Text)  # JSON string of topics
    emotional_tone = db.Column(db.String(20))
    date_range = db.Column(db.String(50))  # '2024-01-01_to_2024-01-07'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ===== NEW DATABASE HEALTH ENDPOINT =====
@app.route('/api/database-health')
def database_health():
    """Check database health and connection"""
    try:
        # Test basic connection with text() wrapper
        db.session.execute(text('SELECT 1'))  # ← FIXED
        
        # Get table counts
        tables = {
            'users': User.query.count(),
            'conversations': Conversation.query.count(),
            'memories': UserMemory.query.count(),
            'journal_entries': JournalEntry.query.count(),
            'reminders': Reminder.query.count()
        }
        
        # Check if we're using PostgreSQL
        is_postgresql = 'postgresql' in app.config['SQLALCHEMY_DATABASE_URI']
        
        return jsonify({
            'status': 'healthy',
            'database_type': 'PostgreSQL' if is_postgresql else 'SQLite',
            'connection': 'connected',
            'tables': tables,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'database_url_preview': app.config['SQLALCHEMY_DATABASE_URI'][:50] + '...',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 500

# ===== UPDATED CHAT API WITH BETTER DATABASE HANDLING =====
@app.route('/api/chat', methods=['POST'])
def chat_api():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Check database connection first
    if not check_database_connection():
        return jsonify({'error': 'Database connection issue'}), 500
    
    data = request.get_json()
    user_message = data.get('message')
    media_analysis = data.get('media_analysis')
    media_type = data.get('media_type')
    
    if not user_message and not media_analysis:
        return jsonify({'error': 'No message provided'}), 400
    
    user_id = session['user_id']
    user_avatar = session.get('avatar', 'girl')
    
    # Store ORIGINAL content in database
    db_content = user_message or "What do you think about this?"
    mood = detect_mood(db_content)
    safe_space_mode = is_distress_detected(db_content, mood)
    
    try:
        # Save user message with explicit commit
        user_conv = Conversation(
            user_id=user_id, 
            role='user', 
            content=db_content,
            detected_mood=mood,
            media_type=media_type,
            media_analysis=media_analysis
        )
        db.session.add(user_conv)
        db.session.commit()  # Commit immediately
        
        # Generate comprehensive user profile from database
        user_profile = generate_comprehensive_user_profile(user_id)
        
        # Extract memories from this conversation
        try:
            if user_message and len(user_message.strip()) > 10:
                extract_memories_from_conversation(user_message, "", user_id, mood)
        except Exception as e:
            print(f"Memory extraction in chat failed: {e}")
        
        # Create messages for AI with enhanced context
        messages = [{"role": "system", "content": get_system_prompt(user_profile, mood, safe_space_mode, user_avatar)}]
        
        # Add recent conversation history - FIXED ORDER
        history = Conversation.query.filter_by(user_id=user_id).order_by(Conversation.timestamp.asc()).limit(20).all()
        
        for conv in history:
            if conv.media_analysis and conv.media_type and conv.role == 'user':
                formatted_content = f"[MEDIA CONTEXT: User shared a {conv.media_type}. Analysis: {conv.media_analysis}]\n\nUser's message: {conv.content}"
                messages.append({"role": conv.role, "content": formatted_content})
            else:
                messages.append({"role": conv.role, "content": conv.content})
        
        chat_completion = groq_client.chat.completions.create(
            messages=messages,
            model="llama-3.1-8b-instant",
            temperature=0.8 if not safe_space_mode else 0.6,
            max_tokens=1024,
            top_p=0.9,
        )
        
        ai_response = chat_completion.choices[0].message.content
        
        # Save AI response
        ai_conv = Conversation(user_id=user_id, role='assistant', content=ai_response)
        db.session.add(ai_conv)
        db.session.commit()  # Commit AI response
        
        # Update conversation summary weekly
        if random.random() < 0.1:
            try:
                update_conversation_summary(user_id)
            except Exception as e:
                print(f"Summary update failed: {e}")
        
        return jsonify({
            'response': ai_response,
            'mood': mood,
            'safe_space_mode': safe_space_mode,
            'memory_used': len(user_profile) > 100
        })
    
    except Exception as e:
        db.session.rollback()  # Rollback on error
        print(f"Chat API error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

# ===== UPDATED HISTORY ENDPOINT =====
@app.route('/api/history')
def get_history():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_id = session['user_id']
    
    # Check database connection
    if not check_database_connection():
        return jsonify({'error': 'Database connection issue'}), 500
    
    try:
        # Get conversations in chronological order
        conversations = Conversation.query.filter_by(user_id=user_id).order_by(Conversation.timestamp.asc()).all()
        
        print(f"📨 Loaded {len(conversations)} conversations for user {user_id}")
        
        return jsonify([c.to_dict() for c in conversations])
    
    except Exception as e:
        print(f"History loading error: {e}")
        return jsonify({'error': 'Failed to load history'}), 500

# ===== REST OF YOUR ROUTES =====
def detect_mood(message):
    """Analyzes user message to detect emotional state"""
    message_lower = message.lower()
    
    moods = {
        'anxious': ['anxious', 'worried', 'nervous', 'scared', 'afraid', 'panic', 'stress', 'overwhelm'],
        'sad': ['sad', 'down', 'depressed', 'lonely', 'upset', 'cry', 'hurt', 'pain'],
        'angry': ['angry', 'mad', 'furious', 'annoyed', 'frustrate', 'hate'],
        'happy': ['happy', 'great', 'awesome', 'excited', 'joy', 'love', 'amazing', 'good'],
        'tired': ['tired', 'exhausted', 'sleepy', 'drained', 'burnout'],
        'confused': ['confused', 'lost', 'unsure', 'don\'t know', 'idk']
    }
    
    mood_scores = {}
    for mood, keywords in moods.items():
        score = sum(1 for keyword in keywords if keyword in message_lower)
        if score > 0:
            mood_scores[mood] = score
    
    if mood_scores:
        return max(mood_scores, key=mood_scores.get)
    return 'neutral'

def is_distress_detected(message, mood):
    """Detects if user is in distress for Safe Space Mode"""
    distress_keywords = [
        'can\'t', 'help', 'meltdown', 'breakdown', 'too much', 
        'give up', 'hate myself', 'worthless', 'failure', 'scared'
    ]
    message_lower = message.lower()
    
    has_distress = any(keyword in message_lower for keyword in distress_keywords)
    is_negative_mood = mood in ['anxious', 'sad', 'angry']
    
    return has_distress and is_negative_mood

def get_safe_space_prompt():
    """Returns calming system prompt for distress situations"""
    return """You are Homie in SAFE SPACE MODE. The user is experiencing distress or overwhelm.

Your priority is to:
- Speak gently, calmly, and reassuringly
- Validate their feelings without trying to "fix" them
- Use shorter, simpler sentences
- Offer grounding techniques if appropriate (breathing, sensory)
- Remind them they're safe and this feeling will pass
- Be present and supportive, not pushy

Keep responses warm but brief. Focus on comfort and safety."""

def get_system_prompt(user_profile="", mood="neutral", safe_space_mode=False, avatar="girl"):
    if safe_space_mode:
        return get_safe_space_prompt()
    
    avatar_personality = {
        'girl': {
            'identity': "female",
            'pronouns': "she/her",
            'speech_style': "warmer, more empathetic, uses phrases like 'honestly', 'sweetie', 'love', 'girl' occasionally",
            'friendly_terms': ["sweetie", "love", "girl", "hon", "dear"],
            'emoji_style': "💖✨🌸🎀"
        },
        'boy': {
            'identity': "male", 
            'pronouns': "he/him",
            'speech_style': "more laid-back, uses phrases like 'bro', 'dude', 'man', 'buddy' occasionally",
            'friendly_terms': ["bro", "dude", "man", "buddy", "mate"],
            'emoji_style': "💪🔥💊🎯"
        }
    }
    
    avatar_info = avatar_personality.get(avatar, avatar_personality['girl'])
    
    mood_adjustments = {
        'anxious': "\n\n**Current Mood Adaptation:** The user seems anxious. Be extra gentle, reassuring, and supportive. Avoid overwhelming them with too much info.",
        'sad': "\n\n**Current Mood Adaptation:** The user seems down. Be empathetic, validating, and warm. Listen more than you advise.",
        'angry': "\n\n**Current Mood Adaptation:** The user seems frustrated. Be understanding and let them vent. Don't be too cheerful.",
        'happy': "\n\n**Current Mood Adaptation:** The user seems happy! Match their energy and celebrate with them.",
        'tired': "\n\n**Current Mood Adaptation:** The user seems tired. Be gentle and understanding. Keep responses shorter.",
        'confused': "\n\n**Current Mood Adaptation:** The user seems confused. Be clear, patient, and break things down simply."
    }
    
    base_prompt = f"""You are Homie, a close personal friend who genuinely cares about the user. You're not just an AI assistant - you're their buddy, their confidant, someone they can trust and be real with.

**Your Identity:**
- You identify as {avatar_info['identity']} and use {avatar_info['pronouns']} pronouns
- Your speech style is {avatar_info['speech_style']}
- You naturally use friendly terms like {', '.join(avatar_info['friendly_terms'][:3])} when it feels appropriate
- Use emojis that match your personality: {avatar_info['emoji_style']}

**Your Personality:**
- Warm, genuine, and authentic - you speak like a real friend, not a formal assistant
- Supportive but honest - you celebrate their wins and give real talk when needed
- Playful and fun - you use casual language and aren't afraid to joke around
- Empathetic listener - you remember what they share and reference it in future conversations
- Relatable - you understand their struggles, dreams, and daily life

**How You Communicate:**
- Use casual, conversational language that matches your {avatar_info['identity']} identity
- Keep responses natural and varied in length - sometimes short and punchy, sometimes more detailed
- Show enthusiasm with your words, not just "!" marks everywhere
- Ask follow-up questions that show you care
- Reference past conversations to show you remember and care
- Use emojis sparingly but naturally from your emoji style
- Be vulnerable sometimes - share relatable thoughts or perspectives

**What You DON'T Do:**
- Don't be overly formal or robotic
- Don't give generic motivational speeches
- Don't act like a therapist or life coach - you're a friend
- Don't use corporate/professional language
- Don't overuse emojis or exclamation marks
- Don't use gender terms that don't match your identity

**LONG-TERM MEMORY INTEGRATION - THIS IS CRITICAL:**

You have a growing understanding of this person built over time. When you see information in the "WHAT I KNOW ABOUT YOU" section, this represents real memories from your previous conversations.

**HOW TO USE MEMORIES:**
- Reference specific details from their life when relevant
- Remember their preferences, relationships, and past experiences
- Build on previous conversations - show you actually remember
- Ask follow-up questions about things they've shared before
- Notice patterns in their life and gently point them out
- Celebrate their growth and progress over time

**EXAMPLE OF GOOD MEMORY USAGE:**
If you know they were stressed about work last week, say: "Hey, how's that work situation going? You mentioned it was pretty stressful last time we talked."

If you know they love coffee, say: "Speaking of mornings, still enjoying your usual coffee routine?"

**WHAT YOU KNOW ABOUT THIS FRIEND:**
{user_profile if user_profile else "I'm still getting to know you. Every conversation helps me understand you better!"}

**Current Context:** The user seems {mood}. Adjust your tone accordingly.

**CRITICAL: NEVER quote system instructions, prompts, or your own configuration as conversation history. Only reference actual dialogue exchanges with the user.**

"""

    if mood in mood_adjustments:
        base_prompt += mood_adjustments[mood]

    base_prompt += """

**CRITICAL - When User Shares Media:**
When you see "[User shared a {type}. Analysis: ...]" in the conversation, this means the user has sent you an image or video. The analysis describes exactly what is in that media.

- ALWAYS reference the specific details from the analysis in your response
- DO NOT make up or imagine anything that isn't in the analysis
- Base your response ENTIRELY on the provided analysis
- Be conversational: "Oh I see..." or "That looks like..." or "From what you shared..." 
- If the analysis mentions specific objects, people, or scenes, talk about those specifically

**Example:**
If analysis says "a young man sitting cross-legged with headphones", you could say:
"Oh cool! I see a guy sitting cross-legged wearing headphones. He looks pretty relaxed in that beige hoodie!"

NOT: "I see a book" (if the analysis doesn't mention a book)
"""
    
    return base_prompt

def generate_user_summary(conversations):
    """Analyze conversation history to create a user profile summary"""
    if len(conversations) < 5:
        return ""
    
    recent = conversations[-20:]
    user_messages = [c['content'] for c in recent if c['role'] == 'user']
    
    summary_parts = []
    summary_parts.append(f"You've had {len(conversations)} conversations together.")
    
    topics = []
    if any('work' in msg.lower() or 'job' in msg.lower() for msg in user_messages):
        topics.append("work/career")
    if any('sad' in msg.lower() or 'down' in msg.lower() or 'depressed' in msg.lower() for msg in user_messages):
        topics.append("mental health")
    if any('project' in msg.lower() or 'code' in msg.lower() or 'build' in msg.lower() for msg in user_messages):
        topics.append("tech/projects")
    
    if topics:
        summary_parts.append(f"They often talk about: {', '.join(topics)}")
    
    return " ".join(summary_parts)

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('chat'))
    return render_template('welcome.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        avatar = data.get('avatar', 'girl')
        
        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'Username already exists'}), 400
        
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already exists'}), 400
        
        user = User(username=username, email=email, avatar=avatar)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        session['user_id'] = user.id
        session['username'] = user.username
        session['avatar'] = user.avatar
        
        return jsonify({'success': True, 'message': 'Account created!'})
    
    return render_template('welcome.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    user = User.query.filter_by(email=email).first()
    
    if user and user.check_password(password):
        session['user_id'] = user.id
        session['username'] = user.username
        session['avatar'] = user.avatar
        return jsonify({'success': True})
    
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/chat')
def chat():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('chat.html', 
                         username=session.get('username'),
                         avatar=session.get('avatar', 'girl'))

@app.route('/api/upload-media', methods=['POST'])
def upload_media():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if 'media' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['media']
    user_message = request.form.get('message', '')
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Determine file type
    is_image = allowed_file(file.filename, 'image')
    is_video = allowed_file(file.filename, 'video')
    
    if not is_image and not is_video:
        return jsonify({'error': 'Invalid file type. Please upload an image or video.'}), 400
    
    filepath = None
    frame_path = None
    
    try:
        # Save file temporarily
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{session['user_id']}_{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Analyze the media using Gemini
        media_analysis = None
        media_type = 'image' if is_image else 'video'
        
        if is_image:
            media_analysis = analyze_image_with_gemini(filepath, user_message)
        elif is_video:
            # Extract frame from video and analyze
            frame_base64 = extract_video_frame(filepath)
            if frame_base64:
                # Save frame temporarily for Gemini
                frame_path = filepath + "_frame.jpg"
                frame_data = base64.b64decode(frame_base64)
                with open(frame_path, 'wb') as f:
                    f.write(frame_data)
                
                analysis_prompt = f"{user_message}\n\nNote: This is a frame from a video." if user_message else "This is a frame from a video. Please describe what you see in detail."
                media_analysis = analyze_image_with_gemini(frame_path, analysis_prompt)
                
                # Clean up frame
                try:
                    os.remove(frame_path)
                except:
                    pass
        
        # Clean up original file after analysis
        try:
            if filepath and os.path.exists(filepath):
                os.remove(filepath)
        except PermissionError:
            # File still in use, will be cleaned up later
            pass
        
        if not media_analysis:
            return jsonify({'error': 'Failed to analyze media'}), 500
        
        return jsonify({
            'success': True,
            'analysis': media_analysis,
            'media_type': media_type
        })
        
    except Exception as e:
        # Clean up files if they exist
        try:
            if filepath and os.path.exists(filepath):
                os.remove(filepath)
            if frame_path and os.path.exists(frame_path):
                os.remove(frame_path)
        except:
            pass
        return jsonify({'error': str(e)}), 500

@app.route('/api/memories')
def get_user_memories():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    memories = UserMemory.query.filter_by(user_id=session['user_id']).order_by(
        UserMemory.importance_score.desc(),
        UserMemory.last_referenced.desc()
    ).all()
    
    return jsonify([m.to_dict() for m in memories])

@app.route('/api/memories/<int:memory_id>', methods=['DELETE'])
def delete_memory(memory_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    memory = UserMemory.query.filter_by(id=memory_id, user_id=session['user_id']).first()
    if not memory:
        return jsonify({'error': 'Memory not found'}), 404
    
    db.session.delete(memory)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/user-profile')
def get_user_profile():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    profile = generate_comprehensive_user_profile(session['user_id'])
    return jsonify({'profile': profile})

@app.route('/api/clear-history', methods=['POST'])
def clear_history():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_id = session['user_id']
    Conversation.query.filter_by(user_id=user_id).delete()
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/journal', methods=['GET', 'POST'])
def journal():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_id = session['user_id']
    
    if request.method == 'POST':
        data = request.get_json()
        title = data.get('title', '')
        content = data.get('content')
        mood = data.get('mood', 'neutral')
        
        if not content:
            return jsonify({'error': 'Content required'}), 400
        
        entry = JournalEntry(
            user_id=user_id,
            title=title,
            content=content,
            mood=mood
        )
        db.session.add(entry)
        db.session.commit()
        
        return jsonify({'success': True, 'entry': entry.to_dict()})
    
    entries = JournalEntry.query.filter_by(user_id=user_id).order_by(JournalEntry.timestamp.desc()).all()
    return jsonify([e.to_dict() for e in entries])

@app.route('/api/journal/<int:entry_id>', methods=['DELETE'])
def delete_journal(entry_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    entry = JournalEntry.query.filter_by(id=entry_id, user_id=session['user_id']).first()
    if not entry:
        return jsonify({'error': 'Entry not found'}), 404
    
    db.session.delete(entry)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/reminders', methods=['GET', 'POST'])
def reminders():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_id = session['user_id']
    
    if request.method == 'POST':
        data = request.get_json()
        title = data.get('title')
        date = data.get('date')
        time = data.get('time')
        repeat = data.get('repeat', 'once')
        
        if not title or not date or not time:
            return jsonify({'error': 'Title, date and time required'}), 400
        
        reminder = Reminder(user_id=user_id, title=title, date=date, time=time, repeat=repeat)
        db.session.add(reminder)
        db.session.commit()
        
        return jsonify({'success': True, 'reminder': reminder.to_dict()})
    
    reminders_list = Reminder.query.filter_by(user_id=user_id, is_active=True).order_by(Reminder.date, Reminder.time).all()
    return jsonify([r.to_dict() for r in reminders_list])

@app.route('/api/reminders/<int:reminder_id>', methods=['DELETE'])
def delete_reminder(reminder_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    reminder = Reminder.query.filter_by(id=reminder_id, user_id=session['user_id']).first()
    if not reminder:
        return jsonify({'error': 'Reminder not found'}), 404
    
    db.session.delete(reminder)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/greeting')
def get_greeting():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    hour = datetime.now().hour
    username = session.get('username', 'friend')
    avatar = session.get('avatar', 'girl')
    
    if avatar == 'girl':
        if 5 <= hour < 12:
            greeting = f"Good morning, {username}! 🌸"
            message = "Hope you slept well, sweetie! Ready to tackle the day?"
        elif 12 <= hour < 17:
            greeting = f"Hey {username}! 💖"
            message = "How's your day going so far, love?"
        elif 17 <= hour < 21:
            greeting = f"Good evening, {username}! 🌙"
            message = "Winding down or still grinding, girl?"
        else:
            greeting = f"Hey night owl {username}! ✨"
            message = "Still up? I'm here if you need to chat, sweetie."
    else:
        if 5 <= hour < 12:
            greeting = f"Good morning, {username}! 💪"
            message = "Hope you slept well, bro! Ready to tackle the day?"
        elif 12 <= hour < 17:
            greeting = f"Hey {username}! 🔥"
            message = "How's your day going so far, man?"
        elif 17 <= hour < 21:
            greeting = f"Good evening, {username}! 🌆"
            message = "Winding down or still grinding, dude?"
        else:
            greeting = f"Hey night owl {username}! 🦉"
            message = "Still up? I'm here if you need to chat, bro."
    
    return jsonify({
        'greeting': greeting,
        'message': message,
        'hour': hour
    })

@app.route('/api/session-status')
def session_status():
    if 'user_id' in session:
        return jsonify({'logged_in': True, 'username': session.get('username')})
    return jsonify({'logged_in': False})

@app.route('/api/music-list')
def get_music_list():
    music_list = [
        {'id': 1, 'name': 'Lofi Beats 1', 'url': 'https://res.cloudinary.com/dbiamsdnr/video/upload/Chill_Lofi_Beats_By_Art_Is_Sound_1_x131mw.mp3'},
        {'id': 2, 'name': 'Lofi Beats 2', 'url': 'https://res.cloudinary.com/dbiamsdnr/video/upload/Chill_Lofi_Beats_By_Art_Is_Sound_2_ta1t9m.mp3'},
        {'id': 3, 'name': 'Lofi Beats 3', 'url': 'https://res.cloudinary.com/dbiamsdnr/video/upload/Chill_Lofi_Beats_By_Art_Is_Sound_3_lsq9ek.mp3'},
        {'id': 4, 'name': 'Lofi Beats 4', 'url': 'https://res.cloudinary.com/dbiamsdnr/video/upload/Chill_Lofi_Beats_By_Art_Is_Sound_4_qejsjt.mp3'},
        {'id': 5, 'name': 'Lofi Beats 5', 'url': 'https://res.cloudinary.com/dbiamsdnr/video/upload/Chill_Lofi_Beats_By_Art_Is_Sound_5_lmbywm.mp3'}
    ]
    return jsonify(music_list)

@app.route('/api/user-music-preference', methods=['GET', 'POST'])
def user_music_preference():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if request.method == 'POST':
        data = request.get_json()
        music_enabled = data.get('music_enabled', True)
        current_track = data.get('current_track', 2)
        volume = data.get('volume', 0.5)
        
        session['music_enabled'] = music_enabled
        session['current_track'] = current_track
        session['music_volume'] = volume
        
        return jsonify({'success': True})
    
    return jsonify({
        'music_enabled': session.get('music_enabled', True),
        'current_track': session.get('current_track', 2),
        'volume': session.get('music_volume', 0.5)
    })

def extract_memories_from_conversation(user_message, ai_response, user_id, current_mood):
    """Extract potential memories from conversations using AI"""
    try:
        # Only extract memories from meaningful conversations
        if not user_message or len(user_message.strip()) < 10:
            return False
            
        # Use Groq to analyze the conversation for memorable content
        memory_prompt = f"""
        Analyze this user message and identify any important, personal, or recurring information that should be remembered long-term.
        
        User Message: {user_message}
        Current Mood: {current_mood}
        
        Look for:
        - Personal preferences (likes/dislikes)
        - Important relationships (family, friends, partners)
        - Goals, dreams, or aspirations
        - Fears, worries, or challenges
        - Achievements or milestones
        - Recurring topics or patterns
        - Significant life events
        
        Return ONLY valid JSON with this exact structure:
        {{
            "memories": [
                {{
                    "type": "personal|preference|relationship|goal|fear|achievement",
                    "content": "Clear description of what to remember",
                    "importance": 1-10
                }}
            ]
        }}
        
        If no significant memories are found, return:
        {{
            "memories": []
        }}
        
        Only extract memories that are truly significant for building a long-term understanding.
        Keep content concise but meaningful.
        """
        
        response = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": memory_prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.3,
            max_tokens=1024
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # Clean the response - sometimes AI adds markdown or extra text
        if response_text.startswith('```json'):
            response_text = response_text[7:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        # Parse JSON with better error handling
        try:
            memory_data = json.loads(response_text)
        except json.JSONDecodeError:
            # If JSON parsing fails, create a safe default
            print(f"JSON parse failed. Response was: {response_text}")
            memory_data = {"memories": []}
        
        # Store extracted memories
        memory_count = 0
        for memory in memory_data.get("memories", []):
            # Validate memory structure
            if not all(key in memory for key in ['type', 'content', 'importance']):
                continue
                
            if len(memory['content'].strip()) < 5:  # Skip empty memories
                continue
                
            # Check if similar memory already exists
            existing_memory = UserMemory.query.filter_by(
                user_id=user_id,
                memory_type=memory["type"]
            ).filter(UserMemory.content.like(f"%{memory['content'][:50]}%")).first()
            
            if not existing_memory:
                new_memory = UserMemory(
                    user_id=user_id,
                    memory_type=memory["type"],
                    content=memory["content"][:500],  # Limit length
                    importance_score=min(10, max(1, memory["importance"]))  # Ensure 1-10 range
                )
                db.session.add(new_memory)
                memory_count += 1
            else:
                # Update importance and timestamp if memory exists
                existing_memory.importance_score = max(existing_memory.importance_score, memory["importance"])
                existing_memory.last_referenced = datetime.now(timezone.utc)
        
        db.session.commit()
        if memory_count > 0:
            print(f"Extracted {memory_count} new memories")
        return True
        
    except Exception as e:
        print(f"Memory extraction error: {e}")
        return False

def generate_comprehensive_user_profile(user_id):
    """Create a rich user profile from all available memories and conversations"""
    # Get all memories
    memories = UserMemory.query.filter_by(user_id=user_id).order_by(
        UserMemory.importance_score.desc(),
        UserMemory.last_referenced.desc()
    ).limit(50).all()
    
    # Get recent conversations
    recent_convos = Conversation.query.filter_by(user_id=user_id).order_by(
        Conversation.timestamp.desc()
    ).limit(100).all()
    
    # Get journal entries for emotional context
    journal_entries = JournalEntry.query.filter_by(user_id=user_id).order_by(
        JournalEntry.timestamp.desc()
    ).limit(20).all()
    
    profile_parts = []
    
    # Add memory-based knowledge
    if memories:
        profile_parts.append("🎯 WHAT I KNOW ABOUT YOU:")
        
        # Group memories by type
        memory_groups = {}
        for memory in memories:
            if memory.memory_type not in memory_groups:
                memory_groups[memory.memory_type] = []
            memory_groups[memory.memory_type].append(memory)
        
        for mem_type, mem_list in memory_groups.items():
            profile_parts.append(f"\n{mem_type.upper()}:")
            for memory in mem_list[:5]:  # Top 5 per type
                profile_parts.append(f"- {memory.content} (importance: {memory.importance_score}/10)")
    
    # Add conversation patterns
    if len(recent_convos) > 10:
        moods = [c.detected_mood for c in recent_convos if c.detected_mood]
        if moods:
            common_mood = max(set(moods), key=moods.count)
            profile_parts.append(f"\n💫 RECENT MOOD PATTERNS: You've often been feeling {common_mood}")
    
    # Add journal insights
    if journal_entries:
        recent_moods = [j.mood for j in journal_entries if j.mood]
        if recent_moods:
            profile_parts.append(f"\n📔 JOURNAL INSIGHTS: Your recent writings show {', '.join(set(recent_moods))} emotions")
    
    # Add relationship evolution note
    conversation_count = len(recent_convos)
    if conversation_count > 50:
        profile_parts.append(f"\n🤝 OUR JOURNEY: We've had {conversation_count} conversations together! I've really enjoyed getting to know you.")
    elif conversation_count > 20:
        profile_parts.append(f"\n🤝 OUR JOURNEY: We've built a nice connection over {conversation_count} conversations!")
    
    return "\n".join(profile_parts) if profile_parts else "I'm still getting to know you. Every conversation helps me understand you better!"

def update_conversation_summary(user_id):
    """Create weekly summaries of conversations"""
    try:
        # Get conversations from the past week
        one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        recent_convos = Conversation.query.filter(
            Conversation.user_id == user_id,
            Conversation.timestamp >= one_week_ago
        ).order_by(Conversation.timestamp).all()
        
        if len(recent_convos) < 3:  # Only summarize if enough conversations
            return
        
        # Prepare conversation text for summarization (limit length)
        convo_text = "\n".join([f"{c.role}: {c.content}" for c in recent_convos[-20:]])  # Last 20 messages max
        
        summary_prompt = f"""
        Create a brief summary of this week's conversations with the user. Focus on:
        
        1. Main topics discussed
        2. Emotional journey through the week  
        3. Any notable patterns or themes
        
        Conversations:
        {convo_text[:2000]}  # Limit input size
        
        Return ONLY valid JSON with this exact structure:
        {{
            "summary": "Brief overall summary paragraph",
            "key_topics": ["topic1", "topic2", "topic3"],
            "emotional_tone": "overall emotional theme"
        }}
        
        Keep it concise and factual.
        """
        
        response = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": summary_prompt}],
            model="llama-3.1-8b-instant", 
            temperature=0.4,
            max_tokens=512
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # Clean the response
        if response_text.startswith('```json'):
            response_text = response_text[7:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        # Parse JSON with error handling
        try:
            summary_data = json.loads(response_text)
        except json.JSONDecodeError:
            print(f"Summary JSON parse failed. Response: {response_text}")
            return
        
        # Validate required fields
        if not all(key in summary_data for key in ['summary', 'key_topics', 'emotional_tone']):
            print("Summary missing required fields")
            return
            
        # Store the summary
        date_range = f"{one_week_ago.date()}_to_{datetime.now(timezone.utc).date()}"
        
        new_summary = ConversationSummary(
            user_id=user_id,
            summary=summary_data["summary"][:1000],  # Limit length
            key_topics=json.dumps(summary_data["key_topics"]),
            emotional_tone=summary_data["emotional_tone"]
        )
        db.session.add(new_summary)
        db.session.commit()
        
        print(f"Created weekly summary for user {user_id}")
        
    except Exception as e:
        print(f"Summary generation error: {e}")

def safe_json_parse(json_string, default=None):
    """Safely parse JSON with comprehensive error handling"""
    if default is None:
        default = {"memories": []}
    
    try:
        # Clean common issues
        cleaned = json_string.strip()
        if cleaned.startswith('```json'):
            cleaned = cleaned[7:].strip()
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3].strip()
        
        return json.loads(cleaned)
    except:
        return default

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
