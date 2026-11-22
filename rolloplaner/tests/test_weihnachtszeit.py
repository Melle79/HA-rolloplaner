"""Prüfungen für 3.0: Weihnachtszeit und „es ändert sich nichts“.

Aufruf:  python3 rolloplaner/tests/test_weihnachtszeit.py

Zwei Dinge sind hier zu beweisen. Erstens: Wer auf 3.0 aktualisiert, ohne die
Weihnachtszeit einzurichten, bekommt **auf die Minute** dieselben Fahrten wie
mit 2.26. Verglichen wird gegen eine eingefrorene Kopie des alten
Zeitplanmoduls (``fixtures/zeitplan_2_26.py``) mit einer echten, anonymisierten
Anlage (``fixtures/anlage.json``: zehn Rollos, zwei gemeinsame und drei eigene
Pläne, acht Schalter, die Terrassentür mit ihrem 24-Uhr-Modus).

Zweitens: Die Weihnachtszeit tut, was sie verspricht – und die Lichter
schalten auf der Flanke, nicht in jedem Takt.
"""
import importlib.util
import json
import os
import sys
from datetime import date, datetime, timedelta

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "..", "backend"))
os.environ.setdefault("TZ", "Europe/Berlin")
try:
    import time as _time
    _time.tzset()
except AttributeError:  # pragma: no cover – Windows
    pass

import ha_api       # noqa: E402
import programme    # noqa: E402
import regelung     # noqa: E402
import sonne        # noqa: E402
import store        # noqa: E402
import zeitplan     # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "zeitplan_2_26", os.path.join(HIER, "fixtures", "zeitplan_2_26.py"))
zeitplan_alt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(zeitplan_alt)

LAT, LON = 48.07274558526573, 11.689136624336243

with open(os.path.join(HIER, "fixtures", "anlage.json"), encoding="utf-8") as _f:
    ANLAGE = json.load(_f)

EG = ["cover.rollo_2", "cover.rollo_9", "cover.rollo_10"]   # gemeinsamer Plan 1
TUER = "cover.rollo_8"                                       # eigener Plan, 24 Uhr
KINDER = ["cover.rollo_3", "cover.rollo_4", "cover.rollo_5"]


def _config(weihnacht=None):
    einst = dict(store.STANDARD_EINSTELLUNGEN)
    einst["eigene_schalter"] = ANLAGE["schalter"]
    einst["trockenlauf"] = False        # die Anlage läuft scharf
    if weihnacht is not None:
        einst["weihnachtszeit"] = {**programme.STANDARD_WEIHNACHTSZEIT, **weihnacht}
    einst = store.validate_einstellungen(einst)
    return {"einstellungen": einst,
            "plaene": [store._merge(store.STANDARD_PLAN, p) for p in ANLAGE["plaene"]],
            "rollos": [store._merge(store.STANDARD_ROLLO, r) for r in ANLAGE["rollos"]],
            "gruppen": [store._merge(store.STANDARD_GRUPPE, g) for g in ANLAGE["gruppen"]]}


def _sonnenstand():
    return sonne.Sonnenstand(LAT, LON)


def _zustaende(config):
    return regelung.eigene_zustaende(config["einstellungen"], {})


def _lage(config, hand=None, fb=None):
    cfg = config["einstellungen"]["weihnachtszeit"]
    aktiv_am = lambda t: programme.aktiv_am(cfg, t, hand)  # noqa: E731
    return {"weihnachtszeit": {"aktiv_am": aktiv_am, "heute": None, "hand": hand, "fb": fb or {}},
            "zustaende": _zustaende(config)}


def _punkte(config, rollo):
    plaene = {p["id"]: p for p in config["plaene"]}
    return regelung._plan_von(rollo, plaene, None)[0]


def _kalender(frei):
    verlauf = {(date(2026, 11, 1) + timedelta(days=n)).isoformat(): frei for n in range(120)}
    return zeitplan.Schulkalender(frei, frei, verlauf)


def _schritte(von: date, tage: int, minuten: int = 10):
    t = datetime.combine(von, datetime.min.time())
    for _ in range(tage * 24 * 60 // minuten):
        yield t
        t += timedelta(minutes=minuten)


def _vergleich(config, frei, von, tage):
    """Alt gegen neu: derselbe zuletzt fällige Punkt zu jeder Zeit."""
    s = _sonnenstand()
    lage = _lage(config)
    kal = _kalender(frei)
    abweichungen = []
    for rollo in config["rollos"]:
        if rollo["betriebsart"] == "von_hand":
            continue
        punkte = _punkte(config, rollo)
        programm = regelung._programm_fuer(rollo, config["einstellungen"], lage, s, kal, punkte)
        for jetzt in _schritte(von, tage):
            alt = zeitplan_alt.letzter_zeitpunkt(punkte, jetzt, kal, s, None, lage["zustaende"])
            neu = zeitplan.letzter_zeitpunkt(punkte, jetzt, kal, s, None, lage["zustaende"],
                                             programm)
            a = (alt[0], alt[1]["position"]) if alt else None
            n = (neu[0], neu[1]["position"]) if neu else None
            if a != n:
                abweichungen.append((rollo["entity_id"], jetzt, a, n))
    return abweichungen


# ------------------------------------------------- Es ändert sich nichts ----

def test_ohne_weihnachtszeit_dieselben_fahrten_wie_2_26():
    """Die Übernahme: Nichts eingerichtet → jede Minute wie bisher."""
    config = _config()
    for frei in (False, True):
        abw = _vergleich(config, frei, date(2026, 11, 23), 50)
        assert not abw, abw[:3]


def test_eingeschaltet_aber_kein_rollo_beteiligt_aendert_nichts():
    """Programm an, alle Rollos auf „normaler Plan“: auch dann wie bisher."""
    config = _config({"aktiv": True, "lichter": ["light.kette"]})
    for frei in (False, True):
        abw = _vergleich(config, frei, date(2026, 12, 1), 10)
        assert not abw, abw[:3]


def test_terrassentuer_behaelt_den_24_uhr_modus():
    config = _config()
    s = _sonnenstand()
    tuer = next(r for r in config["rollos"] if r["entity_id"] == TUER)
    ablauf = zeitplan.tagesablauf(_punkte(config, tuer), date(2026, 12, 1), _kalender(False),
                                  s, _zustaende(config))
    zeiten = [(p["zeit"], p["position"]) for p in ablauf["punkte"]]
    assert ("00:00", 0) in zeiten and ("06:30", 100) in zeiten, zeiten


# --------------------------------------------------------- Zeitraum ----

def test_erster_advent():
    assert programme.erster_advent(2026) == date(2026, 11, 29)
    assert programme.erster_advent(2027) == date(2027, 11, 28)
    assert programme.erster_advent(2028) == date(2028, 12, 3)   # 24.12. ist Sonntag
    assert programme.erster_advent(2025) == date(2025, 11, 30)


def test_zeitraum_advent_bis_dreikoenig():
    cfg = dict(programme.STANDARD_WEIHNACHTSZEIT)
    assert not programme.im_zeitraum(cfg, date(2026, 11, 28))
    assert programme.im_zeitraum(cfg, date(2026, 11, 29))
    assert programme.im_zeitraum(cfg, date(2026, 12, 31))
    assert programme.im_zeitraum(cfg, date(2027, 1, 6))
    assert not programme.im_zeitraum(cfg, date(2027, 1, 7))
    assert not programme.im_zeitraum(cfg, date(2027, 7, 1))


def test_fester_zeitraum_ueber_neujahr():
    cfg = {**programme.STANDARD_WEIHNACHTSZEIT, "zeitraum": "fest", "von": "12-10", "bis": "01-02"}
    assert not programme.im_zeitraum(cfg, date(2026, 12, 9))
    assert programme.im_zeitraum(cfg, date(2026, 12, 10))
    assert programme.im_zeitraum(cfg, date(2027, 1, 2))
    assert not programme.im_zeitraum(cfg, date(2027, 1, 3))


def test_von_hand_gilt_bis_zur_naechsten_grenze():
    cfg = {**programme.STANDARD_WEIHNACHTSZEIT, "aktiv": True}
    grenze = programme.naechste_grenze(cfg, date(2027, 1, 3))
    assert grenze == date(2027, 1, 7)
    hand = {"wert": "off", "bis": grenze.isoformat()}
    assert not programme.aktiv_am(cfg, date(2027, 1, 3), hand)
    assert not programme.aktiv_am(cfg, date(2027, 1, 6), hand)
    # nächstes Jahr wieder von selbst
    assert programme.aktiv_am(cfg, date(2027, 11, 28), hand)


def test_nicht_eingerichtet_laeuft_nur_von_hand():
    cfg = dict(programme.STANDARD_WEIHNACHTSZEIT)
    assert not programme.aktiv_am(cfg, date(2026, 12, 1), None)
    hand = {"wert": "on", "bis": "2027-01-07"}
    assert programme.aktiv_am(cfg, date(2026, 12, 1), hand)


# ------------------------------------------------------- Der Abend ----

STARTWERTE = {"aktiv": True, "lichter": ["light.kette", "switch.terrasse"],
        "rollos": {EG[0]: 40, EG[1]: 40, EG[2]: 40, TUER: "offen"}}


def _ablauf(config, eid, tag, frei=False, schalter=None, fb=None):
    s = _sonnenstand()
    rollo = next(r for r in config["rollos"] if r["entity_id"] == eid)
    lage = _lage(config, fb=fb)
    lage["zustaende"].update(schalter or {})
    punkte, kal = _punkte(config, rollo), _kalender(frei)
    return [(p["zeit"], p["position"]) for p in zeitplan.tagesablauf(
        punkte, tag, kal, s, lage["zustaende"],
        regelung._programm_fuer(rollo, config["einstellungen"], lage, s, kal, punkte))["punkte"]]


def test_zwischenstellung_statt_zu_bei_sonnenuntergang():
    config = _config(STARTWERTE)
    tag = date(2026, 12, 1)
    untergang = _sonnenstand().untergang(tag).strftime("%H:%M")
    for eid in EG:
        assert _ablauf(config, eid, tag) == [("06:00", 40), ("06:30", 100),
                                             (untergang, 40), ("22:30", 0)], eid


def test_schulfrei_morgens_halb_bis_zehn():
    config = _config(STARTWERTE)
    zeiten = _ablauf(config, EG[0], date(2026, 12, 26), frei=True)
    assert zeiten[:2] == [("09:30", 40), ("10:00", 100)], zeiten


AUSWAHL = "rolloplaner:s3"   # Terrassentür schließen: normal / 24 Uhr / aus


def test_terrassentuer_24_uhr_schliesst_weiter_um_mitternacht():
    """Die Weihnachtszeit darf das Schließen nur hinauszögern, nie vorziehen."""
    mit, ohne = _config(STARTWERTE), _config()
    tag = date(2026, 12, 1)
    zeiten = _ablauf(mit, TUER, tag, schalter={AUSWAHL: "24 Uhr"})
    assert zeiten == _ablauf(ohne, TUER, tag, schalter={AUSWAHL: "24 Uhr"}), zeiten
    assert ("00:00", 0) in zeiten and not [z for z in zeiten if z[0] == "22:30"], zeiten


def test_terrassentuer_normal_bleibt_offen_bis_licht_aus():
    config = _config(STARTWERTE)
    zeiten = _ablauf(config, TUER, date(2026, 12, 1), schalter={AUSWAHL: "normal"})
    assert zeiten == [("06:30", 100), ("22:30", 0)], zeiten


def test_terrassentuer_aus_wird_nie_geschlossen():
    mit, ohne = _config(STARTWERTE), _config()
    tag = date(2026, 12, 1)
    zeiten = _ablauf(mit, TUER, tag, schalter={AUSWAHL: "aus"})
    assert zeiten == _ablauf(ohne, TUER, tag, schalter={AUSWAHL: "aus"}), zeiten
    assert not [z for z in zeiten if z[1] < 100], zeiten


def test_zwischenstellung_zieht_kein_offenes_rollo_zu():
    """Lässt der Plan ein Rollo abends offen (Schließen abgeschaltet), bleibt es
    offen – die Zwischenstellung hebt nur an, sie senkt nie."""
    mit, ohne = _config(STARTWERTE), _config()
    tag = date(2026, 12, 1)
    aus = {"rolloplaner:s2": "off"}          # „EG schließen“ aus
    assert _ablauf(mit, EG[0], tag, schalter=aus) == _ablauf(ohne, EG[0], tag, schalter=aus)


def test_kinderzimmer_unberuehrt_in_der_weihnachtszeit():
    mit, ohne = _config(STARTWERTE), _config()
    for eid in KINDER:
        assert _ablauf(mit, eid, date(2026, 12, 1)) == _ablauf(ohne, eid, date(2026, 12, 1)), eid


def test_ausserhalb_des_zeitraums_wie_immer():
    mit, ohne = _config(STARTWERTE), _config()
    for eid in EG + [TUER]:
        assert _ablauf(mit, eid, date(2026, 11, 28)) == _ablauf(ohne, eid, date(2026, 11, 28))
        assert _ablauf(mit, eid, date(2027, 1, 7)) == _ablauf(ohne, eid, date(2027, 1, 7))


def test_ohne_vorlauf_morgens_nichts():
    config = _config({**STARTWERTE, "morgens_vorlauf": 0})
    zeiten = _ablauf(config, EG[0], date(2026, 12, 1))
    assert zeiten[0] == ("06:30", 100), zeiten


def test_licht_aus_nach_mitternacht():
    config = _config({**STARTWERTE, "licht_aus": "00:30"})
    zeiten = _ablauf(config, EG[0], date(2026, 12, 2))
    assert zeiten[0] == ("00:30", 0), zeiten


# ------------------------------------------------------- Abläufe (3.2) ----

def _config_ablaeufe(ablaeufe):
    config = _config()
    config["einstellungen"]["weihnachtszeit"] = store.validate_einstellungen(
        {"weihnachtszeit": {"aktiv": True, "ablaeufe": ablaeufe}})["weihnachtszeit"]
    return config


KINDER_ABLAUF = {"name": "Kinder", "licht_aus": "20:30", "licht_aus_vor_schulfrei": "22:00",
                 "morgens_vorlauf": 0, "lichter": ["light.stern"],
                 "rollos": {KINDER[0]: 40, KINDER[1]: 40, KINDER[2]: 40}}


def test_alte_einstellung_wird_zum_ablauf_erdgeschoss():
    """3.1 → 3.2: dieselben Fahrten, ob flach oder als Ablauf gespeichert."""
    flach = _config(STARTWERTE)
    migriert = _config()
    migriert["einstellungen"]["weihnachtszeit"] = store.validate_einstellungen(
        {"weihnachtszeit": STARTWERTE})["weihnachtszeit"]
    assert migriert["einstellungen"]["weihnachtszeit"]["ablaeufe"][0]["name"] == "Erdgeschoss"
    assert "lichter" not in migriert["einstellungen"]["weihnachtszeit"]
    for eid in EG + [TUER] + KINDER:
        for tag in (date(2026, 12, 1), date(2026, 12, 4)):
            assert _ablauf(flach, eid, tag) == _ablauf(migriert, eid, tag), eid


def test_kinder_eigener_ablauf_abhaengig_von_morgen():
    eg = {**{k: v for k, v in STARTWERTE.items() if k != "aktiv"}, "name": "Erdgeschoss"}
    config = _config_ablaeufe([eg, KINDER_ABLAUF])
    untergang = _sonnenstand().untergang(date(2026, 12, 1)).strftime("%H:%M")
    # morgen Schule: bis 20:30, morgen frei: bis 22:00
    assert _ablauf(config, KINDER[2], date(2026, 12, 1)) == [
        ("06:30", 100), (untergang, 40), ("20:30", 0)], _ablauf(config, KINDER[2], date(2026, 12, 1))
    frei = _ablauf(config, KINDER[2], date(2026, 12, 4), frei=True)
    assert frei[-1] == ("22:00", 0), frei
    # das Erdgeschoss bleibt, wie es war
    assert _ablauf(config, EG[0], date(2026, 12, 1)) == _ablauf(_config(STARTWERTE), EG[0], date(2026, 12, 1))


def test_ein_rollo_hoechstens_in_einem_ablauf():
    try:
        _config_ablaeufe([{"name": "A", "rollos": {EG[0]: 40}}, {"name": "B", "rollos": {EG[0]: 20}}])
    except store.ValidationError:
        return
    raise AssertionError("doppelt vergebenes Rollo hätte abgelehnt werden müssen")


def test_lichter_je_ablauf():
    eg = {**{k: v for k, v in STARTWERTE.items() if k != "aktiv"}, "name": "Erdgeschoss"}
    config = _config_ablaeufe([eg, KINDER_ABLAUF])
    state = {}
    index = {e: _licht(e) for e in ("light.kette", "switch.terrasse", "light.stern")}
    with _Lichter() as l:
        _licht_takt(config, state, datetime(2026, 12, 1, 12, 0), index)
        _licht_takt(config, state, datetime(2026, 12, 1, 17, 0), index)
        assert sorted(l.befehle) == [("light.kette", True), ("light.stern", True), ("switch.terrasse", True)]
        _licht_takt(config, state, datetime(2026, 12, 1, 20, 31), index)
        assert l.befehle[3:] == [("light.stern", False)], l.befehle
        _licht_takt(config, state, datetime(2026, 12, 1, 22, 31), index)
        assert sorted(l.befehle[4:]) == [("light.kette", False), ("switch.terrasse", False)]


# ------------------------------------------------- Morgen/Abend (3.3) ----

SCHULMORGEN = {"name": "Kinder", "lichter": ["light.stern"],
               "rollos": {KINDER[2]: 40},
               "morgens": {"schultag": {"licht": "uhrzeit", "licht_zeit": "05:45",
                                        "licht_aus": "sonnenaufgang", "licht_aus_versatz": 0,
                                        "rollos": "uhrzeit", "rollos_zeit": "06:00"},
                           "schulfrei": {"licht": "aus", "rollos": "plan"}},
               "abends": {"schultag": {"licht": "uhrzeit", "licht_zeit": "17:00",
                                       "licht_aus_zeit": "20:30", "rollos": "sonnenuntergang"},
                          "schulfrei": {"licht": "uhrzeit", "licht_zeit": "17:00",
                                        "licht_aus_zeit": "22:00", "rollos": "sonnenuntergang"}}}


def test_alte_32_form_wird_uebertragen():
    """Ein Ablauf aus 3.2 (Licht an/aus, vor freien Tagen, Vorlauf) rechnet
    nach der Übertragung genau wie vorher."""
    eg32 = {**{k: v for k, v in STARTWERTE.items() if k != "aktiv"}, "name": "Erdgeschoss",
            "licht_aus_vor_schulfrei": "23:00"}
    neu = _config_ablaeufe([eg32])
    a = neu["einstellungen"]["weihnachtszeit"]["ablaeufe"][0]
    assert a["abends"]["schulfrei"]["licht_aus_zeit"] == "23:00" and a["morgens"]["schultag"]["licht"] == "vor_oeffnen"
    # Gegenprobe: dieselbe 3.2-Form ungeprüft gelesen (so rechnet ein
    # laufender Planer, bevor er die Einstellung neu speichert).
    roh = _config()
    roh["einstellungen"]["weihnachtszeit"] = {"aktiv": True, "zeitraum": "advent",
                                              "von": "12-01", "bis": "01-06", "ablaeufe": [eg32]}
    for eid in EG + [TUER]:
        for tag, frei in ((date(2026, 12, 1), False), (date(2026, 12, 4), False), (date(2026, 12, 5), True)):
            assert _ablauf(neu, eid, tag, frei) == _ablauf(roh, eid, tag, frei), (eid, tag)
    assert _ablauf(neu, EG[0], date(2026, 12, 5), True)[-1] == ("23:00", 0)
    assert _ablauf(neu, EG[0], date(2026, 12, 1), False)[-1] == ("22:30", 0)


def test_schulmorgen_licht_um_uhrzeit_aus_bei_sonnenaufgang():
    config = _config_ablaeufe([SCHULMORGEN])
    tag = date(2026, 12, 1)
    s = _sonnenstand()
    ablauf = config["einstellungen"]["weihnachtszeit"]["ablaeufe"][0]
    fenster = programme.lichtfenster(ablauf, tag, s, None, False, False)
    assert fenster[0][0].strftime("%H:%M") == "05:45"
    assert fenster[0][1] == s.aufgang(tag), fenster
    assert fenster[1][0].strftime("%H:%M") == "17:00" and fenster[1][1].strftime("%H:%M") == "20:30"
    zeiten = _ablauf(config, KINDER[2], tag)
    untergang = s.untergang(tag).strftime("%H:%M")
    assert zeiten == [("06:00", 40), ("06:30", 100), (untergang, 40), ("20:30", 0)], zeiten


def test_schulfrei_morgens_kein_licht_und_normaler_plan():
    config = _config_ablaeufe([SCHULMORGEN])
    tag = date(2026, 12, 5)
    ablauf = config["einstellungen"]["weihnachtszeit"]["ablaeufe"][0]
    fenster = programme.lichtfenster(ablauf, tag, _sonnenstand(), None, True, True)
    assert len(fenster) == 1 and fenster[0][1].strftime("%H:%M") == "22:00", fenster
    zeiten = _ablauf(config, KINDER[2], tag, frei=True)
    assert zeiten[0] == ("10:00", 100) and zeiten[-1] == ("22:00", 0), zeiten


# --------------------------------------------------- Fernbedienung (3.4) ----

FB = {"an": "event.fb_taste_1", "aus": "event.fb_taste_2"}


def _ev(stempel, typ):
    return {"state": stempel, "attributes": {"event_type": typ}}


def test_fernbedienung_tasten_erkennen():
    config = _config_ablaeufe([{**{k: v for k, v in STARTWERTE.items() if k != "aktiv"},
                                "name": "Erdgeschoss", "fernbedienung": FB}])
    zustaende = {FB["an"]: _ev("t0", "multi_press_1"), FB["aus"]: _ev("t0", "multi_press_1")}
    aktionen, gesehen = [], {}
    lauf = lambda: regelung.fb_auswerten(config, gesehen, zustaende.get,  # noqa: E731
                                         lambda a, x: aktionen.append(x))
    lauf()
    assert aktionen == [], "der erste Blick merkt nur – kein alter Druck nach dem Neustart"
    zustaende[FB["an"]] = _ev("t1", "multi_press_1"); lauf()
    zustaende[FB["aus"]] = _ev("t2", "multi_press_1"); lauf()
    zustaende[FB["aus"]] = _ev("t3", "long_press"); lauf()
    zustaende[FB["aus"]] = _ev("t4", "long_release"); lauf()
    lauf()
    assert aktionen == ["an", "aus", "alles_aus"], aktionen


def _fb(modus, wann):
    return {"eg": {"modus": modus, "seit": wann.isoformat(timespec="seconds")}}


def test_fernbedienung_aus_bringt_rollos_zum_plan():
    config = _config(STARTWERTE)
    zeiten = _ablauf(config, EG[0], date(2026, 12, 1), fb=_fb("aus", datetime(2026, 12, 1, 18, 0)))
    assert ("18:00", 0) in zeiten, zeiten


def test_fernbedienung_an_hebt_nur_an():
    config = _config(STARTWERTE)
    nacht = _ablauf(config, EG[0], date(2026, 12, 1), fb=_fb("an", datetime(2026, 12, 1, 23, 0)))
    assert ("23:00", 40) in nacht, nacht
    mittag = _ablauf(config, EG[0], date(2026, 12, 1), fb=_fb("an", datetime(2026, 12, 1, 12, 0)))
    assert ("12:00", 40) not in mittag, "ein offenes Rollo zieht die Fernbedienung nie zu"


def test_fernbedienung_ausserhalb_der_saison_nur_lichter():
    config = _config(STARTWERTE)
    tag = date(2026, 11, 22)
    assert _ablauf(config, EG[0], tag, fb=_fb("an", datetime(2026, 11, 22, 23, 0))) == _ablauf(config, EG[0], tag)
    state = {}
    with _Lichter() as l:
        regelung.fernbedienung(config, state, "eg", "an", datetime(2026, 11, 22, 18, 0), lambda *a, **k: None)
        assert sorted(l.befehle) == [("light.kette", True), ("switch.terrasse", True)]
        index = {"light.kette": _licht("light.kette", "on"), "switch.terrasse": _licht("switch.terrasse", "on")}
        _licht_takt(config, state, datetime(2026, 11, 22, 18, 5), index)
        assert len(l.befehle) == 2, "der Takt schaltet das Licht nicht gleich wieder aus"


def test_fernbedienung_licht_gilt_bis_zur_naechsten_grenze():
    config = _config(STARTWERTE)
    state = {}
    index = {"light.kette": _licht("light.kette"), "switch.terrasse": _licht("switch.terrasse")}
    with _Lichter() as l:
        _licht_takt(config, state, datetime(2026, 12, 1, 17, 0), index)      # Plan: an
        regelung.fernbedienung(config, state, "eg", "aus", datetime(2026, 12, 1, 18, 0), lambda *a, **k: None)
        n = len(l.befehle)
        _licht_takt(config, state, datetime(2026, 12, 1, 18, 5), index)
        assert len(l.befehle) == n, "bleibt aus, solange der Druck gilt"
        _licht_takt(config, state, datetime(2026, 12, 2, 6, 5), index)       # nächste Grenze: Morgenlicht
        assert sorted(l.befehle[n:]) == [("light.kette", True), ("switch.terrasse", True)], l.befehle[n:]
        assert "eg" not in state.get("weihnachtszeit_fb", {})


def test_lang_aus_trifft_alle_ablaeufe():
    eg = {**{k: v for k, v in STARTWERTE.items() if k != "aktiv"}, "name": "Erdgeschoss", "id": "eg"}
    config = _config_ablaeufe([eg, {**KINDER_ABLAUF, "id": "kinder"}])
    state = {}
    with _Lichter() as l:
        namen = regelung.fernbedienung(config, state, "eg", "alles_aus", datetime(2026, 12, 1, 19, 0),
                                       lambda *a, **k: None)
    assert set(namen) == {"Erdgeschoss", "Kinder"}
    assert {e for e, an in l.befehle if not an} == {"light.kette", "switch.terrasse", "light.stern"}
    assert set(state["weihnachtszeit_fb"]) == {"eg", "kinder"}


def test_freie_stellung_wird_genau_gefahren():
    """3.5: Stellungen außerhalb der Zehnerschritte (z. B. 61 % offen)."""
    eg = {**{k: v for k, v in STARTWERTE.items() if k != "aktiv"}, "name": "Erdgeschoss",
          "rollos": {EG[0]: 61, EG[1]: 83, TUER: "offen"}}
    config = _config_ablaeufe([eg])
    a = config["einstellungen"]["weihnachtszeit"]["ablaeufe"][0]
    assert a["rollos"][EG[0]] == 61 and a["rollos"][EG[1]] == 83
    zeiten = _ablauf(config, EG[0], date(2026, 12, 1))
    assert ("06:00", 61) in zeiten and [z for z in zeiten if z[1] == 61][1][0] != "06:00", zeiten


# ------------------------------------------------------- Die Lichter ----

class _Lichter:
    def __init__(self):
        self.befehle = []

    def __enter__(self):
        self._echt = ha_api.schalten
        ha_api.schalten = lambda eid, an: self.befehle.append((eid, an)) or True
        return self

    def __exit__(self, *a):
        ha_api.schalten = self._echt


def _licht_takt(config, state, jetzt, index):
    lage = {"weihnachtszeit": regelung._weihnachtslage(config["einstellungen"], state, jetzt),
            "zustaende": _zustaende(config)}
    plaene = {p["id"]: p for p in config["plaene"]}
    gruppe_von = {eid: g for g in config["gruppen"] for eid in g["rollos"]}
    return regelung._weihnachtslichter(
        config, config["einstellungen"], index, state, _kalender(False), _sonnenstand(),
        jetzt, lage, plaene, gruppe_von, lambda *a, **k: None)


def _licht(eid, zustand="off"):
    return {"entity_id": eid, "state": zustand, "attributes": {"friendly_name": eid}}


def test_lichter_schalten_auf_der_flanke():
    config = _config(STARTWERTE)
    state = {}
    index = {"light.kette": _licht("light.kette"), "switch.terrasse": _licht("switch.terrasse")}
    tag = date(2026, 12, 1)
    with _Lichter() as l:
        _licht_takt(config, state, datetime.combine(tag, datetime.min.time()).replace(hour=12), index)
        assert l.befehle == [], "mittags nichts – und vor allem kein „aus“ beim ersten Takt"
        _licht_takt(config, state, datetime(2026, 12, 1, 17, 0), index)
        assert sorted(l.befehle) == [("light.kette", True), ("switch.terrasse", True)]
        _licht_takt(config, state, datetime(2026, 12, 1, 17, 2), index)
        assert len(l.befehle) == 2, "nicht wiederholen"
        _licht_takt(config, state, datetime(2026, 12, 1, 22, 31), index)
        assert sorted(l.befehle[2:]) == [("light.kette", False), ("switch.terrasse", False)]
        _licht_takt(config, state, datetime(2026, 12, 2, 6, 5), index)
        assert sorted(l.befehle[4:]) == [("light.kette", True), ("switch.terrasse", True)]
        _licht_takt(config, state, datetime(2026, 12, 2, 6, 31), index)
        assert len(l.befehle) == 8


def test_unerreichbares_licht_wird_nachgeholt_und_haelt_nichts_auf():
    config = _config(STARTWERTE)
    state = {}
    index = {"light.kette": _licht("light.kette", "unavailable"),
             "switch.terrasse": _licht("switch.terrasse")}
    with _Lichter() as l:
        _licht_takt(config, state, datetime(2026, 12, 1, 12, 0), index)
        _licht_takt(config, state, datetime(2026, 12, 1, 17, 0), index)
        assert l.befehle == [("switch.terrasse", True)]
        index["light.kette"] = _licht("light.kette")
        _licht_takt(config, state, datetime(2026, 12, 1, 18, 0), index)
        assert l.befehle[-1] == ("light.kette", True)


def test_trockenlauf_schaltet_keine_lichter():
    config = _config(STARTWERTE)
    config["einstellungen"]["trockenlauf"] = True
    state = {}
    index = {"light.kette": _licht("light.kette"), "switch.terrasse": _licht("switch.terrasse")}
    with _Lichter() as l:
        _licht_takt(config, state, datetime(2026, 12, 1, 12, 0), index)
        _licht_takt(config, state, datetime(2026, 12, 1, 17, 0), index)
        assert l.befehle == []


def test_ausserhalb_der_saison_kein_licht():
    config = _config(STARTWERTE)
    state = {}
    index = {"light.kette": _licht("light.kette"), "switch.terrasse": _licht("switch.terrasse")}
    with _Lichter() as l:
        for stunde in (12, 17, 23):
            _licht_takt(config, state, datetime(2026, 11, 20, stunde, 0), index)
        assert l.befehle == []


def test_einstellungen_werden_geprueft():
    try:
        store.validate_einstellungen({"weihnachtszeit": {"ablaeufe": [{"name": "A", "licht_aus": "25:00"}]}})
    except store.ValidationError:
        pass
    else:
        raise AssertionError("25:00 hätte abgelehnt werden müssen")
    e = store.validate_einstellungen({"weihnachtszeit": {"ablaeufe": [{"name": "A",
        "lichter": ["light.a", "cover.b", "switch.c", "light.a"],
        "rollos": {"cover.x": "plan", "cover.y": "offen", "cover.z": "40"}}]}})
    a = e["weihnachtszeit"]["ablaeufe"][0]
    assert a["lichter"] == ["light.a", "switch.c"]
    assert a["rollos"] == {"cover.y": "offen", "cover.z": 40}
    try:
        store.validate_einstellungen({"weihnachtszeit": {"ablaeufe": [
            {"name": "A", "lichter": ["light.a"]}, {"name": "B", "lichter": ["light.a"]}]}})
    except store.ValidationError:
        pass
    else:
        raise AssertionError("ein Licht in zwei Abläufen hätte abgelehnt werden müssen")


def test_darf_frueher_schliessen_nur_ausdruecklich():
    """Standard: nur hinauszögern. Mit der Option schließt der Ablauf um Licht
    aus, auch wenn der Plan das Rollo noch offen hätte."""
    tag = date(2026, 12, 1)
    tuer = {AUSWAHL: "24 Uhr"}
    normal = _config_ablaeufe([{"name": "EG", "licht_aus": "21:00", "rollos": {TUER: "offen"}}])
    assert ("21:00", 0) not in _ablauf(normal, TUER, tag, schalter=tuer)
    frueher = _config_ablaeufe([{"name": "EG", "licht_aus": "21:00", "frueher_schliessen": True,
                                 "rollos": {TUER: "offen"}}])
    assert ("21:00", 0) in _ablauf(frueher, TUER, tag, schalter=tuer), _ablauf(frueher, TUER, tag, schalter=tuer)


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
            print(f"  FEHL {name}: {err!r}")
    print(f"\n{fehler} Fehler")
    sys.exit(1 if fehler else 0)
