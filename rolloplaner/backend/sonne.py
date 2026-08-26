"""Sonnenstand: Auf- und Untergang eines beliebigen Tages, Höhe und Richtung.

Warum gerechnet statt abgelesen: ``sun.sun`` meldet nur den **nächsten** Auf-
und Untergang. Der Zeitplan braucht aber den Sonnenuntergang von *gestern* –
sonst weiß der Planer um zwei Uhr nachts nicht, dass der Schaltpunkt „bei
Sonnenuntergang zufahren“ längst fällig war, und lässt das Rollo offen. Die
Rückschau über Tagesgrenzen ist der Kern der Zeitplanlogik, und die kann man
aus einem „nächsten“ Zeitpunkt nicht bauen.

Gerechnet wird nach dem üblichen NOAA-Verfahren. Es ist auf etwa eine Minute
genau; für einen Rollladen ist das reichlich.
"""
from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta

# Sonnenhöhe, bei der ein Ereignis gilt. Der Aufgang liegt nicht bei 0°:
# Die Sonnenscheibe hat einen Radius, und die Atmosphäre hebt sie optisch an.
HOEHE_AUFGANG = -0.833
HOEHE_DAEMMERUNG = -6.0     # bürgerliche Dämmerung: draußen wird es dunkel


# So weit darf die Justierung an ``sun.sun`` höchstens gehen. Alles darüber
# ist kein Höhenunterschied mehr, sondern ein Datenfehler – und den soll die
# Justierung nicht in den Zeitplan tragen.
MAX_KORREKTUR_SEKUNDEN = 900


def _julianischer_tag(tag: date) -> float:
    y, m, d = tag.year, tag.month, tag.day
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return (math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1))
            + d + b - 1524.5)


def _sonnenparameter(jd: float) -> tuple[float, float]:
    """Deklination und Zeitgleichung (in Minuten) für einen Julianischen Tag."""
    t = (jd - 2451545.0) / 36525.0
    # Mittlere Länge und mittlere Anomalie der Sonne
    L0 = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360
    M = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    Mr = math.radians(M)
    # Mittelpunktsgleichung: die Bahn ist eine Ellipse, keine Kreisbahn
    C = ((1.914602 - t * (0.004817 + 0.000014 * t)) * math.sin(Mr)
         + (0.019993 - 0.000101 * t) * math.sin(2 * Mr)
         + 0.000289 * math.sin(3 * Mr))
    wahre_laenge = L0 + C
    omega = 125.04 - 1934.136 * t
    lambda_ = wahre_laenge - 0.00569 - 0.00478 * math.sin(math.radians(omega))

    epsilon0 = (23 + (26 + ((21.448 - t * (46.8150 + t * (0.00059 - t * 0.001813))))
                      / 60) / 60)
    epsilon = epsilon0 + 0.00256 * math.cos(math.radians(omega))

    deklination = math.degrees(math.asin(
        math.sin(math.radians(epsilon)) * math.sin(math.radians(lambda_))))

    # Zeitgleichung
    y = math.tan(math.radians(epsilon / 2)) ** 2
    e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    L0r = math.radians(L0)
    eq = (y * math.sin(2 * L0r)
          - 2 * e * math.sin(Mr)
          + 4 * e * y * math.sin(Mr) * math.cos(2 * L0r)
          - 0.5 * y * y * math.sin(4 * L0r)
          - 1.25 * e * e * math.sin(2 * Mr))
    return deklination, math.degrees(eq) * 4


def _ereignis(tag: date, lat: float, lon: float, hoehe: float,
              aufgang: bool, zeitzone_offset_h: float) -> datetime | None:
    """Ortszeit, zu der die Sonne die angegebene Höhe erreicht.

    ``None``, wenn sie das an diesem Tag nicht tut – im Juni geht die Sonne
    nördlich des Polarkreises nicht unter. In Bayern kommt das nicht vor, aber
    ein Programm, das dabei mit einer Wurzel aus einer negativen Zahl abstürzt,
    fährt eben auch in Bayern kein Rollo mehr.
    """
    jd = _julianischer_tag(tag)
    deklination, zeitgleichung = _sonnenparameter(jd)

    latr, dekr = math.radians(lat), math.radians(deklination)
    cos_h = ((math.sin(math.radians(hoehe)) - math.sin(latr) * math.sin(dekr))
             / (math.cos(latr) * math.cos(dekr)))
    if not -1.0 <= cos_h <= 1.0:
        return None
    stundenwinkel = math.degrees(math.acos(cos_h))
    if not aufgang:
        stundenwinkel = -stundenwinkel

    # Minuten nach Mitternacht Weltzeit, dann in Ortszeit umrechnen
    minuten_utc = 720 - 4 * (lon + stundenwinkel) - zeitgleichung
    minuten_lokal = minuten_utc + zeitzone_offset_h * 60
    versatz_tage, minuten_im_tag = divmod(minuten_lokal, 1440)
    return (datetime.combine(tag, time(0, 0))
            + timedelta(days=int(versatz_tage), minutes=minuten_im_tag))


class Sonnenstand:
    """Sonnenzeiten und -richtung für einen festen Ort.

    Die Zeitzone wird aus der Systemzeit genommen: Das Add-on übernimmt beim
    Start die Zeitzone von Home Assistant, und alle Zeitpläne rechnen in
    Ortszeit. Der Versatz wird je Tag bestimmt, damit die Sommerzeitumstellung
    nicht eine Stunde Fehler hinterlässt.
    """

    def __init__(self, lat: float, lon: float):
        self.lat = lat
        self.lon = lon
        self._cache: dict[tuple, datetime | None] = {}
        # Justierung gegen ``sun.sun``, je Ereignisart in Sekunden.
        self.korrektur: dict[str, float] = {}

    # -------------------------------------------------------- Justierung ----

    def kalibrieren(self, art: str, soll: datetime) -> float | None:
        """Die eigene Rechnung an einem Zeitpunkt aus ``sun.sun`` ausrichten.

        Die reine Formel gilt für Meereshöhe. Ottobrunn liegt auf 553 m, und
        Home Assistant rechnet das anders ein als jede Formel, die man hier
        nachbauen könnte – gemessen bleiben drei Minuten Unterschied stehen.

        Statt Annahmen über fremde Rechenwege zu treffen, nimmt der Planer den
        Zeitpunkt, den ``sun.sun`` ohnehin liefert, und merkt sich die
        Differenz. Damit fährt er auf die Sekunde dann, wenn im Dashboard
        „Sonnenuntergang“ steht – und bleibt es auch, wenn Home Assistant
        seine Rechnung eines Tages ändert.
        """
        roh = self._roh(art, soll.date())
        if roh is None:
            return None
        abweichung = (soll - roh).total_seconds()
        if abs(abweichung) > MAX_KORREKTUR_SEKUNDEN:
            return None
        self.korrektur[art] = abweichung
        return abweichung

    def _roh(self, art: str, tag: date) -> datetime | None:
        if art == "sonnenaufgang":
            return self._hole(tag, HOEHE_AUFGANG, True)
        if art == "sonnenuntergang":
            return self._hole(tag, HOEHE_AUFGANG, False)
        if art == "daemmerung":
            return self._hole(tag, HOEHE_DAEMMERUNG, False)
        return None

    @staticmethod
    def _offset_stunden(tag: date) -> float:
        mittag = datetime.combine(tag, time(12, 0))
        versatz = mittag.astimezone().utcoffset()
        return versatz.total_seconds() / 3600 if versatz else 0.0

    def _hole(self, tag: date, hoehe: float, aufgang: bool) -> datetime | None:
        schluessel = (tag, hoehe, aufgang)
        if schluessel not in self._cache:
            if len(self._cache) > 400:      # ein gutes Jahr, dann von vorn
                self._cache.clear()
            self._cache[schluessel] = _ereignis(
                tag, self.lat, self.lon, hoehe, aufgang, self._offset_stunden(tag))
        return self._cache[schluessel]

    def aufgang(self, tag: date) -> datetime | None:
        return self.zeitpunkt("sonnenaufgang", tag)

    def untergang(self, tag: date) -> datetime | None:
        return self.zeitpunkt("sonnenuntergang", tag)

    def daemmerung(self, tag: date) -> datetime | None:
        return self.zeitpunkt("daemmerung", tag)

    def zeitpunkt(self, art: str, tag: date) -> datetime | None:
        roh = self._roh(art, tag)
        if roh is None:
            return None
        return roh + timedelta(seconds=self.korrektur.get(art, 0.0))

    # ------------------------------------------------------------- Stand ----

    def stand(self, wann: datetime) -> tuple[float, float]:
        """Höhe und Richtung der Sonne: (Elevation in Grad, Azimut in Grad).

        Azimut wie in Home Assistant: 0° Nord, 90° Ost, 180° Süd, 270° West.
        """
        offset = self._offset_stunden(wann.date())
        utc = wann - timedelta(hours=offset)
        jd = _julianischer_tag(utc.date()) + (
            utc.hour + utc.minute / 60 + utc.second / 3600) / 24
        deklination, zeitgleichung = _sonnenparameter(jd)

        minuten = utc.hour * 60 + utc.minute + utc.second / 60
        wahre_sonnenzeit = (minuten + zeitgleichung + 4 * self.lon) % 1440
        stundenwinkel = wahre_sonnenzeit / 4 - 180

        latr = math.radians(self.lat)
        dekr = math.radians(deklination)
        hr = math.radians(stundenwinkel)

        sin_hoehe = (math.sin(latr) * math.sin(dekr)
                     + math.cos(latr) * math.cos(dekr) * math.cos(hr))
        sin_hoehe = max(-1.0, min(1.0, sin_hoehe))
        hoehe = math.degrees(math.asin(sin_hoehe))

        azimut = math.degrees(math.atan2(
            math.sin(hr),
            math.cos(hr) * math.sin(latr) - math.tan(dekr) * math.cos(latr)))
        return round(hoehe, 2), round((azimut + 180) % 360, 2)


# ------------------------------------------------------------ Beschattung ----

def winkelabstand(a: float, b: float) -> float:
    """Der kleinere der beiden Winkel zwischen zwei Richtungen, 0…180°.

    Ohne diese Rechnung stünde ein Südwestfenster (225°) und eine Sonne bei
    350° scheinbar 125° auseinander; tatsächlich sind es 125° – aber bei
    Fenster 10° und Sonne 350° wären es 340 statt der richtigen 20.
    """
    return abs((a - b + 180) % 360 - 180)


def sonne_steht_im_fenster(azimut: float, elevation: float,
                           ausrichtung: float | None, oeffnungswinkel: float,
                           min_elevation: float) -> bool:
    """Trifft die Sonne gerade dieses Fenster?

    Zwei Bedingungen: Sie muss aus der Richtung kommen, in die das Fenster
    zeigt, und hoch genug stehen. Eine Sonne knapp über dem Horizont blendet
    zwar, heizt den Raum aber kaum auf – und im Winter ist genau das die
    Sonne, die man haben will.
    """
    if ausrichtung is None:
        return False
    if elevation < min_elevation:
        return False
    return winkelabstand(azimut, ausrichtung) <= oeffnungswinkel / 2
