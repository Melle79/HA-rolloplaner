"""MQTT Discovery: der Rolloplaner als Gerät mit Entitäten in Home Assistant.

Feste Entitäten für den Gesamtzustand, Schalter für die einzelnen Funktionen
und je Raum einen Sensor mit Zielstellung und Begründung – dazu je Raum einen
Schalter.

Die Schalter sind der Kern: Sie treten an die Stelle der neun
``input_boolean``-Helfer, die bisher im Dashboard standen. Und sie sind ein
echter Fortschritt gegenüber diesen: Ein Helfer war nur eine **Bedingung** in
einer Automation, die zu ihrer Uhrzeit lief. Wer ihn umlegte, bewegte nie ein
Rollo – es passierte erst am nächsten Tag etwas, oder auch gar nichts. Diese
Schalter dagegen sind der Zustand selbst.
"""
from __future__ import annotations

import json
from datetime import datetime
import logging
import re
import sprache
import threading

import paho.mqtt.client as mqtt

from version import VERSION

_LOGGER = logging.getLogger(__name__)

DISCOVERY_PREFIX = "homeassistant"
BASE_TOPIC = "rolloplaner"
AVAILABILITY_TOPIC = f"{BASE_TOPIC}/availability"
COMMAND_TOPIC = f"{BASE_TOPIC}/cmd"
SCHALTER_TOPIC = f"{BASE_TOPIC}/schalter"      # …/<key>/set
ROLLO_TOPIC = f"{BASE_TOPIC}/rollo"            # …/<entity_id>/set
HITZE_TOPIC = f"{BASE_TOPIC}/hitzeschutz"      # …/<entity_id>/set
PLAN_TOPIC = f"{BASE_TOPIC}/plan"              # …/<id>/set
EIGEN_TOPIC = f"{BASE_TOPIC}/eigen"            # …/<id>/set – die eigenen Schalter
DEVICE_ID = "rolloplaner"

# (component, key, Anzeigename, Icon, Einheit, device_class)
GRUND_ENTITAETEN = [
    ("sensor", "status", "Rolloplaner Status", "mdi:window-shutter", None, None),
    ("binary_sensor", "trockenlauf", "Rollos Trockenlauf", "mdi:test-tube", None, None),
    ("binary_sensor", "rauchsperre", "Rollos Rauchsperre", "mdi:smoke-detector-variant-alert",
     None, "safety"),
    ("binary_sensor", "fluchtweg_offen", "Rollos Fluchtweg offen", "mdi:fire-alert",
     None, "safety"),
    ("binary_sensor", "stoerung", "Rollos Störung", "mdi:window-shutter-alert",
     None, "problem"),
    ("sensor", "stoerungen", "Rollos mit Störung", "mdi:alert-circle", None, None),
    ("sensor", "naechster_wechsel", "Rollos nächster Wechsel", "mdi:clock-outline",
     None, None),
]

# Die Funktionsschalter – genau das, was die Karte ein- und ausschaltet.
# (key, Anzeigename, Icon)
SCHALTER = [
    ("automatik", "Rollos Automatik", "mdi:home-automation"),
    ("beschattung", "Rollos Hitzeschutz", "mdi:sun-thermometer"),
    ("urlaubssimulation", "Rollos Urlaubssimulation", "mdi:shield-home"),
    ("fluchtweg", "Rollos Fluchtweg-Freigabe", "mdi:fire-alert"),
    ("trockenlauf_schalter", "Rollos Trockenlauf schalten", "mdi:test-tube"),
]


def _uhrzeit(iso: str | None) -> str | None:
    """Aus einem Zeitstempel die reine Uhrzeit – mehr passt nicht in eine Kachel."""
    if not iso:
        return None
    try:
        return datetime.fromisoformat(str(iso)).strftime("%H:%M")
    except ValueError:
        return None


def _slug(text: str) -> str:
    text = (text.lower()
            .replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss"))
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "raum"


class Publisher:
    """MQTT-Verbindung, Discovery und Zustandsmeldungen."""

    def __init__(self, host: str, port: int, username: str | None, password: str | None):
        self.connected = threading.Event()
        self.on_ready = None
        self.on_command = None
        self.on_schalter = None      # (key, an: bool)
        self.on_rollo = None         # (entity_id, an: bool)
        self.on_hitzeschutz = None   # (entity_id, an: bool)
        self.on_plan = None          # (plan_id, an: bool)
        self.on_eigen = None         # (schalter_id, wert: str)
        self._bekannte_eigene: set[str] = set()
        self._bekannte_rollos: set[str] = set()
        self._bekannte_plaene: set[str] = set()
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                   client_id="rolloplaner")
        if username:
            self._client.username_pw_set(username, password or "")
        self._client.will_set(AVAILABILITY_TOPIC, "offline", retain=True)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._host = host
        self._port = port

    def start(self) -> None:
        try:
            self._client.connect_async(self._host, self._port, keepalive=60)
            self._client.loop_start()
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("MQTT-Verbindung fehlgeschlagen: %s", err)

    def stop(self) -> None:
        try:
            self._client.publish(AVAILABILITY_TOPIC, "offline", retain=True)
            self._client.loop_stop()
            self._client.disconnect()
        except Exception:  # noqa: BLE001
            pass

    def _publish(self, topic: str, payload: str) -> None:
        self._client.publish(topic, payload, qos=1, retain=True)

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code == 0:
            _LOGGER.info("Mit MQTT-Broker verbunden")
            client.publish(AVAILABILITY_TOPIC, "online", qos=1, retain=True)
            client.subscribe(COMMAND_TOPIC, qos=1)
            client.subscribe(f"{SCHALTER_TOPIC}/+/set", qos=1)
            client.subscribe(f"{ROLLO_TOPIC}/+/set", qos=1)
            client.subscribe(f"{HITZE_TOPIC}/+/set", qos=1)
            client.subscribe(f"{PLAN_TOPIC}/+/set", qos=1)
            client.subscribe(f"{EIGEN_TOPIC}/+/set", qos=1)
            self.connected.set()
            if self.on_ready is not None:
                try:
                    self.on_ready()
                except Exception as err:  # noqa: BLE001
                    _LOGGER.error("Fehler nach Verbindungsaufbau: %s", err)
        else:
            _LOGGER.error("MQTT-Verbindung abgelehnt: %s", reason_code)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties) -> None:
        _LOGGER.warning("MQTT-Verbindung getrennt (%s)", reason_code)
        self.connected.clear()

    def _on_message(self, client, userdata, msg) -> None:
        try:
            nutzlast = msg.payload.decode("utf-8").strip()
        except UnicodeDecodeError:
            return
        teile = msg.topic.split("/")

        if msg.topic.startswith(f"{SCHALTER_TOPIC}/") and self.on_schalter is not None:
            self._sicher(self.on_schalter, teile[-2], nutzlast.upper() == "ON")
            return
        if msg.topic.startswith(f"{HITZE_TOPIC}/") and self.on_hitzeschutz is not None:
            self._sicher(self.on_hitzeschutz, teile[-2], nutzlast.upper() == "ON")
            return
        if msg.topic.startswith(f"{ROLLO_TOPIC}/") and self.on_rollo is not None:
            self._sicher(self.on_rollo, teile[-2], nutzlast.upper() == "ON")
            return
        if msg.topic.startswith(f"{PLAN_TOPIC}/") and self.on_plan is not None:
            self._sicher(self.on_plan, teile[-2], nutzlast.upper() == "ON")
            return
        if msg.topic.startswith(f"{EIGEN_TOPIC}/") and self.on_eigen is not None:
            # Die Nutzlast bleibt, wie sie kommt: Bei einem Schalter ist es
            # ON/OFF, bei einer Auswahl der Name der Stellung.
            self._sicher(self.on_eigen, teile[-2], nutzlast)
            return
        if msg.topic != COMMAND_TOPIC or self.on_command is None:
            return
        try:
            payload = json.loads(nutzlast)
        except json.JSONDecodeError as err:
            _LOGGER.warning("Ungültiger Befehl: %s", err)
            return
        self._sicher(self.on_command, payload)

    @staticmethod
    def _sicher(fn, *args) -> None:
        try:
            fn(*args)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Befehl konnte nicht ausgeführt werden: %s", err)

    # ---------------------------------------------------------- Discovery ----

    def _device(self) -> dict:
        return {
            "identifiers": [DEVICE_ID],
            "name": "Rolloplaner",
            "manufacturer": "Rolloplaner Add-on",
            "model": "Rollladensteuerung nach Zeit und Sonne",
            "sw_version": VERSION,
        }

    def rollo_schluessel(self, rollos: list[dict] | None) -> list[str]:
        return [_slug(r["entity_id"].split(".", 1)[-1]) for r in rollos or []]

    def plan_schluessel(self, plaene: list[dict] | None) -> list[str]:
        return [p["id"] for p in plaene or []]

    def entferne_rollos(self, schluessel: list[str]) -> None:
        """Entitäten weggefallener Rollos aus Home Assistant nehmen.

        Ohne das bliebe nach jedem Entfernen eine Karteileiche stehen: Die
        Discovery-Nachricht ist „retained“, also überlebt sie das Add-on und
        wird beim nächsten Start von Home Assistant wieder eingelesen.
        """
        for key in schluessel:
            self._publish(f"{DISCOVERY_PREFIX}/sensor/{DEVICE_ID}/rollo_{key}/config", "")
            self._publish(f"{DISCOVERY_PREFIX}/switch/{DEVICE_ID}/rollo_{key}_an/config", "")
            self._publish(
                f"{DISCOVERY_PREFIX}/switch/{DEVICE_ID}/rollo_{key}_hitzeschutz/config", "")
            self._publish(f"{BASE_TOPIC}/rollo_{key}/state", "")
            self._publish(f"{BASE_TOPIC}/rollo_{key}/attributes", "")
            self._publish(f"{BASE_TOPIC}/rollo_{key}_an/state", "")
            self._publish(f"{BASE_TOPIC}/rollo_{key}_hitzeschutz/state", "")
            self._bekannte_rollos.discard(key)
        if schluessel:
            _LOGGER.info("Rollos entfernt: %s", ", ".join(schluessel))

    def entferne_plaene(self, ids: list[str]) -> None:
        for kennung in ids:
            self._publish(f"{DISCOVERY_PREFIX}/switch/{DEVICE_ID}/plan_{kennung}/config", "")
            self._publish(f"{BASE_TOPIC}/plan_{kennung}/state", "")
            self._bekannte_plaene.discard(kennung)
        if ids:
            _LOGGER.info("Zeitpläne entfernt: %s", ", ".join(ids))

    def eigene_schluessel(self, schalter: list[dict] | None) -> list[str]:
        return [s["id"] for s in schalter or []]

    def entferne_eigene(self, ids: list[str]) -> None:
        """Entitäten gelöschter eigener Schalter aus Home Assistant nehmen."""
        for kennung in ids:
            for component in ("switch", "select"):
                self._publish(
                    f"{DISCOVERY_PREFIX}/{component}/{DEVICE_ID}/schalter_{kennung}/config",
                    "")
            self._publish(f"{BASE_TOPIC}/schalter_{kennung}/state", "")
            self._bekannte_eigene.discard(kennung)
        if ids:
            _LOGGER.info("Eigene Schalter entfernt: %s", ", ".join(ids))

    def publish_eigene(self, schalter: list[dict] | None, zustaende: dict) -> None:
        """Die eigenen Schalter des Planers als Entitäten anmelden.

        Ein Add-on, das fremde Helfer voraussetzt, ist nach einer
        Neuinstallation nutzlos – dort gibt es keine. Diese hier gehören dem
        Planer: Er legt sie an, kennt ihren Stand und räumt sie wieder ab.
        """
        device = self._device()
        for eintrag in schalter or []:
            kennung = eintrag["id"]
            key = f"schalter_{kennung}"
            self._bekannte_eigene.add(kennung)
            gemeinsam = {
                "name": eintrag["name"],
                # Die unique_id hängt an der ID, nicht am Namen: Ein
                # umbenannter Schalter behält damit seine Entität, statt als
                # neue aufzutauchen und die alte als Karteileiche zu
                # hinterlassen.
                "unique_id": f"{DEVICE_ID}_{key}",
                "state_topic": f"{BASE_TOPIC}/{key}/state",
                "command_topic": f"{EIGEN_TOPIC}/{kennung}/set",
                "availability_topic": AVAILABILITY_TOPIC,
                "icon": eintrag.get("icon") or "mdi:window-shutter-cog",
                "device": device,
            }
            if eintrag["art"] == "auswahl":
                gemeinsam["options"] = eintrag["optionen"]
                gemeinsam["default_entity_id"] = f"select.{DEVICE_ID}_{_slug(eintrag['name'])}"
                self._publish(f"{DISCOVERY_PREFIX}/select/{DEVICE_ID}/{key}/config",
                              json.dumps(gemeinsam))
            else:
                gemeinsam["default_entity_id"] = f"switch.{DEVICE_ID}_{_slug(eintrag['name'])}"
                # Ein MQTT-Switch erwartet von Haus aus „ON“/„OFF“ in
                # Großbuchstaben. Der Planer führt seine Zustände klein – ohne
                # diese vier Zeilen steht jeder eigene Schalter in Home
                # Assistant auf „unknown“, weil dort niemand „on“ erkennt.
                gemeinsam.update({"payload_on": "on", "payload_off": "off",
                                  "state_on": "on", "state_off": "off"})
                self._publish(f"{DISCOVERY_PREFIX}/switch/{DEVICE_ID}/{key}/config",
                              json.dumps(gemeinsam))
            wert = zustaende.get(kennung, eintrag["vorgabe"])
            self._publish(f"{BASE_TOPIC}/{key}/state", str(wert))
        if schalter:
            _LOGGER.info("Eigene Schalter veröffentlicht (%d)", len(schalter))

    def publish_eigenen_zustand(self, kennung: str, wert: str) -> None:
        self._publish(f"{BASE_TOPIC}/schalter_{kennung}/state", str(wert))

    def publish_discovery(self, rollos: list[dict] | None = None,
                          plaene: list[dict] | None = None,
                          namen: dict | None = None) -> None:
        device = self._device()
        namen = namen or {}
        for component, key, name, icon, einheit, klasse in GRUND_ENTITAETEN:
            payload = {
                "name": name,
                "unique_id": f"{DEVICE_ID}_{key}",
                "default_entity_id": f"{component}.{DEVICE_ID}_{key}",
                "state_topic": f"{BASE_TOPIC}/{key}/state",
                "json_attributes_topic": f"{BASE_TOPIC}/{key}/attributes",
                "availability_topic": AVAILABILITY_TOPIC,
                "icon": icon,
                "device": device,
            }
            if einheit:
                payload["unit_of_measurement"] = einheit
            if klasse:
                payload["device_class"] = klasse
            self._publish(f"{DISCOVERY_PREFIX}/{component}/{DEVICE_ID}/{key}/config",
                          json.dumps(payload))

        for key, name, icon in SCHALTER:
            self._publish(f"{DISCOVERY_PREFIX}/switch/{DEVICE_ID}/{key}/config",
                          json.dumps({
                              "name": name,
                              "unique_id": f"{DEVICE_ID}_{key}",
                              "default_entity_id": f"switch.{DEVICE_ID}_{key}",
                              "state_topic": f"{BASE_TOPIC}/{key}/state",
                              "command_topic": f"{SCHALTER_TOPIC}/{key}/set",
                              "json_attributes_topic": f"{BASE_TOPIC}/{key}/attributes",
                              "availability_topic": AVAILABILITY_TOPIC,
                              "payload_on": "ON", "payload_off": "OFF",
                              "icon": icon,
                              "device": device,
                          }))

        # Je Rollo ein Sensor mit der Zielstellung und ein Schalter für seine
        # Automatik. Beides hängt an der Entität, nicht am Namen: Wer das Rollo
        # in Home Assistant umbenennt, hat immer noch dasselbe Rollo.
        for rollo in rollos or []:
            kurz = _slug(rollo["entity_id"].split(".", 1)[-1])
            key = f"rollo_{kurz}"
            self._bekannte_rollos.add(kurz)
            anzeige = namen.get(rollo["entity_id"]) or rollo.get("name") or kurz
            self._publish(f"{DISCOVERY_PREFIX}/sensor/{DEVICE_ID}/{key}/config",
                          json.dumps({
                              "name": anzeige,
                              "unique_id": f"{DEVICE_ID}_{key}",
                              "default_entity_id": f"sensor.{DEVICE_ID}_{key}",
                              "state_topic": f"{BASE_TOPIC}/{key}/state",
                              "json_attributes_topic": f"{BASE_TOPIC}/{key}/attributes",
                              "availability_topic": AVAILABILITY_TOPIC,
                              "unit_of_measurement": "%",
                              "icon": "mdi:window-shutter",
                              "device": device,
                          }))
            # Der Hitzeschutz je Rollo. Bisher gab es ihn nur als Haken im
            # Add-on und als einen Schalter fürs ganze Haus – wer ihn für ein
            # einzelnes Fenster abstellen wollte, musste die Konfiguration
            # öffnen. Das ist keine Bedienung, das ist Wartung.
            self._publish(f"{DISCOVERY_PREFIX}/switch/{DEVICE_ID}/{key}_hitzeschutz/config",
                          json.dumps({
                              "name": f"{anzeige} Hitzeschutz",
                              "unique_id": f"{DEVICE_ID}_{key}_hitzeschutz",
                              "default_entity_id": f"switch.{DEVICE_ID}_{key}_hitzeschutz",
                              "state_topic": f"{BASE_TOPIC}/{key}_hitzeschutz/state",
                              "command_topic": f"{HITZE_TOPIC}/{rollo['entity_id']}/set",
                              "availability_topic": AVAILABILITY_TOPIC,
                              "payload_on": "ON", "payload_off": "OFF",
                              "icon": "mdi:sun-thermometer",
                              "device": device,
                          }))
            self._publish(f"{DISCOVERY_PREFIX}/switch/{DEVICE_ID}/{key}_an/config",
                          json.dumps({
                              "name": f"{anzeige} Automatik",
                              "unique_id": f"{DEVICE_ID}_{key}_an",
                              "default_entity_id": f"switch.{DEVICE_ID}_{key}_an",
                              "state_topic": f"{BASE_TOPIC}/{key}_an/state",
                              "command_topic": f"{ROLLO_TOPIC}/{rollo['entity_id']}/set",
                              "availability_topic": AVAILABILITY_TOPIC,
                              "payload_on": "ON", "payload_off": "OFF",
                              "icon": "mdi:window-shutter-auto",
                              "device": device,
                          }))

        # Je Zeitplan ein Schalter – damit lässt sich „Erdgeschoss“ auf einmal
        # stilllegen, ohne jedes Rollo einzeln anzufassen.
        for plan in plaene or []:
            kennung = plan["id"]
            self._bekannte_plaene.add(kennung)
            self._publish(f"{DISCOVERY_PREFIX}/switch/{DEVICE_ID}/plan_{kennung}/config",
                          json.dumps({
                              "name": f"Zeitplan {plan['name']}",
                              "unique_id": f"{DEVICE_ID}_plan_{kennung}",
                              "default_entity_id":
                                  f"switch.{DEVICE_ID}_plan_{_slug(plan['name'])}",
                              "state_topic": f"{BASE_TOPIC}/plan_{kennung}/state",
                              "command_topic": f"{PLAN_TOPIC}/{kennung}/set",
                              "availability_topic": AVAILABILITY_TOPIC,
                              "payload_on": "ON", "payload_off": "OFF",
                              "icon": "mdi:calendar-clock",
                              "device": device,
                          }))
        _LOGGER.info("Discovery veröffentlicht (%d Rollos, %d Zeitpläne)",
                     len(rollos or []), len(plaene or []))

    # ------------------------------------------------------------ Zustand ----

    def publish_status(self, bericht: dict, config: dict | None = None) -> None:
        """Den Bericht eines Regeltakts nach MQTT spiegeln."""
        if not self.connected.is_set():
            return
        rollos = bericht.get("rollos") or []
        einstellungen = (config or {}).get("einstellungen") or {}
        # Ist die Zählweise umgedreht, gilt das auch für den Sensorwert – sonst
        # zeigte die Karte etwas anderes als die Entität dahinter. Der Wert in
        # der Zählweise von Home Assistant kommt als Attribut mit, damit
        # Automationen eine verlässliche Größe haben.
        invertiert = bool(einstellungen.get("prozent_invertiert"))

        def zeige(wert):
            if wert is None:
                return None
            return 100 - int(wert) if invertiert else int(wert)

        if bericht.get("rauch"):
            # Im Alarm ist die Auskunft, die zählt, nicht „der Planer hält
            # still“, sondern ob der Fluchtweg offen ist.
            status = sprache.t("lage.fluchtweg_offen"
                               if (bericht.get("fluchtweg") or {}).get("aktiv")
                               else "lage.rauchsperre")
        elif not bericht.get("automatik"):
            status = sprache.t("lage.automatik_aus")
        elif bericht.get("trockenlauf"):
            status = sprache.t("lage.trockenlauf")
        elif bericht.get("urlaub"):
            status = sprache.t("lage.urlaub")
        else:
            beschattet = [r for r in rollos if r.get("zustand") == "beschattung"]
            # „aktiv" hieß hier immer „der Planer fährt es" – gelesen wurde es
            # als „das Rollo funktioniert". Ein Rollo mit abgeschalteter
            # Automatik ist aber nicht kaputt, es wird nur nicht gefahren.
            mit = [r for r in rollos if r.get("zustand") not in ("aus", "gesperrt")]
            status = (sprache.t("lage.beschattet", n=len(beschattet)) if beschattet
                      else sprache.t("lage.alle_mit_automatik")
                      if len(mit) == len(rollos)
                      else sprache.t("lage.mit_automatik", n=len(mit),
                                     gesamt=len(rollos)))

        sonne = bericht.get("sonne") or {}
        self._zustand("status", status, {
            "zeit": bericht.get("zeit"),
            "automatik": bericht.get("automatik"),
            "trockenlauf": bericht.get("trockenlauf"),
            "urlaub": bericht.get("urlaub"),
            "schulfrei": bericht.get("schulfrei"),
            "schulfrei_morgen": bericht.get("schulfrei_morgen"),
            "aussentemperatur": bericht.get("aussen"),
            "sonnenaufgang": sonne.get("aufgang"),
            "sonnenuntergang": sonne.get("untergang"),
            "sonnenhoehe": sonne.get("elevation"),
            "sonnenrichtung": sonne.get("azimut"),
            "prozent_invertiert": invertiert,
            # Die Schalter, die mehr als ein Rollo betreffen – sie gehören in
            # der Karte nach oben und nicht in jede Kachel einzeln.
            "freigaben": [e for e in (bericht.get("freigaben") or []) if e["geteilt"]],
            "plaene": bericht.get("plaene") or [],
            "rollos": {r["name"]: r.get("zustand") for r in rollos},
        })
        self._zustand("trockenlauf", "ON" if bericht.get("trockenlauf") else "OFF", {})
        self._zustand("rauchsperre", "ON" if bericht.get("rauch") else "OFF",
                      {"grund": bericht.get("rauch_grund") or ""})
        freigabe = bericht.get("fluchtweg") or {}
        self._zustand("fluchtweg_offen", "ON" if freigabe.get("aktiv") else "OFF",
                      {"grund": bericht.get("rauch_grund") or "",
                       "akut": bool(freigabe.get("akut")),
                       "seit": freigabe.get("seit") or "",
                       "geoeffnet": freigabe.get("gefahren") or [],
                       "stand_schon_offen": freigabe.get("offen") or [],
                       "nicht_erreichbar": freigabe.get("fehlt") or [],
                       "aufgegeben": freigabe.get("aufgegeben") or [],
                       "ausgenommen": freigabe.get("uebergangen") or []})

        stoerungen = bericht.get("stoerungen") or []
        schwer = [s for s in stoerungen if s.get("schwere") == "fehler"]
        self._zustand("stoerung", "ON" if stoerungen else "OFF",
                      {"anzahl": len(stoerungen), "ausgefallen": len(schwer),
                       "meldungen": [s["text"] for s in stoerungen]})
        self._zustand("stoerungen", str(len(schwer)),
                      {"geraete": [s["entity_id"] for s in schwer],
                       "meldungen": [s["text"] for s in stoerungen]})

        # Der nächste Wechsel im ganzen Haus – als fertiger Anzeigetext. In
        # Lovelace-Templates gibt es kein `strftime`, und die Zeitrechnerei
        # dort ist eine Fehlerquelle, die im Zweifel die Karte lahmlegt.
        naechste = [r for r in rollos if r.get("naechster_zeitpunkt")]
        naechste.sort(key=lambda r: r["naechster_zeitpunkt"])
        if naechste:
            erster = naechste[0]
            stellung = erster.get("naechste_stellung")
            was = ("auf" if stellung is not None and stellung >= 100
                   else "zu" if stellung == 0
                   else f"{zeige(stellung)} %")
            self._zustand("naechster_wechsel",
                          f"{erster['name']} {was} um {erster.get('naechste_uhrzeit')} Uhr",
                          {"rollo": erster["name"],
                           "uhrzeit": erster.get("naechste_uhrzeit"),
                           "zeitpunkt": erster.get("naechster_zeitpunkt"),
                           "stellung": zeige(stellung),
                           "alle": [{"rollo": r["name"], "uhrzeit": r.get("naechste_uhrzeit"),
                                     "stellung": zeige(r.get("naechste_stellung"))}
                                    for r in naechste[:14]]})
        else:
            self._zustand("naechster_wechsel", sprache.t("lage.kein_wechsel"), {})

        # Die Funktionsschalter spiegeln die Einstellungen wider.
        self._zustand("automatik", "ON" if einstellungen.get("automatik") else "OFF", {})
        self._zustand("beschattung",
                      "ON" if (einstellungen.get("beschattung") or {}).get("aktiv") else "OFF",
                      {"beschattete_rollos": [r["name"] for r in rollos
                                              if r.get("beschattet")]})
        self._zustand("urlaubssimulation",
                      "ON" if (einstellungen.get("urlaub") or {}).get("modus") == "simulation"
                      else "OFF",
                      {"modus": (einstellungen.get("urlaub") or {}).get("modus")})
        self._zustand("trockenlauf_schalter",
                      "ON" if einstellungen.get("trockenlauf") else "OFF", {})
        self._zustand("fluchtweg",
                      "ON" if (einstellungen.get("rauchsperre") or {}).get("fluchtweg", True)
                      else "OFF", {})

        for rollo in rollos:
            kurz = _slug(rollo["entity_id"].split(".", 1)[-1])
            key = f"rollo_{kurz}"
            ziel = rollo.get("ziel")
            # Ohne Ziel zeigt der Sensor, **wo das Rollo steht**. Das ist bei
            # einem Rollo ohne Zeitplan die einzige sinnvolle Auskunft – und es
            # vermeidet den Textwert „unknown“, mit dem Home Assistant einen
            # Sensor mit Einheit gar nicht erst anlegt: Er stand dann als
            # „nicht verfügbar“ da, obwohl mit ihm nichts war.
            angezeigt = zeige(ziel if ziel is not None else rollo.get("ist"))
            self._zustand(key, str(angezeigt) if angezeigt is not None else "unknown", {
                "cover": rollo["entity_id"],
                "raum": rollo.get("raum") or "",
                "gruppe": rollo.get("gruppe") or "",
                "gruppe_platz": rollo.get("gruppe_platz", 999),
                "art": rollo.get("art") or "fenster",
                "stellung_ha": ziel,
                "ist": rollo.get("ist"),
                "prozent_invertiert": invertiert,
                "zustand": rollo.get("zustand"),
                "begruendung": rollo.get("begruendung"),
                # Dieselbe Auskunft in jeder Sprache: Die Karte spricht die
                # ihres Betrachters, das Add-on die eigene. Ohne das stünde in
                # einer englischen Karte ein deutscher Satz.
                "begruendungen": rollo.get("begruendungen") or {},
                "naechste_punkte": rollo.get("naechste_punkte") or {},
                "beschattet": rollo.get("beschattet", False),
                "fenster_offen": rollo.get("fenster_offen") or [],
                "zeitplan": rollo.get("plan") or "",
                # Wann der geltende Schaltpunkt fällig war. Ohne diese Angabe
                # liest sich die Begründung wie ein Vorhaben statt wie ein
                # Vorgang: „zu um Sonnenuntergang … dann offen um 10:00" klingt
                # nach zwei Terminen, von denen der erste längst vorbei ist.
                "zuletzt_uhrzeit": _uhrzeit(rollo.get("punkt_zeit")),
                "naechste_uhrzeit": rollo.get("naechste_uhrzeit"),
                "naechste_stellung": zeige(rollo.get("naechste_stellung")),
                "naechste_stellung_ha": rollo.get("naechste_stellung"),
                "naechster_punkt": rollo.get("naechster_punkt"),
                # Nur die Schalter, die allein dieses Rollo betreffen. Die
                # geteilten stehen einmal oben, im Status.
                "helfer": [h for h in (rollo.get("helfer") or [])
                           if not h.get("geteilt")],
                "hinweis": rollo.get("hinweis") or "",
            })
            self._zustand(f"{key}_an",
                          "OFF" if rollo.get("zustand") == "aus" else "ON", {})
            self._zustand(f"{key}_hitzeschutz",
                          "ON" if rollo.get("hitzeschutz") else "OFF",
                          {"ausrichtung": rollo.get("ausrichtung")})

        for plan in bericht.get("plaene") or []:
            self._zustand(f"plan_{plan['id']}", "ON" if plan.get("aktiv") else "OFF", {})

    def _zustand(self, key: str, state: str, attributes: dict) -> None:
        self._publish(f"{BASE_TOPIC}/{key}/state", state)
        self._publish(f"{BASE_TOPIC}/{key}/attributes",
                      json.dumps(attributes, ensure_ascii=False))

    def remove_all(self) -> None:
        """Alle Entitäten wieder aus Home Assistant entfernen."""
        for component, key, *_ in GRUND_ENTITAETEN:
            self._publish(f"{DISCOVERY_PREFIX}/{component}/{DEVICE_ID}/{key}/config", "")
            self._publish(f"{BASE_TOPIC}/{key}/state", "")
        for key, *_ in SCHALTER:
            self._publish(f"{DISCOVERY_PREFIX}/switch/{DEVICE_ID}/{key}/config", "")
            self._publish(f"{BASE_TOPIC}/{key}/state", "")
        self.entferne_rollos(list(self._bekannte_rollos))
        self.entferne_plaene(list(self._bekannte_plaene))
        self.entferne_eigene(list(self._bekannte_eigene))
        _LOGGER.info("Entitäten aus MQTT entfernt")
