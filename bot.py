import discord
from discord.ext import commands, tasks
from logic import DatabaseManager # hide_img'i artık doğrudan burada çağırmıyoruz
from config import TOKEN, DATABASE
import os

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
        await ctx.send("""Merhaba! Hoş geldiniz! Başarılı bir şekilde kaydoldunuz!
Her dakika yeni resimler alacaksınız ve bunları elde etme şansınız olacak!
Bunu yapmak için “Al!” butonuna tıklamanız gerekiyor!
Sadece “Al!” butonuna tıklayan ilk üç kullanıcı resmi alacaktır! =)""")
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
        print("⚠️ Kullanılmamış ve 3'ten az kazananı olan uygun ödül kalmadı. (Yeni ödül ekleyin veya mevcut ödülleri sıfırlayın)")
        return 

    prize_id, img_name = random_prize_data
    image_path_hidden = os.path.join('hidden_img', img_name)

    if not os.path.exists(image_path_hidden):
        print(f"❌ Gizlenmiş resim dosyası bulunamadı: {image_path_hidden}. Lütfen logic.py'yi çalıştırdığınızdan emin olun.")
        return 

    sent_count = 0
    for user_id in users:
        try:
            user = await bot.fetch_user(user_id)
            if user:
                await send_image(user, image_path_hidden, prize_id)
                sent_count += 1
            else:
                print(f"Kullanıcı {user_id} bulunamadı.")
        except discord.errors.NotFound:
            print(f"Kullanıcı {user_id} bulunamadı (Botun olduğu sunucuda olmayabilir veya silinmiş olabilir).")
        except Exception as e:
            print(f"❌ Kullanıcı {user_id} için resim gönderilirken hata oluştu: {e}")
            
    manager.mark_prize_used_session(prize_id) 


async def send_image(user, image_path, prize_id):
    try:
        with open(image_path, 'rb') as img_file:
            file = discord.File(img_file, filename=os.path.basename(image_path))
            button = discord.ui.Button(label="Al!", custom_id=f"get_prize_{prize_id}") 
            view = discord.ui.View(timeout=None) 
            view.add_item(button)
            await user.send(file=file, view=view)
            print(f"Ödül {prize_id} ({os.path.basename(image_path)}) {user.name} kullanıcısına gönderildi.")
    except Exception as e:
        print(f"❌ Kullanıcıya {image_path} gönderilirken hata oluştu: {e}")


@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data['custom_id']
        user_id = interaction.user.id
        
        if custom_id.startswith("get_prize_"):
            prize_id_str = custom_id.replace("get_prize_", "") 
            try:
                prize_id = int(prize_id_str)
            except ValueError:
                await interaction.response.send_message(content="Hatalı ödül kimliği.", ephemeral=True)
                print(f"❌ Hatalı custom_id formatı: {custom_id}")
                return

            print(f"Kullanıcı {interaction.user.name} ({user_id}), ödül {prize_id} için 'Al!' butonuna tıkladı.")

            img_name = manager.get_prize_img(prize_id)
            if img_name is None:
                await interaction.response.send_message(content="Üzgünüm, bu ödül bulunamadı.", ephemeral=True)
                print(f"Ödül {prize_id} veritabanında bulunamadı.")
                return

            if manager.add_winner(user_id, prize_id):
                original_image_path = os.path.join('img', img_name)
                if os.path.exists(original_image_path):
                    with open(original_image_path, 'rb') as photo:
                        file = discord.File(photo, filename=img_name)
                        await interaction.response.send_message(file=file, content="Tebrikler, resmi aldınız!")
                        print(f"✅ Kullanıcı {interaction.user.name} ödül {prize_id}'i başarıyla aldı.")
                else:
                    await interaction.response.send_message(content="Tebrikler, resmi aldınız! Ancak orijinal resim dosyası bulunamadı.", ephemeral=True)
                    print(f"❌ Orijinal resim dosyası bulunamadı: {original_image_path}")
            else:
                await interaction.response.send_message(content="Maalesef, bu resmi bir başkası çoktan aldı veya siz zaten aldınız...", ephemeral=True)
                print(f"Kullanıcı {interaction.user.name} ödül {prize_id}'i alamadı (limit veya zaten almış).")
    
    await bot.process_commands(interaction)

bot.run(TOKEN)
