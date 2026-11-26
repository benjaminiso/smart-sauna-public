( TL;DR: 
1. Kopioi .env.example → .env
2. Täytä omat tunnukset
3. lataa .env jokaiseen terminaaliin (set -a; . ./.env; set +a)
4. Käynnistä palvelut järjestyksessä 1→6 )



Kopioi asetuspohja, täytä paikalliset tunnukset, lataa .env jokaisessa terminaalissa ja käynnistä palvelut tässä järjestyksessä. Älä kopioi oikeita tunnuksia ohjeeseen.

Kun Mosquitto on käynnissä ja projektin riippuvuudet on asennettu, aja jokaisessa uudessa Debian-terminaalissa projektin juuressa:

set -a
. ./.env
set +a

Tämä lataa oman .env-tiedostosi arvot terminaalista käynnistyville ohjelmille. Lataa näin vain itse luomasi tai tarkistamasi tiedosto, koska Bash tulkitsee sen komentotiedostona. Jos käytät Python-virtuaaliympäristöä, aktivoi se Python-terminaaleissa.

Käynnistä palvelut omissa terminaaleissaan:
Järjestys	Komento
1			node web/server.js
2			python3 mqtt-server/ingestor.py
3			python3 mqtt-server/profile_bridge.py
4			python3 mqtt-server/readiness.py
5			python3 mqtt-server/simulator.py
6			python3 opla-controller/opla_simulator.py

Web-palvelin käynnistetään ensin, koska se alustaa sauna_state-taulun.