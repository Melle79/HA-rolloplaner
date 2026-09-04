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
