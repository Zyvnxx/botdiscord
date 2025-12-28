import discord
import random
from discord.ext import commands
from datetime import datetime
import os
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

bot = commands.Bot(
    command_prefix=PREFIX, 
    intents=intents, 
    help_command=None,
    case_insensitive=True
)

# ========== GAME VARIABLES ==========
rps_stats = {}  # {user_id: {wins, losses, draws}}
guessing_games = {}  # {channel_id: {"number": num, "attempts": int}}
coin_flip_stats = {}  # {user_id: {wins, losses}}
hangman_games = {}  # {channel_id: game_data}

# ========== EVENT ==========
@bot.event
async def on_ready():
    print(f'✅ {bot.user} telah online!')
    print(f'✅ Prefix: {PREFIX}')
    await bot.change_presence(activity=discord.Game(name=f"{PREFIX}help | Shop Bot & Games"))

# ========== GAME: TEBAK ANGKA ==========
@bot.command(name='tebak', aliases=['guess'])
async def guess_number(ctx):
    """Mulai permainan tebak angka 1-100"""
    channel_id = ctx.channel.id
    
    if channel_id in guessing_games:
        await ctx.send("🎮 **Sudah ada permainan tebak angka di channel ini!**")
        return
    
    number = random.randint(1, 100)
    guessing_games[channel_id] = {
        "number": number,
        "attempts": 0,
        "creator": ctx.author.id
    }
    
    embed = discord.Embed(
        title="🔢 **PERMAINAN TEBAK ANGKA**",
        description="Saya telah memilih angka antara **1 sampai 100**!",
        color=discord.Color.blue()
    )
    embed.add_field(name="🎯 Cara Bermain", value="Coba tebak dengan `.tebakangka [angka]`", inline=False)
    embed.add_field(name="⏱️ Batas Waktu", value="Game akan berakhir dalam 5 menit", inline=False)
    embed.set_footer(text=f"Dimulai oleh: {ctx.author.name}")
    
    await ctx.send(embed=embed)

@bot.command(name='tebakangka')
async def guess_number_input(ctx, angka: int):
    """Tebak angka dalam permainan"""
    channel_id = ctx.channel.id
    
    if channel_id not in guessing_games:
        await ctx.send("❌ **Tidak ada permainan tebak angka aktif di channel ini!**\nMulai dengan `.tebak`")
        return
    
    game = guessing_games[channel_id]
    game["attempts"] += 1
    target = game["number"]
    
    if angka == target:
        embed = discord.Embed(
            title="🎉 **SELAMAT! ANDA MENANG!**",
            description=f"Angka yang benar adalah **{target}**",
            color=discord.Color.green()
        )
        embed.add_field(name="🎯 Tebakan Anda", value=f"**{angka}** ✅", inline=True)
        embed.add_field(name="📊 Total Percobaan", value=f"**{game['attempts']}** kali", inline=True)
        embed.set_footer(text=f"Pemenang: {ctx.author.name}")
        
        del guessing_games[channel_id]
        await ctx.send(embed=embed)
        
    elif angka < target:
        await ctx.send(f"📈 **Terlalu rendah!** Coba angka yang lebih besar dari **{angka}**")
    else:
        await ctx.send(f"📉 **Terlalu tinggi!** Coba angka yang lebih kecil dari **{angka}**")

# ========== GAME: SUIT (BATU GUNTING KERTAS) ==========
@bot.command(name='suit', aliases=['rps', 'batu'])
async def rock_paper_scissors(ctx, pilihan: str = None):
    """Mainkan batu, gunting, kertas melawan bot"""
    
    if not pilihan:
        embed = discord.Embed(
            title="🪨✂️📄 **BATU GUNTING KERTAS**",
            description="Pilih salah satu: `batu`, `gunting`, atau `kertas`",
            color=discord.Color.blue()
        )
        embed.add_field(name="🎮 Cara Main", value=f"`.suit [pilihan]`\nContoh: `.suit batu`", inline=False)
        embed.add_field(name="🏆 Statistik", value=f"Lihat statistik dengan `.suitstats`", inline=False)
        await ctx.send(embed=embed)
        return
    
    pilihan = pilihan.lower()
    if pilihan not in ['batu', 'gunting', 'kertas']:
        await ctx.send("❌ **Pilihan tidak valid!** Gunakan: `batu`, `gunting`, atau `kertas`")
        return
    
    # Bot memilih
    bot_choices = ['batu', 'gunting', 'kertas']
    bot_choice = random.choice(bot_choices)
    
    # Emoji untuk setiap pilihan
    emojis = {
        'batu': '🪨',
        'gunting': '✂️',
        'kertas': '📄'
    }
    
    # Tentukan pemenang
    if pilihan == bot_choice:
        result = "SERI!"
        winner = "tidak ada"
        stat_key = "draws"
    elif (pilihan == 'batu' and bot_choice == 'gunting') or \
         (pilihan == 'gunting' and bot_choice == 'kertas') or \
         (pilihan == 'kertas' and bot_choice == 'batu'):
        result = "ANDA MENANG! 🎉"
        winner = ctx.author.name
        stat_key = "wins"
    else:
        result = "BOT MENANG! 🤖"
        winner = "Bot"
        stat_key = "losses"
    
    # Update statistik
    user_id = ctx.author.id
    if user_id not in rps_stats:
        rps_stats[user_id] = {"wins": 0, "losses": 0, "draws": 0}
    rps_stats[user_id][stat_key] += 1
    
    # Buat embed hasil
    embed = discord.Embed(
        title="🪨✂️📄 **HASIL SUIT**",
        color=discord.Color.gold()
    )
    embed.add_field(name=f"👤 {ctx.author.name}", value=f"{emojis[pilihan]} **{pilihan.upper()}**", inline=True)
    embed.add_field(name="🤖 Bot", value=f"{emojis[bot_choice]} **{bot_choice.upper()}**", inline=True)
    embed.add_field(name="🏆 Hasil", value=f"**{result}**", inline=False)
    embed.set_footer(text=f"Pemenang: {winner}")
    
    await ctx.send(embed=embed)

@bot.command(name='suitstats')
async def rps_stats_command(ctx):
    """Lihat statistik suit Anda"""
    user_id = ctx.author.id
    
    if user_id not in rps_stats:
        embed = discord.Embed(
            title="📊 **STATISTIK SUIT**",
            description="Anda belum pernah bermain suit!",
            color=discord.Color.blue()
        )
    else:
        stats = rps_stats[user_id]
        total = stats["wins"] + stats["losses"] + stats["draws"]
        win_rate = (stats["wins"] / total * 100) if total > 0 else 0
        
        embed = discord.Embed(
            title="📊 **STATISTIK SUIT**",
            description=f"Statistik untuk {ctx.author.mention}",
            color=discord.Color.green()
        )
        embed.add_field(name="🎯 Menang", value=f"**{stats['wins']}** kali", inline=True)
        embed.add_field(name="💀 Kalah", value=f"**{stats['losses']}** kali", inline=True)
        embed.add_field(name="🤝 Seri", value=f"**{stats['draws']}** kali", inline=True)
        embed.add_field(name="📈 Win Rate", value=f"**{win_rate:.1f}%**", inline=True)
        embed.add_field(name="📊 Total Game", value=f"**{total}** game", inline=True)
    
    await ctx.send(embed=embed)

# ========== GAME: FLIP COIN ==========
@bot.command(name='flip', aliases=['coin', 'koin'])
async def flip_coin(ctx, tebakan: str = None):
    """Lempar koin dan tebak hasilnya"""
    
    if tebakan:
        tebakan = tebakan.lower()
        if tebakan not in ['angka', 'gambar', 'head', 'tail']:
            await ctx.send("❌ **Tebakan tidak valid!** Gunakan: `angka` atau `gambar`")
            return
    
    # Lempar koin
    coin = ['angka', 'gambar']
    result = random.choice(coin)
    
    # Emoji
    emoji = "🪙" if result == "angka" else "🪙"
    result_display = "**ANGKA**" if result == "angka" else "**GAMBAR**"
    
    # Tentukan apakah user menang jika menebak
    if tebakan:
        win = False
        if (tebakan == 'angka' and result == 'angka') or \
           (tebakan == 'gambar' and result == 'gambar') or \
           (tebakan == 'head' and result == 'angka') or \
           (tebakan == 'tail' and result == 'gambar'):
            win = True
        
        # Update statistik
        user_id = ctx.author.id
        if user_id not in coin_flip_stats:
            coin_flip_stats[user_id] = {"wins": 0, "losses": 0}
        
        if win:
            coin_flip_stats[user_id]["wins"] += 1
            result_msg = "✅ **ANDA MENANG!** 🎉"
        else:
            coin_flip_stats[user_id]["losses"] += 1
            result_msg = "❌ **ANDA KALAH!** 💀"
        
        embed = discord.Embed(
            title=f"{emoji} **LEMPAR KOIN**",
            description=f"Anda menebak: **{tebakan.upper()}**",
            color=discord.Color.green() if win else discord.Color.red()
        )
        embed.add_field(name="🎯 Hasil", value=result_display, inline=True)
        embed.add_field(name="🏆 Status", value=result_msg, inline=True)
        
    else:
        embed = discord.Embed(
            title=f"{emoji} **LEMPAR KOIN**",
            description="Koin dilempar!",
            color=discord.Color.gold()
        )
        embed.add_field(name="🎯 Hasil", value=result_display, inline=True)
        embed.add_field(name="💡 Tips", value="Tebak dengan `.flip [angka/gambar]`", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='flipstats')
async def coin_stats_command(ctx):
    """Lihat statistik flip coin"""
    user_id = ctx.author.id
    
    if user_id not in coin_flip_stats:
        embed = discord.Embed(
            title="📊 **STATISTIK FLIP COIN**",
            description="Anda belum pernah bermain flip coin!",
            color=discord.Color.blue()
        )
    else:
        stats = coin_flip_stats[user_id]
        total = stats["wins"] + stats["losses"]
        win_rate = (stats["wins"] / total * 100) if total > 0 else 0
        
        embed = discord.Embed(
            title="📊 **STATISTIK FLIP COIN**",
            description=f"Statistik untuk {ctx.author.mention}",
            color=discord.Color.green()
        )
        embed.add_field(name="✅ Menang", value=f"**{stats['wins']}** kali", inline=True)
        embed.add_field(name="❌ Kalah", value=f"**{stats['losses']}** kali", inline=True)
        embed.add_field(name="📈 Win Rate", value=f"**{win_rate:.1f}%**", inline=True)
        embed.add_field(name="📊 Total Game", value=f"**{total}** game", inline=True)
    
    await ctx.send(embed=embed)

# ========== GAME: DADU ==========
@bot.command(name='dadu', aliases=['dice', 'roll'])
async def roll_dice(ctx, jumlah_dadu: int = 1):
    """Lempar dadu (1-5 dadu sekaligus)"""
    
    if jumlah_dadu < 1 or jumlah_dadu > 5:
        await ctx.send("❌ **Jumlah dadu tidak valid!** Pilih 1-5 dadu")
        return
    
    results = []
    total = 0
    
    for i in range(jumlah_dadu):
        roll = random.randint(1, 6)
        results.append(roll)
        total += roll
    
    # Format hasil
    dice_emojis = ['⚀', '⚁', '⚂', '⚃', '⚄', '⚅']
    dice_display = " | ".join([f"{dice_emojis[r-1]} **{r}**" for r in results])
    
    embed = discord.Embed(
        title="🎲 **LEMPAR DADU**",
        color=discord.Color.purple()
    )
    embed.add_field(name="🎯 Hasil", value=dice_display, inline=False)
    
    if jumlah_dadu > 1:
        embed.add_field(name="📊 Total", value=f"**{total}**", inline=True)
        embed.add_field(name="📈 Rata-rata", value=f"**{total/jumlah_dadu:.1f}**", inline=True)
    
    embed.set_footer(text=f"Dilempar oleh: {ctx.author.name}")
    
    await ctx.send(embed=embed)

# ========== GAME: SLOT MACHINE SEDERHANA ==========
@bot.command(name='slot', aliases=['slots'])
async def slot_machine(ctx):
    """Mainkan mesin slot sederhana"""
    
    # Simbol slot
    symbols = ["🍒", "🍋", "🍊", "🍉", "🍇", "⭐", "7️⃣", "🔔"]
    
    # Putar slot
    slot1 = random.choice(symbols)
    slot2 = random.choice(symbols)
    slot3 = random.choice(symbols)
    
    # Tentukan hasil
    if slot1 == slot2 == slot3:
        result = "🎉 **JACKPOT!** 🎉"
        color = discord.Color.gold()
    elif slot1 == slot2 or slot2 == slot3 or slot1 == slot3:
        result = "✅ **HAMPIR!**"
        color = discord.Color.green()
    else:
        result = "❌ **COBA LAGI!**"
        color = discord.Color.red()
    
    # Buat tampilan slot
    slot_display = f"**[ {slot1} | {slot2} | {slot3} ]**"
    
    embed = discord.Embed(
        title="🎰 **MESIN SLOT**",
        description=slot_display,
        color=color
    )
    embed.add_field(name="🏆 Hasil", value=result, inline=False)
    embed.set_footer(text=f"Dimainkan oleh: {ctx.author.name}")
    
    await ctx.send(embed=embed)

# ========== PERBAIKAN HELP COMMAND ==========
@bot.command(name='help')
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
        name="𖥔˚ **GAMES**",
        value=f"""
        `{PREFIX}tebak` - Mulai tebak angka 1-100
        `{PREFIX}tebakangka [angka]` - Tebak angka
        `{PREFIX}suit [batu/gunting/kertas]` - Batu gunting kertas
        `{PREFIX}suitstats` - Lihat statistik suit
        `{PREFIX}flip [angka/gambar]` - Lempar koin
        `{PREFIX}flipstats` - Statistik flip coin
        `{PREFIX}dadu [jumlah]` - Lempar dadu (1-5)
        `{PREFIX}slot` - Main mesin slot
        `{PREFIX}games` - Lihat semua game
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
    
    await ctx.send(embed=embed)

# ========== COMMAND GAMES LIST ==========
@bot.command(name='games')
async def games_list(ctx):
    """Tampilkan semua game yang tersedia"""
    embed = discord.Embed(
        title="🎮 **DAFTAR PERMAINAN**",
        description="Semua game yang tersedia di bot ini:",
        color=discord.Color.purple()
    )
    
    embed.add_field(
        name="🔢 **TEBAK ANGKA**",
        value=f"""
        `{PREFIX}tebak` - Mulai permainan
        `{PREFIX}tebakangka [angka]` - Tebak angka
        Tebak angka 1-100 dengan percobaan sebanyak mungkin
        """,
        inline=False
    )
    
    embed.add_field(
        name="🪨✂️📄 **BATU GUNTING KERTAS**",
        value=f"""
        `{PREFIX}suit [pilihan]` - Main melawan bot
        `{PREFIX}suitstats` - Lihat statistik
        Pilihan: batu, gunting, kertas
        """,
        inline=False
    )
    
    embed.add_field(
        name="🪙 **LEMPAR KOIN**",
        value=f"""
        `{PREFIX}flip [angka/gambar]` - Lempar dan tebak koin
        `{PREFIX}flipstats` - Lihat statistik
        Tebak hasil lemparan koin
        """,
        inline=False
    )
    
    embed.add_field(
        name="🎲 **PERMAINAN LAINNYA**",
        value=f"""
        `{PREFIX}dadu [jumlah]` - Lempar 1-5 dadu
        `{PREFIX}slot` - Main mesin slot sederhana
        """,
        inline=False
    )
    
    embed.set_footer(text="Selamat bermain! 🎮")
    
    await ctx.send(embed=embed)

# ========== COMMAND CLEANUP (MENGHAPUS GAME YANG TIDAK AKTIF) ==========
@bot.command(name='cleargames')
@commands.has_permissions(administrator=True)
async def clear_inactive_games(ctx):
    """Hapus game yang tidak aktif (admin only)"""
    removed = 0
    
    # Hapus game tebak angka yang sudah lama
    for channel_id in list(guessing_games.keys()):
        try:
            del guessing_games[channel_id]
            removed += 1
        except:
            pass
    
    await ctx.send(f"✅ **Berhasil membersihkan {removed} game yang tidak aktif!**")

# ========== TAMBAHKAN COMMAND-CCOMMAND LAIN YANG SUDAH ADA ==========
# (Masukkan semua command yang sudah ada di sini: done, pricelist, payment, payimage, ping)

@bot.command(name='done')
async def done_command(ctx):
    """Kirim link testimoni"""
    await ctx.send("**https://discord.com/channels/1452584833766129686/1452593189595648112\n\nmohon untuk share testi di sini ya mas, bebas record/ss**")

@bot.command(name='pricelist')
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
async def show_payment(ctx, invoice_id: str = None):
    """Tampilkan gambar pembayaran QR Code"""
    embed = discord.Embed(
        title="💳 **METODE PEMBAYARAN**",
        description="Pilih metode pembayaran di bawah:",
        color=discord.Color.green()
    )
    
    embed.add_field(
        name="🏦 **TRANSFER BANK**",
        value="""
        **SEABANK**
        ```
        No. Rek: 901926260432
        Atas Nama: Naufal Dhiyaul Haq
        ```
        """,
        inline=False
    )
    
    await ctx.send(embed=embed)
    
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
async def send_payment_image(ctx):
    """Kirim gambar QR Code pembayaran langsung"""
    await ctx.send("**💳 GAMBAR PEMBAYARAN:**")
    await ctx.send("https://image2url.com/r2/bucket3/images/1766903385567-ce0ecef3-a493-4bd4-8b5c-ca5c68f3acc5.png")
    await ctx.send("**📋 INSTRUKSI:** Transfer sesuai nominal, lalu kirim bukti ke admin!")

@bot.command(name='ping')
async def ping(ctx):
    """Cek koneksi bot"""
    latency = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong! {latency}ms")

# ========== ERROR HANDLER ==========
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(f"❌ Command tidak ditemukan! Ketik `{PREFIX}help` untuk bantuan.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Argument kurang! Ketik `{PREFIX}help` untuk format yang benar.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Argument tidak valid! Periksa format command.")
    else:
        await ctx.send(f"❌ Error: {str(error)}")

# ========== JALANKAN BOT ==========
if __name__ == "__main__":
    print("🚀 Starting Discord Shop Bot with Games...")
    print(f"🎮 Game features: Tebak Angka, Suit, Flip Coin, Dadu, Slot")
    print(f"📝 Prefix: {PREFIX}")
    print("⏳ Connecting to Discord...")
    bot.run(TOKEN)