"""Persistenz: Konfiguration (Rollos, Zeitpläne, Einstellungen) und Laufzeitzustand.

**Die Steuereinheit ist das Rollo, nicht der Raum.** Das ist der Kern des
Modells, und er ergibt sich aus dem Haus: Luna hat ein Fenster und eine
Balkontür, das Schlafzimmer ebenso, das Wohnzimmer zwei Fenster und eine
Terrassentür. Wer den Raum steuert, kann die Balkontür nicht offen lassen,
während das Fenster zufährt – und muss für jedes Rollo mit eigenem Regime
einen Kunstraum erfinden.

Jedes Rollo führt deshalb seine eigenen Angaben: was es ist (Fenster, Balkon-
oder Terrassentür), wohin es zeigt, welcher Kontakt es sperrt. Und es folgt
einem **benannten Zeitplan**, den sich mehrere Rollos teilen – oder einem
eigenen. Der Raum kommt aus Home Assistant und ordnet nur die Anzeige.

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
#                    eines einzelnen Rollos, ohne die Automatik im Haus
#                    insgesamt abzuschalten.
# "von_hand"       – kein Zeitplan, und das ist Absicht. Der Planer führt das
#                    Rollo weiter (Anzeige, Wächter, Rauchsperre, Fahren von
#                    Hand), steuert es aber nicht nach der Uhr. Ohne diese Art
#                    stünde für jedes bewusst ungeplante Rollo dauerhaft eine
#                    Warnung da – und echte Warnungen gingen darin unter.
BETRIEBSARTEN = ["plan", "nur_schliessen", "beobachten", "von_hand"]

ZUSTAENDE = ["an", "aus"]

# Was hinter dem Rollladen steckt. Das ist keine Frage der Optik: Eine
# Balkontür braucht eine Fenstersperre (wer draußen steht, will nicht
# ausgesperrt werden), ein Dachfenster hat eine andere Sonnenbahn, und in der
# Anzeige sieht eine Tür anders aus als ein Fenster.
ARTEN = {
    "fenster": "Fenster",
    "balkontuer": "Balkontür",
    "terrassentuer": "Terrassentür",
    "dachfenster": "Dachfenster",
    "haustuer": "Haustür",
}
# Welche davon bis zum Boden gehen – die Anzeige zeichnet sie als Tür.
TUERARTEN = ("balkontuer", "terrassentuer", "haustuer")

# Die eigenen Schalter des Planers. Ein Add-on, das fremde `input_boolean`
# voraussetzt, ist nach einer Neuinstallation nutzlos: Dort gibt es keine.
# Der Planer legt seine Schalter deshalb selbst an und veröffentlicht sie über
# MQTT – als `switch.` (an/aus) oder als `select.` (mehrere Stellungen).
SCHALTERARTEN = ["schalter", "auswahl"]

# Bedingungen dürfen auf eigene Schalter zeigen. Das Präfix kann keine
# entity_id sein, deshalb kommen eigene und fremde ohne zweite Codebahn durch
# dieselbe Prüfung.
EIGEN_PREFIX = "rolloplaner:"

# Himmelsrichtungen für den Hitzeschutz, in Grad wie der Azimut der Sonne:
# 0° Nord, 90° Ost, 180° Süd, 270° West.
HIMMELSRICHTUNGEN = {
    "n": 0, "no": 45, "o": 90, "so": 135,
    "s": 180, "sw": 225, "w": 270, "nw": 315,
}

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class ValidationError(ValueError):
    """Ungültige Eingabedaten."""


def eigener_schalter(entity: str) -> str | None:
    """Die ID eines eigenen Schalters, oder None bei einer fremden Entität."""
    if entity and entity.startswith(EIGEN_PREFIX):
        return entity[len(EIGEN_PREFIX):]
    return None


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
    # [{"id", "name", "art": "schalter"|"auswahl", "optionen": [...],
    #   "vorgabe": "on"|"<option>", "icon"}]
    "eigene_schalter": [],

    # Der Not-Aus. Solange ein Melder anschlägt, fasst der Planer **kein**
    # Rollo mehr nach Plan an. Ohne das führe er einer Notöffnung beim nächsten
    # Takt hinterher und machte den Fluchtweg wieder zu.
    "rauchsperre": {
        "aktiv": True,
        "melder": [],             # leer = alle binary_sensor mit device_class „smoke“
        "nachlauf_min": 30,       # so lange nach der Entwarnung bleibt es dabei
        # Die Fluchtweg-Freigabe: Bei Alarm fährt der Planer **jedes** Rollo
        # auf. Das steht über allem anderen – über der Automatik, über
        # „von Hand“, über einem abgeschalteten Zeitplan. Wer das für ein
        # einzelnes Rollo nicht will, schaltet es dort einzeln ab.
        "fluchtweg": True,
        # Ein Rollo, das trotz Befehl zu bleibt, wird erneut angefahren – aber
        # nicht endlos. Ein blockierter Antrieb, der im Minutentakt gegen ein
        # Hindernis fährt, ist im Brandfall keine Hilfe, sondern ein zweiter
        # Schaden.
        "fluchtweg_versuche": 3,
        # Ein eigener Meldeweg. Der Wächter meldet Ausfälle – ein Rauchalarm
        # ist etwas anderes und darf nicht an derselben Einstellung hängen wie
        # „ein Antrieb meldet sich nicht". Leer heißt: der Weg des Wächters,
        # damit die Meldung nie ins Leere geht.
        "melden_an": [],
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

STANDARD_PLAN = {
    "name": "Neuer Zeitplan",
    "aktiv": True,
    "zeitplan": [],
}

STANDARD_ROLLO = {
    # Die Entität ist der Schlüssel: Ein Rollo ist genau ein `cover.`.
    "entity_id": "",
    "name": "",                # leer = der Name aus Home Assistant
    "raum": "",                # aus dem Bereich; nur zum Ordnen der Anzeige
    "art": "fenster",
    "aktiv": True,
    "betriebsart": "plan",
    # Welchem benannten Zeitplan das Rollo folgt. Leer = es hat einen eigenen.
    "plan": "",
    "zeitplan": [],
    # Hitzeschutz gehört ans Rollo, nicht an den Raum: Ein Zimmer kann ein
    # Fenster nach Süden und eines nach Westen haben, und die wollen zu
    # verschiedenen Tageszeiten verschattet werden.
    "ausrichtung": None,
    "oeffnungswinkel": 90,
    "beschattung": False,
    "beschattung_position": None,
    "raumtemp": "",
    "raumtemp_ab": None,
    # Kontakte, die das Zufahren sperren. An einer Balkontür ist das kein
    # Zubehör, sondern der Unterschied zwischen „zu“ und „ausgesperrt“.
    "fenster": [],
    "praesenz": [],
    "personen": [],
    "urlaub_simulation": True,
    "position_offen": 100,
    "position_zu": 0,
    # Fährt bei Rauchalarm auf. Aus nur für ein Rollo, das nicht fahren darf –
    # eines vor einem Regal etwa, das gegen das Brett läuft.
    "fluchtweg": True,
}


def rauch_meldewege(einstellungen: dict) -> list[str]:
    """Wohin ein Rauchalarm gemeldet wird.

    Ein eigener Weg, weil ein Brandalarm etwas anderes ist als „ein Antrieb
    meldet sich nicht“ – wer den Wächter stummschaltet, weil ihn die
    Hinderniswarnungen nerven, will deswegen keinen Brand verschweigen. Ist
    kein eigener eingetragen, gilt trotzdem der Weg des Wächters: lieber die
    falsche Zustellart als gar keine Meldung.
    """
    sperre = einstellungen.get("rauchsperre") or {}
    return (list(sperre.get("melden_an") or [])
            or list((einstellungen.get("wachhund") or {}).get("melden_an") or []))


def _leer_config() -> dict:
    return {"einstellungen": dict(STANDARD_EINSTELLUNGEN), "plaene": [], "rollos": []}


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
        "plaene": [_merge(STANDARD_PLAN, p) for p in (roh.get("plaene") or [])],
        "rollos": [_merge(STANDARD_ROLLO, r) for r in (roh.get("rollos") or [])],
    }


def ist_alte_konfiguration() -> bool:
    """Steckt in ``config.json`` noch das raumzentrierte Modell?

    Bis Fassung 1.6 war der Raum die Steuereinheit. Diese Konfiguration lässt
    sich nicht sinnvoll weiterverwenden – ein Raum mit drei Rollos wusste
    nicht, welches davon eine Terrassentür ist.
    """
    with _lock:
        roh = _read(CONFIG_FILE, None)
    return bool(roh) and bool(roh.get("raeume")) and not roh.get("rollos")


def alte_konfiguration_sichern() -> str | None:
    """Die alte Konfiguration beiseitelegen, bevor neu eingerichtet wird."""
    with _lock:
        roh = _read(CONFIG_FILE, None)
        if not roh:
            return None
        ziel = os.path.join(DATA_DIR, "config-vor-umbau.json")
        _write(ziel, roh)
    return ziel


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
            # `rolloplaner:<id>` zeigt auf einen eigenen Schalter; alles andere
            # muss wie eine entity_id aussehen.
            if not eigener_schalter(entity) and "." not in entity:
                raise ValidationError(f"Bedingung: {entity!r} ist keine Entität")

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


def validate_plan(plan: dict, vorhandene_id: str | None = None) -> dict:
    """Ein benannter Zeitplan, den sich mehrere Rollos teilen können."""
    if not isinstance(plan, dict):
        raise ValidationError("Zeitplan: Objekt erwartet")
    name = str(plan.get("name") or "").strip()[:60]
    if not name:
        raise ValidationError("Der Zeitplan braucht einen Namen")
    return {
        "id": vorhandene_id or str(plan.get("id") or "").strip() or uuid.uuid4().hex[:8],
        "name": name,
        "aktiv": bool(plan.get("aktiv", True)),
        "zeitplan": validate_zeitplan(plan.get("zeitplan") or []),
    }


def validate_rollo(rollo: dict) -> dict:
    """Ein Rollo mit allem, was nur es betrifft.

    Der Schlüssel ist die Entität, nicht eine erfundene ID: Ein Rollo *ist*
    sein ``cover.`` – es kann nicht zweimal vorkommen, und wer es in Home
    Assistant umbenennt, hat immer noch dasselbe Rollo.
    """
    if not isinstance(rollo, dict):
        raise ValidationError("Rollo: Objekt erwartet")
    entity_id = str(rollo.get("entity_id") or "").strip()
    if not entity_id.startswith("cover."):
        raise ValidationError(f"{entity_id or '(leer)'} ist kein Rollladen")

    art = str(rollo.get("art") or "fenster").strip()
    if art not in ARTEN:
        raise ValidationError(f"Unbekannte Art {art!r}")

    betriebsart = str(rollo.get("betriebsart") or "plan").strip()
    if betriebsart not in BETRIEBSARTEN:
        raise ValidationError(f"Unbekannte Betriebsart {betriebsart!r}")

    ausrichtung = rollo.get("ausrichtung")
    if ausrichtung in (None, "", "null"):
        ausrichtung = None
    elif isinstance(ausrichtung, str) and ausrichtung.lower() in HIMMELSRICHTUNGEN:
        ausrichtung = HIMMELSRICHTUNGEN[ausrichtung.lower()]
    else:
        ausrichtung = int(_zahl(ausrichtung, "Ausrichtung", 0, 359))

    raumtemp_ab = rollo.get("raumtemp_ab")
    raumtemp_ab = (None if raumtemp_ab in (None, "", "null")
                   else _zahl(raumtemp_ab, "Raumtemperatur-Schwelle", 10.0, 40.0))

    beschattung_position = rollo.get("beschattung_position")
    beschattung_position = (None if beschattung_position in (None, "", "null")
                            else _position(beschattung_position, "Beschattungsstellung"))

    offen = _position(rollo.get("position_offen", 100), "Stellung offen")
    zu = _position(rollo.get("position_zu", 0), "Stellung zu")
    if offen <= zu:
        raise ValidationError("„Offen“ muss über „Zu“ liegen")

    plan = str(rollo.get("plan") or "").strip()
    # Entweder es folgt einem Plan, oder es hat einen eigenen – nicht beides.
    eigener = [] if plan else validate_zeitplan(rollo.get("zeitplan") or [])

    return {
        "entity_id": entity_id,
        "name": str(rollo.get("name") or "").strip()[:60],
        "raum": str(rollo.get("raum") or "").strip()[:60],
        "art": art,
        "aktiv": bool(rollo.get("aktiv", True)),
        "betriebsart": betriebsart,
        "plan": plan,
        "zeitplan": eigener,
        "ausrichtung": ausrichtung,
        "oeffnungswinkel": int(_zahl(rollo.get("oeffnungswinkel", 90),
                                     "Öffnungswinkel", 10, 180)),
        "beschattung": bool(rollo.get("beschattung", False)) and ausrichtung is not None,
        "beschattung_position": beschattung_position,
        "raumtemp": str(rollo.get("raumtemp") or "").strip(),
        "raumtemp_ab": raumtemp_ab,
        "fenster": [str(e).strip() for e in (rollo.get("fenster") or []) if str(e).strip()],
        "praesenz": [str(e).strip() for e in (rollo.get("praesenz") or []) if str(e).strip()],
        "personen": [str(e).strip() for e in (rollo.get("personen") or []) if str(e).strip()],
        "urlaub_simulation": bool(rollo.get("urlaub_simulation", True)),
        "position_offen": offen,
        "position_zu": zu,
        "fluchtweg": bool(rollo.get("fluchtweg", True)),
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
    r["fluchtweg"] = bool(r.get("fluchtweg", True))
    r["fluchtweg_versuche"] = int(_zahl(r.get("fluchtweg_versuche", 3),
                                        "Versuche der Fluchtweg-Freigabe", 1, 10))
    r["melden_an"] = [str(m).strip() for m in (r.get("melden_an") or []) if str(m).strip()]

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

    e["eigene_schalter"] = validate_schalter(e.get("eigene_schalter"))

    w = e["wachhund"]
    w["aktiv"] = bool(w["aktiv"])
    w["stumm_stunden"] = _zahl(w["stumm_stunden"], "Schweigefrist", 0.5, 336.0)
    w["hindernis_melden"] = bool(w["hindernis_melden"])
    w["melden_an"] = [str(d).strip() for d in (w.get("melden_an") or []) if str(d).strip()]
    return e


def validate_schalter(roh) -> list[dict]:
    """Die eigenen Schalter prüfen.

    Die ID wird **nie** aus dem Namen abgeleitet: Ein umbenannter Schalter soll
    seine Entität in Home Assistant behalten und nicht als neue auftauchen,
    während die alte als Karteileiche stehenbleibt.
    """
    if roh is None:
        return []
    if not isinstance(roh, list):
        raise ValidationError("Eigene Schalter: Liste erwartet")
    out, ids = [], set()
    for eintrag in roh:
        if not isinstance(eintrag, dict):
            raise ValidationError("Schalter: Objekt erwartet")
        name = str(eintrag.get("name") or "").strip()[:60]
        if not name:
            raise ValidationError("Der Schalter braucht einen Namen")
        art = str(eintrag.get("art") or "schalter").strip()
        if art not in SCHALTERARTEN:
            raise ValidationError(f"Unbekannte Schalterart {art!r}")

        optionen = [str(o).strip() for o in (eintrag.get("optionen") or [])
                    if str(o).strip()]
        if art == "auswahl":
            if len(optionen) < 2:
                raise ValidationError(
                    f"„{name}“: eine Auswahl braucht mindestens zwei Stellungen")
            if len(set(optionen)) != len(optionen):
                raise ValidationError(f"„{name}“: doppelte Stellungen")
        else:
            optionen = []

        vorgabe = str(eintrag.get("vorgabe") or "").strip()
        if art == "auswahl":
            if vorgabe not in optionen:
                vorgabe = optionen[0]
        else:
            vorgabe = "on" if vorgabe not in ("on", "off") else vorgabe

        kennung = str(eintrag.get("id") or "").strip() or uuid.uuid4().hex[:8]
        if kennung in ids:
            raise ValidationError(f"Schalter-ID {kennung} kommt doppelt vor")
        ids.add(kennung)

        out.append({"id": kennung, "name": name, "art": art,
                    "optionen": optionen, "vorgabe": vorgabe,
                    "icon": str(eintrag.get("icon") or "").strip(),
                    # Woher der Schalter stammt, falls er beim Umstellen aus
                    # einem fremden Helfer entstanden ist. Nur zur Zuordnung
                    # bei einem zweiten Durchlauf.
                    "quelle": str(eintrag.get("quelle") or "").strip()})
    return out


# ------------------------------------------------------------------ CRUD ----

def rollos_setzen(rollos: list) -> list[dict]:
    """Die ganze Rolloliste auf einmal – ein Rollo kommt nur einmal vor."""
    config = load_config()
    gesehen, out = set(), []
    for roh in rollos or []:
        eintrag = validate_rollo(roh)
        if eintrag["entity_id"] in gesehen:
            raise ValidationError(f"{eintrag['entity_id']} steht doppelt in der Liste")
        gesehen.add(eintrag["entity_id"])
        out.append(eintrag)
    _plaene_pruefen(out, config["plaene"])
    config["rollos"] = out
    save_config(config)
    return out


def update_rollo(entity_id: str, rollo: dict) -> dict:
    config = load_config()
    for i, vorhanden in enumerate(config["rollos"]):
        if vorhanden["entity_id"] == entity_id:
            neu = validate_rollo({**rollo, "entity_id": entity_id})
            _plaene_pruefen([neu], config["plaene"])
            config["rollos"][i] = neu
            save_config(config)
            return neu
    raise ValidationError("Rollo nicht gefunden")


def add_rollo(rollo: dict) -> dict:
    config = load_config()
    neu = validate_rollo(rollo)
    if any(r["entity_id"] == neu["entity_id"] for r in config["rollos"]):
        raise ValidationError(f"{neu['entity_id']} ist schon eingerichtet")
    _plaene_pruefen([neu], config["plaene"])
    config["rollos"].append(neu)
    save_config(config)
    return neu


def delete_rollo(entity_id: str) -> bool:
    config = load_config()
    vorher = len(config["rollos"])
    config["rollos"] = [r for r in config["rollos"] if r["entity_id"] != entity_id]
    if len(config["rollos"]) == vorher:
        return False
    save_config(config)
    return True


def _plaene_pruefen(rollos: list[dict], plaene: list[dict]) -> None:
    """Zeigt jedes Rollo auf einen Zeitplan, den es gibt?

    Ein Rollo, das einem gelöschten Plan folgt, hätte gar keinen – und stünde
    still, ohne dass man ihm das ansieht.
    """
    vorhanden = {p["id"] for p in plaene}
    for rollo in rollos:
        if rollo["plan"] and rollo["plan"] not in vorhanden:
            raise ValidationError(
                f"{rollo['entity_id']}: den Zeitplan gibt es nicht")


def add_plan(plan: dict) -> dict:
    config = load_config()
    neu = validate_plan(plan)
    config["plaene"].append(neu)
    save_config(config)
    return neu


def update_plan(plan_id: str, plan: dict) -> dict:
    config = load_config()
    for i, vorhanden in enumerate(config["plaene"]):
        if vorhanden["id"] == plan_id:
            config["plaene"][i] = validate_plan(plan, vorhandene_id=plan_id)
            save_config(config)
            return config["plaene"][i]
    raise ValidationError("Zeitplan nicht gefunden")


def delete_plan(plan_id: str) -> bool:
    """Einen Zeitplan löschen – aber nicht, solange ihm ein Rollo folgt."""
    config = load_config()
    folgen = [r["entity_id"] for r in config["rollos"] if r["plan"] == plan_id]
    if folgen:
        raise ValidationError("Diesem Zeitplan folgen noch: " + ", ".join(folgen))
    vorher = len(config["plaene"])
    config["plaene"] = [p for p in config["plaene"] if p["id"] != plan_id]
    if len(config["plaene"]) == vorher:
        return False
    save_config(config)
    return True


def plaene_setzen(plaene: list) -> list[dict]:
    config = load_config()
    out = [validate_plan(p) for p in plaene or []]
    _plaene_pruefen(config["rollos"], out)
    config["plaene"] = out
    save_config(config)
    return out


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
    # entity_id -> {ziel, gesetzt_am, grund, manuell_bis,
    #               letzter_punkt, beschattet}
    # Alles am Rollo: Der zuletzt ausgeführte Schaltpunkt gehört zum Rollo und
    # nicht zum Plan – zwei Rollos am selben Plan können verschieden weit sein,
    # wenn eines wegen offener Tür übergangen wurde.
    state.setdefault("rollos", {})
    state.setdefault("veroeffentlichte_rollos", [])
    state.setdefault("veroeffentlichte_plaene", [])
    state.setdefault("stoerungen", {})
    state.setdefault("rauch_bis", None)
    # Der Stand der laufenden Fluchtweg-Freigabe: seit wann sie läuft und wie
    # oft welches Rollo schon angefahren wurde. Ohne diesen Zähler schickte
    # der Planer bei jedem Takt einen neuen Fahrbefehl.
    state.setdefault("fluchtweg", {"seit": None, "versuche": {}})
    # Seit wann der Alarm läuft – unabhängig davon, ob die Fluchtweg-Freigabe
    # eingeschaltet ist. Daran hängt, dass je Alarm genau einmal gemeldet wird.
    state.setdefault("rauch_seit", None)
    # Tagesversatz der Urlaubssimulation: je Raum und Schaltpunkt eine Zahl,
    # die einmal am Tag neu gewürfelt wird.
    state.setdefault("simulation", {"tag": None, "versatz": {}})
    # Der Stand der eigenen Schalter. Er **muss** die Platte überleben – sonst
    # stünde nach jedem Neustart des Add-ons jede Freigabe wieder auf der
    # Vorgabe, und ein abends abgeschalteter Raum führe nachts doch.
    state.setdefault("schalter", {})
    return state


def save_state(state: dict) -> None:
    with _lock:
        _write(STATE_FILE, state)
