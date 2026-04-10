import os
import sys
import io
import threading
import psycopg2
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

from dotenv import load_dotenv
import discord
from discord.ext import commands

load_dotenv()
token = os.getenv('DISCORD_BOT_TOKEN')
db_url = os.getenv('DATABASE_URL')

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

def insert_activity(discord_id, username, activities):
    """Insert activity events AND create/close game sessions"""
    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # Insert or update user
        cursor.execute(
            "INSERT INTO tracker_discorduser (discord_id, username, created_at, updated_at) VALUES (%s, %s, NOW(), NOW()) ON CONFLICT (discord_id) DO UPDATE SET username = %s, updated_at = NOW()",
            (discord_id, username, username)
        )
        conn.commit()
        
        # Get user id
        cursor.execute("SELECT id FROM tracker_discorduser WHERE discord_id = %s", (discord_id,))
        user_id = cursor.fetchone()[0]
        
        # Close old activities AND game sessions
        cursor.execute(
            "UPDATE tracker_activityevent SET ended_at = NOW() WHERE user_id = %s AND ended_at IS NULL",
            (user_id,)
        )
        
        # END GameSessions that match closed ActivityEvents
        cursor.execute("""
            UPDATE tracker_gamesession 
            SET ended_at = NOW(), duration_seconds = EXTRACT(EPOCH FROM (NOW() - started_at))::int
            WHERE user_id = %s AND ended_at IS NULL
        """, (user_id,))
        conn.commit()
        
        # Insert new activities
        if activities:
            for activity in activities:
                act_type = 'unknown'
                act_name = getattr(activity, 'name', 'Unknown')
                
                if isinstance(activity, discord.Game):
                    act_type = 'game'
                elif hasattr(activity, 'type'):
                    if activity.type == discord.ActivityType.playing:
                        act_type = 'game'
                    elif activity.type == discord.ActivityType.listening:
                        act_type = 'listening'
                    elif activity.type == discord.ActivityType.watching:
                        act_type = 'watching'
                
                # Insert activity event
                cursor.execute(
                    "INSERT INTO tracker_activityevent (user_id, activity_type, activity_name, activity_details, started_at) VALUES (%s, %s, %s, %s, NOW())",
                    (user_id, act_type, act_name, '{}')
                )
                
                # If it's a game, also create GameSession
                if act_type == 'game':
                    cursor.execute(
                        "INSERT INTO tracker_gamesession (user_id, game_name, started_at, duration_seconds) VALUES (%s, %s, NOW(), 0)",
                        (user_id, act_name)
                    )
                    print(f"{username} started playing {act_name}", flush=True)
                else:
                    print(f"{username}: {act_type} - {act_name}", flush=True)
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"DB ERROR (activity): {e}", flush=True)

def insert_voice_event(discord_id, username, channel_name, is_join):
    """Insert voice session events"""
    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # Insert or update user
        cursor.execute(
            "INSERT INTO tracker_discorduser (discord_id, username, created_at, updated_at) VALUES (%s, %s, NOW(), NOW()) ON CONFLICT (discord_id) DO UPDATE SET username = %s, updated_at = NOW()",
            (discord_id, username, username)
        )
        conn.commit()
        
        # Get user id
        cursor.execute("SELECT id FROM tracker_discorduser WHERE discord_id = %s", (discord_id,))
        user_id = cursor.fetchone()[0]
        
        if is_join:
            # Create new voice session
            cursor.execute(
                "INSERT INTO tracker_voicesession (user_id, channel_name, started_at, duration_seconds) VALUES (%s, %s, NOW(), 0)",
                (user_id, channel_name)
            )
            print(f" {username} joined {channel_name}", flush=True)
        else:
            # End current voice session
            cursor.execute("""
                UPDATE tracker_voicesession 
                SET ended_at = NOW(), duration_seconds = EXTRACT(EPOCH FROM (NOW() - started_at))::int
                WHERE user_id = %s AND channel_name = %s AND ended_at IS NULL
            """, (user_id, channel_name))
            print(f"{username} left {channel_name}", flush=True)
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"DB ERROR (voice): {e}", flush=True)

def insert_message(discord_id, username, channel_name, message_length):
    """Insert message event"""
    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # Insert or update user
        cursor.execute(
            "INSERT INTO tracker_discorduser (discord_id, username, created_at, updated_at) VALUES (%s, %s, NOW(), NOW()) ON CONFLICT (discord_id) DO UPDATE SET username = %s, updated_at = NOW()",
            (discord_id, username, username)
        )
        conn.commit()
        
        # Get user id
        cursor.execute("SELECT id FROM tracker_discorduser WHERE discord_id = %s", (discord_id,))
        user_id = cursor.fetchone()[0]
        
        # Insert message
        cursor.execute(
            "INSERT INTO tracker_message (user_id, channel_name, message_length, created_at) VALUES (%s, %s, %s, NOW())",
            (user_id, channel_name, message_length)
        )
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"DB ERROR (message): {e}", flush=True)

@bot.event
async def on_ready():
    print(f"\nBOT READY: {bot.user}\n", flush=True)
    for guild in bot.guilds:
        print(f"Guild: {guild.name}", flush=True)
        print(f"   Members: {guild.member_count}\n", flush=True)

@bot.event
async def on_presence_update(before, after):
    print(f"PRESENCE: {after.name}", flush=True)
    
    # Run DB operations in separate thread
    thread = threading.Thread(target=insert_activity, args=(after.id, str(after), after.activities))
    thread.daemon = True
    thread.start()

@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return
    
    print(f"VOICE: {member.name}", flush=True)
    
    # User joined voice
    if not before.channel and after.channel:
        thread = threading.Thread(target=insert_voice_event, args=(member.id, str(member), after.channel.name, True))
        thread.daemon = True
        thread.start()
    
    # User left voice
    elif before.channel and not after.channel:
        thread = threading.Thread(target=insert_voice_event, args=(member.id, str(member), before.channel.name, False))
        thread.daemon = True
        thread.start()
    
    # User switched channels
    elif before.channel and after.channel and before.channel != after.channel:
        thread1 = threading.Thread(target=insert_voice_event, args=(member.id, str(member), before.channel.name, False))
        thread2 = threading.Thread(target=insert_voice_event, args=(member.id, str(member), after.channel.name, True))
        thread1.daemon = True
        thread2.daemon = True
        thread1.start()
        thread2.start()

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    thread = threading.Thread(target=insert_message, args=(message.author.id, str(message.author), message.channel.name, len(message.content)))
    thread.daemon = True
    thread.start()

print("\n🚀 STARTING BOT...\n", flush=True)
bot.run(token)
