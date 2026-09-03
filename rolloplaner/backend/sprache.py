"""Die Sprache des Planers.

Ein eigenes Modul und kein `gettext`: Die Texte stehen hier als Tabelle, weil
eine dritte Sprache damit **nur eine Tabelle** ist – keine Werkzeugkette, keine
`.po`-Dateien, kein Übersetzungslauf beim Bauen. Das Add-on soll sich mit einem
Texteditor erweitern lassen.

Zwei Regeln, die den Rest tragen:

**Deutsch ist die Rückfallebene.** Fehlt ein Schlüssel in einer Sprache, kommt
der deutsche Text – nie der nackte Schlüssel. Eine halbfertige Übersetzung soll
eine halbfertige Oberfläche ergeben, keine kaputte.

**Sätze werden aus Bausteinen gebaut, und die Bausteine gehören der Sprache.**
„zu um Sonnenuntergang, spätestens 22:00" heißt auf Englisch „closed at sunset,
at the latest 22:00" – andere Wortstellung, andere Fügung. Deshalb steht hier
nicht eine Wörterliste, sondern je Sprache die ganze Vorlage.
"""
from __future__ import annotations

import logging

_LOGGER = logging.getLogger(__name__)

VORGABE = "de"

TEXTE: dict[str, dict[str, str]] = {
    "de": {
        # ── Schaltpunkte: die Bausteine eines Satzes ──────────────────────
        "punkt.satz": "{was} um {wann}{geltung}",
        "punkt.auf": "auf",
        "punkt.zu": "zu",
        "punkt.prozent": "{n} %",
        "punkt.uhrzeit": "{zeit} Uhr",
        "punkt.sonnenaufgang": "Sonnenaufgang",
        "punkt.sonnenuntergang": "Sonnenuntergang",
        "punkt.daemmerung": "Dämmerung",
        "punkt.versatz": " {n:+d} min",
        "punkt.fruehestens": ", frühestens {zeit}",
        "punkt.spaetestens": ", spätestens {zeit}",
        "punkt.gilt.schultag": " an Schultagen",
        "punkt.gilt.schulfrei": " an schulfreien Tagen",
        "punkt.gilt.morgen_schultag": " wenn morgen Schule ist",
        "punkt.gilt.morgen_schulfrei": " wenn morgen schulfrei ist",
        "punkt.seit": "seit {zeit} Uhr: {satz}",
        "punkt.dann": "dann {was} um {zeit} Uhr",

        # ── Zustände eines Rollos ─────────────────────────────────────────
        "zustand.aus_rollo": "Automatik für dieses Rollo ist aus",
        "zustand.aus_gesamt": "Automatik ist insgesamt aus",
        "zustand.von_hand": "Ohne Zeitplan – wird von Hand gefahren",
        "zustand.plan_aus": "Zeitplan „{name}“ ist abgeschaltet",
        "zustand.gruppe_aus": "Gruppe „{name}“ ist abgeschaltet",
        "zustand.gruppe_gesperrt": "Gruppe „{name}“ ist nicht freigegeben",
        "zustand.fluchtweg": "Fluchtweg offen – {grund}",
        "zustand.fehlt": "In Home Assistant nicht gefunden",
        "zustand.unerreichbar": "Nicht erreichbar",
        "zustand.ohne_plan": "Kein Schaltpunkt eingerichtet",
        "zustand.fenster_offen": "Offen: {liste}",
        "zustand.manuell": "Handbetrieb bis {zeit} Uhr",
        "zustand.nur_schliessen": "Betriebsart „nur schließen“ – bleibt in Ruhe",
        "zustand.unveraendert": "unverändert",
        "zustand.steht_richtig": "steht schon richtig",
        "zustand.trockenlauf": "Trockenlauf",
        "zustand.beobachten": "beobachten",
        "zustand.abgelehnt": "Fahrbefehl abgelehnt",
        "zustand.von_hand_erkannt": "von Hand gefahren",
        "zustand.urlaub_zu": "Urlaub – geschlossen",

        # ── Hitzeschutz ───────────────────────────────────────────────────
        "hitze.grund": "Sonne steht im Fenster ({azimut}°, {hoehe}° hoch), "
                       "außen {temperatur} °C",

        # ── Rauchalarm ────────────────────────────────────────────────────
        "rauch.melder": "Rauchmelder: {orte}",
        "rauch.nachlauf": "Nachlauf der Rauchsperre bis {zeit} Uhr",
        "rauch.weitere": "{orte} und {n} weitere",
        "rauch.titel": "Rauchalarm: {orte}",
        "rauch.titel_ohne_ort": "Rauchalarm",
        "rauch.titel_freigabe_aus": " – Freigabe ist aus",
        "rauch.freigabe_aus": "Die Fluchtweg-Freigabe ist AUS – es fährt kein Rollo auf.",
        "rauch.nicht_erreichbar": "NICHT erreichbar",
        "rauch.bleibt_zu": "Bleibt zu",
        "rauch.ausgenommen": "Ausgenommen",
        "rauch.aufgefahren": "Aufgefahren",
        "rauch.stand_offen": "Stand schon offen",
        "rauch.trockenlauf": "Trockenlauf – es ist nichts wirklich gefahren.",
        "rauch.nichts_betroffen": "Kein Rollo betroffen.",
        "rauch.probe_titel": "Rolloplaner – Probe Rauchalarm",
        "rauch.probe_text": "Probemeldung – es brennt nicht.\n"
                            "Bei einem echten Alarm käme hier, welche Rollos "
                            "aufgefahren sind und welche NICHT erreichbar waren.\n"
                            "Fluchtweg-Freigabe: {freigabe} · Melder: {melder}",
        "rauch.an": "an",
        "rauch.aus": "AUS",
        "rauch.alle": "alle",

        # ── Gesamtlage ────────────────────────────────────────────────────
        "lage.fluchtweg_offen": "Fluchtweg offen",
        "lage.rauchsperre": "Rauchsperre",
        "lage.automatik_aus": "Automatik aus",
        "lage.trockenlauf": "Trockenlauf",
        "lage.urlaub": "Urlaub",
        "lage.beschattet": "{n} Rollos beschattet",
        "lage.beschattet_1": "ein Rollo beschattet",
        "lage.alle_mit_automatik": "Alle Rollos mit Automatik",
        "lage.mit_automatik": "{n} von {gesamt} Rollos mit Automatik",
        "lage.kein_wechsel": "kein Wechsel geplant",

        # ── Von Hand bedient ──────────────────────────────────────────────
        "hand.gestellt": "von Hand gestellt",
        "hand.halt": "Halt",
        "hand.angehalten": "von Hand angehalten",

        # ── Übernahme aus den alten Automationen ─────────────────────────
        "ueb.kein_ausloeser": "kein Zeit- oder Sonnenauslöser",
        "ueb.toter_zweig": "{alias}: ein Zweig verlangt zwei Wochentags-Bedingungen "
                           "gleichzeitig und läuft nie – übersprungen",
    },
    "en": {
        "punkt.satz": "{was} at {wann}{geltung}",
        "punkt.auf": "open",
        "punkt.zu": "closed",
        "punkt.prozent": "{n} %",
        "punkt.uhrzeit": "{zeit}",
        "punkt.sonnenaufgang": "sunrise",
        "punkt.sonnenuntergang": "sunset",
        "punkt.daemmerung": "dusk",
        "punkt.versatz": " {n:+d} min",
        "punkt.fruehestens": ", not before {zeit}",
        "punkt.spaetestens": ", no later than {zeit}",
        "punkt.gilt.schultag": " on school days",
        "punkt.gilt.schulfrei": " on days off",
        "punkt.gilt.morgen_schultag": " when tomorrow is a school day",
        "punkt.gilt.morgen_schulfrei": " when tomorrow is a day off",
        "punkt.seit": "since {zeit}: {satz}",
        "punkt.dann": "then {was} at {zeit}",

        "zustand.aus_rollo": "Automation is off for this cover",
        "zustand.aus_gesamt": "Automation is off altogether",
        "zustand.von_hand": "No schedule – operated by hand",
        "zustand.plan_aus": "Schedule “{name}” is switched off",
        "zustand.gruppe_aus": "Group “{name}” is switched off",
        "zustand.gruppe_gesperrt": "Group “{name}” is not released",
        "zustand.fluchtweg": "Escape route open – {grund}",
        "zustand.fehlt": "Not found in Home Assistant",
        "zustand.unerreichbar": "Unavailable",
        "zustand.ohne_plan": "No switching point set up",
        "zustand.fenster_offen": "Open: {liste}",
        "zustand.manuell": "Manual until {zeit}",
        "zustand.nur_schliessen": "Mode “close only” – stays put",
        "zustand.unveraendert": "unchanged",
        "zustand.steht_richtig": "already in position",
        "zustand.trockenlauf": "Dry run",
        "zustand.beobachten": "watching",
        "zustand.abgelehnt": "Command refused",
        "zustand.von_hand_erkannt": "moved by hand",
        "zustand.urlaub_zu": "Holiday – kept closed",

        "hitze.grund": "Sun on this window ({azimut}°, {hoehe}° high), "
                       "{temperatur} °C outside",

        "rauch.melder": "Smoke detector: {orte}",
        "rauch.nachlauf": "Smoke lock still active until {zeit}",
        "rauch.weitere": "{orte} and {n} more",
        "rauch.titel": "Smoke alarm: {orte}",
        "rauch.titel_ohne_ort": "Smoke alarm",
        "rauch.titel_freigabe_aus": " – escape route is off",
        "rauch.freigabe_aus": "The escape route release is OFF – no cover will open.",
        "rauch.nicht_erreichbar": "NOT reachable",
        "rauch.bleibt_zu": "Stays closed",
        "rauch.ausgenommen": "Excluded",
        "rauch.aufgefahren": "Opened",
        "rauch.stand_offen": "Already open",
        "rauch.trockenlauf": "Dry run – nothing actually moved.",
        "rauch.nichts_betroffen": "No cover affected.",
        "rauch.probe_titel": "Rolloplaner – smoke alarm test",
        "rauch.probe_text": "Test message – nothing is burning.\n"
                            "In a real alarm this would list which covers "
                            "opened and which were NOT reachable.\n"
                            "Escape route release: {freigabe} · detectors: {melder}",
        "rauch.an": "on",
        "rauch.aus": "OFF",
        "rauch.alle": "all",

        "lage.fluchtweg_offen": "Escape route open",
        "lage.rauchsperre": "Smoke lock",
        "lage.automatik_aus": "Automation off",
        "lage.trockenlauf": "Dry run",
        "lage.urlaub": "Holiday",
        "lage.beschattet": "{n} covers shaded",
        "lage.beschattet_1": "one cover shaded",
        "lage.alle_mit_automatik": "All covers automated",
        "lage.mit_automatik": "{n} of {gesamt} covers automated",
        "lage.kein_wechsel": "no change scheduled",

        "hand.gestellt": "set by hand",
        "hand.halt": "stop",
        "hand.angehalten": "stopped by hand",

        "ueb.kein_ausloeser": "no time or sun trigger",
        "ueb.toter_zweig": "{alias}: one branch demands two weekday conditions at "
                           "once and never runs – skipped",
    },
}

_aktuell = VORGABE


def sprachen() -> list[str]:
    """Die Sprachen, die es gibt – für die Auswahl in der Oberfläche."""
    return sorted(TEXTE)


def setze(code: str | None) -> str:
    """Die Sprache festlegen. Unbekanntes fällt auf Deutsch zurück.

    ``code`` darf auch ein Gebietsschema sein (``en-GB``); gewertet wird nur
    der Teil davor. Home Assistant liefert es in dieser Form.
    """
    global _aktuell
    kurz = (code or "").split("-")[0].strip().lower()
    _aktuell = kurz if kurz in TEXTE else VORGABE
    return _aktuell


def aktuell() -> str:
    return _aktuell


def t(schluessel: str, sprache: str | None = None, **werte) -> str:
    """Ein Text in der eingestellten Sprache.

    Fehlt der Schlüssel, kommt der deutsche Text; fehlt auch der, der
    Schlüssel selbst – dann sieht man im Bild, was zu übersetzen ist, statt
    einer leeren Stelle.
    """
    tabelle = TEXTE.get(sprache or _aktuell) or TEXTE[VORGABE]
    # Einzahl: Steht neben dem Schlüssel einer mit ``_1``, gilt der bei genau
    # einem Stück. „1 covers shaded" liest sich wie ein Fehler.
    if werte.get("n") == 1 and (schluessel + "_1") in TEXTE[VORGABE]:
        schluessel += "_1"
    vorlage = tabelle.get(schluessel)
    if vorlage is None:
        vorlage = TEXTE[VORGABE].get(schluessel)
        if vorlage is None:
            _LOGGER.warning("Unbekannter Textschlüssel: %s", schluessel)
            return schluessel
    if not werte:
        return vorlage
    try:
        return vorlage.format(**werte)
    except (KeyError, IndexError, ValueError):
        # Eine Vorlage mit falschen Platzhaltern darf nicht den Takt kippen.
        _LOGGER.warning("Textvorlage passt nicht zu den Werten: %s", schluessel)
        return vorlage
