
import time
import json
import paho.mqtt.client as mqtt

# MQTT configuration
BROKER = "localhost"
PORT = 1883
USERNAME = "mqttuser"
PASSWORD = "YOUR_PASSWORD"

TOPIC = "sauna/sensors"

# Connect to MQTT broker
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(USERNAME, PASSWORD)
client.connect(BROKER, PORT, 60)
client.loop_start()

# Starting conditions
temperature = 20.0
humidity = 30.0

print("Smart Sauna Simulator started!")

try:
    while True:

        data = {
            "temperature": round(temperature, 1),
            "humidity": round(humidity, 1),
            "mode": "simulation"
        }

        client.publish(TOPIC, json.dumps(data), qos=1)

        print(f"Published: {data}")

        # Simulate sauna heating
        temperature = min(temperature + 2.0, 80.0)
        humidity = min(humidity + 0.5, 45.0)

        time.sleep(3)

except KeyboardInterrupt:
    print("\nSimulator stopped.")

finally:
    client.disconnect()
    client.loop_stop()
