
let selectedProfileId = null;
let profiles = [];

async function profileRequest(url, method = "GET", data) {
    const options = {
        method,
        headers: {
            "Content-Type": "application/json"
        }
    };

    if (data !== undefined) {
        options.body = JSON.stringify(data);
    }

    const response = await fetch(url, options);
    const result = await response.json();

    if (!response.ok) {
        throw new Error(result.error || "Request failed");
    }

    return result;
}

// Load profiles from SQLite through the API
async function loadProfiles() {
    try {
        profiles = await profileRequest("/api/profiles");

        const list = document.getElementById("profileList");
        list.replaceChildren();

        profiles.forEach(profile => {
            const row = document.createElement("div");
            row.className = "profile-row";

            const info = document.createElement("span");

            info.textContent =
                profile.name + " — " +
                profile.target_temperature + " °C / " +
                profile.target_humidity + " %" +
                (profile.active ? " (Active)" : "");

            const editButton = document.createElement("button");
            editButton.textContent = "Edit";
            editButton.onclick = () => editProfile(profile);

            const activateButton = document.createElement("button");
            activateButton.textContent = "Activate";
            activateButton.disabled = Boolean(profile.active);

            activateButton.onclick = () =>
                activateProfile(profile.id);

            row.append(info, editButton, activateButton);
            list.appendChild(row);
        });

    } catch (error) {
        alert(error.message);
    }
}

// Fill the form with an existing profile
function editProfile(profile) {
    selectedProfileId = profile.id;

    document.getElementById("profileName").value =
        profile.name;

    document.getElementById("targetTemperature").value =
        profile.target_temperature;

    document.getElementById("targetHumidity").value =
        profile.target_humidity;
}

// Clear the form for a new profile
function newProfile() {
    selectedProfileId = null;

    document.getElementById("profileName").value = "";
    document.getElementById("targetTemperature").value = 75;
    document.getElementById("targetHumidity").value = 40;
}

// Create or update a profile
async function saveProfile() {
    const name = document.getElementById("profileName");
    const temperature =
        document.getElementById("targetTemperature");
    const humidity =
        document.getElementById("targetHumidity");

    if (!name.value.trim() ||
        !temperature.reportValidity() ||
        !humidity.reportValidity()) {

        alert("Please enter valid profile information.");
        return;
    }

    const data = {
        name: name.value.trim(),
        target_temperature: Number(temperature.value),
        target_humidity: Number(humidity.value)
    };

    try {
        if (selectedProfileId === null) {
            await profileRequest(
                "/api/profiles", "POST", data
            );
        } else {
            await profileRequest(
                "/api/profiles/" + selectedProfileId,
                "PUT", data
            );
        }

        newProfile();
        await loadProfiles();

        alert("Profile saved!");

    } catch (error) {
        alert(error.message);
    }
}

// Activate a profile
async function activateProfile(id) {
    try {
        await profileRequest(
            "/api/profiles/" + id + "/activate",
            "PUT"
        );

        await loadProfiles();

    } catch (error) {
        alert(error.message);
    }
}

// Delete a profile
async function deleteProfile() {
    if (selectedProfileId === null) {
        alert("Select a profile to edit first.");
        return;
    }

    if (!confirm("Delete this profile?")) {
        return;
    }

    try {
        await profileRequest(
            "/api/profiles/" + selectedProfileId,
            "DELETE"
        );

        newProfile();
        await loadProfiles();

    } catch (error) {
        alert(error.message);
    }
}

loadProfiles();
