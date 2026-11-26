
import time
import json
import threading

import paho.mqtt.client as mqtt
import os


# =============================
# MQTT CONFIGURATION
# =============================

BROKER = os.getenv("MQTT_HOST", "localhost")
PORT = int(os.getenv("MQTT_PORT", "1883"))
USERNAME = os.getenv("MQTT_USERNAME", "mqttuser")
PASSWORD = os.getenv("MQTT_PASSWORD")

if not PASSWORD:
    raise SystemExit("MQTT_PASSWORD puuttuu. Lataa paikallinen .env ennen käynnistystä.")

TOPIC = "sauna/sensors"

TOPIC_CONTROL_STATE = "sauna/control/state"
TOPIC_CONTROL_REQUEST = "sauna/control/request"

TOPIC_PROFILE_LIST = "sauna/profiles/list"
TOPIC_PROFILE_REQUEST = "sauna/profiles/request"


# =============================
# SIMULATION SETTINGS
# =============================

ROOM_TEMPERATURE = 20.0
ROOM_HUMIDITY = 30.0

HEATING_RATE = 2.0
COOLING_RATE = 1.0
HUMIDITY_RATE = 0.5

UPDATE_INTERVAL = 3
REQUEST_INTERVAL = 5
STATE_TIMEOUT = 15


# =============================
# SHARED STATE
# =============================

connected = False
sauna_on = None
active_profile = None

last_control_message = 0
last_profile_message = 0

state_lock = threading.Lock()

temperature = ROOM_TEMPERATURE
humidity = ROOM_HUMIDITY


# =============================
# REQUEST BACKEND STATE
# =============================

def request_state(client):

    client.publish(
        TOPIC_CONTROL_REQUEST,
        "{}",
        qos=1
    )

    client.publish(
        TOPIC_PROFILE_REQUEST,
        "{}",
        qos=1
    )


# =============================
# MQTT CALLBACKS
# =============================

def on_connect(
    client, userdata, flags, reason_code, properties
):

    global connected
    global sauna_on, active_profile
    global last_control_message, last_profile_message

    with state_lock:

        connected = reason_code == 0
        sauna_on = None
        active_profile = None
        last_control_message = 0
        last_profile_message = 0

    if reason_code == 0:

        print("Simulator connected to MQTT")

        client.subscribe([
            (TOPIC_CONTROL_STATE, 1),
            (TOPIC_PROFILE_LIST, 1)
        ])

        request_state(client)

    else:
        print(f"Connection failed: {reason_code}")


def on_disconnect(
    client, userdata, flags, reason_code, properties
):

    global connected
    global sauna_on, active_profile

    with state_lock:

        connected = False
        sauna_on = None
        active_profile = None

    print("MQTT disconnected - simulated heating stopped")


def on_message(client, userdata, message):

    global sauna_on, active_profile
    global last_control_message, last_profile_message

    try:

        data = json.loads(
            message.payload.decode("utf-8")
        )

        # Wait for fresh backend information
        if message.retain:
            return

        with state_lock:

            if message.topic == TOPIC_CONTROL_STATE:

                if not isinstance(data, dict):
                    return

                value = data.get("is_on")

                if type(value) is int and value in (0, 1):

                    sauna_on = value == 1
                    last_control_message = time.monotonic()

            elif message.topic == TOPIC_PROFILE_LIST:

                if not isinstance(data, list):
                    return

                active_profile = next(
                    (
                        profile for profile in data
                        if isinstance(profile, dict)
                        and profile.get("active") == 1
                    ),
                    None
                )

                last_profile_message = time.monotonic()

    except (ValueError, UnicodeDecodeError) as error:

        print(f"Invalid MQTT message: {error}")


# =============================
# SIMULATION HELPER
# =============================

def move_towards(current, target, rate):

    if current < target:
        return min(current + rate, target)

    if current > target:
        return max(current - rate, target)

    return current


# =============================
# START MQTT CLIENT
# =============================

client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id="sauna-sensor-simulator"
)

client.username_pw_set(USERNAME, PASSWORD)

client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_message = on_message

client.reconnect_delay_set(
    min_delay=1,
    max_delay=30
)

client.connect(BROKER, PORT, 60)
client.loop_start()

print("Smart Sauna Simulator started!")
print("Waiting for sauna state and active profile...")

last_request = time.monotonic()


# =============================
# MAIN SIMULATION LOOP
# =============================

try:

    while True:

        now = time.monotonic()

        with state_lock:

            mqtt_connected = connected
            current_state = sauna_on

            profile = (
                active_profile.copy()
                if active_profile is not None
                else None
            )

            state_fresh = (
                now - last_control_message
                <= STATE_TIMEOUT
            )

            profile_fresh = (
                now - last_profile_message
                <= STATE_TIMEOUT
            )

        # Request fresh backend information
        if mqtt_connected:

            if now - last_request >= REQUEST_INTERVAL:

                request_state(client)
                last_request = now

        # Default conditions when heating is disabled
        target_temperature = ROOM_TEMPERATURE
        target_humidity = ROOM_HUMIDITY

        simulation_status = "COOLING / OFF"

        if not mqtt_connected:

            simulation_status = "MQTT OFFLINE"

        elif not state_fresh or not profile_fresh:

            simulation_status = "WAITING FOR BACKEND"

        elif current_state is None:

            simulation_status = "STATE UNKNOWN"

        elif current_state:

            if profile is None:

                simulation_status = "NO ACTIVE PROFILE"

            else:

                try:

                    target_temperature = float(
                        profile["target_temperature"]
                    )

                    target_humidity = float(
                        profile["target_humidity"]
                    )

                    if not (
                        20 <= target_temperature <= 100
                        and 0 <= target_humidity <= 100
                    ):
                        raise ValueError("Invalid targets")

                    simulation_status = "ON / " + str(
                        profile.get("name", "Unknown")
                    )

                except (KeyError, ValueError, TypeError):

                    target_temperature = ROOM_TEMPERATURE
                    target_humidity = ROOM_HUMIDITY

                    simulation_status = "INVALID PROFILE"

        # Adjust temperature
        rate = (
            HEATING_RATE
            if temperature < target_temperature
            else COOLING_RATE
        )

        temperature = move_towards(
            temperature,
            target_temperature,
            rate
        )

        # Adjust humidity
        humidity = move_towards(
            humidity,
            target_humidity,
            HUMIDITY_RATE
        )

        # Preserve existing sensor data format
        data = {
            "temperature": round(temperature, 1),
            "humidity": round(humidity, 1),
            "mode": "simulation"
        }

        if mqtt_connected:

            client.publish(
                TOPIC,
                json.dumps(data),
                qos=1
            )

            print(
                f"[{simulation_status}] "
                f"Temperature: {temperature:.1f} C | "
                f"Humidity: {humidity:.1f}% | "
                f"Target: {target_temperature:.1f} C / "
                f"{target_humidity:.1f}%"
            )

        else:

            print(
                f"[OFFLINE] "
                f"Temperature: {temperature:.1f} C | "
                f"Humidity: {humidity:.1f}%"
            )

        time.sleep(UPDATE_INTERVAL)

except KeyboardInterrupt:

    print("\nSimulator stopped.")

finally:

    client.disconnect()
    client.loop_stop()
