const REFRESH_INTERVAL_MS = 4 * 60 * 60 * 1000;
const RETRY_INTERVAL_MS = 10 * 60 * 1000;
const TIME_ZONE = "Europe/Helsinki";

const forecastUrl = new URL("https://api.open-meteo.com/v1/forecast");
forecastUrl.search = new URLSearchParams({
  latitude: "63.84",
  longitude: "23.13",
  hourly: "temperature_2m",
  temperature_unit: "celsius",
  forecast_days: "2",
  timeformat: "unixtime",
  timezone: "GMT",
}).toString();

const localDate = new Intl.DateTimeFormat("sv-SE", {
  timeZone: TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

let status = "waiting";
let lastForecast = null;
let nextAttemptAt = null;

function getWeather() {
  const isFromToday = lastForecast?.date === localDate.format(Date.now());

  return {
    status,
    location: "Kokkola (esimerkkipaikka)",
    timezone: TIME_ZONE,
    forecast: lastForecast,
    stale: lastForecast !== null && (status === "error" || !isFromToday),
    next_attempt_at: nextAttemptAt,
    message: status === "error"
      ? "Sääennustetta ei saatu päivitettyä."
      : status === "waiting"
        ? "Odotetaan ensimmäistä sääennustetta."
        : !isFromToday
          ? "Viimeisin ennuste on aiemmalta päivältä."
          : lastForecast.hours_used === 0
            ? "Tälle päivälle ei ole enää jäljellä ennustetunteja."
            : null,
  };
}

async function refreshWeather() {
  let delay = REFRESH_INTERVAL_MS;

  try {
    const response = await fetch(forecastUrl, {
      signal: AbortSignal.timeout(8000),
    });

    if (!response.ok) {
      throw new Error(`Open-Meteo HTTP ${response.status}`);
    }

    const data = await response.json();
    const times = data.hourly?.time;
    const temperatures = data.hourly?.temperature_2m;

    if (
      !Array.isArray(times) ||
      !Array.isArray(temperatures) ||
      times.length === 0 ||
      times.length !== temperatures.length
    ) {
      throw new Error("Ennusteen tuntitiedot puuttuvat tai ovat virheelliset.");
    }

    const now = Date.now();
    const today = localDate.format(now);
    let sum = 0;
    let count = 0;

    for (let i = 0; i < times.length; i++) {
      if (!Number.isFinite(times[i]) || !Number.isFinite(temperatures[i])) {
        continue;
      }

      const hour = times[i] * 1000;
      if (hour >= now && localDate.format(hour) === today) {
        sum += temperatures[i];
        count++;
      }
    }

    lastForecast = {
      date: today,
      fetched_at: new Date(now).toISOString(),
      hours_used: count,
      average_temperature_c: count > 0 ? Math.round((sum / count) * 10) / 10 : null,
    };
    status = "ok";
  } catch (error) {
    // Viimeisin onnistunut ennuste säilyy näkyvissä virheen jälkeen.
    status = "error";
    delay = RETRY_INTERVAL_MS;
    console.warn("Rantasaunan sääennusteen haku epäonnistui:", error.message);
  } finally {
    nextAttemptAt = new Date(Date.now() + delay).toISOString();
    setTimeout(refreshWeather, delay).unref();
  }
}

module.exports = { startWeather: refreshWeather, getWeather };