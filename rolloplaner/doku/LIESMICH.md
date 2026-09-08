# Bildquellen

`icon.svg` und `logo.svg` sind die Quellen für `icon.png` (128×128) und
`logo.png` (250×100) im Add-on-Verzeichnis. Neu erzeugen mit einem beliebigen
Browser im Kopflos-Betrieb, zum Beispiel:

```
chrome --headless=new --screenshot=icon.png --window-size=128,128 \
       --default-background-color=00000000 --hide-scrollbars seite.html
```

Das Motiv: ein Rollladen, halb heruntergelassen, und dahinter die Sonne – die
beiden Dinge, um die es geht. Der Panzer ist eine Fläche mit dunklen Fugen und
nicht eine Reihe einzelner Balken: Durch echte Zwischenräume sah der Himmel
hindurch, und aus anderthalb Metern las sich das als Streifenmuster statt als
Rollladen.

**Eine Falle beim Nachbauen:** Der Verlauf der Sonne steht in festen
Koordinaten (`gradientUnits="userSpaceOnUse"`) und nicht in der Bounding-Box
des Elements. Ein waagerechter Strahl hat eine Box ohne Höhe; ein Verlauf
darüber ist entartet, und Chrome zeichnet das Element dann gar nicht. Die
beiden seitlichen Strahlen fehlten deshalb spurlos – zu sehen war nur, dass
die Sonne vier statt sechs Strahlen hatte.

Dieselbe Farbwelt wie beim Heizungsplaner: derselbe dunkle Grund, dieselbe
Schrift, dasselbe Muster aus Name und drei Stichworten. In der Add-on-Liste
sollen die beiden als Geschwister zu erkennen und trotzdem auf einen Blick zu
unterscheiden sein.

## Bilder für README und Handbuch

`bilder/*.png` zeigen die Oberfläche und die Karte, `bilder/en/*.png` dieselben
Ansichten auf Englisch. Beide sind **echte Aufnahmen mit echten Daten**, kein
Nachbau:

* Die **Oberfläche** wird lokal gerendert. Die Antworten des Add-ons holt man
  einmal ab und legt sie als Dateien daneben, dann läuft `index.html` gegen
  diesen Stand:

  ```
  for e in config status entitaeten logbuch schalter gesundheit uebernahme; do
    ssh haos "curl -s http://<add-on-ip>:8100/api/$e" > api/$e
  done
  ```

  Der Weg über die Ingress-Adresse geht nicht: Die verlangt eine Anmeldung.
  Ein SSH-Tunnel auf Port 8100 auch nicht – die SSH-Erweiterung von Home
  Assistant erlaubt kein Weiterleiten.

* Die **Karte** bekommt die echten Entitäten: alles unter
  `sensor.rolloplaner*`, `switch.rolloplaner*` und
  `binary_sensor.rolloplaner*` aus `/api/states`, als `zustaende.json`
  daneben. Dazu zwei Attrappen für `ha-card` und `ha-icon`.

  **Zwei Fallstricke dabei**, beide haben mich erst falsch messen lassen: Die
  `ha-card`-Attrappe braucht eine Breite, sonst ist alles null Pixel breit –
  ein Stil aus dem Dokument greift im Schattenbaum der Karte nicht, er muss
  inline stehen. Und sie darf nicht `style.cssText` setzen: Die Karte legt
  ihre Textskala im selben Attribut ab, und `cssText` wischt sie weg.

* Für die **englischen** Aufnahmen wird die Sprache des Add-ons kurz auf `en`
  gestellt, einen Takt abgewartet, aufgenommen und wieder zurückgestellt. Die
  Karte braucht das nicht: Sie folgt dem Betrachter, dafür genügt ein anderes
  `hass.locale.language`.

Zimmer- und Rollo-Namen bleiben in den englischen Aufnahmen deutsch – das sind
die Namen des Hauses und keine Oberfläche.
