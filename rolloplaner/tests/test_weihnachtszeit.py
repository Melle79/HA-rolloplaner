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


def _lage(config, hand=None):
    cfg = config["einstellungen"]["weihnachtszeit"]
    aktiv_am = lambda t: programme.aktiv_am(cfg, t, hand)  # noqa: E731
    return {"weihnachtszeit": {"aktiv_am": aktiv_am, "heute": None, "hand": hand},
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


def _ablauf(config, eid, tag, frei=False, schalter=None):
    s = _sonnenstand()
    rollo = next(r for r in config["rollos"] if r["entity_id"] == eid)
    lage = _lage(config)
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
        store.validate_einstellungen({"weihnachtszeit": {"licht_aus": "25:00"}})
    except store.ValidationError:
        pass
    else:
        raise AssertionError("25:00 hätte abgelehnt werden müssen")
    e = store.validate_einstellungen({"weihnachtszeit": {
        "lichter": ["light.a", "cover.b", "switch.c", "light.a"],
        "rollos": {"cover.x": "plan", "cover.y": "offen", "cover.z": "40"}}})
    assert e["weihnachtszeit"]["lichter"] == ["light.a", "switch.c"]
    assert e["weihnachtszeit"]["rollos"] == {"cover.y": "offen", "cover.z": 40}


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
