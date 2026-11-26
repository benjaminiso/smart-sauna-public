
import json
import sqlite3
import math
from getpass import getpass
from pathlib import Path

import paho.mqtt.client as mqtt


# MQTT configuration
BROKER = "localhost"
PORT = 1883
USERNAME = "mqttuser"
PASSWORD = getpass("Enter MQTT password: ")

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


def get_sauna_configuration():

    with sqlite3.connect(DB_PATH, timeout=5) as conn:

        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN")

        profile = conn.execute(
            "SELECT * FROM profiles WHERE active = 1"
        ).fetchone()

        state = conn.execute(
            "SELECT is_on FROM sauna_state WHERE id = 1"
        ).fetchone()

        if state is None:
            sauna_on = None
        else:
            sauna_on = state["is_on"] == 1

        return profile, sauna_on


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

        profile, sauna_on = get_sauna_configuration()

        target_temp = None
        target_humidity = None

        temperature_ready = False
        humidity_ready = False
        ready = False

        profile_name = "No active profile"

        # Check preferred conditions
        if profile is not None:

            profile_name = profile["name"]

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

        # Determine overall sauna status
        if sauna_on is None:

            state = "unknown"
            message = "Sauna state unavailable"

        elif not sauna_on:

            state = "off"
            message = "Sauna is OFF"

        elif profile is None:

            state = "no_profile"
            message = "No active profile"

        elif temperature_ready and humidity_ready:

            state = "ready"
            ready = True
            message = "Sauna Ready!"

        else:

            state = "heating"
            message = "Preferred conditions not reached"

        # Publish sauna status
        status = {
            "profile": profile_name,
            "temperature": temperature,
            "humidity": humidity,
            "target_temperature": target_temp,
            "target_humidity": target_humidity,
            "temperature_ready": temperature_ready,
            "humidity_ready": humidity_ready,
            "sauna_on": sauna_on,
            "state": state,
            "ready": ready,
            "mode": data.get("mode", "unknown"),
            "message": message
        }

        client.publish(
            STATUS_TOPIC,
            json.dumps(status),
            qos=1
        )

        print(
            f"[{state.upper()}] "
            f"{profile_name}: "
            f"{temperature} C / {humidity}% - "
            f"{message}"
        )

    except Exception as error:

        print("Error:", error)

        client.publish(
            STATUS_TOPIC,
            json.dumps({
                "sauna_on": None,
                "state": "error",
                "ready": False,
                "temperature_ready": False,
                "humidity_ready": False,
                "message": "Readiness service error"
            }),
            qos=1
        )


# Start MQTT client
client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2
)

client.username_pw_set(USERNAME, PASSWORD)

client.on_connect = on_connect
client.on_message = on_message

client.reconnect_delay_set(
    min_delay=1,
    max_delay=30
)

client.connect(BROKER, PORT, 60)

print("Smart Sauna Readiness Service started!")

try:

    client.loop_forever()

except KeyboardInterrupt:

    print("\nReadiness service stopped.")

finally:

    client.disconnect()
