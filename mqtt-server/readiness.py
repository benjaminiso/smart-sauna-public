
import json
import sqlite3
import math
from pathlib import Path
import paho.mqtt.client as mqtt

# MQTT configuration
BROKER = "localhost"
PORT = 1883
USERNAME = "mqttuser"
PASSWORD = "YOUR_PASSWORD

SENSOR_TOPIC = "sauna/sensors"
STATUS_TOPIC = "sauna/status"

# Database location
DB_PATH = (
    Path(__file__).resolve().parent.parent
    / "database" / "sauna.db"
)

# Allowed differences from preferred conditions
TEMP_TOLERANCE = 2
HUMIDITY_TOLERANCE = 5


def get_active_profile():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        return conn.execute(
            "SELECT * FROM profiles WHERE active = 1"
        ).fetchone()


def on_connect(client, userdata, flags,
               reason_code, properties):

    if reason_code == 0:
        print("Connected to MQTT broker!")
        client.subscribe(SENSOR_TOPIC)
    else:
        print("Connection failed:", reason_code)


def on_message(client, userdata, msg):

    try:
        data = json.loads(msg.payload.decode())

        temperature = float(data["temperature"])
        humidity = float(data["humidity"])

        if not math.isfinite(temperature):
            raise ValueError("Invalid temperature")

        if not math.isfinite(humidity) or not 0 <= humidity <= 100:
            raise ValueError("Invalid humidity")

        profile = get_active_profile()

        if profile is None:
            client.publish(
                STATUS_TOPIC,
                json.dumps({
                    "ready": False,
                    "message": "No active profile"
                })
            )
            return

        target_temp = profile["target_temperature"]
        target_humidity = profile["target_humidity"]

        temperature_ready = (
            abs(temperature - target_temp)
            <= TEMP_TOLERANCE
        )

        humidity_ready = (
            abs(humidity - target_humidity)
            <= HUMIDITY_TOLERANCE
        )

        ready = temperature_ready and humidity_ready

        status = {
            "profile": profile["name"],
            "temperature": temperature,
            "humidity": humidity,
            "target_temperature": target_temp,
            "target_humidity": target_humidity,
            "temperature_ready": temperature_ready,
            "humidity_ready": humidity_ready,
            "ready": ready,
            "mode": data.get("mode", "unknown"),
            "message": (
                "Sauna Ready!"
                if ready
                else "Preferred conditions not reached"
            )
        }

        client.publish(
            STATUS_TOPIC,
            json.dumps(status)
        )

        print(
            f'{profile["name"]}: '
            f'{temperature}°C / {humidity}% - '
            f'{status["message"]}'
        )

    except Exception as error:
        print("Error:", error)


client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2
)

client.username_pw_set(USERNAME, PASSWORD)

client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, PORT, 60)

print("Smart Sauna Readiness Service started!")

client.loop_forever()
