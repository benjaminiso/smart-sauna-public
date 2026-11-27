(() => {
  const location = document.getElementById("rantaWeatherLocation");
  const average = document.getElementById("rantaWeatherAverage");
  const fetched = document.getElementById("rantaWeatherFetched");
  const status = document.getElementById("rantaWeatherStatus");

  const numberFormat = new Intl.NumberFormat("fi-FI", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });

  const dateTimeFormat = new Intl.DateTimeFormat("fi-FI", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "Europe/Helsinki",
  });

  function showStatus(message) {
    if (status.textContent !== message) {
      status.textContent = message;
    }
  }

  async function refreshWeather() {
    try {
      const response = await fetch("/api/ranta/weather", {
        cache: "no-store",
        signal: AbortSignal.timeout(5000),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const weather = await response.json();
      const forecast = weather.forecast;
      const value = forecast?.average_temperature_c;
      const fetchedAt = Date.parse(forecast?.fetched_at);

      location.textContent = weather.location ?? "";
      average.textContent = Number.isFinite(value)
        ? `${numberFormat.format(value)} °C${weather.stale ? " (aiempi ennuste)" : ""}`
        : "—";
      fetched.textContent = Number.isFinite(fetchedAt)
        ? dateTimeFormat.format(fetchedAt)
        : "—";

      showStatus(
        weather.message ??
          `Keskiarvo laskettiin hakuhetkellä ${forecast?.hours_used ?? 0} ennustetunnista.`
      );
    } catch {
      showStatus(
        "Ennustetietoa ei saatu palvelimelta. Näkyvät tiedot voivat olla vanhoja."
      );
    } finally {
      setTimeout(refreshWeather, 30_000);
    }
  }

  refreshWeather();
})();