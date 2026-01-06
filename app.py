import os
from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# --- KONFIGURASI APP & DATABASE ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'discord_pro_master_key'

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat_pro.db' # Database file lokal
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# --- DATABASE MODELS (STRUKTUR DATA) ---
class Server(db.Model):
    id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    icon = db.Column(db.String(10), nullable=False)
    channels = db.relationship('Channel', backref='server', lazy=True)

class Channel(db.Model):
    id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    server_id = db.Column(db.String(50), db.ForeignKey('server.id'), nullable=False)
    messages = db.relationship('Message', backref='channel', lazy=True)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.String(50), nullable=False) # Redudansi untuk query cepat
    channel_id = db.Column(db.String(50), db.ForeignKey('channel.id'), nullable=False)
    user = db.Column(db.String(50), nullable=False)
    text = db.Column(db.Text, nullable=False) # Menyimpan Ciphertext (Terenkripsi)
    time = db.Column(db.String(20), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# --- INIT DATABASE (Jalankan sekali otomatis) ---
with app.app_context():
    db.create_all()
    # Buat server default jika kosong agar UI tidak rusak saat pertama kali load
    if not Server.query.first():
        s1 = Server(id='s1', name='Web Developer ID', icon='WD')
        c1 = Channel(id='c1', name='umum', server_id='s1')
        db.session.add(s1)
        db.session.add(c1)
        db.session.commit()

# --- FRONTEND CODE (TIDAK DIUBAH SECARA VISUAL) ---
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Discord Pro - E2EE Persistent</title>
    
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/crypto-js/4.1.1/crypto-js.min.js"></script>
    
    <style>
        /* CSS ASLI ANDA - DIPERTAHANKAN UTUH */
        :root {
            --bg-server: #1e1f22;
            --bg-channels: #2b2d31;
            --bg-chat: #313338;
            --bg-hover: #35373c;
            --bg-active: #3f4147;
            --bg-user: #232428;
            --text-normal: #dbdee1;
            --text-muted: #949ba4;
            --accent: #5865f2;
            --accent-hover: #4752c4;
            --server-width: 72px;
            --channel-width: 240px;
            --member-width: 260px;
            --header-height: 48px;
            --transition-speed: 0.3s;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
        
        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-chat);
            color: var(--text-normal);
            height: 100dvh;
            overflow: hidden;
            display: flex;
            touch-action: none;
        }

        .left-sidebars {
            display: flex; height: 100%; z-index: 1001;
            transition: transform var(--transition-speed) cubic-bezier(0.4, 0, 0.2, 1);
            will-change: transform; flex-shrink: 0;
        }

        .server-sidebar {
            width: var(--server-width); background-color: var(--bg-server);
            display: flex; flex-direction: column; align-items: center; padding-top: 12px; gap: 8px;
        }

        .channel-sidebar {
            width: var(--channel-width); background-color: var(--bg-channels);
            display: flex; flex-direction: column;
        }

        .chat-main {
            flex-grow: 1; display: flex; flex-direction: column; min-width: 0;
            background-color: var(--bg-chat); position: relative; z-index: 10;
        }

        .member-sidebar {
            width: var(--member-width); background-color: var(--bg-channels);
            display: flex; flex-direction: column; flex-shrink: 0; z-index: 1001;
            transition: transform var(--transition-speed) cubic-bezier(0.4, 0, 0.2, 1);
        }

        .header {
            height: var(--header-height); padding: 0 16px; display: flex;
            align-items: center; border-bottom: 1px solid rgba(0,0,0,0.2); font-weight: 700;
        }

        .server-icon-wrap { position: relative; cursor: pointer; }
        .server-icon {
            width: 48px; height: 48px; border-radius: 50%; background-color: var(--bg-chat);
            display: flex; align-items: center; justify-content: center; transition: 0.2s;
            font-weight: 600; color: var(--text-normal); overflow: hidden;
        }
        .server-icon-wrap.active .server-icon { border-radius: 16px; background: var(--accent); color: white; }
        .server-icon-wrap:hover .server-icon { border-radius: 16px; background: var(--accent); color: white; }
        
        .add-btn { color: #23a559 !important; }
        .add-btn:hover { background: #23a559 !important; color: white !important; }

        .pill {
            position: absolute; left: -4px; top: 50%; width: 4px; height: 8px;
            background: white; border-radius: 0 4px 4px 0; transform: translateY(-50%);
            opacity: 0; transition: 0.2s;
        }
        .server-icon-wrap.active .pill { opacity: 1; height: 40px; }

        .channel-item {
            margin: 2px 8px; padding: 8px; border-radius: 4px; cursor: pointer;
            display: flex; align-items: center; gap: 12px; color: var(--text-muted); font-size: 15px;
        }
        .channel-item:hover { background: var(--bg-hover); color: var(--text-normal); }
        .channel-item.active { background: var(--bg-active); color: white; }

        .message-list { flex-grow: 1; overflow-y: auto; padding: 16px 0; }
        .message { display: flex; padding: 8px 16px; gap: 16px; }
        .avatar { width: 40px; height: 40px; border-radius: 50%; background: var(--accent); flex-shrink: 0; display: flex; align-items: center; justify-content: center; font-weight: bold; color: white; }

        .input-area { padding: 0 16px 20px; }
        .input-box { background: var(--bg-hover); border-radius: 8px; padding: 0 16px; height: 44px; display: flex; align-items: center; gap: 12px; }
        .input-box input { background: transparent; border: none; outline: none; color: white; flex: 1; }

        .modal-overlay {
            position: fixed; inset: 0; background: rgba(0,0,0,0.8);
            display: none; align-items: center; justify-content: center; z-index: 2000;
        }
        .modal {
            background: var(--bg-chat); width: 400px; border-radius: 8px;
            padding: 24px; box-shadow: 0 8px 24px rgba(0,0,0,0.5);
        }
        .modal h2 { margin-bottom: 16px; font-size: 20px; }
        .modal input {
            width: 100%; padding: 10px; background: var(--bg-server);
            border: none; border-radius: 4px; color: white; margin-bottom: 20px; outline: none;
        }
        .modal-btns { display: flex; justify-content: flex-end; gap: 12px; }
        .btn { padding: 10px 20px; border-radius: 4px; cursor: pointer; border: none; font-weight: 600; }
        .btn-primary { background: var(--accent); color: white; }
        .btn-ghost { background: transparent; color: white; }

        #overlay {
            position: fixed; inset: 0; background: rgba(0,0,0,0.7);
            z-index: 1000; opacity: 0; pointer-events: none; transition: opacity 0.3s;
        }

        @media (max-width: 1024px) {
            .left-sidebars { position: fixed; transform: translateX(-100%); }
            .member-sidebar { position: fixed; right: 0; transform: translateX(100%); }
            body.left-open .left-sidebars { transform: translateX(0); }
            body.right-open .member-sidebar { transform: translateX(0); }
            body.left-open #overlay, body.right-open #overlay { opacity: 1; pointer-events: auto; }
        }

        .custom-scroll::-webkit-scrollbar { width: 4px; }
        .custom-scroll::-webkit-scrollbar-thumb { background: #1a1b1e; border-radius: 4px; }
        .custom-scroll { overflow-y: auto; }
        .truncate { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        
        /* Loading Overlay */
        #loading-screen {
            position: fixed; inset: 0; background: var(--bg-chat); z-index: 9999;
            display: flex; justify-content: center; align-items: center; flex-direction: column;
            color: white; font-weight: bold; transition: opacity 0.5s;
        }
    </style>
</head>
<body id="app-body">
    <div id="loading-screen">
        <i class="fas fa-circle-notch fa-spin fa-2x" style="margin-bottom: 20px; color: var(--accent);"></i>
        <div>Menghubungkan ke Secure Server...</div>
    </div>

    <div id="overlay" onclick="closeAll()"></div>

    <div class="modal-overlay" id="modal-server">
        <div class="modal">
            <h2>Buat Server Baru</h2>
            <input type="text" id="new-server-name" placeholder="Nama Server">
            <input type="text" id="new-server-icon" placeholder="Inisial (Contoh: WD)" maxlength="2">
            <div class="modal-btns">
                <button class="btn btn-ghost" onclick="closeModal('modal-server')">Batal</button>
                <button class="btn btn-primary" onclick="createServer()">Buat</button>
            </div>
        </div>
    </div>

    <div class="modal-overlay" id="modal-channel">
        <div class="modal">
            <h2>Buat Channel Baru</h2>
            <input type="text" id="new-channel-name" placeholder="Nama Channel (contoh: diskusi)">
            <div class="modal-btns">
                <button class="btn btn-ghost" onclick="closeModal('modal-channel')">Batal</button>
                <button class="btn btn-primary" onclick="createChannel()">Buat</button>
            </div>
        </div>
    </div>

    <div class="left-sidebars" id="left-nav">
        <nav class="server-sidebar custom-scroll">
            <div id="server-list-ui"></div>
            <div class="server-icon-wrap" onclick="openModal('modal-server')">
                <div class="server-icon add-btn"><i class="fas fa-plus"></i></div>
            </div>
        </nav>
        <aside class="channel-sidebar">
            <header class="header truncate" style="justify-content: space-between;">
                <span id="active-server-name">Memuat...</span>
                <i class="fas fa-plus cursor-pointer" onclick="openModal('modal-channel')" style="font-size:12px; color:var(--text-muted);"></i>
            </header>
            <div class="custom-scroll" style="flex:1;" id="channel-list-ui"></div>
            <div style="background: var(--bg-user); height: 52px; display: flex; align-items:center; padding: 0 10px; gap:8px;">
                <div class="avatar" id="my-avatar" style="width:32px; height:32px; font-size:12px;">ME</div>
                <div style="flex:1; overflow:hidden;">
                    <div id="my-username" style="font-size:13px; font-weight:600;" class="truncate">User_Aktif</div>
                    <div style="font-size:10px; color:var(--text-muted);"><i class="fas fa-lock"></i> Secured</div>
                </div>
            </div>
        </aside>
    </div>

    <main class="chat-main">
        <header class="header" style="justify-content: space-between;">
            <div style="display:flex; align-items:center; gap:12px; min-width:0;">
                <i class="fas fa-bars mobile-only" onclick="toggleLeft(true)" style="padding: 5px; cursor:pointer;"></i>
                <i class="fas fa-hashtag text-muted"></i>
                <span style="font-weight:700;" id="active-channel-name">umum</span>
            </div>
            <i class="fas fa-users text-muted mobile-only" onclick="toggleRight(true)" style="padding: 5px; cursor:pointer;"></i>
        </header>
        <div class="message-list custom-scroll" id="msg-container"></div>
        <div class="input-area">
            <div class="input-box">
                <i class="fas fa-plus-circle text-muted"></i>
                <input type="text" id="chat-input" placeholder="Kirim pesan terenkripsi...">
            </div>
        </div>
    </main>

    <aside class="member-sidebar" id="right-nav">
        <header class="header">Anggota</header>
        <div class="custom-scroll" style="padding: 10px;" id="member-list-ui"></div>
    </aside>

    <script>
        const SECRET_KEY = "discord-pro-global-encryption-key";
        const socket = io();
        const myUsername = "User_" + Math.floor(Math.random() * 1000);
        document.getElementById('my-username').textContent = myUsername;
        document.getElementById('my-avatar').textContent = myUsername.substring(5);

        // State awal kosong, akan diisi oleh server via SocketIO
        let appState = {
            activeServerId: null,
            activeChannelId: null,
            servers: {}
        };

        const body = document.getElementById('app-body');
        function toggleLeft(open) { body.classList.toggle('left-open', open); body.classList.remove('right-open'); }
        function toggleRight(open) { body.classList.toggle('right-open', open); body.classList.remove('left-open'); }
        function closeAll() { body.classList.remove('left-open', 'right-open'); }
        
        function openModal(id) { document.getElementById(id).style.display = 'flex'; }
        function closeModal(id) { document.getElementById(id).style.display = 'none'; }

        // --- CORE UI UPDATE ---
        function updateUI() {
            if (!appState.activeServerId || !appState.servers[appState.activeServerId]) return;

            const server = appState.servers[appState.activeServerId];
            // Jika channel aktif tidak valid, pilih yang pertama
            const channel = server.channels.find(c => c.id === appState.activeChannelId) || server.channels[0];
            if(channel) appState.activeChannelId = channel.id;

            // Render Server List
            document.getElementById('server-list-ui').innerHTML = Object.entries(appState.servers).map(([id, s]) => `
                <div class="server-icon-wrap ${id === appState.activeServerId ? 'active' : ''}" onclick="selectServer('${id}')">
                    <div class="pill"></div>
                    <div class="server-icon">${s.icon}</div>
                </div>
            `).join('');

            document.getElementById('active-server-name').textContent = server.name;
            
            // Render Channel List
            document.getElementById('channel-list-ui').innerHTML = server.channels.map(ch => `
                <div class="channel-item ${ch.id === appState.activeChannelId ? 'active' : ''}" onclick="selectChannel('${ch.id}')">
                    <i class="fas fa-hashtag"></i>
                    <span class="truncate">${ch.name}</span>
                </div>
            `).join('');

            document.getElementById('active-channel-name').textContent = channel ? channel.name : '-';
            
            // Render Messages (Decryption happens here implicitly if text is encrypted, but here we assume raw text from state)
            // Note: Server sends encrypted text, client needs to decrypt for display
            const msgs = (server.messages && server.messages[appState.activeChannelId]) ? server.messages[appState.activeChannelId] : [];
            
            document.getElementById('msg-container').innerHTML = msgs.map(m => {
                // Dekripsi "on-the-fly" saat render
                let displayText = m.text;
                try {
                    const bytes = CryptoJS.AES.decrypt(m.text, SECRET_KEY);
                    const originalText = bytes.toString(CryptoJS.enc.Utf8);
                    if(originalText) displayText = originalText;
                } catch(e) { /* Biarkan ciphertext jika gagal */ }

                return `
                <div class="message">
                    <div class="avatar">${m.user[0]}</div>
                    <div>
                        <div style="font-weight:600;">${m.user} <span style="font-weight:400; font-size:11px; color:var(--text-muted); margin-left:8px;">${m.time}</span></div>
                        <p style="margin-top:2px;">${displayText}</p>
                    </div>
                </div>
            `}).join('');

            // Render Members (Static for now, can be dynamic later)
            document.getElementById('member-list-ui').innerHTML = server.members.map(m => `
                <div class="channel-item">
                    <div class="avatar" style="width:24px; height:24px; font-size:10px;">${m[0]}</div>
                    <span class="truncate">${m}</span>
                </div>
            `).join('');
            
            const sc = document.getElementById('msg-container');
            sc.scrollTop = sc.scrollHeight;
        }

        // --- SOCKET EVENTS UNTUK DATA LOADING & SYNC ---
        
        // 1. Menerima Data Awal dari Database saat Connect
        socket.on('init_state', (data) => {
            console.log("Database Loaded:", data);
            appState.servers = data;
            
            // Set default aktif jika belum ada
            const serverIds = Object.keys(data);
            if (serverIds.length > 0) {
                if (!appState.activeServerId) {
                    appState.activeServerId = serverIds[0];
                    appState.activeChannelId = data[serverIds[0]].channels[0].id;
                }
            }
            
            updateUI();
            
            // Hilangkan loading screen
            const loader = document.getElementById('loading-screen');
            if(loader) { loader.style.opacity = 0; setTimeout(() => loader.remove(), 500); }
        });

        // --- GLOBAL SYNC (Tambah Server/Channel) ---
        function createServer() {
            const name = document.getElementById('new-server-name').value;
            const icon = document.getElementById('new-server-icon').value || name[0];
            if(!name) return;
            const id = 's' + Date.now();
            socket.emit('add_server', { id, name, icon });
            closeModal('modal-server');
        }

        function createChannel() {
            const name = document.getElementById('new-channel-name').value;
            if(!name) return;
            const id = 'c' + Date.now();
            socket.emit('add_channel', { serverId: appState.activeServerId, id, name });
            closeModal('modal-channel');
        }

        socket.on('server_added', (data) => {
            // Tambahkan ke state lokal
            appState.servers[data.id] = {
                name: data.name, icon: data.icon,
                channels: [{ id: data.initialChannelId, name: 'umum' }],
                members: ['Admin_Bot'],
                messages: { [data.initialChannelId]: [] }
            };
            updateUI();
        });

        socket.on('channel_added', (data) => {
            if(appState.servers[data.serverId]) {
                appState.servers[data.serverId].channels.push({ id: data.id, name: data.name });
                // Init message array
                if(!appState.servers[data.serverId].messages) appState.servers[data.serverId].messages = {};
                appState.servers[data.serverId].messages[data.id] = [];
                updateUI();
            }
        });

        // --- MESSAGING ---
        document.getElementById('chat-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && e.target.value.trim()) {
                const cipherText = CryptoJS.AES.encrypt(e.target.value, SECRET_KEY).toString();
                socket.emit('global_msg', {
                    user: myUsername, text: cipherText,
                    serverId: appState.activeServerId, channelId: appState.activeChannelId
                });
                e.target.value = '';
            }
        });

        socket.on('broadcast_msg', (data) => {
            const s = appState.servers[data.serverId];
            if (s) {
                if (!s.messages) s.messages = {};
                if (!s.messages[data.channelId]) s.messages[data.channelId] = [];
                
                // Masukkan data terenkripsi langsung ke state
                s.messages[data.channelId].push(data);
                
                if (data.serverId === appState.activeServerId && data.channelId === appState.activeChannelId) updateUI();
            }
        });

        window.selectServer = (id) => { 
            appState.activeServerId = id; 
            // Ambil channel pertama sebagai default saat pindah server
            if(appState.servers[id].channels.length > 0) {
                appState.activeChannelId = appState.servers[id].channels[0].id;
            }
            updateUI(); 
        };
        window.selectChannel = (id) => { appState.activeChannelId = id; updateUI(); };

    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_CONTENT)

# --- BACKEND LOGIC ---

@socketio.on('connect')
def handle_connect():
    """
    Saat user connect/refresh, ambil SEMUA data dari database
    dan susun menjadi format JSON yang dimengerti frontend (appState).
    """
    servers = Server.query.all()
    state_data = {}

    for s in servers:
        # Siapkan struktur server
        server_obj = {
            'name': s.name,
            'icon': s.icon,
            'channels': [],
            'members': ['Admin_Bot', 'User_Lain'], # Placeholder member
            'messages': {}
        }

        # Ambil Channels
        channels = Channel.query.filter_by(server_id=s.id).all()
        for c in channels:
            server_obj['channels'].append({'id': c.id, 'name': c.name})
            
            # Ambil Messages per Channel
            msgs = Message.query.filter_by(channel_id=c.id).order_by(Message.timestamp).all()
            msg_list = []
            for m in msgs:
                msg_list.append({
                    'user': m.user,
                    'text': m.text, # Masih terenkripsi
                    'time': m.time,
                    'serverId': m.server_id,
                    'channelId': m.channel_id
                })
            server_obj['messages'][c.id] = msg_list
        
        state_data[s.id] = server_obj

    # Kirim state penuh ke user yang baru connect
    emit('init_state', state_data)

@socketio.on('global_msg')
def handle_msg(data):
    # 1. Simpan ke Database
    msg = Message(
        server_id=data['serverId'],
        channel_id=data['channelId'],
        user=data['user'],
        text=data['text'],
        time=datetime.now().strftime("%H:%M")
    )
    db.session.add(msg)
    db.session.commit()

    # 2. Tambahkan waktu ke payload sebelum broadcast
    data['time'] = msg.time
    emit('broadcast_msg', data, broadcast=True)

@socketio.on('add_server')
def handle_add_server(data):
    # Simpan Server Baru
    new_server = Server(id=data['id'], name=data['name'], icon=data['icon'])
    # Otomatis buat channel 'umum'
    init_channel_id = 'c_' + data['id'] + '_init'
    new_channel = Channel(id=init_channel_id, name='umum', server_id=data['id'])
    
    db.session.add(new_server)
    db.session.add(new_channel)
    db.session.commit()
    
    data['initialChannelId'] = init_channel_id
    emit('server_added', data, broadcast=True)

@socketio.on('add_channel')
def handle_add_channel(data):
    new_channel = Channel(id=data['id'], name=data['name'], server_id=data['serverId'])
    db.session.add(new_channel)
    db.session.commit()
    
    emit('channel_added', data, broadcast=True)

if __name__ == '__main__':
    # Gunakan port dari environment variable yang disediakan Render
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
