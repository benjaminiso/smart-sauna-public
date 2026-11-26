
async function loadReadiness() {

    const message = document.getElementById("readyMessage");
    const profile = document.getElementById("readyProfile");
    const temperature = document.getElementById("readyTemperature");
    const humidity = document.getElementById("readyHumidity");
    const connection = document.getElementById("readyConnection");

    function showOffline(text) {

        message.textContent = text;
        message.style.color = "tomato";

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

        // Check for recent MQTT data
        if (!status.online) {

            showOffline("Waiting for sauna data...");
            return;
        }

        // Check backend errors
        if (status.state === "error") {

            showOffline("Readiness service error");

            connection.textContent =
                "MQTT data received - service error";

            return;
        }

        connection.textContent =
            "MQTT connected - " + (status.mode || "unknown");

        connection.style.color = "lightgreen";

        profile.textContent =
            "Active profile: " +
            (status.profile || "No active profile");

        // Display sauna operational state
        switch (status.state) {

            case "off":

                message.textContent = "Sauna is OFF";
                message.style.color = "lightgray";
                break;

            case "heating":

                message.textContent = "Sauna is heating";
                message.style.color = "orange";
                break;

            case "ready":

                message.textContent = "Sauna Ready!";
                message.style.color = "lightgreen";
                break;

            case "no_profile":

                message.textContent = "No active profile";
                message.style.color = "orange";
                break;

            case "unknown":

                message.textContent = "Sauna state unavailable";
                message.style.color = "tomato";
                break;

            default:

                message.textContent = "Unknown sauna status";
                message.style.color = "lightgray";
        }

        // Display temperature
        temperature.textContent =
            "Temperature: " +
            (status.temperature ?? "--") + " °C / " +
            (status.target_temperature ?? "--") + " °C";

        // Display humidity
        humidity.textContent =
            "Humidity: " +
            (status.humidity ?? "--") + " % / " +
            (status.target_humidity ?? "--") + " %";

        // Neutral measurement colors when OFF
        // or when target values are unavailable
        if (
            status.state === "off" ||
            status.state === "no_profile" ||
            status.state === "unknown"
        ) {

            temperature.style.color = "lightgray";
            humidity.style.color = "lightgray";

        } else {

            temperature.textContent +=
                status.temperature_ready
                    ? " - Target reached"
                    : " - Outside target";

            temperature.style.color =
                status.temperature_ready
                    ? "lightgreen"
                    : "tomato";

            humidity.textContent +=
                status.humidity_ready
                    ? " - Target reached"
                    : " - Outside target";

            humidity.style.color =
                status.humidity_ready
                    ? "lightgreen"
                    : "tomato";
        }

    } catch (error) {

        showOffline("Unable to load sauna status");
        console.error(error);
    }
}

loadReadiness();

setInterval(loadReadiness, 3000);
