import os
import random
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
from pymongo import MongoClient
from datetime import datetime, timedelta
import yt_dlp as youtube_dl

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
MONGO_URI = os.getenv('MONGO_URI')

# MongoDB setup
mongo_client = MongoClient(MONGO_URI)
db = mongo_client['xsin_database']
users_collection = db['users']

# Intents setup
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.reactions = True

# Bot setup
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    check_reminders.start()

### Anti-Raid Measures
@bot.event
async def on_member_join(member):
    # Basic example of a join check
    if len(member.name) < 3 or member.created_at.timestamp() > (datetime.utcnow().timestamp() - 86400):  # Accounts created within the last day
        await member.ban(reason="Potential raid account.")

@bot.event
async def on_message(message):
    # Anti-spam: Check for repeated messages or suspicious content
    if message.author == bot.user:
        return

    # Example anti-spam check
    if "http" in message.content or "@everyone" in message.content:
        await message.delete()
        await message.channel.send(f'{message.author.mention}, spam detected!')

    await bot.process_commands(message)  # Ensure commands still work

### Leveling System
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = str(message.author.id)
    user_data = users_collection.find_one({"user_id": user_id})

    if not user_data:
        users_collection.insert_one({"user_id": user_id, "xp": 0, "level": 1})
    else:
        xp = random.randint(5, 15)
        new_xp = user_data['xp'] + xp
        new_level = new_xp // 100

        if new_level > user_data['level']:
            await message.channel.send(f"Congratulations {message.author.mention}, you've leveled up to level {new_level}!")
            users_collection.update_one({"user_id": user_id}, {"$set": {"level": new_level, "xp": new_xp}})
        else:
            users_collection.update_one({"user_id": user_id}, {"$inc": {"xp": xp}})

    await bot.process_commands(message)  # Ensure commands still work

@bot.command(name='rank')
async def rank(ctx):
    user_id = str(ctx.author.id)
    user_data = users_collection.find_one({"user_id": user_id})
    if user_data:
        await ctx.send(f"{ctx.author.mention}, you are at level {user_data['level']} with {user_data['xp']} XP.")
    else:
        await ctx.send("No data found for you. Start chatting to earn XP!")

### Mini-Games
@bot.command(name='trivia')
async def trivia(ctx):
    trivia_questions = {
        "What is the capital of France?": "Paris",
        "What is 2+2?": "4",
        "Who wrote 'To Kill a Mockingbird'?": "Harper Lee"
    }
    question, answer = random.choice(list(trivia_questions.items()))
    await ctx.send(question)

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    response = await bot.wait_for('message', check=check)
    if response.content.lower() == answer.lower():
        await ctx.send(f"Correct, {ctx.author.mention}!")
    else:
        await ctx.send(f"Incorrect! The answer was {answer}.")

### Server Growth Tools
@bot.event
async def on_member_join(member):
    channel = discord.utils.get(member.guild.text_channels, name='welcome')
    if channel:
        await channel.send(f"Welcome to the server, {member.mention}!")

@bot.command(name='promote')
@commands.has_permissions(administrator=True)
async def promote(ctx):
    await ctx.send("Don't forget to invite your friends to our server!")

### Premium Features
@bot.command(name='analytics', hidden=True)
@commands.has_permissions(administrator=True)
async def analytics(ctx):
    total_members = ctx.guild.member_count
    text_channels = len(ctx.guild.text_channels)
    voice_channels = len(ctx.guild.voice_channels)
    await ctx.send(f"Server has {total_members} members, {text_channels} text channels, and {voice_channels} voice channels.")

### Music Integration
@bot.command(name='play')
async def play(ctx, url: str):
    if ctx.author.voice is None:
        await ctx.send("You need to be in a voice channel to play music.")
        return

    voice_channel = ctx.author.voice.channel
    voice_client = await voice_channel.connect()

    ydl_opts = {'format': 'bestaudio'}
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        URL = info['formats'][0]['url']

    voice_client.play(discord.FFmpegPCMAudio(URL))

### Event Reminders
reminders = []

@bot.command(name='remindme')
async def remindme(ctx, time: int, *, reminder: str):
    reminder_time = datetime.now() + timedelta(seconds=time)
    reminders.append((reminder_time, ctx.author.id, reminder))
    await ctx.send(f"{ctx.author.mention}, I will remind you about '{reminder}' in {time} seconds.")

@tasks.loop(seconds=5)
async def check_reminders():
    now = datetime.now()
    for reminder_time, user_id, reminder in reminders:
        if now >= reminder_time:
            user = await bot.fetch_user(user_id)
            await user.send(f"Reminder: {reminder}")
            reminders.remove((reminder_time, user_id, reminder))

@check_reminders.before_loop
async def before_check_reminders():
    await bot.wait_until_ready()

# Run the bot
bot.run(TOKEN)
