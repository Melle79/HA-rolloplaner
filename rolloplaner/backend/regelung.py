"""Die Regelkette: was soll jedes Rollo jetzt tun, und warum.

Gerechnet wird **je Rollo**. Das ist keine Feinheit: Luna hat ein Fenster und
eine Balkontür, das Schlafzimmer ebenso. Wer den Raum regelt, kann die
Balkontür nicht offen lassen, während das Fenster zufährt.

Rangfolge – der erste Treffer gewinnt:

    Rauch → aus → Rollo aus → Zeitplan aus → Fenster → Urlaub → Hitzeschutz
    → Handbetrieb → Zeitplan

Rauch steht ganz oben, und zwar seit der Fluchtweg-Freigabe: Ein Rollo, das
„von Hand“ gefahren wird oder dessen Zeitplan abgeschaltet ist, gehört im
Brandfall genauso auf wie jedes andere.

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
import store
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
                 jetzt: datetime) -> tuple[bool, str, bool, str]:
    """Schlägt gerade ein Rauchmelder an – oder hat er es eben noch getan?

    Zurück kommen vier Dinge: ob die Sperre gilt, warum, ob der Alarm **akut**
    ist, und wo er ist – der Ort gehört in die Überschrift der Nachricht, denn
    auf einem Sperrbildschirm liest man die erste Zeile und sonst nichts. Der Unterschied zählt: Die Sperre gilt auch im Nachlauf nach
    der Entwarnung, der Fluchtweg wird dort aber nicht mehr aufgefahren – sonst
    führe der Planer eine halbe Stunde lang gegen jeden an, der hinter dem
    abgezogenen Alarm wieder zumachen will.

    Der wichtigste Griff im ganzen Planer. In diesem Haus fährt die Automation
    „RM Alarm öffnet alle Rollos“ bei Rauch **alle** Rollläden hoch. Ein
    Planer, der beim nächsten Takt stur seinen Abendplan durchsetzt, macht den
    Fluchtweg wieder zu. Deshalb: Schlägt ein Melder an, fasst der Planer gar
    nichts mehr an – und nach der Entwarnung noch eine Weile nicht, damit er
    nicht in eine gerade laufende Lüftung hineinfährt.
    """
    sperre = einstellungen.get("rauchsperre") or {}
    if not sperre.get("aktiv", True):
        return False, "", False, ""

    melder = [m for m in (sperre.get("melder") or [])
              if not ha_api.ist_eigene_entitaet(m)]
    if melder:
        kandidaten = [(eid, index.get(eid)) for eid in melder]
    else:
        kandidaten = [(eid, z) for eid, z in index.items()
                      if eid.startswith("binary_sensor.")
                      and not ha_api.ist_eigene_entitaet(eid)
                      and ha_api.ist_rauchmelder(
                          eid, ((z.get("attributes") or {}).get("friendly_name") or ""),
                          (z.get("attributes") or {}).get("device_class"))]

    ausgeloest = [eid for eid, z in kandidaten if _an(z)]
    if ausgeloest:
        nachlauf = int(sperre.get("nachlauf_min", 30))
        state["rauch_bis"] = _iso(jetzt + timedelta(minutes=nachlauf))
        orte = _melderorte(ausgeloest, index)
        state["rauch_orte"] = orte
        return True, "Rauchmelder: " + orte, True, orte

    bis = _aus_iso(state.get("rauch_bis"))
    if bis and jetzt < bis:
        return (True, f"Nachlauf der Rauchsperre bis {bis.strftime('%H:%M')} Uhr",
                False, state.get("rauch_orte") or "")
    if bis:
        state["rauch_bis"] = None
        state["rauch_orte"] = None
    return False, "", False, ""


# Was am Namen eines Melders hinten dranhängt und nichts sagt. „RM Flur EG
# Alarmstatus" ist auf einem Sperrbildschirm drei Wörter zu lang.
_MELDER_BALLAST = ("alarmstatus", "alarm", "rauch", "smoke", "status")


def _melderort(entity_id: str, index: dict, bereiche: dict | None = None) -> str:
    """Wo dieser Melder hängt – möglichst als Raum, sonst als gekürzter Name.

    Der Bereich aus Home Assistant ist die bessere Auskunft: „Flur 1.OG" sagt
    im Ernstfall mehr als „RM Flur OG Alarmstatus", und er steht auch dann
    richtig da, wenn der Melder einmal umbenannt wird.
    """
    bereich = (bereiche or {}).get(entity_id)
    if bereich:
        return bereich
    name = ((index.get(entity_id) or {}).get("attributes") or {}).get(
        "friendly_name") or entity_id
    worte = [w for w in str(name).split() if w.lower() not in _MELDER_BALLAST]
    # „RM" allein ist kein Ort – dann lieber den ganzen Namen als gar nichts.
    return " ".join(worte) if len(worte) > 1 else str(name)


def _melderorte(ausgeloest: list, index: dict, grenze: int = 4) -> str:
    """Die Orte aller ausgelösten Melder, ohne Doppelungen.

    Bei einem Brand schlagen mehrere an. Die Liste zu kürzen ist richtig – sie
    stillschweigend zu kürzen nicht: „und 3 weitere" gehört dazu, sonst hält
    man vier Melder für alles, was los ist.
    """
    try:
        bereiche = ha_api.bereiche_je_entitaet(("binary_sensor",))
    except Exception:  # noqa: BLE001 – im Ernstfall lieber ohne Bereiche melden
        bereiche = {}
    orte: list[str] = []
    for eid in ausgeloest:
        ort = _melderort(eid, index, bereiche)
        if ort not in orte:
            orte.append(ort)
    if len(orte) <= grenze:
        return ", ".join(orte)
    return ", ".join(orte[:grenze]) + f" und {len(orte) - grenze} weitere"


def _fluchtweg(config: dict, einstellungen: dict, index: dict, state: dict,
               jetzt: datetime, rauch: bool, akut: bool = True) -> dict:
    """Bei Rauchalarm jedes Rollo aufmachen.

    Der Gegenpol zur Rauchsperre: Die sorgt dafür, dass der Planer nichts mehr
    zufährt, diese hier dafür, dass überhaupt etwas aufgeht. Beides zusammen
    ersetzt die Automation „RM Alarm öffnet alle Rollos“.

    Drei Dinge unterscheiden das vom gewöhnlichen Fahren:

    **Es steht über allem.** Nicht über der Automatik, nicht über einem
    abgeschalteten Zeitplan, nicht über „von Hand“ – über allem. Wer im
    Schlafzimmer keinen Zeitplan will, will trotzdem aus dem Fenster kommen.
    Einzig ein Rollo, an dem ``fluchtweg`` ausgeschaltet ist, bleibt in Ruhe.

    **Es fasst nach.** Ein Fahrbefehl kann verlorengehen, ein Funkmotor kann
    ihn verschlucken. Ein Rollo, das nach der Fahrzeit immer noch zu ist,
    bekommt den Befehl erneut – aber nur ``fluchtweg_versuche`` mal. Ein
    blockierter Antrieb, der im Minutentakt gegen ein Hindernis fährt, ist im
    Brandfall kein Rettungsweg, sondern ein zweiter Schaden.

    **Es hält den Trockenlauf ein.** Der Trockenlauf ist der Schalter, mit dem
    man dem Planer sagt: Fass nichts an. Ihn ausgerechnet hier zu übergehen,
    hieße, dass ein Add-on im Probebetrieb nachts das Haus aufmacht.
    """
    sperre = einstellungen.get("rauchsperre") or {}
    stand = state.setdefault("fluchtweg", {"seit": None, "versuche": {}})
    bericht: dict = {"aktiv": False, "neu": False, "akut": bool(akut), "seit": None,
                     "offen": [], "gefahren": [], "unterwegs": [], "aufgegeben": [],
                     "fehlt": [], "uebergangen": [], "nachlauf": []}

    # Entwarnung: Sobald der Alarm samt Nachlauf vorbei ist, zählt der nächste
    # von vorn. Sonst hätte ein Rollo, das im Frühjahr dreimal vergeblich
    # angefahren wurde, im Herbst keinen Versuch mehr frei.
    if not rauch:
        if stand.get("seit"):
            stand["seit"] = None
            stand["versuche"] = {}
        return bericht
    if not sperre.get("aktiv", True) or not sperre.get("fluchtweg", True):
        return bericht

    bericht["aktiv"] = True
    if not stand.get("seit"):
        stand["seit"] = _iso(jetzt)
        stand["versuche"] = {}
        bericht["neu"] = True
    bericht["seit"] = stand["seit"]

    trockenlauf = bool(einstellungen.get("trockenlauf"))
    grenze = int(sperre.get("fluchtweg_versuche", 3))
    versuche = stand.setdefault("versuche", {})

    for rollo in config.get("rollos") or []:
        eid = rollo["entity_id"]
        name = anzeigename(rollo, index)
        if not rollo.get("aktiv", True):
            continue
        if not rollo.get("fluchtweg", True):
            bericht["uebergangen"].append(name)
            continue

        zustand = index.get(eid)
        if zustand is None or zustand.get("state") == "unavailable":
            bericht["fehlt"].append(name)
            continue

        ziel = int(rollo.get("position_offen", 100))
        ist = ha_api.position_von(zustand)
        if ist is not None and ist >= ziel - TOLERANZ:
            bericht["offen"].append(name)
            continue

        # Nach der Entwarnung wird nur noch berichtet, nicht mehr gefahren.
        if not akut:
            bericht["nachlauf"].append(name)
            continue

        eintrag = versuche.setdefault(eid, {"n": 0, "am": None})
        letzte = _aus_iso(eintrag.get("am"))
        if letzte is not None and jetzt - letzte < timedelta(minutes=FAHRZEIT_MIN):
            bericht["unterwegs"].append(name)
            continue
        if eintrag["n"] >= grenze:
            bericht["aufgegeben"].append(name)
            continue

        eintrag["n"] += 1
        eintrag["am"] = _iso(jetzt)
        if trockenlauf:
            bericht["gefahren"].append(name)
            _LOGGER.warning("Fluchtweg: %s bliebe im Trockenlauf zu", eid)
            continue
        if ha_api.set_position(eid, ziel, zustand):
            bericht["gefahren"].append(name)
            state.setdefault("rollos", {}).setdefault(eid, {}).update(
                ziel=ziel, gesetzt_am=_iso(jetzt), grund="Fluchtweg", manuell_bis=None)
        else:
            bericht["fehlt"].append(name)
    return bericht


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

# Woran ein Rollo als Tür zu erkennen ist. Ein Rollladen vor einer Balkontür
# geht bis zum Boden; das sieht anders aus als eines vor einem Fenster mit
# Brüstung, und in der Anzeige soll man es auch so sehen.
TUER_WORTE = ("tür", "tuer", "door", "balkon", "terrasse")


def anzeigename(rollo: dict, index: dict) -> str:
    """Der Name, unter dem ein Rollo erscheint."""
    if rollo.get("name"):
        return rollo["name"]
    zustand = index.get(rollo["entity_id"])
    if zustand:
        name = (zustand.get("attributes") or {}).get("friendly_name")
        if name:
            return name
    return rollo["entity_id"]


def eigene_zustaende(einstellungen: dict, state: dict) -> dict:
    """Der Stand der eigenen Schalter, unter ihrem Präfix.

    So laufen eigene und fremde Bedingungen durch dieselbe Prüfung – die
    Zeitplanlogik muss nicht wissen, wem ein Schalter gehört.
    """
    gemerkt = state.get("schalter") or {}
    out = {}
    for eintrag in einstellungen.get("eigene_schalter") or []:
        wert = gemerkt.get(eintrag["id"], eintrag["vorgabe"])
        out[store.EIGEN_PREFIX + eintrag["id"]] = str(wert)
    return out


def _fenster_offen(rollo: dict, index: dict) -> list[str]:
    """Welche Kontakte dieses Rollos gerade offen sind.

    Solange einer offen ist, wird nicht zugefahren. Wer auf der Terrasse steht
    und das Rollo fährt vor der offenen Tür herunter, steht draußen.
    """
    offen = []
    for eid in rollo.get("fenster") or []:
        zustand = index.get(eid)
        if _an(zustand):
            offen.append((zustand.get("attributes") or {}).get("friendly_name") or eid)
    return offen


def _jemand_da(rollo: dict, index: dict) -> bool | None:
    melder = (rollo.get("praesenz") or []) + (rollo.get("personen") or [])
    if not melder:
        return None
    return any(_an(index.get(eid)) for eid in melder)


def _beschattung_pruefen(rollo: dict, einstellungen: dict, index: dict,
                         sonnenstand, jetzt: datetime,
                         war_beschattet: bool) -> tuple[bool, str, int | None]:
    """Steht die Sonne in diesem Fenster, und ist es warm genug?

    Die Hysterese hängt an der Temperatur, nicht am Sonnenstand: Ein Rollo,
    das an der Grenze zwischen 23,9 und 24,1 Grad im Minutentakt auf und ab
    fährt, ist schlimmer als gar kein Hitzeschutz.
    """
    global_ = einstellungen.get("beschattung") or {}
    if not global_.get("aktiv", True) or not rollo.get("beschattung"):
        return False, "", None
    if rollo.get("ausrichtung") is None:
        return False, "", None

    elevation, azimut = sonnenstand.stand(jetzt)
    if not sonnenmodul.sonne_steht_im_fenster(
            azimut, elevation, rollo.get("ausrichtung"),
            float(rollo.get("oeffnungswinkel") or 90),
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

    if rollo.get("raumtemp") and rollo.get("raumtemp_ab") is not None:
        innen = _temperatur(rollo["raumtemp"], index)
        if innen is not None and innen < float(rollo["raumtemp_ab"]):
            return False, "", None

    if global_.get("nur_wenn_niemand_da") and _jemand_da(rollo, index):
        return False, "", None

    position = rollo.get("beschattung_position")
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


def _plan_von(rollo: dict, plaene: dict,
              gruppe: dict | None = None) -> tuple[list, dict | None]:
    """Welchen Schaltpunkten folgt dieses Rollo – und wem gehört der Plan?

    Liefert (Schaltpunkte, Plan). Ohne Plan-ID hat das Rollo einen eigenen;
    dann ist der zweite Wert ``None``.

    Die **Obergruppe legt dazu**, sie ersetzt nicht: Hat sie einen eigenen
    Zeitplan, gelten seine Punkte für alle ihre Rollos – so wie früher die
    Automation „Rollo schliessen EG" neben den Einzelautomationen lief.
    Welcher Punkt am Ende gilt, entscheidet wie immer der zuletzt fällige.
    """
    if rollo.get("plan"):
        plan = plaene.get(rollo["plan"])
        eigene = plan["zeitplan"] if plan else []
    else:
        plan, eigene = None, rollo.get("zeitplan") or []

    if gruppe and gruppe.get("aktiv", True) and gruppe.get("plan"):
        gruppenplan = plaene.get(gruppe["plan"])
        if gruppenplan and gruppenplan.get("aktiv", True):
            return list(eigene) + list(gruppenplan.get("zeitplan") or []), plan
    return eigene, plan


def _rollo_rechnen(rollo: dict, einstellungen: dict, index: dict, state: dict,
                   kalender, sonnenstand, jetzt: datetime, lage: dict,
                   plaene: dict, gruppe: dict | None = None) -> dict:
    """Was dieses Rollo jetzt tun soll – mitsamt Begründung.

    Liefert ein Ergebnis, auch wenn nichts zu tun ist: Die Oberfläche soll
    jederzeit erklären können, warum ein Rollo steht, wo es steht.
    """
    eid = rollo["entity_id"]
    rollo_state = state["rollos"].setdefault(eid, {})
    zustand = index.get(eid)
    punkte, plan = _plan_von(rollo, plaene, gruppe)
    invertiert = bool(einstellungen.get("prozent_invertiert"))

    ergebnis = {
        "entity_id": eid,
        "name": anzeigename(rollo, index),
        "raum": rollo.get("raum") or "",
        "gruppe": (gruppe or {}).get("name") or "",
        "gruppe_id": (gruppe or {}).get("id") or "",
        "hitzeschutz": bool(rollo.get("beschattung")),
        "ausrichtung": rollo.get("ausrichtung"),
        "art": rollo.get("art") or "fenster",
        "ist": ha_api.position_von(zustand),
        "zustand": "plan",
        "begruendung": "",
        "ziel": None,
        "gefahren": False,
        "plan": plan["name"] if plan else "",
        "plan_id": rollo.get("plan") or "",
        "helfer": _bedienbare_helfer(rollo, punkte, index, einstellungen,
                                     lage["zustaende"]),
    }

    # 1. Rauch ----------------------------------------------------------------
    # Ganz oben, weil die Fluchtweg-Freigabe über allem steht. Gefahren wird
    # hier nicht: Das erledigt ``_fluchtweg`` einmal zentral, damit der
    # Fluchtweg nicht an der Automatik hängt. Hier steht nur, was gilt.
    if lage["rauch"]:
        freigabe = lage.get("fluchtweg") or {}
        if (freigabe.get("aktiv") and rollo.get("aktiv", True)
                and rollo.get("fluchtweg", True)):
            ergebnis.update(zustand="fluchtweg",
                            begruendung="Fluchtweg offen – " + lage["rauch_grund"])
        else:
            ergebnis.update(zustand="rauch", begruendung=lage["rauch_grund"])
        return ergebnis

    # 2. aus ------------------------------------------------------------------
    # „Abgeschaltet" ist die Automatik, nicht das Rollo. Das Rollo hängt weiter
    # da, meldet seine Stellung und lässt sich von Hand fahren – der Planer
    # fasst es nur nicht mehr nach Plan an. Wer hier „Rollo ist abgeschaltet"
    # liest, sucht nach einem Defekt, den es nicht gibt.
    if not rollo.get("aktiv", True):
        ergebnis.update(zustand="aus",
                        begruendung="Automatik für dieses Rollo ist aus")
        return ergebnis
    if rollo.get("betriebsart") == "von_hand":
        ergebnis.update(zustand="von_hand",
                        begruendung="Ohne Zeitplan – wird von Hand gefahren")
        return ergebnis
    if not lage["automatik"]:
        ergebnis.update(zustand="aus",
                        begruendung="Automatik ist insgesamt aus")
        return ergebnis
    if plan is not None and not plan.get("aktiv", True):
        ergebnis.update(zustand="gesperrt",
                        begruendung=f"Zeitplan „{plan['name']}“ ist abgeschaltet")
        return ergebnis
    if gruppe is not None and not gruppe.get("aktiv", True):
        ergebnis.update(zustand="gesperrt",
                        begruendung=f"Gruppe „{gruppe['name']}“ ist abgeschaltet")
        return ergebnis
    if gruppe is not None and gruppe.get("schalter"):
        # Ein eigener Schalter des Planers, kein fremder: Sein Stand steht in
        # denselben Zuständen, durch die auch die Bedingungen an den
        # Schaltpunkten laufen.
        stand = lage["zustaende"].get(store.EIGEN_PREFIX + gruppe["schalter"])
        if stand is not None and str(stand).lower() in ("off", "aus", "false", "0"):
            ergebnis.update(zustand="gesperrt",
                            begruendung=f"Gruppe „{gruppe['name']}“ ist nicht freigegeben")
            return ergebnis

    if zustand is None:
        ergebnis.update(zustand="fehlt", begruendung="In Home Assistant nicht gefunden")
        return ergebnis
    if zustand.get("state") == "unavailable":
        ergebnis.update(zustand="fehlt", begruendung="Nicht erreichbar")
        return ergebnis

    # Der Zeitplan ist die Grundlage; Urlaub und Hitzeschutz verschieben ihn.
    anpassen = _urlaubsversatz(rollo, einstellungen, lage)
    zustaende = lage["zustaende"]
    treffer = zeitplanmodul.letzter_zeitpunkt(punkte, jetzt, kalender, sonnenstand,
                                              anpassen, zustaende)
    naechster = zeitplanmodul.naechster_wechsel(punkte, jetzt, kalender, sonnenstand,
                                                anpassen, zustaende)

    ziel = None
    punkt_zeit = None
    beschreibung = ""
    if treffer:
        punkt_zeit, punkt = treffer
        ziel = int(punkt["position"])
        beschreibung = zeitplanmodul.beschreibung(punkt, invertiert=invertiert)

    if naechster:
        ergebnis["naechster_zeitpunkt"] = _iso(naechster[0])
        ergebnis["naechste_uhrzeit"] = naechster[0].strftime("%H:%M")
        ergebnis["naechste_stellung"] = int(naechster[1]["position"])
        ergebnis["naechster_punkt"] = zeitplanmodul.beschreibung(
            naechster[1], invertiert=invertiert)

    # 3. Urlaub ---------------------------------------------------------------
    urlaub = einstellungen.get("urlaub") or {}
    if lage["urlaub"] and urlaub.get("modus") != "plan":
        ergebnis["urlaub"] = True
        ergebnis["zustand"] = "urlaub"
        if urlaub.get("modus") == "zu" or not rollo.get("urlaub_simulation", True):
            ziel = int(rollo.get("position_zu", 0))
            punkt_zeit = lage["urlaub_seit"] or punkt_zeit
            beschreibung = "Urlaub – geschlossen"
        elif anpassen is not None and treffer:
            versatz = int((punkt_zeit - _roh_zeitpunkt(
                treffer[1], punkt_zeit, kalender, sonnenstand)).total_seconds() // 60)
            if versatz:
                beschreibung += f" (Urlaubssimulation {versatz:+d} min)"

    # 4. Hitzeschutz ----------------------------------------------------------
    war_beschattet = bool(rollo_state.get("beschattet"))
    beschatten, beschattungsgrund, beschattungsposition = _beschattung_pruefen(
        rollo, einstellungen, index, sonnenstand, jetzt, war_beschattet)
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

    ergebnis["fenster_offen"] = _fenster_offen(rollo, index)
    ergebnis["begruendung"] = beschreibung
    ergebnis["ziel"] = ziel
    ergebnis["punkt_zeit"] = _iso(punkt_zeit)
    return ergebnis


def _eigene_entitaet(index: dict, domain: str, name: str) -> str:
    """Die Entität, unter der ein eigener Schalter in Home Assistant steht.

    Nicht raten, nachsehen. Die entity_id wird **einmal** beim Anlegen aus dem
    Namen gebildet und ändert sich beim Umbenennen nie – der Anzeigename schon.
    Wer sie aus dem aktuellen Namen zurückrechnet, zeigt nach einer Umbenennung
    auf eine Entität, die es nicht gibt: Am 27.08.2026 wurde aus „Erdgeschoss"
    der Schalter „EG öffnen", und er verschwand von der Karte, obwohl er in
    Home Assistant unverändert als ``switch.rolloplaner_erdgeschoss`` stand.

    Gesucht wird über den Anzeigenamen, denn der folgt der Umbenennung. Home
    Assistant stellt den Gerätenamen voran; beides wird geprüft. Findet sich
    nichts, bleibt die alte Schätzung – besser als gar keine Entität.
    """
    gesucht = (name or "").strip().casefold()
    for eid, zustand in index.items():
        if not eid.startswith(domain + ".rolloplaner_"):
            continue
        anzeige = ((zustand.get("attributes") or {}).get("friendly_name") or "").strip()
        if anzeige.casefold() == gesucht:
            return eid
        if anzeige.casefold() == f"rolloplaner {gesucht}":
            return eid
    return f"{domain}.rolloplaner_{_slug(name)}"


def _bedienbare_helfer(rollo: dict, punkte: list, index: dict,
                       einstellungen: dict, zustaende: dict) -> list[dict]:
    """Die Schalter, an denen die Schaltpunkte dieses Rollos hängen.

    Damit kann die Dashboard-Karte sie gleich mitbedienen – sonst müsste man
    für „die Terrassentür heute mal nicht zufahren“ die Karte verlassen und
    den Schalter anderswo suchen.
    """
    stellungen: dict[str, set] = {}
    reihenfolge: list[str] = []
    for punkt in punkte:
        position = int(punkt.get("position", 100))
        art = "auf" if position >= 100 else "zu" if position <= 0 else "teil"
        for bedingung in punkt.get("wenn") or []:
            eid = bedingung.get("entity")
            if not eid:
                continue
            if eid not in stellungen:
                stellungen[eid] = set()
                reihenfolge.append(eid)
            stellungen[eid].add(art)

    eigene = {e["id"]: e for e in (einstellungen.get("eigene_schalter") or [])}
    out = []
    for eid in reihenfolge:
        kennung = store.eigener_schalter(eid)
        if kennung is not None:
            eintrag = eigene.get(kennung)
            if eintrag is None:
                continue
            domain = "select" if eintrag["art"] == "auswahl" else "switch"
            zustand = {"attributes": {"friendly_name": eintrag["name"],
                                      "options": eintrag["optionen"]},
                       "state": zustaende.get(eid, eintrag["vorgabe"])}
            eid_ha = _eigene_entitaet(index, domain, eintrag["name"])
        else:
            zustand = index.get(eid)
            if zustand is None:
                continue
            eid_ha = eid
        attrs = zustand.get("attributes") or {}
        arten = stellungen.get(eid) or set()
        wirkung = ("oeffnen" if arten == {"auf"} else
                   "schliessen" if arten == {"zu"} else "beides")
        out.append({
            "entity_id": eid_ha,
            "eigen": kennung,
            "name": attrs.get("friendly_name") or eid,
            "zustand": zustand.get("state"),
            "optionen": list(attrs.get("options") or []),
            "wirkung": wirkung,
        })
    return out


def _slug(text: str) -> str:
    """Wie der MQTT-Publisher: derselbe Slug, damit die Entity-ID stimmt."""
    import re
    text = (text.lower()
            .replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss"))
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_") or "schalter"


def _urlaubsversatz(rollo: dict, einstellungen: dict, lage: dict):
    """Die Funktion, die jeden Schaltpunkt um den Tagesversatz verschiebt.

    ``None``, wenn nicht simuliert wird – dann bleibt der Zeitplan unberührt.
    """
    urlaub = einstellungen.get("urlaub") or {}
    if not lage["urlaub"] or urlaub.get("modus") != "simulation":
        return None
    if not rollo.get("urlaub_simulation", True):
        return None
    streuung = int(urlaub.get("streuung_min", 20))
    if streuung <= 0:
        return None

    def anpassen(zeitpunkt: datetime, eintrag: dict, tag) -> datetime:
        # Der Schlüssel hängt am Rollo: Zwei Rollos am selben Zeitplan sollen
        # verschieden streuen, sonst fährt das halbe Haus wieder im Gleichtakt.
        schluessel = (f"{rollo['entity_id']}|{tag}|{eintrag.get('ausloeser')}|"
                      f"{eintrag.get('start')}|{eintrag.get('position')}")
        versatz = _versatz_fuer(lage["simulation"], schluessel, streuung)
        return _in_fenster(zeitpunkt + timedelta(minutes=versatz), urlaub)

    return anpassen


def _roh_zeitpunkt(eintrag: dict, verschoben: datetime, kalender, sonnenstand) -> datetime:
    """Der unverschobene Zeitpunkt – nur, um den Versatz anzeigen zu können."""
    roh = zeitplanmodul.zeitpunkt_von(eintrag, verschoben.date(), sonnenstand)
    return roh if roh is not None else verschoben


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

def _rollo_stellen(rollo: dict, ergebnis: dict, einstellungen: dict, index: dict,
                   state: dict, jetzt: datetime, protokoll) -> None:
    """Das Rollo auf die errechnete Stellung bringen.

    Hier entscheidet sich, ob überhaupt gefahren wird. Vier Gründe, es zu
    lassen: Es steht schon richtig, der Schaltpunkt ist nicht neu, jemand hat
    von Hand gefahren, oder ein Fenster steht offen.
    """
    eid = rollo["entity_id"]
    rollo_state = state["rollos"].setdefault(eid, {})
    ziel = ergebnis.get("ziel")
    trockenlauf = bool(einstellungen.get("trockenlauf"))
    beobachten = rollo.get("betriebsart") == "beobachten"

    if ziel is None or ergebnis["zustand"] in ("aus", "rauch", "fluchtweg",
                                               "gesperrt", "ohne_plan", "fehlt"):
        return

    punkt_zeit = _aus_iso(ergebnis.get("punkt_zeit"))
    zuletzt = _aus_iso(rollo_state.get("letzter_punkt"))
    beschattung_wechsel = bool(rollo_state.get("beschattet")) != bool(ergebnis["beschattet"])

    # Die Flanke: ein Schaltpunkt zählt nur, wenn er seit dem letzten Mal neu
    # dazugekommen ist.
    neuer_punkt = punkt_zeit is not None and (zuletzt is None or punkt_zeit > zuletzt)
    if not neuer_punkt and not beschattung_wechsel:
        ergebnis["begruendung"] = ergebnis["begruendung"] or "unverändert"
        _stellung_erfassen(rollo, ergebnis, index, state, jetzt, einstellungen)
        return

    # „Nur schließen“: der Planer fährt zu, öffnet aber nie von selbst.
    if rollo.get("betriebsart") == "nur_schliessen" and ziel > int(rollo.get("position_zu", 0)):
        ergebnis["zustand"] = "nur_schliessen"
        ergebnis["begruendung"] = "Betriebsart „nur schließen“ – bleibt in Ruhe"
        rollo_state["letzter_punkt"] = _iso(punkt_zeit)
        return

    zustand = index.get(eid)
    ist = ha_api.position_von(zustand)
    offen = ergebnis.get("fenster_offen") or []

    # Fenster offen: Zufahren wird unterdrückt, Öffnen bleibt erlaubt.
    if offen and ist is not None and ziel < ist:
        ergebnis["zustand"] = "fenster"
        ergebnis["begruendung"] = "Offen: " + ", ".join(offen)
        # Der Punkt bleibt offen. Sobald die Tür zugeht, wird er nachgeholt –
        # und zwar der dann *zuletzt fällige*.
        ergebnis["aufgeschoben"] = True
        rollo_state["beschattet"] = bool(ergebnis["beschattet"])
        return

    # Handbetrieb: Steht das Rollo woanders, als der Planer es zuletzt
    # hingefahren hat, war jemand am Schalter. Ein neu fälliger Schaltpunkt
    # beendet die Schonfrist – sonst müsste man daran denken, sie aufzuheben.
    manuell_bis = _aus_iso(rollo_state.get("manuell_bis"))
    if (einstellungen.get("manuell_respektieren") and manuell_bis
            and jetzt < manuell_bis and not neuer_punkt):
        ergebnis["zustand"] = "manuell"
        ergebnis["begruendung"] = f"Handbetrieb bis {manuell_bis.strftime('%H:%M')} Uhr"
        return

    if ist is not None and abs(ist - ziel) <= TOLERANZ:
        ergebnis["hinweis"] = "steht schon richtig"
        rollo_state["letzter_punkt"] = _iso(punkt_zeit)
        rollo_state["beschattet"] = bool(ergebnis["beschattet"])
        rollo_state["ziel"] = ziel
        return

    if trockenlauf or beobachten:
        ergebnis["hinweis"] = "Trockenlauf" if trockenlauf else "beobachten"
        ergebnis["gefahren"] = True
    else:
        erfolg = ha_api.set_position(eid, ziel, zustand)
        ergebnis["gefahren"] = erfolg
        if erfolg:
            rollo_state.update(ziel=ziel, gesetzt_am=_iso(jetzt),
                               grund=ergebnis["begruendung"], manuell_bis=None)
        else:
            ergebnis["hinweis"] = "Fahrbefehl abgelehnt"

    if ergebnis["gefahren"]:
        invertiert = bool(einstellungen.get("prozent_invertiert"))
        was = ("auf" if ziel >= 100 else "zu" if ziel <= 0
               else f"{100 - ziel if invertiert else ziel} %")
        protokoll(ergebnis["name"], was,
                  ergebnis["begruendung"] + (" (Trockenlauf)" if trockenlauf else ""),
                  eid, art="warnung" if trockenlauf else None)

    # Der Schaltpunkt gilt als abgearbeitet – auch im Trockenlauf, sonst
    # meldete das Protokoll alle zwei Minuten dasselbe. Beim Beenden des
    # Trockenlaufs wird dieser Merkposten verworfen (``_durchsetzen``).
    if punkt_zeit is not None:
        rollo_state["letzter_punkt"] = _iso(punkt_zeit)
    rollo_state["beschattet"] = bool(ergebnis["beschattet"])
    # ``ziel`` heißt „dorthin habe ich es geschickt“ und wird deshalb nur beim
    # wirklichen Fahren fortgeschrieben (weiter oben). Im Trockenlauf stünde
    # sonst ein Ziel im Zustand, das nie jemand angefahren hat – und die
    # Handbetriebserkennung hielte die Abweichung für einen Griff ans Rollo.


def _stellung_erfassen(rollo: dict, ergebnis: dict, index: dict, state: dict,
                       jetzt: datetime, einstellungen: dict) -> None:
    """Ohne Schaltvorgang: nur nachsehen, wo das Rollo steht.

    Dabei fällt der Handbetrieb auf – die einzige Stelle, an der er überhaupt
    erkannt werden kann, denn Home Assistant sagt nicht, wer gefahren ist.
    Erkannt wird er daran, dass das Rollo woanders steht, als der Planer es
    zuletzt hingeschickt hat.

    Im **Trockenlauf** ist diese Schlussfolgerung wertlos: Dort schickt der
    Planer nichts, also bewegt sich jedes Rollo von woanders her – die alten
    Automationen tun schließlich weiter ihren Dienst. Er meldete dann
    reihenweise „Handbetrieb“ und legte sich selbst für zwölf Stunden still,
    statt zu zeigen, was er täte. Dasselbe gilt für ein Rollo auf
    „beobachten“.
    """
    if (einstellungen.get("trockenlauf")
            or rollo.get("betriebsart") == "beobachten"):
        return
    eid = rollo["entity_id"]
    zustand = index.get(eid)
    ist = ha_api.position_von(zustand)
    rollo_state = state["rollos"].setdefault(eid, {})
    gesetzt = _aus_iso(rollo_state.get("gesetzt_am"))
    eigenes_ziel = rollo_state.get("ziel")
    stunden = float(einstellungen.get("manuell_stunden", 12.0))

    if (ist is not None and eigenes_ziel is not None
            and abs(ist - int(eigenes_ziel)) > TOLERANZ
            and gesetzt and jetzt - gesetzt > timedelta(minutes=FAHRZEIT_MIN)
            and not ha_api.faehrt(zustand)):
        if not rollo_state.get("manuell_bis"):
            rollo_state["manuell_bis"] = _iso(jetzt + timedelta(hours=stunden))
        ergebnis["hinweis"] = "von Hand gefahren"
        ergebnis["zustand"] = "manuell"


# ------------------------------------------------------------------ Takt ----

def takt(config: dict, state: dict, protokoll, wachhund_haken=None) -> dict:
    """Ein Durchlauf: alle Rollos rechnen und, wo nötig, fahren.

    ``wachhund_haken`` bekommt die bereits geladenen Zustände gereicht. Ohne
    ihn müsste der Wächter ``/states`` ein zweites Mal abrufen – anderthalb
    Megabyte, alle zwei Minuten, für dieselbe Auskunft.
    """
    einstellungen = config["einstellungen"]
    jetzt = _jetzt()
    bericht = {"zeit": _iso(jetzt), "rollos": [], "stoerungen": []}

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

    rauch, rauch_grund, akut, rauch_orte = _rauchsperre(
        einstellungen, index, state, jetzt)
    # Ein Alarm ist neu, sobald ein Melder anschlägt und noch keiner lief.
    # Gemerkt wird das getrennt von der Fluchtweg-Freigabe: Gemeldet gehört ein
    # Rauchalarm auch dann, wenn die Freigabe abgeschaltet ist.
    rauch_neu = bool(akut and not state.get("rauch_seit"))
    if akut and not state.get("rauch_seit"):
        state["rauch_seit"] = _iso(jetzt)
    elif not rauch:
        state["rauch_seit"] = None
    fluchtweg = _fluchtweg(config, einstellungen, index, state, jetzt, rauch, akut)

    elevation, azimut = sonnenstand.stand(jetzt)
    lage = {
        "automatik": bool(einstellungen.get("automatik", True)),
        "urlaub": urlaub,
        "urlaub_seit": _aus_iso(state.get("urlaub_seit")),
        "rauch": rauch,
        "rauch_grund": rauch_grund,
        "fluchtweg": fluchtweg,
        "simulation": _versatz_wuerfeln(
            state, jetzt, int((einstellungen.get("urlaub") or {}).get("streuung_min", 20))),
        # Für die Bedingungen an Schaltpunkten: entity_id → Zustand als Text.
        # Die eigenen Schalter stehen unter ihrem Präfix mit darin, damit
        # eigene und fremde durch dieselbe Prüfung laufen.
        "zustaende": {**{eid: z.get("state") for eid, z in index.items()},
                      **eigene_zustaende(einstellungen, state)},
    }

    plaene = {p["id"]: p for p in config.get("plaene") or []}

    # Welches Rollo liegt in welcher Obergruppe? Die Zuordnung steht an der
    # Gruppe, gebraucht wird sie am Rollo.
    gruppe_von = {eid: g for g in (config.get("gruppen") or [])
                  for eid in g.get("rollos") or []}

    for rollo in config.get("rollos") or []:
        ergebnis = _rollo_rechnen(rollo, einstellungen, index, state, kalender,
                                  sonnenstand, jetzt, lage, plaene,
                                  gruppe_von.get(rollo["entity_id"]))
        try:
            _rollo_stellen(rollo, ergebnis, einstellungen, index, state, jetzt, protokoll)
        except Exception as err:  # noqa: BLE001 – eines darf die übrigen nicht mitreißen
            _LOGGER.exception("Rollo %s fehlgeschlagen", rollo.get("entity_id"))
            ergebnis["begruendung"] = f"Fehler: {err}"
        bericht["rollos"].append(ergebnis)

    if wachhund_haken is not None:
        try:
            bericht["stoerungen"] = wachhund_haken(index, jetzt)
        except Exception:  # noqa: BLE001 – der Wächter darf den Takt nicht kippen
            _LOGGER.exception("Wächter fehlgeschlagen")

    # Welcher Schalter betrifft welche Rollos? Ohne diese Auskunft sieht in der
    # Karte jeder Schalter aus, als gehöre er dem Rollo, in dessen Kachel er
    # steht – und wer „Obergeschoss schließen“ bei Nele ausschaltet, wundert
    # sich, warum es bei Luna auch verschwindet. Es ist derselbe Schalter.
    freigaben: dict[str, dict] = {}
    for ergebnis in bericht["rollos"]:
        for helfer in ergebnis.get("helfer") or []:
            eintrag = freigaben.setdefault(helfer["entity_id"], {
                **{k: v for k, v in helfer.items() if k != "wirkung"},
                "wirkungen": [], "rollos": [], "raeume": []})
            eintrag["rollos"].append(ergebnis["name"])
            raum = ergebnis.get("raum") or ""
            if raum not in eintrag["raeume"]:
                eintrag["raeume"].append(raum)
            if helfer["wirkung"] not in eintrag["wirkungen"]:
                eintrag["wirkungen"].append(helfer["wirkung"])
    for eintrag in freigaben.values():
        # Als „geteilt“ gilt, was **über einen Raum hinaus** wirkt. Dass ein
        # Schalter beide Rollos in Lunas Zimmer betrifft, überrascht niemanden;
        # dass derselbe Schalter auch bei Nele hängt, sehr wohl – und genau das
        # gehört sichtbar nach oben, statt in beiden Kacheln als eigener
        # Schalter aufzutreten.
        eintrag["geteilt"] = len(eintrag["raeume"]) > 1
    for ergebnis in bericht["rollos"]:
        for helfer in ergebnis.get("helfer") or []:
            helfer["geteilt"] = freigaben[helfer["entity_id"]]["geteilt"]

    # Die Zeitpläne mit ihrem Stand – für die Karte und die Übersicht.
    plan_bericht = []
    for plan in config.get("plaene") or []:
        folger = [r for r in bericht["rollos"] if r.get("plan_id") == plan["id"]]
        plan_bericht.append({
            "id": plan["id"], "name": plan["name"], "aktiv": plan.get("aktiv", True),
            "rollos": [r["name"] for r in folger],
            "punkte": len(plan.get("zeitplan") or []),
        })

    bericht.update({
        "plaene": plan_bericht,
        "freigaben": sorted(freigaben.values(), key=lambda e: e["name"]),
        "prozent_invertiert": bool(einstellungen.get("prozent_invertiert")),
        "automatik": lage["automatik"],
        "trockenlauf": bool(einstellungen.get("trockenlauf")),
        "urlaub": urlaub,
        "schulfrei": schulfrei,
        "schulfrei_morgen": schulfrei_morgen,
        "rauch": rauch,
        "rauch_grund": rauch_grund,
        "rauch_akut": akut,
        "rauch_orte": rauch_orte,
        "rauch_neu": rauch_neu,
        "rauch_seit": state.get("rauch_seit"),
        "fluchtweg": fluchtweg,
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
