rver.channels[0];
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
