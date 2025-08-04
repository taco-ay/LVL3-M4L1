import discord
from discord.ext import commands, tasks
from logic import DatabaseManager
from config import TOKEN, DATABASE
import os
import sqlite3

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

manager = DatabaseManager(DATABASE)

@bot.event
async def on_ready():
    print(f'🔔 {bot.user} olarak giriş yapıldı!')
    manager.create_tables()

    if not send_message.is_running():
        send_message.start()
        print("🕐 'send_message' görevi başlatıldı.")
    else:
        print("🕐 'send_message' görevi zaten çalışıyor.")

@bot.command()
async def start(ctx):
    user_id = ctx.author.id
    user_name = ctx.author.name

    if user_id in manager.get_users():
        await ctx.send("Zaten kayıtlısınız!")
    else:
        manager.add_user(user_id, user_name)
        await ctx.send("""Merhaba! Başarılı bir şekilde kaydoldunuz!
Her dakika yeni resimler alacaksınız. “Al!” butonuna tıklayın!
Sadece ilk 3 kişi resmi kazanacak!""")
    print(f"'{ctx.author.name}' tarafından !start komutu kullanıldı.")

@tasks.loop(minutes=1)
async def send_message():
    print("✅ 'send_message' görevi çalışıyor...")

    users = manager.get_users()
    if not users:
        print("⚠️ Kayıtlı kullanıcı bulunamadı, resim gönderilemiyor.")
        return

    random_prize_data = manager.get_random_prize()

    if random_prize_data is None:
        print("⚠️ Gönderilecek uygun ödül kalmadı.")
        return

    prize_id, img_name = random_prize_data
    image_path_hidden = os.path.join('hidden_img', img_name)

    if not os.path.exists(image_path_hidden):
        print(f"❌ Gizli resim bulunamadı: {image_path_hidden}")
        return

    for user_id in users:
        try:
            user = await bot.fetch_user(user_id)
            if user:
                await send_image(user, image_path_hidden, prize_id)
        except Exception as e:
            print(f"❌ {user_id} için resim gönderilemedi: {e}")

    manager.mark_prize_used_session(prize_id)

async def send_image(user, image_path, prize_id):
    try:
        with open(image_path, 'rb') as img_file:
            file = discord.File(img_file, filename=os.path.basename(image_path))
            button = discord.ui.Button(label="Al!", custom_id=f"get_prize_{prize_id}")
            view = discord.ui.View(timeout=None)
            view.add_item(button)
            await user.send(file=file, view=view)
            print(f"{user.name} kullanıcısına ödül gönderildi.")
    except Exception as e:
        print(f"❌ Resim gönderim hatası: {e}")

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data['custom_id']
        user_id = interaction.user.id
        user_name = interaction.user.name

        if custom_id.startswith("get_prize_"):
            prize_id = int(custom_id.replace("get_prize_", ""))
            print(f"{user_name} ({user_id}) ödül {prize_id} için tıkladı.")

            if manager.get_winners_count(prize_id) >= 3 or manager.has_user_won(user_id, prize_id):
                await interaction.response.send_message("Üzgünüm, bu ödülü alamazsınız.", ephemeral=True)
                return

            if manager.add_winner(user_id, prize_id):
                img_name = manager.get_prize_img(prize_id)
                original_path = os.path.join('img', img_name)

                if os.path.exists(original_path):
                    with open(original_path, 'rb') as photo:
                        file = discord.File(photo, filename=img_name)
                        await interaction.response.send_message(file=file, content="🎉 Tebrikler! Ödülü kazandınız!")
                else:
                    await interaction.response.send_message("Resim kayboldu ama yine de kazandınız! 😅", ephemeral=True)
            else:
                await interaction.response.send_message("Bu ödülü zaten aldınız veya kontenjan dolu.", ephemeral=True)

    await bot.process_commands(interaction)

# Derecelendirme komutu
@bot.command()
async def rating(ctx):
    rating_list = manager.get_rating()
    if not rating_list:
        await ctx.send("Henüz kimse ödül kazanmadı.")
    else:
        message = "**🏅 İlk 10 Kullanıcı Sıralaması:**\n"
        for i, (name, count) in enumerate(rating_list, start=1):
            message += f"{i}. {name}: {count} ödül\n"
        await ctx.send(message)

# Debug komutları
@bot.command()
async def debug_users(ctx):
    users = manager.get_users()
    await ctx.send(f"👥 Kullanıcılar: {users if users else 'Yok'}")

@bot.command()
async def debug_list(ctx):
    conn = sqlite3.connect(manager.database)
    with conn:
        cur = conn.cursor()
        cur.execute('SELECT prize_id, image, used FROM prizes')
        rows = cur.fetchall()
    if rows:
        message = '\n'.join([f"{pid}: {img} (used={used})" for pid, img, used in rows])
    else:
        message = "🎁 Ödül yok."
    await ctx.send(message[:2000])

@bot.command()
async def debug_winners(ctx):
    conn = sqlite3.connect(manager.database)
    with conn:
        cur = conn.cursor()
        cur.execute('SELECT * FROM winners')
        winners = cur.fetchall()
    if winners:
        message = '\n'.join([str(w) for w in winners])
    else:
        message = "🏆 Kazanan yok."
    await ctx.send(message[:2000])

@bot.command()
async def debug_all(ctx):
    await debug_users(ctx)
    await debug_list(ctx)
    await debug_winners(ctx)

bot.run(TOKEN)
