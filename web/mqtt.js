
const mqtt = require("mqtt");

let latestStatus = null;
let lastReceived = 0;

const client = mqtt.connect("mqtt://localhost:1883", {
    username: "mqttuser",
    password: "YOUR_PASSWORD"
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
