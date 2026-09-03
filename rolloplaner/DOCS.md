# Rolloplaner

Rollladensteuerung für Home Assistant: je Rollo ein Zeitplan, der nach Uhrzeit
**oder** nach dem Stand der Sonne schaltet, Obergruppen für alles, was
zusammengehört, Hitzeschutz nach Sonnenrichtung, Urlaubssimulation, eine
Fenstersperre – und bei Rauchalarm eine Fluchtweg-Freigabe, die jedes Rollo
auffährt.

## Wie der Planer denkt

**Die Steuereinheit ist das Rollo, nicht der Raum.** Das ist die Entscheidung,
aus der alles Übrige folgt – und sie ergibt sich aus jedem Haus, in dem ein
Zimmer ein Fenster *und* eine Balkontür hat. Wer den Raum steuert, kann die
Balkontür nicht offen lassen, während das Fenster zufährt, und muss für jedes
Rollo mit eigenem Regime einen Kunstraum erfinden.

Jedes Rollo führt deshalb seine eigenen Angaben:

* **was dahintersteckt** – Fenster, Balkontür, Terrassentür, Dachfenster, Haustür
* **wohin es zeigt** – die Himmelsrichtung für den Hitzeschutz
* **welcher Kontakt es sperrt** – damit niemand ausgesperrt wird
* **was „offen“ und „zu“ heißen** – nicht jeder Antrieb fährt bis zum Anschlag

Und es folgt einem **benannten Zeitplan**, den sich mehrere Rollos teilen –
oder einem eigenen. Ein Zeitplan gehört keinem Raum, sondern allen, die ihm
folgen.

Darüber liegt die **Obergruppe** – bei uns die Etage. Sie ersetzt nichts: Jedes
Rollo behält seinen Zeitplan. Sie kann zusätzlich einen eigenen haben, der für
alle ihre Rollos gilt, und sie trägt den Freigabeschalter für den ganzen
Schnitt. Siehe [Obergruppen](#obergruppen).

**Der Raum** kommt aus Home Assistant und steuert nichts. Er ordnet die
Anzeige: Er ist der Ort, an dem man ein Rollo sucht.

## Einrichten

1. Add-on starten. Es beginnt im **Trockenlauf**: Es rechnet, protokolliert –
   und fährt nichts. So lässt sich alles in Ruhe prüfen.
2. Reiter **Einrichtung** öffnen. Der Planer liest `automations.yaml` und
   schlägt vor, was er dort findet – je Rollo die Schaltzeiten, und für Rollos
   mit gleichem Muster einen gemeinsamen Zeitplan. Prüfen, abhaken, anlegen.
3. Im Reiter **Übersicht** eine Weile mitlesen. Jedes Rollo sagt, was es tun
   würde und warum.
4. Wenn es stimmt: **Trockenlauf** in den Einstellungen ausschalten. Der
   Planer setzt den geltenden Stand dann sofort durch.
5. Erst danach die alten Automationen abschalten – nicht vorher, sonst steht
   das Haus zwischendurch ohne Steuerung da. Die Selbstauskunft unter
   *Einrichtung* zeigt, welche noch laufen.

**Zwei Automationen sollen bleiben** und werden vom Planer bewusst nicht
angetastet: die Notöffnung bei Rauch und die Kopplung an den Urlaubsschalter,
sofern sie über Melder auslösen statt über die Uhr. Der Planer weicht ihnen
aus (siehe *Rauchsperre*).

## Eigene Schalter

Unter *Schalter* legt der Planer eigene Bedienelemente an und veröffentlicht
sie über MQTT:

* **Schalter** – kennt an und aus, wird `switch.rolloplaner_<name>`
* **Auswahl** – mehrere Stellungen, wird `select.rolloplaner_<name>`

Sie gehören dem Planer: Er legt sie an, kennt ihren Stand (der einen Neustart
überlebt) und räumt sie wieder ab, wenn man sie löscht. Damit hängt kein
Zeitplan an Helfern, die jemand vorher von Hand anlegen müsste – nach einer
Neuinstallation gäbe es die nicht.

In einem Zeitplan stehen sie als
Bedingung an einem Schaltpunkt. Sie tauchen in der Lovelace-Karte bei dem Rollo
auf, dessen Schaltpunkte an ihnen hängen, und lassen sich dort bedienen.

Wer eine bestehende Einrichtung übernommen hat, findet unter *Schalter* den
Knopf **Fremde Helfer ersetzen**: Der Planer legt für jeden benutzten
`input_boolean` und `input_select` einen eigenen Schalter an – gleicher Name,
gleiche Stellungen, übernommener Stand – und biegt die Zeitpläne darauf um. Die
alten Helfer bleiben liegen und können danach weg.

Ein Schalter, der noch als Bedingung in Gebrauch ist, lässt sich nicht löschen.
Eine Bedingung auf einen Schalter, den es nicht gibt, trifft nie zu – der
Schaltpunkt wäre stumm, ohne dass es auffiele.

## Obergruppen

Eine Obergruppe liegt **über** den Rollos – bei uns die Etage („Erdgeschoss",
„Obergeschoß"). Sie ersetzt nichts: Jedes Rollo behält seinen eigenen
Zeitplan. Gibt man der Gruppe zusätzlich einen, gelten dessen Schaltpunkte für
alle ihre Rollos, so wie früher eine Automation „Rollo schliessen EG" neben den
Einzelautomationen lief. Welcher Punkt gilt, entscheidet wie immer der zuletzt
fällige.

Die Gruppe trägt außerdem den **Freigabeschalter**: Steht er aus, fährt der
Planer keines ihrer Rollos nach Plan – von Hand und bei Rauchalarm fahren sie
weiter. Bisher hing so eine Freigabe als Bedingung an jedem einzelnen
Schaltpunkt und war nur über Umwege zu erkennen.

Zwei Regeln gelten hart: Ein Rollo gehört in **höchstens eine** Gruppe (sonst
hätte es zwei Zeitpläne, und welcher gilt, wäre Zufall der Speicherreihenfolge),
und eine Gruppe kann nicht auf ein gelöschtes Rollo oder einen gelöschten Plan
zeigen. Ein Rollo ohne Gruppe fährt weiter nach seinem eigenen Zeitplan – ihm
fehlt nur die Obergruppe.

Im Reiter *Gruppen* legt man sie an, benennt sie, schiebt Rollos hinein
(*Rollo in diese Gruppe legen*, direkt an der Gruppe) und sortiert beides. **Die Reihenfolge dort ist die Reihenfolge in der Karte.** Der
Knopf *Vorschlag aus Home Assistant* macht aus den dort gepflegten **Etagen**
einen Anfang – ohne Gruppenzeitplan, er ändert also kein Verhalten.

## Der Zeitplan

Ein Zeitplan ist eine Liste von **Schaltpunkten** – wie am mechanischen
Zeitschaltwerk. Jeder Punkt sagt: ab hier steht das Rollo auf dieser Stellung.
Es gibt keine Endzeiten; der nächste Punkt löst den vorherigen ab. Dadurch kann
keine Lücke entstehen, in der niemand zuständig ist.

| Feld | Bedeutung |
| --- | --- |
| **Auslöser** | Feste Uhrzeit, Sonnenaufgang, Sonnenuntergang oder Dämmerung |
| **Zeit / Versatz** | Die Uhrzeit – oder, bei einem Sonnenauslöser, der Versatz in Minuten |
| **frühestens / spätestens** | Klammern um einen Sonnenauslöser |
| **Stellung** | 0 % = ganz zu, 100 % = ganz offen |
| **gilt** | immer, an Schultagen, an schulfreien Tagen – oder danach, ob **morgen** Schule ist |
| **Wochentage** | An welchen Tagen der Punkt überhaupt zählt |
| **nur wenn** | Bedingungen: Der Punkt gilt nur, wenn alle zutreffen |

Die Klammer ist kein Zierrat. „Bei Sonnenuntergang zufahren, spätestens 20:30“
ist im Juni etwas anderes als im Dezember: Im Sommer geht die Sonne um zwanzig
nach neun unter – ohne die Klammer bliebe das Kinderzimmer bis dahin hell.

**„wenn morgen Schule ist“** klingt umständlich, ist aber genau das, was ein
Kinderzimmer braucht: Wann abends zugefahren wird, hängt nicht am heutigen Tag,
sondern am morgigen.

**Bedingungen** bilden Auswahlhelfer ab. Steht in Home Assistant ein
`input_select` mit den Stellungen *normal / 24 Uhr / aus*, werden daraus zwei
Schaltpunkte mit je einer Bedingung – und bei „aus“ greift keiner, das Rollo
bleibt oben.

## Zählweise der Prozentangaben

Home Assistant zählt **100 % = offen**. Amazon Echo zählt andersherum. Unter
*Einstellungen → Betrieb* lässt sich die Anzeige umdrehen: dann heißt 0 % offen
und 100 % geschlossen.

Umgedreht wird nur, was angezeigt und eingegeben wird. **Gespeichert bleibt
alles in der Zählweise von Home Assistant** – sonst stünde nach jedem
Umschalten jeder Zeitplan auf dem Kopf. „auf“ und „zu“ bleiben ebenfalls, wie
sie sind; die Wörter hängen nicht an der Zählweise, nur die Zahl dazwischen.

Der Wert der Rollo-Sensoren dreht sich mit. Wer in einer Automation eine
verlässliche Größe braucht, nimmt das Attribut `stellung_ha` – das behält immer
die Zählweise von Home Assistant.

## Die Regelkette

Gerechnet wird **je Rollo**, und der erste Treffer gewinnt.

**Betriebsarten** je Rollo: *Plan* (auf und zu), *nur schließen* (öffnet nie von
selbst), *nur von Hand* (kein Zeitplan, und das ist Absicht – der Planer zeigt
es an, überwacht es und fährt es bei Rauchalarm auf, aber nicht nach der Uhr) und *beobachten* (rechnet mit, schaltet nichts – für den Probelauf
eines einzelnen Rollos).

| Rang | Zustand | Was er bedeutet |
| --- | --- | --- |
| 1 | **Fluchtweg** | Ein Melder schlägt an – das Rollo fährt auf |
| 1 | **Rauchsperre** | Alarm, aber dieses Rollo ist von der Freigabe ausgenommen |
| 2 | **aus** | Die Automatik ist abgeschaltet – für dieses Rollo oder insgesamt |
| 3 | **gesperrt** | Der Zeitplan, dem es folgt, ist stillgelegt – oder seine Obergruppe ist aus, oder ihr Freigabeschalter steht auf aus |
| 4 | **Fenster offen** | Ein Kontakt ist offen – es wird nicht zugefahren |
| 5 | **Urlaub** | Urlaubsprogramm statt Zeitplan |
| 6 | **Hitzeschutz** | Die Sonne steht in *diesem* Fenster und es ist warm |
| 7 | **Handbetrieb** | Jemand hat von Hand gefahren |
| 8 | **Zeitplan** | Der Normalfall |

Geschaltet wird **auf der Flanke, nie auf dem Pegel**: Der Planer merkt sich,
welchen Schaltpunkt er zuletzt ausgeführt hat, und rührt sich erst wieder, wenn
ein neuer fällig wird oder eine Bedingung kippt. Ein Thermostat, dem man
denselben Sollwert zum zehnten Mal schickt, tut nichts – ein Rollladen fährt.

Jedes Rollo wird **einzeln** angefahren. Ein Sammelaufruf scheitert an einem
nicht erreichbaren Funkmotor und reißt die übrigen mit.

## Rauchalarm: Fluchtweg und Sperre

Alles dazu steht im **eigenen Reiter *Rauchalarm*** – nicht in den
Einstellungen. Diese Funktion ist zu wichtig, um in einer langen Seite zwischen
Ferienkalender und Urlaubssimulation zu verschwinden. Ganz oben im Reiter zeigt
eine Ampelzeile, ob die Sache scharf ist: Sperre, Freigabe, Trockenlauf,
Meldeweg. Rot heißt: Hier fährt im Ernstfall nichts oder es erfährt niemand.

Zwei Dinge, die zusammengehören. Die **Sperre** sorgt dafür, dass der Planer
nichts mehr zufährt, die **Fluchtweg-Freigabe** dafür, dass überhaupt etwas
aufgeht.

### Die Sperre

Schlägt ein Rauchmelder an, führt der Planer **keinen Zeitplan** mehr aus – auch
nicht, wenn ein Schaltpunkt fällig wird. Nach der Entwarnung bleibt es dabei,
solange der eingestellte Nachlauf läuft. Ohne sie führe der Planer beim nächsten
Takt seinen Abendplan durch und machte den Fluchtweg wieder zu. **Nicht
abschalten.**

Welche Melder auslösen, steht unter *Einstellungen → Rauchalarm*. Keiner
angehakt heißt **alle** `binary_sensor` der Geräteklasse *smoke* – auch
CO-Melder, die als solche eingetragen sind. Das ist die sichere Vorgabe: Ein
Melder, den man beim Auswählen übersieht, löst dann trotzdem aus. Ein nicht
angehakter Melder schlägt für den Planer dagegen niemals an.

### Die Freigabe

Schlägt ein Melder an, fährt der Planer **jedes** Rollo auf. Drei Dinge
unterscheiden das vom gewöhnlichen Fahren:

**Es steht über allem.** Über der Automatik, über einem abgeschalteten
Zeitplan, über „nur schließen“, über „von Hand“, über „beobachten“. Ein
Schlafzimmer ohne Zeitplan ist kein Zimmer, aus dem man nicht herauskommen
soll. Einzig ein Rollo, an dem *Bei Rauchalarm auffahren* ausgeschaltet ist,
bleibt zu – gedacht für eines, das nicht fahren darf, etwa weil ein Möbelstück
im Weg steht.

**Es fasst nach.** Ein Fahrbefehl kann verlorengehen, ein Funkmotor kann ihn
verschlucken. Ein Rollo, das nach der Fahrzeit immer noch zu ist, bekommt den
Befehl erneut – so oft, wie unter *Versuche je Rollo* steht (Vorgabe: 3).
Danach gilt es als blockiert und wird in Ruhe gelassen, statt im Minutentakt
gegen ein Hindernis zu fahren.

**Der Trockenlauf gilt auch hier.** Solange er an ist, meldet die Freigabe nur,
was sie täte. Ein Add-on im Probebetrieb, das nachts das Haus aufmacht, wäre
schlimmer als eines, das im Ernstfall nichts tut – im Ernstfall gibt es die
Melder ja auch noch.

### Der Meldeweg

Beim ersten Takt eines Alarms geht **eine** Meldung hinaus und ein Eintrag ins
Protokoll: was aufgefahren wurde, was schon offen stand und – zuerst – was
**nicht** erreichbar war. Wer bei jedem Takt meldete, verschickte während eines
Brandes im Minutentakt Nachrichten und begrübe die eine, auf die es ankommt.

**In der Überschrift steht der Ort**, denn auf einem Sperrbildschirm liest man
die erste Zeile und sonst nichts: *„Rauchalarm: Flur 1.OG"*. Genommen wird der
**Bereich** aus Home Assistant – der sagt mehr als „RM Flur OG Alarmstatus" und
stimmt auch nach einem Umbenennen noch. Hat ein Melder keinen Bereich, wird sein
Name gekürzt. Schlagen mehrere an, stehen bis zu vier Orte da und danach
„und N weitere“ – gekürzt wird, aber nicht stillschweigend.

Darunter steht, **was schiefging, zuerst**: nicht erreichbar, bleibt zu,
ausgenommen – und erst dann, was aufgefahren ist. Wer im Ernstfall aufs Telefon
sieht, muss wissen, welches Fenster zu bleibt, nicht welche neun offen sind.

Wohin, steht im Reiter unter *Meldeweg*. Das ist ein **eigener** Weg, nicht der
des Wächters: Wer den Wächter stummschaltet, weil ihn die Hinderniswarnungen
nerven, will deswegen keinen Brand verschweigen. Ist keiner angehakt, gilt
trotzdem der Weg des Wächters – lieber die falsche Zustellart als gar keine
Meldung.

Gemeldet wird **jeder** Rauchalarm, auch bei abgeschalteter Freigabe. Dann sagt
die Nachricht eben, dass kein Rollo aufgefahren ist; das ist die wichtigere
Auskunft, nicht die unwichtigere.

Der Knopf **Probemeldung senden** verschickt eine Testnachricht über denselben
Weg. Der einzige Weg, den Ernstfall vorher einmal zu sehen, ohne einen Melder
anzuzünden – gefahren wird dabei nichts.

Läuft diese Freigabe, kann eine eigene Automation „bei Rauch alle Rollos hoch“
entfallen. Beide nebeneinander schaden nicht – sie wollen dasselbe.

## Hitzeschutz

Steht die Sonne im Fenster und ist es draußen warm, fährt das Rollo teilweise
zu. Dafür braucht **jedes Rollo** eine Ausrichtung – wohin sein Fenster zeigt.
Das gehört ans Rollo und nicht an den Raum: Ein Zimmer kann ein Fenster nach
Süden und eines nach Westen haben, und die wollen zu verschiedenen Tageszeiten
verschattet werden.

Ohne Ausrichtung bleibt der Hitzeschutz wirkungslos: Der Planer kann nicht
raten, und ein geratener Wert verschattet zur falschen Tageszeit.

Die Ausrichtung ist eine **Gradzahl von 0 bis 359** (0 Nord, 90 Ost, 180 Süd,
270 West), keine Auswahl aus acht Himmelsrichtungen. Krumme Werte sind der
Normalfall: Ein Haus steht selten genau nach der Himmelsrichtung, und die 22
Grad zwischen „Süd“ und „SSO“ sind am Nachmittag eine gute Stunde Sonne. Wer
den Wert nicht schätzen will, kann ihn aus dem Gebäudeumriss rechnen — die
Außenwände eines Hauses stehen in den Kartendaten.

Der **Öffnungswinkel** sagt, wie weit die Sonne daneben stehen darf und
trotzdem noch ins Fenster scheint (Vorgabe 90°, also 45° zu jeder Seite).

Der Hitzeschutz lässt sich **je Rollo** schalten, nicht nur insgesamt: Jedes
Rollo hat dafür einen eigenen Schalter in Home Assistant
(`switch.rolloplaner_rollo_<name>_hitzeschutz`) und einen Knopf in seiner
Kachel. Der Knopf erscheint nur, wo eine Himmelsrichtung hinterlegt ist – ohne
sie kann der Hitzeschutz nichts tun, und ein Knopf ohne Wirkung hält man für
kaputt statt für unzuständig.

### Wie weit zufahren?

Die **Stellung beim Beschatten** steht unter *Einstellungen → Hitzeschutz* und
gilt für alle Rollos. Wo ein einzelnes Rollo davon abweichen soll, trägt man im
Rollo-Dialog unter *Stellung* einen eigenen Wert ein; leer heißt „die Vorgabe“.
Ein Wohnzimmer, in dem man tagsüber sitzt, will vielleicht heller bleiben als
ein Schlafzimmer, das nur kühl werden soll.

Beide Felder folgen der eingestellten **Zählweise** – steht die Umkehrung an,
heißt eine höhere Zahl „weiter zu“.

Im Winter bleibt das Rollo offen, auch bei tiefstehender Sonne. Die wärmt kaum,
und genau die will man haben.

Die Hysterese hängt an der Temperatur, nicht am Sonnenstand: Ein Rollo, das an
der Grenze zwischen 23,9 und 24,1 Grad im Minutentakt auf und ab fährt, ist
schlimmer als gar kein Hitzeschutz.

## Urlaub

Drei Betriebsarten:

* **Anwesenheit simulieren** – derselbe Zeitplan, aber jeden Tag ein paar
  Minuten anders. Ein Haus, dessen Rollos wochenlang auf die Minute genau
  fahren, verrät sich; eines, dessen Rollos gar nicht mehr fahren, erst recht.
* **alles geschlossen halten**
* **normaler Zeitplan**

Der Versatz wird einmal am Tag gewürfelt und bleibt dann fest – auch über einen
Neustart des Add-ons hinweg. Er wird aus dem Datum abgeleitet, nicht aus einem
Zufallsgenerator; ein Versatz, der sich bei jedem Takt neu auslost, führe das
Rollo jede Minute woanders hin.

„Nicht vor“ und „nicht nach“ klammern die Streuung ein, damit kein Rollo um
Viertel vor sieben hochfährt, während das Haus leer steht.

## Fenstersperre

Solange ein zugeordneter Kontakt offen ist, wird **nicht zugefahren** – Öffnen
bleibt erlaubt. Wer auf der Terrasse steht und das Rollo fährt vor der offenen
Tür herunter, steht draußen.

Der Schaltpunkt gilt dann **nicht** als erledigt: Sobald die Tür zugeht, wird er
nachgeholt. Und zwar der dann zuletzt fällige – geht die Tür erst morgens um
neun zu, fährt das Rollo nicht verspätet zu, sondern bleibt offen.

## Handbetrieb

Steht ein Rollo woanders, als der Planer es zuletzt hingefahren hat, war jemand
am Schalter. Dann bleibt es in Ruhe, bis die eingestellte Frist abgelaufen ist –
oder bis der nächste Schaltpunkt fällig wird. Man muss also nicht daran denken,
den Handbetrieb wieder aufzuheben.

### Bedienen in der Übersicht

Jede Kachel trägt **auf · Halt · zu** – der Halt in der Mitte, so wie auf jedem
Handsender – und darunter einen **Schieber** für alles dazwischen. Gefahren
wird erst beim Loslassen: Jeder Zwischenwert als Befehl wäre ein Dutzend
Befehle für eine Handbewegung, der Antrieb ruckte, und das Protokoll stünde
voll.

Beide Bedienelemente erscheinen nur, wenn der Antrieb sie beherrscht. Ein
Rollladen, der nur auf und zu kann, bekommt keinen Schieber, und einer ohne
`stop_cover` keinen Halt. Ein Knopf, der nichts tut, ist schlimmer als keiner:
Er behauptet, es ginge – und wer ihn drückt, sucht den Fehler beim Rollo.

**Der Halt zählt als Handbetrieb.** Anders als beim Fahren weiß der Planer
danach nämlich *nicht*, wo das Rollo steht: Der Antrieb meldet seine Stellung
erst, wenn er zur Ruhe gekommen ist. Ein Ziel zu erfinden wäre der schlimmere
Weg – daran hat sich schon einmal die Handbetriebserkennung verschluckt.
„Handbetrieb“ ist ohnehin genau das, was gemeint war: *Ich habe eingegriffen,
lass es stehen.* Der nächste fällige Schaltpunkt hebt die Schonfrist von selbst
wieder auf.

Solange die Zahl über der Kachel und der Schieber auseinandergehen, sieht man
beides zugleich: **oben, wohin der Planer will; unten, wo das Rollo steht.**
Nach einem Halt ist das der Normalfall, und die Marke *Handbetrieb* sagt,
warum.

## Wächter

Meldet ein Antrieb länger als die Schweigefrist nichts mehr, oder meldet er ein
Hindernis, geht eine Nachricht über die eingestellten Meldewege raus. Die
Rademacher-Gurtwickler bringen dafür eigene Melder mit
(`*_obstacle_detection`, `*_blocking_detection`); der Planer wertet sie aus,
sofern sie so heißen wie das Rollo.

Die Schweigefrist steht bewusst hoch. Ein Rollladen meldet nur, wenn er fährt –
eines, das zweimal am Tag fährt, meldet sich auch nur zweimal am Tag.

## Sprache

Der Planer spricht **Deutsch und Englisch**. Wer eine dritte Sprache will,
ergänzt eine Tabelle in `backend/sprache.py` und eine in der Karte – kein
`gettext`, keine `.po`-Dateien, kein Übersetzungslauf beim Bauen.

**Zwei Stellen, zwei Regeln:**

* **Das Add-on** folgt Home Assistant (dessen `language` aus `/api/config`,
  beim Start gelesen) oder der Einstellung unter *Einstellungen → Sprache*.
  Danach richtet sich alles, was der Planer selbst formuliert: Protokoll und
  die Meldung bei Rauchalarm.
* **Die Oberfläche des Add-ons** folgt derselben Einstellung wie der Planer –
  sie ist schließlich der Ort, an dem sie gesetzt wird. Wer auf *Englisch*
  stellt und speichert, sieht die Einrichtung beim nächsten Takt englisch.
* **Die Karte** folgt dem **Betrachter** (`hass.locale.language`). Auf dem
  Wandtablett steht Deutsch, ein englischsprachiger Gast sieht dieselbe Karte
  auf Englisch, und niemand muss etwas umstellen.

Damit beides nicht auseinanderläuft, liefert der Planer seine Begründungen
**in jeder Sprache** mit (Attribut `begruendungen`). Sonst stünde in einer
englischen Karte ein deutscher Satz – halb übersetzt ist schlechter als gar
nicht.

Der schwierige Teil war nicht die Menge, sondern der Satzbau: Der Planer setzt
seine Begründungen aus Bausteinen zusammen, und „zu um Sonnenuntergang,
spätestens 22:00 wenn morgen schulfrei ist" heißt auf Englisch „closed at
sunset, no later than 22:00 when tomorrow is a day off" – andere Wortstellung,
andere Fügung. Deshalb steht je Sprache die ganze Vorlage da, nicht eine
Wörterliste. Tests wachen darüber, dass alle drei Tabellen – Planer, Karte,
Oberfläche – dieselben Schlüssel und dieselben Platzhalter führen, dass kein
Schlüssel doppelt vergeben ist und dass jeder benutzte Schlüssel auch wirklich
in der Tabelle steht. **Deutsch ist die Rückfallebene**: Fehlt ein Schlüssel,
kommt der deutsche Text und nie der nackte Schlüssel.

Steht neben einem Schlüssel einer mit `_1`, gilt der bei genau einem Stück –
„1 covers shaded" liest sich wie ein Fehler, und wer die Sprache nicht spricht,
hält es auch für einen.

## Entitäten

Über MQTT legt das Add-on ein Gerät „Rolloplaner“ an:

| Entität | Inhalt |
| --- | --- |
| `sensor.rolloplaner_status` | Gesamtlage, mit Sonnenzeiten und Außentemperatur als Attribute |
| `sensor.rolloplaner_naechster_wechsel` | Der nächste Schaltpunkt im ganzen Haus, als fertiger Text |
| `sensor.rolloplaner_rollo_<name>` | Zielstellung dieses Rollos in Prozent, mit Begründung |
| `switch.rolloplaner_rollo_<name>_an` | Automatik dieses Rollos |
| `switch.rolloplaner_rollo_<name>_hitzeschutz` | Hitzeschutz dieses Rollos |
| `switch.rolloplaner_plan_<name>` | Automatik eines gemeinsamen Zeitplans |
| `switch.rolloplaner_automatik` | Automatik insgesamt |
| `switch.rolloplaner_beschattung` | Hitzeschutz insgesamt |
| `switch.rolloplaner_urlaubssimulation` | Urlaubssimulation |
| `switch.rolloplaner_fluchtweg` | Fluchtweg-Freigabe |
| `binary_sensor.rolloplaner_rauchsperre` | Sperre aktiv |
| `binary_sensor.rolloplaner_fluchtweg_offen` | Freigabe läuft gerade; Attribute sagen, was auffuhr und was nicht |
| `binary_sensor.rolloplaner_stoerung` | Ein Antrieb meldet sich nicht oder hängt |
| `binary_sensor.rolloplaner_trockenlauf` | Der Planer rechnet, fährt aber nichts |

Die eigenen Schalter des Planers (Reiter *Schalter*) kommen als
`switch.rolloplaner_<name>` beziehungsweise `select.rolloplaner_<name>` dazu.

**Die entity_id entsteht einmal beim Anlegen und folgt keiner Umbenennung.**
Wer einen Schalter umbenennt, ändert den Anzeigenamen; die Kennung bleibt. Das
Add-on schlägt sie deshalb nach, statt sie aus dem Namen zurückzurechnen – wer
das täte, zeigte nach einer Umbenennung auf eine Entität, die es nicht gibt.

## Die Karte

Je Rollo eine Kachel. Geordnet wird nach **Obergruppe**: Ihr Name ist die
Überschrift über die volle Breite, darunter läuft **ein** Raster – alle Kacheln
gleich breit, gleich hoch, in sauberen Spalten.

Das war einmal anders: Bis Fassung 2.12 war jeder Raum ein eigener Block, und
ein Block war so breit, wie er Kacheln hatte. Bei 1280 px war die Kachel eines
Ein-Rollo-Zimmers 619 px breit, die daneben 413 – gleiche Dinge in
verschiedenen Größen, und die Karte sah unruhig aus.

Zu sehen sind Name, die Stellung als Zahl – und ein **simulierter Rollladen**, der zeigt, wie weit der Panzer heruntersteht. Ein Balken sagt
„65 %“, aber nicht, ob das Rollo dabei oben oder unten ist; das Bild sagt es
ohne Umweg, und beim Fahren läuft es sichtbar mit.

Vor einer **Tür** sieht der Rollladen anders aus als vor einem **Fenster**: Die
Tür reicht bis zur Bodenlinie hinunter und hat einen Flügelrahmen mit Griff,
das Fenster hängt darüber in der Wand. Gezeichnet wird nach der **Art** des
Rollos – die steht im Rollo-Dialog und wird beim Übernehmen aus dem Namen
geraten.

Das Add-on bringt seine Lovelace-Karte selbst mit; eine getrennte Installation
über HACS ist nicht nötig. Beim Start wird sie nach `www/` kopiert und als
Ressource registriert.

```yaml
type: custom:rolloplaner-card
```

Alle Angaben sind freiwillig:

```yaml
type: custom:rolloplaner-card
title: Rollos
show_funktionen: true     # die Schalter oben
show_raeume: true
show_naechster: true
show_stoerungen: true
show_helfer: true         # die Helfer, an denen die Schaltpunkte hängen
allow_fahren: true        # Auf/Zu je Rollo
gruppieren: true          # nach Obergruppe ordnen
textgroesse: gross        # klein | normal | gross | riesig – oder eine Zahl
zimmer: schild            # schild | ueberschrift | aus
gruppen: [Erdgeschoss, Obergeschoß]   # welche und in welcher Reihenfolge
```

Einstellen lässt sich das alles auch **ohne YAML** – siehe
[Einstellen ohne YAML](#einstellen-ohne-yaml).

**Die Helfer je Rollo**: Hängt ein Schaltpunkt an einem `input_boolean` oder
einem `input_select`, zeigt die Karte ihn bei dem Rollo an und lässt ihn dort
bedienen – als Chip mit Punkt für an/aus, als Auswahlliste bei mehreren
Stellungen. So lässt sich „die Terrassentür heute mal offen lassen“ dort
erledigen, wo man ohnehin hinsieht.

Auf dem Chip steht nicht der Name des Schalters, sondern **was er freigibt**:
*öffnen*, *schließen*, *auf und zu* oder *alles*. Abgeleitet wird das aus den
Schaltpunkten, an denen er hängt. „Öffnen Nele“ sagt nur, wie der Schalter
heißt; „öffnen“ sagt, was ausfällt, wenn man ihn ausschaltet. Der volle Name
steht im Tooltip.

Ein Schalter, der über **ein Zimmer hinaus** wirkt, steht nicht in den Kacheln,
sondern einmal oben unter *Gilt für mehrere Rollos*. Sonst sähe er in jeder
Kachel aus wie ein eigener – und wer ihn bei einem Rollo ausschaltet, wundert
sich, warum er beim anderen auch weg ist. Es ist derselbe Schalter.

Ist die Karte bereits aus einer anderen Quelle eingebunden (etwa HACS), legt
das Add-on **nichts** an und schreibt nur einen Hinweis ins Protokoll: Zwei
Registrierungen desselben Elements legen das Dashboard lahm.

### Bedienung mit dem Finger

Die Tasten in der Kachel sind **34 × 34 px mal Textskala** groß, bei der
Vorgabe also gut 40 px. Vorher waren es 24 px – am Wandtablett kaum zu treffen.
Sie wachsen mit der Schrift mit: Eine große Schrift deutet auf einen weiter
entfernten Betrachter, und der zielt schlechter.

Die Reihe heißt **auf · Halt · zu** – der Halt in der Mitte, so wie auf jedem
Handsender. Darunter liegt ein **Schieber** für alles dazwischen; er wächst
ebenso mit der Textskala, weil man ihn aus anderthalb Metern mit dem Daumen
bedient und nicht mit dem Zeigefinger. Beides lässt sich im Karteneditor
abschalten (*Tasten zum Fahren*, *Schieber für die Zwischenstellungen*) – der
Schieber kostet eine Zeile Höhe, und wer die Karte nur zum Nachsehen aufhängt,
will sie nicht ausgeben.

Gefahren wird **beim Loslassen**, nicht bei jedem Zwischenwert: Sonst wären
zwanzig Fahrbefehle für eine Fingerbewegung unterwegs, der Antrieb ruckte, und
im Protokoll stünde die ganze Bewegung. Solange jemand zieht – und noch
fünfzehn Sekunden danach, bis der Antrieb angekommen ist und seine neue
Stellung meldet – zeichnet sich die Karte nicht neu. Ein Schieber, den es
einem unter dem Finger wegreißt, ist unbedienbar. Was in dieser Zeit an neuen
Zuständen ankam, holt sie danach von selbst nach.

Halt und Schieber erscheinen nur, wo der Antrieb sie beherrscht
(`supported_features`). Ein Knopf, der nichts tut, ist schlimmer als keiner:
Er behauptet, es ginge – und wer ihn drückt, sucht den Fehler beim Rollo statt
beim Antrieb.

### Die große Zahl: wo es steht, nicht wohin es soll

Die Zahl an der Kachel sagt, **wo das Rollo steht**. Solange der Planer
bekommt, was er will, ist das dasselbe wie sein Ziel – nach einem Halt gehen
beide auseinander, und dann ist die wahre Stellung die Auskunft, nach der man
sucht. Wohin der Planer will, steht in der Zeile darunter: *Plan: zu*. Sie
erscheint nur, wenn beide mehr als sechs Prozentpunkte auseinanderliegen; das
ist die Toleranz, mit der auch der Planer rechnet, denn darunter ist eine
Abweichung kein Eingriff, sondern der Weg, den ein Antrieb beim Anhalten noch
macht.

Der **Sensor** führt weiter das Ziel des Planers – daran ändert sich nichts,
sonst bekäme seine Verlaufskurve rückwirkend eine andere Bedeutung. Die
tatsächliche Stellung steht in seinem Attribut `ist`.

### Ein Rollo ohne Automatik ist nicht abgeschaltet

„Aus" heißt in diesem Add-on immer: **die Automatik** ist aus, nie das Rollo.
Es bleibt in der Übersicht, meldet seine Stellung, lässt sich von Hand fahren
und geht bei Rauchalarm trotzdem auf – der Planer fährt es nur nicht nach Plan.
Deshalb heißt der Haken am Rollo *Automatik für dieses Rollo*, das Schild in
der Kachel *Automatik aus* und die Kopfzeile *9 von 10 Rollos mit Automatik*.
Vorher stand dort „Rollo ist abgeschaltet" und „9 von 10 Rollos aktiv", und
beides las sich wie ein Defekt.

### Ein abgeschaltetes Rollo ist nicht verschwunden

Steht die Automatik eines Rollos auf aus, bekommt seine Kachel einen
**gestrichelten Rand** und das Schild *aus*; gedimmt wird nur die Begründung
und der nächste Schaltpunkt. Vorher lag die halbe Deckkraft über der ganzen
Kachel – das las sich wie „nicht verfügbar", obwohl Stellung, Name und Tasten
weiter stimmen und das Rollo sich von Hand fahren lässt.

### Das Zimmer

Seit die **Obergruppe** die Überschrift stellt, ist das Zimmer eine eigene
Angabe. Die Kartenoption `zimmer` bestimmt, wie es erscheint:

* **`schild`** (Vorgabe) – ein kleines Schild am Namen, das entfällt, wo der
  Name das Zimmer schon nennt („Rollo Küche" im Zimmer „Küche" zweimal zu
  lesen, hilft niemandem).
* **`ueberschrift`** – eine Zwischenzeile innerhalb der Gruppe. Jedes Zimmer
  bekommt dabei sein **eigenes** Raster: Die Kacheln eines Zimmers sind gleich
  hoch und fluchten mit denen der anderen, über Zimmer hinweg dürfen die Höhen
  sich unterscheiden. (Die Überschrift in dasselbe Raster zu setzen, ging
  schief – sie erbte die Zeilenhöhe einer Kachel, und zwischen den Zimmern
  klafften kachelgroße Löcher.) Ein Zimmer mit einem Rollo lässt den Rest
  seiner Reihe leer; das ist der Preis dieser Ansicht.
* **`aus`** – gar nicht.

### Einstellen ohne YAML

Die Karte bringt einen **Editor** mit: In Home Assistant unter *Karte
bearbeiten* stehen dort Überschrift, Schriftgröße, was die Karte zeigt, und
eine Liste der Gruppen zum **An- und Abhaken und Sortieren**. Die Reihenfolge
dort gilt vor der aus dem Add-on; sind alle angehakt und unverschoben, folgt
die Karte dem Add-on.

In YAML heißt das `gruppen: [...]` – die Liste bestimmt zugleich, **welche**
Gruppen erscheinen und **in welcher Reihenfolge**. Der Vorgänger `raeume` gilt
weiter.

Innerhalb einer Gruppe zählt der Platz, den das Add-on vergibt: Wer die Rollos
im Reiter *Gruppen* sortiert, meint damit die Karte.

### Schriftgröße

Die Karte hängt hier auch an einem Wandtablett im Flur, und was am Schreibtisch
klein und aufgeräumt wirkt, ist aus anderthalb Metern nicht mehr zu lesen.
Deshalb hat sie eine Textskala:

```yaml
type: custom:rolloplaner-card
textgroesse: gross      # klein | normal | gross | riesig – oder eine Zahl
```

Vorgabe ist **gross** (1,2×). *normal* ist die alte, kleinere Darstellung,
*riesig* (1,45×) ist für die Wand gedacht. Statt einer Stufe geht auch eine
Zahl zwischen 0,7 und 2,5, wer dazwischen liegt.

Mitskaliert wird **alles**: Schrift, Symbole, die Mindestbreite einer Kachel
und die Umbruchschwelle. Sonst wüchse der Text in eine Kachel hinein, die
gleich breit bleibt, und jeder zweite Name stünde abgeschnitten da. Nach oben
begrenzt die Kartenbreite: Auf einem Telefon im Hochformat bleibt eine Spalte,
egal wie groß die Schrift steht.

## Trockenlauf

Der Probebetrieb: Der Planer rechnet, protokolliert und meldet, **fährt aber
nichts**. So lässt sich neben den alten Automationen mitlaufen und vergleichen,
ob er dasselbe wollen würde.

Was im Trockenlauf gilt:

* **Kein Fahrbefehl verlässt das Add-on** – auch nicht die Fluchtweg-Freigabe
  bei Rauchalarm. Sie meldet dann nur, was sie täte.
* **Das Protokoll führt mit**, jeder Eintrag mit dem Zusatz *(Trockenlauf)*.
  Ein Schaltpunkt gilt dabei als abgearbeitet, sonst stünde alle zwei Minuten
  derselbe Eintrag darin.
* **Kein Handbetrieb wird erkannt.** Im Trockenlauf bewegt jedes Rollo etwas
  anderes – die alten Automationen tun ja weiter ihren Dienst. Der Planer
  daraus „jemand war am Schalter“ zu folgern, hieße, dass er reihenweise
  Handbetrieb meldet und sich selbst stilllegt, statt zu zeigen, was er täte.
  Dasselbe gilt für ein Rollo auf *beobachten*.
* **Die Pfeiltasten in der Karte fahren trotzdem.** Sie sind ein Handgriff des
  Benutzers, nicht des Planers.

**Beim Ausschalten setzt der Planer den geltenden Stand sofort durch.** Der
gemerkte Schaltpunkt wird verworfen und der Plan neu ausgeführt – wer den
Trockenlauf beendet, erwartet genau das. Vorher hinsehen, ob gerade jemand
etwas absichtlich offen stehen hat: Ein von Hand geöffnetes Rollo, das der Plan
zu haben will, fährt in diesem Moment zu.

## „Warum fährt das Rollo nicht?“

Der Reiter **Einrichtung** hat unten eine Selbstauskunft. Sie beantwortet fast
alle Fälle: fehlende Entitäten, Rollos ohne Schaltpunkt, Hitzeschutz ohne
Ausrichtung, **Türen ohne Kontakt**, stillgelegte Schaltpunkte – und ob noch
alte Automationen mitlaufen, die gegen den Planer anfahren.

Bleibt es unklar, hilft das **Protokoll**: Dort steht jede Fahrt mit ihrer
Begründung. Nur Fahrten, keine Takte – so bleibt es lesbar.

## Sonnenzeiten

Der Planer rechnet die Sonnenzeiten selbst, weil `sun.sun` nur den **nächsten**
Auf- und Untergang kennt. Der Zeitplan braucht aber den von gestern – sonst
wüsste er um zwei Uhr nachts nicht, dass „bei Sonnenuntergang zufahren“ längst
fällig war.

Damit trotzdem dasselbe herauskommt wie im Dashboard, richtet er seine Rechnung
bei jedem Takt an `sun.sun` aus. Abweichungen von mehr als einer Viertelstunde
werden dabei verworfen – das wäre kein Höhenunterschied mehr, sondern ein
Datenfehler.
