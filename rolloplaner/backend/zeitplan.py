"""Der Wochenplan eines Raumes: welcher Schaltpunkt gilt jetzt, was kommt als Nächstes.

Ein Zeitplan ist eine Liste von Schaltpunkten – wie am mechanischen
Zeitschaltwerk. Jeder Punkt sagt: ab hier, an diesen Wochentagen, steht das
Rollo auf dieser Stellung. Es gibt keine Endzeiten; der nächste Punkt löst den
vorherigen ab. Dadurch kann keine Lücke entstehen, in der niemand zuständig
ist – der Fallstrick der Slot-Pläne mit ``stop``-Zeit.

Der Unterschied zur Heizung: Ein Schaltpunkt muss nicht an einer Uhrzeit
hängen. „Bei Sonnenuntergang, aber nie vor 20:30“ ist genau das, was die
heutigen Automationen von Hand nachbauen – mit je zwei Auslösern und einer
Zeitbedingung. Hier ist es ein Eintrag.
"""
from __future__ import annotations

import sprache

from datetime import date, datetime, time, timedelta

TAGE = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# So weit schaut der Planer zurück, wenn er den zuletzt fälligen Punkt sucht.
# Eine Woche deckt auch einen Plan ab, der nur sonntags schaltet.
RUECKSCHAU_TAGE = 8


def _uhrzeit(text: str) -> time:
    stunde, minute = text.split(":")
    return time(int(stunde), int(minute))


class Schulkalender:
    """Weiß, ob ein Tag schulfrei war, ist oder sein wird.

    Home Assistant kennt nur zwei Tage: heute und morgen. Für die Rückschau
    fehlt gestern – und gerade daran hängen die Kinderzimmer, deren Rollos
    abends je nach *morgigem* Tag um 20:30 oder erst um 22:00 zufahren.

    Deshalb schreibt der Planer jeden gesehenen Tag mit. Solange er das noch
    nicht getan hat, gilt die Notlösung: Samstag und Sonntag sind schulfrei.
    Die ist an Feiertagen falsch – aber nur am allerersten Tag nach der
    Einrichtung, und sie ist besser als gar keine Auskunft.
    """

    def __init__(self, heute: bool | None, morgen: bool | None, verlauf: dict):
        self.heute = heute
        self.morgen = morgen
        self.verlauf = verlauf or {}

    def fuer(self, tag: date, heute: date) -> bool | None:
        if tag == heute:
            return self.heute
        if tag == heute + timedelta(days=1) and self.morgen is not None:
            return self.morgen
        gemerkt = self.verlauf.get(tag.isoformat())
        if gemerkt is not None:
            return bool(gemerkt)
        return tag.weekday() >= 5

    def merken(self, tag: date) -> None:
        if self.heute is not None:
            self.verlauf[tag.isoformat()] = bool(self.heute)
        if self.morgen is not None:
            self.verlauf[(tag + timedelta(days=1)).isoformat()] = bool(self.morgen)
        # Nur die letzten zwei Wochen aufheben; mehr schaut niemand zurück.
        grenze = (tag - timedelta(days=14)).isoformat()
        for schluessel in [k for k in self.verlauf if k < grenze]:
            del self.verlauf[schluessel]


def bedingungen_erfuellt(eintrag: dict, zustaende: dict | None) -> bool:
    """Treffen die Bedingungen eines Schaltpunkts gerade zu?

    Geprüft wird der **jetzige** Zustand, auch wenn der Punkt von gestern
    stammt. Das ist die richtige Auslegung: Steht der Auswahlhelfer heute auf
    „24 Uhr“, dann gilt der 24-Uhr-Punkt – und nicht der, der gestern Abend
    gegolten hätte. Ein Helfer, den man umstellt, soll sofort wirken.
    """
    wenn = eintrag.get("wenn") or []
    if not wenn:
        return True
    if zustaende is None:
        # Ohne Zustände kann nicht geprüft werden. Dann gilt der Punkt **nicht**
        # – sonst führe die Terrassentür auch bei „aus“ zu.
        return False
    for bedingung in wenn:
        zustand = zustaende.get(bedingung.get("entity"))
        if zustand is None:
            return False
        if str(zustand) != str(bedingung.get("wert")):
            return False
    return True


def passt(eintrag: dict, tag: date, kalender: Schulkalender, heute: date,
          zustaende: dict | None = None) -> bool:
    """Gilt dieser Schaltpunkt an diesem Tag?"""
    if TAGE[tag.weekday()] not in eintrag.get("tage", []):
        return False
    if not bedingungen_erfuellt(eintrag, zustaende):
        return False
    gilt = eintrag.get("gilt", "immer")
    if gilt == "immer":
        return True
    if gilt.startswith("morgen_"):
        frei = kalender.fuer(tag + timedelta(days=1), heute)
        erwartet = gilt == "morgen_schulfrei"
    else:
        frei = kalender.fuer(tag, heute)
        erwartet = gilt == "schulfrei"
    if frei is None:
        # Ohne Kenntnis gelten nur die immer-Einträge, sonst griffen Schultag-
        # und Schulfrei-Plan gleichzeitig.
        return False
    return frei == erwartet


def zeitpunkt_von(eintrag: dict, tag: date, sonnenstand,
                  anpassen=None) -> datetime | None:
    """Wann wird dieser Schaltpunkt an diesem Tag fällig?

    Bei einem Sonnenauslöser wird der berechnete Zeitpunkt um den Versatz
    verschoben und dann in die Klammer ``frühestens``/``spätestens`` gezwungen.
    Die Klammer ist kein Zierrat: Im Juni geht die Sonne um halb sechs auf –
    ohne „frühestens 08:30“ stünde das Bürorollo im Sommer drei Stunden zu
    früh offen.
    """
    zeitpunkt = _roher_zeitpunkt(eintrag, tag, sonnenstand)
    if zeitpunkt is None or anpassen is None:
        return zeitpunkt
    # Die Anpassung sitzt bewusst **hier** und nicht beim Aufrufer: Der
    # Tagesversatz der Urlaubssimulation muss schon feststehen, wenn gesucht
    # wird, welcher Punkt zuletzt fällig war. Wer ihn erst danach aufschlägt,
    # bekommt nur Verspätungen zu sehen – ein um zwanzig Minuten *vorgezogener*
    # Punkt wird nie gefunden, weil zu seiner Zeit noch der Punkt von heute
    # früh als der letzte gilt.
    return anpassen(zeitpunkt, eintrag, tag)


def _roher_zeitpunkt(eintrag: dict, tag: date, sonnenstand) -> datetime | None:
    art = eintrag.get("ausloeser") or "uhrzeit"
    if art == "uhrzeit":
        start = eintrag.get("start")
        if not start:
            return None
        return datetime.combine(tag, _uhrzeit(start))

    roh = sonnenstand.zeitpunkt(art, tag) if sonnenstand else None
    if roh is None:
        # Kein Sonnenereignis an diesem Tag (Polartag) – dann greift die
        # Klammer allein, und ohne Klammer eben gar nichts.
        spaet = eintrag.get("spaet")
        return datetime.combine(tag, _uhrzeit(spaet)) if spaet else None

    zeitpunkt = roh + timedelta(minutes=int(eintrag.get("versatz_min") or 0))
    # Der Versatz kann über Mitternacht schieben; der Punkt gehört trotzdem zu
    # diesem Tag, damit die Rückschau ihn nicht doppelt zählt.
    frueh, spaet = eintrag.get("frueh"), eintrag.get("spaet")
    if frueh:
        untergrenze = datetime.combine(tag, _uhrzeit(frueh))
        zeitpunkt = max(zeitpunkt, untergrenze)
    if spaet:
        obergrenze = datetime.combine(tag, _uhrzeit(spaet))
        zeitpunkt = min(zeitpunkt, obergrenze)
    return zeitpunkt


def _punkte_am_tag(zeitplan: list[dict], tag: date, kalender: Schulkalender,
                   heute: date, sonnenstand, anpassen=None,
                   zustaende: dict | None = None) -> list[tuple[datetime, dict]]:
    out = []
    for eintrag in zeitplan:
        if not passt(eintrag, tag, kalender, heute, zustaende):
            continue
        zeitpunkt = zeitpunkt_von(eintrag, tag, sonnenstand, anpassen)
        if zeitpunkt is not None:
            out.append((zeitpunkt, eintrag))
    out.sort(key=lambda p: p[0])
    return out


def letzter_zeitpunkt(zeitplan: list[dict], jetzt: datetime, kalender: Schulkalender,
                      sonnenstand, anpassen=None,
                      zustaende: dict | None = None) -> tuple[datetime, dict] | None:
    """Der zuletzt fällig gewordene Schaltpunkt samt Zeitpunkt.

    Sucht rückwärts über Tagesgrenzen hinweg: Der Sonnenuntergang von gestern
    Abend gilt bis zum ersten Punkt von heute früh. Der Zeitpunkt selbst wird
    gebraucht, um „ist gerade fällig geworden“ von „gilt schon seit gestern“ zu
    unterscheiden – und das ist der Unterschied zwischen einem Rollo, das
    einmal fährt, und einem, das bei jedem Takt anläuft.
    """
    heute = jetzt.date()
    for versatz in range(RUECKSCHAU_TAGE):
        tag = heute - timedelta(days=versatz)
        kandidaten = [p for p in _punkte_am_tag(zeitplan, tag, kalender, heute,
                                                sonnenstand, anpassen, zustaende)
                      if p[0] <= jetzt]
        if kandidaten:
            return kandidaten[-1]
    return None


def naechster_wechsel(zeitplan: list[dict], jetzt: datetime, kalender: Schulkalender,
                      sonnenstand, anpassen=None,
                      zustaende: dict | None = None) -> tuple[datetime, dict] | None:
    """Der nächste anstehende Schaltpunkt samt Zeitpunkt."""
    heute = jetzt.date()
    for versatz in range(RUECKSCHAU_TAGE):
        tag = heute + timedelta(days=versatz)
        kandidaten = [p for p in _punkte_am_tag(zeitplan, tag, kalender, heute,
                                                sonnenstand, anpassen, zustaende)
                      if p[0] > jetzt]
        if kandidaten:
            return kandidaten[0]
    return None


def beschreibung(eintrag: dict, mit_bedingungen: bool = False,
                 invertiert: bool = False) -> str:
    """Ein Schaltpunkt in einem Satz – für Protokoll und Karte.

    Die Bedingungen bleiben draußen, sofern nicht ausdrücklich verlangt: Auf
    einer Dashboard-Kachel liest sich „zu um Sonnenuntergang, spätestens 23:00
    (helfer_rollo_eg_schliessen = on)“ wie eine Fehlermeldung. Wer wissen will,
    woran ein Punkt hängt, sieht im Raum-Dialog nach, wo es hingehört.
    """
    if eintrag.get("name"):
        return eintrag["name"]
    art = eintrag.get("ausloeser") or "uhrzeit"
    if art == "uhrzeit":
        wann = sprache.t("punkt.uhrzeit", zeit=eintrag.get("start", "??:??"))
    else:
        wann = sprache.t(f"punkt.{art}") if f"punkt.{art}" in sprache.TEXTE[
            sprache.VORGABE] else art
        versatz = int(eintrag.get("versatz_min") or 0)
        if versatz:
            wann += sprache.t("punkt.versatz", n=versatz)
        if eintrag.get("frueh"):
            wann += sprache.t("punkt.fruehestens", zeit=eintrag["frueh"])
        if eintrag.get("spaet"):
            wann += sprache.t("punkt.spaetestens", zeit=eintrag["spaet"])
    stellung = int(eintrag.get("position", 100))
    # „auf“ und „zu“ bleiben, wie sie sind – die Wörter hängen nicht an der
    # Zählweise. Nur die Zahl dazwischen dreht sich.
    if stellung >= 100:
        was = sprache.t("punkt.auf")
    elif stellung <= 0:
        was = sprache.t("punkt.zu")
    else:
        was = sprache.t("punkt.prozent",
                        n=100 - stellung if invertiert else stellung)
    gilt = eintrag.get("gilt", "immer")
    geltung = ("" if gilt == "immer"
               else sprache.t(f"punkt.gilt.{gilt}"))
    text = sprache.t("punkt.satz", was=was, wann=wann, geltung=geltung)
    if mit_bedingungen:
        for bedingung in eintrag.get("wenn") or []:
            text += (f" ({bedingung.get('entity', '').split('.')[-1]}"
                     f" = {bedingung.get('wert')})")
    return text


# ------------------------------------------------------------- Vorgaben ----

WERKTAGE = ["mon", "tue", "wed", "thu", "fri"]
ALLE = TAGE


def standardplan(art: str = "wohnraum") -> list[dict]:
    """Ein brauchbarer Plan zum Anfangen.

    Nachgebildet nach dem, was in diesem Haus bisher als Automation lief –
    wer einen Raum neu anlegt, soll nicht bei null beginnen.
    """
    def punkt(position, ausloeser="uhrzeit", start="", **rest):
        return {"ausloeser": ausloeser, "start": start, "versatz_min": 0,
                "frueh": "", "spaet": "", "position": position, "wenn": [],
                "gilt": "immer", "tage": ALLE, "name": "", **rest}

    if art == "kinderzimmer":
        return [
            punkt(100, start="06:30", gilt="schultag", tage=WERKTAGE),
            punkt(100, start="10:00", gilt="schulfrei"),
            punkt(0, "sonnenuntergang", spaet="20:30", gilt="morgen_schultag"),
            punkt(0, "sonnenuntergang", spaet="22:00", gilt="morgen_schulfrei"),
        ]
    if art == "schlafzimmer":
        return [
            punkt(100, start="07:00", gilt="schultag", tage=WERKTAGE),
            punkt(100, start="09:00", gilt="schulfrei"),
            punkt(0, "sonnenuntergang", spaet="22:30"),
        ]
    if art == "buero":
        return [
            punkt(100, "sonnenaufgang", frueh="08:30", tage=WERKTAGE),
            punkt(100, "sonnenaufgang", frueh="10:00", tage=["sat", "sun"]),
            punkt(0, "sonnenuntergang", spaet="23:00"),
        ]
    return [
        punkt(100, start="06:30", gilt="schultag", tage=WERKTAGE),
        punkt(100, start="10:00", gilt="schulfrei"),
        punkt(0, "sonnenuntergang", spaet="23:00"),
    ]
