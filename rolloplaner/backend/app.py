"""Rolloplaner – Dienst, Regeltakt und REST-Schnittstelle.

Der Takt läuft in einem eigenen Faden und rechnet alle paar Minuten alle Räume
durch. Die Oberfläche liest denselben Bericht, den auch MQTT bekommt; es gibt
keine zweite Wahrheit.
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
import threading
import time
import urllib.request
from datetime import datetime

from flask import Flask, jsonify, request, send_from_directory

import cardsync
import ha_api
import logbuch
import regelung
import store
import uebernahme
import wachhund
import zeitplan
from version import VERSION

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
_LOGGER = logging.getLogger("rolloplaner")

FRONTEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "frontend")
PORT = 8100

app = Flask(__name__, static_folder=None)

_takt_lock = threading.Lock()
_wecker = threading.Event()
_letzter_bericht: dict = {"zeit": None, "rollos": [], "hinweis": "Noch kein Durchlauf"}
_publisher = None


# ----------------------------------------------------------- Zeitzone ----

def _zeitzone_uebernehmen() -> None:
    """Die Zeitzone von Home Assistant übernehmen.

    Ohne das rechnet der Container in UTC – ein Schaltpunkt um 20:30 würde im
    Sommer zwei Stunden zu spät fahren, und der Sonnenuntergang läge auf einer
    ganz anderen Uhrzeit als im Dashboard.
    """
    try:
        req = urllib.request.Request(
            "http://supervisor/core/api/config",
            headers={"Authorization": f"Bearer {os.environ.get('SUPERVISOR_TOKEN', '')}"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            zone = json.loads(resp.read().decode("utf-8")).get("time_zone")
        if zone:
            os.environ["TZ"] = zone
            time.tzset()
            _LOGGER.info("Zeitzone: %s", zone)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Zeitzone konnte nicht übernommen werden: %s", err)


# --------------------------------------------------------------- Takt ----

def _takt_ausfuehren() -> dict:
    global _letzter_bericht
    with _takt_lock:
        config = store.load_config()
        state = store.load_state()
        def wachhund_haken(index: dict, jetzt: datetime) -> list[dict]:
            stoerungen = wachhund.pruefen(config, index, jetzt, state)
            _stoerungen_melden(stoerungen, state, config["einstellungen"])
            return stoerungen

        try:
            bericht = regelung.takt(config, state, logbuch.eintragen, wachhund_haken)
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Regeltakt fehlgeschlagen")
            bericht = {"zeit": None, "rollos": [], "fehler": str(err)}
        else:
            store.save_state(state)
        bericht["version"] = VERSION
        _letzter_bericht = bericht
    if _publisher is not None:
        try:
            _publisher.publish_status(bericht, config)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("MQTT-Meldung fehlgeschlagen: %s", err)
    return bericht


def _stoerungen_melden(stoerungen: list, state: dict, einstellungen: dict) -> None:
    """Neue Störungen einmal melden, behobene einmal entwarnen.

    Eine Meldung, die nur in der Oberfläche steht, hilft bei einem Rollo nicht:
    Dass eines auf halber Höhe hängt, sieht man von innen kaum und von außen
    nur, wenn man hinschaut.
    """
    gemerkt = state.get("stoerungen") or {}
    hinzu, weg = wachhund.vergleichen(stoerungen, gemerkt)
    state["stoerungen"] = wachhund.als_gedaechtnis(stoerungen)
    if not hinzu and not weg:
        return

    for eintrag in hinzu:
        logbuch.eintragen(eintrag["raum"], "Störung", eintrag["text"],
                          eintrag["entity_id"],
                          art="fehler" if eintrag["schwere"] == "fehler" else "warnung")
    for eintrag in weg:
        logbuch.eintragen(eintrag["raum"], "wieder da",
                          f"{eintrag['name']} meldet sich wieder",
                          eintrag["entity_id"], art="gut")

    meldung = wachhund.meldung_bauen(hinzu, weg)
    if not meldung:
        return
    titel, text = meldung
    dienste = (einstellungen.get("wachhund") or {}).get("melden_an") or []
    if not dienste:
        _LOGGER.warning("Störung, aber kein Meldeweg eingestellt: %s", titel)
        return
    for dienst in dienste:
        ha_api.notify(dienst, titel, text)


def _takt_schleife() -> None:
    while True:
        bericht = _takt_ausfuehren()
        anzahl = len(bericht.get("rollos") or [])
        if bericht.get("fehler"):
            _LOGGER.warning("Takt mit Fehler: %s", bericht["fehler"])
        elif bericht.get("hinweis"):
            _LOGGER.info("Takt ausgesetzt: %s", bericht["hinweis"])
        else:
            gefahren = sum(1 for r in bericht.get("rollos") or [] if r.get("gefahren"))
            _LOGGER.info("Takt: %d Rollos%s%s", anzahl,
                         f", {gefahren} gefahren" if gefahren else "",
                         " (Trockenlauf)" if bericht.get("trockenlauf") else "")
        pause = int(store.load_config()["einstellungen"].get("takt_sekunden", 120))
        _wecker.wait(timeout=pause)
        _wecker.clear()


def _sofort_rechnen() -> None:
    """Den Regeltakt vorziehen, etwa nach einer Änderung in der Oberfläche."""
    _wecker.set()


# ---------------------------------------------------------------- MQTT ----

def _mqtt_starten() -> None:
    global _publisher
    host = os.environ.get("MQTT_HOST")
    if not host:
        _LOGGER.warning("Kein MQTT – die Statusentitäten und Schalter fehlen in HA")
        return
    import mqtt_publisher
    _publisher = mqtt_publisher.Publisher(
        host, int(os.environ.get("MQTT_PORT", 1883)),
        os.environ.get("MQTT_USER"), os.environ.get("MQTT_PASSWORD"))

    def bereit() -> None:
        _discovery_auffrischen()
        if _letzter_bericht.get("zeit"):
            _publisher.publish_status(_letzter_bericht, store.load_config())

    _publisher.on_ready = bereit
    _publisher.on_schalter = _schalter_setzen
    _publisher.on_rollo = _rollo_schalten
    _publisher.on_plan = _plan_schalten
    _publisher.on_eigen = _eigenen_schalter_setzen
    _publisher.on_command = _befehl
    _publisher.start()


def _discovery_auffrischen() -> None:
    """Entitäten neu anmelden – und die weggefallener Räume abräumen."""
    if _publisher is None or not _publisher.connected.is_set():
        return
    try:
        config = store.load_config()
        rollos = config["rollos"]
        plaene = config["plaene"]
        eigene = config["einstellungen"].get("eigene_schalter") or []
        zustand = store.load_state()

        aktuell = _publisher.rollo_schluessel(rollos)
        veraltet = [k for k in (zustand.get("veroeffentlichte_rollos") or [])
                    if k not in aktuell]
        if veraltet:
            _publisher.entferne_rollos(veraltet)

        plan_aktuell = _publisher.plan_schluessel(plaene)
        plan_veraltet = [k for k in (zustand.get("veroeffentlichte_plaene") or [])
                         if k not in plan_aktuell]
        if plan_veraltet:
            _publisher.entferne_plaene(plan_veraltet)

        # Dasselbe für die eigenen Schalter: Ein gelöschter muss aus Home
        # Assistant verschwinden, sonst bleibt er als Karteileiche stehen –
        # die Discovery-Nachricht ist „retained“ und überlebt das Add-on.
        eigen_aktuell = _publisher.eigene_schluessel(eigene)
        eigen_veraltet = [k for k in (zustand.get("veroeffentlichte_schalter") or [])
                          if k not in eigen_aktuell]
        if eigen_veraltet:
            _publisher.entferne_eigene(eigen_veraltet)

        namen = {}
        try:
            namen = {e["entity_id"]: e["name"]
                     for e in ha_api.cover_entities()}
        except Exception:  # noqa: BLE001 – ohne Namen tut es auch die Kurzform
            pass
        _publisher.publish_discovery(rollos, plaene, namen)
        _publisher.publish_eigene(eigene, zustand.get("schalter") or {})
        zustand["veroeffentlichte_rollos"] = aktuell
        zustand["veroeffentlichte_plaene"] = plan_aktuell
        zustand["veroeffentlichte_schalter"] = eigen_aktuell
        store.save_state(zustand)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Discovery fehlgeschlagen: %s", err)


def _eigenen_schalter_setzen(kennung: str, wert: str) -> None:
    """Einen eigenen Schalter aus Home Assistant heraus stellen."""
    config = store.load_config()
    eintrag = next((e for e in config["einstellungen"].get("eigene_schalter") or []
                    if e["id"] == kennung), None)
    if eintrag is None:
        _LOGGER.warning("Unbekannter eigener Schalter: %s", kennung)
        return

    if eintrag["art"] == "auswahl":
        if wert not in eintrag["optionen"]:
            _LOGGER.warning("„%s“ kennt die Stellung %r nicht", eintrag["name"], wert)
            return
        neu = wert
    else:
        neu = "on" if str(wert).strip().upper() == "ON" else "off"

    with _takt_lock:
        state = store.load_state()
        state.setdefault("schalter", {})[kennung] = neu
        store.save_state(state)
    if _publisher is not None:
        _publisher.publish_eigenen_zustand(kennung, neu)
    _LOGGER.info("Schalter „%s“ → %s", eintrag["name"], neu)
    _sofort_rechnen()


def _schalter_setzen(key: str, an: bool) -> None:
    """Einen der Funktionsschalter aus Home Assistant umlegen."""
    if key == "automatik":
        store.update_einstellungen({"automatik": an})
    elif key == "beschattung":
        store.update_einstellungen({"beschattung": {"aktiv": an}})
    elif key == "urlaubssimulation":
        store.update_einstellungen({"urlaub": {"modus": "simulation" if an else "zu"}})
    elif key == "trockenlauf_schalter":
        vorher = store.load_config()["einstellungen"].get("trockenlauf")
        store.update_einstellungen({"trockenlauf": an})
        if vorher and not an:
            _durchsetzen()
    else:
        _LOGGER.warning("Unbekannter Schalter: %s", key)
        return
    _LOGGER.info("Schalter %s → %s", key, "an" if an else "aus")
    _sofort_rechnen()


def _rollo_schalten(entity_id: str, an: bool) -> None:
    config = store.load_config()
    for rollo in config["rollos"]:
        if rollo["entity_id"] == entity_id:
            store.update_rollo(entity_id, {**rollo, "aktiv": an})
            _LOGGER.info("Rollo %s → %s", entity_id, "an" if an else "aus")
            _sofort_rechnen()
            return
    _LOGGER.warning("Rollo %s nicht eingerichtet", entity_id)


def _plan_schalten(plan_id: str, an: bool) -> None:
    config = store.load_config()
    for plan in config["plaene"]:
        if plan["id"] == plan_id:
            store.update_plan(plan_id, {**plan, "aktiv": an})
            _LOGGER.info("Zeitplan %s → %s", plan["name"], "an" if an else "aus")
            _sofort_rechnen()
            return
    _LOGGER.warning("Zeitplan %s nicht gefunden", plan_id)


def _befehl(payload: dict) -> None:
    """Sonderbefehle aus der Lovelace-Karte."""
    was = payload.get("befehl")
    if was == "fahren":
        _rollo_fahren(payload.get("rollo"), payload.get("position"))
    elif was == "takt":
        _sofort_rechnen()
    elif was == "handbetrieb_aufheben":
        _handbetrieb_aufheben(payload.get("rollo"))
    elif was == "durchsetzen":
        _durchsetzen()
    else:
        _LOGGER.warning("Unbekannter Befehl: %s", payload)


def _rollo_fahren(entity_id: str | None, position) -> dict:
    """Ein Rollo von Hand auf eine Stellung fahren."""
    config = store.load_config()
    rollo = next((r for r in config["rollos"] if r["entity_id"] == entity_id), None)
    if rollo is None:
        raise store.ValidationError("Rollo nicht eingerichtet")
    try:
        ziel = max(0, min(100, int(position)))
    except (TypeError, ValueError) as err:
        raise store.ValidationError("Stellung: Zahl von 0 bis 100 erwartet") from err

    with _takt_lock:
        state = store.load_state()
        zustand = ha_api.get_state(entity_id)
        erfolg = ha_api.set_position(entity_id, ziel, zustand)
        if erfolg:
            # Von Hand gefahren heißt: Der Planer hält sich hier zurück, bis
            # der nächste Schaltpunkt fällig wird.
            state["rollos"].setdefault(entity_id, {}).update(
                ziel=ziel, gesetzt_am=datetime.now().isoformat(timespec="seconds"),
                grund="von Hand über die Karte", manuell_bis=None)
            store.save_state(state)
    if erfolg:
        logbuch.eintragen(rollo.get("name") or entity_id, f"{ziel} %",
                          "von Hand gestellt", entity_id)
    return {"gefahren": erfolg, "position": ziel}


def _durchsetzen() -> None:
    """Den gemerkten Stand verwerfen – der geltende Schaltpunkt wird neu ausgeführt.

    Nötig beim Ausschalten des Trockenlaufs: Im Trockenlauf merkt sich der
    Planer die Schaltpunkte als erledigt, damit das Protokoll nicht alle zwei
    Minuten dasselbe meldet. Ohne dieses Verwerfen bliebe danach alles stehen,
    wo es steht, bis zum nächsten Schaltpunkt – wer den Trockenlauf beendet,
    erwartet aber genau das Gegenteil.

    Derselbe Griff hilft nach einem Stromausfall oder wenn jemand alle Rollos
    von Hand verstellt hat.
    """
    # Unter demselben Schloss wie der Takt: Sonst lädt ein gerade laufender
    # Takt den Zustand vor dem Verwerfen und schreibt ihn hinterher zurück –
    # das Verwerfen wäre spurlos verschwunden.
    with _takt_lock:
        state = store.load_state()
        for daten in (state.get("rollos") or {}).values():
            daten["letzter_punkt"] = None
            daten["beschattet"] = False
            daten["manuell_bis"] = None
        store.save_state(state)
    _LOGGER.info("Gemerkter Stand verworfen – der Plan wird neu durchgesetzt")
    _sofort_rechnen()


def _handbetrieb_aufheben(entity_id: str | None) -> int:
    """Die Schonfrist nach Handbetrieb vorzeitig beenden."""
    config = store.load_config()
    anzahl = 0
    with _takt_lock:
        state = store.load_state()
        for rollo in config["rollos"]:
            eid = rollo["entity_id"]
            if entity_id not in (None, eid):
                continue
            daten = state["rollos"].get(eid) or {}
            if daten.get("manuell_bis"):
                daten["manuell_bis"] = None
                anzahl += 1
            # Damit der Plan sofort wieder greift, muss auch der zuletzt
            # ausgeführte Schaltpunkt vergessen werden – sonst wartet das
            # Rollo auf den nächsten.
            daten["letzter_punkt"] = None
            state["rollos"][eid] = daten
        store.save_state(state)
    _sofort_rechnen()
    return anzahl


def _in_eigene_umwandeln(rollos: list[dict], plaene: list[dict],
                         einstellungen: dict,
                         index: dict) -> tuple[list[dict], list[dict], list[dict], dict]:
    """Fremde Helfer durch eigene Schalter des Planers ersetzen.

    Aus der Übernahme kommen Bedingungen auf fremde `input_boolean` und
    `input_select` – die gab es in diesem Haus schon. Bei einer
    Neuinstallation gibt es sie **nicht**, und ein Zeitplan, der auf eine
    Entität zeigt, die niemand angelegt hat, schaltet nie.

    Deshalb legt der Planer eigene an: gleicher Name, gleiche Stellungen,
    übernommener Stand. Danach zeigen alle Bedingungen auf ihn selbst, und die
    alten Helfer können weg.

    Liefert (Rollos, Zeitpläne, Schalterliste, Anfangszustände).
    """
    schalter = list(einstellungen.get("eigene_schalter") or [])
    # Zugeordnet wird über die **Quell-Entität**, nicht über den Namen: Zwei
    # verschiedene Helfer können gleich heißen, und die dürfen nicht zu einem
    # Schalter verschmelzen. Die Quelle bleibt am Schalter stehen, damit ein
    # zweiter Durchlauf denselben wiederfindet statt einen weiteren anzulegen.
    nach_quelle = {e["quelle"]: e for e in schalter if e.get("quelle")}
    vergebene_namen = {e["name"] for e in schalter}
    zuordnung: dict[str, str] = {}
    zustaende: dict[str, str] = {}

    def sauberer_name(roh: str) -> str:
        """Die Vorsilben der alten Helfer weglassen.

        Aus dem Namen wird die entity_id – `switch.rolloplaner_helfer_
        rollosteuerung_buero` will niemand lesen. Bei einer Namensgleichheit
        wird durchnummeriert, damit zwei Schalter unterscheidbar bleiben.
        """
        name = re.sub(r"^(Helfer|Rollosteuerung)\s*-?\s*", "", roh, flags=re.I)
        name = re.sub(r"^(Helfer|Rollosteuerung)\s*-?\s*", "", name, flags=re.I)
        name = re.sub(r"^Rollo\s+", "", name, flags=re.I).strip() or roh
        name = name[:1].upper() + name[1:]
        if name not in vergebene_namen:
            return name
        for n in range(2, 50):
            kandidat = f"{name} {n}"
            if kandidat not in vergebene_namen:
                return kandidat
        return roh

    def eigenen_finden(entity: str) -> str | None:
        """Die Ziel-ID für eine fremde Entität – notfalls neu angelegt."""
        if store.eigener_schalter(entity):
            return None                      # ist schon einer
        if entity in zuordnung:
            return zuordnung[entity]
        zustand = index.get(entity)
        if zustand is None:
            return None                      # gibt es nicht – dann nichts anfassen
        attrs = zustand.get("attributes") or {}
        name = attrs.get("friendly_name") or entity
        optionen = [str(o) for o in (attrs.get("options") or [])]
        art = "auswahl" if optionen else "schalter"

        vorhanden = nach_quelle.get(entity)
        if vorhanden is None:
            anzeige = sauberer_name(name)
            vergebene_namen.add(anzeige)
            vorhanden = {"id": uuid.uuid4().hex[:8], "name": anzeige, "art": art,
                         "optionen": optionen,
                         "vorgabe": (zustand.get("state") if art == "auswahl"
                                     else ("on" if zustand.get("state") == "on" else "off")),
                         "icon": attrs.get("icon") or "",
                         "quelle": entity}
            schalter.append(vorhanden)
            nach_quelle[entity] = vorhanden
        zuordnung[entity] = vorhanden["id"]
        # Den jetzigen Stand mitnehmen: Wer den Öffner gestern abgeschaltet
        # hat, will ihn nach der Umstellung nicht wieder an vorfinden.
        zustaende[vorhanden["id"]] = str(zustand.get("state"))
        return vorhanden["id"]

    def punkte_umbiegen(punkte: list) -> None:
        for punkt in punkte or []:
            for bedingung in punkt.get("wenn") or []:
                kennung = eigenen_finden(bedingung.get("entity") or "")
                if kennung:
                    bedingung["entity"] = store.EIGEN_PREFIX + kennung

    neue_rollos = json.loads(json.dumps(rollos))
    neue_plaene = json.loads(json.dumps(plaene))
    for rollo in neue_rollos:
        punkte_umbiegen(rollo.get("zeitplan"))
    for plan in neue_plaene:
        punkte_umbiegen(plan.get("zeitplan"))
    return neue_rollos, neue_plaene, schalter, zustaende


# ------------------------------------------------------------ Oberfläche ----

@app.route("/")
def index():
    return send_from_directory(FRONTEND, "index.html")


@app.route("/<path:datei>")
def statisch(datei: str):
    return send_from_directory(FRONTEND, datei)


# ------------------------------------------------------------------ API ----

@app.route("/api/status")
def api_status():
    return jsonify(_letzter_bericht)


@app.route("/api/takt", methods=["POST"])
def api_takt():
    return jsonify(_takt_ausfuehren())


@app.route("/api/config")
def api_config():
    config = store.load_config()
    config["version"] = VERSION
    return jsonify(config)


@app.route("/api/rollos", methods=["GET", "PUT"])
def api_rollos():
    if request.method == "GET":
        return jsonify(store.load_config()["rollos"])
    try:
        ergebnis = store.rollos_setzen((request.get_json(force=True) or {}).get("rollos"))
    except store.ValidationError as err:
        return jsonify({"fehler": str(err)}), 400
    _discovery_auffrischen()
    _sofort_rechnen()
    return jsonify(ergebnis)


@app.route("/api/rollos/<path:entity_id>", methods=["PUT", "DELETE"])
def api_rollo(entity_id: str):
    if request.method == "DELETE":
        if not store.delete_rollo(entity_id):
            return jsonify({"fehler": "Rollo nicht eingerichtet"}), 404
        _discovery_auffrischen()
        _sofort_rechnen()
        return jsonify({"geloescht": entity_id})
    try:
        ergebnis = store.update_rollo(entity_id, request.get_json(force=True) or {})
    except store.ValidationError as err:
        return jsonify({"fehler": str(err)}), 400
    _discovery_auffrischen()
    _sofort_rechnen()
    return jsonify(ergebnis)


@app.route("/api/plaene", methods=["GET", "POST", "PUT"])
def api_plaene():
    if request.method == "GET":
        return jsonify(store.load_config()["plaene"])
    try:
        if request.method == "POST":
            ergebnis = store.add_plan(request.get_json(force=True) or {})
        else:
            ergebnis = store.plaene_setzen(
                (request.get_json(force=True) or {}).get("plaene"))
    except store.ValidationError as err:
        return jsonify({"fehler": str(err)}), 400
    _discovery_auffrischen()
    _sofort_rechnen()
    return jsonify(ergebnis), 201 if request.method == "POST" else 200


@app.route("/api/plaene/<plan_id>", methods=["PUT", "DELETE"])
def api_plan(plan_id: str):
    try:
        if request.method == "DELETE":
            if not store.delete_plan(plan_id):
                return jsonify({"fehler": "Zeitplan nicht gefunden"}), 404
            _discovery_auffrischen()
            _sofort_rechnen()
            return jsonify({"geloescht": plan_id})
        ergebnis = store.update_plan(plan_id, request.get_json(force=True) or {})
    except store.ValidationError as err:
        return jsonify({"fehler": str(err)}), 400
    _discovery_auffrischen()
    _sofort_rechnen()
    return jsonify(ergebnis)


@app.route("/api/einstellungen", methods=["GET", "PUT"])
def api_einstellungen():
    if request.method == "GET":
        return jsonify(store.load_config()["einstellungen"])
    vorher = store.load_config()["einstellungen"].get("trockenlauf")
    try:
        neu = store.update_einstellungen(request.get_json(force=True) or {})
    except store.ValidationError as err:
        return jsonify({"fehler": str(err)}), 400
    if vorher and not neu.get("trockenlauf"):
        _durchsetzen()
    else:
        _sofort_rechnen()
    return jsonify(neu)


@app.route("/api/schalter", methods=["GET", "PUT"])
def api_schalter():
    """Die eigenen Schalter des Planers verwalten."""
    config = store.load_config()
    if request.method == "GET":
        state = store.load_state()
        gemerkt = state.get("schalter") or {}
        return jsonify([{**e, "zustand": gemerkt.get(e["id"], e["vorgabe"])}
                        for e in config["einstellungen"].get("eigene_schalter") or []])
    try:
        liste = store.validate_schalter((request.get_json(force=True) or {}).get("schalter"))
    except store.ValidationError as err:
        return jsonify({"fehler": str(err)}), 400

    # Wird ein Schalter gelöscht, der noch als Bedingung in Gebrauch ist, wäre
    # der betroffene Schaltpunkt stumm: Eine Bedingung auf einen Schalter, den
    # es nicht gibt, trifft nie zu. Das muss auffallen.
    vorhanden = {e["id"] for e in liste}
    benutzt = _benutzte_schalter(config)
    fehlend = sorted(benutzt - vorhanden)
    if fehlend:
        namen = {e["id"]: e["name"]
                 for e in config["einstellungen"].get("eigene_schalter") or []}
        return jsonify({"fehler": "Noch in Gebrauch: "
                        + ", ".join(namen.get(i, i) for i in fehlend)}), 400

    store.update_einstellungen({"eigene_schalter": liste})
    _discovery_auffrischen()
    _sofort_rechnen()
    return jsonify(liste)


@app.route("/api/schalter/uebernehmen", methods=["POST"])
def api_schalter_uebernehmen():
    """Die fremden Helfer der eingerichteten Räume durch eigene ersetzen."""
    config = store.load_config()
    index = {s["entity_id"]: s for s in ha_api.get_states()}
    if not index:
        return jsonify({"fehler": "Keine Zustände von Home Assistant erhalten"}), 503

    rollos, plaene, schalter, zustaende = _in_eigene_umwandeln(
        config["rollos"], config["plaene"], config["einstellungen"], index)
    neu = len(schalter) - len(config["einstellungen"].get("eigene_schalter") or [])
    if not neu and rollos == config["rollos"] and plaene == config["plaene"]:
        return jsonify({"angelegt": 0, "hinweis": "Es gab nichts umzustellen"})

    store.update_einstellungen({"eigene_schalter": schalter})
    store.plaene_setzen(plaene)
    store.rollos_setzen(rollos)
    with _takt_lock:
        state = store.load_state()
        state.setdefault("schalter", {}).update(zustaende)
        store.save_state(state)

    _discovery_auffrischen()
    _sofort_rechnen()
    logbuch.eintragen("Einrichtung", "umgestellt",
                      f"{neu} eigene Schalter angelegt, "
                      "die Zeitpläne zeigen jetzt auf den Planer selbst")
    return jsonify({"angelegt": neu,
                    "schalter": [{"name": e["name"], "art": e["art"]} for e in schalter]})


def _benutzte_schalter(config: dict) -> set:
    """Welche eigenen Schalter als Bedingung in einem Zeitplan stehen."""
    benutzt = set()
    for punkte in ([r.get("zeitplan") for r in config.get("rollos") or []]
                   + [p.get("zeitplan") for p in config.get("plaene") or []]):
        for punkt in punkte or []:
            for bedingung in punkt.get("wenn") or []:
                kennung = store.eigener_schalter(bedingung.get("entity") or "")
                if kennung:
                    benutzt.add(kennung)
    return benutzt


@app.route("/api/entitaeten")
def api_entitaeten():
    states = ha_api.get_states()
    bereiche = ha_api.bereiche_je_entitaet(("cover", "binary_sensor"))
    daten = ha_api.sensor_candidates(states, bereiche={
        eid: bereich for eid, bereich in bereiche.items()
        if eid.startswith("binary_sensor.")})
    daten["rollos"] = ha_api.cover_entities(states, bereiche)
    daten["personen"] = ha_api.person_entities(states)
    daten["notify"] = ha_api.notify_dienste()
    return jsonify(daten)


@app.route("/api/uebernahme", methods=["GET", "POST"])
def api_uebernahme():
    """Vorschlag aus den vorhandenen Automationen – ansehen und übernehmen."""
    config = store.load_config()
    einstellungen = config["einstellungen"]
    bereiche = ha_api.bereiche_je_entitaet(("cover",))
    states = ha_api.get_states()
    cover = ha_api.cover_entities(states, bereiche)
    vorschlag = uebernahme.vorschlag(
        bereiche, einstellungen.get("schulfrei_entity"),
        einstellungen.get("schulfrei_morgen_entity"), cover)

    if request.method == "GET":
        eingerichtet = {r["entity_id"] for r in config["rollos"]}
        for rollo in vorschlag["rollos"]:
            rollo["schon_da"] = rollo["entity_id"] in eingerichtet
        return jsonify(vorschlag)

    nutzlast = request.get_json(force=True) or {}
    gewuenscht = nutzlast.get("rollos")
    if gewuenscht is None:
        gewuenscht = vorschlag["rollos"]
    plaene = nutzlast.get("plaene")
    if plaene is None:
        plaene = vorschlag["plaene"]

    # Nur Zeitpläne behalten, denen auch jemand folgt – sonst bleiben nach
    # einer Auswahl leere Pläne stehen.
    gebraucht = {r.get("plan") for r in gewuenscht if r.get("plan")}
    plaene = [p for p in plaene if p["id"] in gebraucht]

    # Vorgabe: gleich auf eigene Schalter umstellen. Ein übernommener Zeitplan
    # soll nicht davon abhängen, dass jemand vorher von Hand die passenden
    # Helfer angelegt hat – nach einer Neuinstallation gibt es die nicht.
    schalter, zustaende = None, {}
    if nutzlast.get("eigene_schalter", True):
        index = {s["entity_id"]: s for s in states}
        gewuenscht, plaene, schalter, zustaende = _in_eigene_umwandeln(
            gewuenscht, plaene, einstellungen, index)

    try:
        if schalter:
            store.update_einstellungen({"eigene_schalter": schalter})
            with _takt_lock:
                state = store.load_state()
                state.setdefault("schalter", {}).update(zustaende)
                store.save_state(state)
        store.plaene_setzen(plaene)
        # Die Felder aus dem Vorschlag, die nicht ins Modell gehören, fallen
        # bei der Prüfung von selbst weg.
        store.rollos_setzen(gewuenscht)
    except store.ValidationError as err:
        return jsonify({"fehler": str(err)}), 400

    _discovery_auffrischen()
    _sofort_rechnen()
    logbuch.eintragen("Einrichtung", "übernommen",
                      f"{len(gewuenscht)} Rollos, {len(plaene)} gemeinsame Zeitpläne, "
                      f"{len(schalter or [])} eigene Schalter")
    return jsonify({"rollos": len(gewuenscht), "plaene": len(plaene),
                    "schalter": len(schalter or [])})


@app.route("/api/vorschlag/abweisen", methods=["POST"])
def api_vorschlag_abweisen():
    name = (request.get_json(force=True) or {}).get("name")
    if not name:
        return jsonify({"fehler": "Name fehlt"}), 400
    einstellungen = store.load_config()["einstellungen"]
    ignoriert = set(einstellungen.get("ignorierte_vorschlaege") or [])
    ignoriert.add(str(name))
    store.update_einstellungen({"ignorierte_vorschlaege": sorted(ignoriert)})
    return jsonify({"ignoriert": sorted(ignoriert)})


@app.route("/api/fahren", methods=["POST"])
def api_fahren():
    nutzlast = request.get_json(force=True) or {}
    try:
        ergebnis = _rollo_fahren(nutzlast.get("rollo"), nutzlast.get("position"))
    except store.ValidationError as err:
        return jsonify({"fehler": str(err)}), 400
    return jsonify(ergebnis)


@app.route("/api/handbetrieb", methods=["DELETE"])
def api_handbetrieb():
    return jsonify({"aufgehoben": _handbetrieb_aufheben(request.args.get("rollo"))})


@app.route("/api/durchsetzen", methods=["POST"])
def api_durchsetzen():
    _durchsetzen()
    return jsonify({"verworfen": True})


@app.route("/api/zustand")
def api_zustand():
    """Der Laufzeitzustand – was der Planer sich gemerkt hat."""
    state = store.load_state()
    return jsonify({
        "rollos": state.get("rollos") or {},
        "rauch_bis": state.get("rauch_bis"),
        "simulation": state.get("simulation") or {},
        "schulfrei_verlauf": state.get("schulfrei_verlauf") or {},
    })


@app.route("/api/wachhund/probe", methods=["POST"])
def api_wachhund_probe():
    """Eine Probemeldung über die eingestellten Meldewege schicken."""
    einstellungen = store.load_config()["einstellungen"]
    dienste = (einstellungen.get("wachhund") or {}).get("melden_an") or []
    if not dienste:
        return jsonify({"fehler": "Kein Meldeweg eingestellt"}), 400
    erfolge = [d for d in dienste
               if ha_api.notify(d, "Rolloplaner",
                                "Probemeldung – der Meldeweg funktioniert.")]
    return jsonify({"gesendet": erfolge,
                    "fehlgeschlagen": [d for d in dienste if d not in erfolge]})


@app.route("/api/logbuch", methods=["GET", "DELETE"])
def api_logbuch():
    if request.method == "DELETE":
        logbuch.leeren()
        return jsonify({"geleert": True})
    return jsonify(logbuch.lesen(int(request.args.get("grenze", 200))))


@app.route("/api/gesundheit")
def api_gesundheit():
    """Eine Selbstauskunft: Was steht, was fehlt, was ist verdächtig.

    Gedacht für den Blick nach der Einrichtung – und für die Frage „warum
    fährt das Rollo nicht?“, die sich fast immer mit einer dieser Auskünfte
    beantworten lässt.
    """
    config = store.load_config()
    einstellungen = config["einstellungen"]
    states = ha_api.get_states()
    index = {s["entity_id"]: s for s in states}
    state = store.load_state()
    plaene = {p["id"]: p for p in config["plaene"]}
    eigene_ids = {e["id"] for e in einstellungen.get("eigene_schalter") or []}

    befunde = []

    def melden(schwere: str, text: str, wo: str = "") -> None:
        befunde.append({"schwere": schwere, "text": text, "raum": wo})

    def pruefe_entitaet(eid: str, was: str, wo: str) -> None:
        kennung = store.eigener_schalter(eid)
        if kennung is not None:
            if kennung not in eigene_ids:
                melden("fehler", f"{was}: diesen eigenen Schalter gibt es nicht mehr", wo)
        elif eid not in index:
            melden("fehler", f"{was} {eid} fehlt", wo)

    if not ha_api.available():
        melden("fehler", "Kein SUPERVISOR_TOKEN – der Planer kann nichts fahren")
    if einstellungen.get("trockenlauf"):
        melden("hinweis", "Trockenlauf ist an: Der Planer rechnet, fährt aber nichts")
    if not einstellungen.get("automatik"):
        melden("warnung", "Die Automatik ist ausgeschaltet")

    for schluessel, beschreibung in (("schulfrei_entity", "Schulfrei heute"),
                                     ("schulfrei_morgen_entity", "Schulfrei morgen"),
                                     ("urlaub_entity", "Urlaub"),
                                     ("sonne_entity", "Sonne"),
                                     ("aussen_entity", "Außentemperatur")):
        eid = einstellungen.get(schluessel)
        if eid and eid not in index:
            melden("fehler", f"{beschreibung}: {eid} gibt es in Home Assistant nicht")

    for rollo in config["rollos"]:
        eid = rollo["entity_id"]
        name = regelung.anzeigename(rollo, index)
        punkte = (plaene[rollo["plan"]]["zeitplan"] if rollo.get("plan") in plaene
                  else rollo.get("zeitplan") or [])
        if rollo.get("plan") and rollo["plan"] not in plaene:
            melden("fehler", "Folgt einem Zeitplan, den es nicht mehr gibt", name)
        elif not punkte:
            melden("warnung", "Kein Schaltpunkt – dieses Rollo fährt nie", name)
        if rollo.get("beschattung") and rollo.get("ausrichtung") is None:
            melden("warnung", "Hitzeschutz ohne Ausrichtung – er bleibt wirkungslos", name)
        if rollo.get("art") in store.TUERARTEN and not rollo.get("fenster"):
            melden("hinweis",
                   "Tür ohne Kontakt: Der Planer kann nicht merken, ob jemand "
                   "draußen steht, wenn er zufährt", name)
        for kontakt in rollo.get("fenster") or []:
            pruefe_entitaet(kontakt, "Fensterkontakt", name)
        for punkt in punkte:
            for bedingung in punkt.get("wenn") or []:
                pruefe_entitaet(bedingung.get("entity") or "", "Bedingung", name)

        zustand = index.get(eid)
        if zustand is None:
            melden("fehler", f"{eid} gibt es in Home Assistant nicht", name)
        elif zustand.get("state") == "unavailable":
            melden("fehler", "Nicht erreichbar", name)
        elif not ha_api.kann_position(zustand):
            melden("hinweis",
                   "Kennt keine Zwischenstellung – der Hitzeschutz fährt ganz zu", name)

    # Rollos, die es gibt, die aber nicht eingerichtet sind.
    eingerichtet = {r["entity_id"] for r in config["rollos"]}
    for eintrag in ha_api.cover_entities(states):
        if eintrag["entity_id"] not in eingerichtet:
            melden("hinweis", f"{eintrag['name']} ({eintrag['entity_id']}) "
                              "ist nicht eingerichtet")

    # Zeitpläne ohne Folger legen eine Entität an, die nichts tut.
    for plan in config["plaene"]:
        if not any(r.get("plan") == plan["id"] for r in config["rollos"]):
            melden("hinweis", f"Dem Zeitplan „{plan['name']}“ folgt kein Rollo")

    # Läuft noch eine der alten Automationen mit? Gemeint sind nur die, die der
    # Planer ersetzt – also die zeitgesteuerten. „RM Alarm öffnet alle Rollos“
    # und „Rollos folgen dem Urlaub“ lösen über Melder aus; die sollen
    # weiterlaufen, und eine Warnung über sie wäre eine Aufforderung, genau das
    # Falsche abzuschalten.
    ersetzbar = set()
    try:
        for automation in uebernahme.automationen_lesen():
            if not isinstance(automation, dict) or not automation.get("alias"):
                continue
            treffer: list = []
            uebernahme._aktionen_durchgehen(
                automation.get("actions") or automation.get("action"), treffer)
            if treffer and uebernahme._ausloeser(automation):
                ersetzbar.add(automation["alias"])
    except Exception:  # noqa: BLE001 – die Warnung ist keinen Absturz wert
        _LOGGER.exception("Automationen konnten nicht gelesen werden")

    doppelt = [s for s in states
               if s["entity_id"].startswith("automation.")
               and s.get("state") == "on"
               and (s.get("attributes") or {}).get("friendly_name") in ersetzbar]
    if doppelt and config["rollos"]:
        namen = [(s.get("attributes") or {}).get("friendly_name") for s in doppelt]
        melden("warnung",
               f"{len(doppelt)} Rollo-Automationen sind noch aktiv – sie fahren gegen "
               "den Planer an: " + ", ".join(namen[:6])
               + (" …" if len(namen) > 6 else ""))

    offene_hand = [eid for eid, daten in (state.get("rollos") or {}).items()
                   if daten.get("manuell_bis")]
    if offene_hand:
        melden("hinweis", f"{len(offene_hand)} Rollos stehen im Handbetrieb")

    # Hängt noch ein Zeitplan an einem fremden Helfer? Das läuft hier, aber
    # nach einer Neuinstallation anderswo nicht – dort gibt es den Helfer nicht.
    fremde = sorted({
        b.get("entity") for punkte in
        ([r.get("zeitplan") for r in config["rollos"]]
         + [p.get("zeitplan") for p in config["plaene"]])
        for punkt in punkte or [] for b in punkt.get("wenn") or []
        if b.get("entity") and not store.eigener_schalter(b["entity"])})
    if fremde:
        melden("hinweis",
               f"{len(fremde)} Bedingungen hängen an fremden Helfern – der Planer kann "
               "sie unter „Schalter“ durch eigene ersetzen: " + ", ".join(fremde[:4])
               + (" …" if len(fremde) > 4 else ""))

    # Ein Schaltpunkt, dessen Bedingung auf einen ausgeschalteten Schalter
    # zeigt, ist stillgelegt – er greift nie, und das sieht man ihm im
    # Zeitplan nicht an. Gemeldet wird nur, wenn der Schalter sonst nirgends
    # gebraucht wird: Ein geteilter Schalter ist absichtlich aus.
    schalterstand = {e["id"]: e for e in einstellungen.get("eigene_schalter") or []}
    laufzeit = state.get("schalter") or {}
    zaehler: dict[str, int] = {}
    quellen = ([(regelung.anzeigename(r, index), r.get("zeitplan")) for r in config["rollos"]]
               + [(f"Zeitplan {p['name']}", p.get("zeitplan")) for p in config["plaene"]])
    for _, punkte in quellen:
        for punkt in punkte or []:
            for bedingung in punkt.get("wenn") or []:
                kennung = store.eigener_schalter(bedingung.get("entity") or "")
                if kennung:
                    zaehler[kennung] = zaehler.get(kennung, 0) + 1
    for wo, punkte in quellen:
        for punkt in punkte or []:
            for bedingung in punkt.get("wenn") or []:
                kennung = store.eigener_schalter(bedingung.get("entity") or "")
                eintrag = schalterstand.get(kennung or "")
                if eintrag is None or zaehler.get(kennung, 0) != 1:
                    continue
                jetzt = str(laufzeit.get(kennung, eintrag["vorgabe"]))
                if jetzt != str(bedingung.get("wert")):
                    melden("hinweis",
                           f"„{zeitplan.beschreibung(punkt)}“ ist stillgelegt: "
                           f"„{eintrag['name']}“ steht auf {jetzt}, gebraucht würde "
                           f"{bedingung.get('wert')}", wo)

    unbenutzt = [e["name"] for e in einstellungen.get("eigene_schalter") or []
                 if e["id"] not in _benutzte_schalter(config)]
    for name in unbenutzt:
        melden("hinweis", f"Der eigene Schalter „{name}“ wird nirgends verwendet")

    return jsonify({
        "version": VERSION,
        "befunde": befunde,
        "zaehler": {
            "rollos": len(config["rollos"]),
            "plaene": len(config["plaene"]),
            "fehler": sum(1 for b in befunde if b["schwere"] == "fehler"),
            "warnungen": sum(1 for b in befunde if b["schwere"] == "warnung"),
        },
    })


# ---------------------------------------------------------------- Start ----

def main() -> None:
    _zeitzone_uebernehmen()
    # Eine Konfiguration aus 1.x lässt sich nicht weiterverwenden: Ein Raum mit
    # drei Rollos wusste nicht, welches davon eine Terrassentür ist. Sie wird
    # beiseitegelegt, nicht gelöscht – wer nachsehen will, was vorher galt,
    # findet sie unter /data.
    if store.ist_alte_konfiguration():
        ziel = store.alte_konfiguration_sichern()
        store.save_config({"einstellungen": store.load_config()["einstellungen"],
                           "plaene": [], "rollos": []})
        _LOGGER.warning(
            "Die Einrichtung stammt aus einer älteren Fassung und wurde nach %s "
            "gesichert. Der Planer steuert vorerst nichts – bitte im Reiter "
            "„Einrichtung“ neu übernehmen.", ziel)
    if not ha_api.available():
        _LOGGER.error("Kein SUPERVISOR_TOKEN – der Planer kann nichts fahren")
    cardsync.sync()
    _mqtt_starten()
    threading.Thread(target=_takt_schleife, name="regeltakt", daemon=True).start()
    _LOGGER.info("Rolloplaner %s startet auf Port %d", VERSION, PORT)
    app.run(host="0.0.0.0", port=PORT, threaded=True)


if __name__ == "__main__":
    main()
