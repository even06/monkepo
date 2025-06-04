#!/usr/bin/env python3
"""
Pokemon Battle Bot - Enhanced with Discord Activity Support
Now includes basic activity launcher for battle interface
"""

import discord
from discord.ext import commands
import mysql.connector
from mysql.connector import Error
import asyncio
import json
import random
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
import uuid

# Configuration
from config import DB_CONFIG, DISCORD_BOT_TOKEN

class TranslationManager:
    """Handles multi-language support"""
    
    def __init__(self):
        self.translations = {}
        self.load_translations()
    
    def load_translations(self):
        """Load translation files"""
        for lang in ['en', 'es']:
            try:
                with open(f'translations/{lang}.json', 'r', encoding='utf-8') as f:
                    self.translations[lang] = json.load(f)
                print(f"✅ Loaded {lang} translations")
            except FileNotFoundError:
                print(f"❌ Translation file translations/{lang}.json not found")
                if lang == 'en':  # English is required
                    raise
    
    def get(self, key: str, lang: str = 'en', **kwargs) -> str:
        """Get translated text with formatting"""
        keys = key.split('.')
        text = self.translations.get(lang, self.translations['en'])
        
        for k in keys:
            text = text.get(k, key)
            if isinstance(text, str):
                break
        
        if isinstance(text, str) and kwargs:
            return text.format(**kwargs)
        return text if isinstance(text, str) else key

class DatabaseManager:
    """Enhanced database manager with server config support"""
    
    def __init__(self):
        self.connection = None
    
    async def connect(self):
        """Establish database connection"""
        try:
            self.connection = mysql.connector.connect(**DB_CONFIG)
            print("✅ Connected to Pokemon database")
            return True
        except Error as e:
            print(f"❌ Database connection failed: {e}")
            return False
    
    async def disconnect(self):
        """Close database connection"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
    
    def execute_query(self, query: str, params: tuple = None, fetch: bool = False):
        """Execute SQL query with error handling"""
        try:
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute(query, params or ())
            
            if fetch:
                result = cursor.fetchall()
            else:
                result = cursor.rowcount
                
            cursor.close()
            return result
        except Error as e:
            print(f"Database error: {e}")
            return None
    
    def execute_fetchone(self, query: str, params: tuple = None):
        """Execute query and fetch single result"""
        try:
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute(query, params or ())
            result = cursor.fetchone()
            cursor.close()
            return result
        except Error as e:
            print(f"Database error: {e}")
            return None

class PersistentButtonManager:
    """Manages persistent buttons across bot restarts"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.bot = None
    
    def set_bot(self, bot):
        self.bot = bot
    
    async def create_persistent_button(self, server_id: str, channel_id: str, 
                                     message_id: str, button_type: str, 
                                     button_data: dict = None):
        """Store persistent button in database"""
        query = """
        INSERT INTO persistent_buttons (server_id, channel_id, message_id, button_type, button_data)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
        channel_id = VALUES(channel_id),
        message_id = VALUES(message_id),
        button_data = VALUES(button_data),
        is_active = TRUE
        """
        self.db.execute_query(query, (
            server_id, channel_id, message_id, button_type, 
            json.dumps(button_data) if button_data else None
        ))
    
    async def get_server_buttons(self, server_id: str) -> List[Dict]:
        """Get all active buttons for a server"""
        query = """
        SELECT * FROM persistent_buttons 
        WHERE server_id = %s AND is_active = TRUE
        """
        return self.db.execute_query(query, (server_id,), fetch=True) or []
    
    async def restore_buttons_on_startup(self):
        """Restore all persistent buttons after bot restart"""
        query = "SELECT * FROM persistent_buttons WHERE is_active = TRUE"
        buttons = self.db.execute_query(query, fetch=True) or []
        
        restored = 0
        failed = 0
        
        for button in buttons:
            try:
                channel = self.bot.get_channel(int(button['channel_id']))
                if channel:
                    message = await channel.fetch_message(int(button['message_id']))
                    if message:
                        restored += 1
                        continue
            except:
                pass
            
            # Button/message no longer exists, mark as inactive
            await self.deactivate_button(button['id'])
            failed += 1
        
        print(f"🔄 Restored {restored} persistent buttons, {failed} need recreation")

    async def deactivate_button(self, button_id: int):
        """Mark button as inactive"""
        query = "UPDATE persistent_buttons SET is_active = FALSE WHERE id = %s"
        self.db.execute_query(query, (button_id,))

class IVGenerator:
    """Generates and manages Pokemon Individual Values"""
    
    @staticmethod
    def generate_starter_ivs() -> Dict[str, int]:
        """Generate high-quality IVs for starter Pokemon (20-31 range)"""
        return {
            'hp': random.randint(20, 31),
            'attack': random.randint(20, 31),
            'defense': random.randint(20, 31),
            'sp_attack': random.randint(20, 31),
            'sp_defense': random.randint(20, 31),
            'speed': random.randint(20, 31)
        }
    
    @staticmethod
    def generate_common_ivs() -> Dict[str, int]:
        """Generate standard IVs for common Pokemon (10-25 range)"""
        return {
            'hp': random.randint(10, 25),
            'attack': random.randint(10, 25), 
            'defense': random.randint(10, 25),
            'sp_attack': random.randint(10, 25),
            'sp_defense': random.randint(10, 25),
            'speed': random.randint(10, 25)
        }
    
    @staticmethod
    def calculate_stats(base_stats: Dict, ivs: Dict, level: int) -> Dict[str, int]:
        """Calculate final Pokemon stats using official formula"""
        stats = {}
        
        # HP has special formula
        stats['hp'] = int(((2 * base_stats['hp'] + ivs['hp']) * level / 100) + level + 10)
        
        # Other stats use standard formula
        for stat in ['attack', 'defense', 'sp_attack', 'sp_defense', 'speed']:
            stats[stat] = int(((2 * base_stats[stat] + ivs[stat]) * level / 100) + 5)
        
        return stats
    
    @staticmethod
    def get_iv_quality(ivs: Dict[str, int]) -> str:
        """Determine quality rating based on IV total"""
        total = sum(ivs.values())
        if total >= 180:  # 30+ average
            return "perfect"
        elif total >= 165:  # 27.5+ average  
            return "great"
        elif total >= 150:  # 25+ average
            return "good"
        elif total >= 135:  # 22.5+ average
            return "decent"
        elif total >= 120:  # 20+ average
            return "bad"
        else:
            return "terrible"

class TypeEffectiveness:
    """Pokemon type effectiveness system"""
    
    # Type effectiveness chart (attacking type -> defending types)
    EFFECTIVENESS = {
        'FIRE': {
            'strong': ['GRASS', 'BUG', 'ICE', 'STEEL'],
            'weak': ['WATER', 'ROCK', 'GROUND'],
            'immune': []
        },
        'WATER': {
            'strong': ['FIRE', 'GROUND', 'ROCK'],
            'weak': ['GRASS', 'ELECTRIC'],
            'immune': []
        },
        'GRASS': {
            'strong': ['WATER', 'GROUND', 'ROCK'],
            'weak': ['FIRE', 'BUG', 'POISON', 'FLYING'],
            'immune': []
        },
        'ELECTRIC': {
            'strong': ['WATER', 'FLYING'],
            'weak': ['GRASS', 'ELECTRIC'],
            'immune': ['GROUND']
        },
        'NORMAL': {
            'strong': [],
            'weak': ['ROCK', 'STEEL'],
            'immune': ['GHOST']
        },
        'BUG': {
            'strong': ['GRASS', 'PSYCHIC'],
            'weak': ['FIRE', 'FLYING', 'ROCK'],
            'immune': []
        },
        'FLYING': {
            'strong': ['BUG', 'GRASS', 'FIGHTING'],
            'weak': ['ELECTRIC', 'ROCK'],
            'immune': []
        },
        'POISON': {
            'strong': ['GRASS'],
            'weak': ['GROUND', 'ROCK', 'GHOST'],
            'immune': ['STEEL']
        }
    }
    
    TYPE_EMOJIS = {
        'FIRE': '🔥', 'WATER': '💧', 'GRASS': '🌿', 'ELECTRIC': '⚡',
        'NORMAL': '⭐', 'BUG': '🐛', 'FLYING': '💨', 'POISON': '☠️',
        'GROUND': '🌍', 'ROCK': '🗿', 'ICE': '❄️', 'STEEL': '⚙️',
        'PSYCHIC': '🔮', 'FIGHTING': '👊', 'GHOST': '👻', 'DRAGON': '🐉'
    }
    
    @classmethod
    def get_effectiveness_text(cls, attacking_type: str, lang: str = 'en', 
                             translations: TranslationManager = None) -> str:
        """Get formatted effectiveness text for a type"""
        if attacking_type not in cls.EFFECTIVENESS:
            return ""
        
        eff = cls.EFFECTIVENESS[attacking_type]
        lines = []
        
        if eff['strong']:
            strong_types = [f"{cls.TYPE_EMOJIS.get(t, '❓')} {t}" for t in eff['strong']]
            strong_text = translations.get('pokemon.type_chart.strong_vs', lang) if translations else "Strong vs:"
            lines.append(f"{strong_text} {', '.join(strong_types)}")
        
        if eff['weak']:
            weak_types = [f"{cls.TYPE_EMOJIS.get(t, '❓')} {t}" for t in eff['weak']]
            weak_text = translations.get('pokemon.type_chart.weak_vs', lang) if translations else "Weak vs:"
            lines.append(f"{weak_text} {', '.join(weak_types)}")
        
        return "\n".join(lines)

class BattleManager:
    """Manages battle sessions and state"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.active_battles = {}  # In-memory battle state storage
    
    async def create_battle_session(self, player1_id: str, player2_id: str = None, 
                                  server_id: str = None) -> str:
        """Create a new battle session"""
        battle_id = str(uuid.uuid4())
        
        # Insert battle record
        battle_query = """
        INSERT INTO battles (id, player1_id, player2_id, status, started_at)
        VALUES (%s, %s, %s, %s, %s)
        """
        self.db.execute_query(battle_query, (
            battle_id, player1_id, player2_id, 'LOBBY', datetime.now()
        ))
        
        # Initialize battle state
        self.active_battles[battle_id] = {
            'id': battle_id,
            'player1_id': player1_id,
            'player2_id': player2_id,
            'server_id': server_id,
            'status': 'LOBBY',
            'turn': 1,
            'created_at': datetime.now().isoformat()
        }
        
        print(f"Created battle session: {battle_id}")
        return battle_id
    
    async def get_user_team(self, user_id: str) -> List[Dict]:
        """Get user's active Pokemon team with calculated stats"""
        team_query = """
        SELECT 
            p.id, p.nickname, p.level, p.current_hp, p.status_condition,
            p.hp_iv, p.attack_iv, p.defense_iv, p.sp_attack_iv, p.sp_defense_iv, p.speed_iv,
            s.name as species_name, s.type1, s.type2,
            s.base_hp, s.base_attack, s.base_defense, s.base_sp_attack, s.base_sp_defense, s.base_speed
        FROM pokemon p
        JOIN pokemon_species s ON p.species_id = s.id
        WHERE p.user_id = %s AND p.is_active = TRUE
        ORDER BY p.team_slot
        """
        team_data = self.db.execute_query(team_query, (user_id,), fetch=True) or []
        
        # Calculate final stats for each Pokemon
        team = []
        for pokemon in team_data:
            base_stats = {
                'hp': pokemon['base_hp'],
                'attack': pokemon['base_attack'],
                'defense': pokemon['base_defense'],
                'sp_attack': pokemon['base_sp_attack'],
                'sp_defense': pokemon['base_sp_defense'],
                'speed': pokemon['base_speed']
            }
            
            ivs = {
                'hp': pokemon['hp_iv'],
                'attack': pokemon['attack_iv'],
                'defense': pokemon['defense_iv'],
                'sp_attack': pokemon['sp_attack_iv'],
                'sp_defense': pokemon['sp_defense_iv'],
                'speed': pokemon['speed_iv']
            }
            
            final_stats = IVGenerator.calculate_stats(base_stats, ivs, pokemon['level'])
            
            team.append({
                'id': pokemon['id'],
                'nickname': pokemon['nickname'] or pokemon['species_name'],
                'species': pokemon['species_name'],
                'level': pokemon['level'],
                'type1': pokemon['type1'],
                'type2': pokemon['type2'],
                'current_hp': pokemon['current_hp'] or final_stats['hp'],
                'max_hp': final_stats['hp'],
                'stats': final_stats,
                'status': pokemon['status_condition'],
                'ivs': ivs
            })
        
        return team

class ActivityLauncherView(discord.ui.View):
    """View for launching Discord Activities"""
    
    def __init__(self, activity_url: str, battle_manager: BattleManager, 
                 translations: TranslationManager, lang: str = 'en'):
        super().__init__(timeout=300)
        self.activity_url = activity_url
        self.battle_manager = battle_manager
        self.translations = translations
        self.lang = lang
    
    @discord.ui.button(label='🎮 Launch Battle Arena', 
                      style=discord.ButtonStyle.primary, 
                      custom_id='launch_activity')
    async def launch_activity(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        
        # Check if user has a team
        team = await self.battle_manager.get_user_team(user_id)
        if len(team) < 3:
            await interaction.response.send_message(
                "❌ You need at least 3 Pokemon to battle! Use the starter button to begin your journey.",
                ephemeral=True
            )
            return
        
        # Create battle session for practice/demo
        battle_id = await self.battle_manager.create_battle_session(user_id, server_id=server_id)
        
        # Create activity URL with battle session data
        activity_params = f"?battle_id={battle_id}&user_id={user_id}&mode=practice"
        full_activity_url = f"{self.activity_url}{activity_params}"
        
        # Create launch embed
        embed = discord.Embed(
            title="🎮 Pokemon Battle Arena",
            description="Click the button below to launch the battle interface!",
            color=0x3498db
        )
        
        embed.add_field(
            name="📊 Your Team Status",
            value=f"**Active Pokemon:** {len(team)}/3\n**Ready for Battle:** ✅",
            inline=True
        )
        
        embed.add_field(
            name="⚔️ Battle Mode",
            value="**Practice Mode**\nTest your team and interface",
            inline=True
        )
        
        # Add team preview
        team_preview = ""
        for i, pokemon in enumerate(team[:3], 1):
            type_emoji = TypeEffectiveness.TYPE_EMOJIS.get(pokemon['type1'], '❓')
            hp_percent = int((pokemon['current_hp'] / pokemon['max_hp']) * 100)
            team_preview += f"{i}. {type_emoji} **{pokemon['nickname']}** (Lv.{pokemon['level']}) - {hp_percent}% HP\n"
        
        embed.add_field(
            name="🎒 Your Battle Team",
            value=team_preview,
            inline=False
        )
        
        # Create activity launcher button
        activity_view = discord.ui.View()
        activity_button = discord.ui.Button(
            label="🚀 Open Battle Arena",
            style=discord.ButtonStyle.link,
            url=full_activity_url
        )
        activity_view.add_item(activity_button)
        
        await interaction.response.edit_message(embed=embed, view=activity_view)

class StarterSelectionView(discord.ui.View):
    """Starter Pokemon selection interface"""
    
    def __init__(self, user_id: str, server_id: str, db: DatabaseManager, 
                 translations: TranslationManager, lang: str = 'en'):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.server_id = server_id
        self.db = db
        self.translations = translations
        self.lang = lang
    
    @discord.ui.button(label='🔥 Charmander', style=discord.ButtonStyle.danger, custom_id='starter_charmander')
    async def charmander_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_starter_selection(interaction, 1, 'Charmander', 'FIRE')
    
    @discord.ui.button(label='💧 Squirtle', style=discord.ButtonStyle.primary, custom_id='starter_squirtle')
    async def squirtle_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_starter_selection(interaction, 4, 'Squirtle', 'WATER')
    
    @discord.ui.button(label='🌿 Bulbasaur', style=discord.ButtonStyle.success, custom_id='starter_bulbasaur')
    async def bulbasaur_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_starter_selection(interaction, 7, 'Bulbasaur', 'GRASS')
    
    async def _handle_starter_selection(self, interaction: discord.Interaction, 
                                      species_id: int, pokemon_name: str, pokemon_type: str):
        """Handle starter Pokemon selection and show stats"""
        
        # Generate IVs for this specific Pokemon
        ivs = IVGenerator.generate_starter_ivs()
        
        # Get base stats from database
        base_query = """
        SELECT base_hp, base_attack, base_defense, base_sp_attack, base_sp_defense, base_speed
        FROM pokemon_species WHERE id = %s
        """
        base_stats_row = self.db.execute_fetchone(base_query, (species_id,))
        
        if not base_stats_row:
            await interaction.response.send_message("❌ Error loading Pokemon data.", ephemeral=True)
            return
        
        base_stats = {
            'hp': base_stats_row['base_hp'],
            'attack': base_stats_row['base_attack'],
            'defense': base_stats_row['base_defense'],
            'sp_attack': base_stats_row['base_sp_attack'],
            'sp_defense': base_stats_row['base_sp_defense'],
            'speed': base_stats_row['base_speed']
        }
        
        # Calculate final stats at level 5
        final_stats = IVGenerator.calculate_stats(base_stats, ivs, 5)
        quality = IVGenerator.get_iv_quality(ivs)
        
        # Store pending selection
        pending_id = str(uuid.uuid4())
        expires_at = datetime.now() + timedelta(minutes=10)
        
        pending_query = """
        INSERT INTO pending_starters (id, user_id, server_id, selected_species_id, generated_ivs, expires_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        self.db.execute_query(pending_query, (
            pending_id, self.user_id, self.server_id, species_id,
            json.dumps(ivs), expires_at
        ))
        
        # Create stats display embed
        embed = discord.Embed(
            title=f"🔍 Your {pokemon_name}",
            description=f"Here are the stats for YOUR {pokemon_name}!",
            color=0x3498db
        )
        
        type_emoji = TypeEffectiveness.TYPE_EMOJIS.get(pokemon_type, '❓')
        quality_text = self.translations.get(f'pokemon.stats_quality.{quality}', self.lang)
        
        # Stats display
        stats_text = (
            f"**HP:** {final_stats['hp']}\n"
            f"**Attack:** {final_stats['attack']}\n"
            f"**Defense:** {final_stats['defense']}\n"
            f"**Sp. Attack:** {final_stats['sp_attack']}\n"
            f"**Sp. Defense:** {final_stats['sp_defense']}\n"
            f"**Speed:** {final_stats['speed']}\n\n"
            f"**Quality:** {quality_text} ⭐"
        )
        
        embed.add_field(name=f"{type_emoji} Level 5 Stats", value=stats_text, inline=True)
        
        # Type effectiveness
        effectiveness = TypeEffectiveness.get_effectiveness_text(
            pokemon_type, self.lang, self.translations
        )
        if effectiveness:
            embed.add_field(name="Type Matchups", value=effectiveness, inline=True)
        
        # Create naming modal button
        view = StarterNamingView(pending_id, pokemon_name, self.db, self.translations, self.lang)
        
        await interaction.response.edit_message(embed=embed, view=view)

class StarterNamingView(discord.ui.View):
    """View for naming the selected starter"""
    
    def __init__(self, pending_id: str, pokemon_name: str, db: DatabaseManager,
                 translations: TranslationManager, lang: str = 'en'):
        super().__init__(timeout=300)
        self.pending_id = pending_id
        self.pokemon_name = pokemon_name
        self.db = db
        self.translations = translations
        self.lang = lang
    
    @discord.ui.button(label='📝 Name This Pokemon', style=discord.ButtonStyle.success)
    async def name_pokemon(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = StarterNamingModal(self.pending_id, self.pokemon_name, self.db, 
                                 self.translations, self.lang)
        await interaction.response.send_modal(modal)

class StarterNamingModal(discord.ui.Modal):
    """Modal for entering Pokemon nickname"""
    
    def __init__(self, pending_id: str, pokemon_name: str, db: DatabaseManager,
                 translations: TranslationManager, lang: str = 'en'):
        title = translations.get('starter.name_modal_title', lang, pokemon=pokemon_name)
        super().__init__(title=title, timeout=300)
        self.pending_id = pending_id
        self.pokemon_name = pokemon_name
        self.db = db
        self.translations = translations
        self.lang = lang
        
        # Add nickname input
        label = translations.get('starter.name_modal_label', lang)
        placeholder = translations.get('starter.name_modal_placeholder', lang, pokemon=pokemon_name)
        
        self.nickname_input = discord.ui.TextInput(
            label=label,
            placeholder=placeholder,
            max_length=50,
            default=pokemon_name  # Default to Pokemon species name
        )
        self.add_item(self.nickname_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        nickname = self.nickname_input.value.strip()
        if not nickname:
            nickname = self.pokemon_name
        
        # Update pending selection with nickname
        update_query = """
        UPDATE pending_starters SET pokemon_nickname = %s, step = 'NAMED'
        WHERE id = %s
        """
        self.db.execute_query(update_query, (nickname, self.pending_id))
        
        # Show confirmation
        view = StarterConfirmationView(self.pending_id, nickname, self.pokemon_name,
                                     self.db, self.translations, self.lang)
        
        embed = discord.Embed(
            title=self.translations.get('starter.confirm_title', self.lang),
            description=self.translations.get('starter.confirm_description', self.lang,
                                            nickname=nickname, pokemon=self.pokemon_name),
            color=0x2ecc71
        )
        
        await interaction.response.edit_message(embed=embed, view=view)

class StarterConfirmationView(discord.ui.View):
    """Final confirmation for starter selection"""
    
    def __init__(self, pending_id: str, nickname: str, pokemon_name: str,
                 db: DatabaseManager, translations: TranslationManager, lang: str = 'en'):
        super().__init__(timeout=300)
        self.pending_id = pending_id
        self.nickname = nickname
        self.pokemon_name = pokemon_name
        self.db = db
        self.translations = translations
        self.lang = lang
    
    @discord.ui.button(label='✅ Confirm Choice', style=discord.ButtonStyle.success)
    async def confirm_choice(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._create_starter_team(interaction)
    
    @discord.ui.button(label='❌ Choose Different Pokemon', style=discord.ButtonStyle.danger)
    async def cancel_choice(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Delete pending selection and restart
        self.db.execute_query("DELETE FROM pending_starters WHERE id = %s", (self.pending_id,))
        
        # Show starter selection again
        view = StarterSelectionView(str(interaction.user.id), str(interaction.guild.id),
                                  self.db, self.translations, self.lang)
        
        embed = discord.Embed(
            title=self.translations.get('starter.choose_starter', self.lang),
            description=self.translations.get('starter.starter_description', self.lang),
            color=0x3498db
        )
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    async def _create_starter_team(self, interaction: discord.Interaction):
        """Create the complete starter team"""
        await interaction.response.edit_message(
            content=self.translations.get('starter.creating_team', self.lang),
            embed=None, view=None
        )
        
        # Get pending selection data
        pending_query = "SELECT * FROM pending_starters WHERE id = %s"
        pending = self.db.execute_fetchone(pending_query, (self.pending_id,))
        
        if not pending:
            await interaction.edit_original_response(
                content=self.translations.get('starter.session_expired', self.lang)
            )
            return
        
        user_id = pending['user_id']
        species_id = pending['selected_species_id']
        ivs = json.loads(pending['generated_ivs'])
        
        try:
            # Create starter Pokemon
            starter_query = """
            INSERT INTO pokemon (
                user_id, species_id, nickname, level, experience, is_starter,
                team_slot, hp_iv, attack_iv, defense_iv, sp_attack_iv, 
                sp_defense_iv, speed_iv, original_trainer
            ) VALUES (%s, %s, %s, 5, 0, TRUE, 1, %s, %s, %s, %s, %s, %s, %s)
            """
            self.db.execute_query(starter_query, (
                user_id, species_id, self.nickname, 
                ivs['hp'], ivs['attack'], ivs['defense'],
                ivs['sp_attack'], ivs['sp_defense'], ivs['speed'],
                user_id
            ))
            
            # Add 2 random common Pokemon
            common_species = [10, 13, 16, 19]  # Caterpie, Weedle, Pidgey, Rattata
            for slot in [2, 3]:
                common_species_id = random.choice(common_species)
                common_level = random.randint(3, 4)
                common_ivs = IVGenerator.generate_common_ivs()
                
                common_query = """
                INSERT INTO pokemon (
                    user_id, species_id, level, experience, is_starter,
                    team_slot, hp_iv, attack_iv, defense_iv, sp_attack_iv,
                    sp_defense_iv, speed_iv, original_trainer
                ) VALUES (%s, %s, %s, 0, FALSE, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                self.db.execute_query(common_query, (
                    user_id, common_species_id, common_level, slot,
                    common_ivs['hp'], common_ivs['attack'], common_ivs['defense'],
                    common_ivs['sp_attack'], common_ivs['sp_defense'], common_ivs['speed'],
                    user_id
                ))
            
            # Give starter items
            items = [
                ('HEALING', 'POTION', 3),
                ('HEALING', 'ANTIDOTE', 1), 
                ('POKEBALL', 'POKEBALL', 5)
            ]
            
            for item_type, item_id, quantity in items:
                item_query = """
                INSERT INTO user_items (user_id, item_type, item_id, quantity)
                VALUES (%s, %s, %s, %s)
                """
                self.db.execute_query(item_query, (user_id, item_type, item_id, quantity))
            
            # Clean up pending selection
            self.db.execute_query("DELETE FROM pending_starters WHERE id = %s", (self.pending_id,))
            
            # Send success message
            await self._send_welcome_message(interaction, user_id, species_id)
            
            # Send notification to updates channel
            await self._send_notification(interaction, user_id, species_id)
            
        except Exception as e:
            print(f"Error creating starter team: {e}")
            await interaction.edit_original_response(
                content=self.translations.get('starter.creation_failed', self.lang)
            )
    
    async def _send_welcome_message(self, interaction: discord.Interaction, 
                                  user_id: str, species_id: int):
        """Send welcome message to user"""
        # Get Pokemon details
        pokemon_query = """
        SELECT p.nickname, p.level, s.name as species_name, s.type1, s.type2
        FROM pokemon p
        JOIN pokemon_species s ON p.species_id = s.id
        WHERE p.user_id = %s AND p.is_starter = TRUE
        """
        starter = self.db.execute_fetchone(pokemon_query, (user_id,))
        
        if starter:
            type_emoji = TypeEffectiveness.TYPE_EMOJIS.get(starter['type1'], '❓')
            pokemon_info = f"{type_emoji} **{starter['nickname']}** the {starter['species_name']} (Lv.{starter['level']})"
            
            embed = discord.Embed(
                title=self.translations.get('starter.welcome_title', self.lang),
                description=self.translations.get('starter.welcome_description', self.lang),
                color=0x2ecc71
            )
            
            embed.add_field(
                name="🌟 " + self.translations.get('starter.your_starter', self.lang).split(':')[0],
                value=pokemon_info,
                inline=False
            )
            
            embed.add_field(
                name="🎒 " + self.translations.get('starter.starter_kit', self.lang).split(':')[0],
                value=self.translations.get('starter.starter_kit', self.lang).split(':', 1)[1],
                inline=False
            )
            
            embed.add_field(
                name="📋 " + self.translations.get('starter.next_steps', self.lang).split(':')[0],
                value=self.translations.get('starter.next_steps', self.lang).split(':', 1)[1],
                inline=False
            )
            
            await interaction.edit_original_response(content="", embed=embed)
    
    async def _send_notification(self, interaction: discord.Interaction,
                               user_id: str, species_id: int):
        """Send notification to updates channel"""
        # Get server config
        server_query = "SELECT updates_channel_id, language FROM servers WHERE id = %s"
        server_config = self.db.execute_fetchone(server_query, (str(interaction.guild.id),))
        
        if not server_config or not server_config['updates_channel_id']:
            return
        
        try:
            updates_channel = interaction.guild.get_channel(int(server_config['updates_channel_id']))
            if not updates_channel:
                return
            
            # Get starter details
            pokemon_query = """
            SELECT p.nickname, s.name as species_name, s.type1
            FROM pokemon p  
            JOIN pokemon_species s ON p.species_id = s.id
            WHERE p.user_id = %s AND p.is_starter = TRUE
            """
            starter = self.db.execute_fetchone(pokemon_query, (user_id,))
            
            if starter:
                lang = server_config['language'] or 'en'
                type_emoji = TypeEffectiveness.TYPE_EMOJIS.get(starter['type1'], '❓')
                
                embed = discord.Embed(
                    title=self.translations.get('notifications.new_trainer_title', lang),
                    description=self.translations.get('notifications.new_trainer_description', lang,
                                                    username=interaction.user.mention),
                    color=0xf39c12
                )
                
                embed.add_field(
                    name="🌟 Starter Choice",
                    value=self.translations.get('notifications.chose_starter', lang,
                                              starter_emoji=type_emoji,
                                              nickname=starter['nickname'],
                                              species=starter['species_name']),
                    inline=False
                )
                
                embed.add_field(
                    name="📊 Trainer Info",
                    value=self.translations.get('notifications.trainer_stats', lang),
                    inline=False
                )
                
                embed.set_thumbnail(url=interaction.user.display_avatar.url)
                embed.set_footer(text=self.translations.get('notifications.welcome_message', lang))
                
                await updates_channel.send(embed=embed)
                
        except Exception as e:
            print(f"Error sending notification: {e}")

class PersistentStarterView(discord.ui.View):
    """Persistent view for the starter button"""
    
    def __init__(self, db: DatabaseManager, translations: TranslationManager):
        super().__init__(timeout=None)  # Persistent view
        self.db = db
        self.translations = translations
    
    @discord.ui.button(label='🚀 Start Your Pokemon Journey', 
                  style=discord.ButtonStyle.success, 
                  custom_id='persistent_start_journey')

    async def start_journey(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        
        # Get server language
        lang_query = "SELECT language FROM servers WHERE id = %s"
        server_config = self.db.execute_fetchone(lang_query, (server_id,))
        lang = server_config['language'] if server_config else 'en'
        
        # Check if user already exists
        user_query = "SELECT id FROM users WHERE id = %s"
        if self.db.execute_fetchone(user_query, (user_id,)):
            await interaction.response.send_message(
                self.translations.get('starter.already_trainer', lang),
                ephemeral=True
            )
            return
        
        # ✅ CREATE USER IMMEDIATELY (NEW CODE)
        create_user_query = """
        INSERT INTO users (id, username, discriminator, created_at)
        VALUES (%s, %s, %s, %s)
        """
        self.db.execute_query(create_user_query, (
            user_id, interaction.user.name, 
            interaction.user.discriminator or '0000', datetime.now()
        ))
        print(f"✅ Created user record for {interaction.user.name}")
        
        # Show starter selection
        view = StarterSelectionView(user_id, server_id, self.db, self.translations, lang)
        
        embed = discord.Embed(
            title=self.translations.get('starter.choose_starter', lang),
            description=self.translations.get('starter.starter_description', lang),
            color=0x3498db
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class AdminSetupView(discord.ui.View):
    """Admin setup dashboard for server configuration"""
    
    def __init__(self, db: DatabaseManager, translations: TranslationManager, lang: str = 'en'):
        super().__init__(timeout=300)
        self.db = db
        self.translations = translations
        self.lang = lang
    
    @discord.ui.button(label='🏠 Set Starter Channel', style=discord.ButtonStyle.primary)
    async def set_starter_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ChannelSetupModal('starter', self.db, self.translations, self.lang)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label='📢 Set Updates Channel', style=discord.ButtonStyle.primary)
    async def set_updates_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ChannelSetupModal('updates', self.db, self.translations, self.lang)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label='🌐 Set Language', style=discord.ButtonStyle.secondary)
    async def set_language(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = LanguageSelectView(self.db, self.translations)
        await interaction.response.send_message("Select server language:", view=view, ephemeral=True)
    
    @discord.ui.button(label='👀 Preview Setup', style=discord.ButtonStyle.success)
    async def preview_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        server_id = str(interaction.guild.id)
        
        config_query = """
        SELECT starter_channel_id, updates_channel_id, language 
        FROM servers WHERE id = %s
        """
        config = self.db.execute_fetchone(config_query, (server_id,))
        
        if config:
            starter_channel = f"<#{config['starter_channel_id']}>" if config['starter_channel_id'] else "Not set"
            updates_channel = f"<#{config['updates_channel_id']}>" if config['updates_channel_id'] else "Not set"
            language = config['language'] or 'en'
            
            preview_text = self.translations.get('admin.setup_preview', self.lang,
                                               starter_channel=starter_channel,
                                               updates_channel=updates_channel,
                                               language=language)
        else:
            preview_text = "No configuration found."
        
        embed = discord.Embed(
            title="Current Configuration",
            description=preview_text,
            color=0x3498db
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class ChannelSetupModal(discord.ui.Modal):
    """Modal for setting channels"""
    
    def __init__(self, channel_type: str, db: DatabaseManager, 
                 translations: TranslationManager, lang: str = 'en'):
        self.channel_type = channel_type
        self.db = db
        self.translations = translations
        self.lang = lang
        
        title = f"Set {channel_type.title()} Channel"
        super().__init__(title=title, timeout=300)
        
        self.channel_input = discord.ui.TextInput(
            label=f"{channel_type.title()} Channel",
            placeholder="Enter channel ID or #channel-name",
            max_length=100
        )
        self.add_item(self.channel_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        server_id = str(interaction.guild.id)
        channel_input = self.channel_input.value.strip()
        
        # Parse channel mention or ID
        channel_id = None
        if channel_input.startswith('<#') and channel_input.endswith('>'):
            channel_id = channel_input[2:-1]
        elif channel_input.startswith('#'):
            # Search by name
            channel = discord.utils.get(interaction.guild.channels, name=channel_input[1:])
            if channel:
                channel_id = str(channel.id)
        elif channel_input.isdigit():
            channel_id = channel_input
        
        if not channel_id:
            await interaction.response.send_message(
                self.translations.get('admin.invalid_channel', self.lang),
                ephemeral=True
            )
            return
        
        # Verify channel exists
        channel = interaction.guild.get_channel(int(channel_id))
        if not channel:
            await interaction.response.send_message(
                self.translations.get('admin.invalid_channel', self.lang),
                ephemeral=True
            )
            return
        
        # Update database
        if self.channel_type == 'starter':
            column = 'starter_channel_id'
        else:
            column = 'updates_channel_id'
        
        # Ensure server exists
        server_query = """
        INSERT INTO servers (id, name) VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE name = VALUES(name)
        """
        self.db.execute_query(server_query, (server_id, interaction.guild.name))
        
        # Update channel
        update_query = f"UPDATE servers SET {column} = %s WHERE id = %s"
        self.db.execute_query(update_query, (channel_id, server_id))
        
        # If starter channel, create persistent button
        if self.channel_type == 'starter':
            await self._setup_starter_button(interaction, channel, server_id)
        
        await interaction.response.send_message(
            self.translations.get('admin.channel_set', self.lang,
                                channel_type=self.channel_type, channel=channel.mention),
            ephemeral=True
        )
    
    async def _setup_starter_button(self, interaction: discord.Interaction, 
                                  channel: discord.TextChannel, server_id: str):
        """Setup persistent starter button in the designated channel"""
        try:
            # Get server language
            lang_query = "SELECT language FROM servers WHERE id = %s"
            server_config = self.db.execute_fetchone(lang_query, (server_id,))
            lang = server_config['language'] if server_config else 'en'
            
            # Create starter embed
            embed = discord.Embed(
                title=self.translations.get('starter.oak_title', lang),
                description=self.translations.get('starter.oak_description', lang),
                color=0x2ecc71
            )
            embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/123/oak_lab.png")  # Add if you have image
            
            # Create persistent view
            view = PersistentStarterView(self.db, self.translations)
            
            # Send message
            message = await channel.send(embed=embed, view=view)
            
            # Store in database
            button_manager = PersistentButtonManager(self.db)
            await button_manager.create_persistent_button(
                server_id, str(channel.id), str(message.id), 
                'STARTER_SELECTION', {'lang': lang}
            )
            
        except Exception as e:
            print(f"Error setting up starter button: {e}")

class LanguageSelectView(discord.ui.View):
    """Language selection dropdown"""
    
    def __init__(self, db: DatabaseManager, translations: TranslationManager):
        super().__init__(timeout=300)
        self.db = db
        self.translations = translations
        
        # Add language select
        select = discord.ui.Select(
            placeholder="Choose server language...",
            options=[
                discord.SelectOption(label="English", value="en", emoji="🇺🇸"),
                discord.SelectOption(label="Español", value="es", emoji="🇪🇸")
            ]
        )
        select.callback = self.language_select
        self.add_item(select)
    
    async def language_select(self, interaction: discord.Interaction):
        server_id = str(interaction.guild.id)
        language = interaction.data['values'][0]
        
        # Ensure server exists
        server_query = """
        INSERT INTO servers (id, name, language) VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE language = VALUES(language)
        """
        self.db.execute_query(server_query, (server_id, interaction.guild.name, language))
        
        lang_name = "English" if language == "en" else "Español"
        await interaction.response.send_message(
            self.translations.get('admin.language_set', language, language=lang_name),
            ephemeral=True
        )

class PokemonBot(commands.Bot):
    """Main Pokemon Battle Bot"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        super().__init__(command_prefix='!', intents=intents)
        
        # Initialize systems
        self.db = DatabaseManager()
        self.translations = TranslationManager()
        self.button_manager = PersistentButtonManager(self.db)
        self.button_manager.set_bot(self)
        self.battle_manager = BattleManager(self.db)
        
        # Activity configuration
        self.activity_base_url = "https://monkepo.corebots.guru"  # Replace with your Activity URL

        # Store views for persistence
        self.persistent_views_added = False
    
    async def setup_hook(self):
        """Called when bot is starting up"""
        # Connect to database
        await self.db.connect()
        
        # Add persistent views
        if not self.persistent_views_added:
            self.add_view(PersistentStarterView(self.db, self.translations))
            self.persistent_views_added = True
        
        # Restore persistent buttons
        await self.button_manager.restore_buttons_on_startup()
        
        print(f"🤖 {self.user} is ready!")
    
    async def close(self):
        """Called when bot is shutting down"""
        await self.db.disconnect()
        await super().close()

# Initialize bot
bot = PokemonBot()

# Add this as a temporary command to your existing pokemon_bot.py
@bot.tree.command(name="debug-commands")
async def debug_commands(interaction: discord.Interaction):
    """Debug: Show registered commands"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Admin only!", ephemeral=True)
        return
    
    try:
        app_info = await bot.application_info()
        commands = await bot.http.get_global_commands(app_info.id)
        
        embed = discord.Embed(title="Registered Commands", color=0x3498db)
        
        if commands:
            cmd_list = []
            for cmd in commands:
                cmd_type = "Entry Point" if cmd.get('integration_types') else "Slash"
                cmd_list.append(f"• {cmd['name']} ({cmd_type})")
            
            embed.description = "\n".join(cmd_list)
        else:
            embed.description = "No commands found!"
            
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Error: {e}", ephemeral=True)

@bot.tree.command(name="mkp-battle")
async def battle_command(interaction: discord.Interaction, opponent: discord.Member = None):
    """
    Start a Pokemon battle or open practice arena
    
    Parameters:
    opponent: Another trainer to battle (optional - if none, opens practice mode)
    """
    user_id = str(interaction.user.id)
    server_id = str(interaction.guild.id)
    
    # Get server language
    lang_query = "SELECT language FROM servers WHERE id = %s"
    server_config = bot.db.execute_fetchone(lang_query, (server_id,))
    lang = server_config['language'] if server_config else 'en'
    
    # Check if user exists and has Pokemon
    user_query = "SELECT id FROM users WHERE id = %s"
    if not bot.db.execute_fetchone(user_query, (user_id,)):
        await interaction.response.send_message(
            bot.translations.get('errors.user_not_found', lang),
            ephemeral=True
        )
        return
    
    # Get user's team
    team = await bot.battle_manager.get_user_team(user_id)
    if len(team) < 3:
        await interaction.response.send_message(
            "❌ You need at least 3 Pokemon to battle! Complete your starter journey first.",
            ephemeral=True
        )
        return
    
    if opponent:
        # PvP Battle (future implementation)
        opponent_id = str(opponent.id)
        opponent_team = await bot.battle_manager.get_user_team(opponent_id)
        
        if len(opponent_team) < 3:
            await interaction.response.send_message(
                f"❌ {opponent.display_name} doesn't have enough Pokemon to battle!",
                ephemeral=True
            )
            return
        
        # Create battle invitation embed
        embed = discord.Embed(
            title="⚔️ Battle Challenge!",
            description=f"**{interaction.user.display_name}** challenges **{opponent.display_name}** to a Pokemon battle!",
            color=0xe74c3c
        )
        
        embed.add_field(
            name="🎯 Battle Format",
            value="3v3 Singles Battle\nFirst to defeat all opponent Pokemon wins!",
            inline=True
        )
        
        embed.add_field(
            name="⏱️ Time Limit",
            value="60 seconds per turn\n30 minute battle limit",
            inline=True
        )
        
        # Add team previews
        challenger_preview = ""
        for i, pokemon in enumerate(team[:3], 1):
            type_emoji = TypeEffectiveness.TYPE_EMOJIS.get(pokemon['type1'], '❓')
            challenger_preview += f"{type_emoji} {pokemon['nickname']} (Lv.{pokemon['level']})\n"
        
        opponent_preview = ""
        for i, pokemon in enumerate(opponent_team[:3], 1):
            type_emoji = TypeEffectiveness.TYPE_EMOJIS.get(pokemon['type1'], '❓')
            opponent_preview += f"{type_emoji} {pokemon['nickname']} (Lv.{pokemon['level']})\n"
        
        embed.add_field(
            name=f"🔥 {interaction.user.display_name}'s Team",
            value=challenger_preview,
            inline=True
        )
        
        embed.add_field(
            name="⚔️ VS",
            value="**VS**",
            inline=True
        )
        
        embed.add_field(
            name=f"💧 {opponent.display_name}'s Team",
            value=opponent_preview,
            inline=True
        )
        
        # Battle acceptance view (implement later)
        view = discord.ui.View()
        accept_button = discord.ui.Button(
            label="✅ Accept Challenge",
            style=discord.ButtonStyle.success,
            custom_id=f"accept_battle_{user_id}"
        )
        decline_button = discord.ui.Button(
            label="❌ Decline",
            style=discord.ButtonStyle.danger,
            custom_id="decline_battle"
        )
        view.add_item(accept_button)
        view.add_item(decline_button)
        
        await interaction.response.send_message(
            content=f"{opponent.mention}",
            embed=embed,
            view=view
        )
    
    else:
        # Practice Mode - Launch Activity
        embed = discord.Embed(
            title="🎮 Pokemon Battle Arena",
            description="Welcome to the Pokemon Battle Arena! Choose your battle mode below.",
            color=0x3498db
        )
        
        embed.add_field(
            name="🥊 Practice Mode",
            value="Train against AI opponents\nTest your team and strategies\nNo risk of losing Pokemon",
            inline=True
        )
        
        embed.add_field(
            name="📊 Your Team",
            value=f"**Pokemon Ready:** {len(team)}/3\n**Status:** Ready for Battle ✅",
            inline=True
        )
        
        # Team preview
        team_preview = ""
        total_level = 0
        for i, pokemon in enumerate(team[:3], 1):
            type_emoji = TypeEffectiveness.TYPE_EMOJIS.get(pokemon['type1'], '❓')
            hp_percent = int((pokemon['current_hp'] / pokemon['max_hp']) * 100)
            status_icon = "❤️" if hp_percent > 75 else "💛" if hp_percent > 25 else "🧡"
            team_preview += f"{type_emoji} **{pokemon['nickname']}** (Lv.{pokemon['level']}) {status_icon}\n"
            total_level += pokemon['level']
        
        embed.add_field(
            name="⭐ Your Battle Team",
            value=team_preview,
            inline=False
        )
        
        embed.add_field(
            name="💪 Team Power Level",
            value=f"Average Level: **{total_level // len(team)}**\nCombined Level: **{total_level}**",
            inline=True
        )
        
        embed.set_footer(text="💡 Tip: Practice battles help you learn type matchups and strategies!")
        
        # Create activity launcher
        view = ActivityLauncherView(
            bot.activity_base_url,
            bot.battle_manager,
            bot.translations,
            lang
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@bot.tree.command(name="mkp-arena")
async def arena_command(interaction: discord.Interaction):
    """Quick access to the Pokemon Battle Arena"""
    await battle_command(interaction)

# ========================================
# BATTLE STATE API ENDPOINTS (for Activity)
# ========================================

@bot.tree.command(name="mkp-battle-info")
async def battle_info(interaction: discord.Interaction, battle_id: str = None):
    """Get battle information (for debugging/testing)"""
    user_id = str(interaction.user.id)
    
    if not battle_id:
        # Show user's recent battles
        battles_query = """
        SELECT id, player1_id, player2_id, status, started_at
        FROM battles 
        WHERE player1_id = %s OR player2_id = %s
        ORDER BY started_at DESC
        LIMIT 5
        """
        battles = bot.db.execute_query(battles_query, (user_id, user_id), fetch=True) or []
        
        if not battles:
            await interaction.response.send_message("No battles found.", ephemeral=True)
            return
        
        embed = discord.Embed(title="Your Recent Battles", color=0x3498db)
        for battle in battles:
            opponent_id = battle['player2_id'] if battle['player1_id'] == user_id else battle['player1_id']
            opponent = "Practice Mode" if not opponent_id else f"<@{opponent_id}>"
            
            embed.add_field(
                name=f"Battle {battle['id'][:8]}...",
                value=f"**Status:** {battle['status']}\n**Opponent:** {opponent}\n**Started:** {battle['started_at']}",
                inline=True
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    else:
        # Show specific battle info
        if battle_id in bot.battle_manager.active_battles:
            battle_state = bot.battle_manager.active_battles[battle_id]
            embed = discord.Embed(
                title=f"Battle {battle_id[:8]}...",
                description=f"**Status:** {battle_state['status']}\n**Turn:** {battle_state['turn']}",
                color=0x2ecc71
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("Battle not found or inactive.", ephemeral=True)

# Admin Commands
@bot.tree.command(name="mkp-admin")
async def admin_setup(interaction: discord.Interaction):
    """Configure Pokemon bot settings for this server"""
    
    # Check permissions
    if not interaction.user.guild_permissions.administrator:
        lang_query = "SELECT language FROM servers WHERE id = %s"
        server_config = bot.db.execute_fetchone(lang_query, (str(interaction.guild.id),))
        lang = server_config['language'] if server_config else 'en'
        
        await interaction.response.send_message(
            bot.translations.get('admin.no_permission', lang),
            ephemeral=True
        )
        return
    
    # Get server language
    server_id = str(interaction.guild.id)
    lang_query = "SELECT language FROM servers WHERE id = %s"
    server_config = bot.db.execute_fetchone(lang_query, (server_id,))
    lang = server_config['language'] if server_config else 'en'
    
    # Create setup embed
    embed = discord.Embed(
        title=bot.translations.get('admin.setup_title', lang),
        description=bot.translations.get('admin.setup_description', lang),
        color=0xe74c3c
    )
    
    # Check current configuration status
    if server_config:
        if server_config.get('starter_channel_id') and server_config.get('updates_channel_id'):
            status = bot.translations.get('admin.config_complete', lang)
            color = 0x2ecc71
        elif server_config.get('starter_channel_id') or server_config.get('updates_channel_id'):
            status = bot.translations.get('admin.config_partial', lang)
            color = 0xf39c12
        else:
            status = bot.translations.get('admin.config_missing', lang)
            color = 0xe74c3c
    else:
        status = bot.translations.get('admin.config_missing', lang)
        color = 0xe74c3c
    
    embed.add_field(name="Status", value=status, inline=False)
    embed.color = color
    
    view = AdminSetupView(bot.db, bot.translations, lang)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# Basic Pokemon commands
@bot.tree.command(name="monkepo")
async def pokemon_command(interaction: discord.Interaction, action: str):
    """
    Pokemon management commands
    
    Parameters:
    action: Action to perform (list, stats, heal)
    """
    user_id = str(interaction.user.id)
    server_id = str(interaction.guild.id)
    
    # Get server language
    lang_query = "SELECT language FROM servers WHERE id = %s"
    server_config = bot.db.execute_fetchone(lang_query, (server_id,))
    lang = server_config['language'] if server_config else 'en'
    
    if action.lower() == "list":
        # Check if user exists
        user_query = "SELECT id FROM users WHERE id = %s"
        if not bot.db.execute_fetchone(user_query, (user_id,)):
            await interaction.response.send_message(
                bot.translations.get('errors.user_not_found', lang),
                ephemeral=True
            )
            return
        
        # Get user's Pokemon with calculated stats
        pokemon_query = """
        SELECT 
            p.id, p.nickname, p.level, p.experience, p.is_starter, p.team_slot,
            p.current_hp, p.status_condition, p.hp_iv, p.attack_iv, p.defense_iv,
            p.sp_attack_iv, p.sp_defense_iv, p.speed_iv,
            s.name as species_name, s.type1, s.type2, s.pokedex_number,
            s.base_hp, s.base_attack, s.base_defense, s.base_sp_attack, s.base_sp_defense, s.base_speed
        FROM pokemon p
        JOIN pokemon_species s ON p.species_id = s.id
        WHERE p.user_id = %s AND p.is_active = TRUE
        ORDER BY p.team_slot
        """
        pokemon_list = bot.db.execute_query(pokemon_query, (user_id,), fetch=True) or []
        
        if not pokemon_list:
            await interaction.response.send_message(
                bot.translations.get('errors.pokemon_not_found', lang),
                ephemeral=True
            )
            return
        
        # Create team display
        embed = discord.Embed(
            title=f"🎒 {interaction.user.display_name}'s Pokemon Team",
            color=0xe74c3c
        )
        
        for i, pokemon in enumerate(pokemon_list, 1):
            # Calculate current stats
            base_stats = {
                'hp': pokemon['base_hp'],
                'attack': pokemon['base_attack'], 
                'defense': pokemon['base_defense'],
                'sp_attack': pokemon['base_sp_attack'],
                'sp_defense': pokemon['base_sp_defense'],
                'speed': pokemon['base_speed']
            }
            
            ivs = {
                'hp': pokemon['hp_iv'],
                'attack': pokemon['attack_iv'],
                'defense': pokemon['defense_iv'], 
                'sp_attack': pokemon['sp_attack_iv'],
                'sp_defense': pokemon['sp_defense_iv'],
                'speed': pokemon['speed_iv']
            }
            
            final_stats = IVGenerator.calculate_stats(base_stats, ivs, pokemon['level'])
            
            # Get type emojis
            type1_emoji = TypeEffectiveness.TYPE_EMOJIS.get(pokemon['type1'], '❓')
            type_display = bot.translations.get(f'pokemon.types.{pokemon["type1"]}', lang)
            if pokemon['type2']:
                type2_emoji = TypeEffectiveness.TYPE_EMOJIS.get(pokemon['type2'], '❓')
                type_display += f"/{bot.translations.get(f'pokemon.types.{pokemon["type2"]}', lang)}"
                type1_emoji += type2_emoji
            
            # Calculate current HP
            current_hp = pokemon['current_hp'] or final_stats['hp']
            hp_percentage = current_hp / final_stats['hp']
            hp_bar = "█" * int(hp_percentage * 10)
            hp_bar += "░" * (10 - len(hp_bar))
            
            # Status indicator
            status = ""
            if pokemon['status_condition'] != 'HEALTHY':
                status_emojis = {
                    'BURN': '🔥', 'POISON': '🟣', 'PARALYSIS': '⚡', 'SLEEP': '💤'
                }
                status = f" {status_emojis.get(pokemon['status_condition'], '❓')}"
            
            starter_mark = " ⭐" if pokemon['is_starter'] else ""
            nickname = pokemon['nickname'] or pokemon['species_name']
            
            # Get IV quality
            quality = IVGenerator.get_iv_quality(ivs)
            quality_text = bot.translations.get(f'pokemon.stats_quality.{quality}', lang)
            
            embed.add_field(
                name=f"Slot {i}: {type1_emoji} {nickname}{starter_mark}",
                value=(
                    f"**{pokemon['species_name']}** • Level {pokemon['level']}\n"
                    f"HP: {hp_bar} {current_hp}/{final_stats['hp']}{status}\n"
                    f"Type: {type_display} • Quality: {quality_text}\n"
                    f"XP: {pokemon['experience']}"
                ),
                inline=True
            )
        
        await interaction.response.send_message(embed=embed)
    
    else:
        await interaction.response.send_message(
            bot.translations.get('errors.invalid_command', lang),
            ephemeral=True
        )

@bot.event
async def on_ready():
    """Bot startup event"""
    await safe_sync_commands()

async def safe_sync_commands():
    """Safely sync commands without affecting Entry Point commands"""
    try:
        print("🔄 Starting command sync...")
        
        # Get existing commands first
        existing_commands = await bot.tree.fetch_commands()
        print(f"Found {len(existing_commands)} existing commands")
        
        # Show what commands we're trying to register
        local_commands = [cmd.name for cmd in bot.tree.get_commands()]
        print(f"Local commands to sync: {local_commands}")
        
        try:
            synced = await bot.tree.sync()
            print(f"✅ Successfully synced {len(synced)} command(s)")
            print(f"Synced commands: {[cmd['name'] for cmd in synced]}")
        except discord.HTTPException as e:
            if e.code == 50240:  # Entry Point command error
                print("⚠️ Entry Point command conflict detected")
                print("🔄 Commands may already exist as Entry Point commands...")
                
                # Get application info for checking
                app_info = await bot.application_info()
                current_commands = await bot.http.get_global_commands(app_info.id)
                
                # Show what's already registered
                print("📋 Currently registered commands:")
                existing_names = []
                for cmd in current_commands:
                    cmd_type = "Entry Point" if cmd.get('integration_types') else "Slash"
                    print(f"  - {cmd['name']} ({cmd_type})")
                    existing_names.append(cmd['name'])
                
                # Check which of our commands are already there
                already_exists = []
                missing = []
                for local_cmd in local_commands:
                    if local_cmd in existing_names:
                        already_exists.append(local_cmd)
                    else:
                        missing.append(local_cmd)
                
                if already_exists:
                    print(f"✅ Commands already registered: {already_exists}")
                if missing:
                    print(f"❌ Commands missing: {missing}")
                else:
                    print("✅ All your commands are already registered!")
                    print("💡 They might be Entry Point commands - try using them in Discord")
                
            else:
                print(f"❌ Other sync error: {e}")
                raise e
        
        print("🤖 Bot is ready to battle!")
        
    except Exception as e:
        print(f"❌ Command sync failed: {e}")
        print("💡 Bot will still function, but commands may not be available")

@bot.event
async def on_guild_join(guild):
    """When bot joins a new server"""
    # Create server entry
    server_query = """
    INSERT INTO servers (id, name, created_at) 
    VALUES (%s, %s, %s)
    ON DUPLICATE KEY UPDATE name = VALUES(name)
    """
    bot.db.execute_query(server_query, (str(guild.id), guild.name, datetime.now()))
    print(f"Joined server: {guild.name}")

# Error handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    print(f"Command error: {error}")

if __name__ == "__main__":
    if DISCORD_BOT_TOKEN == 'your_bot_token_here':
        print("❌ Please set your Discord bot token in config.py!")
    else:
        bot.run(DISCORD_BOT_TOKEN)