"""
Database table creation script for Homie AI
This runs during deployment to create all necessary tables
WITH RETRY LOGIC FOR PRODUCTION DEPLOYMENT
"""

from app import app, db
from sqlalchemy import inspect
import time
import sys

# Force import all models to ensure they're registered
from app import User, Conversation, JournalEntry, Reminder, UserMemory, ConversationSummary

def wait_for_database(max_retries=10, wait_seconds=2):
    """Wait for database to be ready with retry logic"""
    for attempt in range(max_retries):
        try:
            with app.app_context():
                from sqlalchemy import text
                db.session.execute(text('SELECT 1'))
                print(f"✅ Database connection successful on attempt {attempt + 1}")
                return True
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = wait_seconds * (attempt + 1)  # Exponential backoff
                print(f"⏳ Database not ready (attempt {attempt + 1}/{max_retries}), waiting {wait_time}s...")
                print(f"   Error: {str(e)[:100]}")
                time.sleep(wait_time)
            else:
                print(f"❌ Database connection failed after {max_retries} attempts")
                print(f"   Final error: {e}")
                return False
    return False

def create_tables():
    """Create all database tables with retry logic"""
    with app.app_context():
        print("=" * 60)
        print("🔨 CREATING DATABASE TABLES FOR HOMIE AI")
        print("=" * 60)
        
        try:
            # Show current database URL (masked for security)
            db_url = app.config['SQLALCHEMY_DATABASE_URI']
            is_postgresql = 'postgresql' in db_url
            
            # Extract and display host information
            if '@' in db_url:
                try:
                    host_part = db_url.split('@')[1].split('/')[0]
                    print(f"📊 Database Type: {'PostgreSQL' if is_postgresql else 'SQLite'}")
                    print(f"📊 Database Host: {host_part}")
                except:
                    pass
            
            # Wait for database to be ready
            print("\n🔄 Waiting for database connection...")
            if not wait_for_database():
                print("❌ Cannot proceed without database connection")
                print("💡 Tip: Check if DATABASE_URL environment variable is set correctly")
                return False
            
            # Create all tables
            print("\n🔄 Creating tables...")
            db.create_all()
            print("✅ db.create_all() executed successfully")
            
            # Verify tables were created
            print("\n🔍 Verifying tables...")
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            if tables:
                print(f"\n✅ SUCCESS! Tables created:")
                for table in sorted(tables):
                    print(f"   ✓ {table}")
                print(f"\n📊 Total tables: {len(tables)}")
            else:
                print("\n⚠️ WARNING: No tables were created!")
                print("This might indicate a configuration issue.")
                return False
            
            # Create indexes for better performance (PostgreSQL only)
            if is_postgresql:
                print("\n🔧 Creating database indexes for performance...")
                try:
                    from sqlalchemy import text
                    with db.engine.connect() as conn:
                        # Index for conversation queries (most frequent)
                        conn.execute(text("""
                            CREATE INDEX IF NOT EXISTS idx_conversation_user_timestamp 
                            ON conversation(user_id, timestamp DESC);
                        """))
                        
                        # Index for memory queries
                        conn.execute(text("""
                            CREATE INDEX IF NOT EXISTS idx_user_memory_user_importance 
                            ON user_memory(user_id, importance_score DESC);
                        """))
                        
                        # Index for journal queries
                        conn.execute(text("""
                            CREATE INDEX IF NOT EXISTS idx_journal_entry_user_timestamp 
                            ON journal_entry(user_id, timestamp DESC);
                        """))
                        
                        # Index for reminder queries
                        conn.execute(text("""
                            CREATE INDEX IF NOT EXISTS idx_reminder_user_date 
                            ON reminder(user_id, date, time);
                        """))
                        
                        conn.commit()
                    print("✅ Database indexes created successfully")
                except Exception as e:
                    print(f"⚠️ Index creation warning (non-critical): {e}")
            
            print("\n" + "=" * 60)
            print("🎉 DATABASE INITIALIZATION COMPLETE!")
            print("=" * 60)
            return True
            
        except Exception as e:
            print("\n❌ ERROR: Failed to create tables")
            print(f"Error: {e}")
            print("=" * 60)
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    success = create_tables()
    sys.exit(0 if success else 1)
