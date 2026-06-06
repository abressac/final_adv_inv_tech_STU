from flask import Flask, request, jsonify, render_template
import sqlite3
import datetime
import os
import shutil

app = Flask(__name__)

system_status = "CLOSED"
monitoring_status = "STOPPED"
capture_interval = 3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
SAVE_DIR = os.path.join(DATA_DIR, "saves")
DB_NAME = os.path.join(DATA_DIR, "data.db")
LOG_FILE = os.path.join(DATA_DIR, "log.txt")

def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(SAVE_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            temperature REAL,
            humidity REAL,
            action TEXT
        )
    ''')
    conn.commit()
    conn.close()

def log_to_file(temp, hum, action=""):
    with open(LOG_FILE, "a") as f:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if action:
            f.write(f"{now} - Action: {action}\n")
        else:
            f.write(f"{now} - Temp: {temp}C, Hum: {hum}%\n")

def save_to_db(temp, hum, action=""):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO sensor_data (timestamp, temperature, humidity, action) VALUES (?, ?, ?, ?)", (now, temp, hum, action))
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/update', methods=['GET'])
def update_data():
    global capture_interval
    
    temp = request.args.get('temp')
    hum = request.args.get('hum')

    if system_status == "OPENED" and monitoring_status == "STARTED":
        if temp is not None and hum is not None:
            save_to_db(temp, hum, "")
            log_to_file(temp, hum, "")

    return f"INTERVAL={capture_interval}\n"

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({
        "system_status": system_status,
        "monitoring_status": monitoring_status,
        "interval": capture_interval
    })

@app.route('/api/parameters', methods=['POST'])
def set_parameters():
    global capture_interval
    data = request.get_json()
    interval = data.get('interval')
    
    if interval is not None and int(interval) >= 1:
        capture_interval = int(interval)
        save_to_db(None, None, f"SET INTERVAL={capture_interval}")
        log_to_file(None, None, f"SET INTERVAL={capture_interval}")
        
    return jsonify({"status": "success", "interval": capture_interval})

@app.route('/api/control', methods=['POST'])
def control_system():
    global system_status, monitoring_status
    data = request.get_json()
    command = data.get('command')

    if command == "OPEN":
        system_status = "OPENED"
        save_to_db(None, None, "OPEN")
        log_to_file(None, None, "OPEN")
    elif command == "CLOSE":
        system_status = "CLOSED"
        monitoring_status = "STOPPED"
        save_to_db(None, None, "CLOSE")
        log_to_file(None, None, "CLOSE")
    elif command == "START" and system_status == "OPENED":
        monitoring_status = "STARTED"
        save_to_db(None, None, "START")
        log_to_file(None, None, "START")
    elif command == "STOP":
        monitoring_status = "STOPPED"
        save_to_db(None, None, "STOP")
        log_to_file(None, None, "STOP")

    return jsonify({"status": "success"})

@app.route('/api/clear', methods=['POST'])
def clear_data():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sensor_data")
    conn.commit()
    conn.close()
    
    with open(LOG_FILE, "w") as f:
        pass
        
    return jsonify({"status": "success"})

@app.route('/api/save_log', methods=['POST'])
def save_log():
    os.makedirs(SAVE_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(SAVE_DIR, f"log_save_{timestamp}.txt")
    
    if os.path.exists(LOG_FILE):
        shutil.copy2(LOG_FILE, save_path)
    else:
        with open(save_path, "w") as f:
            pass
            
    return jsonify({"status": "success", "file": save_path})

@app.route('/api/load_log', methods=['POST'])
def load_log():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded"})
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "Empty file name"})

    content = file.read().decode('utf-8')

    with open(LOG_FILE, "w") as f:
        f.write(content)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sensor_data")

    lines = content.strip().split('\n')
    for line in lines:
        if not line.strip():
            continue
        try:
            parts = line.split(' - ', 1)
            if len(parts) != 2:
                continue
                
            timestamp = parts[0].strip()
            data_part = parts[1].strip()

            if data_part.startswith("Action:"):
                action = data_part.replace("Action:", "").strip()
                cursor.execute("INSERT INTO sensor_data (timestamp, temperature, humidity, action) VALUES (?, NULL, NULL, ?)", (timestamp, action))
            else:
                data_elements = data_part.split(', ')
                temp_str = data_elements[0].replace('Temp:', '').replace('C', '').strip()
                hum_str = data_elements[1].replace('Hum:', '').replace('%', '').strip()
                cursor.execute("INSERT INTO sensor_data (timestamp, temperature, humidity, action) VALUES (?, ?, ?, ?)", (timestamp, float(temp_str), float(hum_str), ""))
        except Exception:
            pass

    conn.commit()
    conn.close()

    return jsonify({"status": "success"})

@app.route('/api/data', methods=['GET'])
def get_data():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sensor_data ORDER BY id DESC LIMIT 15")
    rows = cursor.fetchall()
    conn.close()

    data = []
    for row in rows:
        data.append({
            "id": row[0],
            "timestamp": row[1],
            "temperature": row[2] if row[2] is not None else "",
            "humidity": row[3] if row[3] is not None else "",
            "action": row[4] if row[4] is not None else ""
        })
    
    return jsonify(data)

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)