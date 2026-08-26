"""Der Wächter: welches Rollo meldet sich nicht mehr, welches hängt fest.

Ein Rollladen fällt anders aus als ein Thermostat. Er meldet keine Temperatur,
an der man ihn beim Schweigen ertappen könnte – er meldet nur, wenn er fährt.
Ein Rollo, das zweimal am Tag fährt, meldet sich auch nur zweimal am Tag; die
Schweigefrist steht deshalb auf gut einem Tag und nicht auf sechs Stunden.

Die Rademacher-Gurtwickler bringen dafür etwas mit, das der Heizung fehlt:
Sie merken selbst, wenn sie beim Fahren gegen etwas stoßen oder blockiert
werden. Genau das ist der Ausfall, der auffallen muss – ein Rollo, das auf
halber Strecke hängt, sieht von außen aus wie eines, das dort stehen soll.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

import ha_api

_LOGGER = logging.getLogger(__name__)

# Art → (Beschreibung, Schwere)
ARTEN = {
    "weg": ("ist nicht erreichbar", "fehler"),
    "stumm": ("meldet sich nicht mehr", "fehler"),
    "hindernis": ("meldet ein Hindernis", "fehler"),
    "blockiert": ("meldet eine Blockade", "fehler"),
    "steht_falsch": ("steht nicht, wo es soll", "warnung"),
}

# Endungen der Diagnosemelder eines Rademacher-Gurtwicklers. Sie hängen am
# selben Gerät wie das Rollo, tragen aber eine eigene Entität.
DIAGNOSE = {
    "hindernis": "_obstacle_detection",
    "blockiert": "_blocking_detection",
}


def _zeit(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.fromisoformat(str(text).replace("Z", "+00:00")).astimezone()
    except ValueError:
        return None


def pruefen(config: dict, index: dict, jetzt: datetime,
            state: dict | None = None) -> list[dict]:
    """Alle eingerichteten Rollos durchsehen."""
    einstellungen = config["einstellungen"]
    wachhund = einstellungen.get("wachhund") or {}
    if not wachhund.get("aktiv", True):
        return []

    stumm_grenze = timedelta(hours=float(wachhund.get("stumm_stunden", 26.0)))
    hindernis_melden = bool(wachhund.get("hindernis_melden", True))
    stoerungen = []

    for raum in config["raeume"]:
        if not raum.get("aktiv", True):
            continue
        for eid in raum.get("rollos") or []:
            zustand = index.get(eid)
            name = ((zustand.get("attributes") or {}).get("friendly_name")
                    if zustand else None) or eid

            if zustand is None:
                stoerungen.append(_bauen(eid, name, raum, "weg",
                                         "in Home Assistant nicht gefunden"))
                continue
            if zustand.get("state") == "unavailable":
                stoerungen.append(_bauen(eid, name, raum, "weg", ""))
                continue

            if hindernis_melden:
                for art, endung in DIAGNOSE.items():
                    melder = index.get(eid.replace("cover.", "binary_sensor.") + endung)
                    if melder is not None and melder.get("state") == "on":
                        stoerungen.append(_bauen(eid, name, raum, art, ""))

            # Schweigen zählt erst, wenn das Gerät auch fahren sollte. Ein
            # Rollo in einem abgeschalteten Raum meldet zu Recht nichts.
            gesehen = _zeit(zustand.get("last_reported") or zustand.get("last_updated"))
            if gesehen is not None and jetzt.astimezone() - gesehen > stumm_grenze:
                stunden = (jetzt.astimezone() - gesehen).total_seconds() / 3600
                stoerungen.append(_bauen(eid, name, raum, "stumm",
                                         f"seit {stunden:.0f} Stunden"))
    return stoerungen


def _bauen(entity_id: str, name: str, raum: dict, art: str, zusatz: str) -> dict:
    beschreibung, schwere = ARTEN[art]
    text = f"{name} ({raum['name']}) {beschreibung}"
    if zusatz:
        text += f" – {zusatz}"
    return {"entity_id": entity_id, "name": name, "raum": raum["name"],
            "art": art, "schwere": schwere, "text": text}


def vergleichen(neu: list[dict], gemerkt: dict) -> tuple[list[dict], list[dict]]:
    """Was ist neu hinzugekommen, was hat sich erledigt?

    Verglichen wird über Entität **und** Art: Wird aus „meldet sich nicht mehr“
    ein „meldet ein Hindernis“, ist das eine neue Nachricht wert – das Rollo
    ist inzwischen nicht mehr nur still, sondern hängt fest.
    """
    jetzt = {f"{s['entity_id']}|{s['art']}": s for s in neu}
    vorher = set(gemerkt or {})
    hinzu = [s for schluessel, s in jetzt.items() if schluessel not in vorher]
    weg = [gemerkt[schluessel] for schluessel in vorher if schluessel not in jetzt]
    return hinzu, weg


def als_gedaechtnis(stoerungen: list[dict]) -> dict:
    return {f"{s['entity_id']}|{s['art']}": s for s in stoerungen}


def meldung_bauen(hinzu: list[dict], weg: list[dict]) -> tuple[str, str] | None:
    """Titel und Text für die Benachrichtigung – oder nichts zu melden."""
    if not hinzu and not weg:
        return None
    if hinzu:
        haengen = [s for s in hinzu if s["art"] in ("hindernis", "blockiert")]
        if haengen:
            titel = ("Rollo hängt fest" if len(haengen) == 1
                     else f"{len(haengen)} Rollos hängen fest")
        else:
            schwer = [s for s in hinzu if s["schwere"] == "fehler"]
            titel = ("Rollos: %d Antrieb%s meldet sich nicht" %
                     (len(schwer), "" if len(schwer) == 1 else "e")) if schwer \
                else "Rollos: Hinweis"
        zeilen = [s["text"] for s in hinzu]
        if weg:
            zeilen.append("")
            zeilen += ["Wieder in Ordnung: " + s["name"] for s in weg]
        return titel, "\n".join(zeilen)
    return ("Rollos: wieder in Ordnung",
            "\n".join(f"{s['name']} ({s['raum']}) meldet sich wieder" for s in weg))
