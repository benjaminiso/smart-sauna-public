
import json
import time
import urllib.request
import urllib.error
import threading
import os

import paho.mqtt.client as mqtt


# =============================
# CONFIGURATION
# =============================

BROKER = os.getenv("MQTT_HOST", "localhost")
PORT = int(os.getenv("MQTT_PORT", "1883"))
USERNAME = os.getenv("MQTT_USERNAME", "mqttuser")
PASSWORD = os.getenv("MQTT_PASSWORD")

if not PASSWORD:
    raise SystemExit("MQTT_PASSWORD puuttuu. Lataa paikallinen .env ennen käynnistystä.")

API_URL = "http://127.0.0.1:3000/api/profiles"
STATE_API_URL = "http://127.0.0.1:3000/api/sauna/state"

# Profile topics
TOPIC_REQUEST = "sauna/profiles/request"
TOPIC_LIST = "sauna/profiles/list"
TOPIC_ACTIVATE = "sauna/profiles/activate"
TOPIC_CREATE = "sauna/profiles/create"
TOPIC_UPDATE = "sauna/profiles/update"
TOPIC_DELETE = "sauna/profiles/delete"
TOPIC_RESULT = "sauna/profiles/result"

# Sauna control topics
TOPIC_CONTROL_REQUEST = "sauna/control/request"
TOPIC_CONTROL_SET = "sauna/control/set"
TOPIC_CONTROL_STATE = "sauna/control/state"
TOPIC_CONTROL_RESULT = "sauna/control/result"

sync_lock = threading.Lock()


# =============================
# HTTP API COMMUNICATION
# =============================

def api_request(
    method="GET",
    endpoint="",
    data=None,
    base_url=API_URL
):

    body = None

    if data is not None:
        body = json.dumps(data).encode("utf-8")

    request = urllib.request.Request(
        base_url + endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method=method
    )

    try:
        with urllib.request.urlopen(
            request, timeout=5
        ) as response:

            return json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.HTTPError as error:

        try:
            result = json.loads(
                error.read().decode("utf-8")
            )
            message = result.get("error", str(error))
        except Exception:
            message = str(error)

        raise RuntimeError(message)

    except urllib.error.URLError as error:
        raise RuntimeError(
            f"Backend unavailable: {error.reason}"
        )


# =============================
# PUBLISH PROFILES
# =============================

last_profiles = None


def publish_profiles(client, force=False):

    global last_profiles

    with sync_lock:

        profiles = api_request()

        if force or profiles != last_profiles:

            info = client.publish(
                TOPIC_LIST,
                json.dumps(profiles),
                qos=1
            )

            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError("Profile publish failed")

            last_profiles = profiles

            print(f"Published {len(profiles)} profiles")


# =============================
# PUBLISH SAUNA STATE
# =============================

last_sauna_state = None


def publish_sauna_state(client, force=False):

    global last_sauna_state

    with sync_lock:

        state = api_request(
            base_url=STATE_API_URL
        )

        if force or state != last_sauna_state:

            info = client.publish(
                TOPIC_CONTROL_STATE,
                json.dumps(state),
                qos=1,
                retain=True
            )

            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError("State publish failed")

            last_sauna_state = state

            status = "ON" if state["is_on"] == 1 else "OFF"

            print(f"Published sauna state: {status}")


# =============================
# PUBLISH OPERATION RESULT
# =============================

def publish_result(
    client,
    action,
    success,
    message,
    request_id=None,
    topic=TOPIC_RESULT
):

    result = {
        "action": action,
        "success": success,
        "message": message,
        "request_id": request_id
    }

    client.publish(
        topic,
        json.dumps(result),
        qos=1
    )

    print(result)


# =============================
# MQTT CONNECTION
# =============================

def on_connect(
    client, userdata, flags, reason_code, properties
):

    if reason_code == 0:

        print("Profile and sauna control bridge connected to MQTT")

        client.subscribe([
            (TOPIC_REQUEST, 1),
            (TOPIC_ACTIVATE, 1),
            (TOPIC_CREATE, 1),
            (TOPIC_UPDATE, 1),
            (TOPIC_DELETE, 1),
            (TOPIC_CONTROL_REQUEST, 1),
            (TOPIC_CONTROL_SET, 1)
        ])

        try:
            publish_profiles(client, force=True)
        except Exception as error:
            print(f"Profile request failed: {error}")

        try:
            publish_sauna_state(client, force=True)
        except Exception as error:
            print(f"Sauna state request failed: {error}")

    else:
        print(f"Connection failed: {reason_code}")


# =============================
# VALIDATE PROFILE ID
# =============================

def get_profile_id(data):

    profile_id = data.get("id")

    if type(profile_id) is not int or profile_id < 1:
        raise ValueError("Invalid profile ID")

    return profile_id


# =============================
# SAUNA CONTROL HANDLING
# =============================

def handle_sauna_control(client, message):

    action = message.topic.split("/")[-1]
    request_id = None

    try:

        if message.retain:
            return

        payload = message.payload.decode("utf-8")
        data = json.loads(payload) if payload else {}

        if not isinstance(data, dict):
            raise ValueError("Invalid request format")

        request_id = data.get("request_id")

        if message.topic == TOPIC_CONTROL_REQUEST:

            publish_sauna_state(client, force=True)
            return

        elif message.topic == TOPIC_CONTROL_SET:

            is_on = data.get("is_on")

            if type(is_on) is not int or is_on not in (0, 1):
                raise ValueError("Sauna state must be 0 or 1")

            result = api_request(
                method="PUT",
                data={"is_on": is_on},
                base_url=STATE_API_URL
            )

        else:
            return

    except Exception as error:

        publish_result(
            client,
            action,
            False,
            str(error),
            request_id,
            topic=TOPIC_CONTROL_RESULT
        )

        return

    publish_result(
        client,
        action,
        True,
        result.get("message", "Sauna state updated"),
        request_id,
        topic=TOPIC_CONTROL_RESULT
    )

    try:
        publish_sauna_state(client, force=True)
    except Exception as error:
        print(f"Sauna state refresh failed: {error}")


# =============================
# MQTT MESSAGE HANDLING
# =============================

def on_message(client, userdata, message):

    if message.topic in (
        TOPIC_CONTROL_REQUEST,
        TOPIC_CONTROL_SET
    ):

        handle_sauna_control(client, message)
        return

    action = message.topic.split("/")[-1]
    request_id = None

    try:

        # Ignore retained commands
        if message.retain:
            return

        payload = message.payload.decode("utf-8")

        data = json.loads(payload) if payload else {}

        if not isinstance(data, dict):
            raise ValueError("Invalid request format")

        request_id = data.get("request_id")

        # Request all profiles
        if message.topic == TOPIC_REQUEST:

            publish_profiles(client, force=True)
            return

        # Activate profile
        elif message.topic == TOPIC_ACTIVATE:

            profile_id = get_profile_id(data)

            result = api_request(
                "PUT",
                f"/{profile_id}/activate"
            )

        # Create profile
        elif message.topic == TOPIC_CREATE:

            result = api_request(
                "POST",
                data=data
            )

        # Update profile
        elif message.topic == TOPIC_UPDATE:

            profile_id = get_profile_id(data)

            result = api_request(
                "PUT",
                f"/{profile_id}",
                data=data
            )

        # Delete profile
        elif message.topic == TOPIC_DELETE:

            profile_id = get_profile_id(data)

            result = api_request(
                "DELETE",
                f"/{profile_id}"
            )

        else:
            return

    except Exception as error:

        publish_result(
            client,
            action,
            False,
            str(error),
            request_id
        )

        return

    publish_result(
        client,
        action,
        True,
        result.get("message", "Operation completed"),
        request_id
    )

    try:
        publish_profiles(client, force=True)
    except Exception as error:
        print(f"Profile refresh failed: {error}")


# =============================
# START MQTT CLIENT
# =============================

client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id="sauna-profile-bridge"
)

client.username_pw_set(USERNAME, PASSWORD)

client.on_connect = on_connect
client.on_message = on_message

client.reconnect_delay_set(
    min_delay=1,
    max_delay=30
)

client.connect(BROKER, PORT, 60)

client.loop_start()

print("Smart Sauna profile and control bridge running")


# =============================
# WEBSITE SYNCHRONIZATION
# =============================

try:

    while True:

        time.sleep(3)

        if client.is_connected():

            try:
                publish_profiles(client)

            except Exception as error:
                print(f"Profile synchronization error: {error}")

            try:
                publish_sauna_state(client)

            except Exception as error:
                print(f"Sauna synchronization error: {error}")

except KeyboardInterrupt:

    print("\nStopping sauna bridge")

finally:

    client.disconnect()
    client.loop_stop()
