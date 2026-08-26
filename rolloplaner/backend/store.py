"""Persistenz: Konfiguration (Räume, Zeitpläne, Einstellungen) und Laufzeitzustand.

Drei Dateien unter ``/data``:

``config.json``   – was der Benutzer eingestellt hat.
``zustand.json``  – was der Planer zuletzt getan hat.
``logbuch.json``  – womit er es begründet hat.

Der Laufzeitzustand **muss** die Platte überleben. Ein Rollladen ist kein
Thermostat: Ein überflüssiger Schaltbefehl kostet nicht ein halbes Grad,
sondern lässt den Motor anlaufen. Ohne gespeicherten Zustand führe nach jedem
Add-on-Neustart das halbe Haus einmal durch – nachts um drei genauso wie
mittags.
"""
from __future__ import annotations

import json
import os
import re
import threading
import uuid

DATA_DIR = os.environ.get("DATA_DIR", "./data")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
STATE_FILE = os.path.join(DATA_DIR, "zustand.json")

_lock = threading.Lock()

TAGE = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# Wann ein Schaltpunkt fällig wird. „sonnenaufgang“/„sonnenuntergang“ folgen
# dem Lauf der Sonne über das Jahr – im Dezember fährt das Rollo damit vier
# Stunden früher zu als im Juni, ohne dass jemand etwas umstellt.
AUSLOESER = ["uhrzeit", "sonnenaufgang", "sonnenuntergang", "daemmerung"]

# Geltung eines Schaltpunkts. „morgen_*“ ist kein Schreibfehler: Wann die
# Kinderzimmer abends zufahren, hängt nicht am heutigen Tag, sondern daran,
# ob morgen die Schule ruft.
GELTUNG = ["immer", "schultag", "schulfrei", "morgen_schultag", "morgen_schulfrei"]

# "plan"           – der Planer fährt auf und zu.
# "nur_schliessen" – er fährt abends zu, öffnet aber nie von selbst.
# "beobachten"     – er rechnet mit, schaltet aber nichts. Für den Probelauf
#                    eines einzelnen Raumes, ohne die Automatik im Haus
#                    insgesamt abzuschalten.
BETRIEBSARTEN = ["plan", "nur_schliessen", "beobachten"]

ZUSTAENDE = ["an", "aus"]

# Was die Anzeige zeichnet. „auto“ entscheidet nach den Namen der Rollos –
# ein „Rollo Balkontür Luna“ ist eine Tür, ein „Rollo Küche“ ein Fenster.
BILDARTEN = ["auto", "fenster", "tuer"]

# Himmelsrichtungen für den Hitzeschutz, in Grad wie der Azimut der Sonne:
# 0° Nord, 90° Ost, 180° Süd, 270° West.
HIMMELSRICHTUNGEN = {
    "n": 0, "no": 45, "o": 90, "so": 135,
    "s": 180, "sw": 225, "w": 270, "nw": 315,
}

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class ValidationError(ValueError):
    """Ungültige Eingabedaten."""


def anzeige_prozent(wert, invertiert: bool):
    """Einen intern gespeicherten Wert so umrechnen, wie er angezeigt wird."""
    if wert is None or not invertiert:
        return wert
    return 100 - int(wert)


# --------------------------------------------------------------- Vorgaben ----

STANDARD_EINSTELLUNGEN = {
    "automatik": True,
    "trockenlauf": True,          # sicherer Start: erst rechnen, nicht fahren
    "takt_sekunden": 120,
    "schulfrei_entity": "input_boolean.wochenende_feiertag",
    "schulfrei_morgen_entity": "input_boolean.morgen_wochenende_feiertag",
    "urlaub_entity": "input_boolean.urlaub",
    "sonne_entity": "sun.sun",
    "aussen_entity": "weather.forecast_home",
    "manuell_respektieren": True,
    # So lange bleibt ein von Hand gefahrenes Rollo in Ruhe. Danach greift der
    # Plan wieder – sonst müsste man daran denken, den Handbetrieb zu beenden.
    "manuell_stunden": 12.0,
    "ignorierte_vorschlaege": [],
    # Home Assistant zählt 100 % = offen. Amazon Echo zählt andersherum, und
    # wer beides bedient, verrechnet sich sonst ständig. Diese Einstellung
    # dreht **nur die Anzeige und die Eingabe** um; gespeichert wird immer in
    # der Zählweise von Home Assistant. Sonst stünde nach jedem Umschalten
    # jeder Zeitplan auf dem Kopf.
    "prozent_invertiert": False,

    # Der Not-Aus. Solange ein Melder anschlägt, fasst der Planer **kein**
    # Rollo mehr an. Ohne das führe er einer Notöffnung beim nächsten Takt
    # hinterher und machte den Fluchtweg wieder zu.
    "rauchsperre": {
        "aktiv": True,
        "melder": [],             # leer = alle binary_sensor mit device_class „smoke“
        "nachlauf_min": 30,       # so lange nach der Entwarnung bleibt es dabei
    },

    # Hitzeschutz: Rollo teilweise zufahren, wenn die Sonne aufs Fenster steht
    # und es draußen warm ist. Im Winter bleibt es offen – die Sonne heizt
    # dann kostenlos mit.
    "beschattung": {
        "aktiv": True,
        "ab_temperatur": 24.0,    # Außentemperatur, ab der beschattet wird
        "hysterese": 1.5,         # … und um wie viel sie darunter fallen muss
        "min_elevation": 12.0,    # tief stehende Sonne blendet, wärmt aber kaum
        "position": 35,           # so weit bleibt das Rollo offen
        "nur_wenn_niemand_da": False,
    },

    # Anwesenheitssimulation im Urlaub: dieselben Schaltpunkte, aber jeden Tag
    # ein paar Minuten anders. Ein Haus, dessen Rollos wochenlang auf die
    # Minute genau fahren, verrät sich – und eines, dessen Rollos gar nicht
    # mehr fahren, erst recht.
    "urlaub": {
        "modus": "simulation",    # "simulation" | "zu" | "plan"
        "streuung_min": 20,
        "nicht_vor": "07:00",
        "nicht_nach": "22:30",
    },

    # Ein Rollo, das nicht mehr meldet oder beim Fahren hängen bleibt, soll
    # auffallen, ohne dass jemand hinsieht.
    "wachhund": {
        "aktiv": True,
        "stumm_stunden": 26.0,    # ein Rollo, das nur zweimal am Tag fährt,
                                  # meldet sich auch nur zweimal am Tag
        "hindernis_melden": True,
        "melden_an": ["notify.persistent_notification"],
    },
}

STANDARD_RAUM = {
    "name": "Neuer Raum",
    "aktiv": True,
    "betriebsart": "plan",
    "rollos": [],
    "freigabe_entity": "",     # leer = der Raum ist immer freigegeben
    "fenster": [],             # Kontakte, die das Zufahren sperren
    "praesenz": [],
    "personen": [],
    # Hitzeschutz je Raum. Ohne Ausrichtung bleibt er aus: Der Planer kann
    # nicht erraten, wohin ein Fenster zeigt, und ein geratener Wert
    # verschattet zur falschen Tageszeit.
    "ausrichtung": None,       # Grad, 0 = Nord, 180 = Süd
    "oeffnungswinkel": 90,     # ± um die Ausrichtung, in dem die Sonne zählt
    "beschattung": False,
    "beschattung_position": None,   # None = die globale Vorgabe
    "raumtemp": "",            # optional: erst beschatten, wenn es drinnen warm ist
    "raumtemp_ab": None,
    "urlaub_simulation": True,
    "position_offen": 100,
    "position_zu": 0,
    "bildart": "auto",
    "zeitplan": [],
}


def _leer_config() -> dict:
    return {"einstellungen": dict(STANDARD_EINSTELLUNGEN), "raeume": []}


# ------------------------------------------------------------------- I/O ----

def _read(path: str, fallback):
    if not os.path.exists(path):
        return fallback
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return fallback


def _write(path: str, data) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _merge(vorgabe: dict, gespeichert: dict) -> dict:
    """Gespeicherte Werte über die Vorgaben legen, verschachtelt.

    Sorgt dafür, dass neue Einstellungen aus einer Add-on-Aktualisierung
    auftauchen, ohne dass die Konfiguration von Hand nachgezogen werden muss.
    """
    out = dict(vorgabe)
    for key, value in (gespeichert or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


# --------------------------------------------------------- Konfiguration ----

def load_config() -> dict:
    with _lock:
        roh = _read(CONFIG_FILE, None)
    if not roh:
        return _leer_config()
    return {
        "einstellungen": _merge(STANDARD_EINSTELLUNGEN, roh.get("einstellungen") or {}),
        "raeume": [_merge(STANDARD_RAUM, r) for r in (roh.get("raeume") or [])],
    }


def save_config(config: dict) -> dict:
    with _lock:
        _write(CONFIG_FILE, config)
    return config


# ------------------------------------------------------------ Validierung ----

def _zahl(wert, name: str, minimum: float, maximum: float) -> float:
    try:
        f = float(wert)
    except (TypeError, ValueError) as err:
        raise ValidationError(f"{name}: Zahl erwartet") from err
    if not minimum <= f <= maximum:
        raise ValidationError(f"{name}: Wert muss zwischen {minimum} und {maximum} liegen")
    return round(f, 2)


def _position(wert, name: str) -> int:
    """Rollladenstellung in Prozent, 100 = ganz offen."""
    return int(_zahl(wert, name, 0, 100))


def validate_zeitplan(zeitplan) -> list[dict]:
    """Die Schaltpunkte eines Raumes prüfen und in feste Reihenfolge bringen.

    Ein Schaltpunkt ist kein Zeitraum, sondern ein Ereignis: „ab hier steht das
    Rollo auf 100 %“. Es gibt bewusst keine Endzeit – der nächste Punkt löst
    den vorherigen ab, und es kann keine Lücke geben, in der niemand zuständig
    ist.

    ``frueh``/``spaet`` klammern einen Sonnenauslöser ein. Genau das macht die
    heutige Büro-Automation von Hand: bei Sonnenaufgang öffnen, aber nie vor
    halb neun.
    """
    if not isinstance(zeitplan, list):
        raise ValidationError("Zeitplan: Liste erwartet")
    out = []
    for eintrag in zeitplan:
        if not isinstance(eintrag, dict):
            raise ValidationError("Zeitplan: ungültiger Eintrag")

        ausloeser = str(eintrag.get("ausloeser") or "uhrzeit").strip()
        if ausloeser not in AUSLOESER:
            raise ValidationError(f"Zeitplan: unbekannter Auslöser {ausloeser!r}")

        start = str(eintrag.get("start") or "").strip()
        if ausloeser == "uhrzeit":
            if not _TIME_RE.match(start):
                raise ValidationError(
                    f"Zeitplan: ungültige Uhrzeit {start!r} (erwartet HH:MM)")
        else:
            start = ""

        versatz = int(_zahl(eintrag.get("versatz_min", 0), "Versatz", -180, 180))
        frueh = str(eintrag.get("frueh") or "").strip()
        spaet = str(eintrag.get("spaet") or "").strip()
        for wert, name in ((frueh, "Frühestens"), (spaet, "Spätestens")):
            if wert and not _TIME_RE.match(wert):
                raise ValidationError(f"Zeitplan: ungültige Uhrzeit für {name}: {wert!r}")
        if ausloeser == "uhrzeit":
            # Bei fester Uhrzeit wären die Klammern sinnlos und nur verwirrend.
            frueh = spaet = ""
            versatz = 0

        gilt = str(eintrag.get("gilt") or "immer").strip()
        if gilt not in GELTUNG:
            raise ValidationError(f"Zeitplan: unbekannte Geltung {gilt!r}")

        tage = [t for t in (eintrag.get("tage") or []) if t in TAGE]
        if not tage:
            raise ValidationError("Zeitplan: mindestens ein Wochentag nötig")

        # Bedingungen: Der Punkt gilt nur, wenn **alle** zutreffen. Damit
        # lässt sich ein Auswahlhelfer abbilden – „Terrassentür schließen:
        # normal / 24 Uhr / aus“ sind drei Punkte, von denen je nach Stellung
        # des Helfers einer greift oder keiner.
        bedingungen = []
        for bedingung in (eintrag.get("wenn") or []):
            if not isinstance(bedingung, dict):
                raise ValidationError("Bedingung: Objekt erwartet")
            entity = str(bedingung.get("entity") or "").strip()
            if not entity:
                continue
            bedingungen.append({"entity": entity,
                                "wert": str(bedingung.get("wert") or "").strip()})

        out.append({
            "ausloeser": ausloeser,
            "start": start,
            "wenn": bedingungen,
            "versatz_min": versatz,
            "frueh": frueh,
            "spaet": spaet,
            "position": _position(eintrag.get("position", 100), "Stellung"),
            "gilt": gilt,
            "tage": tage,
            "name": str(eintrag.get("name") or "").strip()[:40],
        })
    # Nach der frühestmöglichen Tageszeit sortieren, damit die Liste in der
    # Oberfläche dem Tagesablauf folgt. Sonnenauslöser ohne Klammer bekommen
    # einen groben Platzhalter – die genaue Lage steht erst zur Laufzeit fest.
    def _rang(e: dict) -> str:
        if e["ausloeser"] == "uhrzeit":
            return e["start"]
        if e["frueh"]:
            return e["frueh"]
        return "05:00" if e["ausloeser"] == "sonnenaufgang" else "19:00"

    out.sort(key=_rang)
    return out


def validate_raum(raum: dict, vorhandene_id: str | None = None) -> dict:
    if not isinstance(raum, dict):
        raise ValidationError("Raum: Objekt erwartet")
    name = str(raum.get("name") or "").strip()[:60]
    if not name:
        raise ValidationError("Der Raum braucht einen Namen")

    rollos = [str(e).strip() for e in (raum.get("rollos") or []) if str(e).strip()]
    for eid in rollos:
        if not eid.startswith("cover."):
            raise ValidationError(f"{eid} ist kein Rollladen")

    betriebsart = str(raum.get("betriebsart") or "plan").strip()
    if betriebsart not in BETRIEBSARTEN:
        raise ValidationError(f"Unbekannte Betriebsart {betriebsart!r}")

    ausrichtung = raum.get("ausrichtung")
    if ausrichtung in (None, "", "null"):
        ausrichtung = None
    elif isinstance(ausrichtung, str) and ausrichtung.lower() in HIMMELSRICHTUNGEN:
        ausrichtung = HIMMELSRICHTUNGEN[ausrichtung.lower()]
    else:
        ausrichtung = int(_zahl(ausrichtung, "Ausrichtung", 0, 359))

    raumtemp_ab = raum.get("raumtemp_ab")
    raumtemp_ab = (None if raumtemp_ab in (None, "", "null")
                   else _zahl(raumtemp_ab, "Raumtemperatur-Schwelle", 10.0, 40.0))

    beschattung_position = raum.get("beschattung_position")
    beschattung_position = (None if beschattung_position in (None, "", "null")
                            else _position(beschattung_position, "Beschattungsstellung"))

    bildart = str(raum.get("bildart") or "auto").strip()
    if bildart not in BILDARTEN:
        raise ValidationError(f"Unbekannte Darstellung {bildart!r}")

    offen = _position(raum.get("position_offen", 100), "Stellung offen")
    zu = _position(raum.get("position_zu", 0), "Stellung zu")
    if offen <= zu:
        raise ValidationError("„Offen“ muss über „Zu“ liegen")

    return {
        "id": vorhandene_id or uuid.uuid4().hex[:8],
        "name": name,
        "aktiv": bool(raum.get("aktiv", True)),
        "betriebsart": betriebsart,
        "rollos": rollos,
        "freigabe_entity": str(raum.get("freigabe_entity") or "").strip(),
        "fenster": [str(e).strip() for e in (raum.get("fenster") or []) if str(e).strip()],
        "praesenz": [str(e).strip() for e in (raum.get("praesenz") or []) if str(e).strip()],
        "personen": [str(e).strip() for e in (raum.get("personen") or []) if str(e).strip()],
        "ausrichtung": ausrichtung,
        "oeffnungswinkel": int(_zahl(raum.get("oeffnungswinkel", 90),
                                     "Öffnungswinkel", 10, 180)),
        # Ohne Ausrichtung kann der Hitzeschutz nicht rechnen – dann bleibt er
        # aus, auch wenn das Häkchen gesetzt ist.
        "beschattung": bool(raum.get("beschattung", False)) and ausrichtung is not None,
        "beschattung_position": beschattung_position,
        "raumtemp": str(raum.get("raumtemp") or "").strip(),
        "raumtemp_ab": raumtemp_ab,
        "urlaub_simulation": bool(raum.get("urlaub_simulation", True)),
        "position_offen": offen,
        "position_zu": zu,
        "bildart": bildart,
        "zeitplan": validate_zeitplan(raum.get("zeitplan") or []),
    }


def validate_einstellungen(roh: dict) -> dict:
    """Nur bekannte Felder übernehmen und in vernünftige Grenzen zwingen."""
    e = _merge(STANDARD_EINSTELLUNGEN, roh or {})
    e["automatik"] = bool(e["automatik"])
    e["trockenlauf"] = bool(e["trockenlauf"])
    e["manuell_respektieren"] = bool(e["manuell_respektieren"])
    e["prozent_invertiert"] = bool(e["prozent_invertiert"])
    e["manuell_stunden"] = _zahl(e["manuell_stunden"], "Handbetrieb", 0.0, 168.0)
    e["takt_sekunden"] = int(_zahl(e["takt_sekunden"], "Takt", 30, 3600))
    for schluessel in ("schulfrei_entity", "schulfrei_morgen_entity", "urlaub_entity",
                       "sonne_entity", "aussen_entity"):
        e[schluessel] = str(e[schluessel] or "").strip()
    e["ignorierte_vorschlaege"] = sorted({
        str(x).strip() for x in (e.get("ignorierte_vorschlaege") or []) if str(x).strip()})

    r = e["rauchsperre"]
    r["aktiv"] = bool(r["aktiv"])
    r["melder"] = [str(m).strip() for m in (r.get("melder") or []) if str(m).strip()]
    r["nachlauf_min"] = int(_zahl(r["nachlauf_min"], "Nachlauf der Rauchsperre", 0, 720))

    b = e["beschattung"]
    b["aktiv"] = bool(b["aktiv"])
    b["ab_temperatur"] = _zahl(b["ab_temperatur"], "Beschattungstemperatur", 10.0, 40.0)
    b["hysterese"] = _zahl(b["hysterese"], "Hysterese", 0.0, 10.0)
    b["min_elevation"] = _zahl(b["min_elevation"], "Mindesthöhe der Sonne", 0.0, 60.0)
    b["position"] = _position(b["position"], "Beschattungsstellung")
    b["nur_wenn_niemand_da"] = bool(b["nur_wenn_niemand_da"])

    u = e["urlaub"]
    if str(u.get("modus")) not in ("simulation", "zu", "plan"):
        u["modus"] = "simulation"
    u["streuung_min"] = int(_zahl(u["streuung_min"], "Streuung", 0, 120))
    for schluessel, name in (("nicht_vor", "Nicht vor"), ("nicht_nach", "Nicht nach")):
        wert = str(u.get(schluessel) or "").strip()
        if wert and not _TIME_RE.match(wert):
            raise ValidationError(f"Urlaub – {name}: ungültige Uhrzeit {wert!r}")
        u[schluessel] = wert

    w = e["wachhund"]
    w["aktiv"] = bool(w["aktiv"])
    w["stumm_stunden"] = _zahl(w["stumm_stunden"], "Schweigefrist", 0.5, 336.0)
    w["hindernis_melden"] = bool(w["hindernis_melden"])
    w["melden_an"] = [str(d).strip() for d in (w.get("melden_an") or []) if str(d).strip()]
    return e


# ------------------------------------------------------------- Raum-CRUD ----

def add_raum(raum: dict) -> dict:
    config = load_config()
    neu = validate_raum(raum)
    config["raeume"].append(neu)
    save_config(config)
    return neu


def update_raum(raum_id: str, raum: dict) -> dict:
    config = load_config()
    for i, vorhanden in enumerate(config["raeume"]):
        if vorhanden.get("id") == raum_id:
            neu = validate_raum(raum, vorhandene_id=raum_id)
            config["raeume"][i] = neu
            save_config(config)
            return neu
    raise ValidationError("Raum nicht gefunden")


def delete_raum(raum_id: str) -> bool:
    config = load_config()
    vorher = len(config["raeume"])
    config["raeume"] = [r for r in config["raeume"] if r.get("id") != raum_id]
    if len(config["raeume"]) == vorher:
        return False
    save_config(config)
    return True


def update_einstellungen(roh: dict) -> dict:
    config = load_config()
    config["einstellungen"] = validate_einstellungen(
        _merge(config["einstellungen"], roh or {}))
    save_config(config)
    return config["einstellungen"]


# -------------------------------------------------------- Laufzeitzustand ----

def load_state() -> dict:
    with _lock:
        state = _read(STATE_FILE, None)
    if not isinstance(state, dict):
        state = {}
    # entity_id -> {ziel, gesetzt_am, ausloeser, gemeldet}
    state.setdefault("rollos", {})
    # raum_id -> {letzter_punkt, beschattet, manuell_bis}
    state.setdefault("raeume", {})
    state.setdefault("veroeffentlichte_raeume", [])
    state.setdefault("stoerungen", {})
    state.setdefault("rauch_bis", None)
    # Tagesversatz der Urlaubssimulation: je Raum und Schaltpunkt eine Zahl,
    # die einmal am Tag neu gewürfelt wird.
    state.setdefault("simulation", {"tag": None, "versatz": {}})
    return state


def save_state(state: dict) -> None:
    with _lock:
        _write(STATE_FILE, state)
