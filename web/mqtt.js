
const mqtt = require("mqtt");

let latestStatus = null;
let lastReceived = 0;

const host = process.env.MQTT_HOST || "localhost";
const port = process.env.MQTT_PORT || "1883";
const username = process.env.MQTT_USERNAME || "mqttuser";
const password = process.env.MQTT_PASSWORD;

if (!password) {
  throw new Error("MQTT_PASSWORD puuttuu. Lataa paikallinen .env ennen käynnistystä.");
}

const client = mqtt.connect(`mqtt://${host}:${port}`, {
  username,
  password,
});

client.on("connect", () => {
    console.log("Web server connected to MQTT!");

    client.subscribe("sauna/status");
});

client.on("message", (topic, message) => {
    if (topic === "sauna/status") {
        try {
            latestStatus = JSON.parse(message.toString());
            lastReceived = Date.now();
        } catch (error) {
            console.error("Invalid MQTT message:", error);
        }
    }
});

client.on("error", (error) => {
    console.error("MQTT error:", error.message);
});

function getStatus() {
    if (!latestStatus || Date.now() - lastReceived > 15000) {
        return {
            ready: false,
            online: false,
            message: "Waiting for live sauna data"
        };
    }

    return {
        ...latestStatus,
        online: true
    };
}

module.exports = { getStatus };
