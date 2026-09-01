import telebot

# Masukkan Token Bot Agen Test Anda di sini
TOKEN_AGEN = '8895188926:AAGrhDqQm6UE3nXdPDbIbcXOTRAl56scsCA'
bot = telebot.TeleBot(TOKEN_AGEN)

# ==========================================
# DATABASE PURA-PURA UNTUK SIMULATOR
# ==========================================
database_agen_test = {}

# Statistik untuk fitur /myorder
statistik_agen = {
    'completed': 0,
    'target': 0,
    'sent': 0,
    'deleted': 0
}

@bot.message_handler(func=lambda message: message.chat.type in ['group', 'supergroup'])
def proses_perintah_grup(message):
    teks = message.text
    if not teks: return

    pecahan = teks.split()
    perintah = pecahan[0].lower()

    # ==========================================
    # 1. PERINTAH: /add <kode> <jumlah>
    # ==========================================
    if perintah == '/add' and len(pecahan) >= 3:
        kode = pecahan[1]
        jumlah = int(pecahan[2])
        
        # Simpan ke memori pura-pura dengan status processing
        database_agen_test[kode] = {'jumlah': jumlah, 'hitung_cek': 0, 'status': 'processing'}
        
        bot.reply_to(message, f"✅ {kode} : {jumlah}")
        print(f"[AGEN] Menerima order baru: {kode}")

    # ==========================================
    # 2. PERINTAH: /check <kode>
    # ==========================================
    elif perintah == '/check' and len(pecahan) >= 2:
        kode = pecahan[1]
        
        if kode in database_agen_test:
            data = database_agen_test[kode]
            jumlah = data['jumlah']
            
            # Jika status masih processing, tambah hitungan ceknya
            if data['status'] == 'processing':
                data['hitung_cek'] += 1
                
                # SIMULASI: Jika sudah di-cek 2 kali, order SELESAI
                if data['hitung_cek'] >= 2:
                    data['status'] = 'done' # Ubah status
                    
                    # Tambahkan ke statistik global
                    statistik_agen['completed'] += 1
                    statistik_agen['target'] += jumlah
                    statistik_agen['sent'] += jumlah
                    
                    bot.reply_to(message, f"{kode}(done {jumlah}/{jumlah})-vig")
                    print(f"[AGEN] Order {kode} selesai!")
                else:
                    bot.reply_to(message, f"{kode}(processing 5/{jumlah})-vig")
            
            # Jika sudah pernah done sebelumnya
            elif data['status'] == 'done':
                bot.reply_to(message, f"{kode}(done {jumlah}/{jumlah})-vig")
                
        else:
            bot.reply_to(message, f"{kode}(note_not_found 0/0)-vig")

    # ==========================================
    # 3. PERINTAH: /list 
    # ==========================================
    elif perintah == '/list':
        # Cari yang statusnya masih 'processing'
        task_aktif = {k: v for k, v in database_agen_test.items() if v['status'] == 'processing'}
        
        if not task_aktif:
            bot.reply_to(message, "📋 Task List:\n(kosong)")
            return
            
        teks_list = "📋 Task List:\n"
        for kode, data in task_aktif.items():
            jumlah = data['jumlah']
            teks_list += f"{kode}(processing 5/{jumlah})-vig\n"
            
        bot.reply_to(message, teks_list.strip())

    # ==========================================
    # 4. PERINTAH: /del <kode>
    # ==========================================
    elif perintah == '/del' and len(pecahan) >= 2:
        kode = pecahan[1]
        
        if kode in database_agen_test:
            # Jika yang dihapus masih processing, catat ke statistik deleted
            if database_agen_test[kode]['status'] == 'processing':
                statistik_agen['deleted'] += 1
                
            del database_agen_test[kode]
            print(f"[AGEN] Menghapus task: {kode}")
            
        bot.reply_to(message, "✅ Task deleted: ok")

    # ==========================================
    # 5. PERINTAH BARU: /myorder
    # ==========================================
    elif perintah == '/myorder':
        username = message.from_user.username if message.from_user.username else "vig"
        
        # Hitung berapa banyak yang masih berstatus 'processing'
        waiting_checks = sum(1 for v in database_agen_test.values() if v['status'] == 'processing')
        
        teks_summary = (
            f"📊 Order summary for {username}\n"
            f"Completed orders: {statistik_agen['completed']}\n"
            f"Target hearts: {statistik_agen['target']}\n"
            f"Sent: {statistik_agen['sent']}\n"
            f"Deleted orders: {statistik_agen['deleted']}\n"
            f"Waiting checks: {waiting_checks}"
        )
        
        bot.reply_to(message, teks_summary)


print("Bot Agen Test (Simulator V4 - Support Summary) Menyala...")
bot.infinity_polling()