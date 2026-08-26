# Melle79 Add-ons: Rolloplaner

Home-Assistant-Add-on zur Rollladensteuerung.

## Installation

Diese Adresse als Add-on-Repository in Home Assistant eintragen
(*Einstellungen → Add-ons → Add-on Store → ⋮ → Repositories*):

```
https://github.com/Melle79/HA-rolloplaner
```

Danach erscheint **Rolloplaner** im Store.

## Was es tut

Ein Zeitplan je Raum, der nach Uhrzeit **oder** nach dem Stand der Sonne
schaltet – „bei Sonnenuntergang zufahren, spätestens 20:30“ ist ein Eintrag und
nicht zwei Automationen. Dazu Hitzeschutz nach Sonnenrichtung,
Anwesenheitssimulation im Urlaub, eine Fenstersperre und eine Rauchsperre, die
einer Notöffnung nicht hinterherfährt.

Vorhandene Rollladen-Automationen liest das Add-on ein und schlägt vor, was es
daraus machen würde. Übernommen wird nichts von selbst.

Ausführlich: [rolloplaner/DOCS.md](rolloplaner/DOCS.md)

## Lizenz

MIT
