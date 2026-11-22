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

# Seit 3.3 hat jeder Ablauf einen Morgen und einen Abend, jeweils für
# Schultag und schulfrei. Morgens zählt, ob *heute* Schule ist, abends, ob
# *morgen* Schule ist. ``None`` bei „schulfrei“ heißt: wie am Schultag.
STANDARD_MORGEN = {
    "licht": "vor_oeffnen",       # "aus" | "vor_oeffnen" | "uhrzeit" | "sonnenaufgang"
    "licht_zeit": "06:00",
    "licht_versatz": 30,          # vor_oeffnen: Minuten davor; Sonne: ± Minuten
    "licht_aus": "oeffnen",       # "oeffnen" | "uhrzeit" | "sonnenaufgang"
    "licht_aus_zeit": "07:30",
    "licht_aus_versatz": 0,
    "rollos": "mit_licht",        # "plan" | "mit_licht" | "uhrzeit" | "sonnenaufgang"
    "rollos_zeit": "06:00",
    "rollos_versatz": 0,
}
STANDARD_ABEND = {
    "licht": "sonnenuntergang",   # "aus" | "sonnenuntergang" | "daemmerung" | "uhrzeit"
    "licht_zeit": "17:00",
    "licht_versatz": 0,
    "licht_aus_zeit": "22:30",    # Licht aus – und die Rollos gehen zurück zum Plan
    "rollos": "mit_licht",        # "plan" | "mit_licht" | "uhrzeit" | "sonnenuntergang" | "daemmerung"
    "rollos_zeit": "17:00",
    "rollos_versatz": 0,
}
MORGEN_LICHT = ("aus", "vor_oeffnen", "uhrzeit", "sonnenaufgang")
MORGEN_LICHT_AUS = ("oeffnen", "uhrzeit", "sonnenaufgang")
MORGEN_ROLLOS = ("plan", "mit_licht", "uhrzeit", "sonnenaufgang")
ABEND_LICHT = ("aus", "sonnenuntergang", "daemmerung", "uhrzeit")
ABEND_ROLLOS = ("plan", "mit_licht", "uhrzeit", "sonnenuntergang", "daemmerung")

STANDARD_ABLAUF = {
    "id": "",
    "name": "",
    "morgens": {"schultag": dict(STANDARD_MORGEN), "schulfrei": None},
    "abends": {"schultag": dict(STANDARD_ABEND), "schulfrei": None},
    # Standard: nur hinauszögern. Mit Haken schließt der Ablauf bei Licht aus,
    # auch wenn der normale Plan das Rollo dann noch offen hätte.
    "frueher_schliessen": False,
    # Fernbedienung: je eine event.-Entität für „an“ und „aus“ (leer = keine)
    "fernbedienung": {"an": "", "aus": ""},
    "lichter": [],                 # light.* / switch.*
    "rollos": {},                  # entity_id → "plan" | "offen" | 0..99
}

# Die Felder, die bis 3.1 direkt an der Weihnachtszeit standen.
_ALTE_FELDER = ("licht_an", "licht_an_zeit", "licht_an_versatz", "licht_aus",
                "morgens_vorlauf", "lichter", "rollos")


def _aus_alter_form(a: dict) -> dict:
    """Ein Ablauf aus 3.0–3.2 (Licht an/aus, „vor freien Tagen“, Vorlauf) im
    Modell von 3.3 – so, dass er genau dasselbe tut."""
    if "morgens" in a and "abends" in a:
        return a
    abend = {**STANDARD_ABEND,
             "licht": a.get("licht_an") or "sonnenuntergang",
             "licht_zeit": a.get("licht_an_zeit") or "17:00",
             "licht_versatz": int(a.get("licht_an_versatz") or 0),
             "licht_aus_zeit": a.get("licht_aus") or "22:30",
             "rollos": "mit_licht"}
    frei = a.get("licht_aus_vor_schulfrei") or ""
    vorlauf = int(a.get("morgens_vorlauf", 30) or 0)
    morgen = ({**STANDARD_MORGEN, "licht": "vor_oeffnen", "licht_versatz": vorlauf,
               "licht_aus": "oeffnen", "rollos": "mit_licht"} if vorlauf
              else {**STANDARD_MORGEN, "licht": "aus", "rollos": "plan"})
    neu = {k: v for k, v in a.items()
           if k not in ("licht_an", "licht_an_zeit", "licht_an_versatz", "licht_aus",
                        "licht_aus_vor_schulfrei", "morgens_vorlauf")}
    neu["abends"] = {"schultag": abend,
                     "schulfrei": {**abend, "licht_aus_zeit": frei} if frei else None}
    neu["morgens"] = {"schultag": morgen, "schulfrei": None}
    return neu


def ablaeufe(cfg: dict) -> list[dict]:
    """Die Abläufe der Weihnachtszeit – auch aus Einstellungen früherer Fassungen.

    3.0/3.1: Lichter, Zeiten und Rollos standen direkt an der Weihnachtszeit
    (→ Ablauf „Erdgeschoss“). 3.2: ein Ablauf mit Licht an/aus und Vorlauf
    (→ Morgen und Abend). Gerechnet wird mit beiden Formen gleich, bis die
    Einstellung einmal neu gespeichert ist.
    """
    liste = cfg.get("ablaeufe")
    if not liste and (cfg.get("lichter") or cfg.get("rollos")):
        liste = [{**{k: cfg[k] for k in _ALTE_FELDER if k in cfg},
                  "id": "eg", "name": "Erdgeschoss"}]
    out = []
    for a in liste or []:
        a = _aus_alter_form(a)
        out.append({**STANDARD_ABLAUF, **a})
    return out


def variante(ablauf: dict, teil: str, frei: bool | None) -> dict:
    """Morgen oder Abend für Schultag bzw. schulfrei (leer = wie Schultag)."""
    block = ablauf.get(teil) or {}
    vorgabe = STANDARD_MORGEN if teil == "morgens" else STANDARD_ABEND
    schultag = {**vorgabe, **(block.get("schultag") or {})}
    if frei and block.get("schulfrei"):
        return {**schultag, **block["schulfrei"]}
    return schultag


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


def zeit_von(art: str, zeit: str, versatz, tag: date, sonnenstand) -> datetime | None:
    """Eine Uhrzeit oder ein Sonnenereignis (± Minuten) an diesem Tag."""
    if art == "uhrzeit":
        return datetime.combine(tag, _uhrzeit(zeit or "00:00"))
    roh = sonnenstand.zeitpunkt(art, tag) if sonnenstand else None
    if roh is None:
        return None
    return roh + timedelta(minutes=int(versatz or 0))


def abend(cfg: dict, tag: date, sonnenstand,
          morgen_frei: bool | None = None) -> tuple[datetime, datetime] | None:
    """Wann das Licht an diesem Abend angeht und wieder ausgeht – oder None.

    ``cfg`` ist ein Ablauf; ob morgen schulfrei ist, wählt die Variante.
    """
    v = variante(cfg, "abends", morgen_frei)
    if v.get("licht") == "aus":
        return None
    an = zeit_von(v["licht"], v.get("licht_zeit"), v.get("licht_versatz"), tag, sonnenstand)
    return _bis_aus(an, v, tag)


def _bis_aus(an, v: dict, tag: date):
    if an is None:
        return None
    aus = datetime.combine(tag, _uhrzeit(v.get("licht_aus_zeit") or "22:30"))
    # „aus um 00:30“ meint die Nacht danach.
    if aus <= an and aus.time() < time(12, 0):
        aus += timedelta(days=1)
    if aus <= an:
        return None
    return an, aus


def abend_rollos(cfg: dict, tag: date, sonnenstand,
                 morgen_frei: bool | None = None) -> tuple[datetime, datetime] | None:
    """Wann die Rollos abends auf ihre Weihnachtsstellung gehen und wann
    zurück zum Plan – unabhängig vom Licht, wenn so eingestellt."""
    v = variante(cfg, "abends", morgen_frei)
    art = v.get("rollos") or "mit_licht"
    if art == "plan":
        return None
    if art == "mit_licht":
        fenster = abend(cfg, tag, sonnenstand, morgen_frei)
        return fenster
    start = zeit_von(art, v.get("rollos_zeit"), v.get("rollos_versatz"), tag, sonnenstand)
    return _bis_aus(start, v, tag)


def morgen(cfg: dict, tag: date, sonnenstand, oeffnen: datetime | None,
           heute_frei: bool | None = None) -> tuple[datetime, datetime] | None:
    """Wann das Licht am Morgen brennt – oder None.

    ``oeffnen`` ist das erste normale Öffnen der Rollos dieses Ablaufs; daran
    hängen „x Minuten vor dem Öffnen“ und „aus beim Öffnen“.
    """
    v = variante(cfg, "morgens", heute_frei)
    if v.get("licht") == "aus":
        return None
    if v["licht"] == "vor_oeffnen":
        an = oeffnen - timedelta(minutes=int(v.get("licht_versatz") or 0)) if oeffnen else None
    else:
        an = zeit_von(v["licht"], v.get("licht_zeit"), v.get("licht_versatz"), tag, sonnenstand)
    if v.get("licht_aus") == "oeffnen":
        aus = oeffnen
    else:
        aus = zeit_von(v.get("licht_aus"), v.get("licht_aus_zeit"), v.get("licht_aus_versatz"),
                       tag, sonnenstand)
    if an is None or aus is None or aus <= an:
        return None
    return an, aus


def morgen_rollo(cfg: dict, tag: date, sonnenstand, eigenes_oeffnen: datetime | None,
                 heute_frei: bool | None = None) -> datetime | None:
    """Wann dieses Rollo morgens auf seine Weihnachtsstellung geht – oder None."""
    v = variante(cfg, "morgens", heute_frei)
    art = v.get("rollos") or "mit_licht"
    if art == "plan":
        return None
    if art == "mit_licht":
        if v.get("licht") == "aus":
            return None
        if v["licht"] == "vor_oeffnen":
            # wie bis 3.2: je Rollo vor *seinem* Öffnen
            return (eigenes_oeffnen - timedelta(minutes=int(v.get("licht_versatz") or 0))
                    if eigenes_oeffnen else None)
        return zeit_von(v["licht"], v.get("licht_zeit"), v.get("licht_versatz"), tag, sonnenstand)
    return zeit_von(art, v.get("rollos_zeit"), v.get("rollos_versatz"), tag, sonnenstand)


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
            morgen_frei: bool | None = None,
            heute_frei: bool | None = None,
            fb: dict | None = None) -> list[tuple[datetime, dict]]:
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
    fenster = abend_rollos(cfg, tag, sonnenstand, morgen_frei)
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
    frueh = morgen_rollo(cfg, tag, sonnenstand, erstes_oeffnen(punkte), heute_frei)
    if frueh is not None and (wert != OFFEN or (variante(cfg, "morgens", heute_frei).get("rollos")
                                                 not in ("plan", "mit_licht"))):
        normal = _stand(punkte, frueh, zu)
        if normal is None or normal < ziel:
            out.append((frueh, _punkt(ziel, texte.get(
                "morgen", "Weihnachtszeit: {n} %").format(n=ziel))))
    out += fernbedienung_punkt(fb, tag, punkte, zu, ziel, texte)
    out.sort(key=lambda p: p[0])
    return out


def fernbedienung_punkt(fb: dict | None, tag: date, punkte, zu, ziel: int,
                        texte: dict) -> list[tuple[datetime, dict]]:
    """Der Tastendruck an der Fernbedienung als Schaltpunkt.

    „an“: auf die Weihnachtsstellung – aber nur, wenn der Plan das Rollo
    gerade weiter zu hätte; ein offenes Rollo zieht die Fernbedienung nie zu.
    „aus“: dorthin, wo der normale Plan das Rollo jetzt hätte.
    Der Punkt gilt wie jeder andere bis zum nächsten fälligen.
    """
    if not fb or not fb.get("seit"):
        return []
    try:
        seit = datetime.fromisoformat(fb["seit"])
    except ValueError:
        return []
    if seit.date() != tag:
        return []
    normal = _stand(punkte, seit, zu)
    if fb.get("modus") == "an":
        if normal is not None and normal >= ziel:
            return []
        name = texte.get("fb_an", "Fernbedienung: Weihnachtsstellung")
        position = ziel
    else:
        name = texte.get("fb_aus", "Fernbedienung: zurück zum Plan")
        position = normal if normal is not None else zu
    return [(seit, {**_punkt(position, name), "quelle": "fernbedienung"})]


# Was an einer Taste „kurz“ und was „lang“ ist – je nach Hersteller heißen die
# Ereignisse anders (Matter, Hue, Zigbee2MQTT). „long_release“ und
# „initial_press“ fehlen mit Absicht: sie folgen bzw. gehen einem Druck voraus,
# den es schon gibt, und sonst zählte ein Druck doppelt.
FB_KURZ = {"multi_press_1", "short_release", "single", "press", "on", "off", "toggle",
           "click", "single_press"}
FB_LANG = {"long_press", "long", "hold", "brightness_move_down", "brightness_move_up",
           "on_long", "off_long"}


def fb_druck(event_type: str | None) -> str | None:
    """„kurz“, „lang“ oder None für ein Ereignis einer Taste."""
    if event_type in FB_KURZ:
        return "kurz"
    if event_type in FB_LANG:
        return "lang"
    return None


def lichtfenster(cfg: dict, tag: date, sonnenstand,
                 morgens_oeffnen: datetime | None,
                 morgen_frei: bool | None = None,
                 heute_frei: bool | None = None) -> list[tuple[datetime, datetime]]:
    """Die Zeiten, in denen an diesem Tag die Lichter brennen."""
    fenster = []
    frueh = morgen(cfg, tag, sonnenstand, morgens_oeffnen, heute_frei)
    if frueh:
        fenster.append(frueh)
    abends = abend(cfg, tag, sonnenstand, morgen_frei)
    if abends:
        fenster.append(abends)
    return fenster


def licht_soll(fenster: list[tuple[datetime, datetime]], jetzt: datetime) -> bool:
    return any(von <= jetzt < bis for von, bis in fenster)
