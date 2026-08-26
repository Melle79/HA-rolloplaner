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
import uuid

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
              cover: list[dict] | None = None) -> dict:
    """Aus den vorhandenen Automationen einen Einrichtungsvorschlag bauen.

    Gesammelt wird **je Rollo** – so, wie der Planer auch regelt. Erst danach
    werden Rollos mit **identischem Schaltmuster** zu einem benannten Zeitplan
    zusammengefasst. Das ist die Reihenfolge, auf die es ankommt: Wer zuerst
    gruppiert und dann die Zeiten sucht, muss für jedes Rollo mit eigenem
    Regime eine Ausnahme erfinden.

    Rollos, für die sich gar keine Automation findet, kommen ohne Zeitplan mit
    – sichtbar, damit sie nicht stillschweigend fehlen.
    """
    je_rollo: dict[str, dict] = {}
    ungedeutet: list[dict] = []

    def eintrag_fuer(eid: str) -> dict:
        return je_rollo.setdefault(eid, {"zeitplan": [], "quellen": [], "hinweise": []})

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
        daten["zeitplan"].sort(key=lambda p: (p.get("start") or "", p["ausloeser"]))

    rollos, plaene = _zu_plaenen(je_rollo, bereiche, cover or [])
    return {"rollos": rollos, "plaene": plaene, "ungedeutet": ungedeutet}


def art_raten(name: str, entity_id: str) -> str:
    """Fenster oder Tür? Der Name verrät es.

    Ein Rollladen vor einer Balkontür geht bis zum Boden und braucht eine
    Fenstersperre; eines vor einem Fenster nicht. Geraten wird nur die
    Vorgabe – ändern lässt es sich in der Oberfläche.

    **Der Anzeigename gewinnt gegen die entity_id.** In dieser Anlage heißt
    die Schlafzimmer-Balkontür `cover.rollo_terrassentur`: Das Gerät hing im
    alten Haus woanders, und die ID ist beim Umzug geblieben. Der Name wurde
    gepflegt, die ID nicht – wer der ID glaubt, macht aus jeder zweiten
    Balkontür eine Terrassentür.
    """
    def deuten(text: str) -> str | None:
        text = text.lower()
        if "terrasse" in text:
            return "terrassentuer"
        if "balkon" in text:
            return "balkontuer"
        if "haustür" in text or "haustuer" in text:
            return "haustuer"
        if "dach" in text:
            return "dachfenster"
        if "fenster" in text:
            return "fenster"
        return None

    return deuten(name) or deuten(entity_id) or "fenster"


def _plan_name(rollos: list[dict], bereiche: dict) -> str:
    """Ein Name für einen Zeitplan, dem mehrere Rollos folgen.

    Kommen sie alle aus demselben Bereich, heißt der Plan wie der Bereich.
    Sonst wird aus den Bereichen einer gemacht – „Küche + Wohnzimmer“ sagt
    mehr als „Zeitplan 2“.
    """
    orte = []
    for eid in rollos:
        ort = bereiche.get(eid) or ""
        if ort and ort not in orte:
            orte.append(ort)
    if len(orte) == 1:
        return orte[0]
    if 2 <= len(orte) <= 3:
        return " + ".join(orte)
    return "Zeitplan"


def _zu_plaenen(je_rollo: dict, bereiche: dict, cover: list[dict]) -> tuple[list, list]:
    """Rollos mit gleichem Schaltmuster teilen sich einen benannten Zeitplan.

    Ein Plan entsteht nur, wenn ihm **mehrere** Rollos folgen. Ein einzelnes
    behält seinen eigenen – ein benannter Plan mit einem Folger wäre nur ein
    Umweg.
    """
    namen = {e["entity_id"]: e.get("name") or e["entity_id"] for e in cover}
    nach_muster: dict[tuple, list[str]] = {}
    for eid, daten in je_rollo.items():
        nach_muster.setdefault(_plan_schluessel(daten["zeitplan"]), []).append(eid)

    plaene, zuordnung = [], {}
    vergeben: set[str] = set()
    for muster, eids in nach_muster.items():
        if len(eids) < 2 or not muster:
            continue
        name = _plan_name(eids, bereiche)
        while name in vergeben:
            name += " 2"
        vergeben.add(name)
        plan = {"id": uuid.uuid4().hex[:8], "name": name, "aktiv": True,
                "zeitplan": je_rollo[eids[0]]["zeitplan"]}
        plaene.append(plan)
        for eid in eids:
            zuordnung[eid] = plan["id"]

    rollos = []
    # Erst die mit Automation, dann die ohne – in der Reihenfolge der Bereiche.
    alle = list(je_rollo) + [e["entity_id"] for e in cover if e["entity_id"] not in je_rollo]
    for eid in alle:
        daten = je_rollo.get(eid) or {"zeitplan": [], "quellen": [],
                                      "hinweise": ["Für dieses Rollo gibt es heute "
                                                   "keine Zeitautomation"]}
        name = namen.get(eid, eid)
        rollos.append({
            "entity_id": eid,
            "name": "",
            "raum": bereiche.get(eid, ""),
            "art": art_raten(name, eid),
            "anzeige": name,
            "plan": zuordnung.get(eid, ""),
            "zeitplan": [] if eid in zuordnung else daten["zeitplan"],
            "quellen": daten["quellen"],
            "hinweise": daten["hinweise"],
        })
    rollos.sort(key=lambda r: (r["raum"], r["anzeige"]))
    return rollos, plaene


def _plan_schluessel(zeitplan: list[dict]) -> tuple:
    """Die Kennung eines Schaltmusters – zwei gleiche Pläne, eine Kennung.

    Daran erkennt die Übernahme, welche Rollos sich einen Zeitplan teilen
    können: Wohnzimmer links und rechts fahren identisch, die Terrassentür
    daneben nicht.
    """
    return tuple(sorted(
        (p["ausloeser"], p.get("start", ""), p.get("versatz_min", 0), p.get("frueh", ""),
         p.get("spaet", ""), p["position"], p["gilt"], tuple(sorted(p["tage"])),
         _wenn_schluessel(p))
        for p in zeitplan))


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
