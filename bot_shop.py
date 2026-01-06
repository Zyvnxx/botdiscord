import discord
import random
import json
import asyncio
import os
from datetime import datetime, timedelta
from discord.ext import commands, tasks
import aiohttp
import math

TOKEN = os.getenv("TOKEN")

from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Online 24 Jam"

def run():
    app.run(host='0.0.0.0', port=10000)

Thread(target=run).start()

PREFIX = '.'

# ========== INTENTS ==========
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix=PREFIX, 
    intents=intents, 
    help_command=None,
    case_insensitive=True
)

# ========== FILE PATHS ==========
ECONOMY_FILE = "economy_data.json"
GACHA_FILE = "gacha_data.json"
INVENTORY_FILE = "inventory_data.json"

# ========== GAME VARIABLES ==========
rps_stats = {}  # {user_id: {wins, losses, draws}}
guessing_games = {}  # {channel_id: {"number": num, "attempts": int}}
coin_flip_stats = {}  # {user_id: {wins, losses}}
hangman_games = {}  # {channel_id: game_data}
daily_rewards = {}  # {user_id: last_daily_claim}
work_cooldowns = {}  # {user_id: last_work_time}
crime_cooldowns = {}  # {user_id: last_crime_time}

# ========== EKONOMI VIRTUAL ==========
class EconomySystem:
    def __init__(self):
        self.data = {}
        self.gacha_data = {}
        self.inventory_data = {}
        self._save_timer = None
        self._pending_save = False
        self.load_data()
    
    def load_data(self):
        """Load semua data dari file"""
        try:
            with open(ECONOMY_FILE, 'r') as f:
                self.data = json.load(f)
        except FileNotFoundError:
            self.data = {}
        
        try:
            with open(GACHA_FILE, 'r') as f:
                self.gacha_data = json.load(f)
        except FileNotFoundError:
            self.gacha_data = {}
            
        try:
            with open(INVENTORY_FILE, 'r') as f:
                self.inventory_data = json.load(f)
        except FileNotFoundError:
            self.inventory_data = {}
    
    def schedule_save(self):
        """Jadwalkan save data (debounced)"""
        if not self._pending_save:
            self._pending_save = True
            asyncio.create_task(self._delayed_save())
    
    async def _delayed_save(self):
        """Delay save untuk mengurangi I/O"""
        await asyncio.sleep(10)  # Tunggu 10 detik sebelum save
        self._pending_save = False
        self._force_save()
    
    def _force_save(self):
        """Save data langsung (digunakan saat bot shutdown)"""
        with open(ECONOMY_FILE, 'w') as f:
            json.dump(self.data, f, indent=4)
        
        with open(GACHA_FILE, 'w') as f:
            json.dump(self.gacha_data, f, indent=4)
            
        with open(INVENTORY_FILE, 'w') as f:
            json.dump(self.inventory_data, f, indent=4)
    
    def get_user_data(self, user_id):
        """Dapatkan data user, buat jika belum ada"""
        if str(user_id) not in self.data:
            self.data[str(user_id)] = {
                "balance": 1000,  # Saldo awal
                "bank": 0,
                "xp": 0,
                "level": 1,
                "total_earned": 0,
                "total_spent": 0,
                "daily_streak": 0,
                "last_daily": None,
                "achievements": [],
                "transactions": [],
                "last_collect": None
            }
        return self.data[str(user_id)]
    
    def get_inventory(self, user_id):
        """Dapatkan inventory user"""
        if str(user_id) not in self.inventory_data:
            self.inventory_data[str(user_id)] = {
                "items": {},
                "gacha_items": [],
                "badges": []
            }
        return self.inventory_data[str(user_id)]
    
    def add_money(self, user_id, amount, reason="Tidak diketahui"):
        """Tambahkan uang ke user"""
        user_data = self.get_user_data(user_id)
        user_data["balance"] += amount
        user_data["total_earned"] += amount
        
        # Record transaction
        transaction = {
            "type": "income",
            "amount": amount,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }
        user_data["transactions"].append(transaction)
        
        # Jadwalkan save
        self.schedule_save()
        return user_data["balance"]
    
    def remove_money(self, user_id, amount, reason="Tidak diketahui"):
        """Kurangi uang dari user"""
        user_data = self.get_user_data(user_id)
        if user_data["balance"] < amount:
            return False
        
        user_data["balance"] -= amount
        user_data["total_spent"] += amount
        
        # Record transaction
        transaction = {
            "type": "expense",
            "amount": amount,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }
        user_data["transactions"].append(transaction)
        
        self.schedule_save()
        return True
    
    def transfer_money(self, from_id, to_id, amount):
        """Transfer uang antar user"""
        from_user = self.get_user_data(from_id)
        to_user = self.get_user_data(to_id)
        
        if from_user["balance"] < amount:
            return False, "Saldo tidak cukup"
        
        from_user["balance"] -= amount
        to_user["balance"] += amount
        
        # Record transactions
        transaction_out = {
            "type": "transfer_out",
            "amount": amount,
            "to": str(to_id),
            "timestamp": datetime.now().isoformat()
        }
        from_user["transactions"].append(transaction_out)
        
        transaction_in = {
            "type": "transfer_in",
            "amount": amount,
            "from": str(from_id),
            "timestamp": datetime.now().isoformat()
        }
        to_user["transactions"].append(transaction_in)
        
        self.schedule_save()
        return True, "Transfer berhasil"
    
    def add_xp(self, user_id, xp_amount):
        """Tambahkan XP ke user"""
        user_data = self.get_user_data(user_id)
        user_data["xp"] += xp_amount
        
        # Check level up
        required_xp = user_data["level"] * 100
        level_ups = 0
        
        while user_data["xp"] >= required_xp:
            user_data["xp"] -= required_xp
            user_data["level"] += 1
            level_ups += 1
            required_xp = user_data["level"] * 100
            
            # Beri bonus level up
            bonus = user_data["level"] * 100
            user_data["balance"] += bonus
            user_data["total_earned"] += bonus
        
        self.schedule_save()
        return level_ups
    
    def add_to_inventory(self, user_id, item_name, quantity=1):
        """Tambahkan item ke inventory"""
        inventory = self.get_inventory(user_id)
        
        if item_name in inventory["items"]:
            inventory["items"][item_name] += quantity
        else:
            inventory["items"][item_name] = quantity
        
        self.schedule_save()
    
    def add_gacha_item(self, user_id, item_data):
        """Tambahkan item gacha ke inventory"""
        inventory = self.get_inventory(user_id)
        inventory["gacha_items"].append({
            "name": item_data["name"],
            "rarity": item_data["rarity"],
            "value": item_data["value"],
            "timestamp": datetime.now().isoformat()
        })
        self.schedule_save()
    
    def get_gacha_pool(self, gacha_type="normal"):
        """Dapatkan pool gacha berdasarkan tipe"""
        gacha_pools = {
            "normal": [
                {"name": "Koin Emas", "rarity": "common", "value": 50, "weight": 40},
                {"name": "Permata Hijau", "rarity": "common", "value": 100, "weight": 30},
                {"name": "Permata Biru", "rarity": "uncommon", "value": 250, "weight": 15},
                {"name": "Permata Ungu", "rarity": "rare", "value": 500, "weight": 10},
                {"name": "Permata Emas", "rarity": "epic", "value": 1000, "weight": 4},
                {"name": "Kristal Legenda", "rarity": "legendary", "value": 5000, "weight": 1}
            ],
            "premium": [
                {"name": "Sayap Malaikat", "rarity": "epic", "value": 2000, "weight": 20},
                {"name": "Pedang Cahaya", "rarity": "epic", "value": 3000, "weight": 15},
                {"name": "Mahkota Raja", "rarity": "legendary", "value": 10000, "weight": 10},
                {"name": "Naga Api", "rarity": "mythic", "value": 50000, "weight": 5},
                {"name": "Phoenix Abadi", "rarity": "mythic", "value": 75000, "weight": 5},
                {"name": "Titan Essence", "rarity": "divine", "value": 150000, "weight": 1}
            ]
        }
        
        return gacha_pools.get(gacha_type, gacha_pools["normal"])

# Inisialisasi sistem ekonomi
economy = EconomySystem()

# ========== EVENT ==========
@bot.event
async def on_ready():
    print(f'✅ {bot.user} telah online!')
    print(f'✅ Prefix: {PREFIX}')
    print(f'✅ Sistem Ekonomi: Ready!')
    print(f'✅ Optimasi: XP otomatis DIHAPUS, cooldown ditambahkan')
    await bot.change_presence(activity=discord.Game(name=f"{PREFIX}help | Shop & Games"))
    check_daily_reset.start()

@bot.event
async def on_message(message):
    # TIDAK ADA XP OTOMATIS LAGI untuk menghindari rate limit
    await bot.process_commands(message)

# ========== TASK: RESET DAILY ==========
@tasks.loop(hours=24)
async def check_daily_reset():
    """Reset daily streak jika lebih dari 2 hari"""
    current_time = datetime.now()
    for user_id_str in economy.data:
        user_data = economy.data[user_id_str]
        if user_data["last_daily"]:
            last_daily = datetime.fromisoformat(user_data["last_daily"])
            if (current_time - last_daily).days > 2:
                user_data["daily_streak"] = 0
    economy._force_save()

# ========== SISTEM XP MANUAL (AMAN DARI RATE LIMIT) ==========
@bot.command(name='claimxp')
@commands.cooldown(1, 300, commands.BucketType.user)  # 1x per 5 menit
async def claim_xp(ctx):
    """Klaim XP secara manual (cooldown 5 menit)"""
    user_id = ctx.author.id
    xp_gained = random.randint(5, 15)  # Lebih banyak dari sistem lama
    level_ups = economy.add_xp(user_id, xp_gained)
    
    user_data = economy.get_user_data(user_id)
    
    embed = discord.Embed(
        title="🎮 **XP DICLAIM!**",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="⚡ XP Didapat", value=f"**+{xp_gained}** XP", inline=True)
    embed.add_field(name="📊 XP Total", value=f"**{user_data['xp']}**/{user_data['level'] * 100}", inline=True)
    
    if level_ups > 0:
        embed.title = "🎉 **LEVEL UP!**"
        embed.color = discord.Color.gold()
        embed.add_field(
            name="✨ Level Baru",
            value=f"**Level {user_data['level']}**! (+{level_ups * 100} koin bonus)",
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command(name='collect')
@commands.cooldown(1, 600, commands.BucketType.user)  # 1x per 10 menit
async def collect_rewards(ctx):
    """Kumpulkan reward berkala (cooldown 10 menit)"""
    user_id = ctx.author.id
    user_data = economy.get_user_data(user_id)
    
    # Cek cooldown internal
    current_time = datetime.now()
    if user_data["last_collect"]:
        last_collect = datetime.fromisoformat(user_data["last_collect"])
        if (current_time - last_collect).seconds < 600:
            time_left = 600 - (current_time - last_collect).seconds
            minutes = time_left // 60
            seconds = time_left % 60
            await ctx.send(f"⏰ **Cooldown!** Tunggu **{minutes} menit {seconds} detik** lagi.")
            return
    
    # Berikan reward acak
    rewards = [
        {"type": "xp", "min": 10, "max": 30, "emoji": "⚡"},
        {"type": "money", "min": 50, "max": 200, "emoji": "💵"},
        {"type": "both", "xp_min": 5, "xp_max": 15, "money_min": 25, "money_max": 100, "emoji": "🎁"}
    ]
    
    reward = random.choice(rewards)
    message = ""
    level_ups = 0
    
    if reward["type"] == "xp":
        xp = random.randint(reward["min"], reward["max"])
        level_ups = economy.add_xp(user_id, xp)
        message = f"{reward['emoji']} **+{xp} XP**"
    
    elif reward["type"] == "money":
        money = random.randint(reward["min"], reward["max"])
        economy.add_money(user_id, money, "Collect Reward")
        message = f"{reward['emoji']} **+{money} koin**"
    
    else:  # both
        xp = random.randint(reward["xp_min"], reward["xp_max"])
        money = random.randint(reward["money_min"], reward["money_max"])
        level_ups = economy.add_xp(user_id, xp)
        economy.add_money(user_id, money, "Collect Reward")
        message = f"{reward['emoji']} **+{xp} XP** dan **+{money} koin**"
    
    # Update last collect time
    user_data["last_collect"] = current_time.isoformat()
    economy.schedule_save()
    
    # Create embed
    embed = discord.Embed(
        title="🎁 **REWARD DICLAIM!**",
        description=f"{ctx.author.mention} mendapatkan reward!",
        color=discord.Color.green()
    )
    
    embed.add_field(name="📦 Hadiah", value=message, inline=False)
    
    if level_ups > 0:
        user_data = economy.get_user_data(user_id)  # Refresh data
        embed.add_field(
            name="✨ LEVEL UP!",
            value=f"**Level {user_data['level']}** tercapai! (+{level_ups * 100} koin bonus)",
            inline=False
        )
        embed.color = discord.Color.gold()
    
    embed.add_field(name="⏰ Cooldown", value="10 menit", inline=True)
    
    await ctx.send(embed=embed)

# ========== SISTEM EKONOMI: BASIC COMMANDS ==========
@bot.command(name='balance', aliases=['bal', 'uang', 'saldo'])
async def check_balance(ctx, member: discord.Member = None):
    """Cek saldo uang virtual"""
    target = member or ctx.author
    user_data = economy.get_user_data(target.id)
    
    embed = discord.Embed(
        title=f"💰 **SALDO {target.name}**",
        color=discord.Color.gold()
    )
    
    embed.add_field(name="💵 Dompet", value=f"**{user_data['balance']}** koin", inline=True)
    embed.add_field(name="🏦 Bank", value=f"**{user_data['bank']}** koin", inline=True)
    embed.add_field(name="📊 Total", value=f"**{user_data['balance'] + user_data['bank']}** koin", inline=True)
    
    embed.add_field(name="🎮 Level", value=f"**{user_data['level']}**", inline=True)
    embed.add_field(name="⭐ XP", value=f"**{user_data['xp']}**/{user_data['level'] * 100}", inline=True)
    embed.add_field(name="🔥 Daily Streak", value=f"**{user_data['daily_streak']}** hari", inline=True)
    
    embed.set_thumbnail(url=target.avatar.url if target.avatar else target.default_avatar.url)
    
    await ctx.send(embed=embed)

@bot.command(name='daily')
@commands.cooldown(1, 86400, commands.BucketType.user)  # 1x per 24 jam
async def daily_reward(ctx):
    """Klaim reward harian"""
    user_id = ctx.author.id
    user_data = economy.get_user_data(user_id)
    current_time = datetime.now()
    
    # Check if already claimed today
    if user_data["last_daily"]:
        last_daily = datetime.fromisoformat(user_data["last_daily"])
        if (current_time - last_daily).days < 1:
            time_left = timedelta(days=1) - (current_time - last_daily)
            hours = time_left.seconds // 3600
            minutes = (time_left.seconds % 3600) // 60
            
            embed = discord.Embed(
                title="⏰ **DAILY REWARD**",
                description=f"Anda sudah klaim daily hari ini!\nTunggu **{hours} jam {minutes} menit** lagi.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
    
    # Calculate reward
    streak = user_data["daily_streak"]
    base_reward = 100
    streak_bonus = min(streak * 10, 200)  # Max bonus 200
    total_reward = base_reward + streak_bonus
    
    # Update streak
    if (current_time - last_daily).days == 1 if user_data["last_daily"] else True:
        user_data["daily_streak"] += 1
    else:
        user_data["daily_streak"] = 1
    
    user_data["last_daily"] = current_time.isoformat()
    economy.add_money(user_id, total_reward, "Daily Reward")
    
    embed = discord.Embed(
        title="🎁 **DAILY REWARD BERHASIL!**",
        description=f"Selamat {ctx.author.mention}! Anda mendapatkan reward harian!",
        color=discord.Color.green()
    )
    
    embed.add_field(name="💵 Reward Dasar", value=f"**{base_reward}** koin", inline=True)
    embed.add_field(name="🔥 Streak Bonus", value=f"**{streak_bonus}** koin", inline=True)
    embed.add_field(name="💰 Total", value=f"**{total_reward}** koin", inline=True)
    embed.add_field(name="📅 Streak Saat Ini", value=f"**{user_data['daily_streak']}** hari berturut-turut", inline=False)
    
    # Special bonus for 7-day streak
    if user_data["daily_streak"] % 7 == 0:
        special_bonus = 500
        economy.add_money(user_id, special_bonus, "7-Day Streak Bonus")
        embed.add_field(name="🎊 **BONUS 7 HARI!**", value=f"Bonus tambahan **{special_bonus}** koin!", inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name='work', aliases=['kerja'])
@commands.cooldown(1, 3600, commands.BucketType.user)  # 1x per jam
async def work_command(ctx):
    """Bekerja untuk mendapatkan uang (cooldown 1 jam)"""
    user_id = ctx.author.id
    
    # Get random job and salary
    jobs = [
        {"name": "👨‍🍳 Koki Restoran", "min": 50, "max": 150},
        {"name": "👨‍💻 Programmer", "min": 100, "max": 300},
        {"name": "👷 Pekerja Konstruksi", "min": 30, "max": 100},
        {"name": "🎨 Desainer Grafis", "min": 80, "max": 250},
        {"name": "🚕 Driver Ojek Online", "min": 40, "max": 120},
        {"name": "👨‍🏫 Guru Les", "min": 60, "max": 180}
    ]
    
    job = random.choice(jobs)
    earnings = random.randint(job["min"], job["max"])
    
    # Give money
    new_balance = economy.add_money(user_id, earnings, f"Work: {job['name']}")
    
    embed = discord.Embed(
        title="💼 **BEKERJA**",
        description=f"{ctx.author.mention} bekerja sebagai **{job['name']}**!",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="💰 Gaji", value=f"**{earnings}** koin", inline=True)
    embed.add_field(name="💵 Saldo Baru", value=f"**{new_balance}** koin", inline=True)
    embed.add_field(name="⏰ Cooldown", value="1 jam", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='crime', aliases=['kejahatan'])
@commands.cooldown(1, 7200, commands.BucketType.user)  # 1x per 2 jam
async def crime_command(ctx):
    """Melakukan kejahatan untuk dapat uang cepat (risiko tinggi)"""
    user_id = ctx.author.id
    
    # Crime outcomes
    outcomes = [
        {"name": "🔫 Perampokan Bank", "success_rate": 0.3, "success_pay": 1000, "fail_loss": 500},
        {"name": "👜 Copet", "success_rate": 0.6, "success_pay": 200, "fail_loss": 100},
        {"name": "💎 Pencurian Permata", "success_rate": 0.4, "success_pay": 800, "fail_loss": 400},
        {"name": "🖥️ Hacking", "success_rate": 0.5, "success_pay": 400, "fail_loss": 200},
        {"name": "🚗 Pencurian Mobil", "success_rate": 0.35, "success_pay": 700, "fail_loss": 350}
    ]
    
    crime = random.choice(outcomes)
    success = random.random() < crime["success_rate"]
    
    if success:
        new_balance = economy.add_money(user_id, crime["success_pay"], f"Crime Success: {crime['name']}")
        
        embed = discord.Embed(
            title="✅ **KEJAHATAN BERHASIL!**",
            description=f"{ctx.author.mention} berhasil **{crime['name']}**!",
            color=discord.Color.green()
        )
        embed.add_field(name="💰 Hasil", value=f"**+{crime['success_pay']}** koin", inline=True)
        embed.add_field(name="💵 Saldo Baru", value=f"**{new_balance}** koin", inline=True)
    else:
        # Check if user has enough money
        user_data = economy.get_user_data(user_id)
        loss = min(crime["fail_loss"], user_data["balance"])
        
        if loss > 0:
            economy.remove_money(user_id, loss, f"Crime Failed: {crime['name']}")
            user_data = economy.get_user_data(user_id)
        
        embed = discord.Embed(
            title="❌ **KEJAHATAN GAGAL!**",
            description=f"{ctx.author.mention} gagal **{crime['name']}** dan ditangkap!",
            color=discord.Color.red()
        )
        embed.add_field(name="💸 Denda", value=f"**-{loss}** koin", inline=True)
        embed.add_field(name="💵 Saldo Baru", value=f"**{user_data['balance']}** koin", inline=True)
        embed.add_field(name="⚠️ Hukuman", value="2 jam cooldown", inline=True)
    
    await ctx.send(embed=embed)

# ========== SISTEM TRANSFER ==========
@bot.command(name='transfer', aliases=['tf', 'kirim'])
@commands.cooldown(3, 60, commands.BucketType.user)  # 3x per menit
async def transfer_money(ctx, member: discord.Member, amount: int):
    """Transfer uang ke member lain"""
    if amount <= 0:
        await ctx.send("❌ **Jumlah transfer harus lebih dari 0!**")
        return
    
    if member.bot:
        await ctx.send("❌ **Tidak bisa transfer ke bot!**")
        return
    
    if member.id == ctx.author.id:
        await ctx.send("❌ **Tidak bisa transfer ke diri sendiri!**")
        return
    
    success, message = economy.transfer_money(ctx.author.id, member.id, amount)
    
    if success:
        user_data = economy.get_user_data(ctx.author.id)
        embed = discord.Embed(
            title="✅ **TRANSFER BERHASIL!**",
            description=f"{ctx.author.mention} mentransfer **{amount}** koin ke {member.mention}",
            color=discord.Color.green()
        )
        embed.add_field(name="💰 Jumlah", value=f"**{amount}** koin", inline=True)
        embed.add_field(name="💵 Saldo Anda", value=f"**{user_data['balance']}** koin", inline=True)
        embed.add_field(name="📝 Catatan", value="Transfer tercatat di riwayat transaksi", inline=False)
    else:
        embed = discord.Embed(
            title="❌ **TRANSFER GAGAL!**",
            description=message,
            color=discord.Color.red()
        )
    
    await ctx.send(embed=embed)

@bot.command(name='rich', aliases=['top', 'leaderboard'])
@commands.cooldown(1, 30, commands.BucketType.channel)  # 1x per 30 detik per channel
async def rich_leaderboard(ctx):
    """Lihat leaderboard orang terkaya"""
    # Get top 10 users
    users = []
    for user_id_str, data in economy.data.items():
        try:
            user = await bot.fetch_user(int(user_id_str))
            total_wealth = data["balance"] + data["bank"]
            users.append((user, total_wealth, data["level"]))
        except:
            continue
    
    # Sort by wealth
    users.sort(key=lambda x: x[1], reverse=True)
    top_10 = users[:10]
    
    embed = discord.Embed(
        title="🏆 **LEADERBOARD KAYA RAYA**",
        description="10 Orang Terkaya di Server",
        color=discord.Color.gold()
    )
    
    for i, (user, wealth, level) in enumerate(top_10, 1):
        medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
        embed.add_field(
            name=f"{medal} {user.name}",
            value=f"💵 **{wealth:,}** koin | 🎮 Level {level}",
            inline=False
        )
    
    # Add author's rank if not in top 10
    author_wealth = economy.get_user_data(ctx.author.id)["balance"] + economy.get_user_data(ctx.author.id)["bank"]
    author_rank = next((i+1 for i, (user, wealth, _) in enumerate(users) if user.id == ctx.author.id), len(users)+1)
    
    embed.set_footer(text=f"Peringkat Anda: #{author_rank} dengan {author_wealth:,} koin")
    
    await ctx.send(embed=embed)

# ========== SISTEM GACHA ==========
@bot.command(name='gacha', aliases=['gatcha'])
@commands.cooldown(1, 10, commands.BucketType.user)  # 1x per 10 detik
async def gacha_command(ctx, gacha_type: str = "normal"):
    """Buka gacha untuk mendapatkan item langka"""
    user_id = ctx.author.id
    user_data = economy.get_user_data(user_id)
    
    # Check gacha type
    gacha_type = gacha_type.lower()
    if gacha_type not in ["normal", "premium"]:
        await ctx.send("❌ **Tipe gacha tidak valid!** Gunakan: `normal` atau `premium`")
        return
    
    # Check cost
    costs = {"normal": 100, "premium": 500}
    cost = costs[gacha_type]
    
    if user_data["balance"] < cost:
        await ctx.send(f"❌ **Saldo tidak cukup!** Dibutuhkan **{cost}** koin untuk gacha {gacha_type}")
        return
    
    # Deduct cost
    economy.remove_money(user_id, cost, f"Gacha {gacha_type}")
    
    # Get gacha pool
    pool = economy.get_gacha_pool(gacha_type)
    
    # Weighted random selection
    total_weight = sum(item["weight"] for item in pool)
    random_value = random.uniform(0, total_weight)
    
    current_weight = 0
    selected_item = None
    
    for item in pool:
        current_weight += item["weight"]
        if random_value <= current_weight:
            selected_item = item
            break
    
    # Add item to inventory
    economy.add_gacha_item(user_id, selected_item)
    
    # Give item value as money (or special effect for premium)
    item_value = selected_item["value"]
    economy.add_money(user_id, item_value, f"Gacha Item Value: {selected_item['name']}")
    
    # Create embed
    rarity_colors = {
        "common": discord.Color.light_gray(),
        "uncommon": discord.Color.green(),
        "rare": discord.Color.blue(),
        "epic": discord.Color.purple(),
        "legendary": discord.Color.gold(),
        "mythic": discord.Color.orange(),
        "divine": discord.Color.red()
    }
    
    color = rarity_colors.get(selected_item["rarity"], discord.Color.blue())
    
    embed = discord.Embed(
        title="🎊 **GACHA RESULT**",
        description=f"{ctx.author.mention} membuka **Gacha {gacha_type.title()}**!",
        color=color
    )
    
    # Add sparkle effect for higher rarities
    rarity_emojis = {
        "common": "⚪",
        "uncommon": "🟢",
        "rare": "🔵",
        "epic": "🟣",
        "legendary": "🟡",
        "mythic": "🟠",
        "divine": "🔴"
    }
    
    embed.add_field(
        name=f"{rarity_emojis.get(selected_item['rarity'], '⚪')} **ITEM DIPEROLEH**",
        value=f"**{selected_item['name']}**",
        inline=False
    )
    
    embed.add_field(name="✨ Rarity", value=f"**{selected_item['rarity'].upper()}**", inline=True)
    embed.add_field(name="💰 Nilai Item", value=f"**+{item_value}** koin", inline=True)
    embed.add_field(name="💸 Biaya Gacha", value=f"**-{cost}** koin", inline=True)
    
    # Calculate profit/loss
    profit = item_value - cost
    if profit > 0:
        embed.add_field(name="📈 Profit", value=f"**+{profit}** koin", inline=True)
    else:
        embed.add_field(name="📉 Loss", value=f"**{profit}** koin", inline=True)
    
    # Add special message for divine items
    if selected_item["rarity"] == "divine":
        embed.add_field(name="🎇 **LEGENDARY PULL!**", value="Anda mendapatkan item DIVINE! 🎉", inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name='gachainfo')
@commands.cooldown(1, 60, commands.BucketType.channel)  # 1x per menit per channel
async def gacha_info(ctx):
    """Lihat informasi tentang sistem gacha"""
    embed = discord.Embed(
        title="🎰 **SISTEM GACHA**",
        description="Informasi tentang sistem gacha dan drop rates",
        color=discord.Color.purple()
    )
    
    # Normal Gacha info
    normal_pool = economy.get_gacha_pool("normal")
    embed.add_field(
        name="🎪 **GACHA NORMAL** (100 koin)",
        value="Drop Rates:",
        inline=False
    )
    
    normal_text = ""
    for item in normal_pool:
        rate = (item["weight"] / sum(i["weight"] for i in normal_pool)) * 100
        normal_text += f"{item['rarity'].title()}: **{rate:.1f}%** - {item['name']} (💰{item['value']})\n"
    
    embed.add_field(name="📊 Rates", value=normal_text, inline=False)
    
    # Premium Gacha info
    premium_pool = economy.get_gacha_pool("premium")
    embed.add_field(
        name="💎 **GACHA PREMIUM** (500 koin)",
        value="Drop Rates:",
        inline=False
    )
    
    premium_text = ""
    for item in premium_pool:
        rate = (item["weight"] / sum(i["weight"] for i in premium_pool)) * 100
        premium_text += f"{item['rarity'].title()}: **{rate:.1f}%** - {item['name']} (💰{item['value']})\n"
    
    embed.add_field(name="📊 Rates", value=premium_text, inline=False)
    
    embed.add_field(
        name="💡 Tips",
        value=f"• Gunakan `{PREFIX}gacha normal` untuk gacha normal\n• Gunakan `{PREFIX}gacha premium` untuk gacha premium\n• Item akan otomatis dijual dan uang ditambahkan ke saldo",
        inline=False
    )
    
    await ctx.send(embed=embed)

# ========== INVENTORY SYSTEM ==========
@bot.command(name='inventory', aliases=['inv', 'items'])
@commands.cooldown(1, 10, commands.BucketType.user)  # 1x per 10 detik
async def show_inventory(ctx, member: discord.Member = None):
    """Lihat inventory user"""
    target = member or ctx.author
    inventory = economy.get_inventory(target.id)
    
    embed = discord.Embed(
        title=f"🎒 **INVENTORY {target.name}**",
        color=discord.Color.dark_green()
    )
    
    # Regular items
    if inventory["items"]:
        items_text = ""
        for item_name, quantity in inventory["items"].items():
            items_text += f"• {item_name}: **{quantity}**\n"
    else:
        items_text = "Tidak ada item"
    
    embed.add_field(name="📦 **Items**", value=items_text, inline=False)
    
    # Gacha items count by rarity
    if inventory["gacha_items"]:
        rarity_counts = {}
        for item in inventory["gacha_items"]:
            rarity = item["rarity"]
            rarity_counts[rarity] = rarity_counts.get(rarity, 0) + 1
        
        gacha_text = ""
        for rarity, count in rarity_counts.items():
            gacha_text += f"• {rarity.title()}: **{count}** item\n"
        
        embed.add_field(name="🎰 **Gacha Items**", value=gacha_text, inline=False)
    else:
        embed.add_field(name="🎰 **Gacha Items**", value="Belum ada item gacha", inline=False)
    
    # Badges
    if inventory["badges"]:
        badges_text = "\n".join([f"• {badge}" for badge in inventory["badges"]])
        embed.add_field(name="🏆 **Badges**", value=badges_text, inline=False)
    
    # Total gacha items value
    total_value = sum(item["value"] for item in inventory["gacha_items"])
    embed.set_footer(text=f"Total nilai gacha items: {total_value} koin")
    
    await ctx.send(embed=embed)

@bot.command(name='sell')
@commands.cooldown(1, 5, commands.BucketType.user)  # 1x per 5 detik
async def sell_item(ctx, item_name: str, quantity: int = 1):
    """Jual item dari inventory"""
    user_id = ctx.author.id
    inventory = economy.get_inventory(user_id)
    
    # Check if item exists
    if item_name not in inventory["items"] or inventory["items"][item_name] < quantity:
        await ctx.send(f"❌ **Item tidak ditemukan atau jumlah tidak cukup!**")
        return
    
    # Calculate sell price (50% of base value)
    item_values = {
        "Koin Emas": 50,
        "Permata Hijau": 100,
        "Permata Biru": 250,
        "Permata Ungu": 500,
        "Permata Emas": 1000,
        "Kristal Legenda": 5000
    }
    
    base_value = item_values.get(item_name, 10)
    sell_price = base_value * quantity // 2  # 50% value
    
    # Update inventory
    inventory["items"][item_name] -= quantity
    if inventory["items"][item_name] == 0:
        del inventory["items"][item_name]
    
    # Add money
    new_balance = economy.add_money(user_id, sell_price, f"Sell {item_name}")
    
    embed = discord.Embed(
        title="💰 **ITEM TERJUAL!**",
        description=f"{ctx.author.mention} menjual **{quantity}x {item_name}**",
        color=discord.Color.green()
    )
    
    embed.add_field(name="📦 Item", value=f"**{item_name}** x{quantity}", inline=True)
    embed.add_field(name="💵 Harga Jual", value=f"**{sell_price}** koin", inline=True)
    embed.add_field(name="💎 Saldo Baru", value=f"**{new_balance}** koin", inline=True)
    
    economy.schedule_save()
    await ctx.send(embed=embed)

# ========== PERBAIKAN HELP COMMAND (DENGAN EKONOMI) ==========
@bot.command(name='help')
@commands.cooldown(1, 10, commands.BucketType.user)  # 1x per 10 detik
async def bot_help(ctx):
    embed = discord.Embed(
        title="𖥔˚ BANTUAN BOT SHOP & GAMES",
        description=f"Prefix: `{PREFIX}`",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="𖥔˚ **PRICELIST**",
        value=f"""
        `{PREFIX}pricelist` - Lihat pricelist lengkap
        """,
        inline=False
    )
    
    embed.add_field(
        name="𖥔˚ **PEMBAYARAN**",
        value=f"""
        `{PREFIX}payment` - Tampilkan QR Code pembayaran
        `{PREFIX}payimage` - Kirim gambar QR Code langsung
        """,
        inline=False
    )
    

    embed.add_field(
        name="𖥔˚ **UTILITAS**",
        value=f"""
        `{PREFIX}done` - Link testimoni
        `{PREFIX}ping` - Cek koneksi bot
        `{PREFIX}help` - Tampilkan bantuan ini
        """,
        inline=False
    )
    
    embed.set_footer(text="✅ Sistem dioptimasi untuk menghindari rate limit Discord")
    
    await ctx.send(embed=embed)

# ========== ADMIN COMMANDS ==========
@bot.command(name='addmoney')
@commands.has_permissions(administrator=True)
@commands.cooldown(1, 10, commands.BucketType.user)
async def admin_add_money(ctx, member: discord.Member, amount: int):
    """Admin: Tambahkan uang ke user (admin only)"""
    new_balance = economy.add_money(member.id, amount, f"Admin Add by {ctx.author.name}")
    
    embed = discord.Embed(
        title="👑 **ADMIN ACTION**",
        description=f"{ctx.author.mention} menambahkan **{amount}** koin ke {member.mention}",
        color=discord.Color.gold()
    )
    embed.add_field(name="💰 Jumlah", value=f"**{amount}** koin", inline=True)
    embed.add_field(name="💵 Saldo Baru", value=f"**{new_balance}** koin", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='reseteco')
@commands.has_permissions(administrator=True)
@commands.cooldown(1, 30, commands.BucketType.user)
async def reset_economy(ctx, member: discord.Member):
    """Admin: Reset ekonomi user (admin only)"""
    user_id_str = str(member.id)
    
    if user_id_str in economy.data:
        old_balance = economy.data[user_id_str]["balance"]
        economy.data[user_id_str] = {
            "balance": 1000,
            "bank": 0,
            "xp": 0,
            "level": 1,
            "total_earned": 0,
            "total_spent": 0,
            "daily_streak": 0,
            "last_daily": None,
            "achievements": [],
            "transactions": [],
            "last_collect": None
        }
        economy._force_save()
        
        embed = discord.Embed(
            title="🔄 **RESET EKONOMI**",
            description=f"Ekonomi {member.mention} telah direset!",
            color=discord.Color.orange()
        )
        embed.add_field(name="💰 Saldo Lama", value=f"**{old_balance}** koin", inline=True)
        embed.add_field(name="💵 Saldo Baru", value=f"**1000** koin", inline=True)
    else:
        embed = discord.Embed(
            title="❌ **ERROR**",
            description=f"User {member.mention} tidak ditemukan dalam sistem ekonomi!",
            color=discord.Color.red()
        )
    
    await ctx.send(embed=embed)

# ========== TAMBAHKAN COMMAND-CCOMMAND LAIN YANG SUDAH ADA ==========
@bot.command(name='done')
@commands.cooldown(1, 10, commands.BucketType.user)
async def done_command(ctx):
    """Kirim link testimoni"""
    await ctx.send("**https://discord.com/channels/1452584833766129686/1452593189595648112\n\nmohon untuk share testi di sini ya mas, bebas record/ss**")

@bot.command(name='pricelist')
@commands.cooldown(1, 30, commands.BucketType.channel)
async def pricelist_command(ctx):
    """Tampilkan pricelist dalam format teks yang dipisah"""
    pricelist_part1 = """
📋 **PRICELIST DISCSHOP** 📋
========================================

**NITRO PROMOTION** 
https://discord.com/channels/1452584833766129686/1452839168697696278/1453019423358062683

**DECORATION DISCORD**
https://discord.com/channels/1452584833766129686/1452611173600985181/1452623490094993459

**THUMBNAIL & OVERLAY STREAMING**
https://discord.com/channels/1452584833766129686/1452611090906091620/1453018905684475946

**J0KI ORBS**
https://discord.com/channels/1452584833766129686/1453053305184849960
"""
    await ctx.send(pricelist_part1)

@bot.command(name='payment')
@commands.cooldown(1, 30, commands.BucketType.channel)
async def show_payment(ctx, invoice_id: str = None):
    """Tampilkan gambar pembayaran QR Code"""
    embed = discord.Embed(
        title="💳 **METODE PEMBAYARAN**",
        description="Pilih metode pembayaran di bawah:",
        color=discord.Color.green()
    )
    
    try:
        await ctx.send("**🏦 QR CODE ALLPAY:**")
        await ctx.send("https://image2url.com/r2/bucket3/images/1766903385567-ce0ecef3-a493-4bd4-8b5c-ca5c68f3acc5.png")
        
        instructions = discord.Embed(
            title="📋 **CARA PEMBAYARAN**",
            color=discord.Color.orange()
        )
        instructions.add_field(
            name="LANGKAH-LANGKAH",
            value="""
            1️⃣ **Pilih metode** transfer di atas
            2️⃣ **Scan QR** dengan aplikasi bank/e-wallet
            3️⃣ **Transfer** sesuai jumlah
            4️⃣ **Screenshot** bukti transfer
            5️⃣ **Kirim** ke admin untuk konfirmasi
            
            """,
            inline=False
        )
        
        if invoice_id:
            instructions.add_field(
                name="📄 **INVOICE ID**",
                value=f"`{invoice_id}`",
                inline=False
            )
        
        await ctx.send(embed=instructions)
        
    except Exception as e:
        await ctx.send(f"❌ Gagal menampilkan QR Code: {str(e)}")

@bot.command(name='payimage')
@commands.cooldown(1, 30, commands.BucketType.channel)
async def send_payment_image(ctx):
    """Kirim gambar QR Code pembayaran langsung"""
    await ctx.send("**💳 GAMBAR PEMBAYARAN:**")
    await ctx.send("https://image2url.com/r2/bucket3/images/1766903385567-ce0ecef3-a493-4bd4-8b5c-ca5c68f3acc5.png")
    await ctx.send("**📋 INSTRUKSI:** Transfer sesuai nominal, lalu kirim bukti ke admin!")

@bot.command(name='ping')
@commands.cooldown(1, 5, commands.BucketType.user)
async def ping(ctx):
    """Cek koneksi bot"""
    latency = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong! {latency}ms")

# ========== COOLDOWN ERROR HANDLER ==========
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        # Format waktu cooldown
        seconds = error.retry_after
        if seconds > 3600:
            time_str = f"{seconds // 3600} jam {seconds % 3600 // 60} menit"
        elif seconds > 60:
            time_str = f"{seconds // 60} menit {seconds % 60} detik"
        else:
            time_str = f"{seconds:.1f} detik"
        
        embed = discord.Embed(
            title="⏰ **COOLDOWN**",
            description=f"Command sedang dalam cooldown!\nTunggu **{time_str}** lagi.",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)
    
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send(f"❌ Command tidak ditemukan! Ketik `{PREFIX}help` untuk bantuan.")
    
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Argument kurang! Ketik `{PREFIX}help` untuk format yang benar.")
    
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Argument tidak valid! Periksa format command.")
    
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Anda tidak memiliki izin untuk menggunakan command ini!")
    
    else:
        # Log error tanpa mengirim ke user
        print(f"Error pada command {ctx.command}: {str(error)}")
        await ctx.send("❌ Terjadi error internal. Silakan coba lagi nanti.")

# ========== SHUTDOWN HANDLER ==========
@bot.event
async def on_disconnect():
    """Save data saat bot disconnect"""
    print("⚠️ Bot disconnected, saving data...")
    economy._force_save()

@bot.event
async def close():
    """Save data saat bot shutdown"""
    print("🛑 Bot shutting down, saving data...")
    economy._force_save()
    await super().close()

# ========== RUNNING BOT ==========
if __name__ == "__main__":
    print("🚀 Starting Discord Shop Bot with Economy System...")
    print(f"✅ Economy features: Balance, Daily, Work, Crime, Transfer, Gacha")
    print(f"✅ Game features: Tebak Angka, Suit, Flip Coin, Dadu, Slot")
    print(f"✅ Prefix: {PREFIX}")
    print(f"✅ OPTIMIZATION: XP auto system REMOVED to prevent rate limits")
    print(f"✅ OPTIMIZATION: Cooldowns added to all commands")
    print(f"✅ OPTIMIZATION: Debounced file saving implemented")
    print("🔗 Connecting to Discord...")
    
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
        economy._force_save()
    except Exception as e:
        print(f"❌ Error: {e}")
        economy._force_save()