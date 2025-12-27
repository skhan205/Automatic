import os
import time
import threading
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
import requests
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, BadPassword

app = Flask(__name__)

# Global variables
BOT_STATUS = "stopped"
CURRENT_SETTINGS = {}
LOGS = []
SESSION_FILE = "session.json"
STOP_FLAG = False

def add_log(message):
    timestamp = datetime.now().strftime('%H:%M:%S')
    log = f"[{timestamp}] {message}"
    LOGS.append(log)
    if len(LOGS) > 100:
        LOGS.pop(0)
    print(log)

def instagram_bot_worker(username, password, group_ids, messages, delay_sec):
    """Main Instagram bot logic"""
    global STOP_FLAG
    
    add_log("🤖 Instagram Bot Starting...")
    
    # Instagram client setup
    cl = Client()
    
    # Try to load saved session
    try:
        if os.path.exists(SESSION_FILE):
            cl.load_settings(SESSION_FILE)
            cl.login(username, password)
            add_log("✅ Session loaded successfully")
        else:
            cl.login(username, password)
            cl.dump_settings(SESSION_FILE)
            add_log("✅ New login successful")
    except BadPassword as e:
        add_log(f"❌ Login failed: {e}")
        return
    except Exception as e:
        add_log(f"⚠️ Login error: {e}")
        return
    
    add_log(f"✅ Logged in as: {username}")
    
    message_count = 0
    cycle_count = 0
    
    # Main bot loop - 24/7
    while not STOP_FLAG:
        try:
            cycle_count += 1
            add_log(f"🔄 Cycle {cycle_count} started")
            
            for group_id in group_ids:
                if STOP_FLAG:
                    break
                    
                for message in messages:
                    if STOP_FLAG:
                        break
                    
                    try:
                        # Send message to group
                        cl.direct_send(message, thread_ids=[group_id])
                        message_count += 1
                        add_log(f"✅ [{message_count}] Sent to {group_id}: {message[:50]}...")
                        
                        # Delay between messages
                        time.sleep(delay_sec)
                        
                    except LoginRequired:
                        add_log("⚠️ Session expired, re-logging in...")
                        try:
                            cl.login(username, password)
                            cl.direct_send(message, thread_ids=[group_id])
                            add_log("✅ Re-login successful")
                        except Exception as e:
                            add_log(f"❌ Re-login failed: {e}")
                            STOP_FLAG = True
                            break
                    except Exception as e:
                        add_log(f"⚠️ Send error: {e}")
                        time.sleep(10)
            
            if STOP_FLAG:
                break
                
            add_log(f"⏸️ Waiting before next cycle...")
            time.sleep(30)  # 30 seconds between cycles
            
        except Exception as e:
            add_log(f"❌ Loop error: {e}")
            time.sleep(30)
    
    add_log(f"🛑 Bot stopped. Total messages: {message_count}")
    global BOT_STATUS
    BOT_STATUS = "stopped"

# ===================== FLASK ROUTES =====================

@app.route('/')
def dashboard():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🤖 Android Bot Controller</title>
        <style>
            body { font-family: Arial; background: #0f172a; color: white; padding: 20px; }
            .container { max-width: 600px; margin: auto; }
            .card { background: #1e293b; padding: 20px; border-radius: 10px; margin: 15px 0; }
            input, textarea, button { 
                width: 100%; padding: 12px; margin: 8px 0; 
                border-radius: 5px; border: 1px solid #334155;
                background: #0f172a; color: white;
            }
            button { background: #3b82f6; border: none; font-weight: bold; }
            .start-btn { background: #10b981; }
            .stop-btn { background: #ef4444; }
            .logs { background: #000; padding: 15px; border-radius: 5px; 
                    height: 300px; overflow-y: auto; font-family: monospace; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📱 Android Bot Controller</h1>
            
            <div class="card">
                <h3>⚙️ Bot Settings</h3>
                <form id="botForm">
                    <input type="text" name="username" placeholder="Instagram Username" required>
                    <input type="password" name="password" placeholder="Instagram Password" required>
                    <textarea name="group_ids" placeholder="Group IDs (comma separated)" required></textarea>
                    <textarea name="messages" placeholder="Messages (one per line)" rows="4" required></textarea>
                    <input type="number" name="delay" placeholder="Delay between messages (seconds)" value="5">
                    
                    <button type="button" onclick="startBot()" class="start-btn">▶ START BOT</button>
                    <button type="button" onclick="stopBot()" class="stop-btn">⏹ STOP BOT</button>
                </form>
            </div>
            
            <div class="card">
                <h3>📋 Live Logs</h3>
                <div class="logs" id="logBox">Loading logs...</div>
            </div>
        </div>
        
        <script>
            async function startBot() {
                const form = document.getElementById('botForm');
                const formData = new FormData(form);
                
                const response = await fetch('/start', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                alert(result.message);
                location.reload();
            }
            
            async function stopBot() {
                const response = await fetch('/stop', {method: 'POST'});
                const result = await response.json();
                alert(result.message);
                location.reload();
            }
            
            async function loadLogs() {
                const response = await fetch('/logs');
                const data = await response.json();
                document.getElementById('logBox').innerHTML = data.logs.join('<br>');
            }
            
            setInterval(loadLogs, 2000);
            loadLogs();
        </script>
    </body>
    </html>
    ''', status=BOT_STATUS)

@app.route('/start', methods=['POST'])
def start_bot():
    global BOT_STATUS, STOP_FLAG, CURRENT_SETTINGS
    
    if BOT_STATUS == "running":
        return jsonify({"success": False, "message": "❌ Bot is already running!"})
    
    # Get form data
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    group_ids = [g.strip() for g in request.form.get('group_ids', '').split(',') if g.strip()]
    messages = [m.strip() for m in request.form.get('messages', '').split('\n') if m.strip()]
    delay = int(request.form.get('delay', 5))
    
    if not username or not password or not group_ids or not messages:
        return jsonify({"success": False, "message": "❌ All fields are required!"})
    
    # Save settings
    CURRENT_SETTINGS = {
        'username': username,
        'group_ids': group_ids,
        'message_count': len(messages),
        'delay': delay
    }
    
    # Reset stop flag
    STOP_FLAG = False
    
    # Start bot in background thread
    bot_thread = threading.Thread(
        target=instagram_bot_worker,
        args=(username, password, group_ids, messages, delay),
        daemon=True
    )
    bot_thread.start()
    
    BOT_STATUS = "running"
    add_log(f"🚀 Bot started for user: {username}")
    
    return jsonify({
        "success": True, 
        "message": "✅ Bot started successfully!",
        "settings": CURRENT_SETTINGS
    })

@app.route('/stop', methods=['POST'])
def stop_bot():
    global STOP_FLAG, BOT_STATUS
    
    STOP_FLAG = True
    BOT_STATUS = "stopped"
    add_log("🛑 Bot stop requested")
    
    return jsonify({
        "success": True, 
        "message": "✅ Bot stopped successfully!"
    })

@app.route('/logs')
def get_logs():
    return jsonify({"logs": LOGS[-50:]})

@app.route('/status')
def get_status():
    return jsonify({
        "status": BOT_STATUS,
        "settings": CURRENT_SETTINGS if BOT_STATUS == "running" else {},
        "log_count": len(LOGS)
    })

@app.route('/ping')
def ping():
    return jsonify({"status": "alive", "bot_status": BOT_STATUS})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    
    add_log("=" * 50)
    add_log("🤖 INSTAGRAM BOT STARTING")
    add_log("=" * 50)
    add_log(f"🌐 Server running on port: {port}")
    add_log("=" * 50)
    
    app.run(host="0.0.0.0", port=port, debug=False)
