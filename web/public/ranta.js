(() => {
  const temperature = document.getElementById("rantaTemperature");
  const humidity = document.getElementById("rantaHumidity");
  const timestamp = document.getElementById("rantaTimestamp");
  const status = document.getElementById("rantaStatus");

  const heater = document.getElementById("rantaHeater");
  const heatingReason = document.getElementById("rantaHeatingReason");
  const frostAlarm = document.getElementById("rantaFrostAlarm");

  const automaticEnabled = document.getElementById("rantaAutomaticEnabled");
  const autoRequest = document.getElementById("rantaAutoRequest");
  const remoteRequest = document.getElementById("rantaRemoteRequest");

  const enableAutomatic = document.getElementById("rantaEnableAutomatic");
  const disableAutomatic = document.getElementById("rantaDisableAutomatic");
  const automaticWarning = document.getElementById("rantaAutomaticWarning");

  const requestHeat = document.getElementById("rantaRequestHeat");
  const returnToAuto = document.getElementById("rantaReturnToAuto");
  const commandStatus = document.getElementById("rantaCommandStatus");

  let sendingCommand = false;
  let latestProtection = null;
  let commandVersion = 0;

  const numberFormat = new Intl.NumberFormat("fi-FI", {
    maximumFractionDigits: 1,
  });

  // Status colors

  function setStatusColor(element, color) {
    element.classList.remove(
      "status-active",
      "status-inactive",
      "status-success",
      "status-warning",
      "status-error"
    );

    element.classList.add("status-" + color);
  }

  function showValue(element, message, color) {
    element.textContent = message;
    setStatusColor(element, color);
  }

  // Enable and disable buttons based on server state

  function updateButtons() {
    const automatic = latestProtection?.automatic_enabled;
    const remote = latestProtection?.remote_requested;

    enableAutomatic.disabled =
      sendingCommand || automatic !== false;

    disableAutomatic.disabled =
      sendingCommand || automatic !== true;

    requestHeat.disabled =
      sendingCommand || remote !== false;

    returnToAuto.disabled =
      sendingCommand || remote !== true;
  }

  // Display frost protection information

  function showFrostProtection(protection) {
    latestProtection = protection ?? null;

    const automatic = protection?.automatic_enabled;
    const autoHeating = protection?.heating_requested;
    const remote = protection?.remote_requested;
    const heaterOn = protection?.heater_on;
    const alarm = protection?.frost_alarm;

    // Actual simulated heater state

    showValue(
      heater,
      heaterOn === true ? "● PÄÄLLÄ"
        : heaterOn === false ? "● POIS PÄÄLTÄ"
        : "● TILA EI TIEDOSSA",
      heaterOn === true ? "active"
        : heaterOn === false ? "inactive"
        : "warning"
    );

    // Reason for heating

    if (heaterOn == null) {
      heatingReason.textContent =
        "Lämmittimen tilaa ei voida vahvistaa.";
    } else if (autoHeating && remote) {
      heatingReason.textContent =
        "Lämmityksen syy: automatiikka ja etäohjaus";
    } else if (autoHeating) {
      heatingReason.textContent =
        "Lämmityksen syy: automatiikka";
    } else if (remote) {
      heatingReason.textContent =
        "Lämmityksen syy: etäohjaus";
    } else if (automatic === false) {
      heatingReason.textContent =
        "Automaattinen lämmitys poistettu käytöstä.";
    } else {
      heatingReason.textContent =
        "Ei lämmitystarvetta.";
    }

    // Frost alarm

    showValue(
      frostAlarm,
      alarm === true ? "PAKKASHÄLYTYS"
        : alarm === false ? "Ei hälytystä"
        : "Ei arvioitavissa",
      alarm === true ? "error"
        : alarm === false ? "success"
        : "warning"
    );

    // Automatic protection setting

    showValue(
      automaticEnabled,
      automatic === true ? "Käytössä"
        : automatic === false ? "Pois käytöstä"
        : "Ei tiedossa",
      automatic === true ? "success"
        : automatic === false ? "inactive"
        : "warning"
    );

    automaticWarning.hidden = automatic !== false;

    // Automatic heating status

    if (automatic === false) {
      showValue(autoRequest, "Pois käytöstä", "inactive");
    } else if (autoHeating === true) {
      showValue(autoRequest, "Lämmittää", "active");
    } else if (autoHeating === false) {
      showValue(autoRequest, "Valmiustilassa", "inactive");
    } else {
      showValue(autoRequest, "Ei tiedossa", "warning");
    }

    // Remote heating status

    showValue(
      remoteRequest,
      remote === true ? "Aktiivinen"
        : remote === false ? "Ei aktiivinen"
        : "Ei tiedossa",
      remote === true ? "active"
        : remote === false ? "inactive"
        : "warning"
    );

    updateButtons();
  }

  // Send heating commands to server

  async function sendCommand(url, body, successMessage) {
    if (sendingCommand) return;

    sendingCommand = true;
    commandVersion++;
    updateButtons();

    showValue(
      commandStatus,
      "Lähetetään komentoa…",
      "warning"
    );

    try {
      const response = await fetch(url, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(5000),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const result = await response.json();

      const [key, requestedValue] =
        Object.entries(body)[0];

      if (result[key] !== requestedValue) {
        throw new Error("Komennon tilaa ei voitu vahvistaa.");
      }

      // Confirm the updated server state

      const stateResponse = await fetch(
        "/api/latest?sauna=ranta",
        {
          cache: "no-store",
          signal: AbortSignal.timeout(5000),
        }
      );

      if (!stateResponse.ok) {
        throw new Error(`HTTP ${stateResponse.status}`);
      }

      const reading = await stateResponse.json();

      showFrostProtection(reading.frost_protection);

      if (reading.frost_protection?.[key] !== requestedValue) {
        throw new Error("Palvelimen tila ei vastaa komentoa.");
      }

      showValue(
        commandStatus,
        "✓ " + successMessage,
        "success"
      );

    } catch (error) {
      showFrostProtection(null);

      showValue(
        commandStatus,
        "Komennon onnistumista ei voitu vahvistaa. Tarkista tila.",
        "error"
      );

      console.warn("Rantasaunan komento epäonnistui:", error);

    } finally {
      commandVersion++;
      sendingCommand = false;
      updateButtons();
    }
  }

  // Automatic frost protection buttons

  enableAutomatic.addEventListener("click", () => {
    sendCommand(
      "/api/ranta/frost-protection",
      { automatic_enabled: true },
      "Automaattinen jäätymissuoja otettu käyttöön."
    );
  });

  disableAutomatic.addEventListener("click", () => {
    const confirmed = window.confirm(
      "Haluatko varmasti poistaa automaattisen jäätymissuojan käytöstä?"
    );

    if (!confirmed) return;

    sendCommand(
      "/api/ranta/frost-protection",
      { automatic_enabled: false },
      "Automaattinen jäätymissuoja poistettu käytöstä."
    );
  });

  // Remote heating buttons

  requestHeat.addEventListener("click", () => {
    sendCommand(
      "/api/ranta/pipe-heater",
      { remote_requested: true },
      "Etälämmitys aktivoitu onnistuneesti."
    );
  });

  returnToAuto.addEventListener("click", () => {
    sendCommand(
      "/api/ranta/pipe-heater",
      { remote_requested: false },
      "Etälämmitys poistettu käytöstä."
    );
  });

  // Refresh measurements

  async function refreshRanta() {
    const version = commandVersion;

    try {
      const response = await fetch(
        "/api/latest?sauna=ranta",
        {
          cache: "no-store",
          signal: AbortSignal.timeout(5000),
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reading = await response.json();

      if (!sendingCommand && version === commandVersion) {
        showFrostProtection(reading.frost_protection);
      }

      if (reading.id == null) {
        temperature.textContent = "—";
        humidity.textContent = "—";
        timestamp.textContent = "—";

        showValue(
          status,
          "Rantasaunalta ei ole vielä tallennettuja mittauksia.",
          "warning"
        );

        return;
      }

      if (
        reading.sauna_id !== "ranta" ||
        !Number.isFinite(reading.temperature) ||
        !Number.isFinite(reading.humidity) ||
        typeof reading.timestamp !== "string"
      ) {
        throw new Error("Virheellinen Rantasaunan mittaus");
      }

      const savedAt = Date.parse(
        reading.timestamp.replace(" ", "T") + "Z"
      );

      if (!Number.isFinite(savedAt)) {
        throw new Error("Virheellinen mittausaika");
      }

      temperature.textContent =
        `${numberFormat.format(reading.temperature)} °C`;

      humidity.textContent =
        `${numberFormat.format(reading.humidity)} %`;

      timestamp.textContent = reading.timestamp;

      if (Date.now() - savedAt > 15_000) {
        showValue(
          status,
          "Mittaus on vanhentunut – uutta dataa ei ole tallentunut.",
          "warning"
        );
      } else {
        showValue(
          status,
          reading.mode === "simulation"
            ? "Simuloitu mittaus"
            : "Tuore mittaus",
          "success"
        );
      }

    } catch (error) {
      showValue(
        status,
        "Mittauksia ei saatu haettua. Näkyvät lukemat voivat olla vanhoja.",
        "error"
      );

      if (!sendingCommand && version === commandVersion) {
        showFrostProtection(null);
      }

      console.warn(
        "Rantasaunan mittaushaku epäonnistui:",
        error
      );

    } finally {
      setTimeout(refreshRanta, 3000);
    }
  }

  updateButtons();
  refreshRanta();
})();