"""Prüfungen der Rechenkerne – ohne Home Assistant, ohne Netz.

Aufruf:  python3 -m pytest rolloplaner/tests/ -q
oder:    python3 rolloplaner/tests/test_logik.py

Geprüft wird, was beim Bauen tatsächlich schiefging: vertauschter Auf- und
Untergang, eine Streuung, die nur in eine Richtung wirkt, ein Schaltpunkt, der
als erledigt gilt, obwohl er nie ausgeführt wurde.
"""
import os
import pathlib
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
os.environ.setdefault("TZ", "Europe/Berlin")
try:
    import time as _time
    _time.tzset()
except AttributeError:  # pragma: no cover – Windows
    pass

import ha_api         # noqa: E402
import regelung       # noqa: E402
import sonne          # noqa: E402
import sprache        # noqa: E402
import store          # noqa: E402
import uebernahme     # noqa: E402
import zeitplan       # noqa: E402

# Ottobrunn, wie in Home Assistant hinterlegt
LAT, LON = 48.07274558526573, 11.689136624336243


def _kalender(heute=False, morgen=False):
    return zeitplan.Schulkalender(heute, morgen, {})


def _sonnenstand():
    s = sonne.Sonnenstand(LAT, LON)
    # dieselbe Justierung, die der Takt aus sun.sun vornimmt
    s.kalibrieren("sonnenaufgang", datetime(2026, 8, 27, 6, 20, 54))
    s.kalibrieren("sonnenuntergang", datetime(2026, 8, 27, 20, 7, 43))
    return s


# ------------------------------------------------------------------ Sonne ----

def test_aufgang_ist_vor_untergang():
    """Der Klassiker: In der NOAA-Formel steht das Vorzeichen des
    Stundenwinkels für den Aufgang anders herum als für den Untergang. Wer es
    verwechselt, bekommt einen Sonnenuntergang um sechs Uhr früh – und ein
    Rollo, das morgens zufährt."""
    s = sonne.Sonnenstand(LAT, LON)
    for tag in (date(2026, 1, 15), date(2026, 6, 21), date(2026, 12, 21)):
        assert s.aufgang(tag) < s.untergang(tag), tag
        assert 4 <= s.aufgang(tag).hour <= 9, tag
        assert 15 <= s.untergang(tag).hour <= 22, tag


def test_justierung_trifft_home_assistant():
    s = _sonnenstand()
    assert abs((s.untergang(date(2026, 8, 27))
                - datetime(2026, 8, 27, 20, 7, 43)).total_seconds()) < 2
    # … und auch am Nachbartag, nicht nur an dem einen justierten
    assert abs((s.untergang(date(2026, 8, 26))
                - datetime(2026, 8, 26, 20, 9, 40)).total_seconds()) < 90


def test_justierung_verwirft_unsinn():
    s = sonne.Sonnenstand(LAT, LON)
    assert s.kalibrieren("sonnenaufgang", datetime(2026, 8, 27, 12, 0)) is None
    assert "sonnenaufgang" not in s.korrektur


def test_sommerzeit_bleibt_ortszeit():
    """Ohne den je Tag bestimmten Zeitzonenversatz läge der Sonnenuntergang im
    Sommer eine Stunde daneben."""
    s = sonne.Sonnenstand(LAT, LON)
    juni = s.untergang(date(2026, 6, 21))
    dezember = s.untergang(date(2026, 12, 21))
    assert juni.hour == 21 and dezember.hour == 16


def test_winkelabstand_ueber_norden():
    assert sonne.winkelabstand(10, 350) == 20
    assert sonne.winkelabstand(350, 10) == 20
    assert sonne.winkelabstand(180, 0) == 180


def test_sonne_im_fenster():
    # Südwestfenster, Sonne im Westen, hoch genug
    assert sonne.sonne_steht_im_fenster(260, 30, 225, 90, 12)
    # dieselbe Richtung, aber die Sonne steht zu tief
    assert not sonne.sonne_steht_im_fenster(260, 5, 225, 90, 12)
    # Sonne im Osten – trifft das Südwestfenster nicht
    assert not sonne.sonne_steht_im_fenster(100, 30, 225, 90, 12)
    # ohne Ausrichtung bleibt der Hitzeschutz aus
    assert not sonne.sonne_steht_im_fenster(260, 30, None, 90, 12)


# --------------------------------------------------------------- Zeitplan ----

PLAN_KIND = [
    {"ausloeser": "uhrzeit", "start": "06:30", "position": 100, "gilt": "schultag",
     "tage": zeitplan.WERKTAGE, "versatz_min": 0, "frueh": "", "spaet": "", "wenn": []},
    {"ausloeser": "sonnenuntergang", "start": "", "position": 0, "gilt": "morgen_schultag",
     "tage": zeitplan.ALLE, "versatz_min": 0, "frueh": "", "spaet": "20:30", "wenn": []},
    {"ausloeser": "sonnenuntergang", "start": "", "position": 0, "gilt": "morgen_schulfrei",
     "tage": zeitplan.ALLE, "versatz_min": 0, "frueh": "", "spaet": "22:00", "wenn": []},
]


def test_klammer_greift_im_sommer():
    """Im Juni geht die Sonne um 21:18 unter – „spätestens 20:30“ muss
    gewinnen, sonst bleibt das Kinderzimmer eine Dreiviertelstunde zu hell."""
    s = _sonnenstand()
    treffer = zeitplan.letzter_zeitpunkt(
        PLAN_KIND, datetime(2026, 6, 22, 21, 0), _kalender(), s)
    assert treffer[0].strftime("%H:%M") == "20:30"


def test_klammer_greift_im_winter_nicht():
    """Im Dezember geht die Sonne um 16:20 unter – lange vor der Klammer."""
    s = _sonnenstand()
    treffer = zeitplan.letzter_zeitpunkt(
        PLAN_KIND, datetime(2026, 12, 21, 18, 0), _kalender(), s)
    assert treffer[0].hour == 16


def test_morgen_schulfrei_verschiebt_den_abend():
    """Am selben Wochentag, zur selben Uhrzeit, bei gleichem Wetter: Steht
    morgen die Schule an, ist um 21 Uhr längst zugefahren – steht sie nicht an,
    ist noch offen. Der Unterschied liegt allein am *morgigen* Tag.

    Im Juni geht die Sonne um 21:18 unter. „Spätestens 20:30“ greift also,
    „spätestens 22:00“ nicht – dort wartet der Punkt auf den Sonnenuntergang."""
    s = _sonnenstand()
    um_neun = datetime(2026, 6, 25, 21, 0)

    morgen_schule = zeitplan.letzter_zeitpunkt(
        PLAN_KIND, um_neun, _kalender(heute=False, morgen=False), s)
    assert morgen_schule[1]["position"] == 0
    assert morgen_schule[0].strftime("%H:%M") == "20:30"

    morgen_frei = zeitplan.letzter_zeitpunkt(
        PLAN_KIND, um_neun, _kalender(heute=False, morgen=True), s)
    assert morgen_frei[1]["position"] == 100        # noch der Öffner von früh

    # … und eine halbe Stunde später ist auch dort zugefahren, zum
    # Sonnenuntergang statt zur Klammer.
    spaeter = zeitplan.letzter_zeitpunkt(
        PLAN_KIND, datetime(2026, 6, 25, 21, 30),
        _kalender(heute=False, morgen=True), s)
    assert spaeter[1]["position"] == 0
    assert spaeter[0].strftime("%H:%M") == "21:18"


def test_rueckschau_ueber_die_nacht():
    """Um zwei Uhr nachts gilt noch der Punkt von gestern Abend. Genau dafür
    rechnet der Planer die Sonnenzeiten selbst – `sun.sun` kennt nur den
    nächsten Untergang, nicht den vergangenen."""
    s = _sonnenstand()
    treffer = zeitplan.letzter_zeitpunkt(
        PLAN_KIND, datetime(2026, 6, 23, 2, 0), _kalender(), s)
    assert treffer[1]["position"] == 0
    assert treffer[0].date() == date(2026, 6, 22)


def test_bedingung_ohne_zustaende_gilt_nicht():
    """Ohne Kenntnis der Zustände darf ein bedingter Punkt **nicht** greifen –
    sonst führe die Terrassentür auch in der Stellung „aus“ zu."""
    punkt = {"ausloeser": "uhrzeit", "start": "00:00", "position": 0, "gilt": "immer",
             "tage": zeitplan.ALLE, "versatz_min": 0, "frueh": "", "spaet": "",
             "wenn": [{"entity": "input_select.x", "wert": "24 Uhr"}]}
    jetzt = datetime(2026, 9, 2, 1, 0)
    assert zeitplan.letzter_zeitpunkt([punkt], jetzt, _kalender(), None) is None
    assert zeitplan.letzter_zeitpunkt([punkt], jetzt, _kalender(), None,
                                      zustaende={"input_select.x": "aus"}) is None
    assert zeitplan.letzter_zeitpunkt([punkt], jetzt, _kalender(), None,
                                      zustaende={"input_select.x": "24 Uhr"}) is not None


def test_streuung_wirkt_in_beide_richtungen():
    """Der Versatz muss in der Zeitpunktberechnung sitzen, nicht danach: Wer
    ihn erst hinterher aufschlägt, sieht nur Verspätungen – ein vorgezogener
    Punkt wird nie gefunden, weil zu seiner Zeit noch der vorige gilt."""
    plan = [{"ausloeser": "uhrzeit", "start": "20:00", "position": 0, "gilt": "immer",
             "tage": zeitplan.ALLE, "versatz_min": 0, "frueh": "", "spaet": "", "wenn": []}]
    frueher = zeitplan.letzter_zeitpunkt(
        plan, datetime(2026, 9, 2, 19, 50), _kalender(), None,
        anpassen=lambda z, e, t: z - timedelta(minutes=15))
    assert frueher is not None and frueher[0].strftime("%H:%M") == "19:45"


# --------------------------------------------------------------- Übernahme ----

def test_zeitklammer_erkennt_toten_zweig():
    """Zwei Zeitbedingungen mit verschiedenen Wochentagen sind UND-verknüpft
    und treffen nie zusammen zu. So ein Zweig darf nicht als Schaltpunkt
    übernommen werden – er läuft in der Automation ja auch nicht."""
    bedingungen = [
        {"condition": "time", "after": "08:29:59",
         "weekday": ["mon", "tue", "wed", "thu", "fri"]},
        {"condition": "time", "after": "09:59:59", "weekday": ["sat", "sun"]},
    ]
    assert uebernahme._zeitklammer(bedingungen) == {"widerspruch": True}


def test_zeitklammer_rundet_die_krumme_sekunde():
    """`after: 08:29:59` ist als „ab halb neun“ gemeint."""
    klammer = uebernahme._zeitklammer([{"condition": "time", "after": "08:29:59"}])
    assert klammer["frueh"] == "08:30"


def test_falten_zieht_zwei_ausloeser_zusammen():
    """„Sonnenuntergang oder 23:00“ ist ein Punkt mit Klammer, nicht zwei."""
    plan = [
        {"ausloeser": "sonnenuntergang", "start": "", "position": 0, "gilt": "immer",
         "tage": zeitplan.ALLE, "versatz_min": 0, "frueh": "", "spaet": "", "wenn": []},
        {"ausloeser": "uhrzeit", "start": "23:00", "position": 0, "gilt": "immer",
         "tage": zeitplan.ALLE, "versatz_min": 0, "frueh": "", "spaet": "", "wenn": []},
    ]
    gefaltet = uebernahme._falten(plan)
    assert len(gefaltet) == 1
    assert gefaltet[0]["spaet"] == "23:00"


def test_falten_laesst_verschiedene_bedingungen_stehen():
    """Zwei Punkte, die an verschiedenen Stellungen eines Auswahlhelfers
    hängen, dürfen nicht zusammengezogen werden."""
    plan = [
        {"ausloeser": "sonnenuntergang", "start": "", "position": 0, "gilt": "immer",
         "tage": zeitplan.ALLE, "versatz_min": 0, "frueh": "", "spaet": "",
         "wenn": [{"entity": "input_select.x", "wert": "normal"}]},
        {"ausloeser": "uhrzeit", "start": "23:00", "position": 0, "gilt": "immer",
         "tage": zeitplan.ALLE, "versatz_min": 0, "frueh": "", "spaet": "",
         "wenn": [{"entity": "input_select.x", "wert": "24 Uhr"}]},
    ]
    assert len(uebernahme._falten(plan)) == 2


def test_gleiche_muster_teilen_sich_einen_plan():
    """Zwei Rollos, die identisch fahren, bekommen einen gemeinsamen Zeitplan –
    ein einzelnes behält seinen eigenen. Ein benannter Plan mit einem Folger
    wäre nur ein Umweg."""
    def punkte(uhr):
        return [{"ausloeser": "uhrzeit", "start": uhr, "position": 100,
                 "gilt": "immer", "tage": zeitplan.ALLE, "versatz_min": 0,
                 "frueh": "", "spaet": "", "wenn": []}]

    je_rollo = {
        "cover.a": {"zeitplan": punkte("07:00"), "quellen": [], "hinweise": []},
        "cover.b": {"zeitplan": punkte("07:00"), "quellen": [], "hinweise": []},
        "cover.c": {"zeitplan": punkte("09:00"), "quellen": [], "hinweise": []},
    }
    bereiche = {"cover.a": "Küche", "cover.b": "Küche", "cover.c": "Bad"}
    cover = [{"entity_id": e, "name": e} for e in je_rollo]
    rollos, plaene = uebernahme._zu_plaenen(je_rollo, bereiche, cover)

    assert len(plaene) == 1, "a und b teilen sich einen Plan, c nicht"
    assert plaene[0]["name"] == "Küche"
    nach_id = {r["entity_id"]: r for r in rollos}
    assert nach_id["cover.a"]["plan"] == nach_id["cover.b"]["plan"] == plaene[0]["id"]
    assert nach_id["cover.c"]["plan"] == ""
    assert len(nach_id["cover.c"]["zeitplan"]) == 1


def test_rollo_ohne_automation_kommt_trotzdem_mit():
    """Sonst fehlten die beiden Schlafzimmer-Rollos stillschweigend – sie
    fahren heute nur bei Rauch und im Urlaub."""
    cover = [{"entity_id": "cover.ohne", "name": "Rollo ohne Plan"}]
    rollos, plaene = uebernahme._zu_plaenen({}, {"cover.ohne": "Bad"}, cover)
    assert len(rollos) == 1 and rollos[0]["zeitplan"] == []
    assert rollos[0]["hinweise"], "das muss auffallen"


# ------------------------------------------------------------------ Store ----

def test_rollo_ohne_ausrichtung_beschattet_nicht():
    rollo = store.validate_rollo({"entity_id": "cover.x", "beschattung": True,
                                  "ausrichtung": None})
    assert rollo["beschattung"] is False


def test_himmelsrichtung_als_wort():
    rollo = store.validate_rollo({"entity_id": "cover.x", "ausrichtung": "sw"})
    assert rollo["ausrichtung"] == 225


def test_offen_muss_ueber_zu_liegen():
    try:
        store.validate_rollo({"entity_id": "cover.x", "position_offen": 0,
                              "position_zu": 100})
    except store.ValidationError:
        return
    raise AssertionError("verdrehte Stellungen hätten auffallen müssen")


def test_die_faehigkeiten_des_antriebs_werden_gelesen():
    """Welche Knöpfe die Übersicht zeigt, hängt daran.

    Ein Halt-Knopf vor einem Antrieb, der nicht anhalten kann, ist schlimmer
    als keiner: Er behauptet, es ginge – und wer ihn drückt, sucht den Fehler
    beim Rollo statt beim Antrieb.
    """
    def zustand(merkmale):
        return {"attributes": {"supported_features": merkmale}}

    # 15 = open|close|set_position|stop, 3 = nur auf und zu.
    assert ha_api.kann_position(zustand(15)) and ha_api.kann_stoppen(zustand(15))
    assert not ha_api.kann_position(zustand(3))
    assert not ha_api.kann_stoppen(zustand(3))
    # 11 = auf|zu|stop, ohne Zwischenstellung: Halt ja, Schieber nein.
    assert ha_api.kann_stoppen(zustand(11)) and not ha_api.kann_position(zustand(11))
    # Fehlt die Angabe ganz, wird nichts versprochen.
    for leer in (None, {}, zustand(None), zustand("viele")):
        assert not ha_api.kann_position(leer)
        assert not ha_api.kann_stoppen(leer)


def test_nur_cover_sind_rollos():
    """Ein Rollo *ist* sein `cover.` – alles andere wäre eine Verwechslung,
    die erst beim Fahren auffiele."""
    for eid in ("light.x", "input_boolean.y", ""):
        try:
            store.validate_rollo({"entity_id": eid})
        except store.ValidationError:
            continue
        raise AssertionError(f"{eid!r} hätte abgewiesen werden müssen")


def test_rollo_folgt_entweder_einem_plan_oder_hat_einen_eigenen():
    """Beides gleichzeitig wäre zweideutig: Welcher gilt dann?"""
    punkt = {"ausloeser": "uhrzeit", "start": "07:00", "position": 100,
             "tage": ["mon"]}
    mit_plan = store.validate_rollo({"entity_id": "cover.x", "plan": "abc",
                                     "zeitplan": [punkt]})
    assert mit_plan["zeitplan"] == []
    ohne = store.validate_rollo({"entity_id": "cover.x", "zeitplan": [punkt]})
    assert len(ohne["zeitplan"]) == 1


def test_art_wird_aus_dem_namen_geraten_nicht_aus_der_id():
    """In dieser Anlage heißt die Schlafzimmer-Balkontür
    `cover.rollo_terrassentur`: Das Gerät hing im alten Haus woanders. Der Name
    wurde gepflegt, die ID nicht."""
    assert uebernahme.art_raten("Rollo Schlafzimmer Balkontür",
                                "cover.rollo_terrassentur") == "balkontuer"
    assert uebernahme.art_raten("Rollo Terrassentür", "cover.terrassentur") == "terrassentuer"
    assert uebernahme.art_raten("Rollo Küche", "cover.rollo_kuche") == "fenster"
    # Ohne aussagekräftigen Namen zählt die ID
    assert uebernahme.art_raten("", "cover.balkon_links") == "balkontuer"


def test_uhrzeit_punkt_verliert_die_klammer():
    """Bei fester Uhrzeit wären „frühestens“/„spätestens“ sinnlos und nur
    verwirrend."""
    plan = store.validate_zeitplan([{"ausloeser": "uhrzeit", "start": "07:00",
                                     "frueh": "06:00", "spaet": "08:00",
                                     "position": 100, "tage": ["mon"]}])
    assert plan[0]["frueh"] == "" and plan[0]["spaet"] == ""


# ------------------------------------------------------- Zählweise ----

def test_umgedrehte_zaehlweise_beschriftet_nur_um():
    """„auf“ und „zu“ hängen nicht an der Zählweise – nur die Zahl dazwischen.

    Sonst hieße ein geschlossenes Rollo bei umgedrehter Zählung „auf“, und der
    Schalter, der das Verrechnen verhindern soll, wäre selbst die Fehlerquelle.
    """
    def punkt(position):
        return {"ausloeser": "uhrzeit", "start": "12:00", "position": position,
                "gilt": "immer", "tage": zeitplan.ALLE, "versatz_min": 0,
                "frueh": "", "spaet": "", "wenn": []}

    assert zeitplan.beschreibung(punkt(100), invertiert=True).startswith("auf")
    assert zeitplan.beschreibung(punkt(0), invertiert=True).startswith("zu")
    assert zeitplan.beschreibung(punkt(35), invertiert=True).startswith("65 %")
    assert zeitplan.beschreibung(punkt(35)).startswith("35 %")


def test_anzeige_prozent_ist_ihre_eigene_umkehrung():
    """Hin und zurück muss denselben Wert ergeben – daran hängt, dass ein
    Umschalten der Zählweise keinen gespeicherten Zeitplan verdreht."""
    for wert in (0, 1, 35, 50, 99, 100):
        assert store.anzeige_prozent(store.anzeige_prozent(wert, True), True) == wert
        assert store.anzeige_prozent(wert, False) == wert
    assert store.anzeige_prozent(None, True) is None


# --------------------------------------------------- Eigene Schalter ----

def test_eigener_schalter_wird_am_praefix_erkannt():
    assert store.eigener_schalter("rolloplaner:a1b2c3") == "a1b2c3"
    assert store.eigener_schalter("input_boolean.x") is None
    assert store.eigener_schalter("") is None


def test_auswahl_braucht_zwei_stellungen():
    try:
        store.validate_schalter([{"name": "Halb", "art": "auswahl", "optionen": ["nur eine"]}])
    except store.ValidationError:
        pass
    else:
        raise AssertionError("eine Auswahl mit einer Stellung ist keine Auswahl")


def test_vorgabe_wird_auf_eine_gueltige_stellung_gezogen():
    """Eine Vorgabe, die es nicht gibt, ließe den Schalter beim ersten Start in
    einem Zustand stehen, den er gar nicht annehmen kann."""
    [k] = store.validate_schalter([{"name": "Tür", "art": "auswahl",
                                    "optionen": ["normal", "aus"], "vorgabe": "gibtsnicht"}])
    assert k["vorgabe"] == "normal"
    [k] = store.validate_schalter([{"name": "Öffner", "art": "schalter",
                                    "vorgabe": "vielleicht"}])
    assert k["vorgabe"] == "on"


def test_schalter_behaelt_seine_id():
    """Die ID darf nicht am Namen hängen: Ein umbenannter Schalter soll seine
    Entität in Home Assistant behalten, statt als neue aufzutauchen und die
    alte als Karteileiche zu hinterlassen."""
    [k] = store.validate_schalter([{"id": "feste_id", "name": "Vorher"}])
    [k2] = store.validate_schalter([{**k, "name": "Nachher"}])
    assert k2["id"] == "feste_id"


def test_bedingung_auf_eigenen_schalter_laeuft_durch_dieselbe_pruefung():
    punkt = {"ausloeser": "uhrzeit", "start": "12:00", "position": 0, "gilt": "immer",
             "tage": zeitplan.ALLE, "versatz_min": 0, "frueh": "", "spaet": "",
             "wenn": [{"entity": "rolloplaner:abc", "wert": "24 Uhr"}]}
    assert zeitplan.bedingungen_erfuellt(punkt, {"rolloplaner:abc": "24 Uhr"})
    assert not zeitplan.bedingungen_erfuellt(punkt, {"rolloplaner:abc": "aus"})
    # Ein Schalter, den es nicht mehr gibt, lässt den Punkt **nicht** greifen.
    assert not zeitplan.bedingungen_erfuellt(punkt, {})


# ------------------------------------------------------------ Die Karte ----

def test_kein_backtick_im_stilblock_der_karte():
    """Das CSS der Karte steckt in einem JavaScript-Template-String.

    Ein Backtick in einem CSS-Kommentar beendet ihn – ab da liest der Browser
    Programmtext statt Stil, und die Karte bleibt leer. Das ist beim Bauen
    dreimal passiert, immer beim Erklären einer CSS-Eigenschaft in Anführungs-
    zeichen. Deshalb steht es hier und nicht in einem Merkzettel.
    """
    karte = (pathlib.Path(__file__).parent.parent / "card"
             / "rolloplaner-card.js").read_text(encoding="utf-8")
    # Genau der Stilblock der Karte, nicht irgendein <style> in der Datei: Der
    # Editor bringt seinen eigenen mit, und dessen Backticks sind in Ordnung –
    # sie stehen in ${…}-Ausdrücken. Geprüft wird von `_stil()` bis zum
    # Ende seines Templates; dazwischen gehört genau der öffnende Backtick.
    anfang = karte.index("  _stil() {")
    stil = karte[anfang:karte.index("</style>", anfang)]
    anzahl = stil.count("`")
    if anzahl != 1:
        zeilen = [z.strip()[:70] for z in stil.splitlines() if "`" in z][1:]
        raise AssertionError(
            f"{anzahl} Backticks im Stilblock (1 ist richtig): " + "; ".join(zeilen))


def test_die_karte_kennt_in_beiden_sprachen_dieselben_schluessel():
    """Derselbe Wächter wie im Backend, nur für die Karte.

    Fehlt dort ein Schlüssel, fällt die Stelle ins Deutsche zurück – und das
    merkt am wenigsten der, der die Sprache nicht spricht.
    """
    import re
    karte = (pathlib.Path(__file__).parent.parent / "card"
             / "rolloplaner-card.js").read_text(encoding="utf-8")
    tabellen = {}
    for code in ("de", "en"):
        block = re.search(rf"\n  {code}: \{{(.*?)\n  \}},\n", karte, re.S)
        assert block, f"Sprachtabelle {code} nicht gefunden"
        paare = re.findall(r'"([a-z][\w.]*)":\s*("[^"]*")', block.group(1))
        # Derselbe stumme Fehler wie in der Oberfläche: JavaScript nimmt bei
        # einem doppelt vergebenen Schlüssel den letzten, ein Wörterbuch hier
        # ebenso – im Bild stünde also die ältere Fassung, und niemand merkt
        # es. Einmal ist es genau so passiert.
        namen = [n for n, _ in paare]
        doppelt = sorted({n for n in namen if namen.count(n) > 1})
        assert not doppelt, f"{code}: doppelt vergeben {doppelt}"
        tabellen[code] = dict(paare)
    deutsch = set(tabellen["de"])
    for code, tabelle in tabellen.items():
        assert not deutsch - set(tabelle), f"{code}: es fehlen {sorted(deutsch - set(tabelle))}"
        assert not set(tabelle) - deutsch, f"{code}: unbekannt {sorted(set(tabelle) - deutsch)}"
    # Und die Platzhalter müssen zueinander passen.
    for schluessel, deutsch_wert in tabellen["de"].items():
        erwartet = set(re.findall(r"\{(\w+)\}", deutsch_wert))
        for code, tabelle in tabellen.items():
            hier = set(re.findall(r"\{(\w+)\}", tabelle[schluessel]))
            assert hier == erwartet, f"{code}/{schluessel}: {hier} statt {erwartet}"


def test_alle_drei_stellen_nennen_dieselbe_fassung():
    """Die Nummer steht an drei Stellen – und sie müssen sich einig sein.

    Der Supervisor liest `config.yaml`, das Protokoll `version.py`, die Karte
    ihre eigene Zeile. Läuft eine nach, meldet das Add-on beim Start eine
    Fassung, die es gar nicht mehr ist – und genau daran sucht man einen
    Fehler zuerst.
    """
    import re
    wurzel = pathlib.Path(__file__).parent.parent
    yaml = re.search(r'^version:\s*"([^"]+)"',
                     (wurzel / "config.yaml").read_text(encoding="utf-8"), re.M)
    py = re.search(r'VERSION\s*=\s*"([^"]+)"',
                   (wurzel / "backend" / "version.py").read_text(encoding="utf-8"))
    karte = re.search(r'CARD_VERSION\s*=\s*"([^"]+)"',
                      (wurzel / "card" / "rolloplaner-card.js").read_text(encoding="utf-8"))
    assert yaml and py and karte, "eine der drei Fassungszeilen ist nicht auffindbar"
    fassungen = {"config.yaml": yaml.group(1), "version.py": py.group(1),
                 "rolloplaner-card.js": karte.group(1)}
    assert len(set(fassungen.values())) == 1, f"uneinig: {fassungen}"


def test_bei_einem_stueck_gilt_die_einzahl():
    """„1 covers shaded" liest sich wie ein Fehler – und wer die Sprache nicht
    spricht, hält es für einen."""
    sprache.setze("en")
    assert sprache.t("lage.beschattet", n=1) == "one cover shaded"
    assert sprache.t("lage.beschattet", n=3) == "3 covers shaded"
    sprache.setze("de")
    assert sprache.t("lage.beschattet", n=1) == "ein Rollo beschattet"
    assert sprache.t("lage.beschattet", n=2) == "2 Rollos beschattet"
    # Ohne Einzahlform bleibt es bei der einen Vorlage – kein Rückfall auf den
    # nackten Schlüssel.
    assert "{" not in sprache.t("lage.mit_automatik", n=1, gesamt=9)


def _oberflaechen_tabellen():
    """Die beiden Sprachtabellen aus `index.html` als Wörterbücher.

    Die Texte stehen dort teils über mehrere Zeilen aneinandergehängt
    (``"..." + "..."``) – deshalb wird jeder Eintrag bis zum nächsten Schlüssel
    gelesen und danach werden alle Zeichenketten darin zusammengefügt.
    """
    import re
    quelle = (pathlib.Path(__file__).parent.parent / "frontend"
              / "index.html").read_text(encoding="utf-8")
    block = re.search(r"\nconst UI = \{\n(.*?)\n\};\n", quelle, re.S)
    assert block, "Sprachtabelle der Oberfläche nicht gefunden"
    tabellen = {}
    for code in ("de", "en"):
        teil = re.search(rf"\n  {code}: \{{\n(.*?)\n  \}},?\n",
                         "\n" + block.group(1) + "\n", re.S)
        assert teil, f"Sprachtabelle {code} nicht gefunden"
        # Kurze Texte stehen zu mehreren in einer Zeile, lange über mehrere
        # Zeilen hinweg. Deshalb wird nicht zeilenweise gelesen, sondern von
        # einem Schlüssel bis zum nächsten.
        rumpf = "\n" + teil.group(1)   # damit auch der erste Schlüssel eine Kante hat
        marken = list(re.finditer(r'(?<=[\{,\n])\s*"([a-z][\w.]*)":', rumpf))
        # Ein Schlüssel zweimal in derselben Tabelle: JavaScript nimmt den
        # letzten, ein Wörterbuch hier ebenso – der Fehler bliebe also stumm,
        # während im Bild die ältere Fassung steht. Darum vorher zählen.
        namen = [m.group(1) for m in marken]
        doppelt = sorted({n for n in namen if namen.count(n) > 1})
        assert not doppelt, f"{code}: doppelt vergeben {doppelt}"
        tabellen[code] = {}
        for i, marke in enumerate(marken):
            ende = marken[i + 1].start() if i + 1 < len(marken) else len(rumpf)
            wert = rumpf[marke.end():ende]
            tabellen[code][marke.group(1)] = "".join(
                re.findall(r'"((?:[^"\\]|\\.)*)"', wert))
    return tabellen


def test_die_oberflaeche_kennt_in_beiden_sprachen_dieselben_schluessel():
    """Wie bei Karte und Backend: eine halbe Übersetzung ist schlimmer als gar
    keine, weil sie erst dem auffällt, der die andere Sprache nicht kann."""
    import re
    tabellen = _oberflaechen_tabellen()
    assert len(tabellen["de"]) > 300, "die Tabelle wurde nicht richtig gelesen"
    deutsch = set(tabellen["de"])
    for code, tabelle in tabellen.items():
        assert not deutsch - set(tabelle), f"{code}: es fehlen {sorted(deutsch - set(tabelle))}"
        assert not set(tabelle) - deutsch, f"{code}: unbekannt {sorted(set(tabelle) - deutsch)}"
    for schluessel, wert in tabellen["de"].items():
        erwartet = set(re.findall(r"\{(\w+)\}", wert))
        for code, tabelle in tabellen.items():
            hier = set(re.findall(r"\{(\w+)\}", tabelle[schluessel]))
            assert hier == erwartet, f"{code}/{schluessel}: {hier} statt {erwartet}"


def test_jeder_verwendete_textschluessel_steht_in_der_tabelle():
    """Ein vertippter Schlüssel zeigt im Bild den Schlüssel selbst.

    Das sieht man nur, wenn man genau diesen Reiter öffnet – und meist erst,
    wenn jemand anderes es meldet. Hier fällt es beim Prüflauf auf.
    """
    import re
    quelle = (pathlib.Path(__file__).parent.parent / "frontend"
              / "index.html").read_text(encoding="utf-8")
    tabelle = _oberflaechen_tabellen()["de"]
    ohne_tabelle = re.sub(r"\nconst UI = \{\n.*?\n\};\n", "\n", quelle, flags=re.S)
    # Ein Schlüssel steht nicht immer gleich hinter der Klammer – es gibt auch
    # `t(gut ? "a" : "b")`. Deshalb wird der ganze Aufruf gelesen, Klammer für
    # Klammer, und darin jede Zeichenkette in Schlüsselform gewertet.
    schluesselform = re.compile(r'"([a-z][\w]*(?:\.[\w]+)+)"')
    benutzt = set()
    for anfang in (m.end() for m in re.finditer(r'\bt\(', ohne_tabelle)):
        tiefe, i = 1, anfang
        while i < len(ohne_tabelle) and tiefe:
            if ohne_tabelle[i] == "(":
                tiefe += 1
            elif ohne_tabelle[i] == ")":
                tiefe -= 1
            i += 1
        benutzt |= set(schluesselform.findall(ohne_tabelle[anfang:i]))
    benutzt |= set(re.findall(r'data-t(?:-titel)?="([a-z][\w.]*)"', ohne_tabelle))
    # Zusammengesetzte Schlüssel: `t("aus." + w)` und Geschwister. Die
    # Vorsilbe allein ist kein Schlüssel – sie steht für die ganze Sippe.
    for vorsilbe in re.findall(r'\bt\("([a-z][\w.]*\.)"\s*\+', ohne_tabelle):
        benutzt.discard(vorsilbe)
        benutzt |= {s for s in tabelle if s.startswith(vorsilbe)}
    # Die Einzahlform wird nie selbst aufgerufen – `t` greift sie sich, wenn
    # n gleich eins ist. Benutzt ist sie also, sobald ihr Grundwort benutzt ist.
    benutzt |= {s for s in tabelle
                if s.endswith("_1") and s[:-2] in benutzt}
    assert not benutzt - set(tabelle), f"nicht in der Tabelle: {sorted(benutzt - set(tabelle))}"
    assert not set(tabelle) - benutzt, f"nie benutzt: {sorted(set(tabelle) - benutzt)}"


def test_karte_ist_gueltiges_javascript():
    """Ein Syntaxfehler in der Karte fällt sonst erst im Dashboard auf – und
    dort sieht man nur, dass nichts kommt."""
    import shutil
    import subprocess
    node = shutil.which("node")
    if node is None:
        return                      # ohne node keine Prüfung, aber kein Fehler
    karte = (pathlib.Path(__file__).parent.parent / "card" / "rolloplaner-card.js")
    ergebnis = subprocess.run([node, "--check", str(karte)],
                              capture_output=True, text=True)
    if ergebnis.returncode != 0:
        raise AssertionError(ergebnis.stderr.strip().splitlines()[-1])


def test_umbenannter_schalter_behaelt_seine_entitaet():
    """Am 27.08.2026 wurde „Erdgeschoss" zu „EG öffnen" – und verschwand von
    der Karte.

    Die entity_id entsteht **einmal** beim Anlegen aus dem Namen und ändert
    sich beim Umbenennen nie; der Anzeigename schon. Wer sie aus dem aktuellen
    Namen zurückrechnet, zeigt auf eine Entität, die es nicht gibt.
    """
    index = {"switch.rolloplaner_erdgeschoss": {
        "entity_id": "switch.rolloplaner_erdgeschoss", "state": "on",
        "attributes": {"friendly_name": "Rolloplaner EG öffnen"}}}
    assert regelung._eigene_entitaet(index, "switch", "EG öffnen") \
        == "switch.rolloplaner_erdgeschoss"
    # Ohne Gerätenamen davor ebenso …
    index["switch.rolloplaner_erdgeschoss"]["attributes"]["friendly_name"] = "EG öffnen"
    assert regelung._eigene_entitaet(index, "switch", "EG öffnen") \
        == "switch.rolloplaner_erdgeschoss"
    # … und wo nichts zu finden ist, bleibt die Schätzung.
    assert regelung._eigene_entitaet({}, "switch", "Neuer Schalter") \
        == "switch.rolloplaner_neuer_schalter"


# ------------------------------------------------------------ Sprache ----

def test_der_satz_wird_je_sprache_neu_gebaut():
    """Übersetzen heißt hier nicht Wörter tauschen.

    „zu um Sonnenuntergang, spätestens 22:00 an Schultagen" hat auf Englisch
    eine andere Wortstellung. Deshalb steht je Sprache die ganze Vorlage da,
    nicht eine Wörterliste.
    """
    punkt = {"ausloeser": "sonnenuntergang", "start": "", "position": 0,
             "gilt": "schultag", "tage": zeitplan.ALLE, "versatz_min": 0,
             "frueh": "", "spaet": "22:00", "wenn": []}
    try:
        sprache.setze("de")
        assert zeitplan.beschreibung(punkt) == \
            "zu um Sonnenuntergang, spätestens 22:00 an Schultagen"
        sprache.setze("en")
        assert zeitplan.beschreibung(punkt) == \
            "closed at sunset, no later than 22:00 on school days"
        # Eine Uhrzeit trägt im Deutschen „Uhr", im Englischen nicht.
        uhr = {**punkt, "ausloeser": "uhrzeit", "start": "08:30",
               "gilt": "immer", "spaet": "", "position": 100}
        assert zeitplan.beschreibung(uhr) == "open at 08:30"
        sprache.setze("de")
        assert zeitplan.beschreibung(uhr) == "auf um 08:30 Uhr"
    finally:
        sprache.setze("de")


def test_unbekannte_sprache_faellt_auf_deutsch_zurueck():
    """Eine halbfertige Übersetzung soll eine halbfertige Oberfläche ergeben,
    keine kaputte."""
    assert sprache.setze("kl-KL") == "de"
    assert sprache.setze("en-GB") == "en", "das Gebietsschema zählt nicht mit"
    assert sprache.setze(None) == "de"
    assert sprache.setze("") == "de"
    # Ein Schlüssel, den nur Deutsch kennt, kommt auf Englisch trotzdem an.
    sprache.TEXTE["de"]["probe.nur_deutsch"] = "nur hier"
    try:
        assert sprache.t("probe.nur_deutsch", sprache="en") == "nur hier"
    finally:
        del sprache.TEXTE["de"]["probe.nur_deutsch"]
        sprache.setze("de")


def test_beide_sprachen_kennen_dieselben_schluessel():
    """Sonst fällt eine Sprache stellenweise ins Deutsche zurück, ohne dass es
    jemandem auffällt – am wenigsten dem, der die Sprache nicht spricht."""
    deutsch = set(sprache.TEXTE["de"])
    for code, tabelle in sprache.TEXTE.items():
        fehlt = deutsch - set(tabelle)
        zuviel = set(tabelle) - deutsch
        assert not fehlt, f"{code}: es fehlen {sorted(fehlt)}"
        assert not zuviel, f"{code}: unbekannt sind {sorted(zuviel)}"


def test_platzhalter_stimmen_in_jeder_sprache_ueberein():
    """Eine Vorlage mit einem Platzhalter, den der Aufrufer nicht liefert,
    bliebe stumm – der Text käme unersetzt heraus."""
    import re
    for schluessel, deutsch in sprache.TEXTE["de"].items():
        erwartet = set(re.findall(r"\{(\w+)", deutsch))
        for code, tabelle in sprache.TEXTE.items():
            hier = set(re.findall(r"\{(\w+)", tabelle.get(schluessel, "")))
            assert hier == erwartet, f"{code}/{schluessel}: {hier} statt {erwartet}"


# ------------------------------------------------------------ Gruppen ----

def test_ein_rollo_gehoert_in_hoechstens_eine_gruppe():
    """Sonst hätte es zwei Zeitpläne, und welcher gilt, wäre Zufall der
    Speicherreihenfolge. Das ist keine Gruppierung mehr."""
    rollos = {"cover.a", "cover.b"}
    store.validate_gruppen([{"name": "Eins", "rollos": ["cover.a"]},
                            {"name": "Zwei", "rollos": ["cover.b"]}], rollos, set())
    try:
        store.validate_gruppen([{"name": "Eins", "rollos": ["cover.a"]},
                                {"name": "Zwei", "rollos": ["cover.a"]}], rollos, set())
    except store.ValidationError as err:
        assert "höchstens eine Gruppe" in str(err)
    else:
        raise AssertionError("doppelte Mitgliedschaft muss auffallen")


def test_gruppe_zeigt_nicht_ins_leere():
    """Eine Gruppe auf ein gelöschtes Rollo wäre still kaputt: Sie sähe
    vollständig aus und ließe eines aus."""
    for gruppe, stueck in (({"name": "G", "rollos": ["cover.weg"]}, "cover.weg"),
                           ({"name": "G", "rollos": [], "plan": "gibtsnicht"},
                            "gibtsnicht")):
        try:
            store.validate_gruppe(gruppe, {"cover.a"}, {"plan1"})
        except store.ValidationError as err:
            assert stueck in str(err)
        else:
            raise AssertionError(f"{stueck} hätte auffallen müssen")


def test_ueberfuehrung_schlaegt_die_etagen_vor_und_nimmt_nichts_weg():
    """Die Obergruppe kommt dazu, sie ersetzt nichts.

    Vorgeschlagen wird nach Etage – so führt Home Assistant die Bereiche, und
    so waren die Sammelautomationen geschnitten. Jedes Rollo behält seinen
    eigenen Zeitplan, und die Gruppen starten ohne eigenen: Die Überführung
    darf das Verhalten nicht ändern.
    """
    plaene = [{"id": "p1", "name": "Küche + Wohnzimmer", "zeitplan": []}]
    punkt = [{"ausloeser": "uhrzeit", "start": "07:00", "position": 100,
              "gilt": "immer", "tage": ["mon"], "versatz_min": 0,
              "frueh": "", "spaet": "", "wenn": []}]
    rollos = [
        {"entity_id": "cover.kueche", "plan": "p1", "zeitplan": [], "raum": "Küche"},
        {"entity_id": "cover.wz", "plan": "p1", "zeitplan": [], "raum": "Wohnzimmer"},
        {"entity_id": "cover.buero", "plan": "", "zeitplan": punkt, "raum": "Büro"},
        {"entity_id": "cover.schlaf1", "plan": "", "zeitplan": [], "raum": "Schlafzimmer"},
        {"entity_id": "cover.ohne", "plan": "", "zeitplan": [], "raum": ""},
    ]
    etagen = {"cover.kueche": "Erdgeschoss", "cover.wz": "Erdgeschoss",
              "cover.buero": "Obergeschoß", "cover.schlaf1": "Obergeschoß"}
    gruppen = store.gruppen_ableiten(rollos, plaene, {"cover.ohne": "Rollo Keller"}, etagen)
    nach_name = {g["name"]: g for g in gruppen}

    assert nach_name["Erdgeschoss"]["rollos"] == ["cover.kueche", "cover.wz"]
    assert nach_name["Obergeschoß"]["rollos"] == ["cover.buero", "cover.schlaf1"]
    # Ohne Etage tritt der Bereich ein, ohne Bereich der Name.
    assert "Rollo Keller" in nach_name
    # Keine Gruppe bringt einen eigenen Zeitplan mit – das Verhalten bleibt.
    assert all(g["plan"] == "" for g in gruppen)

    drin = [eid for g in gruppen for eid in g["rollos"]]
    assert sorted(drin) == sorted(r["entity_id"] for r in rollos)
    assert len(drin) == len(set(drin))


def _punkt(uhr, position, tage=None):
    return {"ausloeser": "uhrzeit", "start": uhr, "position": position,
            "gilt": "immer", "tage": tage or ["mon", "tue", "wed", "thu", "fri",
                                              "sat", "sun"],
            "versatz_min": 0, "frueh": "", "spaet": "", "wenn": []}


def test_die_gruppe_legt_punkte_dazu_statt_sie_zu_ersetzen():
    """Der Kern des Modells: Die Obergruppe kommt über das Rollo, nicht an
    seine Stelle. So lief früher „Rollo schliessen EG" neben den
    Einzelautomationen."""
    rollo = {"entity_id": "cover.a", "plan": "", "zeitplan": [_punkt("08:00", 100)]}
    plaene = {"g1": {"id": "g1", "name": "Erdgeschoss", "aktiv": True,
                     "zeitplan": [_punkt("22:00", 0)]}}
    gruppe = {"id": "x", "name": "Erdgeschoss", "plan": "g1", "aktiv": True,
              "rollos": ["cover.a"]}

    ohne, _ = regelung._plan_von(rollo, plaene, None)
    assert [p["start"] for p in ohne] == ["08:00"]

    mit, _ = regelung._plan_von(rollo, plaene, gruppe)
    assert [p["start"] for p in mit] == ["08:00", "22:00"], "beides, nicht entweder"

    # Eine abgeschaltete Gruppe legt nichts dazu …
    aus, _ = regelung._plan_von(rollo, plaene, {**gruppe, "aktiv": False})
    assert [p["start"] for p in aus] == ["08:00"]
    # … und ein abgeschalteter Gruppenzeitplan ebenso wenig.
    plaene["g1"]["aktiv"] = False
    still, _ = regelung._plan_von(rollo, plaene, gruppe)
    assert [p["start"] for p in still] == ["08:00"]


def test_gruppe_legt_auch_zu_einem_gemeinsamen_plan_dazu():
    """Ein Rollo an einem gemeinsamen Plan behält ihn – die Gruppe kommt
    obendrauf, nicht an seine Stelle."""
    rollo = {"entity_id": "cover.a", "plan": "p1", "zeitplan": []}
    plaene = {"p1": {"id": "p1", "name": "Küche + Wohnzimmer", "aktiv": True,
                     "zeitplan": [_punkt("06:30", 100)]},
              "g1": {"id": "g1", "name": "Erdgeschoss", "aktiv": True,
                     "zeitplan": [_punkt("22:00", 0)]}}
    gruppe = {"id": "x", "name": "Erdgeschoss", "plan": "g1", "aktiv": True,
              "rollos": ["cover.a"]}
    punkte, plan = regelung._plan_von(rollo, plaene, gruppe)
    assert [p["start"] for p in punkte] == ["06:30", "22:00"]
    assert plan["name"] == "Küche + Wohnzimmer", "der eigene Plan bleibt der eigene"


def test_gruppenschalter_gibt_frei_wie_frueher_eg_schliessen():
    """Steht der Schalter der Gruppe aus, fährt der Planer keines ihrer Rollos.

    Bisher hing so eine Freigabe als Bedingung an jedem einzelnen Schaltpunkt
    und war nur über Umwege zu erkennen.
    """
    rollo = {**store.STANDARD_ROLLO, "entity_id": "cover.a", "name": "Prüfrollo",
             "plan": "", "zeitplan": [_punkt("08:00", 100)]}
    gruppe = {"id": "x", "name": "Erdgeschoss", "plan": "", "aktiv": True,
              "schalter": "abc123", "rollos": ["cover.a"]}
    einst = store.validate_einstellungen(dict(store.STANDARD_EINSTELLUNGEN))
    lage = {"automatik": True, "rauch": False, "rauch_grund": "", "urlaub": False,
            "urlaub_seit": None, "simulation": {}, "fluchtweg": {},
            "zustaende": {store.EIGEN_PREFIX + "abc123": "off"}}
    state = {"rollos": {}}
    ergebnis = regelung._rollo_rechnen(
        rollo, einst, {"cover.a": _cover("cover.a", 0)}, state, None, None,
        datetime(2026, 8, 27, 9, 0), lage, {}, gruppe)
    assert ergebnis["zustand"] == "gesperrt"
    assert "nicht freigegeben" in ergebnis["begruendung"]

    lage["zustaende"][store.EIGEN_PREFIX + "abc123"] = "on"
    frei = regelung._rollo_rechnen(
        rollo, einst, {"cover.a": _cover("cover.a", 0)}, state, None, None,
        datetime(2026, 8, 27, 9, 0), lage, {}, gruppe)
    assert frei["zustand"] != "gesperrt"


def test_gruppen_ueberleben_das_laden_und_speichern():
    config = store._leer_config()
    assert config["gruppen"] == []


# ------------------------------------------------------- Trockenlauf ----

def _plan_rollo(eid, name="Prüfrollo"):
    tage = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    punkt = lambda uhr, pos: {"ausloeser": "uhrzeit", "start": uhr, "position": pos,
                              "gilt": "immer", "tage": tage, "versatz_min": 0,
                              "frueh": "", "spaet": "", "wenn": []}
    return {**store.STANDARD_ROLLO, "entity_id": eid, "name": name, "raum": "Prüfstand",
            "plan": "", "zeitplan": store.validate_zeitplan(
                [punkt("20:00", 0), punkt("08:00", 100)])}


def _takt(config, state, index, jetzt):
    import regelung as r
    echt = r._jetzt
    r._jetzt = lambda: jetzt
    ha_api.available = lambda: True
    ha_api.ist_bereit = lambda: True
    ha_api.get_states = lambda: list(index.values())
    try:
        return r.takt(config, state, lambda *a, **k: None)
    finally:
        r._jetzt = echt


def test_trockenlauf_erfindet_keinen_handbetrieb():
    """Der Fehler, der den Trockenlauf wertlos machte.

    Im Trockenlauf schickt der Planer nichts los. Merkte er sich trotzdem ein
    „Ziel“, stünde das Rollo fünf Minuten später woanders als dieses Ziel – und
    die Handbetriebserkennung hielte das für einen Griff ans Rollo. Der Planer
    meldete dann „Handbetrieb“ für ein Rollo, das niemand angefasst hat, und
    legte sich selbst zwölf Stunden stumm.
    """
    config = {"einstellungen": store.validate_einstellungen(
                  {**store.STANDARD_EINSTELLUNGEN, "trockenlauf": True}),
              "plaene": [], "rollos": [_plan_rollo("cover.a")]}
    # So, als wäre vor dem Trockenlauf einmal wirklich gefahren worden.
    state = {"rollos": {"cover.a": {"ziel": 100,
                                    "gesetzt_am": "2026-08-27T19:00:00"}}}
    index = {"cover.a": _cover("cover.a", 100)}      # bleibt stur offen

    with _Fahrten() as f:
        for minute in (0, 5, 30, 90):
            bericht = _takt(config, state, index,
                            datetime(2026, 8, 27, 20, 0) + timedelta(minutes=minute))
            assert bericht["rollos"][0]["zustand"] != "manuell", \
                f"nach {minute} min fälschlich Handbetrieb"
    assert f.befehle == [], "im Trockenlauf darf kein Befehl hinausgehen"
    assert state["rollos"]["cover.a"].get("manuell_bis") is None
    # Und das gemerkte Ziel bleibt das zuletzt *wirklich* gefahrene.
    assert state["rollos"]["cover.a"]["ziel"] == 100


def test_beobachten_erfindet_ebenfalls_keinen_handbetrieb():
    config = {"einstellungen": store.validate_einstellungen(
                  {**store.STANDARD_EINSTELLUNGEN, "trockenlauf": False}),
              "plaene": [], "rollos": [{**_plan_rollo("cover.a"),
                                        "betriebsart": "beobachten"}]}
    state = {"rollos": {"cover.a": {"ziel": 100,
                                    "gesetzt_am": "2026-08-27T19:00:00"}}}
    index = {"cover.a": _cover("cover.a", 100)}
    with _Fahrten() as f:
        for minute in (0, 5, 30):
            bericht = _takt(config, state, index,
                            datetime(2026, 8, 27, 20, 0) + timedelta(minutes=minute))
            assert bericht["rollos"][0]["zustand"] != "manuell"
    assert f.befehle == []


def test_nach_dem_trockenlauf_faehrt_nur_das_falsch_stehende():
    """Beim Ausschalten wird der Merkposten verworfen und der Plan neu
    durchgesetzt – aber ein Rollo, das schon richtig steht, fährt nicht."""
    config = {"einstellungen": store.validate_einstellungen(
                  {**store.STANDARD_EINSTELLUNGEN, "trockenlauf": True}),
              "plaene": [], "rollos": [_plan_rollo("cover.falsch", "Falsch"),
                                       _plan_rollo("cover.richtig", "Richtig")]}
    index = {"cover.falsch": _cover("cover.falsch", 100),
             "cover.richtig": _cover("cover.richtig", 0)}
    state = {"rollos": {}}
    with _Fahrten() as f:
        _takt(config, state, index, datetime(2026, 8, 27, 20, 0))
        assert f.befehle == []

        config["einstellungen"]["trockenlauf"] = False       # wie _durchsetzen()
        for daten in state["rollos"].values():
            daten["letzter_punkt"] = None
            daten["manuell_bis"] = None
        _takt(config, state, index, datetime(2026, 8, 27, 20, 1))
    assert f.befehle == [("cover.falsch", 0)]


# ------------------------------------------------- Fluchtweg bei Rauch ----

def _rollo(eid, **rest):
    return {**store.STANDARD_ROLLO, "entity_id": eid,
            "name": rest.pop("name", eid.split(".")[-1]), **rest}


def _cover(eid, position):
    return {"entity_id": eid, "state": "open" if position else "closed",
            "attributes": {"current_position": position}}


class _Fahrten:
    """Nimmt die Fahrbefehle auf, statt sie an Home Assistant zu schicken."""

    def __enter__(self):
        self.befehle = []
        self._echt = ha_api.set_position
        ha_api.set_position = lambda eid, ziel, zustand=None: (
            self.befehle.append((eid, ziel)) or True)
        return self

    def __exit__(self, *_):
        ha_api.set_position = self._echt
        return False


def _lage(config, state, index, jetzt, rauch=True):
    return regelung._fluchtweg(config, config["einstellungen"], index, state,
                               jetzt, rauch)


def test_fluchtweg_oeffnet_auch_was_vom_zeitplan_ausgenommen_ist():
    """Der Sinn der Sache: Im Brandfall gibt es keine Sonderfälle.

    Das Schlafzimmer hat keinen Zeitplan und steht auf „von Hand“, ein anderes
    Rollo ist gesperrt – aufgehen müssen sie trotzdem beide.
    """
    config = {"einstellungen": store.validate_einstellungen(
                  {**store.STANDARD_EINSTELLUNGEN, "automatik": False,
                   "trockenlauf": False}),
              "rollos": [_rollo("cover.a", betriebsart="von_hand"),
                         _rollo("cover.b", betriebsart="beobachten"),
                         _rollo("cover.c")]}
    index = {eid: _cover(eid, 0) for eid in ("cover.a", "cover.b", "cover.c")}
    state = {}
    with _Fahrten() as f:
        bericht = _lage(config, state, index, datetime(2026, 8, 27, 3, 0))
    assert [eid for eid, _ in f.befehle] == ["cover.a", "cover.b", "cover.c"]
    assert {ziel for _, ziel in f.befehle} == {100}
    assert bericht["aktiv"] and bericht["neu"]


def test_fluchtweg_faehrt_nicht_zweimal_und_nicht_endlos():
    """Flanke statt Pegel – und ein Ende, wenn es nichts mehr bringt.

    Ein Rollladen fährt auf jeden Befehl. Solange die Fahrzeit läuft, darf kein
    zweiter kommen; danach wird nachgefasst, aber nur begrenzt oft.
    """
    config = {"einstellungen": store.validate_einstellungen(
                  {**store.STANDARD_EINSTELLUNGEN, "trockenlauf": False}),
              "rollos": [_rollo("cover.a")]}
    index = {"cover.a": _cover("cover.a", 0)}      # bleibt stur zu
    state = {}
    start = datetime(2026, 8, 27, 3, 0)
    with _Fahrten() as f:
        _lage(config, state, index, start)
        assert len(f.befehle) == 1
        _lage(config, state, index, start + timedelta(minutes=1))
        assert len(f.befehle) == 1, "innerhalb der Fahrzeit kein zweiter Befehl"
        for n in range(1, 8):
            _lage(config, state, index,
                  start + timedelta(minutes=n * (regelung.FAHRZEIT_MIN + 1)))
    grenze = config["einstellungen"]["rauchsperre"]["fluchtweg_versuche"]
    assert len(f.befehle) == grenze
    bericht = _lage(config, state, index, start + timedelta(hours=1))
    assert bericht["aufgegeben"] == ["a"]


def test_fluchtweg_laesst_offene_und_ausgenommene_rollos_in_ruhe():
    config = {"einstellungen": store.validate_einstellungen(
                  {**store.STANDARD_EINSTELLUNGEN, "trockenlauf": False}),
              "rollos": [_rollo("cover.offen"),
                         _rollo("cover.aus", fluchtweg=False),
                         _rollo("cover.zu")]}
    index = {"cover.offen": _cover("cover.offen", 100),
             "cover.aus": _cover("cover.aus", 0),
             "cover.zu": _cover("cover.zu", 0)}
    with _Fahrten() as f:
        bericht = _lage(config, {}, index, datetime(2026, 8, 27, 3, 0))
    assert [eid for eid, _ in f.befehle] == ["cover.zu"]
    assert bericht["offen"] == ["offen"] and bericht["uebergangen"] == ["aus"]


def test_fluchtweg_haelt_den_trockenlauf_ein():
    """Sonst machte ein Add-on im Probebetrieb nachts das Haus auf."""
    config = {"einstellungen": store.validate_einstellungen(
                  {**store.STANDARD_EINSTELLUNGEN, "trockenlauf": True}),
              "rollos": [_rollo("cover.a")]}
    with _Fahrten() as f:
        bericht = _lage(config, {}, {"cover.a": _cover("cover.a", 0)},
                        datetime(2026, 8, 27, 3, 0))
    assert f.befehle == []
    assert bericht["gefahren"] == ["a"]      # gemeldet wird trotzdem


def test_entwarnung_gibt_die_versuche_wieder_frei():
    """Sonst hätte ein einmal blockiertes Rollo beim nächsten Brand keinen
    Versuch mehr frei."""
    config = {"einstellungen": store.validate_einstellungen(
                  {**store.STANDARD_EINSTELLUNGEN, "trockenlauf": False}),
              "rollos": [_rollo("cover.a")]}
    index = {"cover.a": _cover("cover.a", 0)}
    state = {}
    start = datetime(2026, 8, 27, 3, 0)
    with _Fahrten() as f:
        _lage(config, state, index, start)
        _lage(config, state, index, start + timedelta(minutes=10), rauch=False)
        assert state["fluchtweg"]["seit"] is None
        _lage(config, state, index, start + timedelta(minutes=11))
    assert len(f.befehle) == 2


def test_nachlauf_faehrt_nicht_mehr_auf():
    """Nach der Entwarnung gilt die Sperre weiter, die Freigabe aber nicht.

    Sonst führe der Planer eine halbe Stunde lang gegen jeden an, der hinter
    dem abgezogenen Alarm wieder zumachen will.
    """
    config = {"einstellungen": store.validate_einstellungen(
                  {**store.STANDARD_EINSTELLUNGEN, "trockenlauf": False}),
              "rollos": [_rollo("cover.a")]}
    index = {"cover.a": _cover("cover.a", 0)}
    state = {}
    start = datetime(2026, 8, 27, 3, 0)
    with _Fahrten() as f:
        regelung._fluchtweg(config, config["einstellungen"], index, state,
                            start, True, akut=True)
        assert len(f.befehle) == 1
        bericht = regelung._fluchtweg(
            config, config["einstellungen"], index, state,
            start + timedelta(minutes=20), True, akut=False)
    assert len(f.befehle) == 1
    assert bericht["nachlauf"] == ["a"] and not bericht["neu"]


def test_rauchsperre_trennt_akut_von_nachlauf():
    einstellungen = store.validate_einstellungen(dict(store.STANDARD_EINSTELLUNGEN))
    index = {"binary_sensor.rm_flur_rauch": {
        "entity_id": "binary_sensor.rm_flur_rauch", "state": "on",
        "attributes": {"friendly_name": "RM Flur", "device_class": "smoke"}}}
    state = {}
    jetzt = datetime(2026, 8, 27, 3, 0)
    sperre, grund, akut, orte = regelung._rauchsperre(
        einstellungen, index, state, jetzt)
    assert (sperre, akut, orte) == (True, True, "RM Flur")
    assert grund == "Rauchmelder: RM Flur"
    index["binary_sensor.rm_flur_rauch"]["state"] = "off"
    sperre, grund, akut, orte = regelung._rauchsperre(
        einstellungen, index, state, jetzt + timedelta(minutes=5))
    assert sperre and not akut and "Nachlauf" in grund
    assert orte == "RM Flur", "der Ort muss den Nachlauf überleben"


def test_der_eigene_melder_zaehlt_nicht_als_rauchmelder():
    """Sonst hielte sich der erste Alarm für immer.

    Das Add-on legt selbst einen `binary_sensor` „Rauchsperre" an. Der geht bei
    Alarm an – und trüge er zur Erkennung bei, bliebe der Alarm nach der
    Entwarnung stehen, weil der eigene Melder ihn am Leben hielte. Der Planer
    führe nie wieder einen Zeitplan aus.
    """
    einstellungen = store.validate_einstellungen(dict(store.STANDARD_EINSTELLUNGEN))
    def melder(eid, name, an, klasse):
        return {"entity_id": eid, "state": "on" if an else "off",
                "attributes": {"friendly_name": name, "device_class": klasse}}
    echt = melder("binary_sensor.rm_flur_rauch", "RM Flur", True, "smoke")
    eigen = melder("binary_sensor.rolloplaner_rauchsperre",
                   "Rolloplaner Rollos Rauchsperre", False, "safety")
    index = {m["entity_id"]: m for m in (echt, eigen)}
    state = {}
    start = datetime(2026, 8, 27, 3, 0)

    sperre, _, akut, _ = regelung._rauchsperre(einstellungen, index, state, start)
    assert sperre and akut
    echt["state"] = "off"
    eigen["state"] = "on"                    # so setzt MQTT ihn nach dem Alarm
    sperre, _, akut, _ = regelung._rauchsperre(
        einstellungen, index, state, start + timedelta(minutes=1))
    assert sperre and not akut, "Nachlauf, aber nicht mehr akut"
    sperre, _, akut, _ = regelung._rauchsperre(
        einstellungen, index, state, start + timedelta(minutes=40))
    assert not sperre and not akut, "nach dem Nachlauf muss der Alarm vorbei sein"

    # Auch eine ausdrückliche Auswahl darf sich nicht selbst enthalten.
    eigene_wahl = store.validate_einstellungen(
        {**store.STANDARD_EINSTELLUNGEN,
         "rauchsperre": {**store.STANDARD_EINSTELLUNGEN["rauchsperre"],
                         "melder": ["binary_sensor.rolloplaner_rauchsperre"]}})
    sperre, _, akut, _ = regelung._rauchsperre(
        eigene_wahl, index, {}, start + timedelta(minutes=41))
    assert not sperre and not akut


def test_melderort_nimmt_den_bereich_und_kuerzt_den_namen():
    """Im Ernstfall zählt der Ort, nicht die Gerätebezeichnung."""
    index = {"binary_sensor.rm_flur_og_rauch": {
        "entity_id": "binary_sensor.rm_flur_og_rauch",
        "attributes": {"friendly_name": "RM Flur OG Alarmstatus"}}}
    # Mit Bereich gewinnt der Bereich …
    assert regelung._melderort("binary_sensor.rm_flur_og_rauch", index,
                               {"binary_sensor.rm_flur_og_rauch": "Flur 1.OG"}) == "Flur 1.OG"
    # … ohne Bereich fällt der Ballast aus dem Namen.
    assert regelung._melderort("binary_sensor.rm_flur_og_rauch", index, {}) == "RM Flur OG"


def test_meldeweg_faellt_auf_den_waechter_zurueck():
    """Ein Brandalarm darf nie stumm bleiben.

    Ein eigener Weg gewinnt; ist keiner eingetragen, gilt der des Wächters –
    lieber die falsche Zustellart als gar keine Meldung.
    """
    waechter = {"wachhund": {"melden_an": ["notify.handy"]}}
    assert store.rauch_meldewege(waechter) == ["notify.handy"]
    eigen = {**waechter, "rauchsperre": {"melden_an": ["notify.laut", "notify.sirene"]}}
    assert store.rauch_meldewege(eigen) == ["notify.laut", "notify.sirene"]
    assert store.rauch_meldewege({}) == []


def test_alarm_wird_einmal_gemeldet_und_beim_naechsten_wieder():
    """Nicht bei jedem Takt – aber auch nicht nur einmal im Leben.

    Wer während eines Brandes im Minutentakt meldet, begräbt die eine
    Nachricht, auf die es ankommt. Wer den Merkposten nach der Entwarnung nicht
    zurücksetzt, meldet den nächsten Brand gar nicht.
    """
    config = {"einstellungen": store.validate_einstellungen(
                  {**store.STANDARD_EINSTELLUNGEN, "trockenlauf": True}),
              "plaene": [], "rollos": [_rollo("cover.a")]}
    melder = {"entity_id": "binary_sensor.rm_flur_rauch", "state": "off",
              "attributes": {"friendly_name": "RM Flur", "device_class": "smoke"}}
    index = {"cover.a": _cover("cover.a", 0), melder["entity_id"]: melder}
    state = {"rollos": {}}
    start = datetime(2026, 8, 27, 3, 0)

    def takt(minute):
        return _takt(config, state, index, start + timedelta(minutes=minute))

    assert takt(0)["rauch_neu"] is False           # noch kein Alarm
    melder["state"] = "on"
    assert takt(1)["rauch_neu"] is True            # Alarm – melden
    assert takt(2)["rauch_neu"] is False           # derselbe Alarm – schweigen
    melder["state"] = "off"
    assert takt(3)["rauch_neu"] is False           # Nachlauf – schweigen
    b = takt(40)                                   # Nachlauf vorbei
    assert not b["rauch"] and b["rauch_neu"] is False
    melder["state"] = "on"
    assert takt(41)["rauch_neu"] is True           # neuer Alarm – wieder melden


def test_fluchtweg_abschaltbar_und_dann_nur_sperre():
    config = {"einstellungen": store.validate_einstellungen(
                  {**store.STANDARD_EINSTELLUNGEN, "trockenlauf": False,
                   "rauchsperre": {**store.STANDARD_EINSTELLUNGEN["rauchsperre"],
                                   "fluchtweg": False}}),
              "rollos": [_rollo("cover.a")]}
    with _Fahrten() as f:
        bericht = _lage(config, {}, {"cover.a": _cover("cover.a", 0)},
                        datetime(2026, 8, 27, 3, 0))
    assert f.befehle == [] and not bericht["aktiv"]


def test_rauch_steht_ueber_der_automatik():
    """Die Regelkette muss den Fluchtweg auch dann melden, wenn die Automatik
    aus ist – sonst stünde in der Karte „Automatik aus“, während das Haus
    brennt."""
    rollo = _rollo("cover.a", betriebsart="von_hand")
    lage = {"automatik": False, "rauch": True, "rauch_grund": "Rauchmelder: Flur",
            "fluchtweg": {"aktiv": True}, "zustaende": {}, "urlaub": False,
            "urlaub_seit": None, "simulation": {}}
    ergebnis = regelung._rollo_rechnen(
        rollo, store.validate_einstellungen(dict(store.STANDARD_EINSTELLUNGEN)),
        {"cover.a": _cover("cover.a", 0)}, {"rollos": {}}, None, None,
        datetime(2026, 8, 27, 3, 0), lage, {})
    assert ergebnis["zustand"] == "fluchtweg"
    assert "Flur" in ergebnis["begruendung"]


if __name__ == "__main__":
    fehler = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
            print(f"  ok   {name}")
        except Exception as err:  # noqa: BLE001
            fehler += 1
            print(f"  FEHL {name}: {err}")
    print(f"\n{fehler} Fehler")
    sys.exit(1 if fehler else 0)
