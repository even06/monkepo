# config.py - Pokemon Bot Configuration
import os

# Database Configuration
DB_CONFIG = {
    'host': 'localhost',
    'database': 'pokemon_battle_bot',
    'user': 'root',
    'password': os.getenv('MYSQL_PASSWORD', 'your_mysql_password_here'),  # UPDATE THIS
    'charset': 'utf8mb4',
    'use_unicode': True,
    'autocommit': True
}

# Discord Bot Token
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN', 'your_discord_bot_token_here')  # UPDATE THIS

# Bot Settings
BOT_PREFIX = '!'
MAX_TEAM_SIZE = 3  # MVP: 3v3 battles
STARTER_IV_RANGE = (20, 31)  # High quality IVs for starters
COMMON_IV_RANGE = (10, 25)   # Standard IVs for common Pokemon

# Session Timeouts (in minutes)
STARTER_SELECTION_TIMEOUT = 10
BATTLE_TIMEOUT = 30
MODAL_TIMEOUT = 5

# Supported Languages
SUPPORTED_LANGUAGES = ['en', 'es']
DEFAULT_LANGUAGE = 'en'

# Feature Flags (for future development)
FEATURES = {
    'TRADING': False,       # Post-MVP
    'WILD_POKEMON': False,  # Post-MVP
    'TOURNAMENTS': False,   # Post-MVP
    'BREEDING': False,      # Post-MVP
    'ABILITIES': False      # MVP: No abilities yet
}

# Pokemon Game Constants
TYPE_EFFECTIVENESS_MULTIPLIERS = {
    'SUPER_EFFECTIVE': 2.0,
    'NOT_VERY_EFFECTIVE': 0.5,
    'NO_EFFECT': 0.0,
    'NORMAL': 1.0
}

CRITICAL_HIT_CHANCE = 0.0625  # 6.25% chance
CRITICAL_HIT_MULTIPLIER = 2.0

# XP Formula Constants
def get_xp_for_level(level):
    """Calculate XP needed to reach a specific level"""
    return (level * 100) + (level * level * 10)

def get_xp_to_next_level(current_level):
    """Calculate XP needed for next level"""
    return get_xp_for_level(current_level + 1) - get_xp_for_level(current_level)

# Logging Configuration
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pokemon_bot.log'),
        logging.StreamHandler()
    ]
)