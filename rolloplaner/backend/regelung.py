"""Die Regelkette: was soll jedes Rollo jetzt tun, und warum.

Rangfolge – der erste Treffer gewinnt:

    aus → Rauch → Freigabe → Fenster → Urlaub → Hitzeschutz → Handbetrieb → Zeitplan

Zwei Grundsätze ziehen sich durch:

**Geschaltet wird auf der Flanke, nie auf dem Pegel.** Ein Thermostat, dem man
denselben Sollwert zum zehnten Mal schickt, tut nichts. Ein Rollladen fährt.
Der Planer merkt sich deshalb, welchen Schaltpunkt er zuletzt ausgeführt hat,
und rührt sich erst wieder, wenn ein neuer fällig wird oder eine Bedingung
kippt.

**Jedes Rollo wird einzeln angefahren.** Ein Sammelaufruf scheitert an einem
einzigen nicht erreichbaren Funkmotor und reißt die übrigen mit.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta

import ha_api
import sonne as sonnenmodul
import zeitplan as zeitplanmodul

_LOGGER = logging.getLogger(__name__)

# So weit darf die gemeldete Stellung von der gewünschten abweichen, ohne dass
# der Planer nachfährt. Ein Gurtwickler trifft seine Stellung auf ein paar
# Prozent genau; ohne Toleranz führe er dieselbe Stellung immer wieder an.
TOLERANZ = 6

# So lange nach einem eigenen Befehl wird die Stellung nicht ausgewertet – so
# lange braucht ein Rollladen für die volle Bahn. Ohne diese Frist hielte der
# Planer sein eigenes, noch fahrendes Rollo für Handbetrieb.
FAHRZEIT_MIN = 3


def _jetzt() -> datetime:
    return datetime.now().replace(microsecond=0)


def _iso(wann: datetime | None) -> str | None:
    return wann.isoformat(timespec="seconds") if wann else None


def _aus_iso(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _an(zustand: dict | None) -> bool:
    """Gilt diese Entität als „an“? ``home`` zählt mit – für Personen."""
    return bool(zustand) and zustand.get("state") in ("on", "home", "true", "open")


# ------------------------------------------------------------ Gesamtlage ----

def _sonnenstand_justieren(sonnenstand, sun: dict | None) -> None:
    """Die eigene Sonnenrechnung an ``sun.sun`` ausrichten.

    Die „nächsten“ Zeitpunkte aus Home Assistant stehen in Weltzeit; hier wird
    in Ortszeit gerechnet, also müssen sie umgerechnet werden.
    """
    if not sun:
        return
    attrs = sun.get("attributes") or {}
    for art, schluessel in (("sonnenaufgang", "next_rising"),
                            ("sonnenuntergang", "next_setting"),
                            ("daemmerung", "next_dusk")):
        roh = attrs.get(schluessel)
        if not roh:
            continue
        try:
            zeitpunkt = datetime.fromisoformat(str(roh).replace("Z", "+00:00"))
        except ValueError:
            continue
        sonnenstand.kalibrieren(art, zeitpunkt.astimezone().replace(tzinfo=None))


def _rauchsperre(einstellungen: dict, index: dict, state: dict,
                 jetzt: datetime) -> tuple[bool, str]:
    """Schlägt gerade ein Rauchmelder an – oder hat er es eben noch getan?

    Der wichtigste Griff im ganzen Planer. In diesem Haus fährt die Automation
    „RM Alarm öffnet alle Rollos“ bei Rauch **alle** Rollläden hoch. Ein
    Planer, der beim nächsten Takt stur seinen Abendplan durchsetzt, macht den
    Fluchtweg wieder zu. Deshalb: Schlägt ein Melder an, fasst der Planer gar
    nichts mehr an – und nach der Entwarnung noch eine Weile nicht, damit er
    nicht in eine gerade laufende Lüftung hineinfährt.
    """
    sperre = einstellungen.get("rauchsperre") or {}
    if not sperre.get("aktiv", True):
        return False, ""

    melder = sperre.get("melder") or []
    if melder:
        kandidaten = [(eid, index.get(eid)) for eid in melder]
    else:
        kandidaten = [(eid, z) for eid, z in index.items()
                      if eid.startswith("binary_sensor.")
                      and ha_api.ist_rauchmelder(
                          eid, ((z.get("attributes") or {}).get("friendly_name") or ""),
                          (z.get("attributes") or {}).get("device_class"))]

    ausgeloest = [eid for eid, z in kandidaten if _an(z)]
    if ausgeloest:
        nachlauf = int(sperre.get("nachlauf_min", 30))
        state["rauch_bis"] = _iso(jetzt + timedelta(minutes=nachlauf))
        namen = []
        for eid in ausgeloest[:3]:
            zustand = index.get(eid) or {}
            namen.append((zustand.get("attributes") or {}).get("friendly_name") or eid)
        return True, "Rauchmelder: " + ", ".join(namen)

    bis = _aus_iso(state.get("rauch_bis"))
    if bis and jetzt < bis:
        return True, f"Nachlauf der Rauchsperre bis {bis.strftime('%H:%M')} Uhr"
    if bis:
        state["rauch_bis"] = None
    return False, ""


def _versatz_wuerfeln(state: dict, jetzt: datetime, streuung: int) -> dict:
    """Für jeden Raum und Schaltpunkt einen Tagesversatz in Minuten.

    Gewürfelt wird nicht mit einem Zufallsgenerator, sondern aus dem Datum:
    Derselbe Tag ergibt denselben Versatz, auch nach einem Neustart des
    Add-ons. Ein Versatz, der sich bei jedem Takt neu auslost, führe das Rollo
    jede Minute woanders hin – und wäre keine Simulation, sondern ein Defekt.
    """
    simulation = state.setdefault("simulation", {"tag": None, "versatz": {}})
    heute = jetzt.date().isoformat()
    if simulation.get("tag") != heute:
        simulation["tag"] = heute
        simulation["versatz"] = {}
    simulation["streuung"] = streuung
    return simulation


def _versatz_fuer(simulation: dict, schluessel: str, streuung: int) -> int:
    if streuung <= 0:
        return 0
    gespeichert = simulation["versatz"].get(schluessel)
    if gespeichert is None:
        roh = hashlib.sha256(
            f"{simulation.get('tag')}|{schluessel}".encode("utf-8")).digest()
        gespeichert = int.from_bytes(roh[:4], "big") % (2 * streuung + 1) - streuung
        simulation["versatz"][schluessel] = gespeichert
    return int(gespeichert)


# ------------------------------------------------------------------ Raum ----

def _fenster_offen(raum: dict, index: dict) -> list[str]:
    """Welche Kontakte des Raumes gerade offen sind.

    Solange einer offen ist, wird nicht zugefahren. Wer auf der Terrasse steht
    und das Rollo fährt vor der offenen Tür herunter, steht draußen.
    """
    offen = []
    for eid in raum.get("fenster") or []:
        zustand = index.get(eid)
        if _an(zustand):
            offen.append((zustand.get("attributes") or {}).get("friendly_name") or eid)
    return offen


def _jemand_da(raum: dict, index: dict) -> bool | None:
    melder = (raum.get("praesenz") or []) + (raum.get("personen") or [])
    if not melder:
        return None
    return any(_an(index.get(eid)) for eid in melder)


def _beschattung_pruefen(raum: dict, einstellungen: dict, index: dict,
                         sonnenstand, jetzt: datetime,
                         war_beschattet: bool) -> tuple[bool, str, int | None]:
    """Steht die Sonne im Fenster, und ist es warm genug?

    Die Hysterese hängt an der Temperatur, nicht am Sonnenstand: Ein Rollo,
    das an der Grenze zwischen 23,9 und 24,1 Grad im Minutentakt auf und ab
    fährt, ist schlimmer als gar kein Hitzeschutz.
    """
    global_ = einstellungen.get("beschattung") or {}
    if not global_.get("aktiv", True) or not raum.get("beschattung"):
        return False, "", None
    if raum.get("ausrichtung") is None:
        return False, "", None

    elevation, azimut = sonnenstand.stand(jetzt)
    if not sonnenmodul.sonne_steht_im_fenster(
            azimut, elevation, raum.get("ausrichtung"),
            float(raum.get("oeffnungswinkel") or 90),
            float(global_.get("min_elevation", 12.0))):
        return False, "", None

    aussen = _temperatur(einstellungen.get("aussen_entity"), index)
    if aussen is None:
        return False, "", None
    schwelle = float(global_.get("ab_temperatur", 24.0))
    if war_beschattet:
        schwelle -= float(global_.get("hysterese", 1.5))
    if aussen < schwelle:
        return False, "", None

    # Ein zweites Kriterium von innen, wenn der Raum einen Fühler hat: Nicht
    # jeder warme Tag heizt jeden Raum auf.
    if raum.get("raumtemp") and raum.get("raumtemp_ab") is not None:
        innen = _temperatur(raum["raumtemp"], index)
        if innen is not None and innen < float(raum["raumtemp_ab"]):
            return False, "", None

    if global_.get("nur_wenn_niemand_da") and _jemand_da(raum, index):
        return False, "", None

    position = raum.get("beschattung_position")
    if position is None:
        position = int(global_.get("position", 35))
    grund = (f"Sonne steht im Fenster ({azimut:.0f}°, {elevation:.0f}° hoch), "
             f"außen {aussen:.1f} °C")
    return True, grund, int(position)


def _temperatur(entity_id: str | None, index: dict) -> float | None:
    if not entity_id:
        return None
    zustand = index.get(entity_id)
    if not zustand:
        return None
    if entity_id.startswith("weather."):
        return ha_api.as_float((zustand.get("attributes") or {}).get("temperature"))
    return ha_api.as_float(zustand.get("state"))


def _raum_rechnen(raum: dict, einstellungen: dict, index: dict, state: dict,
                  kalender, sonnenstand, jetzt: datetime, lage: dict) -> dict:
    """Was dieser Raum jetzt tun soll – mitsamt Begründung.

    Liefert ein Ergebnis, auch wenn nichts zu tun ist: Die Oberfläche soll
    jederzeit erklären können, warum ein Rollo steht, wo es steht.
    """
    raum_state = state["raeume"].setdefault(raum["id"], {})
    ergebnis = {
        "id": raum["id"], "name": raum["name"], "zustand": "plan",
        "begruendung": "", "ziel": None, "rollos": [], "schaltet": False,
    }

    # 1. aus ------------------------------------------------------------------
    if not raum.get("aktiv", True):
        ergebnis.update(zustand="aus", begruendung="Raum ist abgeschaltet")
        return ergebnis
    if not lage["automatik"]:
        ergebnis.update(zustand="aus", begruendung="Automatik ist aus")
        return ergebnis

    # 2. Rauch ----------------------------------------------------------------
    if lage["rauch"]:
        ergebnis.update(zustand="rauch", begruendung=lage["rauch_grund"])
        return ergebnis

    # 3. Freigabe -------------------------------------------------------------
    freigabe = raum.get("freigabe_entity")
    if freigabe:
        zustand = index.get(freigabe)
        if zustand is None:
            ergebnis.update(zustand="gesperrt",
                            begruendung=f"Freigabeschalter {freigabe} fehlt")
            return ergebnis
        if not _an(zustand):
            name = (zustand.get("attributes") or {}).get("friendly_name") or freigabe
            ergebnis.update(zustand="gesperrt", begruendung=f"„{name}“ ist aus")
            return ergebnis

    # Der Zeitplan ist die Grundlage; Urlaub und Hitzeschutz verschieben ihn.
    anpassen = _urlaubsversatz(raum, einstellungen, lage)
    zustaende = lage["zustaende"]
    treffer = zeitplanmodul.letzter_zeitpunkt(
        raum.get("zeitplan") or [], jetzt, kalender, sonnenstand, anpassen, zustaende)
    naechster = zeitplanmodul.naechster_wechsel(
        raum.get("zeitplan") or [], jetzt, kalender, sonnenstand, anpassen, zustaende)

    ziel = None
    punkt_zeit = None
    beschreibung = ""
    if treffer:
        punkt_zeit, punkt = treffer
        ziel = int(punkt["position"])
        beschreibung = zeitplanmodul.beschreibung(punkt)

    if naechster:
        ergebnis["naechster_zeitpunkt"] = _iso(naechster[0])
        ergebnis["naechste_uhrzeit"] = naechster[0].strftime("%H:%M")
        ergebnis["naechste_stellung"] = int(naechster[1]["position"])
        ergebnis["naechster_punkt"] = zeitplanmodul.beschreibung(naechster[1])

    # 4. Urlaub ---------------------------------------------------------------
    # Die Simulation steckt schon in `anpassen` und damit in `punkt_zeit`;
    # hier bleibt nur der Fall „im Urlaub alles zu“.
    urlaub = einstellungen.get("urlaub") or {}
    if lage["urlaub"] and urlaub.get("modus") != "plan":
        ergebnis["urlaub"] = True
        ergebnis["zustand"] = "urlaub"
        if urlaub.get("modus") == "zu" or not raum.get("urlaub_simulation", True):
            ziel = int(raum.get("position_zu", 0))
            punkt_zeit = lage["urlaub_seit"] or punkt_zeit
            beschreibung = "Urlaub – geschlossen"
        elif anpassen is not None and treffer:
            versatz = int((punkt_zeit - _roh_zeitpunkt(
                treffer[1], punkt_zeit, kalender, sonnenstand)).total_seconds() // 60)
            if versatz:
                beschreibung += f" (Urlaubssimulation {versatz:+d} min)"

    # 5. Hitzeschutz ----------------------------------------------------------
    war_beschattet = bool(raum_state.get("beschattet"))
    beschatten, beschattungsgrund, beschattungsposition = _beschattung_pruefen(
        raum, einstellungen, index, sonnenstand, jetzt, war_beschattet)
    if beschatten and ziel is not None and beschattungsposition < ziel:
        # Nur verdunkeln, nie aufziehen: Steht der Plan ohnehin auf „zu“,
        # bleibt es dabei.
        ziel = beschattungsposition
        ergebnis["zustand"] = "beschattung"
        beschreibung = beschattungsgrund
        punkt_zeit = jetzt          # Pegel, kein Zeitpunkt – Flanke unten
    ergebnis["beschattet"] = beschatten

    if ziel is None:
        ergebnis.update(zustand="ohne_plan",
                        begruendung="Kein Schaltpunkt eingerichtet")
        return ergebnis

    # 6. Fenster --------------------------------------------------------------
    offen = _fenster_offen(raum, index)
    ergebnis["fenster_offen"] = offen

    ergebnis["begruendung"] = beschreibung
    ergebnis["ziel"] = ziel
    ergebnis["punkt_zeit"] = _iso(punkt_zeit)

    # 7. Handbetrieb und 8. Ausführung stecken in _rollos_stellen(); erst dort
    # steht fest, ob überhaupt etwas zu fahren ist.
    return ergebnis


def _roh_zeitpunkt(eintrag: dict, verschoben: datetime, kalender, sonnenstand) -> datetime:
    """Der unverschobene Zeitpunkt – nur, um den Versatz anzeigen zu können."""
    roh = zeitplanmodul.zeitpunkt_von(eintrag, verschoben.date(), sonnenstand)
    return roh if roh is not None else verschoben


def _urlaubsversatz(raum: dict, einstellungen: dict, lage: dict):
    """Die Funktion, die jeden Schaltpunkt um den Tagesversatz verschiebt.

    ``None``, wenn nicht simuliert wird – dann bleibt der Zeitplan unberührt.
    """
    urlaub = einstellungen.get("urlaub") or {}
    if not lage["urlaub"] or urlaub.get("modus") != "simulation":
        return None
    if not raum.get("urlaub_simulation", True):
        return None
    streuung = int(urlaub.get("streuung_min", 20))
    if streuung <= 0:
        return None

    def anpassen(zeitpunkt: datetime, eintrag: dict, tag) -> datetime:
        schluessel = (f"{raum['id']}|{tag}|{eintrag.get('ausloeser')}|"
                      f"{eintrag.get('start')}|{eintrag.get('position')}")
        versatz = _versatz_fuer(lage["simulation"], schluessel, streuung)
        return _in_fenster(zeitpunkt + timedelta(minutes=versatz), urlaub)

    return anpassen


def _in_fenster(wann: datetime, urlaub: dict) -> datetime:
    """Einen simulierten Zeitpunkt in die erlaubten Tagesgrenzen zwingen.

    Ohne Grenzen könnte die Streuung ein Rollo um 06:41 hochfahren, während
    das Haus leer steht – auffälliger als jede Regelmäßigkeit.
    """
    for schluessel, spaeter in (("nicht_vor", True), ("nicht_nach", False)):
        text = urlaub.get(schluessel)
        if not text:
            continue
        stunde, minute = (int(t) for t in text.split(":"))
        grenze = wann.replace(hour=stunde, minute=minute, second=0)
        wann = max(wann, grenze) if spaeter else min(wann, grenze)
    return wann


# ------------------------------------------------------------- Ausführen ----

def _rollos_stellen(raum: dict, ergebnis: dict, einstellungen: dict, index: dict,
                    state: dict, jetzt: datetime, protokoll) -> None:
    """Die Rollos eines Raumes auf die errechnete Stellung bringen.

    Hier entscheidet sich, ob überhaupt gefahren wird. Vier Gründe, es zu
    lassen: Es ist schon richtig, der Schaltpunkt ist nicht neu, jemand hat von
    Hand gefahren, oder ein Fenster steht offen.
    """
    raum_state = state["raeume"].setdefault(raum["id"], {})
    ziel = ergebnis.get("ziel")
    trockenlauf = bool(einstellungen.get("trockenlauf"))
    beobachten = raum.get("betriebsart") == "beobachten"

    if ziel is None or ergebnis["zustand"] in ("aus", "rauch", "gesperrt", "ohne_plan"):
        return

    punkt_zeit = _aus_iso(ergebnis.get("punkt_zeit"))
    zuletzt = _aus_iso(raum_state.get("letzter_punkt"))
    beschattung_wechsel = bool(raum_state.get("beschattet")) != bool(ergebnis["beschattet"])

    # Die Flanke: ein Schaltpunkt zählt nur, wenn er seit dem letzten Mal neu
    # dazugekommen ist.
    neuer_punkt = punkt_zeit is not None and (zuletzt is None or punkt_zeit > zuletzt)
    if not neuer_punkt and not beschattung_wechsel:
        ergebnis["begruendung"] = ergebnis["begruendung"] or "unverändert"
        _stellungen_erfassen(raum, ergebnis, index, state, jetzt)
        return

    # „Nur schließen“: der Planer fährt zu, öffnet aber nie von selbst.
    if raum.get("betriebsart") == "nur_schliessen" and ziel > int(raum.get("position_zu", 0)):
        ergebnis["zustand"] = "nur_schliessen"
        ergebnis["begruendung"] = "Betriebsart „nur schließen“ – bleibt in Ruhe"
        raum_state["letzter_punkt"] = _iso(punkt_zeit)
        _stellungen_erfassen(raum, ergebnis, index, state, jetzt)
        return

    # Fenster offen: Zufahren wird unterdrückt, Öffnen bleibt erlaubt.
    offen = ergebnis.get("fenster_offen") or []
    gefahren = []
    # Wurde ein Rollo aus einem Grund übergangen, der von selbst wieder
    # weggeht? Dann darf der Schaltpunkt **nicht** als erledigt gelten – sonst
    # bliebe das Rollo bis zum nächsten Tag offen, weil die Terrassentür in
    # der einen Minute offen stand, in der der Punkt fällig wurde.
    aufgeschoben = False
    for eid in raum.get("rollos") or []:
        zustand = index.get(eid)
        ist = ha_api.position_von(zustand)
        rollo_state = state["rollos"].setdefault(eid, {})
        eintrag = {"entity_id": eid, "ist": ist, "ziel": ziel, "gefahren": False,
                   "name": ((zustand.get("attributes") or {}).get("friendly_name")
                            if zustand else eid) or eid}

        if zustand is None:
            eintrag["hinweis"] = "nicht gefunden"
            aufgeschoben = True
            ergebnis["rollos"].append(eintrag)
            continue
        if zustand.get("state") == "unavailable":
            eintrag["hinweis"] = "nicht erreichbar"
            aufgeschoben = True
            ergebnis["rollos"].append(eintrag)
            continue

        if offen and ist is not None and ziel < ist:
            eintrag["hinweis"] = "Fenster offen – bleibt stehen"
            ergebnis["zustand"] = "fenster"
            ergebnis["begruendung"] = "Offen: " + ", ".join(offen)
            aufgeschoben = True
            ergebnis["rollos"].append(eintrag)
            continue

        # Handbetrieb: Steht das Rollo woanders, als der Planer es zuletzt
        # hingefahren hat, war jemand am Schalter. Dann gilt eine Schonfrist –
        # aber ein neu fälliger Schaltpunkt beendet sie. Sonst müsste man
        # daran denken, den Handbetrieb wieder aufzuheben.
        manuell_bis = _aus_iso(rollo_state.get("manuell_bis"))
        if (einstellungen.get("manuell_respektieren") and manuell_bis
                and jetzt < manuell_bis and not neuer_punkt):
            eintrag["hinweis"] = f"Handbetrieb bis {manuell_bis.strftime('%H:%M')} Uhr"
            ergebnis["zustand"] = "manuell"
            ergebnis["rollos"].append(eintrag)
            continue

        if ist is not None and abs(ist - ziel) <= TOLERANZ:
            eintrag["hinweis"] = "steht schon richtig"
            ergebnis["rollos"].append(eintrag)
            continue

        if trockenlauf or beobachten:
            eintrag["hinweis"] = "Trockenlauf" if trockenlauf else "beobachten"
            ergebnis["rollos"].append(eintrag)
            gefahren.append(eintrag["name"])
            continue

        erfolg = ha_api.set_position(eid, ziel, zustand)
        eintrag["gefahren"] = erfolg
        if erfolg:
            rollo_state.update(ziel=ziel, gesetzt_am=_iso(jetzt),
                               grund=ergebnis["begruendung"], manuell_bis=None)
            gefahren.append(eintrag["name"])
        else:
            eintrag["hinweis"] = "Fahrbefehl abgelehnt"
        ergebnis["rollos"].append(eintrag)

    if gefahren:
        ergebnis["schaltet"] = True
        was = "auf" if ziel >= 100 else ("zu" if ziel <= 0 else f"{ziel} %")
        protokoll(raum["name"], was,
                  ergebnis["begruendung"] + (" (Trockenlauf)" if trockenlauf else ""),
                  ", ".join(gefahren),
                  art="warnung" if trockenlauf else None)

    if punkt_zeit is not None and not aufgeschoben:
        raum_state["letzter_punkt"] = _iso(punkt_zeit)
    elif aufgeschoben:
        # Der Punkt bleibt offen. Sobald das Hindernis weg ist, wird er
        # nachgeholt – und zwar der dann *zuletzt fällige*, nicht dieser hier.
        # Geht die Terrassentür erst morgens um drei zu, ist das immer noch
        # „21:00 zu“; geht sie um neun zu, ist es „07:00 auf“.
        ergebnis["aufgeschoben"] = True
    raum_state["beschattet"] = bool(ergebnis["beschattet"])
    raum_state["ziel"] = ziel


def _stellungen_erfassen(raum: dict, ergebnis: dict, index: dict, state: dict,
                         jetzt: datetime) -> None:
    """Ohne Schaltvorgang: nur nachsehen, wo die Rollos stehen.

    Dabei fällt der Handbetrieb auf – die einzige Stelle, an der er überhaupt
    erkannt werden kann, denn Home Assistant sagt nicht, wer gefahren ist.
    """
    einstellungen_stunden = state.get("_manuell_stunden", 12.0)
    for eid in raum.get("rollos") or []:
        zustand = index.get(eid)
        ist = ha_api.position_von(zustand)
        eintrag = {"entity_id": eid, "ist": ist, "ziel": ergebnis.get("ziel"),
                   "gefahren": False,
                   "name": ((zustand.get("attributes") or {}).get("friendly_name")
                            if zustand else eid) or eid}
        rollo_state = state["rollos"].setdefault(eid, {})
        gesetzt = _aus_iso(rollo_state.get("gesetzt_am"))
        eigenes_ziel = rollo_state.get("ziel")

        if (ist is not None and eigenes_ziel is not None
                and abs(ist - int(eigenes_ziel)) > TOLERANZ
                and gesetzt and jetzt - gesetzt > timedelta(minutes=FAHRZEIT_MIN)
                and not ha_api.faehrt(zustand)):
            if not rollo_state.get("manuell_bis"):
                rollo_state["manuell_bis"] = _iso(
                    jetzt + timedelta(hours=float(einstellungen_stunden)))
            eintrag["hinweis"] = "von Hand gefahren"
        ergebnis["rollos"].append(eintrag)


# ------------------------------------------------------------------ Takt ----

def takt(config: dict, state: dict, protokoll, wachhund_haken=None) -> dict:
    """Ein Durchlauf: alle Räume rechnen und, wo nötig, fahren.

    ``wachhund_haken`` bekommt die bereits geladenen Zustände gereicht. Ohne
    ihn müsste der Wächter ``/states`` ein zweites Mal abrufen – anderthalb
    Megabyte, alle zwei Minuten, für dieselbe Auskunft.
    """
    einstellungen = config["einstellungen"]
    jetzt = _jetzt()
    bericht = {"zeit": _iso(jetzt), "raeume": [], "stoerungen": []}

    if not ha_api.available():
        bericht["fehler"] = "Kein SUPERVISOR_TOKEN"
        return bericht
    if not ha_api.ist_bereit():
        bericht["hinweis"] = "Home Assistant startet gerade – dieser Takt fällt aus"
        return bericht

    states = ha_api.get_states()
    if not states:
        bericht["hinweis"] = "Keine Zustände von Home Assistant erhalten"
        return bericht
    index = {s["entity_id"]: s for s in states}

    sonnenstand = _sonnenstand(state, index, einstellungen)
    _sonnenstand_justieren(sonnenstand, index.get(einstellungen.get("sonne_entity")))

    schulfrei = _schalter(index, einstellungen.get("schulfrei_entity"))
    schulfrei_morgen = _schalter(index, einstellungen.get("schulfrei_morgen_entity"))
    kalender = zeitplanmodul.Schulkalender(
        schulfrei, schulfrei_morgen, state.setdefault("schulfrei_verlauf", {}))
    kalender.merken(jetzt.date())
    state["schulfrei_verlauf"] = kalender.verlauf

    urlaub = _schalter(index, einstellungen.get("urlaub_entity")) or False
    if urlaub and not state.get("urlaub_seit"):
        state["urlaub_seit"] = _iso(jetzt)
    elif not urlaub:
        state["urlaub_seit"] = None

    rauch, rauch_grund = _rauchsperre(einstellungen, index, state, jetzt)
    state["_manuell_stunden"] = float(einstellungen.get("manuell_stunden", 12.0))

    elevation, azimut = sonnenstand.stand(jetzt)
    lage = {
        "automatik": bool(einstellungen.get("automatik", True)),
        "urlaub": urlaub,
        "urlaub_seit": _aus_iso(state.get("urlaub_seit")),
        "rauch": rauch,
        "rauch_grund": rauch_grund,
        "simulation": _versatz_wuerfeln(
            state, jetzt, int((einstellungen.get("urlaub") or {}).get("streuung_min", 20))),
        # Für die Bedingungen an Schaltpunkten: entity_id → Zustand als Text.
        "zustaende": {eid: z.get("state") for eid, z in index.items()},
    }

    for raum in config["raeume"]:
        ergebnis = _raum_rechnen(raum, einstellungen, index, state, kalender,
                                 sonnenstand, jetzt, lage)
        try:
            _rollos_stellen(raum, ergebnis, einstellungen, index, state, jetzt, protokoll)
        except Exception as err:  # noqa: BLE001 – ein Raum darf die übrigen nicht mitreißen
            _LOGGER.exception("Raum %s fehlgeschlagen", raum.get("name"))
            ergebnis["begruendung"] = f"Fehler: {err}"
        bericht["raeume"].append(ergebnis)

    if wachhund_haken is not None:
        try:
            bericht["stoerungen"] = wachhund_haken(index, jetzt)
        except Exception:  # noqa: BLE001 – der Wächter darf den Takt nicht kippen
            _LOGGER.exception("Wächter fehlgeschlagen")

    bericht.update({
        "automatik": lage["automatik"],
        "trockenlauf": bool(einstellungen.get("trockenlauf")),
        "urlaub": urlaub,
        "schulfrei": schulfrei,
        "schulfrei_morgen": schulfrei_morgen,
        "rauch": rauch,
        "rauch_grund": rauch_grund,
        "sonne": {"elevation": elevation, "azimut": azimut,
                  "aufgang": _iso(sonnenstand.aufgang(jetzt.date())),
                  "untergang": _iso(sonnenstand.untergang(jetzt.date()))},
        "aussen": _temperatur(einstellungen.get("aussen_entity"), index),
    })
    return bericht


def _schalter(index: dict, entity_id: str | None) -> bool | None:
    if not entity_id:
        return None
    zustand = index.get(entity_id)
    if zustand is None or zustand.get("state") in ("unknown", "unavailable"):
        return None
    return _an(zustand)


_sonnenstand_cache: dict = {}


def _sonnenstand(state: dict, index: dict, einstellungen: dict):
    """Den Rechner für den Sonnenstand holen – einmal je Ort.

    Die Koordinaten stehen in ``zone.home``. Fehlt die Zone, wird der Ort
    genommen, den der Planer zuletzt gesehen hat; erst wenn auch der fehlt,
    fällt er auf die Mitte Deutschlands zurück – dann stimmen die Sonnenzeiten
    grob, und der Fehler steht sichtbar im Bericht statt still im Verborgenen.
    """
    zone = index.get("zone.home")
    lat = lon = None
    if zone:
        attrs = zone.get("attributes") or {}
        lat = ha_api.as_float(attrs.get("latitude"))
        lon = ha_api.as_float(attrs.get("longitude"))
    if lat is None or lon is None:
        ort = state.get("ort") or {}
        lat, lon = ort.get("lat", 51.16), ort.get("lon", 10.45)
    else:
        state["ort"] = {"lat": lat, "lon": lon}

    schluessel = (round(lat, 4), round(lon, 4))
    if _sonnenstand_cache.get("schluessel") != schluessel:
        _sonnenstand_cache["schluessel"] = schluessel
        _sonnenstand_cache["objekt"] = sonnenmodul.Sonnenstand(lat, lon)
    return _sonnenstand_cache["objekt"]
