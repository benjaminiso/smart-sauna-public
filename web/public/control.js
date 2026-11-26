
const saunaStateElement =
    document.getElementById("saunaState");

const saunaOnButton =
    document.getElementById("saunaOnButton");

const saunaOffButton =
    document.getElementById("saunaOffButton");

const controlMessage =
    document.getElementById("controlMessage");

let controlBusy = false;


// =============================
// DISPLAY SAUNA STATE
// =============================

function displaySaunaState(isOn) {

    saunaStateElement.textContent =
        isOn ? "Sauna is ON" : "Sauna is OFF";

    saunaStateElement.className =
        isOn ? "on" : "off";

    saunaOnButton.disabled = isOn;
    saunaOffButton.disabled = !isOn;

    controlMessage.textContent =
        "Backend connected - simulation";
}


// =============================
// DISPLAY CONNECTION ERROR
// =============================

function displayControlError(message) {

    saunaStateElement.textContent =
        "Sauna state unavailable";

    saunaStateElement.className = "unknown";

    saunaOnButton.disabled = true;
    saunaOffButton.disabled = true;

    controlMessage.textContent = message;
}


// =============================
// GET CURRENT SAUNA STATE
// =============================

async function loadSaunaState() {

    if (controlBusy) {
        return;
    }

    controlBusy = true;

    try {

        const response = await fetch(
            "/api/sauna/state",
            { cache: "no-store" }
        );

        if (!response.ok) {
            throw new Error("Could not load sauna state");
        }

        const state = await response.json();

        if (state.is_on !== 0 && state.is_on !== 1) {
            throw new Error("Invalid sauna state");
        }

        displaySaunaState(state.is_on === 1);

    } catch (error) {

        displayControlError(error.message);
        console.error(error);

    } finally {

        controlBusy = false;
    }
}


// =============================
// CHANGE SAUNA STATE
// =============================

async function setSaunaState(isOn) {

    if (controlBusy) {
        return;
    }

    controlBusy = true;

    saunaOnButton.disabled = true;
    saunaOffButton.disabled = true;

    controlMessage.textContent =
        "Updating sauna state...";

    try {

        const response = await fetch(
            "/api/sauna/state",
            {
                method: "PUT",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    is_on: isOn ? 1 : 0
                })
            }
        );

        const result = await response.json();

        if (!response.ok) {
            throw new Error(
                result.error || "Could not update sauna"
            );
        }

        if (result.is_on !== 0 && result.is_on !== 1) {
            throw new Error("Invalid sauna state");
        }

        displaySaunaState(result.is_on === 1);

        controlMessage.textContent = result.message;

    } catch (error) {

        displayControlError(error.message);
        console.error(error);

    } finally {

        controlBusy = false;
    }
}


// =============================
// BUTTON EVENTS
// =============================

saunaOnButton.addEventListener("click", () => {
    setSaunaState(true);
});

saunaOffButton.addEventListener("click", () => {
    setSaunaState(false);
});


// =============================
// AUTOMATIC SYNCHRONIZATION
// =============================

loadSaunaState();

setInterval(loadSaunaState, 3000);
