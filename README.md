# Melle79 Add-ons: Rolloplaner

Home-Assistant-Add-on zur Rollladensteuerung — mit eigener Lovelace-Karte.

## Installation

Diese Adresse als Add-on-Repository in Home Assistant eintragen
(*Einstellungen → Add-ons → Add-on Store → ⋮ → Repositories*):

```
https://github.com/Melle79/HA-rolloplaner
```

Danach erscheint **Rolloplaner** im Store. Die Lovelace-Karte bringt das Add-on
selbst mit; eine getrennte Installation über HACS ist nicht nötig.

## Was es tut

**Ein Zeitplan je Rollo**, der nach Uhrzeit **oder** nach dem Stand der Sonne
schaltet: „bei Sonnenuntergang zufahren, spätestens 20:30, an Schultagen“ ist
ein Eintrag und nicht drei Automationen. Schulfrei, Feiertage und „morgen
schulfrei“ kann er berücksichtigen.

Die Steuereinheit ist **das Rollo**, nicht der Raum — in jedem Haus, in dem ein
Zimmer ein Fenster *und* eine Balkontür hat, geht es nicht anders. Darüber
liegen **Obergruppen** (etwa Etagen) für alles, was zusammengehört: Sie können
einen gemeinsamen Zeitplan tragen, der zu den einzelnen dazukommt, und einen
Freigabeschalter für den ganzen Schnitt.

Dazu:

* **Hitzeschutz** nach Sonnenrichtung — fährt teilweise zu, wenn die Sonne in
  *dieses* Fenster steht und es draußen warm ist. Je Rollo schaltbar.
* **Fluchtweg-Freigabe** bei Rauchalarm: fährt jedes Rollo auf, über Automatik
  und Zeitplan hinweg, und meldet, was **nicht** erreichbar war. Danach führt
  der Planer keinen Schaltpunkt mehr aus, der den Weg wieder zumachen würde.
* **Fenstersperre** — solange ein Kontakt offen ist, wird nicht zugefahren.
  An einer Balkontür ist das der Unterschied zwischen „zu“ und „ausgesperrt“.
* **Urlaub**: geschlossen halten oder Anwesenheit simulieren, mit Streuung.
* **Wächter**, der meldet, wenn ein Antrieb sich nicht mehr rührt oder hängt.
* **Trockenlauf**: rechnet und protokolliert, fährt aber nichts — zum
  Mitlaufen neben den bestehenden Automationen.

Vorhandene Rollladen-Automationen liest das Add-on ein und schlägt vor, was es
daraus machen würde. **Übernommen wird nichts von selbst.**

## Die Karte

`custom:rolloplaner-card` — je Rollo eine Kachel mit einem **simulierten
Rollladen** statt eines Balkens: Ein Balken sagt „65 %“, aber nicht, ob das
Rollo dabei oben oder unten ist. Vor einer Tür sieht er anders aus als vor
einem Fenster.

Bedient wird direkt in der Kachel: auf, zu, Automatik, Hitzeschutz — und die
Freigabeschalter, an denen die Schaltpunkte hängen. Eingestellt wird sie im
**Karteneditor**, ohne YAML: Schriftgröße (gedacht für ein Wandtablett), was
sie zeigt, und welche Gruppen in welcher Reihenfolge erscheinen.

## Zweisprachig

Planer, Einrichtung und Karte sprechen **Deutsch und Englisch**. Add-on und
Einrichtung folgen Home Assistant oder der Einstellung unter *Einstellungen →
Sprache*; die Karte folgt dem **Betrachter** — auf dem Wandtablett steht
Deutsch, ein englischsprachiger Gast sieht dieselbe Karte auf Englisch. Eine
dritte Sprache ist eine weitere Tabelle, kein `gettext` und kein Bauschritt.

## Ausführlich

[rolloplaner/DOCS.md](rolloplaner/DOCS.md) — das Handbuch. Es erklärt nicht nur,
was die Knöpfe tun, sondern warum die Entscheidungen so gefallen sind: warum
auf der Flanke geschaltet wird und nicht auf dem Pegel, warum der Planer die
Sonnenzeiten selbst rechnet, und was „aus“ jeweils bedeutet.

[rolloplaner/CHANGELOG.md](rolloplaner/CHANGELOG.md) — was sich geändert hat.

## Lizenz

MIT
