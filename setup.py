#!/usr/bin/env python3

import os
import sys
import mysql.connector
from mysql.connector import Error

def check_requirements():
    '''Check if all requirements are met'''
    print("🔍 Checking requirements...")
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ is required")
        return False
    
    # Check required packages
    try:
        import discord
        import mysql.connector
        print("✅ All packages installed")
    except ImportError as e:
        print(f"❌ Missing package: {e}")
        print("Run: pip install -r requirements.txt")
        return False
    
    return True

def test_database_connection():
    '''Test database connection'''
    print("🔍 Testing database connection...")
    
    from config import DB_CONFIG
    
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        if connection.is_connected():
            print("✅ Database connection successful")
            
            # Check if tables exist
            cursor = connection.cursor()
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            
            required_tables = ['users', 'pokemon_species', 'moves', 'pokemon', 
                             'pokemon_moves', 'battles', 'servers', 'persistent_buttons']
            
            existing_tables = [table[0] for table in tables]
            missing_tables = [t for t in required_tables if t not in existing_tables]
            
            if missing_tables:
                print(f"❌ Missing tables: {missing_tables}")
                print("Run the database schema setup first!")
                return False
            
            print("✅ All required tables exist")
            
            # Check Pokemon data
            cursor.execute("SELECT COUNT(*) FROM pokemon_species")
            species_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM moves")
            moves_count = cursor.fetchone()[0]
            
            print(f"✅ Database loaded: {species_count} Pokemon species, {moves_count} moves")
            
            connection.close()
            return True
            
    except Error as e:
        print(f"❌ Database connection failed: {e}")
        return False

def test_bot_token():
    '''Test bot token validity'''
    print("🔍 Testing Discord bot token...")
    
    from config import DISCORD_BOT_TOKEN
    
    if DISCORD_BOT_TOKEN == 'your_discord_bot_token_here':
        print("❌ Discord bot token not configured")
        print("Update config.py or set DISCORD_BOT_TOKEN environment variable")
        return False
    
    # Basic token format check
    if not DISCORD_BOT_TOKEN.startswith(('MTA', 'MTB', 'MTC', 'MTD', 'MTE', 'MTF', 'MTG', 'MTH', 'MTI', 'MTJ')):
        print("❌ Discord bot token format looks invalid")
        return False
    
    print("✅ Discord bot token format looks correct")
    return True

def create_directories():
    '''Create required directories'''
    print("🔍 Creating directories...")
    
    directories = ['translations', 'logs']
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"✅ Created directory: {directory}")
        else:
            print(f"✅ Directory exists: {directory}")

def main():
    '''Run all setup checks'''
    print("🚀 Pokemon Battle Bot Setup Check")
    print("=" * 40)
    
    checks = [
        check_requirements,
        create_directories,
        test_database_connection,
        test_bot_token
    ]
    
    all_passed = True
    
    for check in checks:
        if not check():
            all_passed = False
        print()
    
    if all_passed:
        print("🎉 All checks passed! Bot is ready to run.")
        print("Start the bot with: python pokemon_bot.py")
    else:
        print("❌ Some checks failed. Please fix the issues above.")
        sys.exit(1)

if __name__ == "__main__":
    main()