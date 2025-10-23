"""
Database table creation script for Homie AI
This runs during deployment to create all necessary tables
"""

from app import app, db
from sqlalchemy import inspect

# Force import all models to ensure they're registered
from app import User, Conversation, JournalEntry, Reminder, UserMemory, ConversationSummary

def create_tables():
    """Create all database tables"""
    with app.app_context():
        print("=" * 60)
        print("🔨 CREATING DATABASE TABLES")
        print("=" * 60)
        
        try:
            # Show current database URL
            db_url = app.config['SQLALCHEMY_DATABASE_URI']
            is_postgresql = 'postgresql' in db_url
            print(f"📊 Database Type: {'PostgreSQL' if is_postgresql else 'SQLite'}")
            print(f"📊 Database URL: {db_url[:60]}...")
            
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
                for table in tables:
                    print(f"   ✓ {table}")
                print(f"\n📊 Total tables: {len(tables)}")
            else:
                print("\n⚠️ WARNING: No tables were created!")
                print("This might indicate a configuration issue.")
                return False
            
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
    exit(0 if success else 1)
