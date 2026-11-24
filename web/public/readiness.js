
async function loadReadiness() {

    const message = document.getElementById("readyMessage");
    const profile = document.getElementById("readyProfile");
    const temperature = document.getElementById("readyTemperature");
    const humidity = document.getElementById("readyHumidity");
    const connection = document.getElementById("readyConnection");

    function showOffline(text) {
        message.textContent = text;
        message.style.color = "lightgray";
        profile.textContent = "Active profile: --";
        temperature.textContent = "Temperature: --";
        humidity.textContent = "Humidity: --";
        temperature.style.color = "lightgray";
        humidity.style.color = "lightgray";
        connection.textContent = "Waiting for live data";
        connection.style.color = "tomato";
    }

    try {
        const response = await fetch("/api/status", {
            cache: "no-store"
        });

        if (!response.ok) {
            throw new Error("Could not load readiness status");
        }

        const status = await response.json();

        if (!status.online) {
            showOffline("Waiting for sauna data...");
            return;
        }

        connection.textContent =
            "MQTT connected - " + (status.mode || "unknown");

        connection.style.color = "lightgreen";

        if (!status.profile) {
            showOffline("No active profile");
            connection.textContent = "MQTT connected";
            connection.style.color = "lightgreen";
            return;
        }

        profile.textContent =
            "Active profile: " + status.profile;

        message.textContent = status.ready
            ? "Sauna Ready!"
            : "Sauna not ready";

        message.style.color = status.ready
            ? "lightgreen"
            : "orange";

        temperature.textContent =
            "Temperature: " +
            status.temperature + " °C / " +
            status.target_temperature + " °C - " +
            (status.temperature_ready
                ? "Target reached"
                : "Outside target");

        temperature.style.color =
            status.temperature_ready
                ? "lightgreen"
                : "tomato";

        humidity.textContent =
            "Humidity: " +
            status.humidity + " % / " +
            status.target_humidity + " % - " +
            (status.humidity_ready
                ? "Target reached"
                : "Outside target");

        humidity.style.color =
            status.humidity_ready
                ? "lightgreen"
                : "tomato";

    } catch (error) {
        showOffline("Unable to load sauna status");
        console.error(error);
    }
}

loadReadiness();

setInterval(loadReadiness, 3000);
