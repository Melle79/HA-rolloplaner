"""Bestehende Rollladen-Automationen einlesen und in Räume übersetzen.

Wer den Planer einrichtet, hat seine Rollos meist schon irgendwie geregelt –
in diesem Haus waren es dreizehn Automationen mit neun Hilfsschaltern. Die
alle von Hand abzutippen ist Fleißarbeit mit hoher Fehlerquote: Genau die
Zeiten, die man abschreibt, sind die, die abends niemandem auffallen, wenn sie
falsch sind.

Deshalb liest der Planer ``automations.yaml`` und schlägt vor, was er dort
findet. Übernommen wird **nichts** von selbst – der Vorschlag landet in der
Oberfläche, wird dort geprüft und erst dann angelegt.

Was erkannt wird:

* Auslöser ``time`` (feste Uhrzeit) und ``sun`` (Auf-/Untergang mit Versatz)
* Bedingungen auf die Schulfrei-Helfer – auch die auf **morgen**, an denen die
  Kinderzimmer hängen
* Zeitbedingungen ``after``/``before``, die einen Sonnenauslöser einklammern
* der Freigabe-Helfer, der in fast jeder dieser Automationen als Bedingung steht
"""
from __future__ import annotations

import logging
import os
import re

_LOGGER = logging.getLogger(__name__)

CONFIG_DIRS = ("/homeassistant", "/config")
DATEI = "automations.yaml"

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)(:([0-5]\d))?$")


def _yaml_laden(pfad: str):
    try:
        import yaml
    except ImportError:  # pragma: no cover – die Bibliothek liegt im Image
        _LOGGER.warning("PyYAML fehlt – Automationen können nicht gelesen werden")
        return None
    try:
        with open(pfad, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("%s nicht lesbar: %s", pfad, err)
        return None


def automationen_lesen() -> list[dict]:
    for verzeichnis in CONFIG_DIRS:
        pfad = os.path.join(verzeichnis, DATEI)
        if os.path.exists(pfad):
            daten = _yaml_laden(pfad)
            if isinstance(daten, list):
                return daten
    return []


def _liste(wert) -> list:
    if wert is None:
        return []
    return wert if isinstance(wert, list) else [wert]


def _ziele(aktion: dict) -> list[str]:
    ziel = aktion.get("target") or {}
    eids = _liste(ziel.get("entity_id")) + _liste((aktion.get("data") or {}).get("entity_id"))
    if isinstance(aktion.get("entity_id"), (str, list)):
        eids += _liste(aktion["entity_id"])
    return [e for e in eids if isinstance(e, str) and e.startswith("cover.")]


def _stellung(aktion: dict) -> int | None:
    dienst = aktion.get("action") or aktion.get("service") or ""
    if dienst == "cover.open_cover":
        return 100
    if dienst == "cover.close_cover":
        return 0
    if dienst == "cover.set_cover_position":
        wert = (aktion.get("data") or {}).get("position")
        try:
            return max(0, min(100, int(wert)))
        except (TypeError, ValueError):
            return None
    return None


def _trigger_ids(bedingungen) -> set[str] | None:
    """Auf welche Auslöser-IDs schränkt dieser Zweig ein?

    ``condition: trigger`` ist der Grund, warum eine einzige Automation drei
    verschiedene Dinge tun kann. Wer sie ignoriert, kreuzt jeden Auslöser mit
    jeder Aktion – und liest aus der Büro-Automation heraus, dass das Rollo bei
    Sonnenaufgang gleichzeitig auf und zu fahren soll.
    """
    ids: set[str] = set()
    for bedingung in _liste(bedingungen):
        if isinstance(bedingung, dict) and bedingung.get("condition") == "trigger":
            ids.update(str(i) for i in _liste(bedingung.get("id")))
    return ids or None


def _aktionen_durchgehen(knoten, treffer: list, ids: set[str] | None = None,
                         klammer: dict | None = None) -> None:
    """Rekursiv durch ``choose``/``if``/``sequence`` nach cover-Aufrufen suchen.

    ``ids`` und ``klammer`` tragen mit, unter welcher Bedingung der gerade
    besuchte Zweig überhaupt läuft: für welche Auslöser, und in welchem
    Zeitfenster.
    """
    for eintrag in _liste(knoten):
        if not isinstance(eintrag, dict):
            continue
        stellung = _stellung(eintrag)
        if stellung is not None:
            ziele = _ziele(eintrag)
            if ziele:
                treffer.append((stellung, ziele, ids, klammer or {}))

        # ``if``/``then``: die Bedingungen gelten für den then-Zweig
        if "if" in eintrag:
            zweig_ids = _trigger_ids(eintrag["if"]) or ids
            zweig_klammer = _zeitklammer(eintrag["if"]) or klammer
            _aktionen_durchgehen(eintrag.get("then"), treffer, zweig_ids, zweig_klammer)
            _aktionen_durchgehen(eintrag.get("else"), treffer, ids, klammer)
            continue
        for schluessel in ("sequence", "default", "actions"):
            if schluessel in eintrag:
                _aktionen_durchgehen(eintrag[schluessel], treffer, ids, klammer)
        for zweig in _liste(eintrag.get("choose")):
            if isinstance(zweig, dict):
                zweig_ids = _trigger_ids(zweig.get("conditions")) or ids
                zweig_klammer = _zeitklammer(zweig.get("conditions")) or klammer
                _aktionen_durchgehen(zweig.get("sequence"), treffer,
                                     zweig_ids, zweig_klammer)


def _zeitklammer(bedingungen) -> dict | None:
    """Zeitbedingungen eines Zweiges als Klammer lesen.

    Mehrere ``condition: time`` mit **verschiedenen** Wochentagen sind
    UND-verknüpft und können nie gleichzeitig zutreffen – so ein Zweig ist
    toter Code. Das wird gemeldet, statt es stillschweigend zu übernehmen.
    """
    zeiten = [b for b in _liste(bedingungen)
              if isinstance(b, dict) and b.get("condition") == "time"]
    if not zeiten:
        return None
    tagesmengen = [frozenset(_wochentage(b.get("weekday")) or ALLE_TAGE) for b in zeiten]
    if len(zeiten) > 1 and not frozenset.intersection(*tagesmengen):
        return {"widerspruch": True}
    erste = zeiten[0]
    return {"frueh": _aufrunden(erste.get("after")),
            "spaet": _uhrzeit(erste.get("before")),
            "tage": _wochentage(erste.get("weekday"))}


def _uhrzeit(text) -> str:
    if not isinstance(text, str):
        return ""
    treffer = _TIME_RE.match(text.strip())
    if not treffer:
        return ""
    return f"{int(treffer.group(1)):02d}:{treffer.group(2)}"


def _ausloeser(automation: dict) -> list[dict]:
    """Die Auslöser einer Automation in Schaltpunkt-Bruchstücke übersetzen."""
    out = []
    for ausloeser in _liste(automation.get("triggers") or automation.get("trigger")):
        if not isinstance(ausloeser, dict):
            continue
        art = ausloeser.get("trigger") or ausloeser.get("platform")
        kennung = str(ausloeser.get("id")) if ausloeser.get("id") else None
        if art == "time":
            for wert in _liste(ausloeser.get("at")):
                zeit = _uhrzeit(wert)
                if zeit:
                    out.append({"ausloeser": "uhrzeit", "start": zeit, "id": kennung,
                                "tage": _wochentage(ausloeser.get("weekday"))})
        elif art == "sun":
            ereignis = ("sonnenaufgang" if ausloeser.get("event") == "sunrise"
                        else "sonnenuntergang")
            versatz = _versatz(ausloeser.get("offset"))
            out.append({"ausloeser": ereignis, "start": "", "versatz_min": versatz,
                        "id": kennung, "tage": None})
    return out


def _versatz(roh) -> int:
    """``offset: "-00:30:00"`` in Minuten."""
    if roh in (None, "", 0):
        return 0
    if isinstance(roh, (int, float)):
        return int(roh // 60)
    text = str(roh).strip()
    vorzeichen = -1 if text.startswith("-") else 1
    teile = text.lstrip("+-").split(":")
    try:
        stunden, minuten = int(teile[0]), int(teile[1]) if len(teile) > 1 else 0
    except ValueError:
        return 0
    return vorzeichen * (stunden * 60 + minuten)


TAGE_KURZ = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _wochentage(roh) -> list[str] | None:
    tage = [t for t in _liste(roh) if isinstance(t, str) and t.lower() in TAGE_KURZ]
    return [t.lower() for t in tage] or None


def _bedingungen(automation: dict, schulfrei_entity: str,
                 schulfrei_morgen_entity: str) -> dict:
    """Bedingungen deuten: Geltung, Klammern und Freigabeschalter."""
    ergebnis = {"gilt": "immer", "frueh": "", "spaet": "", "freigabe": "",
                "tage": None, "wenn": [], "unbekannt": []}
    for bedingung in _liste(automation.get("conditions") or automation.get("condition")):
        if not isinstance(bedingung, dict):
            continue
        art = bedingung.get("condition")
        if art == "state":
            for eid in _liste(bedingung.get("entity_id")):
                zustand = _liste(bedingung.get("state"))
                an = "on" in [str(z) for z in zustand]
                if eid == schulfrei_entity:
                    ergebnis["gilt"] = "schulfrei" if an else "schultag"
                elif eid == schulfrei_morgen_entity:
                    ergebnis["gilt"] = "morgen_schulfrei" if an else "morgen_schultag"
                elif len(zustand) == 1:
                    # Jede andere Zustandsbedingung wird eine Bedingung am
                    # Schaltpunkt. Der Auswahlhelfer der Terrassentür
                    # (normal / 24 Uhr / aus) ist genau das: drei Automationen,
                    # von denen je nach Stellung eine greift – im Planer drei
                    # Schaltpunkte mit je einer Bedingung. Bei „aus“ greift
                    # keiner, und das Rollo bleibt oben.
                    # Auch die Freigabe-Helfer landen hier, und das ist
                    # Absicht: In diesem Haus hängen Öffnen und Schließen an
                    # **verschiedenen** Schaltern – `rollosteuerung_erdgeschoss`
                    # gibt das Öffnen frei, `helfer_rollo_eg_schliessen` das
                    # Zufahren. Ein raumweiter Freigabeschalter kann das nicht
                    # abbilden; er würde beim Übernehmen eines der beiden
                    # stillschweigend unterschlagen. Was allen Punkten eines
                    # Raumes gemeinsam ist, wird weiter unten trotzdem zum
                    # Raumschalter hochgezogen.
                    ergebnis["wenn"].append({"entity": eid, "wert": str(zustand[0])})
                else:
                    ergebnis["unbekannt"].append(
                        f"{eid} mit mehreren erlaubten Werten")
        elif art == "time":
            # „after 08:29:59“ heißt: nicht vor halb neun – das ist die
            # Klammer um einen Sonnenauslöser. Die krumme Sekunde stammt
            # daher, dass die Automation sie als Vergleich schreibt.
            nach = _uhrzeit(bedingung.get("after"))
            vor = _uhrzeit(bedingung.get("before"))
            if nach:
                ergebnis["frueh"] = _aufrunden(bedingung.get("after"))
            if vor:
                ergebnis["spaet"] = vor
            tage = _wochentage(bedingung.get("weekday"))
            if tage:
                ergebnis["tage"] = tage
        elif art == "sun":
            ergebnis["unbekannt"].append("Sonnenstand-Bedingung")
        elif art in ("and", "or", "not"):
            ergebnis["unbekannt"].append(f"{art}-Verknüpfung")
    return ergebnis


def _aufrunden(roh) -> str:
    """``08:29:59`` ist als Klammer ``08:30`` gemeint."""
    text = str(roh or "").strip()
    treffer = _TIME_RE.match(text)
    if not treffer:
        return ""
    stunde, minute = int(treffer.group(1)), int(treffer.group(2))
    if treffer.group(4) and int(treffer.group(4)) >= 30:
        minute += 1
        if minute >= 60:
            minute, stunde = 0, (stunde + 1) % 24
    return f"{stunde:02d}:{minute:02d}"


ALLE_TAGE = list(TAGE_KURZ)


def vorschlag(bereiche: dict, schulfrei_entity: str, schulfrei_morgen_entity: str,
              vorhandene: list[dict] | None = None, namen: dict | None = None) -> dict:
    """Aus den vorhandenen Automationen einen Einrichtungsvorschlag bauen.

    Gesammelt wird **je Rollo**, gruppiert erst danach – und zwar nach Bereich
    *und* Schaltmuster. Der Grund steht im Wohnzimmer dieses Hauses: Drei
    Rollos, ein Bereich, aber die Terrassentür folgt einem eigenen Regime
    (einem Auswahlhelfer mit den Stellungen normal / 24 Uhr / aus), während
    die beiden Fensterrollos schlicht bei Sonnenuntergang zufahren. Wer nur
    nach Bereich gruppiert, wirft beides in einen Topf und legt der
    Terrassentür Schaltpunkte auf, die sie nie hatte.
    """
    schon_verplant = {eid for raum in (vorhandene or []) for eid in raum.get("rollos", [])}
    namen = namen or {}
    je_rollo: dict[str, dict] = {}
    ungedeutet: list[dict] = []

    def eintrag_fuer(eid: str) -> dict:
        return je_rollo.setdefault(eid, {
            "rollos": [eid], "zeitplan": [], "freigabe_entity": "",
            "quellen": [], "hinweise": []})

    for automation in automationen_lesen():
        if not isinstance(automation, dict):
            continue
        treffer: list = []
        _aktionen_durchgehen(automation.get("actions") or automation.get("action"), treffer)
        if not treffer:
            continue
        ausloeser = _ausloeser(automation)
        if not ausloeser:
            # Etwa „RM Alarm öffnet alle Rollos“: löst über einen Melder aus,
            # nicht über die Zeit. Solche Automationen bleiben, wo sie sind –
            # der Planer soll sie nicht ersetzen, sondern ihnen ausweichen.
            ungedeutet.append({"alias": automation.get("alias", "?"),
                               "grund": "kein Zeit- oder Sonnenauslöser"})
            continue
        bedingungen = _bedingungen(automation, schulfrei_entity, schulfrei_morgen_entity)

        for stellung, ziele, ids, klammer in treffer:
            if klammer.get("widerspruch"):
                for eid in ziele:
                    text = (f"{automation.get('alias', '?')}: ein Zweig verlangt zwei "
                            "Wochentags-Bedingungen gleichzeitig und läuft nie – "
                            "übersprungen")
                    hinweise = eintrag_fuer(eid)["hinweise"]
                    if text not in hinweise:
                        hinweise.append(text)
                continue
            passende = [t for t in ausloeser
                        if ids is None or (t.get("id") and t["id"] in ids)]
            if not passende:
                continue
            for eid in ziele:
                daten = eintrag_fuer(eid)
                if bedingungen["freigabe"] and not daten["freigabe_entity"]:
                    daten["freigabe_entity"] = bedingungen["freigabe"]
                if automation.get("alias") not in daten["quellen"]:
                    daten["quellen"].append(automation.get("alias", "?"))
                for teil in passende:
                    punkt = {
                        "ausloeser": teil["ausloeser"],
                        "start": teil.get("start", ""),
                        "versatz_min": teil.get("versatz_min", 0),
                        "frueh": (klammer.get("frueh") or bedingungen["frueh"]
                                  if teil["ausloeser"] != "uhrzeit" else ""),
                        "spaet": (klammer.get("spaet") or bedingungen["spaet"]
                                  if teil["ausloeser"] != "uhrzeit" else ""),
                        "position": stellung,
                        "gilt": bedingungen["gilt"],
                        "tage": (teil.get("tage") or klammer.get("tage")
                                 or bedingungen["tage"] or ALLE_TAGE),
                        "wenn": [dict(w) for w in bedingungen["wenn"]],
                        "name": "",
                    }
                    if punkt not in daten["zeitplan"]:
                        daten["zeitplan"].append(punkt)
                for hinweis in bedingungen["unbekannt"]:
                    text = f"{automation.get('alias', '?')}: {hinweis} nicht übernommen"
                    if text not in daten["hinweise"]:
                        daten["hinweise"].append(text)

    for daten in je_rollo.values():
        daten["zeitplan"] = _falten(daten["zeitplan"])
        _freigabe_hochziehen(daten)
        daten["zeitplan"].sort(key=lambda p: (p.get("start") or "", p["ausloeser"]))

    return {"raeume": _gruppieren(je_rollo, bereiche, namen, schon_verplant),
            "ungedeutet": ungedeutet}


def _freigabe_hochziehen(daten: dict) -> None:
    """Eine Bedingung, die an **jedem** Punkt hängt, wird zum Raumschalter.

    Beim Bürorollo steht `rollosteuerung_buero` in der einen Automation, die
    alles regelt – daraus wird der Freigabeschalter des Raumes, und die Punkte
    bleiben sauber. Wo sich Öffnen und Schließen verschiedene Schalter teilen,
    bleibt es bei den Bedingungen am Punkt: Dort *gibt* es keinen gemeinsamen
    Schalter, und einen zu erfinden hieße, das Verhalten zu ändern.
    """
    zeitplan = daten["zeitplan"]
    if not zeitplan:
        return
    gemeinsam = None
    for punkt in zeitplan:
        schalter = {(w["entity"], w["wert"]) for w in (punkt.get("wenn") or [])
                    if w["entity"].startswith("input_boolean.") and w["wert"] == "on"}
        gemeinsam = schalter if gemeinsam is None else (gemeinsam & schalter)
        if not gemeinsam:
            return
    entity, _ = sorted(gemeinsam)[0]
    daten["freigabe_entity"] = entity
    for punkt in zeitplan:
        punkt["wenn"] = [w for w in punkt["wenn"] if w["entity"] != entity]


def _plan_schluessel(zeitplan: list[dict]) -> tuple:
    """Die Kennung eines Schaltmusters – zwei gleiche Pläne, eine Kennung."""
    return tuple(sorted(
        (p["ausloeser"], p.get("start", ""), p.get("versatz_min", 0), p.get("frueh", ""),
         p.get("spaet", ""), p["position"], p["gilt"], tuple(sorted(p["tage"])),
         _wenn_schluessel(p))
        for p in zeitplan))


def _gruppieren(je_rollo: dict, bereiche: dict, namen: dict,
                schon_verplant: set) -> list[dict]:
    """Rollos zu Räumen zusammenfassen: gleicher Bereich, gleiches Schaltmuster."""
    gruppen: dict[tuple, dict] = {}
    for eid, daten in je_rollo.items():
        schluessel = (bereiche.get(eid) or "Ohne Bereich",
                      _plan_schluessel(daten["zeitplan"]),
                      daten["freigabe_entity"])
        gruppe = gruppen.get(schluessel)
        if gruppe is None:
            gruppen[schluessel] = {**daten, "rollos": list(daten["rollos"])}
            continue
        gruppe["rollos"].extend(daten["rollos"])
        for schluessel_liste in ("quellen", "hinweise"):
            for wert in daten[schluessel_liste]:
                if wert not in gruppe[schluessel_liste]:
                    gruppe[schluessel_liste].append(wert)

    # Benennen: Die größte Gruppe eines Bereichs bekommt dessen Namen, die
    # übrigen einen Zusatz. Ohne Zusatz gäbe es zwei Räume „Wohnzimmer“, und
    # die MQTT-Entitäten beider hießen gleich.
    je_bereich: dict[str, list[dict]] = {}
    for (bereich, _, _), gruppe in gruppen.items():
        je_bereich.setdefault(bereich, []).append(gruppe)

    raeume = []
    for bereich, liste in je_bereich.items():
        liste.sort(key=lambda g: (-len(g["rollos"]), g["rollos"][0]))
        for i, gruppe in enumerate(liste):
            if i == 0:
                gruppe["name"] = bereich
            else:
                erstes = gruppe["rollos"][0]
                kurz = (namen.get(erstes) or erstes.split(".", 1)[-1]).strip()
                # „Rollo Terrassentür“ im Bereich Wohnzimmer wird zu
                # „Wohnzimmer – Terrassentür“: der Bereich bleibt vorn, damit
                # die Räume in der Liste beieinanderstehen.
                kurz = kurz.removeprefix("Rollo ").strip() or erstes
                gruppe["name"] = f"{bereich} – {kurz}"
                gruppe["hinweise"] = list(gruppe["hinweise"]) + [
                    f"Eigener Raum, weil dieses Rollo im Bereich „{bereich}“ nach "
                    "einem anderen Muster fährt als die übrigen"]
            gruppe["schon_verplant"] = [e for e in gruppe["rollos"] if e in schon_verplant]
            raeume.append(gruppe)
    return raeume


def _wenn_schluessel(punkt: dict) -> tuple:
    return tuple(sorted((w.get("entity", ""), w.get("wert", ""))
                        for w in (punkt.get("wenn") or [])))


def _falten(zeitplan: list[dict]) -> list[dict]:
    """Zwei Auslöser derselben Automation zu einem Schaltpunkt zusammenziehen.

    „Auslöser: Sonnenuntergang **oder** 23:00 Uhr“ heißt in einer Automation:
    was zuerst kommt, gilt. Der Planer schreibt dasselbe als einen Punkt mit
    der Klammer „spätestens 23:00“. Ohne dieses Zusammenziehen stünden zwei
    Punkte im Plan, von denen der zweite nie etwas bewirkt – und wer den Plan
    später liest, fragt sich, welcher der richtige ist.

    Zusammengezogen wird nur, was zusammengehört: gleiche Stellung, gleiche
    Geltung, gleiche Wochentage. Und nur in die passende Tageshälfte – eine
    Uhrzeit am Morgen klammert einen Sonnenaufgang ein, keinen Untergang.
    """
    sonnen = [p for p in zeitplan if p["ausloeser"] != "uhrzeit"]
    uebrig = []
    for punkt in zeitplan:
        if punkt["ausloeser"] != "uhrzeit":
            uebrig.append(punkt)
            continue
        gefaltet = False
        for sonne in sonnen:
            if (sonne["position"] != punkt["position"]
                    or sonne["gilt"] != punkt["gilt"]
                    or sorted(sonne["tage"]) != sorted(punkt["tage"])
                    or _wenn_schluessel(sonne) != _wenn_schluessel(punkt)):
                continue
            vormittag = punkt["start"] < "12:00"
            if sonne["ausloeser"] == "sonnenaufgang" and vormittag and not sonne["frueh"]:
                sonne["frueh"] = punkt["start"]
                gefaltet = True
            elif (sonne["ausloeser"] in ("sonnenuntergang", "daemmerung")
                  and not vormittag and not sonne["spaet"]):
                sonne["spaet"] = punkt["start"]
                gefaltet = True
            if gefaltet:
                break
        if not gefaltet:
            uebrig.append(punkt)
    return uebrig


def raeume_ohne_automation(bereiche: dict, cover: list[dict],
                           vorschlag_raeume: list[dict]) -> list[dict]:
    """Rollos, für die sich gar keine Automation gefunden hat.

    In diesem Haus sind das die beiden Schlafzimmer-Rollos: Sie fahren heute
    nur bei Rauch und im Urlaub – nie nach der Uhr. Ohne diesen Abgleich
    fielen sie bei der Einrichtung schlicht unter den Tisch.
    """
    erfasst = {eid for raum in vorschlag_raeume for eid in raum.get("rollos", [])}
    fehlend: dict[str, dict] = {}
    for eintrag in cover:
        eid = eintrag["entity_id"]
        if eid in erfasst:
            continue
        bereich = bereiche.get(eid) or eintrag.get("bereich") or "Ohne Bereich"
        raum = fehlend.setdefault(bereich, {"name": bereich, "rollos": [],
                                            "zeitplan": [], "freigabe_entity": "",
                                            "quellen": [], "hinweise": [
                                                "Für diese Rollos gibt es heute keine "
                                                "Zeitautomation"]})
        raum["rollos"].append(eid)
    return list(fehlend.values())
