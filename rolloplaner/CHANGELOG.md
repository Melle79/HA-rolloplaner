# Änderungen

## 1.4.0 – 26.08.2026

**Die Prozentangaben lassen sich umdrehen.** Home Assistant zählt 100 % =
offen, Amazon Echo andersherum – wer beides bedient, verrechnet sich sonst
ständig. Der Schalter steht unter *Einstellungen → Betrieb*.

Umgedreht wird nur, was **angezeigt und eingegeben** wird. Gespeichert bleibt
alles in der Zählweise von Home Assistant; sonst stünde nach jedem Umschalten
jeder Zeitplan auf dem Kopf. „auf“ und „zu“ bleiben ebenfalls, wie sie sind –
die Wörter hängen nicht an der Zählweise, nur die Zahl dazwischen. Und das
Rollobild folgt der Physik: Wie weit der Panzer heruntersteht, ist eine
Tatsache und keine Frage der Beschriftung.

Der Wert der Raum-Sensoren dreht sich mit, damit die Karte nicht etwas anderes
zeigt als die Entität dahinter. Das Attribut `stellung_ha` behält die Zählweise
von Home Assistant – für Automationen, die eine verlässliche Größe brauchen.

**Die Helfer-Chips sagen jetzt, was sie freigeben.** Vorher stand dort der Name
des Helfers – „Öffnen Nele“, „Obergeschoss schließen“ – und niemand konnte
sehen, wozu die Knöpfe in der Kachel gehören. Jetzt steht davor „gibt frei“ und
auf dem Chip die Wirkung: *öffnen*, *schließen*, *auf und zu* oder *den ganzen
Raum*. Abgeleitet wird sie aus den Schaltpunkten, an denen der Helfer hängt.
Der volle Name steht im Tooltip.

## 1.3.2 – 26.08.2026

**Die Zarge läuft nur noch an drei Seiten**, unten ist sie offen. Genau daran
erkennt man eine Tür: Ein umlaufender Rahmen ist ein Fensterrahmen, und die Tür
wirkte damit wie ein Kasten, der über dem Boden schwebt. Jetzt steht sie auf
der Bodenlinie.

## 1.3.1 – 26.08.2026

**Die Tür sah aus wie ein Kühlschrank.** Ein schmales hohes Rechteck mit einem
Griff an der Seite – da half es nicht, dass die Proportion stimmte. Sie hat
jetzt einen sichtbaren **Flügelrahmen mit Glas darin** und einen kurzen
Drehgriff statt des langen Balkens.

Dazu eine **Bodenlinie** unter beiden Bildern. Sie zeigt, worauf das Ding
steht: Die Tür reicht bis hinunter, das Fenster hängt darüber in der Wand. Das
ist der Unterschied, den man auch bei vierzig Pixeln noch sieht.

## 1.3.0 – 26.08.2026

**Keine Fensterkreuze mehr.** Die Sprossen waren bei 40 Pixeln kein Detail,
sondern Unruhe.

**Türen sehen jetzt aus wie Türen.** Ein Rollladen vor einer Balkontür geht bis
zum Boden, einer vor einem Fenster hat eine Brüstung darunter – genau das
zeigen die Bilder. Beide stecken in einer Box gleicher Höhe, damit in einer
Kachelreihe nichts springt; die Tür hat außerdem einen Griff und eine Schwelle.
Nur schmaler zu zeichnen hätte nicht gereicht, das sähe aus wie ein kleineres
Fenster.

Welches Bild ein Raum bekommt, entscheidet die Vorgabe **automatisch nach den
Namen der Rollos** – „Rollo Balkontür Luna“ ist eine Tür, „Rollo Küche“ ein
Fenster. Ein Raum gilt nur dann als Tür, wenn *alle* seine Rollos welche sind:
Luna hat ein Fenster und eine Balkontür, und ein Bild für zwei verschiedene
Dinge zeigt besser den Regelfall. Im Raum-Dialog lässt sich das überstimmen.

## 1.2.0 – 26.08.2026

**Statt des Fortschrittsbalkens ein simuliertes Fensterrollo.** Ein Balken sagt
„65 %“ – aber nicht, ob das Rollo dabei oben oder unten ist. Das Bild zeigt es:
Der Panzer hängt von oben herunter, darunter kommt das Fenster zum Vorschein,
und beim Fahren läuft er sichtbar mit. Die Farben folgen bewusst nicht dem
Farbschema – das ist kein Bedienelement, sondern das Bild eines Gegenstands.

**Die Karte ist jetzt im Kacheldesign** der Add-on-Oberfläche: Raumname und
großer Prozentwert nebeneinander, darunter Begründung, Helfer und der nächste
Wechsel. Die Kacheln richten sich nach der Breite – in einer schmalen
Dashboard-Spalte steht eine je Zeile, in einer breiten mehrere.

Lange Raumnamen brechen um, statt abgeschnitten zu werden:
„Wohnzimmer – Terrassentür“ ist der Name, an dem man die Kachel erkennt,
„Wohnzimmer – …“ ist keiner.

## 1.1.0 – 26.08.2026

Nach dem ersten Blick auf die Karte im echten Dashboard.

**Die Helfer sind jetzt in der Karte bedienbar.** Wo ein Schaltpunkt an einem
`input_boolean` oder `input_select` hängt, erscheint er beim Raum — als Chip
mit Punkt für an/aus, als Auswahlliste bei mehreren Stellungen. Damit lässt
sich die Terrassentür („normal / 24 Uhr / aus“) dort umstellen, wo man ohnehin
hinsieht, statt die Karte zu verlassen und den Helfer anderswo zu suchen.

**Das Aussehen:**

* Die Räume hießen **„Rolloplaner Rollo Büro“** – Home Assistant stellt den
  Gerätenamen voran, und die Karte strich nur „Rollo “ weg.
* Die Begründung enthielt die **Bedingungen als Entity-IDs**
  („… (helfer_rollo_eg_schliessen = on)“). Auf einer Kachel liest sich das wie
  eine Fehlermeldung; sie stehen jetzt nur noch im Raum-Dialog.
* Das Schild **„Zeitplan“** erschien an jedem Raum und verdeckte damit genau
  die Zeile, auf der wirklich „Hitzeschutz“ oder „Handbetrieb“ steht.
* **Keine eigenen Flächen mehr.** Die Raumzeilen hatten einen eigenen
  Hintergrund – in einem hellen Theme ein dunkler Fremdkörper. Jetzt tun es
  Trennlinien, die die Farbe des Themes annehmen. Der Fortschrittsbalken ist
  weg; er sah bei „zu“ aus wie eine zweite Trennlinie.

## 1.0.0 – 26.08.2026

Erste Fassung.

* **Zeitplan je Raum** mit Schaltpunkten nach Uhrzeit, Sonnenaufgang,
  Sonnenuntergang oder Dämmerung. Sonnenauslöser lassen sich mit
  „frühestens“/„spätestens“ einklammern.
* **Geltung** je Schaltpunkt: immer, an Schultagen, an schulfreien Tagen –
  oder danach, ob *morgen* Schule ist.
* **Bedingungen** je Schaltpunkt, für Auswahlhelfer und Freigabeschalter.
* **Hitzeschutz** nach Sonnenrichtung und Außentemperatur, mit Hysterese und
  freiwilligem Raumfühler.
* **Urlaub**: Anwesenheitssimulation mit reproduzierbarem Tagesversatz,
  „alles zu“ oder normaler Plan.
* **Rauchsperre**: Schlägt ein Melder an, wird kein Rollo mehr angefasst.
* **Fenstersperre**: Bei offenem Kontakt wird nicht zugefahren; der
  Schaltpunkt wird nachgeholt, sobald das Fenster zugeht.
* **Handbetrieb** wird erkannt und für eine einstellbare Frist respektiert.
* **Wächter** für stumme Antriebe und für die Hindernismeldungen der
  Rademacher-Gurtwickler.
* **Übernahme** vorhandener Automationen aus `automations.yaml`, mit
  Erkennung von Auslöser-IDs, Zeitklammern und Auswahlhelfern. Rollos mit
  eigenem Schaltmuster bekommen einen eigenen Raum.
* **Selbstauskunft** über fehlende Entitäten, Räume ohne Plan und noch
  laufende Automationen.
* **Lovelace-Karte** liegt im Add-on und wird beim Start selbst eingebunden.
