# Änderungen

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
