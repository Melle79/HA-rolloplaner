# Änderungen

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
