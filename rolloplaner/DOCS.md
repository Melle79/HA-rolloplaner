# Rolloplaner

Rollladensteuerung für Home Assistant: ein Zeitplan je Raum, der nach Uhrzeit
**oder** nach dem Stand der Sonne schaltet, dazu Hitzeschutz, Urlaubssimulation
und eine Rauchsperre.

Der Planer tritt an die Stelle einer Sammlung von Automationen und
Hilfsschaltern. Der Unterschied ist nicht nur Ordnung: Ein Hilfsschalter war
bisher eine **Bedingung** in einer Automation, die zu ihrer Uhrzeit lief. Wer
ihn umlegte, bewegte nie ein Rollo – es passierte erst am nächsten Tag etwas,
oder auch gar nichts. Beim Planer ist der Schalter der Zustand selbst.

## Einrichten

1. Add-on starten. Es beginnt im **Trockenlauf**: Es rechnet, protokolliert –
   und fährt nichts. So lässt sich alles in Ruhe prüfen.
2. Reiter **Einrichtung** öffnen. Der Planer liest `automations.yaml` und
   schlägt vor, was er dort findet: Räume, Rollos, Schaltzeiten,
   Freigabeschalter. Prüfen, abhaken, anlegen.
3. Im Reiter **Übersicht** eine Weile mitlesen. Jeder Raum sagt, was er tun
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

## Die Regelkette

Der erste Treffer gewinnt:

| Rang | Zustand | Was er bedeutet |
| --- | --- | --- |
| 1 | **aus** | Der Raum oder die Automatik ist abgeschaltet |
| 2 | **Rauchsperre** | Ein Melder schlägt an – der Planer fasst nichts an |
| 3 | **gesperrt** | Der Freigabeschalter des Raumes ist aus |
| 4 | **Fenster offen** | Ein Kontakt ist offen – es wird nicht zugefahren |
| 5 | **Urlaub** | Urlaubsprogramm statt Zeitplan |
| 6 | **Hitzeschutz** | Die Sonne steht im Fenster und es ist warm |
| 7 | **Handbetrieb** | Jemand hat von Hand gefahren |
| 8 | **Zeitplan** | Der Normalfall |

Geschaltet wird **auf der Flanke, nie auf dem Pegel**: Der Planer merkt sich,
welchen Schaltpunkt er zuletzt ausgeführt hat, und rührt sich erst wieder, wenn
ein neuer fällig wird oder eine Bedingung kippt. Ein Thermostat, dem man
denselben Sollwert zum zehnten Mal schickt, tut nichts – ein Rollladen fährt.

Jedes Rollo wird **einzeln** angefahren. Ein Sammelaufruf scheitert an einem
nicht erreichbaren Funkmotor und reißt die übrigen mit.

## Rauchsperre

Schlägt ein Rauchmelder an, fasst der Planer **kein** Rollo mehr an – auch
nicht, wenn ein Schaltpunkt fällig wird. Nach der Entwarnung bleibt es dabei,
solange der eingestellte Nachlauf läuft.

Das ist der wichtigste Griff im ganzen Add-on. Wer eine Automation hat, die bei
Rauch alle Rollläden hochfährt, hätte sonst einen Planer, der ihr beim nächsten
Takt hinterherfährt und den Fluchtweg wieder zumacht. **Diese Sperre nicht
abschalten.**

## Hitzeschutz

Steht die Sonne im Fenster und ist es draußen warm, fährt das Rollo teilweise
zu. Dafür braucht der Raum eine **Ausrichtung** – wohin das Fenster zeigt. Ohne
sie bleibt der Hitzeschutz wirkungslos: Der Planer kann nicht raten, und ein
geratener Wert verschattet zur falschen Tageszeit.

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
| `sensor.rolloplaner_raum_<name>` | Zielstellung des Raumes in Prozent, mit Begründung |
| `switch.rolloplaner_raum_<name>_an` | Automatik dieses Raumes |
| `switch.rolloplaner_automatik` | Automatik insgesamt |
| `switch.rolloplaner_beschattung` | Hitzeschutz |
| `switch.rolloplaner_urlaubssimulation` | Urlaubssimulation |
| `binary_sensor.rolloplaner_rauchsperre` | Sperre aktiv |
| `binary_sensor.rolloplaner_stoerung` | Ein Antrieb meldet sich nicht oder hängt |

## Die Karte

Je Raum eine Kachel: Raumname, die Stellung als Zahl – und ein **simulierter
Rollladen**, der zeigt, wie weit der Panzer heruntersteht. Ein Balken sagt
„65 %“, aber nicht, ob das Rollo dabei oben oder unten ist; das Bild sagt es
ohne Umweg, und beim Fahren läuft es sichtbar mit.

Vor einer **Tür** sieht der Rollladen anders aus als vor einem **Fenster**: Er
geht bis zum Boden, während das Fenster eine Brüstung darunter hat. Welches
Bild ein Raum bekommt, entscheidet der Planer nach den Namen seiner Rollos –
„Rollo Balkontür Luna“ ist eine Tür, „Rollo Küche“ ein Fenster. Ein Raum gilt
nur dann als Tür, wenn *alle* seine Rollos welche sind. Überstimmen lässt sich
das im Raum-Dialog unter *Stellungen → Anzeige zeichnet*.

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
allow_fahren: true        # Auf/Zu je Raum
raeume: [Küche, Wohnzimmer]   # ohne Angabe: alle
```

**Die Helfer je Raum**: Hängt ein Schaltpunkt an einem `input_boolean` oder
einem `input_select`, zeigt die Karte ihn beim Raum an und lässt ihn dort
bedienen – als Chip mit Punkt für an/aus, als Auswahlliste bei mehreren
Stellungen. So lässt sich „die Terrassentür heute mal offen lassen“ dort
erledigen, wo man ohnehin hinsieht.

Ist die Karte bereits aus einer anderen Quelle eingebunden (etwa HACS), legt
das Add-on **nichts** an und schreibt nur einen Hinweis ins Protokoll: Zwei
Registrierungen desselben Elements legen das Dashboard lahm.

## „Warum fährt der Raum nicht?“

Der Reiter **Einrichtung** hat unten eine Selbstauskunft. Sie beantwortet fast
alle Fälle: fehlende Entitäten, Räume ohne Schaltpunkt, Rollos in zwei Räumen,
Hitzeschutz ohne Ausrichtung – und ob noch alte Automationen mitlaufen, die
gegen den Planer anfahren.

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
