"""Prüfungen der Rechenkerne – ohne Home Assistant, ohne Netz.

Aufruf:  python3 -m pytest rolloplaner/tests/ -q
oder:    python3 rolloplaner/tests/test_logik.py

Geprüft wird, was beim Bauen tatsächlich schiefging: vertauschter Auf- und
Untergang, eine Streuung, die nur in eine Richtung wirkt, ein Schaltpunkt, der
als erledigt gilt, obwohl er nie ausgeführt wurde.
"""
import os
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
os.environ.setdefault("TZ", "Europe/Berlin")
try:
    import time as _time
    _time.tzset()
except AttributeError:  # pragma: no cover – Windows
    pass

import sonne          # noqa: E402
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


def test_freigabe_wird_nur_hochgezogen_wenn_alle_sie_teilen():
    gemeinsam = {"zeitplan": [
        {"wenn": [{"entity": "input_boolean.a", "wert": "on"}], "position": 100},
        {"wenn": [{"entity": "input_boolean.a", "wert": "on"}], "position": 0}],
        "freigabe_entity": ""}
    uebernahme._freigabe_hochziehen(gemeinsam)
    assert gemeinsam["freigabe_entity"] == "input_boolean.a"
    assert gemeinsam["zeitplan"][0]["wenn"] == []

    getrennt = {"zeitplan": [
        {"wenn": [{"entity": "input_boolean.oeffner", "wert": "on"}], "position": 100},
        {"wenn": [{"entity": "input_boolean.schliesser", "wert": "on"}], "position": 0}],
        "freigabe_entity": ""}
    uebernahme._freigabe_hochziehen(getrennt)
    assert getrennt["freigabe_entity"] == ""
    assert getrennt["zeitplan"][0]["wenn"]


# ------------------------------------------------------------------ Store ----

def test_raum_ohne_ausrichtung_beschattet_nicht():
    raum = store.validate_raum({"name": "Test", "beschattung": True, "ausrichtung": None})
    assert raum["beschattung"] is False


def test_himmelsrichtung_als_wort():
    raum = store.validate_raum({"name": "Test", "ausrichtung": "sw"})
    assert raum["ausrichtung"] == 225


def test_offen_muss_ueber_zu_liegen():
    try:
        store.validate_raum({"name": "Test", "position_offen": 0, "position_zu": 100})
    except store.ValidationError:
        return
    raise AssertionError("verdrehte Stellungen hätten auffallen müssen")


def test_uhrzeit_punkt_verliert_die_klammer():
    """Bei fester Uhrzeit wären „frühestens“/„spätestens“ sinnlos und nur
    verwirrend."""
    plan = store.validate_zeitplan([{"ausloeser": "uhrzeit", "start": "07:00",
                                     "frueh": "06:00", "spaet": "08:00",
                                     "position": 100, "tage": ["mon"]}])
    assert plan[0]["frueh"] == "" and plan[0]["spaet"] == ""


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
