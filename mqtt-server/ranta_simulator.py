import json
import os
import time
from itertools import cycle
from threading import Event

import paho.mqtt.client as mqtt

TOPIC = "sauna/ranta/sensors"
INTERVAL_SECONDS = 3

# Esitystä varten nopeutettu jäähtymis- ja lämpenemisjakso.
TEMPERATURES = (5.0, 3.0, 2.5, 0.0, -0.5, -2.0, 1.0, 4.0)


def main():
    host = os.getenv("MQTT_HOST", "localhost")
    port = int(os.getenv("MQTT_PORT", "1883"))
    username = os.getenv("MQTT_USERNAME", "mqttuser")
    password = os.getenv("MQTT_PASSWORD")

    if not password:
        raise SystemExit("MQTT_PASSWORD puuttuu. Lataa paikallinen .env.")

    connected = Event()

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            connected.set()
        else:
            print(f"MQTT-kirjautuminen epäonnistui: {reason_code}", flush=True)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.connect(host, port, keepalive=60)
    client.loop_start()

    try:
        if not connected.wait(timeout=5):
            raise SystemExit("MQTT-yhteyttä ei vahvistettu. Tarkista broker ja .env.")

        for temperature in cycle(TEMPERATURES):
            data = {
                "sauna_id": "ranta",
                "temperature": temperature,
                "humidity": 70.0,
                "mode": "simulation",
            }
            message = client.publish(TOPIC, json.dumps(data), qos=1)
            message.wait_for_publish(timeout=5)
            if not message.is_published():
                raise SystemExit("MQTT-broker ei kuitannut mittausta.")

            print(f"{TOPIC}: {data}", flush=True)
            time.sleep(INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\nRantasaunan simulaattori pysäytetty.")
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    main()