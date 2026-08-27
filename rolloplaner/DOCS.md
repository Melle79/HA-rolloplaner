# Rolloplaner

Rollladensteuerung für Home Assistant: je Rollo ein Zeitplan, der nach Uhrzeit
**oder** nach dem Stand der Sonne schaltet, dazu Hitzeschutz, Urlaubssimulation
und eine Rauchsperre.

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

Der erste Treffer gewinnt:

Gerechnet wird **je Rollo**:

**Betriebsarten** je Rollo: *Plan* (auf und zu), *nur schließen* (öffnet nie von
selbst), *nur von Hand* (kein Zeitplan, und das ist Absicht – der Planer zeigt
es an, überwacht es und fährt es bei Rauchalarm auf, aber nicht nach der Uhr) und *beobachten* (rechnet mit, schaltet nichts – für den Probelauf
eines einzelnen Rollos).

| Rang | Zustand | Was er bedeutet |
| --- | --- | --- |
| 1 | **Fluchtweg** | Ein Melder schlägt an – das Rollo fährt auf |
| 1 | **Rauchsperre** | Alarm, aber dieses Rollo ist von der Freigabe ausgenommen |
| 2 | **aus** | Das Rollo oder die Automatik ist abgeschaltet |
| 3 | **gesperrt** | Der Zeitplan, dem es folgt, ist stillgelegt |
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

Beim ersten Takt eines Alarms geht **eine** Meldung über die Meldewege des
Wächters hinaus und ein Eintrag ins Protokoll: was aufgefahren wurde, was schon
offen stand und – zuerst – was **nicht** erreichbar war. Wer bei jedem Takt
meldete, verschickte während eines Brandes im Minutentakt Nachrichten und
begrübe die eine, auf die es ankommt.

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

## Wächter

Meldet ein Antrieb länger als die Schweigefrist nichts mehr, oder meldet er ein
Hindernis, geht eine Nachricht über die eingestellten Meldewege raus. Die
Rademacher-Gurtwickler bringen dafür eigene Melder mit
(`*_obstacle_detection`, `*_blocking_detection`); der Planer wertet sie aus,
sofern sie so heißen wie das Rollo.

Die Schweigefrist steht bewusst hoch. Ein Rollladen meldet nur, wenn er fährt –
eines, das zweimal am Tag fährt, meldet sich auch nur zweimal am Tag.

## Entitäten

Über MQTT legt das Add-on ein Gerät „Rolloplaner“ an:

| Entität | Inhalt |
| --- | --- |
| `sensor.rolloplaner_status` | Gesamtlage, mit Sonnenzeiten und Außentemperatur als Attribute |
| `sensor.rolloplaner_naechster_wechsel` | Der nächste Schaltpunkt im ganzen Haus, als fertiger Text |
| `sensor.rolloplaner_rollo_<name>` | Zielstellung dieses Rollos in Prozent, mit Begründung |
| `switch.rolloplaner_rollo_<name>_an` | Automatik dieses Rollos |
| `switch.rolloplaner_plan_<name>` | Automatik eines gemeinsamen Zeitplans |
| `switch.rolloplaner_automatik` | Automatik insgesamt |
| `switch.rolloplaner_beschattung` | Hitzeschutz |
| `switch.rolloplaner_urlaubssimulation` | Urlaubssimulation |
| `switch.rolloplaner_fluchtweg` | Fluchtweg-Freigabe |
| `binary_sensor.rolloplaner_rauchsperre` | Sperre aktiv |
| `binary_sensor.rolloplaner_fluchtweg_offen` | Freigabe läuft gerade; Attribute sagen, was auffuhr und was nicht |
| `binary_sensor.rolloplaner_stoerung` | Ein Antrieb meldet sich nicht oder hängt |

## Die Karte

Je Rollo eine Kachel, nach Raum geordnet. **Jeder Raum ist ein Block**, und die
Blöcke fließen nebeneinander – ein Zimmer mit einem Rollo ist ein schmaler
Block, eines mit dreien ein breiter. So bleibt die Ordnung nach Räumen
sichtbar, ohne dass neben jedem kleinen Raum die halbe Karte leer bleibt.

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
gruppieren: true          # nach Raum ordnen
raeume: [Küche, Wohnzimmer]   # welche Räume – ohne Angabe: alle
```

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

Ein Schalter, der über **einen Raum hinaus** wirkt, steht nicht in den Kacheln,
sondern einmal oben unter *Gilt für mehrere Rollos*. Sonst sähe er in jeder
Kachel aus wie ein eigener – und wer ihn bei einem Rollo ausschaltet, wundert
sich, warum er beim anderen auch weg ist. Es ist derselbe Schalter.

Ist die Karte bereits aus einer anderen Quelle eingebunden (etwa HACS), legt
das Add-on **nichts** an und schreibt nur einen Hinweis ins Protokoll: Zwei
Registrierungen desselben Elements legen das Dashboard lahm.

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
