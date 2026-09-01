import os
import telebot
import threading
import time
from datetime import datetime
from supabase import create_client, Client

# Ambil data rahasia dari Environment Variables sistem
TOKEN_KLIEN = os.getenv('TOKEN_KLIEN')
ID_GRUP = int(os.getenv('ID_GRUP', '-5479813397'))  
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

bot = telebot.TeleBot(TOKEN_KLIEN)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# 2. PENGATURAN USER (SINKRONISASI SUPABASE)
# ==========================================
WHITELIST_USER = []
ADMIN_USERS = []

def muat_data_user():
    print("⏳ Memuat daftar pengguna dari Supabase...")
    try:
        response = supabase.table("bot_users").select("*").execute()
        WHITELIST_USER.clear()
        ADMIN_USERS.clear()
        for baris in response.data:
            WHITELIST_USER.append(baris['username'])
            if baris['role'] == 'admin':
                ADMIN_USERS.append(baris['username'])
        print(f"✅ Berhasil memuat {len(WHITELIST_USER)} Klien dan {len(ADMIN_USERS)} Admin.")
    except Exception as e:
        print(f"❌ Gagal memuat pengguna: {e}")

# Tarik data saat bot pertama menyala
muat_data_user()

database_order = {} 
menunggu_list = {} 
menunggu_list_all = [] 
menunggu_del = []

# ==========================================
# 3. KELOLA PENGGUNA (/adduser, /addadmin, /deluser)
# ==========================================
@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.text and message.text.startswith('/adduser'))
def tambah_whitelist(message):
    username = message.from_user.username
    if not username:
        bot.reply_to(message, "⛔ Akun Anda tidak punya username!")
        return
    if username not in ADMIN_USERS:
        bot.reply_to(message, "⛔ Akses ditolak. Hanya Admin.")
        return

    pecahan = message.text.split()
    if len(pecahan) < 2:
        bot.reply_to(message, "⚠️ Format: `/adduser username_klien`", parse_mode='Markdown')
        return

    user_baru = pecahan[1].replace('@', '') 
    if user_baru in WHITELIST_USER:
        bot.reply_to(message, f"⚠️ Username **{user_baru}** sudah ada di whitelist.", parse_mode='Markdown')
    else:
        try:
            supabase.table("bot_users").insert({"username": user_baru, "role": "user"}).execute()
            WHITELIST_USER.append(user_baru)
            bot.reply_to(message, f"✅ Sukses! **{user_baru}** ditambahkan sebagai Klien.", parse_mode='Markdown')
        except Exception as e:
            bot.reply_to(message, f"❌ Gagal menyimpan ke Supabase: {e}")

@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.text and message.text.startswith('/addadmin'))
def tambah_admin(message):
    username = message.from_user.username
    if not username or username not in ADMIN_USERS: return
    pecahan = message.text.split()
    if len(pecahan) < 2: return
    
    admin_baru = pecahan[1].replace('@', '') 
    if admin_baru in ADMIN_USERS:
        bot.reply_to(message, f"⚠️ **{admin_baru}** sudah menjadi Admin.", parse_mode='Markdown')
        return

    try:
        if admin_baru in WHITELIST_USER:
            supabase.table("bot_users").update({"role": "admin"}).eq("username", admin_baru).execute()
        else:
            supabase.table("bot_users").insert({"username": admin_baru, "role": "admin"}).execute()
            WHITELIST_USER.append(admin_baru)
        ADMIN_USERS.append(admin_baru)
        bot.reply_to(message, f"👑 Sukses! **{admin_baru}** sekarang memiliki akses Admin.", parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Gagal: {e}")

# ==========================================
# 4. MENERIMA ORDER DARI BUYER (/add)
# ==========================================
# ⚠️ Perbaikan Bug: Memastikan tidak bentrok dengan /adduser
@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.text and message.text.split()[0] == '/add')
def terima_order_buyer(message):
    username = message.from_user.username
    if not username or username not in WHITELIST_USER: 
        bot.reply_to(message, "⛔ Anda belum terdaftar.")
        return

    teks = message.text
    id_buyer = message.chat.id
    pecahan = teks.split()
    
    if len(pecahan) < 3:
        bot.reply_to(message, "⚠️ Format salah. Gunakan: /add <kode> <jumlah>")
        return
        
    kode_order = pecahan[1]
    jumlah = pecahan[2]
    
    database_order[kode_order] = {'id_buyer': id_buyer, 'username': username, 'jumlah': jumlah}
    bot.reply_to(message, f"⏳ Order {kode_order} diterima. Meneruskan ke Agen...")
    bot.send_message(ID_GRUP, teks)

# ==========================================
# 5. FITUR HAPUS & CEK ANTREAN (/del, /list)
# ==========================================
@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.text and message.text.startswith('/del ') and len(message.text.split()) > 1)
def hapus_order(message):
    username = message.from_user.username
    if not username or username not in WHITELIST_USER: return
    kode = message.text.split()[1]
    if username not in ADMIN_USERS:
        if kode not in database_order or database_order[kode]['username'] != username:
            bot.reply_to(message, "⛔ Anda hanya bisa menghapus order Anda sendiri!")
            return
    bot.reply_to(message, f"⏳ Meminta Agen untuk menghapus {kode}...")
    if kode in database_order: del database_order[kode]
    menunggu_del.append(message.chat.id)
    bot.send_message(ID_GRUP, f"/del {kode}")

@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.text == '/list')
def cek_list_pribadi(message):
    username = message.from_user.username
    if not username or username not in WHITELIST_USER: return
    bot.reply_to(message, "⏳ Meminta status antrean dari Agen...")
    menunggu_list[message.chat.id] = username
    bot.send_message(ID_GRUP, "/list")

# ==========================================
# 6. REKAPAN SUMMARY (/myorder)
# ==========================================
@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.text == '/myorder')
def cek_myorder(message):
    username = message.from_user.username
    if not username or username not in WHITELIST_USER: return
    
    waiting_checks = sum(1 for data in database_order.values() if data['username'] == username)
    try:
        response = supabase.table("rekapan_order").select("jumlah").eq("username", username).execute()
        data_selesai = response.data
        completed_orders = len(data_selesai)
        target_hearts = sum(int(row['jumlah']) for row in data_selesai)
        
        teks_rekap = (
            f"📊 Order summary for {username}\n"
            f"Completed orders: {completed_orders}\n"
            f"Target hearts: {target_hearts}\n"
            f"Sent: {target_hearts}\n"
            f"Deleted orders: 0\n"
            f"Waiting checks: {waiting_checks}"
        )
        bot.reply_to(message, teks_rekap)
    except Exception as e:
        bot.reply_to(message, "❌ Gagal konek Database.")

# ==========================================
# 7. MEMBACA BALASAN DI GRUP AGEN
# ==========================================
@bot.message_handler(func=lambda message: message.chat.type in ['group', 'supergroup'])
def baca_grup(message):
    teks = message.text
    if not teks: return

    if "📋 Task List:" in teks:
        for chat_id, req_username in list(menunggu_list.items()):
            kode_milik_user = [k for k, v in database_order.items() if v['username'] == req_username]
            teks_balasan = f"📋 **Task List Anda:**\n"
            ada_isi = False
            for baris in teks.split('\n'):
                for kode in kode_milik_user:
                    if kode in baris:
                        teks_balasan += baris + "\n"
                        ada_isi = True
                        break
            if not ada_isi: teks_balasan += "(Kosong)"
            bot.send_message(chat_id, teks_balasan)
        menunggu_list.clear()
        return

    if "✅ Task deleted: ok" in teks:
        for chat_id in menunggu_del: bot.send_message(chat_id, teks)
        menunggu_del.clear()
        return
    
    for kode, data in list(database_order.items()):
        if kode in teks:
            id_buyer = data['id_buyer']
            if "(done" in teks.lower():
                bot.send_message(id_buyer, f"✅ Order Anda selesai!\nDetail: {teks}")
                try:
                    waktu_db = datetime.now().strftime("%d-%m-%Y %H:%M")
                    supabase.table("rekapan_order").insert({"waktu": waktu_db, "username": data['username'], "kode": kode, "jumlah": int(data['jumlah']), "status": "SUCCESS"}).execute()
                except Exception as e: pass
                del database_order[kode]
            elif "✅" in teks and "deleted" not in teks.lower():
                bot.send_message(id_buyer, f"⏳ Order {kode} sedang diproses oleh Agen.")

# ==========================================
# FITUR ADMIN: /exportcsv (DOWNLOAD REKAPAN CSV)
# ==========================================
@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.text == '/exportcsv')
def export_csv_admin(message):
    username = message.from_user.username
    if not username or username not in ADMIN_USERS:
        bot.reply_to(message, "⛔ Akses ditolak. Hanya Admin yang bisa mengunduh CSV.")
        return

    bot.reply_to(message, "⏳ Sedang menyiapkan file CSV dari database...")

    nama_file = f"rekapan_order_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    try:
        # 1. Ambil semua data dari Supabase
        response = supabase.table("rekapan_order").select("*").order("id", desc=True).execute()
        data = response.data

        if not data:
            bot.reply_to(message, "📭 Belum ada data transaksi di dalam database.")
            return

        # 2. Buat dan tulis file CSV secara lokal
        with open(nama_file, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            
            # Tulis Baris Judul Kolom (Header)
            writer.writerow(["ID", "Waktu", "Username", "Kode Order", "Jumlah", "Status"])
            
            # Tulis Data Baris per Baris
            for row in data:
                writer.writerow([
                    row.get('id'),
                    row.get('waktu'),
                    row.get('username'),
                    row.get('kode'),
                    row.get('jumlah'),
                    row.get('status')
                ])

        # 3. Kirim file CSV tersebut ke chat Telegram Admin
        with open(nama_file, 'rb') as file:
            bot.send_document(
                message.chat.id, 
                file, 
                caption="📊 **Berikut file CSV rekapan transaksi Anda.**", 
                parse_mode='Markdown'
            )

        # 4. Hapus file dari komputer/server setelah berhasil dikirim (agar bersih)
        os.remove(nama_file)

    except Exception as e:
        bot.reply_to(message, f"❌ Terjadi kesalahan saat membuat file CSV.")
        print(f"Error Export CSV: {e}")
        # Pastikan file terhapus jika sempat tercipta tapi error di tengah jalan
        if os.path.exists(nama_file):
            os.remove(nama_file)

# ==========================================
# 8. SISTEM POLLING OTOMATIS
# ==========================================
def polling_checker():
    while True:
        time.sleep(60) # Cek setiap 1 Menit
        for kode in list(database_order.keys()):
            bot.send_message(ID_GRUP, f"/check {kode}")
            time.sleep(3) # Anti limit

print("🚀 Bot Klien Master Siap Dijalankan!")
thread_polling = threading.Thread(target=polling_checker, daemon=True)
thread_polling.start()
bot.infinity_polling()