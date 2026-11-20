"""Programme: Zeiträume, in denen die Rollos etwas anderes tun als sonst.

Das erste Programm ist die **Weihnachtszeit**. Vom ersten Advent bis Heilige
Drei Könige brennen abends Lichter – im Garten, an der Terrasse, im Fenster.
Die Rollos davor sollen dann nicht wie sonst bei Sonnenuntergang zufahren,
sondern offen bleiben oder auf eine Zwischenstellung gehen, damit man das
Licht sieht. Wenn das Licht ausgeht, gehen sie zu. Morgens dasselbe in kurz:
Licht an, Rollos halb, und zur gewohnten Zeit auf.

**Warum ein Programm und keine Bedingungen am Zeitplan.** Bis 2.x ließ sich so
etwas nur mit eigenen Schaltern und „nur wenn“-Bedingungen an jedem einzelnen
Schaltpunkt zusammenstecken – drei Punkte mehr je Plan, und jeder bestehende
Schließpunkt brauchte die Gegenbedingung, sonst gewann still der, der weiter
hinten in der Liste stand. Hier legt das Programm seine Punkte **über** den
Tag und blendet aus, was in seinem Fenster läge. Der Zeitplan bleibt, wie er
ist; nach dem 6. Januar gilt er wieder unverändert.

**Rang in der Regelkette.** Das Programm verändert die Schaltpunkte, es ist
also Teil der Zeitplan-Stufe: Rauch, „aus“, gesperrte Pläne und Gruppen, ein
offenes Fenster und der Urlaub („alles zu“) stehen darüber. Der Hitzeschutz
verschiebt das Ergebnis wie jeden Zeitplan – im Winter greift er ohnehin
nicht. Handbetrieb endet wie immer mit dem nächsten fälligen Punkt; die Punkte
des Programms zählen dabei genauso.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

# Die Stellung eines Rollos während des Lichts: „plan“ = das Programm fasst es
# nicht an, „offen“ = es bleibt offen bis Licht aus, eine Zahl = so weit offen
# (Zählweise von Home Assistant, 100 = offen).
PLAN = "plan"
OFFEN = "offen"

STANDARD_WEIHNACHTSZEIT = {
    # Eingerichtet heißt: Das Programm schaltet sich im Zeitraum selbst ein.
    # Aus = es läuft nur, wenn es jemand von Hand einschaltet.
    "aktiv": False,
    "zeitraum": "advent",          # "advent" | "fest"
    "von": "12-01",                # MM-TT, nur bei "fest"
    "bis": "01-06",                # MM-TT, einschließlich
    # Seit 3.2 mehrere Abläufe – das Erdgeschoss leuchtet bis 22:30, die
    # Kinderzimmer gehen früher zu. Zeitraum und Handschalter teilen sie sich.
    "ablaeufe": [],
}

STANDARD_ABLAUF = {
    "id": "",
    "name": "",
    "licht_an": "sonnenuntergang", # "sonnenuntergang" | "daemmerung" | "uhrzeit"
    "licht_an_zeit": "17:00",      # nur bei "uhrzeit"
    "licht_an_versatz": 0,         # Minuten, bei Sonne
    "licht_aus": "22:30",          # Licht aus, Rollos zu
    "licht_aus_vor_schulfrei": "", # leer = wie licht_aus
    "morgens_vorlauf": 30,         # Minuten vor dem Öffnen; 0 = morgens nichts
    # Standard: nur hinauszögern. Mit Haken schließt der Ablauf bei Licht aus,
    # auch wenn der normale Plan das Rollo dann noch offen hätte.
    "frueher_schliessen": False,
    "lichter": [],                 # light.* / switch.*
    "rollos": {},                  # entity_id → "plan" | "offen" | 0..99
}

# Die Felder, die bis 3.1 direkt an der Weihnachtszeit standen.
_ALTE_FELDER = ("licht_an", "licht_an_zeit", "licht_an_versatz", "licht_aus",
                "morgens_vorlauf", "lichter", "rollos")


def ablaeufe(cfg: dict) -> list[dict]:
    """Die Abläufe der Weihnachtszeit – auch aus einer Einstellung von 3.0/3.1.

    Dort standen Lichter, Zeiten und Rollos direkt an der Weihnachtszeit. Das
    wird hier als ein Ablauf „Erdgeschoss“ gelesen, damit sich nichts ändert,
    bis die Einstellung einmal neu gespeichert ist.
    """
    liste = cfg.get("ablaeufe")
    if liste:
        return [{**STANDARD_ABLAUF, **a} for a in liste]
    if cfg.get("lichter") or cfg.get("rollos"):
        alt = {k: cfg[k] for k in _ALTE_FELDER if k in cfg}
        return [{**STANDARD_ABLAUF, **alt, "id": "eg", "name": "Erdgeschoss"}]
    return []


def ablauf_von(cfg: dict, entity_id: str) -> dict | None:
    """Zu welchem Ablauf gehört dieses Rollo? Höchstens einer."""
    for ablauf in ablaeufe(cfg):
        if stellung(ablauf, entity_id) != PLAN:
            return ablauf
    return None


PROGRAMM_KENNUNG = "weihnachtszeit"


def _uhrzeit(text: str) -> time:
    stunde, minute = str(text).split(":")
    return time(int(stunde), int(minute))


def erster_advent(jahr: int) -> date:
    """Der vierte Sonntag vor dem ersten Weihnachtstag."""
    heiligabend = date(jahr, 12, 24)
    # Sonntag vor oder am 24.12. ist der vierte Advent.
    vierter = heiligabend - timedelta(days=(heiligabend.weekday() + 1) % 7)
    return vierter - timedelta(weeks=3)


def _mmtt(text: str, jahr: int) -> date:
    monat, tag = str(text).split("-")
    return date(jahr, int(monat), int(tag))


def im_zeitraum(cfg: dict, tag: date) -> bool:
    """Liegt der Tag im Zeitraum des Programms – unabhängig von „aktiv“?"""
    bis_text = cfg.get("bis") or "01-06"
    for jahr in (tag.year - 1, tag.year):
        if cfg.get("zeitraum") == "fest":
            von = _mmtt(cfg.get("von") or "12-01", jahr)
        else:
            von = erster_advent(jahr)
        bis = _mmtt(bis_text, jahr)
        if bis < von:
            bis = _mmtt(bis_text, jahr + 1)
        if von <= tag <= bis:
            return True
    return False


def naechste_grenze(cfg: dict, tag: date) -> date:
    """Der nächste Tag, an dem der Zeitraum beginnt oder endet."""
    heute = im_zeitraum(cfg, tag)
    for n in range(1, 400):
        kandidat = tag + timedelta(days=n)
        if im_zeitraum(cfg, kandidat) != heute:
            return kandidat
    return tag + timedelta(days=366)


def aktiv_am(cfg: dict, tag: date, hand: dict | None) -> bool:
    """Läuft das Programm an diesem Tag?

    Von Hand ein- oder ausgeschaltet gilt bis zur nächsten Grenze des
    Zeitraums – wer die Weihnachtszeit am 3. Januar abschaltet, meint dieses
    Jahr, nicht alle künftigen.
    """
    if hand and hand.get("bis"):
        try:
            bis = date.fromisoformat(hand["bis"])
        except ValueError:
            bis = None
        if bis and tag < bis:
            return hand.get("wert") == "on"
    return bool(cfg.get("aktiv")) and im_zeitraum(cfg, tag)


def stellung(cfg: dict, entity_id: str):
    """Was dieses Rollo während des Lichts tut: PLAN, OFFEN oder eine Zahl."""
    wert = (cfg.get("rollos") or {}).get(entity_id, PLAN)
    if wert in (PLAN, OFFEN):
        return wert
    try:
        return max(0, min(100, int(wert)))
    except (TypeError, ValueError):
        return PLAN


def abend(cfg: dict, tag: date, sonnenstand,
          morgen_frei: bool | None = None) -> tuple[datetime, datetime] | None:
    """Wann das Licht an diesem Abend angeht und wieder ausgeht.

    ``cfg`` ist ein Ablauf. Ist morgen schulfrei und hat der Ablauf dafür eine
    eigene Zeit, gilt die – die Kinderzimmer dürfen am Freitag länger.
    """
    art = cfg.get("licht_an") or "sonnenuntergang"
    if art == "uhrzeit":
        an = datetime.combine(tag, _uhrzeit(cfg.get("licht_an_zeit") or "17:00"))
    else:
        roh = sonnenstand.zeitpunkt(art, tag) if sonnenstand else None
        if roh is None:
            return None
        an = roh + timedelta(minutes=int(cfg.get("licht_an_versatz") or 0))
    aus_text = cfg.get("licht_aus") or "22:30"
    if morgen_frei and cfg.get("licht_aus_vor_schulfrei"):
        aus_text = cfg["licht_aus_vor_schulfrei"]
    aus = datetime.combine(tag, _uhrzeit(aus_text))
    # „aus um 00:30“ meint die Nacht danach.
    if aus <= an and aus.time() < time(12, 0):
        aus += timedelta(days=1)
    if aus <= an:
        return None
    return an, aus


def _ist_oeffnen(eintrag: dict) -> bool:
    return int(eintrag.get("position", 100)) >= 100


def erstes_oeffnen(punkte_am_tag: list[tuple[datetime, dict]]) -> datetime | None:
    for zeitpunkt, eintrag in punkte_am_tag:
        if _ist_oeffnen(eintrag) and zeitpunkt.time() < time(12, 0):
            return zeitpunkt
    return None


def _punkt(position: int, name: str) -> dict:
    return {"ausloeser": "programm", "position": int(position), "name": name,
            "programm": PROGRAMM_KENNUNG, "gilt": "immer", "wenn": []}


def _stand(punkte: list[tuple[datetime, dict]], zeit: datetime, start) -> int | None:
    """Wo der normale Plan das Rollo zu dieser Zeit hätte (Punkt zur selben
    Minute eingeschlossen)."""
    stand = start
    for zeitpunkt, eintrag in punkte:
        if zeitpunkt > zeit:
            break
        stand = int(eintrag.get("position", 100))
    return stand


def umbauen(cfg: dict, wert, tag: date, punkte: list[tuple[datetime, dict]],
            sonnenstand, position_zu: int = 0, texte=None,
            start: int | None = None,
            morgen_frei: bool | None = None) -> list[tuple[datetime, dict]]:
    """Die Schaltpunkte eines Tages unter dem Programm.

    ``punkte`` sind die nach Zeit sortierten Punkte des Rollos an diesem Tag –
    schon nach Bedingungen und Auswahlschaltern gefiltert; ``start`` ist die
    Stellung um Mitternacht.

    **Die Weihnachtszeit darf das Schließen nur hinauszögern, nie vorziehen
    oder erzwingen.** Deshalb:

    * Im Lichtfenster wird ein Punkt, der weiter zufahren würde als die
      Zwischenstellung, auf sie angehoben („bleibt offen“: er fällt weg).
      Ein Rollo, das der Plan offen ließe, bleibt offen.
    * Bei Licht aus geht das Rollo dorthin, wo der Plan es *jetzt* hätte –
      und nur, wenn das Programm im Fenster überhaupt etwas verändert hat.
      Steht die Terrassentür auf „24 Uhr“, schließt sie also weiter um
      Mitternacht und nicht schon um 22:30; steht sie auf „aus“, bleibt sie
      offen.
    * Morgens kommt die Zwischenstellung nur, wenn das Rollo dann weiter zu
      wäre als sie.
    """
    if wert == PLAN:
        return punkte
    texte = texte or {}
    ziel = 100 if wert == OFFEN else int(wert)
    zu = position_zu if start is None else start
    out = []
    fenster = abend(cfg, tag, sonnenstand, morgen_frei)
    veraendert = False
    if fenster:
        an, aus = fenster
        for zeitpunkt, eintrag in punkte:
            pos = int(eintrag.get("position", 100))
            if an <= zeitpunkt < aus and pos < ziel:
                veraendert = True
                if wert != OFFEN:
                    out.append((zeitpunkt, _punkt(ziel, texte.get(
                        "abend", "Weihnachtszeit: {n} %").format(n=ziel))))
                continue
            out.append((zeitpunkt, eintrag))
        if cfg.get("frueher_schliessen"):
            # Ausdrücklich gewollt: bei Licht aus zu, gleich was der Plan sagt.
            out.append((aus, _punkt(position_zu, texte.get("aus", "Weihnachtszeit: Licht aus"))))
        elif veraendert:
            normal = _stand(punkte, aus, zu)
            out.append((aus, _punkt(normal if normal is not None else position_zu,
                                    texte.get("aus", "Weihnachtszeit: Licht aus"))))
    else:
        out = list(punkte)
    vorlauf = int(cfg.get("morgens_vorlauf") or 0)
    if vorlauf and wert != OFFEN:
        oeffnen = erstes_oeffnen(punkte)
        if oeffnen is not None:
            frueh = oeffnen - timedelta(minutes=vorlauf)
            normal = _stand(punkte, frueh, zu)
            if normal is None or normal < ziel:
                out.append((frueh, _punkt(ziel, texte.get(
                    "morgen", "Weihnachtszeit: {n} %").format(n=ziel))))
    out.sort(key=lambda p: p[0])
    return out


def lichtfenster(cfg: dict, tag: date, sonnenstand,
                 morgens_oeffnen: datetime | None,
                 morgen_frei: bool | None = None) -> list[tuple[datetime, datetime]]:
    """Die Zeiten, in denen an diesem Tag die Lichter brennen."""
    fenster = []
    vorlauf = int(cfg.get("morgens_vorlauf") or 0)
    if vorlauf and morgens_oeffnen is not None:
        fenster.append((morgens_oeffnen - timedelta(minutes=vorlauf), morgens_oeffnen))
    abends = abend(cfg, tag, sonnenstand, morgen_frei)
    if abends:
        fenster.append(abends)
    return fenster


def licht_soll(fenster: list[tuple[datetime, datetime]], jetzt: datetime) -> bool:
    return any(von <= jetzt < bis for von, bis in fenster)
