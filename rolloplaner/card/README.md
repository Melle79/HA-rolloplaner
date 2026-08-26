# Rolloplaner-Card

Die Karte wird **mit dem Add-on ausgeliefert** – eine getrennte Installation
über HACS ist nicht nötig und auch nicht erwünscht: Zwei Registrierungen
desselben Custom Elements legen das Dashboard lahm.

Beim Start kopiert das Add-on `rolloplaner-card.js` nach `www/` der
Home-Assistant-Konfiguration und trägt sie als Lovelace-Ressource ein. Ist die
Karte bereits aus einer anderen Quelle eingebunden, legt es nichts an und
schreibt nur einen Hinweis ins Protokoll.

Verwendung und Optionen stehen in [../DOCS.md](../DOCS.md).
