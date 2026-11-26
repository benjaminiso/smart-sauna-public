
import json
import sqlite3
from pathlib import Path
import paho.mqtt.client as mqtt

# MQTT configuration
BROKER = "localhost"
PORT = 1883
USERNAME = "mqttuser"
PASSWORD = "yourpassword"
TOPIC = "sauna/sensors"

# Database location
DB_PATH = Path(__file__).resolve().parent.parent / "database" / "sauna.db"

# Create database and table
with sqlite3.connect(DB_PATH) as conn:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            temperature REAL NOT NULL,
            humidity REAL NOT NULL,
            mode TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Connected to MQTT broker!")
        client.subscribe(TOPIC)
    else:
        print(f"Connection failed: {reason_code}")

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())

        temperature = float(data["temperature"])
        humidity = float(data["humidity"])
        mode = data.get("mode", "unknown")

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT INTO measurements
                (temperature, humidity, mode)
                VALUES (?, ?, ?)
            """, (temperature, humidity, mode))

        print(f"Saved: {temperature}°C, {humidity}%")

    except Exception as error:
        print(f"Error: {error}")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(USERNAME, PASSWORD)

client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, PORT, 60)

print("Smart Sauna Ingestor started!")

client.loop_forever()
