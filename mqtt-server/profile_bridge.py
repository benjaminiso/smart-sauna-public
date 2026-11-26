
import json
import time
import getpass
import urllib.request
import urllib.error

import paho.mqtt.client as mqtt


# =============================
# CONFIGURATION
# =============================

BROKER = "localhost"
PORT = 1883

USERNAME = "mqttuser"
PASSWORD = getpass.getpass("Enter MQTT password: ")

API_URL = "http://127.0.0.1:3000/api/profiles"

TOPIC_REQUEST = "sauna/profiles/request"
TOPIC_LIST = "sauna/profiles/list"
TOPIC_ACTIVATE = "sauna/profiles/activate"
TOPIC_CREATE = "sauna/profiles/create"
TOPIC_UPDATE = "sauna/profiles/update"
TOPIC_DELETE = "sauna/profiles/delete"
TOPIC_RESULT = "sauna/profiles/result"


# =============================
# HTTP API COMMUNICATION
# =============================

def api_request(method="GET", endpoint="", data=None):

    body = None

    if data is not None:
        body = json.dumps(data).encode("utf-8")

    request = urllib.request.Request(
        API_URL + endpoint,
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

    profiles = api_request()

    if force or profiles != last_profiles:

        client.publish(
            TOPIC_LIST,
            json.dumps(profiles),
            qos=1
        )

        last_profiles = profiles

        print(f"Published {len(profiles)} profiles")


# =============================
# PUBLISH OPERATION RESULT
# =============================

def publish_result(
    client, action, success, message, request_id=None
):

    result = {
        "action": action,
        "success": success,
        "message": message,
        "request_id": request_id
    }

    client.publish(
        TOPIC_RESULT,
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

        print("Profile bridge connected to MQTT")

        client.subscribe([
            (TOPIC_REQUEST, 1),
            (TOPIC_ACTIVATE, 1),
            (TOPIC_CREATE, 1),
            (TOPIC_UPDATE, 1),
            (TOPIC_DELETE, 1)
        ])

        try:
            publish_profiles(client, force=True)
        except Exception as error:
            print(f"Profile request failed: {error}")

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
# MQTT MESSAGE HANDLING
# =============================

def on_message(client, userdata, message):

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

print("Smart Sauna profile bridge running")


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
                print(f"Synchronization error: {error}")

except KeyboardInterrupt:

    print("\nStopping profile bridge")

finally:

    client.disconnect()
    client.loop_stop()
