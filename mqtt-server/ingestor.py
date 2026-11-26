import json
import math
import os
import sqlite3
from pathlib import Path

import paho.mqtt.client as mqtt

BROKER = os.getenv("MQTT_HOST", "localhost")
PORT = int(os.getenv("MQTT_PORT", "1883"))
USERNAME = os.getenv("MQTT_USERNAME", "mqttuser")
PASSWORD = os.getenv("MQTT_PASSWORD")

DB_PATH = Path(__file__).resolve().parent.parent / "database" / "sauna.db"

SAUNA_BY_TOPIC = {
    "sauna/sensors": "koti",
    "sauna/ranta/sensors": "ranta",
}


def initialize_database():
    with sqlite3.connect(DB_PATH, timeout=5) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS measurements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                temperature REAL NOT NULL,
                humidity REAL NOT NULL,
                mode TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(measurements)")
        }
        if "sauna_id" not in columns:
            conn.execute("""
                ALTER TABLE measurements
                ADD COLUMN sauna_id TEXT NOT NULL DEFAULT 'koti'
                CHECK (sauna_id IN ('koti', 'ranta'))
            """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_measurements_sauna_id_id
            ON measurements (sauna_id, id)
        """)


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        client.subscribe([(topic, 1) for topic in SAUNA_BY_TOPIC])
        print("MQTT-yhteys muodostettu. Kuunnellaan molempia saunoja.")
    else:
        print(f"MQTT-yhteys epäonnistui: {reason_code}")


def on_message(client, userdata, msg):
    sauna_id = SAUNA_BY_TOPIC.get(msg.topic)
    if sauna_id is None:
        return

    try:
        data = json.loads(msg.payload.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Mittauksen pitää olla JSON-objekti")

        temperature = float(data["temperature"])
        humidity = float(data["humidity"])
        mode = data.get("mode", "unknown")

        if not math.isfinite(temperature) or not 0 <= humidity <= 100:
            raise ValueError("Virheellinen lämpötila tai kosteus")
        if not isinstance(mode, str):
            raise ValueError("Virheellinen mittaustila")

        with sqlite3.connect(DB_PATH, timeout=5) as conn:
            conn.execute("""
                INSERT INTO measurements
                    (sauna_id, temperature, humidity, mode)
                VALUES (?, ?, ?, ?)
            """, (sauna_id, temperature, humidity, mode))

        print(f"[{sauna_id}] Tallennettu: {temperature} °C / {humidity} %")

    except (KeyError, TypeError, ValueError, OverflowError, sqlite3.Error) as error:
        print(f"[{sauna_id}] Mittausta ei tallennettu: {error}")


def main():
    if not PASSWORD:
        raise SystemExit("MQTT_PASSWORD puuttuu. Lataa paikallinen .env.")

    initialize_database()
    print("Mittaustaulu valmis.")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(USERNAME, PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, PORT, 60)

    try:
        client.loop_forever()
    except KeyboardInterrupt:
        pass
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()