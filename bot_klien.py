import telebot
import threading
import time
import csv
import os
import re
import sys
import urllib.request
from flask import Flask
from datetime import datetime, timedelta
from supabase import create_client, Client

# ==========================================
# KREDENSIAL LANGSUNG (LOKAL)
# ==========================================
TOKEN_KLIEN = '8804966042:AAEyjY6kc5ni9JWdBYIt_UA0qGqxGQG7rwI'
ID_GRUP = -1003904366569  

SUPABASE_URL = "https://eumvzdngwqrngkzcsbqt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV1bXZ6ZG5nd3FybmdremNzYnF0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODgxOTYxNjUsImV4cCI6MjEwMzc3MjE2NX0.acPVXigY8-jy_WUk49gRV2rnSZEMs5XvkRj_WDEpO88"

bot = telebot.TeleBot(TOKEN_KLIEN)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# PENGATURAN USER (DARI SUPABASE)
# ==========================================
GIST_URL = "https://gist.githubusercontent.com/anfula123-bit/82a63388078ce5345d15dd0380285a85/raw/bot_klien.py"
WHITELIST_USER = set()
ADMIN_USERS = set()

def normalisasi_user(u: str) -> str:
    if not u: return ""
    return u.replace('@', '').strip().lower()

def muat_data_user():
    print("⏳ Memuat daftar pengguna dari Supabase...")
    try:
        response = supabase.table("bot_users").select("*").execute()
        WHITELIST_USER.clear()
        ADMIN_USERS.clear()
        for baris in response.data:
            uname = normalisasi_user(baris.get('username', ''))
            if uname:
                WHITELIST_USER.add(uname)
                if baris.get('role') == 'admin':
                    ADMIN_USERS.add(uname)
        print(f"✅ Berhasil memuat {len(WHITELIST_USER)} User dan {len(ADMIN_USERS)} Admin.")
    except Exception as e:
        print(f"❌ Gagal memuat pengguna: {e}")

muat_data_user()

menunggu_list = {}      # Format: {chat_id: username_bersih}
menunggu_list_all = []  # Format: [chat_id]
menunggu_del = []       # Format: [chat_id]
menunggu_quota = []     # Format: [chat_id]
menunggu_lang = []      # Format: [chat_id]

KNOWN_CHAT_IDS = set()

def periksa_chat_id(username: str, chat_id: int):
    if chat_id not in KNOWN_CHAT_IDS:
        try:
            supabase.table("bot_users").update({"chat_id": str(chat_id)}).ilike("username", username).execute()
            KNOWN_CHAT_IDS.add(chat_id)
        except:
            pass

def check_and_reset_quota(username: str):
    """Mengecek sisa kuota dan melakukan reset otomatis jika sudah berganti hari (lewat jam 07:00)."""
    try:
        res = supabase.table("bot_users").select("max_quota, used_quota, last_reset").ilike("username", username).execute()
        if not res.data:
            return 0, 0
        
        user_data = res.data[0]
        max_quota = user_data.get('max_quota') or 0
        used_quota = user_data.get('used_quota') or 0
        last_reset = user_data.get('last_reset') or ""

        now = datetime.now()
        if now.hour >= 7:
            current_day = now.strftime("%Y-%m-%d")
        else:
            current_day = (now - timedelta(days=1)).strftime("%Y-%m-%d")

        if last_reset != current_day:
            used_quota = 0
            supabase.table("bot_users").update({"used_quota": 0, "last_reset": current_day}).ilike("username", username).execute()
            
        return max_quota, used_quota
    except Exception as e:
        print(f"Error checking quota for {username}: {e}")
        return 0, 0

def bersihkan_kode(kode: str) -> str:
    """Menghapus strip dan spasi serta lowercase untuk pembandingan."""
    return str(kode).replace("-", "").replace(" ", "").strip().lower()

def validasi_format_kode(kode: str) -> bool:
    """Mendukung format XXXXXXXXXXXX (12 karakter) atau XXXX-XXXX-XXXX."""
    pola = r'^(?:[A-Za-z0-9]{12}|[A-Za-z0-9]{4}-[A-Za-z0-9]{4}-[A-Za-z0-9]{4})$'
    return bool(re.match(pola, kode.strip()))

# ==========================================
# MENU BANTUAN (/help)
# ==========================================
@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.text in ['/help', '/start'])
def tampilkan_bantuan(message):
    username = normalisasi_user(message.from_user.username)
    if not username or username not in WHITELIST_USER:
        bot.reply_to(message, "⛔ Anda belum terdaftar di sistem. Hubungi Admin.")
        return
        
    periksa_chat_id(username, message.chat.id)
    
    bantuan = "🤖 **Menu Bantuan Forward Bot**\n\n"
    bantuan += "🔹 **Perintah Klien:**\n"
    bantuan += "• `/add <KODE> <JUMLAH>` - Memproses pesanan baru\n"
    bantuan += "• `/del <KODE>` - Membatalkan pesanan (jika masih pending)\n"
    bantuan += "• `/list` - Melihat daftar antrean aktif\n"
    bantuan += "• `/checkquota` - Melihat sisa kuota harian Anda\n"
    bantuan += "• `/myorder` - Melihat 20 riwayat order terakhir\n"
    bantuan += "• `/exportcsv [MM/YYYY]` - Mengunduh laporan rekap data order Anda\n"
    
    if username in ADMIN_USERS:
        bantuan += "\n👑 **Perintah Khusus Admin:**\n"
        bantuan += "• `/adduser <username>` - Mendaftarkan klien baru\n"
        bantuan += "• `/addadmin <username>` - Menjadikan klien sebagai Admin\n"
        bantuan += "• `/deluser <username>` - Menghapus akses klien\n"
        bantuan += "• `/demoteadmin <username>` - Mencabut akses admin dari seseorang\n"
        bantuan += "• `/listuser` - Melihat daftar semua klien terdaftar\n"
        bantuan += "• `/listall` - Mengecek semua pending order di agen pusat\n"
        bantuan += "• `/setmaxquota <user> <jumlah>` - Mengatur batas kuota klien\n"
        bantuan += "• `/checkquota <user>` - Melihat pemakaian kuota klien secara spesifik\n"
        bantuan += "• `/resetquota <user>` - Mereset pemakaian kuota klien kembali ke 0\n"
        bantuan += "• `/setstatus <kode> <STATUS>` - Ubah status manual (SUCCESS, INVALID, DELETED)\n"
        bantuan += "• `/exportcsv [MM/YYYY] [user]` - Unduh CSV seluruh user / user spesifik\n"
        bantuan += "• `/broadcast <pesan>` - Kirim pengumuman massal ke semua klien\n"
        bantuan += "• `/fwd <pesan>` - Meneruskan pesan/perintah mentah ke agen (bypass Supabase)\n"
        bantuan += "• `/update` - Download pembaruan kode OTA dari GitHub secara otomatis\n"
        bantuan += "• `/setlang <vn/en>` - Mengubah bahasa balasan bot agen pusat\n"

    bot.reply_to(message, bantuan, parse_mode='Markdown')

# ==========================================
# FITUR ADMIN: /adduser, /addadmin, /listuser, /update
# ==========================================
@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.text == '/update')
def ota_update(message):
    username = normalisasi_user(message.from_user.username)
    if not username or username not in ADMIN_USERS: return
    periksa_chat_id(username, message.chat.id)
    
    bot.reply_to(message, "🔄 Mengunduh pembaruan terbaru dari GitHub...")
    try:
        req = urllib.request.Request(GIST_URL)
        with urllib.request.urlopen(req) as response:
            kode_baru = response.read().decode('utf-8')
        
        if "import telebot" not in kode_baru:
            bot.reply_to(message, "❌ Pembaruan gagal: File yang diunduh tidak valid.")
            return
            
        with open(__file__, 'w', encoding='utf-8') as f:
            f.write(kode_baru)
            
        bot.reply_to(message, "✅ Pembaruan berhasil diunduh! Memulai ulang (restart) bot...\nBot akan aktif kembali dalam beberapa detik.")
        time.sleep(2)
        os.execv(sys.executable, ['python'] + sys.argv)
    except Exception as e:
        bot.reply_to(message, f"❌ Gagal memperbarui bot: {e}")

@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.text and message.text.startswith('/adduser'))
def tambah_whitelist(message):
    username = normalisasi_user(message.from_user.username)
    if not username or username not in ADMIN_USERS: return
    pecahan = message.text.split()
    if len(pecahan) < 2:
        bot.reply_to(message, "⚠️ Format: `/adduser username_klien`", parse_mode='Markdown')
        return
    user_baru = normalisasi_user(pecahan[1])
    try:
        supabase.table("bot_users").insert({"username": user_baru, "role": "user"}).execute()
        WHITELIST_USER.add(user_baru)
        bot.reply_to(message, f"✅ Sukses! **{user_baru}** ditambahkan sebagai Klien.", parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Gagal: {e}")

@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.text and message.text.startswith('/addadmin'))
def tambah_admin(message):
    username = normalisasi_user(message.from_user.username)
    if not username or username not in ADMIN_USERS: return
    pecahan = message.text.split()
    if len(pecahan) < 2: return
    admin_baru = normalisasi_user(pecahan[1])
    try:
        if admin_baru in WHITELIST_USER:
            supabase.table("bot_users").update({"role": "admin"}).ilike("username", admin_baru).execute()
        else:
            supabase.table("bot_users").insert({"username": admin_baru, "role": "admin"}).execute()
            WHITELIST_USER.add(admin_baru)
        ADMIN_USERS.add(admin_baru)
        bot.reply_to(message, f"👑 Sukses! **{admin_baru}** sekarang memiliki akses Admin.", parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Gagal: {e}")

@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.text and message.text.startswith('/setmaxquota'))
def set_max_quota(message):
    username = normalisasi_user(message.from_user.username)
    if not username or username not in ADMIN_USERS: return
    pecahan = message.text.split()
    if len(pecahan) < 3:
        bot.reply_to(message, "⚠️ Format: `/setmaxquota username jumlah`", parse_mode='Markdown')
        return
    
    target_user = normalisasi_user(pecahan[1])
    try:
        jumlah = int(pecahan[2])
    except ValueError:
        bot.reply_to(message, "⚠️ Jumlah harus berupa angka.")
        return

    try:
        res = supabase.table("bot_users").select("username").ilike("username", target_user).execute()
        if not res.data:
            bot.reply_to(message, f"❌ User **{target_user}** tidak ditemukan.", parse_mode='Markdown')
            return
        
        supabase.table("bot_users").update({"max_quota": jumlah}).ilike("username", target_user).execute()
        bot.reply_to(message, f"✅ Sukses! Max quota untuk **{target_user}** diatur menjadi {jumlah}.", parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Gagal mengatur quota: {e}")

@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.text and message.text.startswith('/deluser'))
def hapus_whitelist(message):
    username = normalisasi_user(message.from_user.username)
    if not username or username not in ADMIN_USERS: return
    pecahan = message.text.split()
    if len(pecahan) < 2: return
    target_user = normalisasi_user(pecahan[1])
    try:
        supabase.table("bot_users").delete().ilike("username", target_user).execute()
        WHITELIST_USER.discard(target_user)
        ADMIN_USERS.discard(target_user)
        bot.reply_to(message, f"✅ Sukses! **{target_user}** telah dihapus dari sistem.", parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Gagal: {e}")

@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.text and message.text.startswith('/demoteadmin'))
def cabut_admin(message):
    username = normalisasi_user(message.from_user.username)
    if not username or username not in ADMIN_USERS: return
    pecahan = message.text.split()
    if len(pecahan) < 2: return
    target_user = normalisasi_user(pecahan[1])
    try:
        supabase.table("bot_users").update({"role": "user"}).ilike("username", target_user).execute()
        ADMIN_USERS.discard(target_user)
        bot.reply_to(message, f"✅ Sukses! **{target_user}** kini kembali menjadi User biasa.", parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Gagal: {e}")

@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.text and message.text.startswith('/resetquota'))
def manual_reset_quota(message):
    username = normalisasi_user(message.from_user.username)
    if not username or username not in ADMIN_USERS: return
    pecahan = message.text.split()
    if len(pecahan) < 2: return
    target_user = normalisasi_user(pecahan[1])
    try:
        supabase.table("bot_users").update({"used_quota": 0}).ilike("username", target_user).execute()
        bot.reply_to(message, f"✅ Sukses! Kuota **{target_user}** telah di-reset menjadi 0.", parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Gagal mereset kuota: {e}")

@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.text and message.text.startswith('/setstatus'))
def set_status_manual(message):
    username = normalisasi_user(message.from_user.username)
    if not username or username not in ADMIN_USERS: return
    pecahan = message.text.split()
    if len(pecahan) < 3:
        bot.reply_to(message, "⚠️ Format: `/setstatus KODE STATUS`\nContoh: `/setstatus ABC SUCCESS`", parse_mode='Markdown')
        return
    
    kode = bersihkan_kode(pecahan[1])
    status_baru = pecahan[2].upper()
    
    if status_baru not in ["SUCCESS", "PENDING", "INVALID", "DELETED", "DUPLICATE"]:
        bot.reply_to(message, "⚠️ Status tidak valid. Gunakan: SUCCESS, PENDING, INVALID, DELETED, DUPLICATE.")
        return

    try:
        res = supabase.table("rekapan_order").select("*").ilike("kode", f"%{kode}%").execute()
        if not res.data:
            bot.reply_to(message, f"❌ Order dengan kode `{pecahan[1]}` tidak ditemukan.", parse_mode='Markdown')
            return
            
        target_order = res.data[0]
        supabase.table("rekapan_order").update({"status": status_baru}).eq("id", target_order['id']).execute()
        
        # Jika status diubah ke INVALID/DELETED, refund kuota
        if status_baru in ["INVALID", "DELETED", "DUPLICATE"]:
            uname = target_order.get('username')
            jumlah = int(target_order.get('jumlah', 0))
            if uname and jumlah > 0:
                _, current_used = check_and_reset_quota(uname)
                new_used = max(0, current_used - jumlah)
                supabase.table("bot_users").update({"used_quota": new_used}).ilike("username", uname).execute()
                
        bot.reply_to(message, f"✅ Sukses mengubah status `{pecahan[1]}` menjadi **{status_baru}**.", parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Gagal: {e}")

@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.text and message.text.startswith('/broadcast'))
def broadcast_pesan(message):
    username = normalisasi_user(message.from_user.username)
    if not username or username not in ADMIN_USERS: return
    
    pesan_broadcast = message.text.replace(message.text.split()[0], '', 1).strip()
    if not pesan_broadcast:
        bot.reply_to(message, "⚠️ Harap masukkan pesan yang ingin di-broadcast.\nContoh: `/broadcast Halo semua!`", parse_mode='Markdown')
        return

    try:
        res = supabase.table("bot_users").select("chat_id").neq("chat_id", "").execute()
        sukses = 0
        for row in res.data or []:
            chat_id = row.get("chat_id")
            if chat_id:
                try:
                    bot.send_message(chat_id, f"📢 **PENGUMUMAN**\n\n{pesan_broadcast}", parse_mode='Markdown')
                    sukses += 1
                except:
                    pass
        bot.reply_to(message, f"✅ Broadcast selesai! Terkirim ke {sukses} pengguna.")
    except Exception as e:
        bot.reply_to(message, f"❌ Gagal broadcast: {e}")

@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.text and message.text.startswith('/fwd '))
def forward_langsung(message):
    username = normalisasi_user(message.from_user.username)
    if not username or username not in ADMIN_USERS: return
    
    pesan_raw = message.text.replace(message.text.split()[0], '', 1).strip()
    if not pesan_raw:
        bot.reply_to(message, "⚠️ Format salah. Gunakan: `/fwd <pesan>`\nContoh: `/fwd /add XXXXXXX 10`", parse_mode='Markdown')
        return
        
    bot.send_message(ID_GRUP, pesan_raw)
    bot.reply_to(message, f"✅ Pesan mentah berhasil diteruskan ke Agen:\n`{pesan_raw}`", parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.text == '/listuser')
def daftar_pengguna(message):
    username = normalisasi_user(message.from_user.username)
    if not username or username not in ADMIN_USERS: return

    try:
        response = supabase.table("bot_users").select("*").order("role", desc=False).execute()
        data = response.data

        if not data:
            bot.reply_to(message, "📭 Belum ada data pengguna di Supabase.")
            return

        teks_list = "👥 **Daftar Pengguna Terdaftar:**\n\n"
        for idx, user in enumerate(data, 1):
            role_icon = "👑 Admin" if user.get("role") == "admin" else "👤 User"
            teks_list += f"{idx}. @{user.get('username')} — {role_icon}\n"

        bot.reply_to(message, teks_list, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Gagal mengambil daftar pengguna: {e}")

# ==========================================
# MENERIMA ORDER DARI BUYER (/add)
# ==========================================
@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.text and message.text.split()[0] == '/add')
def terima_order_buyer(message):
    username = normalisasi_user(message.from_user.username)
    if not username or username not in WHITELIST_USER: return
    teks_asli = message.text.strip()
    pecahan = teks_asli.split()
    
    if len(pecahan) < 3 or not pecahan[2].isdigit():
        bot.reply_to(message, "⚠️ Format salah. Gunakan: `/add <kode> <jumlah>`\nContoh:\n`/add AAAA-AAAA-AAAA 10`\n`/add AAAAAAAAAAAA 10`", parse_mode='Markdown')
        return

    kode_order = pecahan[1].strip()
    jumlah = int(pecahan[2])

    if not validasi_format_kode(kode_order):
        bot.reply_to(message, "⚠️ Format kode tidak valid! Gunakan format `XXXXXXXXXXXX` (12 karakter) atau `XXXX-XXXX-XXXX`.", parse_mode='Markdown')
        return

    periksa_chat_id(username, message.chat.id)

    # Cek dan potong kuota
    max_quota, used_quota = check_and_reset_quota(username)
    if used_quota + jumlah > max_quota:
        bot.reply_to(message, f"⛔ **Quota tidak mencukupi!**\nLimit Harian: {max_quota}\nTerpakai: {used_quota}\nSisa: {max_quota - used_quota}\n\n_Reset setiap pukul 07:00_", parse_mode='Markdown')
        return

    waktu_skrg = datetime.now().strftime("%d-%m-%Y %H:%M")

    try:
        supabase.table("bot_users").update({"used_quota": used_quota + jumlah}).ilike("username", username).execute()
        
        supabase.table("rekapan_order").insert({
            "waktu": waktu_skrg,
            "username": username,
            "kode": kode_order,
            "jumlah": jumlah,
            "status": "PENDING"
        }).execute()
    except Exception as e:
        print(f"❌ Gagal simpan order ke Supabase: {e}")
        bot.reply_to(message, "❌ Gagal menyimpan ke database.")
        return

    bot.reply_to(message, f"⏳ Order `{kode_order}` diterima. Meneruskan ke Agen...", parse_mode='Markdown')
    bot.send_message(ID_GRUP, teks_asli)

# ==========================================
# FITUR HAPUS, LIST, QUOTA & BAHASA
# ==========================================
@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.text and message.text.startswith('/del ') and len(message.text.split()) > 1)
def hapus_order(message):
    username = normalisasi_user(message.from_user.username)
    if not username or username not in WHITELIST_USER: return
    
    kode_input = message.text.split()[1].strip()
    clean_k = bersihkan_kode(kode_input)

    try:
        res = supabase.table("rekapan_order").select("*").in_("status", ["PENDING", "INVALID"]).execute()
        semua_antrean = res.data or []
        
        target_order = None
        for row in semua_antrean:
            if bersihkan_kode(row['kode']) == clean_k:
                target_order = row
                break

        if not target_order:
            bot.reply_to(message, f"⛔ Kode `{kode_input}` tidak ditemukan di antrean aktif/invalid Anda!", parse_mode='Markdown')
            return

        pemilik_asli = normalisasi_user(target_order.get('username', ''))
        if pemilik_asli != username and username not in ADMIN_USERS:
            bot.reply_to(message, "⛔ Anda DILARANG menghapus order milik orang lain!")
            return

        supabase.table("rekapan_order").update({"status": "DELETED"}).eq("id", target_order['id']).execute()
        
    except Exception as e:
        print(f"Error pengecekan del: {e}")
        bot.reply_to(message, "❌ Terjadi kesalahan saat memeriksa database.")
        return

    bot.reply_to(message, f"⏳ Meminta Agen untuk menghapus `{target_order['kode']}`...", parse_mode='Markdown')
    menunggu_del.append(message.chat.id)
    bot.send_message(ID_GRUP, f"/del {target_order['kode']}")

@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.text and message.text.startswith('/list'))
def cek_list_pribadi(message):
    teks = message.text.strip().split()
    cmd = teks[0].lower()
    
    # Karena startswith('/list'), kita harus filter jika itu /listall atau /listuser
    if cmd not in ['/list', '/listall']:
        return

    username = normalisasi_user(message.from_user.username)
    if not username or username not in WHITELIST_USER: return
    
    halaman = teks[1] if len(teks) > 1 and teks[1].isdigit() else ""
    cmd_agent = f"{cmd} {halaman}".strip()

    if cmd == '/listall':
        if username not in ADMIN_USERS: return
        bot.reply_to(message, f"⏳ Meminta SEMUA antrean dari Agen{f' (Hal {halaman})' if halaman else ''}...")
        menunggu_list_all.append(message.chat.id)
        bot.send_message(ID_GRUP, cmd_agent.replace('/listall', '/list'))
    else:
        bot.reply_to(message, f"⏳ Meminta status antrean Anda dari Agen{f' (Hal {halaman})' if halaman else ''}...")
        menunggu_list[message.chat.id] = username
        bot.send_message(ID_GRUP, cmd_agent)

@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.text and message.text.strip().startswith('/checkquota'))
def minta_cek_kuota(message):
    username = normalisasi_user(message.from_user.username)
    if not username or username not in WHITELIST_USER: return
    
    teks = message.text.strip().split()
    
    if username in ADMIN_USERS:
        if len(teks) > 1:
            target_user = normalisasi_user(teks[1])
            max_q, used_q = check_and_reset_quota(target_user)
            bot.reply_to(message, f"📊 **Kuota {target_user}:**\nLimit: {max_q}\nTerpakai: {used_q}\nSisa: {max_q - used_q}", parse_mode='Markdown')
        else:
            # Jika admin yang checkquota tanpa argumen, forward ke agen
            menunggu_quota.append(message.chat.id)
            bot.send_message(ID_GRUP, "/checkquota")
    else:
        # Jika user yang checkquota, tampilkan quota dari database
        max_quota, used_quota = check_and_reset_quota(username)
        sisa = max_quota - used_quota
        bot.reply_to(message, f"📊 **Informasi Kuota Anda:**\n\nLimit Harian: {max_quota}\nTerpakai: {used_quota}\nSisa Kuota: {sisa}\n\n_Reset setiap pukul 07:00_", parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.text and message.text.startswith('/setlang'))
def ganti_bahasa(message):
    username = normalisasi_user(message.from_user.username)
    if not username or username not in ADMIN_USERS: return
    teks = message.text.strip()
    pecahan = teks.split()
    if len(pecahan) < 2:
        bot.reply_to(message, "⚠️ Format: `/setlang en` atau `/setlang vie`", parse_mode='Markdown')
        return
    menunggu_lang.append(message.chat.id)
    bot.send_message(ID_GRUP, teks)

# ==========================================
# REKAPAN & EXPORT CSV (/myorder, /exportcsv)
# ==========================================
@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.text == '/myorder')
def cek_myorder(message):
    username = normalisasi_user(message.from_user.username)
    if not username or username not in WHITELIST_USER: return
    try:
        response = supabase.table("rekapan_order").select("*").ilike("username", username).execute()
        data_user = response.data or []
        data_selesai = [row for row in data_user if row.get('status') == 'SUCCESS']
        data_deleted = [row for row in data_user if row.get('status') == 'DELETED']
        data_pending = [row for row in data_user if row.get('status') == 'PENDING']

        completed_orders = len(data_selesai)
        target_hearts = sum(int(row.get('jumlah', 0)) for row in data_selesai)
        deleted_orders = len(data_deleted)
        waiting_checks = len(data_pending)

        teks_rekap = (
            f"📊 Order summary for {username}\n"
            f"Completed orders: {completed_orders}\n"
            f"Target hearts: {target_hearts}\n"
            f"Sent: {target_hearts}\n"
            f"Deleted orders: {deleted_orders}\n"
            f"Waiting checks: {waiting_checks}"
        )
        bot.reply_to(message, teks_rekap)
    except Exception as e:
        bot.reply_to(message, "❌ Gagal mengambil summary.")

@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.text and message.text.startswith('/exportcsv'))
def export_csv(message):
    username = normalisasi_user(message.from_user.username)
    if not username or username not in WHITELIST_USER: return
    periksa_chat_id(username, message.chat.id)
    
    teks = message.text.strip().split()
    filter_bulan = ""
    filter_user = ""
    
    # Parsing argumen
    for arg in teks[1:]:
        if re.match(r'^\d{2}/\d{4}$', arg):
            filter_bulan = arg
        else:
            filter_user = normalisasi_user(arg)
            
    # Klien biasa hanya bisa mengambil datanya sendiri
    if username not in ADMIN_USERS:
        if filter_user and filter_user != username:
            bot.reply_to(message, "⛔ Anda hanya dapat mengekspor data transaksi milik Anda sendiri.")
            return
        filter_user = username

    nama_file = f"rekapan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    try:
        query = supabase.table("rekapan_order").select("*")
        
        if filter_bulan:
            bulan, tahun = filter_bulan.split('/')
            like_pattern = f"%-{bulan}-{tahun} %"
            query = query.ilike("waktu", like_pattern)
            
        if filter_user:
            query = query.ilike("username", filter_user)
            
        response = query.order("id", desc=True).execute()
        data = response.data
        
        if not data:
            msg = "📭 Belum ada data transaksi"
            if filter_bulan: msg += f" untuk bulan {filter_bulan}"
            if filter_user and username in ADMIN_USERS: msg += f" dari user @{filter_user}"
            bot.reply_to(message, msg + ".")
            return
            
        with open(nama_file, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Code", "Target", "AlreadySer", "Time Create", "Extra", "Username", "Status"])
            for row in data:
                kode_val = row.get('kode', '')
                target_val = int(row.get('jumlah') or 0)
                already_ser_val = int(row.get('already_served') or 0)
                time_create_val = str(row.get('waktu', '')).replace("-", "/")
                
                status_val = row.get('status', '')
                extra_val = already_ser_val - target_val if status_val == 'SUCCESS' else 0
                
                writer.writerow([
                    kode_val,
                    target_val,
                    already_ser_val,
                    time_create_val,
                    extra_val,
                    row.get('username', ''),
                    status_val
                ])
                
        caption = f"📊 **Rekapan CSV Transaksi**"
        if filter_bulan: caption += f"\nBulan: {filter_bulan}"
        if filter_user and username in ADMIN_USERS: caption += f"\nUser: @{filter_user}"
        
        with open(nama_file, 'rb') as f:
            bot.send_document(message.chat.id, f, caption=caption.strip(), parse_mode='Markdown')
        os.remove(nama_file)
    except Exception as e:
        bot.reply_to(message, f"❌ Gagal membuat CSV: {e}")
        if os.path.exists(nama_file): os.remove(nama_file)

# ==========================================
# MEMBACA BALASAN GRUP AGEN
# ==========================================
@bot.message_handler(func=lambda message: message.chat.type in ['group', 'supergroup'], content_types=['text', 'photo'])
def baca_grup(message):
    teks = message.text or message.caption
    if not teks: return

    print("=" * 40)
    print(f"[LOG MASUK DARI GRUP {message.chat.id}]")
    print(f"Isi Pesan:\n{teks}")
    print("=" * 40)

    teks_lower = teks.lower()
    teks_clean = bersihkan_kode(teks)

    # 0. Menangkap notif (done X/Y) untuk menyimpan already_served
    matches = list(re.finditer(r'([A-Za-z0-9-]+)\s*\(done\s*(\d+)/\d+\)', teks, re.IGNORECASE))
    if matches:
        try:
            res = supabase.table("rekapan_order").select("*").in_("status", ["PENDING", "INVALID"]).execute()
            pending_orders = res.data or []
            for match_done in matches:
                kode_selesai = bersihkan_kode(match_done.group(1))
                already_served = int(match_done.group(2))
                for row in pending_orders:
                    row_kode_clean = bersihkan_kode(row['kode'])
                    if row_kode_clean in kode_selesai or kode_selesai in row_kode_clean:
                        supabase.table("rekapan_order").update({
                            "status": "SUCCESS",
                            "already_served": already_served
                        }).eq("id", row['id']).execute()
                        break
        except Exception as e:
            print(f"Update done notification error: {e}")

    # 1. Balasan Duplicate Code
    if "duplicate code" in teks_lower:
        try:
            res = supabase.table("rekapan_order").select("*").eq("status", "PENDING").execute()
            for row in res.data or []:
                if bersihkan_kode(row['kode']) in teks_clean:
                    supabase.table("rekapan_order").update({"status": "DUPLICATE"}).eq("id", row['id']).execute()
                    
                    # Refund quota
                    uname = row.get('username')
                    jumlah = int(row.get('jumlah', 0))
                    if uname and jumlah > 0:
                        _, current_used = check_and_reset_quota(uname)
                        new_used = max(0, current_used - jumlah)
                        supabase.table("bot_users").update({"used_quota": new_used}).ilike("username", uname).execute()
                        
                        # Kirim notif ke private chat user
                        try:
                            user_res = supabase.table("bot_users").select("chat_id").ilike("username", uname).execute()
                            if user_res.data:
                                chat_id = user_res.data[0].get("chat_id")
                                if chat_id:
                                    bot.send_message(
                                        chat_id, 
                                        f"❌ **Pesanan Ditolak (DUPLIKAT)!**\nKode `{row['kode']}` terdeteksi sudah pernah diproses oleh agen.\n\nKuota sebesar {jumlah} telah dikembalikan ke akun Anda.", 
                                        parse_mode='Markdown'
                                    )
                        except Exception as e_notif:
                            print(f"Gagal kirim notif duplicate ke user: {e_notif}")
                    break
        except Exception as e:
            print(f"Update duplicate error: {e}")
        return

    # 2. Balasan /setlang
    if any(k in teks_lower for k in ["language", "ngôn ngữ", "set language"]):
        for chat_id in menunggu_lang:
            bot.send_message(chat_id, teks)
        menunggu_lang.clear()
        return

    # 3. Balasan /checkquota
    if "quota" in teks_lower and ("used" in teks_lower or "today" in teks_lower):
        for chat_id in menunggu_quota:
            bot.send_message(chat_id, teks)
        menunggu_quota.clear()
        return

    # 4. Balasan /list (Jika Kosong)
    if any(k in teks_lower for k in ["no running tasks", "không có task", "no task"]):
        for chat_id in list(menunggu_list.keys()):
            bot.send_message(chat_id, "📋 Tidak ada task yang aktif saat ini.")
        for chat_id in menunggu_list_all:
            bot.send_message(chat_id, teks)
        menunggu_list.clear()
        menunggu_list_all.clear()
        return

    # 5. Balasan /list (Task List / Ada Isi)
    is_list_response = False
    if "page:" in teks_lower:
        is_list_response = True
    else:
        for baris in teks.split('\n'):
            if re.search(r'\([a-z_]+\s+\d+/\d+\)', baris, re.IGNORECASE):
                is_list_response = True
                break

    if is_list_response:
        for baris in teks.split('\n'):
            baris_clean = baris.strip()
            if not baris_clean or "page:" in baris_clean.lower():
                continue

            baris_kode_clean = bersihkan_kode(baris_clean)

            if "invalid" in baris_clean.lower() or "code_invalid" in baris_clean.lower() or "note_deleted" in baris_clean.lower() or "not_found" in baris_clean.lower() or "error" in baris_clean.lower():
                try:
                    res = supabase.table("rekapan_order").select("*").eq("status", "PENDING").execute()
                    for row in res.data or []:
                        if bersihkan_kode(row['kode']) in baris_kode_clean:
                            supabase.table("rekapan_order").update({"status": "INVALID"}).eq("id", row['id']).execute()
                            
                            # Refund quota
                            uname = row.get('username')
                            jumlah = int(row.get('jumlah', 0))
                            if uname and jumlah > 0:
                                _, current_used = check_and_reset_quota(uname)
                                new_used = max(0, current_used - jumlah)
                                supabase.table("bot_users").update({"used_quota": new_used}).ilike("username", uname).execute()
                except Exception as e:
                    print(f"Supabase update invalid/error list: {e}")

        for chat_id, req_username in list(menunggu_list.items()):
            try:
                res = supabase.table("rekapan_order").select("kode").ilike("username", req_username).in_("status", ["PENDING", "INVALID"]).execute()
                kode_milik_user = [row['kode'] for row in res.data or []]
            except Exception as e:
                print(f"Gagal ambil order user dari Supabase: {e}")
                kode_milik_user = []

            baris_terfilter = []
            for baris in teks.split('\n'):
                baris_clean = baris.strip()
                if not baris_clean:
                    continue
                if "page:" in baris_clean.lower():
                    baris_terfilter.append(baris_clean)
                    continue
                    
                for kode_user in kode_milik_user:
                    if bersihkan_kode(kode_user) in bersihkan_kode(baris_clean):
                        baris_terfilter.append(baris_clean)
                        break

            if baris_terfilter:
                teks_balasan = f"📋 **Task List Anda ({req_username}):**\n" + "\n".join(baris_terfilter)
            else:
                teks_balasan = f"📋 **Task List Anda ({req_username}):**\n(Kosong / Tidak ada antrean aktif)"
                
            bot.send_message(chat_id, teks_balasan)
            
        if menunggu_list_all:
            try:
                res_all = supabase.table("rekapan_order").select("kode, username").in_("status", ["PENDING", "INVALID"]).execute()
                map_kode_user = {bersihkan_kode(row['kode']): row['username'] for row in res_all.data or []}
            except Exception as e:
                print(f"Gagal mapping user untuk listall: {e}")
                map_kode_user = {}

            teks_all_lines = []
            for baris in teks.split('\n'):
                baris_clean = baris.strip()
                if not baris_clean:
                    continue
                if "page:" in baris_clean.lower():
                    teks_all_lines.append(baris_clean)
                    continue
                
                found_user = None
                for kode_bersih, uname in map_kode_user.items():
                    if kode_bersih in bersihkan_kode(baris_clean):
                        found_user = uname
                        break
                
                if found_user:
                    teks_all_lines.append(f"{baris_clean} | 👤 @{found_user}")
                else:
                    teks_all_lines.append(f"{baris_clean} | 👤 ?")
                    
            teks_all_reconstructed = "📋 **Semua Task Aktif:**\n" + "\n".join(teks_all_lines)
            
            for chat_id in menunggu_list_all:
                bot.send_message(chat_id, teks_all_reconstructed)
            
        menunggu_list.clear()
        menunggu_list_all.clear()
        return

    # 6. Balasan /del
    if any(k in teks_lower for k in ["task deleted", "not found to delete", "already removed", "error deleting"]):
        for chat_id in menunggu_del: 
            bot.send_message(chat_id, teks)
        menunggu_del.clear()
        return

# ==========================================
# SISTEM POLLING CHECKER (Dari Supabase PENDING)
# ==========================================
def polling_checker():
    while True:
        time.sleep(1800)
        try:
            res = supabase.table("rekapan_order").select("kode").eq("status", "PENDING").execute()
            for row in res.data or []:
                bot.send_message(ID_GRUP, f"/check {row['kode']}")
                time.sleep(3)
        except Exception as e:
            print(f"Error polling Supabase: {e}")

# ==========================================
# SERVER HTTP DUMMY (UNTUK RENDER)
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot berjalan dengan baik!"

def run_bot():
    print("🚀 Bot sedang berjalan...")
    bot.infinity_polling(skip_pending=True)

if __name__ == '__main__':
    print("🚀 Menginisialisasi sistem bot...")
    # Jalankan thread polling checker
    thread_polling = threading.Thread(target=polling_checker, daemon=True)
    thread_polling.start()
    
    # Jalankan thread bot telegram
    thread_bot = threading.Thread(target=run_bot, daemon=True)
    thread_bot.start()
    
    # Jalankan Flask app untuk binding port (Syarat Render.com)
    port = int(os.environ.get("PORT", 8080))
    print(f"🌍 Menjalankan server HTTP di port {port}...")
    app.run(host="0.0.0.0", port=port)