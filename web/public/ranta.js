(() => {
  const temperature = document.getElementById("rantaTemperature");
  const humidity = document.getElementById("rantaHumidity");
  const timestamp = document.getElementById("rantaTimestamp");
  const status = document.getElementById("rantaStatus");
  const heater = document.getElementById("rantaHeater");
  const frostAlarm = document.getElementById("rantaFrostAlarm");
const autoRequest = document.getElementById("rantaAutoRequest");
const remoteRequest = document.getElementById("rantaRemoteRequest");
const requestHeat = document.getElementById("rantaRequestHeat");
const returnToAuto = document.getElementById("rantaReturnToAuto");
const commandStatus = document.getElementById("rantaCommandStatus");

let sendingCommand = false;

function yesNo(value) {
  return value === true ? "Kyllä" : value === false ? "Ei" : "Ei tiedossa";
}

function showFrostProtection(protection) {
  autoRequest.textContent = yesNo(protection?.heating_requested);
  remoteRequest.textContent = yesNo(protection?.remote_requested);

  heater.textContent = protection?.heater_on === true ? "PÄÄLLÄ"
    : protection?.heater_on === false ? "POIS"
    : "Tila ei tiedossa";

  frostAlarm.textContent = protection?.frost_alarm === true ? "PAKKASHÄLYTYS"
    : protection?.frost_alarm === false ? "Ei hälytystä"
    : "Ei arvioitavissa";
}

async function setRemoteRequest(requested) {
  if (sendingCommand) return;

  sendingCommand = true;
  requestHeat.disabled = true;
  returnToAuto.disabled = true;
  commandStatus.textContent = "Lähetetään pyyntöä…";

  try {
    const response = await fetch("/api/ranta/pipe-heater", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ remote_requested: requested }),
      signal: AbortSignal.timeout(5000),
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    commandStatus.textContent = requested
      ? "Palvelin vastaanotti etälämmityspyynnön."
      : "Etäpyyntö poistettu. Automatiikka jatkaa normaalisti.";
  } catch (error) {
    commandStatus.textContent =
      "Pyynnön vastaanottoa ei voitu vahvistaa. Tarkista etäpyynnön tila.";
  } finally {
    sendingCommand = false;
    requestHeat.disabled = false;
    returnToAuto.disabled = false;
  }
}

requestHeat.addEventListener("click", () => setRemoteRequest(true));
returnToAuto.addEventListener("click", () => setRemoteRequest(false));

  const numberFormat = new Intl.NumberFormat("fi-FI", {
    maximumFractionDigits: 1,
  });

  function setStatus(message) {
    if (status.textContent !== message) {
      status.textContent = message;
    }
  }

  async function refreshRanta() {
    try {
      const response = await fetch("/api/latest?sauna=ranta", {
        cache: "no-store",
        signal: AbortSignal.timeout(5000),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reading = await response.json();
      showFrostProtection(reading.frost_protection);

      // API palauttaa tyhjän objektin, jos mittauksia ei vielä ole.
      if (reading.id == null) {
        temperature.textContent = "—";
        humidity.textContent = "—";
        timestamp.textContent = "—";
        setStatus("Rantasaunalta ei ole vielä tallennettuja mittauksia.");
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

      // SQLite tallentaa ajan UTC:na muodossa YYYY-MM-DD HH:MM:SS.
      const savedAt = Date.parse(reading.timestamp.replace(" ", "T") + "Z");
      if (!Number.isFinite(savedAt)) {
        throw new Error("Virheellinen mittausaika");
      }

      temperature.textContent = `${numberFormat.format(reading.temperature)} °C`;
      humidity.textContent = `${numberFormat.format(reading.humidity)} %`;
      timestamp.textContent = reading.timestamp;

      if (Date.now() - savedAt > 15_000) {
        setStatus("Mittaus on vanhentunut – uutta dataa ei ole tallentunut.");
      } else {
        setStatus(
          reading.mode === "simulation" ? "Simuloitu mittaus" : "Tuore mittaus"
        );
      }
    } catch (error) {
      setStatus("Mittauksia ei saatu haettua. Näkyvät lukemat voivat olla vanhoja.");
      console.warn("Rantasaunan mittaushaku epäonnistui:", error);
      showFrostProtection();
    } finally {
      // Seuraava haku alkaa vasta edellisen päätyttyä.
      setTimeout(refreshRanta, 3000);
    }
  }

  refreshRanta();
})();