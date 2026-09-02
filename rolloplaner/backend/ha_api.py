"""Zugriff auf die Home-Assistant-API über den Supervisor-Proxy.

Alles, was das Add-on über Home Assistant weiß oder an ihm ändert, läuft hier
durch. Zwei Eigenheiten der Rollladensteuerung sind eingebaut:

* Gefahren wird **jedes Rollo einzeln**. Ein Sammelaufruf scheitert an einem
  einzigen nicht erreichbaren Motor und reißt die übrigen mit – bei zehn
  Funk-Gurtwicklern ist das kein Ausnahmefall.
* Ein Rollladen, der schon steht, wo er stehen soll, wird **nicht** erneut
  angefahren. Bei einem Thermostat wäre das ein überflüssiges Datenpaket, hier
  läuft ein Motor an.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

_LOGGER = logging.getLogger(__name__)

API_BASE = "http://supervisor/core/api"
TIMEOUT = 15

# Bitmaske der Fähigkeiten einer cover-Entität (SUPPORT_SET_POSITION).
FEATURE_SET_POSITION = 4


def _token() -> str:
    return os.environ.get("SUPERVISOR_TOKEN", "")


def available() -> bool:
    return bool(_token())


def _request(method: str, path: str, payload: dict | None = None):
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        method=method,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={
            "Authorization": f"Bearer {_token()}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body) if body else None


# ---------------------------------------------------------------- lesen ----

def ist_bereit() -> bool:
    """Läuft Home Assistant, oder startet es gerade?

    Während des Starts liefert `/states` eine wachsende Teilliste. Wer darauf
    rechnet, hält die noch nicht geladenen Geräte für verschwunden – und fährt
    im schlimmsten Fall ein Dutzend Rollos, weil er ihren Stand nicht kennt.
    """
    if not available():
        return False
    try:
        config = _request("GET", "/config")
    except Exception:  # noqa: BLE001
        return False
    if not isinstance(config, dict):
        return False
    zustand = config.get("state")
    return zustand in (None, "RUNNING")


def get_states() -> list[dict]:
    """Alle Zustände auf einen Schlag – ein Aufruf je Regeltakt."""
    if not available():
        return []
    try:
        states = _request("GET", "/states")
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Zustände konnten nicht geladen werden: %s", err)
        return []
    return states if isinstance(states, list) else []


def get_state(entity_id: str) -> dict | None:
    if not available():
        return None
    try:
        data = _request("GET", f"/states/{entity_id}")
        return data if isinstance(data, dict) else None
    except urllib.error.HTTPError as err:
        if err.code != 404:
            _LOGGER.warning("Fehler beim Lesen von %s: %s", entity_id, err)
        return None
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("HA-API nicht erreichbar: %s", err)
        return None


def as_float(value) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if f == f else None  # NaN aussortieren


def position_von(zustand: dict | None) -> int | None:
    """Die Stellung eines Rollladens in Prozent, 100 = offen.

    Nicht jeder Antrieb meldet eine Stellung. Wer nur ``open``/``closed`` kennt,
    wird auf 100 beziehungsweise 0 abgebildet – sonst stünde er im Bericht
    dauerhaft als „unbekannt“ und der Planer führe ihn bei jedem Takt an.
    """
    if not zustand:
        return None
    attrs = zustand.get("attributes") or {}
    wert = as_float(attrs.get("current_position"))
    if wert is not None:
        return int(round(wert))
    if zustand.get("state") == "open":
        return 100
    if zustand.get("state") == "closed":
        return 0
    return None


def kann_position(zustand: dict | None) -> bool:
    """Nimmt dieser Antrieb eine Zwischenstellung an?"""
    if not zustand:
        return False
    merkmale = (zustand.get("attributes") or {}).get("supported_features")
    try:
        return bool(int(merkmale) & FEATURE_SET_POSITION)
    except (TypeError, ValueError):
        return False


def faehrt(zustand: dict | None) -> bool:
    return bool(zustand) and zustand.get("state") in ("opening", "closing")


# -------------------------------------------------------------- schalten ----

def set_position(entity_id: str, position: int, zustand: dict | None = None) -> bool:
    """Ein einzelnes Rollo auf eine Stellung fahren.

    Antriebe ohne Zwischenstellung bekommen ``open``/``close`` – und zwar
    gerundet: Wer 35 % verlangt und nur auf/zu kann, soll nicht versehentlich
    ganz zufahren. Ein Fehler bleibt bei diesem einen Rollo.
    """
    if not available():
        _LOGGER.warning("Kein SUPERVISOR_TOKEN – %s kann nicht gefahren werden", entity_id)
        return False
    position = max(0, min(100, int(position)))

    if zustand is not None and not kann_position(zustand):
        dienst = "open_cover" if position >= 50 else "close_cover"
        return _dienst(dienst, entity_id)
    try:
        _request("POST", "/services/cover/set_cover_position",
                 {"entity_id": entity_id, "position": position})
        _LOGGER.info("%s → %d %%", entity_id, position)
        return True
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Stellung für %s abgelehnt (%s) – versuche auf/zu", entity_id, err)

    dienst = "open_cover" if position >= 50 else "close_cover"
    return _dienst(dienst, entity_id)


def _dienst(dienst: str, entity_id: str) -> bool:
    try:
        _request("POST", f"/services/cover/{dienst}", {"entity_id": entity_id})
        _LOGGER.info("%s → %s", entity_id, dienst)
        return True
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("%s für %s fehlgeschlagen: %s", dienst, entity_id, err)
        return False


def stop(entity_id: str) -> bool:
    return _dienst("stop_cover", entity_id)


# ------------------------------------------------------------- Auswahlen ----

def cover_entities(states: list[dict] | None = None,
                   bereiche: dict | None = None) -> list[dict]:
    """Alle Rollläden für die Raumkonfiguration in der Oberfläche.

    Der Bereich kommt mit, damit die Oberfläche nach Raum vorsortieren kann.
    Bei den Rollläden ist er verlässlich gepflegt – anders als bei den
    Fenstermeldern der Heizung.
    """
    bereiche = bereiche if bereiche is not None else {}
    out = []
    for s in states if states is not None else get_states():
        eid = s.get("entity_id", "")
        if not eid.startswith("cover."):
            continue
        attrs = s.get("attributes", {}) or {}
        out.append({
            "entity_id": eid,
            "name": attrs.get("friendly_name", eid),
            "state": s.get("state"),
            "position": position_von(s),
            "bereich": bereiche.get(eid, ""),
            "device_class": attrs.get("device_class"),
            "kann_position": kann_position(s),
        })
    out.sort(key=lambda e: e["name"])
    return out


def person_entities(states: list[dict] | None = None) -> list[dict]:
    out = []
    for s in states if states is not None else get_states():
        eid = s.get("entity_id", "")
        if not eid.startswith("person."):
            continue
        attrs = s.get("attributes", {}) or {}
        out.append({
            "entity_id": eid,
            "name": attrs.get("friendly_name", eid),
            "state": s.get("state"),
            "zustand": "on" if s.get("state") == "home" else "off",
        })
    out.sort(key=lambda e: e["name"])
    return out


TEMPLATE_API = f"{API_BASE}/template"

# Wörter, an denen ein Fensterkontakt auch ohne Geräteklasse zu erkennen ist.
FENSTER_WORTE = ("fenster", "window", "kipp", "balkontür", "balkontuer",
                 "terrassentür", "terrassentuer")

# Was trotz passender Geräteklasse oder passendem Namen keiner ist. Beide
# Fallgruben stehen in dieser Installation im Weg: Die Öffnungszeiten von
# Tankstellen kommen als ``device_class: opening``, und **jeder** Rademacher-
# Gurtwickler bringt drei Diagnosemelder mit, die das Fenster im Namen führen,
# an dem sie hängen – „Rollo Fenster Luna Obstacle Detection“ ist kein Kontakt.
KEIN_KONTAKT_WORTE = ("status", "blocking", "obstacle", "sun program",
                      "sonnenprogramm", "update", "verfügbar", "battery",
                      "batterie", "signal", "calibration", "tastensperre",
                      "sommermodus", "urlaubsmodus", "offenes fenster erkannt")


def template(vorlage: str) -> str:
    """Ein Jinja-Template in Home Assistant auswerten lassen.

    Der einzige Weg, aus einem Add-on an die Bereichszuordnung zu kommen: Das
    Geräte- und Entitätenregister gibt es nur über die Websocket-API, die einem
    Add-on nicht offensteht. ``area_name()`` liefert dieselbe Auskunft.
    """
    if not available():
        return ""
    req = urllib.request.Request(
        TEMPLATE_API, method="POST",
        data=json.dumps({"template": vorlage}).encode("utf-8"),
        headers={"Authorization": f"Bearer {_token()}",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read().decode("utf-8")
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Template konnte nicht ausgewertet werden: %s", err)
        return ""


_bereich_cache: dict[tuple, tuple[float, dict]] = {}
BEREICH_CACHE_SEKUNDEN = 300


def bereiche_je_entitaet(domains: tuple[str, ...] = ("cover", "binary_sensor"),
                         hoechstalter: float = BEREICH_CACHE_SEKUNDEN) -> dict:
    """Entity-ID → Bereichsname für die angegebenen Domänen.

    Kurz zwischengespeichert: Bereiche ändern sich selten, die Oberfläche fragt
    aber alle halbe Minute nach.
    """
    import time

    gespeichert = _bereich_cache.get(domains)
    if gespeichert and time.monotonic() - gespeichert[0] < hoechstalter:
        return gespeichert[1]

    teile = [
        "{%- for s in states." + domain + " %}{{ s.entity_id }}|"
        "{{ area_name(s.entity_id) or '' }}\n{% endfor -%}"
        for domain in domains
    ]
    zuordnung = {}
    for zeile in template("".join(teile)).splitlines():
        entity_id, _, bereich = zeile.partition("|")
        if entity_id and bereich:
            zuordnung[entity_id] = bereich
    if zuordnung or gespeichert is None:
        _bereich_cache[domains] = (time.monotonic(), zuordnung)
    return zuordnung if zuordnung else (gespeichert[1] if gespeichert else {})


_etagen_cache: dict = {}


def etagen_je_entitaet(hoechstalter: float = BEREICH_CACHE_SEKUNDEN) -> dict:
    """Entity-ID → Etagenname, für die Rollos.

    Home Assistant führt seine Bereiche in Etagen. Das ist genau der Schnitt,
    nach dem in diesem Haus die Sammelautomationen gebaut waren („Rollo
    schliessen EG", „Obergeschoss schliessen"), und damit der beste Vorschlag
    für eine Obergruppe – besser als etwas, das der Planer sich ausdenkt.
    """
    import time

    gespeichert = _etagen_cache.get("cover")
    if gespeichert and time.monotonic() - gespeichert[0] < hoechstalter:
        return gespeichert[1]

    roh = template("{%- for s in states.cover %}{{ s.entity_id }}|"
                   "{{ floor_name(s.entity_id) or '' }}\n{% endfor -%}")
    zuordnung = {}
    for zeile in roh.splitlines():
        entity_id, _, etage = zeile.partition("|")
        if entity_id and etage:
            zuordnung[entity_id] = etage
    if zuordnung or gespeichert is None:
        _etagen_cache["cover"] = (time.monotonic(), zuordnung)
    return zuordnung if zuordnung else (gespeichert[1] if gespeichert else {})


def ist_fensterkontakt(entity_id: str, name: str, klasse: str | None) -> bool:
    """Fensterkontakt an Geräteklasse oder Bezeichnung erkennen.

    ``window`` und ``door`` sind eindeutig. ``opening`` ist es nicht – diese
    Klasse tragen auch Öffnungszeiten von Geschäften –, deshalb muss dort der
    Name mitspielen.
    """
    text = f"{entity_id} {name}".lower()
    if any(wort in text for wort in KEIN_KONTAKT_WORTE):
        return False
    if klasse in ("window", "door"):
        return True
    return any(wort in text for wort in FENSTER_WORTE)


# Was das Add-on selbst über MQTT anlegt. Diese Entitäten gehören in keine
# Auswahlliste – und schon gar nicht unter die Rauchmelder: Der eigene Melder
# „Rauchsperre" geht bei Alarm an. Zählte er als Rauchmelder, hielte sich der
# Alarm von da an selbst, und der Planer führe nie wieder einen Zeitplan aus.
EIGENES_PRAEFIX = "rolloplaner_"


def ist_eigene_entitaet(entity_id: str) -> bool:
    return entity_id.split(".", 1)[-1].startswith(EIGENES_PRAEFIX)


def sprache_von_ha() -> str | None:
    """Welche Sprache hat Home Assistant eingestellt?

    Steht in seiner Konfiguration (``/api/config``) als ``language``. Schlägt
    der Aufruf fehl, kommt nichts zurück – der Aufrufer entscheidet dann, und
    Raten wäre hier schlimmer als Nichtstun.
    """
    try:
        config = _request("GET", "/config")
    except Exception:  # noqa: BLE001
        return None
    wert = (config or {}).get("language")
    return str(wert).strip() or None if wert else None


def ist_rauchmelder(entity_id: str, name: str, klasse: str | None) -> bool:
    if klasse in ("smoke", "gas"):
        return True
    text = f"{entity_id} {name}".lower()
    if any(wort in text for wort in ("battery", "batterie", "test", "fehler")):
        return False
    return "rauch" in text or "smoke" in text


def sensor_candidates(states: list[dict] | None = None,
                      mit_bereichen: bool = True,
                      bereiche: dict | None = None) -> dict:
    """Kandidaten für die Auswahllisten der Oberfläche.

    Die Fensterliste enthält, was nach Geräteklasse oder Namen ein Kontakt ist;
    alles übrige Binäre steht getrennt unter ``sonstige_melder``. Ohne diese
    Trennung stünden dort dreißig Rollladen-Diagnosemelder.
    """
    fenster, rauch, sonstige, praesenz, aussen, raumtemp, schalter, kalender = (
        [], [], [], [], [], [], [], [])
    # Auswahlhelfer taugen als Bedingung an einem Schaltpunkt – etwa
    # „Terrassentür schließen: normal / 24 Uhr / aus“. Ihre möglichen Werte
    # kommen mit, damit die Oberfläche sie zur Auswahl stellen kann statt sie
    # abtippen zu lassen.
    auswahl = []
    zustaende = states if states is not None else get_states()
    if bereiche is None:
        bereiche = (bereiche_je_entitaet(("binary_sensor",)) if mit_bereichen else {})

    for s in zustaende:
        eid = s.get("entity_id", "")
        attrs = s.get("attributes", {}) or {}
        name = attrs.get("friendly_name", eid)
        domain = eid.split(".", 1)[0]
        klasse = attrs.get("device_class")
        if domain == "weather":
            aussen.append({"entity_id": eid, "name": name,
                           "wert": as_float(attrs.get("temperature"))})
        elif domain == "sensor" and klasse == "temperature":
            eintrag = {"entity_id": eid, "name": name, "wert": as_float(s.get("state"))}
            aussen.append(eintrag)
            raumtemp.append(eintrag)
        elif domain == "binary_sensor" and not ist_eigene_entitaet(eid):
            eintrag = {"entity_id": eid, "name": name,
                       "bereich": bereiche.get(eid, ""),
                       "zustand": s.get("state")}
            if ist_rauchmelder(eid, name, klasse):
                rauch.append(eintrag)
            elif klasse in ("motion", "occupancy", "presence"):
                praesenz.append(eintrag)
            elif ist_fensterkontakt(eid, name, klasse):
                fenster.append(eintrag)
            else:
                sonstige.append(eintrag)
            schalter.append(eintrag)
        elif domain in ("input_boolean", "switch"):
            schalter.append({"entity_id": eid, "name": name,
                             "zustand": s.get("state")})
        elif domain in ("input_select", "select"):
            auswahl.append({"entity_id": eid, "name": name,
                            "zustand": s.get("state"),
                            "optionen": list(attrs.get("options") or [])})
        elif domain == "calendar":
            kalender.append({"entity_id": eid, "name": name,
                             "zustand": s.get("state")})
    for liste in (fenster, rauch, sonstige, praesenz, aussen, raumtemp, schalter,
                  kalender, auswahl):
        liste.sort(key=lambda e: e["name"])
    return {"fenster": fenster, "rauch": rauch, "sonstige_melder": sonstige,
            "praesenz": praesenz, "aussen": aussen, "raumtemp": raumtemp,
            "schalter": schalter, "kalender": kalender, "auswahl": auswahl}


def notify(dienst: str, titel: str, nachricht: str) -> bool:
    """Eine Benachrichtigung über einen notify-Dienst von Home Assistant senden."""
    if not available() or not dienst:
        return False
    name = dienst.split(".", 1)[-1]
    try:
        _request("POST", f"/services/notify/{name}",
                 {"title": titel, "message": nachricht})
        _LOGGER.info("Benachrichtigung über %s: %s", dienst, titel)
        return True
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Benachrichtigung über %s fehlgeschlagen: %s", dienst, err)
        return False


def notify_dienste() -> list[dict]:
    """Alle verfügbaren notify-Dienste für die Auswahl in der Oberfläche."""
    if not available():
        return []
    try:
        dienste = _request("GET", "/services")
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Dienste konnten nicht geladen werden: %s", err)
        return []
    out = []
    for eintrag in dienste if isinstance(dienste, list) else []:
        if eintrag.get("domain") != "notify":
            continue
        for name in sorted(eintrag.get("services") or {}):
            out.append({"entity_id": f"notify.{name}", "name": f"notify.{name}"})
    return out
