# Änderungen

## 2.16.1 – 03.09.2026

* `backend/version.py` hinkte hinterher: Das Add-on meldete beim Start weiter
  2.15.0, während es längst die neue Oberfläche fuhr. Genau daran sucht man
  einen Fehler zuerst – und findet keinen.
* Ein Wächter im Prüflauf hält `config.yaml`, `version.py` und die Karte auf
  derselben Nummer.

## 2.16.0 – 03.09.2026

**Auch die Oberfläche des Add-ons spricht jetzt Englisch.** In 2.15.0 sprachen
Planer und Karte zwei Sprachen, die Einrichtung dagegen nur Deutsch – also
ausgerechnet die Stelle, an der man die Sprache einstellt.

* **Alle acht Reiter übersetzt**, samt der langen Erklärtexte, der Dialoge für
  Rollo und Zeitplan, aller Rückfragen und aller Meldungen. Die Oberfläche
  folgt derselben Einstellung wie der Planer.
* **Wochentage, Himmelsrichtungen, Auslöser und Fensterarten** stehen nicht
  mehr als feste Listen im Kopf der Datei, sondern werden bei jedem Zeichnen
  gebaut. Sonst wäre die Sprache dort festgelegt, bevor der Planer sie
  überhaupt gemeldet hat.
* **Einzahl statt „1 covers shaded"**: Steht neben einem Schlüssel einer mit
  `_1`, gilt der bei genau einem Stück – in Planer und Oberfläche.
* Auch die zwei deutschen Sätze aus der Übernahme alter Automationen
  („kein Zeit- oder Sonnenauslöser") sprechen jetzt beide Sprachen.
* Die Uhrzeiten stehen in beiden Sprachen 24-stündig: „7:30 PM" neben einem
  Zeitplan, der in 19:30 gedacht ist, liest sich falsch.
* **Drei neue Wächter im Prüflauf**: beide Tabellen dieselben Schlüssel und
  Platzhalter, kein Schlüssel doppelt vergeben, kein benutzter Schlüssel ohne
  Eintrag. Der doppelte Eintrag ist der heimtückische Fall – JavaScript nimmt
  stillschweigend den letzten.

## 2.15.0 – 28.08.2026

**Der Planer spricht Deutsch und Englisch.**

* **Die Karte folgt dem Betrachter** (`hass.locale.language`): Auf dem
  Wandtablett steht Deutsch, ein englischsprachiger Gast sieht dieselbe Karte
  auf Englisch. Niemand muss etwas umstellen.
* **Das Add-on folgt Home Assistant** oder der neuen Einstellung
  *Einstellungen → Sprache*. Danach richtet sich Protokoll und die Meldung bei
  Rauchalarm.
* **Der Planer liefert seine Begründungen in jeder Sprache mit.** Ohne das
  stünde in einer englischen Karte ein deutscher Satz – der erste Anlauf sah
  genau so aus („since 19:55: zu um Sonnenuntergang"), und halb übersetzt ist
  schlechter als gar nicht.

Der schwierige Teil war nicht die Menge, sondern der Satzbau: „zu um
Sonnenuntergang, spätestens 22:00 wenn morgen schulfrei ist" heißt auf Englisch
„closed at sunset, no later than 22:00 when tomorrow is a day off" – andere
Wortstellung, andere Fügung. Deshalb steht je Sprache die ganze Vorlage da,
nicht eine Wörterliste.

Gebaut ohne `gettext`: Die Texte stehen als Tabelle je Sprache, damit eine
dritte Sprache **nur eine Tabelle** ist – keine Werkzeugkette, keine
`.po`-Dateien, kein Übersetzungslauf beim Bauen. Deutsch ist die Rückfallebene;
fehlt ein Schlüssel, kommt der deutsche Text und nie der nackte Schlüssel.
Drei Tests wachen darüber, dass die Tabellen dieselben Schlüssel und dieselben
Platzhalter führen – die zwei Fehler, die man sonst erst bemerkt, wenn jemand
die Sprache spricht.

**Die Oberfläche des Add-ons ist noch deutsch** – sie folgt als Nächstes.

## 2.14.0 – 28.08.2026

**Handbuch und README auf den Stand gebracht.** Kein neues Verhalten, aber die
Beschreibung stimmte an mehreren Stellen nicht mehr mit dem überein, was das
Add-on tut.

* **Das Handbuch war durcheinandergeraten.** Fünf Abschnitte über die Karte –
  Bedienung mit dem Finger, Zimmer, Schriftgröße, Einstellen ohne YAML, und was
  „Automatik aus" bedeutet – standen **vor** der Überschrift *Die Karte* und
  hingen damit unter *Entitäten*. Ein Nebenschaden der vielen Einschübe der
  letzten Tage.
* Die **Entitätentabelle** war unvollständig: Es fehlten der Hitzeschutz je
  Rollo und der Trockenlauf-Melder. Dazu ein Absatz darüber, dass eine
  entity_id einmal beim Anlegen entsteht und **keiner Umbenennung folgt** – der
  Fehler, der gestern einen Schalter von der Karte verschwinden ließ.
* Die **Regelkette** kannte die Obergruppen noch nicht: Rang 3 nennt jetzt auch
  „Gruppe ist aus" und „Freigabeschalter der Gruppe steht auf aus".
* Die **Kartenbeschreibung** beschrieb noch die Raumblöcke von vor 2.12, samt
  der Beispielkonfiguration mit `raeume:`. Jetzt Obergruppen, `gruppen:`,
  `textgroesse:` und `zimmer:`.
* Die **README** war beim Stand von Anfang der Woche stehengeblieben: keine
  Obergruppen, keine Fluchtweg-Freigabe, kein Karteneditor.

## 2.13.2 – 28.08.2026

**Die Zimmer-Zwischenüberschriften rissen kachelgroße Löcher in die Karte.**

Die Überschrift stand als Gitterzelle über alle Spalten im selben Raster wie
die Kacheln – und erbte damit deren Zeilenhöhe, weil `grid-auto-rows:1fr` alle
Zeilen gleich hoch macht. Zwischen „KÜCHE" und der Küchenkachel klaffte eine
ganze Kachelhöhe. Jetzt bekommt jedes Zimmer sein **eigenes** Raster: Die
Kacheln eines Zimmers sind gleich hoch, alle fluchten in denselben Spalten, und
die Überschrift ist so hoch wie eine Überschrift.

**Im Gruppen-Reiter klebte das Auswahlfeld am Rand.** Rechts ist jetzt Luft.

## 2.13.1 – 28.08.2026

**Das Zimmer lässt sich in der Karte wählen.** Neue Option `zimmer`, auch im
Editor: als **Schild** am Namen (Vorgabe, entfällt wo der Name es schon nennt),
als **Zwischenüberschrift** in der Gruppe, oder **gar nicht**. Die
Zwischenüberschrift trennt sauber, kostet aber Platz – jedes Zimmer fängt eine
neue Reihe an.

**Der Gruppen-Reiter war unaufgeräumt.** Das Auswahlfeld „verschieben nach …"
lief über die ganze Breite und zog die Zeile auseinander; ein Feld, das man
selten braucht, soll nicht das Bild bestimmen. Feste Breite, Pfeile daneben,
Trennlinien über die ganze Zeile.

## 2.13.0 – 28.08.2026

**Die Karte lässt sich jetzt in der Oberfläche einstellen, ohne YAML.**

Unter *Karte bearbeiten* steht ein Editor: Überschrift, Schriftgröße, sechs
Schalter für das, was die Karte zeigt, und eine Liste der Gruppen zum An- und
Abhaken **und Sortieren**. Die Reihenfolge dort gilt vor der aus dem Add-on;
hakt man alle an, ohne zu verschieben, folgt die Karte wieder dem Add-on.

Gebaut ohne Fremdbausteine – ein Editor, der `ha-form` oder Lit voraussetzt,
geht kaputt, sobald Home Assistant daran etwas ändert.

* Neue Kartenoption **`gruppen`**: Sie bestimmt zugleich, welche Gruppen
  erscheinen und in welcher Reihenfolge. Der Vorgänger `raeume` gilt weiter.
* **Innerhalb einer Gruppe zählt jetzt der Platz aus dem Add-on.** Wer die
  Rollos im Reiter *Gruppen* sortiert, meint damit die Karte – vorher fiel sie
  aufs Alphabet zurück, und das Sortieren blieb wirkungslos.
* Der Testfall gegen Backticks im Stilblock war zu grob geworden: Er fand den
  `<style>` des Editors statt den der Karte. Er prüft jetzt genau den Block von
  `_stil()` – nachgewiesen, dass er einen echten Fehler weiterhin fängt.

## 2.12.1 – 28.08.2026

**Aus einer Gruppe heraus ließ sich kein Rollo hinzufügen.**

Zuweisen ging nur über den Abschnitt *Noch in keiner Gruppe* weiter unten – und
der verschwand, sobald alle Rollos zugeordnet waren. Wer dann eine neue Gruppe
anlegte, stand vor „Noch kein Rollo in dieser Gruppe" ohne einen Weg, das zu
ändern. Jetzt hat jede Gruppe ein Feld **Rollo in diese Gruppe legen**; steckt
das Rollo schon woanders, steht das dabei und es wird umgehängt statt kopiert.

## 2.12.0 – 27.08.2026

**Obergruppen: eine Ebene über den Rollos, mit eigenem Zeitplan und eigener
Freigabe.**

Bisher war der Zeitplan die heimliche Gruppe – wer wissen wollte, was
zusammengehört, musste nachsehen, welche Rollos auf denselben Plan zeigen. Das
stand nirgends und ging nicht, solange eine Gruppe ohne Plan auskommen soll.

* Eine Gruppe **legt dazu, sie ersetzt nichts**: Jedes Rollo behält seinen
  eigenen Zeitplan. Hat die Gruppe zusätzlich einen, gelten dessen Punkte für
  alle ihre Rollos – wie früher „Rollo schliessen EG" neben den
  Einzelautomationen.
* Die Gruppe trägt den **Freigabeschalter**. Steht er aus, fährt der Planer
  keines ihrer Rollos nach Plan; von Hand und bei Rauchalarm fahren sie weiter.
* Neuer Reiter **Gruppen**: anlegen, benennen, Rollos hineinschieben, beides
  sortieren. Die Reihenfolge dort ist die Reihenfolge in der Karte. Ein Knopf
  macht aus den **Etagen** von Home Assistant einen Vorschlag – ohne
  Gruppenzeitplan, er ändert also kein Verhalten.

**Der Hitzeschutz lässt sich je Rollo schalten**, nicht nur insgesamt: ein
eigener Schalter in Home Assistant und ein Knopf in der Kachel. Der Knopf
erscheint nur, wo eine Himmelsrichtung hinterlegt ist – ohne sie kann der
Hitzeschutz nichts tun.

**Die Karte hat zwei Ebenen und endlich gleich breite Kacheln.** Vorher war
jeder Raum ein Block, und ein Block war so breit, wie er Kacheln hatte: bei
1280 px war die Kachel eines Ein-Rollo-Zimmers 619 px breit, die daneben 413.
Jetzt ist die Obergruppe die Überschrift über die volle Breite, darunter läuft
**ein** Raster – von 400 px bis 1820 px sind alle Kacheln gleich breit und
gleich hoch, ohne Überlauf. Der Raum ist nicht verschwunden, er steht als
Schild an der Kachel, wo der Name ihn nicht schon nennt.

**Ein umbenannter Schalter verschwand von der Karte.** Aus „Erdgeschoss" wurde
„EG öffnen", und er war weg. Die entity_id entsteht **einmal** beim Anlegen aus
dem Namen und ändert sich beim Umbenennen nie – der Anzeigename schon. Das
Add-on rechnete sie jedes Mal aus dem aktuellen Namen zurück und zeigte damit
auf eine Entität, die es nicht gab. Jetzt schlägt es die echte nach, statt sie
zu raten.

## 2.11.0 – 27.08.2026

**Aufgeräumte Wortwahl: „aus" heißt die Automatik, nicht das Rollo.**

An drei Stellen behauptete das Add-on, das Rollo sei abgeschaltet, während in
Wirklichkeit nur seine Automatik aus war. Das Rollo hängt weiter da, meldet
seine Stellung, lässt sich von Hand fahren und geht bei Rauchalarm trotzdem
auf. Wer das liest, sucht nach einem Defekt, den es nicht gibt.

* In der Kachel: *„Rollo ist abgeschaltet"* → **„Automatik für dieses Rollo
  ist aus"**, das Schild *aus* → **Automatik aus**.
* In der Kopfzeile: *„9 von 10 Rollos aktiv"* → **„9 von 10 Rollos mit
  Automatik"** (und „Alle Rollos mit Automatik", wenn keins fehlt).
* Im Add-on am Rollo: *„Rollo ist eingeschaltet"* → **„Automatik für dieses
  Rollo"**, mit einem Satz darunter, was Ausschalten wirklich bedeutet.
* Und die Automatik insgesamt heißt jetzt **„Automatik ist insgesamt aus"**,
  damit sie nicht mit der eines einzelnen Rollos zu verwechseln ist.

**Die Begründung in der Kachel sagt jetzt, wann sie gilt.**

*„zu um Sonnenuntergang, spätestens 22:00 … dann offen um 10:00 Uhr"* las sich
wie eine Folge von zwei Vorhaben – dabei ist das erste längst geschehen und nur
das zweite steht bevor. Jetzt steht dort **„seit 20:09 Uhr: zu um
Sonnenuntergang …"**. Die Uhrzeit ist der Zeitpunkt des geltenden
Schaltpunkts; sie erscheint nur beim Zeitplan, denn „Fenster offen" oder
„Handbetrieb bis 08:00" sind schon von sich aus eindeutig.

## 2.10.0 – 27.08.2026

**Größere Tasten, und „Automatik aus" sieht nicht mehr nach „nicht verfügbar" aus.**

* **Die Pfeiltasten sind jetzt gut 40 px statt 24 px** (34 px mal Textskala,
  wächst also mit der Schrift mit). Am Wandtablett waren sie kaum zu treffen.
  Dazu eine Rückmeldung beim Drücken – auf einem Tablett gibt es kein „hover".
* **Ein Rollo mit abgeschalteter Automatik** bekommt einen gestrichelten Rand
  und das Schild *aus*; gedimmt wird nur noch die Begründung und der nächste
  Schaltpunkt. Vorher lag die halbe Deckkraft über der ganzen Kachel — Stellung,
  Name und Tasten inbegriffen. Das las sich, als wäre das Rollo weg, obwohl es
  sich weiter von Hand fahren lässt.
* In der Fußzeile schrumpft bei Enge jetzt der **Zeitplanname** und nicht mehr
  die **Uhrzeit**: Die Uhrzeit ist die Tatsache, der Name die Beschriftung.

Nachgemessen gegen 2.9.0 von 400 px bis 1820 px: gleiche Kachelhöhen wie vorher,
kein zusätzliches Abschneiden, kein Überlauf.

## 2.9.0 – 27.08.2026

**Die Karte lässt sich größer stellen — und ist es ab jetzt von Haus aus.**

Am Wandtablett im Flur war sie kaum zu lesen. Neue Kartenoption
`textgroesse: klein | normal | gross | riesig` (oder eine Zahl von 0,7 bis
2,5); **Vorgabe ist jetzt „gross" (1,2×)**, *normal* ist die bisherige
Darstellung.

Mitskaliert wird alles: Schrift, Symbole, die Mindestbreite einer Kachel und
die Umbruchschwelle. Sonst wüchse der Text in eine gleich breite Kachel hinein
und jeder zweite Name stünde abgeschnitten da.

**Zwei alte Layoutfehler dabei gefunden**, beide unabhängig von der Schriftgröße:

* **Die Karte kannte kein `box-sizing`.** Rand und Polster einer Kachel kamen
  zur Spaltenbreite hinzu, also stand jede Kachel 24 px über den Kartenrand
  hinaus, sobald die Karte schmal wurde. Ein Schattenbaum erbt keinen Reset von
  der Seite.
* **Die Gitterspalte konnte nicht schrumpfen.** `1fr` heißt `minmax(auto, 1fr)`
  und geht nie unter den Mindestinhalt — die Kachel stand über den Rand hinaus,
  statt ihren Text abzuschneiden. Jetzt `minmax(0, 1fr)`.

Geprüft von 320 px bis 1820 px: kein Überlauf mehr, und ab 480 px sind alle
Kacheln wieder exakt gleich hoch.

## 2.8.0 – 27.08.2026

**Der eigene Melder des Planers zählte als Rauchmelder – der erste Alarm hätte
nie geendet.**

Das Add-on legt über MQTT einen `binary_sensor` „Rollos Rauchsperre" an. Die
Melder-Erkennung geht über den Namen, und in „Rauchsperre" steckt „Rauch": Der
eigene Melder galt als Rauchmelder. Er geht bei Alarm an — und hielt damit den
Alarm am Leben, auch lange nachdem der echte Melder wieder aus war. Der Planer
hätte ab dem ersten Rauchalarm **nie wieder einen Zeitplan ausgeführt**, und
die Fluchtweg-Freigabe hätte weiter nachgefasst. Aufgefallen wäre es erst im
Ernstfall. Eigene Entitäten sind jetzt aus jeder Melder- und Kontaktliste
ausgeschlossen, auch aus einer ausdrücklichen Auswahl.

**Die Meldung sagt jetzt, wo es brennt.**

* **In der Überschrift steht der Ort** – „Rauchalarm: Flur 1.OG" –, denn auf
  einem Sperrbildschirm liest man die erste Zeile und sonst nichts. Genommen
  wird der **Bereich** aus Home Assistant; der sagt mehr als „RM Flur OG
  Alarmstatus" und stimmt auch nach einem Umbenennen noch.
* **Mehrere Melder werden alle genannt**, bis zu vier Orte, danach „und N
  weitere". Vorher waren es stumm die ersten drei.
* **Was schiefging, steht oben**: nicht erreichbar, bleibt zu, ausgenommen –
  und erst dann, was aufgefahren ist. Wer im Ernstfall aufs Telefon sieht, muss
  wissen, welches Fenster zu bleibt, nicht welche neun offen sind.

## 2.7.0 – 27.08.2026

**Der Rauchalarm hat einen eigenen Reiter und einen eigenen Meldeweg.**

* **Eigener Reiter.** Sperre, Fluchtweg-Freigabe, Melder und Meldeweg standen
  als ein Abschnitt unter vielen in den Einstellungen — zwischen Ferienkalender
  und Urlaubssimulation. Für die eine Funktion, die im Ernstfall zählt, ist das
  der falsche Ort. Jetzt steht sie zwischen *Schalter* und *Einstellungen*, mit
  einer **Ampelzeile** ganz oben: Sperre, Freigabe, Trockenlauf, Meldeweg. Rot
  heißt: Hier fährt im Ernstfall nichts, oder es erfährt niemand.
* **Eigener Meldeweg.** Bisher hing die Alarmmeldung am Meldeweg des Wächters.
  Wer den stummschaltet, weil ihn die Hinderniswarnungen nerven, will deswegen
  keinen Brand verschweigen. Ist kein eigener angehakt, gilt weiterhin der des
  Wächters — lieber die falsche Zustellart als gar keine Meldung.
* **Gemeldet wird jetzt jeder Rauchalarm**, auch bei abgeschalteter Freigabe.
  Dann sagt die Nachricht eben, dass kein Rollo aufgefahren ist; das ist die
  wichtigere Auskunft, nicht die unwichtigere.
* **Probemeldung senden.** Der einzige Weg, den Ernstfall vorher einmal zu
  sehen, ohne einen Melder anzuzünden. Gefahren wird dabei nichts.

**Im Protokoll stand bei „von Hand gestellt" die Entitäts-ID statt des Namens.**
Das war keine Schönheitsfrage: Die Kennungen stammen aus dem alten Haus und
zeigen fast alle auf ein anderes Zimmer, als ihr Name sagt —
`cover.finns_rollo` ist das Schlafzimmerfenster, `cover.rollo_terrassentur` die
Schlafzimmer-Balkontür, `cover.lunas_rollo` das Bürorollo. Eine Kennung im
Protokoll war damit keine Auskunft, sondern eine Falschauskunft. Jetzt steht
dort der Anzeigename, und alte Einträge werden beim Anzeigen mit dem heutigen
Namen nachgeschlagen.

## 2.6.0 – 27.08.2026

**Die Ausrichtung ist jetzt eine Gradzahl, keine Auswahl aus acht Richtungen.**

Das Feld *Zeigt nach* war ein Auswahlmenü mit Nord, Nordost, Ost … — und damit
eine Falle: Stand am Rollo ein Wert dazwischen (aus dem Gebäudeumriss gerechnet
etwa 166°), passte keine Option. Das Menü zeigte „unbekannt“, und wer den
Dialog nur öffnete und speicherte, **löschte die Ausrichtung stillschweigend**.

Jetzt steht dort ein Zahlenfeld von 0 bis 359 mit dem Himmelsstrich daneben
(„Zeigt nach (SSO)“). Krumme Werte sind der Normalfall — ein Haus steht selten
genau nach der Himmelsrichtung, und die 22 Grad zwischen Süd und SSO sind am
Nachmittag eine gute Stunde Sonne. In der Rolloliste steht die Richtung
entsprechend als „SSO 166°“ statt nur „Süd“.

Unverändert, aber jetzt in der Anleitung beschrieben: **Wie weit beim Beschatten
zugefahren wird**, steht unter *Einstellungen → Hitzeschutz* für alle Rollos und
im Rollo-Dialog unter *Stellung* für ein einzelnes. Beide folgen der
eingestellten Zählweise.

## 2.5.0 – 27.08.2026

**Die Melder lassen sich jetzt auswählen.** Bisher stand unter *Rauchalarm* nur
der Satz, dass ohne Auswahl alle Melder gelten – auswählen konnte man keine.
Wer den Fluchtweg an bestimmte Melder hängen will, kann das nun.

Keiner angehakt heißt weiterhin **alle**, und das bleibt die Vorgabe: Ein
Melder, den man beim Auswählen übersieht, löst dann trotzdem aus. Wer auswählt,
sollte wissen, warum – ein nicht angehakter Melder schlägt für den Planer
niemals an.

## 2.4.1 – 27.08.2026

**Der Trockenlauf meldete Handbetrieb, den es nicht gab.**

Er schickt keinen Fahrbefehl hinaus – das stimmte und stimmt. Er merkte sich
aber trotzdem ein *Ziel*, als hätte er gefahren. Fünf Minuten später stand das
Rollo woanders als dieses Ziel, und die Handbetriebserkennung schloss daraus,
jemand sei am Schalter gewesen: Der Planer meldete „von Hand gefahren“ für ein
Rollo, das niemand angefasst hat, und legte sich selbst für zwölf Stunden
still. Genau die Auskunft, für die man einen Trockenlauf laufen lässt – *was
täte er jetzt* – war damit verdeckt.

* **Ein Ziel wird nur noch gemerkt, wenn wirklich gefahren wurde.**
* **Im Trockenlauf wird kein Handbetrieb mehr erkannt.** Dort bewegt jedes
  Rollo etwas anderes; die Schlussfolgerung ist dort wertlos. Dasselbe gilt für
  ein Rollo auf *beobachten* – das hatte denselben Fehler.
* Im Add-on-Protokoll heißt es jetzt „*wäre* gefahren“, solange der
  Trockenlauf läuft.

Unverändert richtig: Es geht weiterhin kein Befehl hinaus (auch die
Fluchtweg-Freigabe nicht), das Protokoll führt mit, und beim Ausschalten wird
der Plan sofort durchgesetzt.

## 2.4.0 – 27.08.2026

**Die Fluchtweg-Freigabe: Bei Rauchalarm fährt der Planer jedes Rollo auf.**

Bisher tat er bei Rauch das Richtige, aber nur die Hälfte – er hielt still,
damit eine fremde Automation den Fluchtweg öffnen konnte. Jetzt öffnet er ihn
selbst.

* **Sie steht über allem.** Über der Automatik, über einem abgeschalteten
  Zeitplan, über „nur schließen“, „von Hand“ und „beobachten“. Ein Schlafzimmer
  ohne Zeitplan ist kein Zimmer, aus dem man nicht herauskommen soll. Wer ein
  einzelnes Rollo ausnehmen will – eines vor einem Regal etwa –, schaltet
  *Bei Rauchalarm auffahren* an diesem Rollo ab.
* **Sie fasst nach.** Ein Rollo, das nach der Fahrzeit immer noch zu ist,
  bekommt den Befehl erneut, bis zu dreimal. Danach gilt es als blockiert und
  wird in Ruhe gelassen, statt im Minutentakt gegen ein Hindernis zu fahren.
* **Der Trockenlauf gilt auch hier.** Solange er an ist, wird nur gemeldet.
* **Eine Meldung je Alarm**, nicht je Takt – mit dem, was *nicht* erreichbar
  war, an erster Stelle.
* Neu: `switch.rolloplaner_fluchtweg` und
  `binary_sensor.rolloplaner_fluchtweg_offen`. In der Karte ein vierter Knopf,
  ein Alarmbanner und – falls die Freigabe ausgeschaltet ist – eine Warnung,
  damit ein Fehlgriff nicht bis zum Ernstfall unbemerkt bleibt.

Die Rauchsperre bleibt, was sie war: Sie verhindert, dass ein fälliger
Schaltpunkt den gerade geöffneten Fluchtweg wieder zumacht. Eine eigene
Automation „bei Rauch alle Rollos hoch“ kann jetzt entfallen.

## 2.3.0 – 26.08.2026

**Alle Kacheln sind gleich hoch, und ein Schalter, der an ist, ist grün.**

* **Gleiche Höhe, überall.** Vorher richteten sich die Kacheln nur innerhalb
  ihrer Reihe aneinander aus – ein Rollo mit zwei Schaltern zog seine ganze
  Reihe in die Länge, und in der schmalen Ansicht war jede Kachel wieder
  anders hoch. Jetzt hat jeder Abschnitt seinen festen Platz: die Begründung
  zwei Zeilen, die Schalter eine Reihe, die Fußzeile unten. Auch ein Rollo
  ohne Schalter behält die Zeile – leer, aber vorhanden.
* **Grün heißt an.** Die drei Knöpfe oben (Automatik, Hitzeschutz, Urlaub)
  waren in der Themenfarbe eingefärbt, die Schalter in den Kacheln in Grün.
  Zwei Farben für dieselbe Aussage sind eine zu viel.
* **Schalter stauchen sich, statt umzubrechen.** In einer schmalen Kachel
  schneidet ein Schaltername jetzt ab (der volle steht im Tooltip), statt die
  Kachel wachsen zu lassen.
* **Kürzere Schalternamen.** Trägt ein Rollo zwei Schalter derselben Wirkung,
  stand bisher der ganze Schaltername dabei – in der Kachel „Terrassentür“
  also „schließen: Terrassentür schliessen“. Der Name des Rollos fällt jetzt
  weg, er steht schon in der Überschrift.

## 2.2.0 – 26.08.2026

**Die Karte zeigt wieder Kacheln, auch auf breiten Ansichten.** Die
Zeilendarstellung war ein Umweg: Sie füllte zwar die Breite, aber eine Karte
soll wie eine Karte aussehen. Stattdessen ist jetzt **jeder Raum ein Block**,
und die Blöcke fließen nebeneinander – ein Zimmer mit einem Rollo ist ein
schmaler Block, das Wohnzimmer mit dreien ein breiter. Damit bleibt die
Ordnung nach Räumen sichtbar, ohne dass neben jedem kleinen Raum die halbe
Karte leer bliebe.

**Drei Fehler und eine Unklarheit im Add-on:**

* **Die Knöpfe unter *Schalter* taten nichts.** Beim Umbau auf Fassung 2.0
  sind ihre Handler verlorengegangen – anlegen und speichern war schlicht
  nicht möglich.
* **Im Reiter *Zeitpläne* standen nur die gemeinsamen.** Wer ihn öffnet, sucht
  alle: Jetzt stehen dort auch die Rollos mit eigenem Zeitplan und die ohne –
  mit einem Knopf, der direkt ins Rollo führt.
* **„Auswahl hinzufügen“ erklärte sich nicht.** Der Text sagt jetzt, wozu die
  beiden Arten da sind, und nennt je ein Beispiel aus einer echten Anlage:
  Ein/Aus für „Obergeschoss schließen“, eine Auswahl für „Terrassentür
  schließen“ mit *normal / 24 Uhr / aus*.

## 2.1.2 – 26.08.2026

**Die Stellung fiel rechts aus der Karte heraus.** Die Spalten der
Zeilendarstellung waren mit der Breitenangabe „auto“ gesetzt – und die
schrumpft nicht. Eine Spalte mit langem Inhalt, etwa die Auswahl der
Terrassentür, machte das Raster damit breiter als die Karte selbst. Jetzt darf
jede Spalte schrumpfen, und was nicht passt, wird abgeschnitten statt
überzulaufen.

Die Spalten sind außerdem gleichmäßiger verteilt: Vorher nahm der Text allen
freien Platz und drängte alles Übrige an den rechten Rand.

## 2.1.1 – 26.08.2026

**Rollos ohne Zeitplan standen in Home Assistant als „nicht verfügbar“ da.**
Ihr Sensor bekam den Textwert „unknown“, und damit legt Home Assistant einen
Sensor mit Einheit gar nicht erst an – die Entität blieb leer, obwohl mit dem
Rollo nichts war.

Jetzt zeigt der Sensor in dem Fall, **wo das Rollo steht**. Bei einem Rollo
ohne Plan ist das ohnehin die einzige sinnvolle Auskunft.

**Die Rolloliste im Add-on ist eine Tabelle statt vieler.** Vorher stand über
jedem Raum eine eigene Kopfzeile, und weil jede Tabelle ihre Spalten selbst
ausmisst, sprangen die Spaltenbreiten von Raum zu Raum. Jetzt gibt es eine
Kopfzeile und Raum-Zwischenzeilen.

**Die Zeilendarstellung der Karte fluchtet.** Sie war als Flexbox gebaut, in
der sich der Textteil über den ganzen freien Platz dehnte und alles Übrige an
den rechten Rand drückte – dazwischen klaffte ein Loch von tausend Pixeln.
Jetzt ist es ein Raster mit festen Spalten, in dem nur die Textspalte wächst.
Name und Begründung stehen nebeneinander statt untereinander, was die Zeile
halb so hoch macht.

## 2.1.0 – 26.08.2026

**Die Karte richtet sich nach ihrer Breite.** In einer Ansicht über die volle
Fensterbreite zerfielen zehn Rollos in sechs schmale Spalten mit großen Löchern
dazwischen – jede Kachel quetschte ihren Text in drei Zeilen, während rechts
anderthalbtausend Pixel leer blieben.

Jetzt misst die Karte ihren eigenen Platz:

* **schmal** (eine Dashboard-Spalte) – Kacheln untereinander
* **mittel** (ab 580 px) – zwei nebeneinander
* **breit** (ab 880 px) – eine **Zeile je Rollo** über die ganze Breite

Zeilen sind bei viel Breite das Richtige: Man liest sie von links nach rechts
wie eine Liste, statt sechs Kacheln abzusuchen.

Zwei Dinge, die dabei zu lernen waren: Eine Container-Query fragt immer den
nächsten Vorfahren mit `container-type` – ein Element kann nicht sein eigener
Container sein. Und bei gleicher Spezifität gewinnt in CSS die spätere Regel,
also müssen die Queries **nach** den Grundregeln stehen.

**Neu geprüft**: Ein Testfall wacht jetzt darüber, dass im Stilblock der Karte
kein Backtick steht. Das CSS lebt in einem JavaScript-Template-String; ein
Backtick in einem Kommentar beendet ihn, und die Karte bleibt leer. Beim Bauen
ist mir das dreimal passiert – deshalb steht es jetzt in den Tests und nicht
in einem Merkzettel.

## 2.0.1 – 26.08.2026

**Neue Betriebsart „nur von Hand“.** Nicht jedes Rollo braucht einen Zeitplan –
die beiden im Schlafzimmer etwa fahren nur bei Rauch und im Urlaub, und das ist
so gewollt. Bisher stand dafür dauerhaft eine Warnung da („Kein Schaltpunkt –
dieses Rollo fährt nie“), und in so einer Dauerwarnung geht die eine unter, die
zählt.

Jetzt sagt die Betriebsart, dass es Absicht ist: Der Planer führt das Rollo
weiter mit – Anzeige, Wächter, Rauchsperre, Fahren von Hand über die Karte –
aber er steuert es nicht nach der Uhr. Die Übernahme setzt sie von selbst für
jedes Rollo, zu dem sich keine Automation findet.

## 2.0.0 – 26.08.2026

**Die Steuereinheit ist jetzt das Rollo, nicht der Raum.**

Bis hierher war der Raum die Einheit, und das war von Anfang an falsch: Das
Modell stammte aus den vorhandenen Automationen statt aus der Frage, wie ein
Rollladenplaner aussehen muss. Die Folgen zogen sich durch alles – Luna hat ein
Fenster *und* eine Balkontür, und der Planer konnte sie nicht unterschiedlich
fahren. Für die Terrassentür musste ein Kunstraum „Wohnzimmer – Terrassentür“
erfunden werden, weil sie einem anderen Regime folgt. Ob Fenster oder Tür hing
am Raum, obwohl im Schlafzimmer beides hängt.

Jetzt führt **jedes Rollo seine eigenen Angaben**: was dahintersteckt (Fenster,
Balkontür, Terrassentür, Dachfenster, Haustür), wohin es zeigt, welcher Kontakt
es sperrt, was „offen“ und „zu“ heißen. Und es folgt einem **benannten
Zeitplan**, den sich mehrere Rollos teilen – oder einem eigenen. Ein Zeitplan
gehört keinem Raum, sondern allen, die ihm folgen; jeder hat einen eigenen
Schalter in Home Assistant.

Der **Raum** kommt aus Home Assistant und steuert nichts mehr. Er ordnet die
Anzeige – er ist der Ort, an dem man ein Rollo sucht.

**Die Übernahme sammelt jetzt je Rollo** und fasst erst danach zusammen, was
identisch fährt. Das ist die Reihenfolge, auf die es ankommt: Wer zuerst
gruppiert und dann die Zeiten sucht, muss für jedes Rollo mit eigenem Regime
eine Ausnahme erfinden. Ein gemeinsamer Zeitplan entsteht nur, wenn ihm
mehrere Rollos folgen.

Die Art wird beim Übernehmen aus dem Namen geraten – und der **Anzeigename
gewinnt gegen die entity_id**: In dieser Anlage heißt die Schlafzimmer-
Balkontür `cover.rollo_terrassentur`, weil das Gerät im alten Haus woanders
hing. Der Name wurde gepflegt, die ID nicht.

**Weiteres:**

* Neue Reiter **Rollos** und **Zeitpläne**; die Übersicht ordnet nach Raum.
* Die Selbstauskunft meldet **Türen ohne Kontakt** – an einer Balkontür ist der
  kein Zubehör, sondern der Unterschied zwischen „zu“ und „ausgesperrt“.
* Als „geteilt“ gilt ein Schalter, der über **einen Raum hinaus** wirkt. Dass
  einer beide Rollos in Lunas Zimmer betrifft, überrascht niemanden.
* Die Urlaubssimulation streut je Rollo, nicht je Zeitplan – sonst führen zwei
  Rollos am selben Plan wieder im Gleichtakt.

**Umstieg**: Eine Konfiguration aus 1.x lässt sich nicht weiterverwenden – ein
Raum mit drei Rollos wusste nicht, welches davon eine Terrassentür ist. Sie
wird unter `/data/config-vor-umbau.json` beiseitegelegt; eingerichtet wird neu
über den Reiter *Einrichtung*.

## 1.6.0 – 26.08.2026

**Geteilte Schalter stehen jetzt oben, nicht in jeder Kachel.** „Obergeschoss
schließen“ ist *ein* Schalter für Luna und Nele – in beiden Kacheln sah er aus
wie ein eigener, und wer ihn bei Nele ausschaltete, wunderte sich, warum er bei
Luna auch weg war. Solche Schalter stehen jetzt einmal unter **Gilt für mehrere
Räume**; in der Kachel bleibt nur, was allein diesem Raum gehört.

**Einheitliche Beschriftung.** „den ganzen Raum“ heißt jetzt *alles* und steht
in derselben Reihe wie *öffnen* und *schließen* – es ist derselbe Mechanismus,
nur ein anderer Umfang. Haben zwei Schalter eines Raumes dieselbe Wirkung,
kommt ihr Name dazu, damit man sie auseinanderhalten kann.

**Aufgeräumtes Layout.** Jede Kachel hat jetzt dieselbe Zeilenfolge – Bild,
Name und Stellung; Begründung; Schalter; Fußzeile mit dem nächsten Wechsel und
den Knöpfen. Die Kacheln einer Reihe sind gleich hoch, und die Fußzeile sitzt
unten, statt auf halber Strecke zu hängen. Chips sehen oben und in der Kachel
gleich aus.

**Neu in der Selbstauskunft**: stillgelegte Schaltpunkte. Zeigt die Bedingung
eines Punktes auf einen Schalter, der aus ist und sonst nirgends gebraucht
wird, greift dieser Punkt nie – im Zeitplan sieht man ihm das nicht an.

## 1.5.1 – 26.08.2026

**Die eigenen Schalter standen in Home Assistant auf „unknown“.** Ein
MQTT-Switch erwartet von Haus aus `ON`/`OFF` in Großbuchstaben; der Planer
führt seine Zustände klein. Die Discovery sagt das jetzt dazu.

## 1.5.0 – 26.08.2026

**Der Planer bringt seine Schalter jetzt selbst mit.** Bisher hingen die
Zeitpläne an fremden `input_boolean`- und `input_select`-Helfern – die gab es
in diesem Haus schon. Nach einer Neuinstallation gibt es sie **nicht**, und ein
Zeitplan, der auf eine Entität zeigt, die niemand angelegt hat, schaltet nie.

Unter dem neuen Reiter **Schalter** legt der Planer eigene an und
veröffentlicht sie über MQTT: als `switch.` (an/aus) oder als `select.`
(mehrere Stellungen, etwa *normal / 24 Uhr / aus*). Ihren Stand kennt er
selbst, er überlebt einen Neustart, und ein gelöschter Schalter verschwindet
auch wieder aus Home Assistant.

* Die **Übernahme** legt sie gleich mit an: gleicher Name (ohne die Vorsilben
  „Helfer –“ und „Rollosteuerung –“, aus denen sonst hässliche Entity-IDs
  würden), gleiche Stellungen, übernommener Stand.
* Für eine bestehende Einrichtung gibt es den Knopf **Fremde Helfer ersetzen**.
  Die alten Helfer bleiben liegen – sie werden danach nur nicht mehr gebraucht.
* Zugeordnet wird über die Quell-Entität, nicht über den Namen: Zwei
  verschiedene Helfer können gleich heißen, und die dürfen nicht zu einem
  Schalter verschmelzen. Ein zweiter Durchlauf legt deshalb nichts doppelt an.
* Die ID hängt **nicht** am Namen. Ein umbenannter Schalter behält seine
  Entität, statt als neue aufzutauchen und die alte als Karteileiche
  stehenzulassen.
* Die Selbstauskunft meldet, wenn ein Zeitplan noch an einem fremden Helfer
  hängt – oder ein eigener Schalter nirgends verwendet wird.

Ein Schalter, der noch als Bedingung in Gebrauch ist, lässt sich nicht löschen:
Eine Bedingung auf einen Schalter, den es nicht gibt, trifft nie zu, und der
Schaltpunkt wäre stumm.

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
