/* Rolloplaner-Card – Lovelace Custom Card für das Rolloplaner Add-on
 *
 * Minimale Konfiguration:
 *   type: custom:rolloplaner-card
 *
 * Die Karte findet ihre Rollos selbst: Alles, was als `sensor.rolloplaner_rollo_*`
 * in Home Assistant steht, taucht auf – geordnet nach dem Raum, den das Add-on
 * mitliefert. Der Raum steuert nichts; er ist nur der Ort, an dem man ein Rollo
 * sucht. Geschaltet wird über die Entitäten, die
 * das Add-on per MQTT anlegt – die Karte kennt keine eigene Logik und keinen
 * eigenen Zustand.
 *
 * Sie tritt an die Stelle der Kachelreihe aus neun `input_boolean`-Helfern und
 * dem Auswahlhelfer der Terrassentür. Diese Helfer sind nicht verschwunden: Wo
 * ein Schaltpunkt an einem von ihnen hängt, zeigt die Karte ihn beim Raum an
 * und lässt ihn dort bedienen – man muss die Karte nicht verlassen, um die
 * Terrassentür heute mal offen zu lassen.
 *
 * Zum Aussehen: Die Karte malt **keine eigenen Flächen**. Ein eigener
 * Zeilenhintergrund ist in einem hellen Theme ein dunkler Fremdkörper und in
 * einem dunklen ein Loch; Trennlinien nehmen die Farbe des Themes an und sehen
 * überall richtig aus.
 */
const CARD_VERSION = "2.13.0";
console.info(`%c ROLLOPLANER-CARD %c v${CARD_VERSION} `,
  "color:#06172a;background:#5aa9e6;font-weight:700", "color:#5aa9e6;background:#1f2630");

const DEFAULTS = {
  title: "Rollos",
  show_funktionen: true,
  show_raeume: true,
  show_naechster: true,
  show_stoerungen: true,
  show_helfer: true,        // die Helfer, an denen die Schaltpunkte hängen
  allow_fahren: true,
  // null = alle. Sonst eine Liste von Gruppennamen: Sie bestimmt zugleich,
  // **welche** gezeigt werden und **in welcher Reihenfolge**.
  gruppen: null,
  raeume: null,             // Vorgänger von `gruppen`, bleibt gültig
  gruppieren: true,         // nach Gruppe ordnen
  // Schriftgröße. Die Karte hängt bei uns auch an einem Wandtablett im Flur,
  // und was am Schreibtisch klein und aufgeräumt wirkt, ist aus anderthalb
  // Metern nicht mehr zu lesen.
  textgroesse: "gross",     // klein | normal | gross | riesig
};

const TEXTSKALA = {klein: 0.9, normal: 1, gross: 1.2, riesig: 1.45};

const FUNKTIONEN = [
  ["switch.rolloplaner_automatik", "Automatik", "mdi:home-automation"],
  ["switch.rolloplaner_beschattung", "Hitzeschutz", "mdi:sun-thermometer"],
  ["switch.rolloplaner_urlaubssimulation", "Urlaub", "mdi:shield-home"],
  ["switch.rolloplaner_fluchtweg", "Fluchtweg", "mdi:fire-alert"],
];

/* Was ein Helfer freigibt – abgeleitet aus den Schaltpunkten, an denen er
   hängt. „raum“ ist der Freigabeschalter des ganzen Raumes. */
const WIRKUNG = {
  oeffnen: "öffnen",
  schliessen: "schließen",
  beides: "auf und zu",
  raum: "alles",
};

// Welche Arten bis zum Boden gehen – die werden als Tür gezeichnet.
const TUERARTEN = ["balkontuer", "terrassentuer", "haustuer"];

const ZUSTAND_TEXT = {
  beschattung: "Hitzeschutz", urlaub: "Urlaub", rauch: "Rauchsperre",
  fluchtweg: "Fluchtweg",
  fenster: "Fenster offen", manuell: "Handbetrieb", aus: "Automatik aus",
  gesperrt: "gesperrt", ohne_plan: "kein Plan", nur_schliessen: "nur schließen",
  von_hand: "von Hand",
};

/* Der Rollladen vor einem Fenster oder einer Tür – siehe die Erklärung im
   Stilblock weiter unten. */
function rollobild(position, art) {
  // Gezeichnet wird nach der Zählweise von Home Assistant: Wie weit der Panzer
  // heruntersteht, ist eine Tatsache und keine Frage der Beschriftung.
  const p = Number(position);
  const zu = Number.isNaN(p) ? 100 : Math.max(0, Math.min(100, 100 - p));
  const tuer = TUERARTEN.includes(art);
  return `<div class="bild"><div class="rollo ${tuer ? "tuer" : "fenster"}"
    style="--zu:${zu}%">
    ${tuer ? '<div class="fluegel"></div><div class="griff"></div>' : ""}
    <div class="panzer"></div><div class="kasten"></div>
  </div></div>`;
}

/* Die Karte bekommt die Zahlen schon in der Zählweise geliefert, die das
   Add-on eingestellt hat – umrechnen muss sie also nichts. Nur „offen“ und
   „zu“ muss sie richtig herum benennen, und dafür braucht sie die Zählweise:
   Bei umgedrehter Zählung heißt 0 % offen und 100 % geschlossen. */
function stellungstext(p, invertiert) {
  if (p === null || p === undefined || p === "unknown" || p === "") return "–";
  const n = Number(p);
  if (Number.isNaN(n)) return "–";
  const offen = invertiert ? n <= 0 : n >= 100;
  const zu = invertiert ? n >= 100 : n <= 0;
  if (offen) return "offen";
  if (zu) return "zu";
  return `${n} %`;
}

class RolloplanerCard extends HTMLElement {
  setConfig(config) {
    this._config = { ...DEFAULTS, ...config };
  }

  getCardSize() { return 4 + (this._rolloAnzahl || 0); }

  static getStubConfig() { return { ...DEFAULTS }; }
  static getConfigElement() { return document.createElement("rolloplaner-card-editor"); }

  set hass(hass) {
    this._hass = hass;
    const status = hass.states["sensor.rolloplaner_status"];
    const rollos = this._rollosSammeln(hass);
    this._rolloAnzahl = rollos.length;
    // Nur neu zeichnen, wenn sich wirklich etwas geändert hat – sonst klappt
    // jede Auswahlliste zu, während man noch darin liest.
    const signatur = JSON.stringify([
      status && status.state,
      FUNKTIONEN.map(([e]) => hass.states[e] && hass.states[e].state),
      rollos.map((r) => [r.sensor.state, r.sensor.attributes.zustand,
                         r.sensor.attributes.prozent_invertiert,
                         r.sensor.attributes.begruendung,
                         r.sensor.attributes.naechste_uhrzeit,
                         (r.sensor.attributes.helfer || []).map(
                           (h) => [h.entity_id, hass.states[h.entity_id]
                                                && hass.states[h.entity_id].state]),
                         r.sensor.attributes.gruppe,
                         r.sensor.attributes.raum,
                         r.schalter && r.schalter.state,
                         r.hitzeschutz && r.hitzeschutz.state]),
      hass.states["sensor.rolloplaner_naechster_wechsel"]
        && hass.states["sensor.rolloplaner_naechster_wechsel"].state,
      hass.states["binary_sensor.rolloplaner_stoerung"]
        && hass.states["binary_sensor.rolloplaner_stoerung"].state,
      hass.states["binary_sensor.rolloplaner_rauchsperre"]
        && hass.states["binary_sensor.rolloplaner_rauchsperre"].state,
    ]);
    if (signatur === this._signatur) return;
    this._signatur = signatur;
    this._render(status, rollos);
  }

  _rollosSammeln(hass) {
    const gewuenscht = this._config.gruppen || this._config.raeume;
    return Object.keys(hass.states)
      .filter((e) => e.startsWith("sensor.rolloplaner_rollo_"))
      .map((e) => {
        const sensor = hass.states[e];
        const schalterId = e.replace(/^sensor\./, "switch.") + "_an";
        const sonnenId = e.replace(/^sensor\./, "switch.") + "_hitzeschutz";
        return {
          id: e,
          // Home Assistant stellt den Gerätenamen voran: aus „Rollo Büro“ wird
          // „Rolloplaner Rollo Büro“. Beides muss weg, sonst steht auf jeder
          // Zeile zweimal dasselbe.
          name: (sensor.attributes.friendly_name || e)
            .replace(/^Rolloplaner\s+/, "").replace(/^Rollo\s+/, ""),
          raum: sensor.attributes.raum || "",
          gruppe: sensor.attributes.gruppe || "",
          platz: Number(sensor.attributes.gruppe_platz ?? 999),
          sensor,
          schalter: hass.states[schalterId] || null,
          hitzeschutz: hass.states[sonnenId] || null,
        };
      })
      .filter((r) => (!gewuenscht || gewuenscht.includes(r.gruppe || r.raum)))
      .sort((a, b) => {
        // Steht eine Reihenfolge in der Konfiguration, gilt sie. Sonst zählt
        // die Reihenfolge aus dem Add-on – dort ordnet man die Gruppen –, und
        // erst zuletzt das Alphabet.
        const ka = a.gruppe || a.raum || "";
        const kb = b.gruppe || b.raum || "";
        if (gewuenscht) {
          const d = gewuenscht.indexOf(ka) - gewuenscht.indexOf(kb);
          if (d) return d;
        } else if (ka !== kb) {
          return ka.localeCompare(kb, "de");
        }
        // Innerhalb einer Gruppe zählt der Platz, den das Add-on vergibt –
        // dort sortiert man die Rollos, und dort ist es auch gemeint.
        return (a.platz - b.platz) || a.name.localeCompare(b.name, "de");
      });
  }

  // ------------------------------------------------------------- Bedienen ---

  _schalten(entityId, an) {
    this._hass.callService(entityId.split(".")[0], an ? "turn_on" : "turn_off",
      { entity_id: entityId });
  }

  _auswaehlen(entityId, option) {
    this._hass.callService(entityId.split(".")[0], "select_option",
      { entity_id: entityId, option });
  }

  _fahrbefehl(cover, position) {
    // Angesprochen wird die Entität des Rollos – sie ist der Schlüssel, unter
    // dem der Planer es führt.
    this._hass.callService("mqtt", "publish", {
      topic: "rolloplaner/cmd",
      payload: JSON.stringify({ befehl: "fahren", rollo: cover, position }),
    });
  }

  // -------------------------------------------------------------- Zeichnen ---

  _render(status, rollos) {
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    const c = this._config;

    if (!status) {
      this.shadowRoot.innerHTML = `<ha-card style="--skala:${this._skala()}"><div class="rand"><div class="leer">
        Entitäten des Rolloplaner Add-ons nicht gefunden
        (<code>sensor.rolloplaner_status</code>). Läuft das Add-on, und ist
        MQTT eingerichtet?</div></div></ha-card>${this._stil()}`;
      return;
    }

    const a = status.attributes || {};
    const rauch = this._hass.states["binary_sensor.rolloplaner_rauchsperre"];
    const fluchtweg = this._hass.states["binary_sensor.rolloplaner_fluchtweg_offen"];
    const fluchtwegSchalter = this._hass.states["switch.rolloplaner_fluchtweg"];
    const stoerung = this._hass.states["binary_sensor.rolloplaner_stoerung"];
    const naechster = this._hass.states["sensor.rolloplaner_naechster_wechsel"];

    const kopf = `<div class="kopf">
      <ha-icon icon="mdi:window-shutter" class="k-icon"></ha-icon>
      <div class="k-text">
        <div class="k-titel">${this._esc(c.title)}</div>
        <div class="k-status">${this._esc(status.state)}</div>
      </div>
      <div class="k-rechts">
        ${a.sonnenaufgang ? `<span title="Sonnenaufgang">
          <ha-icon icon="mdi:weather-sunset-up"></ha-icon>${this._uhr(a.sonnenaufgang)}</span>` : ""}
        ${a.sonnenuntergang ? `<span title="Sonnenuntergang">
          <ha-icon icon="mdi:weather-sunset-down"></ha-icon>${this._uhr(a.sonnenuntergang)}</span>` : ""}
        ${a.aussentemperatur !== null && a.aussentemperatur !== undefined
          ? `<span><ha-icon icon="mdi:thermometer"></ha-icon>${a.aussentemperatur} °C</span>` : ""}
      </div>
    </div>`;

    let warnung = "";
    if (fluchtweg && fluchtweg.state === "on") {
      // Im Alarm zählt eine Auskunft: Ist der Weg nach draußen offen? Was
      // *nicht* aufging, steht deshalb vor dem, was aufging.
      const f = fluchtweg.attributes || {};
      const zeile = (titel, liste, klasse) => (liste || []).length
        ? `<div class="${klasse || ""}">${titel}: ${this._esc(liste.join(", "))}</div>` : "";
      warnung += `<div class="warnung rauch">
        <ha-icon icon="mdi:fire-alert"></ha-icon>
        <div><b>${f.akut === false ? "Entwarnung – Fluchtweg bleibt offen."
                                  : "Rauchalarm – Fluchtweg offen."}</b>
        ${this._esc(f.grund || rauch?.attributes?.grund || "")}
        ${zeile("Nicht erreichbar", f.nicht_erreichbar, "schwer")}
        ${zeile("Bleibt zu", f.aufgegeben, "schwer")}
        ${zeile("Ausgenommen", f.ausgenommen)}
        ${zeile("Aufgefahren", f.geoeffnet)}</div></div>`;
    } else if (rauch && rauch.state === "on") {
      warnung += `<div class="warnung rauch">
        <ha-icon icon="mdi:smoke-detector-variant-alert"></ha-icon>
        <div>Rauchsperre – der Planer fasst gerade kein Rollo an.
        ${this._esc(rauch.attributes.grund || "")}</div></div>`;
    }
    // Ein abgeschalteter Fluchtweg fällt sonst erst im Brandfall auf. Ein
    // Fehlgriff auf den Knopf darüber darf nicht stumm bleiben.
    if (c.show_funktionen && fluchtwegSchalter && fluchtwegSchalter.state === "off") {
      warnung += `<div class="warnung">
        <ha-icon icon="mdi:fire-alert"></ha-icon>
        <div>Die Fluchtweg-Freigabe ist aus – bei Rauchalarm fährt kein Rollo auf.</div></div>`;
    }
    if (c.show_stoerungen && stoerung && stoerung.state === "on") {
      warnung += `<div class="warnung">
        <ha-icon icon="mdi:window-shutter-alert"></ha-icon>
        <div>${(stoerung.attributes.meldungen || []).map((m) =>
          `<div>${this._esc(m)}</div>`).join("")}</div></div>`;
    }

    let funktionen = "";
    if (c.show_funktionen) {
      const knoepfe = FUNKTIONEN.map(([entityId, name, icon]) => {
        const zustand = this._hass.states[entityId];
        if (!zustand) return "";
        const an = zustand.state === "on";
        return `<button class="fn ${an ? "an" : ""}" data-schalter="${entityId}"
                        data-an="${an ? "0" : "1"}" title="${name}">
          <ha-icon icon="${icon}"></ha-icon><span>${name}</span></button>`;
      }).join("");
      if (knoepfe) funktionen = `<div class="funktionen">${knoepfe}</div>`;
    }

    let naechsterHtml = "";
    if (c.show_naechster && naechster && naechster.state
        && naechster.state !== "kein Wechsel geplant") {
      naechsterHtml = `<div class="naechster">
        <ha-icon icon="mdi:clock-outline"></ha-icon>
        <span>${this._esc(naechster.state)}</span></div>`;
    }

    // Die Schalter, die mehrere Räume betreffen, stehen einmal oben. Sonst
    // sähe in jeder Kachel derselbe Schalter aus wie ein eigener – und wer ihn
    // bei Nele ausschaltet, wundert sich, warum er bei Luna auch weg ist.
    let freigabenHtml = "";
    if (c.show_helfer) {
      const geteilt = (a.freigaben || []).filter((f) => this._hass.states[f.entity_id]);
      if (geteilt.length) {
        freigabenHtml = `<div class="freigaben">
          <div class="f-titel">Gilt für mehrere Rollos</div>
          <div class="f-liste">${geteilt.map((f) => this._chip(f, true)).join("")}</div>
        </div>`;
      }
    }

    let rolloHtml = "";
    if (c.show_raeume) {
      if (!rollos.length) {
        rolloHtml = `<div class="rand"><div class="leer">Noch kein Rollo eingerichtet.</div></div>`;
      } else if (c.gruppieren) {
        // Zwei Ebenen: Die Obergruppe – bei uns die Etage – ist die
        // Überschrift, der Raum steht am Rollo. Vorher war der Raum der Block,
        // und ein Block war so breit, wie er Kacheln hatte: Bei 1280 px war
        // die Kachel eines Ein-Rollo-Zimmers 619 px breit, die daneben 413.
        // Gleiche Dinge in verschiedenen Größen, und die Karte sah unruhig aus.
        //
        // Jetzt füllt jede Überschrift die Breite, und darunter läuft **ein**
        // Raster: Alle Kacheln sind gleich breit, egal wie viele Rollos eine
        // Gruppe hat. Der Raum geht dabei nicht verloren, er steht als Schild
        // an der Kachel – dort, wo er hingehört.
        const nachGruppe = new Map();
        rollos.forEach((r) => {
          const titel = r.gruppe || r.raum || "Ohne Gruppe";
          if (!nachGruppe.has(titel)) nachGruppe.set(titel, []);
          nachGruppe.get(titel).push(r);
        });
        rolloHtml = `<div class="raeume">${[...nachGruppe].map(([titel, liste]) =>
          `<section class="raumgruppe">
            <div class="raumtitel">${this._esc(titel)}</div>
            <div class="gruppe">${liste.map((r) => this._rollo(r)).join("")}</div>
          </section>`).join("")}</div>`;
      } else {
        rolloHtml = `<div class="raeume">${rollos.map((r) => this._rollo(r)).join("")}</div>`;
      }
    }

    this.shadowRoot.innerHTML = `<ha-card style="--skala:${this._skala()}">
      <div class="rand">${kopf}${warnung}${funktionen}${naechsterHtml}${freigabenHtml}</div>
      ${rolloHtml}
    </ha-card>${this._stil()}`;

    this.shadowRoot.querySelectorAll("[data-schalter]").forEach((el) =>
      el.addEventListener("click", () =>
        this._schalten(el.dataset.schalter, el.dataset.an === "1")));
    this.shadowRoot.querySelectorAll("[data-fahren]").forEach((el) =>
      el.addEventListener("click", () =>
        this._fahrbefehl(el.dataset.fahren, Number(el.dataset.position))));
    this.shadowRoot.querySelectorAll("select[data-auswahl]").forEach((el) =>
      el.addEventListener("change", () =>
        this._auswaehlen(el.dataset.auswahl, el.value)));
  }

  _rollo(r) {
    const c = this._config;
    const attrs = r.sensor.attributes || {};
    const zustand = attrs.zustand || "plan";
    const an = !r.schalter || r.schalter.state === "on";

    // Das Schild nur, wenn es etwas zu sagen hat: „Zeitplan“ an jedem der
    // sieben Räume ist keine Auskunft, sondern Grundrauschen – und es verdeckt
    // die eine Zeile, auf der wirklich „Hitzeschutz“ steht.
    const schild = ZUSTAND_TEXT[zustand]
      ? `<span class="schild s-${zustand}">${ZUSTAND_TEXT[zustand]}</span>` : "";

    // Der Raum steht seit der Umstellung auf Obergruppen an der Kachel. Er
    // entfällt, wo der Name ihn schon enthält: „Rollo Küche" im Raum „Küche"
    // zweimal zu lesen, hilft niemandem.
    const raum = attrs.raum || "";
    const raumSchild = raum && !r.name.toLowerCase().includes(raum.toLowerCase())
      ? `<span class="raumschild">${this._esc(raum)}</span>` : "";

    // Die Begründung ist Vergangenheit, die Fußzeile Zukunft. Ohne die Uhrzeit
    // davor las sich beides als Folge von Vorhaben: „zu um Sonnenuntergang …
    // dann offen um 10:00 Uhr" klingt nach zwei Terminen, von denen der erste
    // längst vorbei ist. Nur beim Zeitplan – „Fenster offen" oder „Handbetrieb
    // bis 08:00" sind schon von sich aus eindeutig.
    const grund = zustand === "plan" && attrs.zuletzt_uhrzeit && attrs.begruendung
      ? `seit ${this._esc(attrs.zuletzt_uhrzeit)} Uhr: ${this._esc(attrs.begruendung)}`
      : this._esc(attrs.begruendung || "");

    const inv = Boolean(attrs.prozent_invertiert);
    const dann = attrs.naechste_uhrzeit
      ? `dann ${stellungstext(attrs.naechste_stellung, inv)} um ${this._esc(attrs.naechste_uhrzeit)} Uhr`
      : "";

    const knoepfe = c.allow_fahren && attrs.cover ? `
      <button class="tipp" data-fahren="${attrs.cover}" data-position="100"
              title="öffnen"><ha-icon icon="mdi:arrow-up"></ha-icon></button>
      <button class="tipp" data-fahren="${attrs.cover}" data-position="0"
              title="schließen"><ha-icon icon="mdi:arrow-down"></ha-icon></button>` : "";
    const kippe = r.schalter ? `<button class="tipp ${an ? "an" : ""}"
        data-schalter="${r.schalter.entity_id}" data-an="${an ? "0" : "1"}"
        title="Automatik für ${this._esc(r.name)}">
        <ha-icon icon="mdi:${an ? "robot" : "robot-off"}"></ha-icon></button>` : "";

    // Ein Knopf für den Hitzeschutz dieses Rollos – aber nur, wo eine
    // Himmelsrichtung hinterlegt ist. Ohne sie weiß der Planer nicht, wann die
    // Sonne in dieses Fenster steht; ein Knopf ohne Wirkung ist schlimmer als
    // keiner, weil man ihn für kaputt hält statt für unzuständig.
    const sonne = r.hitzeschutz && attrs.ausrichtung !== null
                  && attrs.ausrichtung !== undefined
      ? `<button class="tipp ${r.hitzeschutz.state === "on" ? "an" : ""}"
          data-schalter="${r.hitzeschutz.entity_id}"
          data-an="${r.hitzeschutz.state === "on" ? "0" : "1"}"
          title="Hitzeschutz für ${this._esc(r.name)} (Fenster zeigt nach ${
            this._esc(String(attrs.ausrichtung))}°)">
          <ha-icon icon="mdi:sun-thermometer"></ha-icon></button>` : "";

    const zahl = Number(r.sensor.state);
    const wert = Number.isNaN(zahl) ? "–" : zahl;

    return `<div class="raum ${an ? "" : "ruht"}">
      <div class="z1">
        ${rollobild(attrs.stellung_ha === null || attrs.stellung_ha === undefined
                    ? r.sensor.state : attrs.stellung_ha, attrs.art)}
        <div class="z1-text">
          <div class="namenzeile">
            <span class="name" title="${this._esc(r.name)}">${this._esc(r.name)}</span>${raumSchild}${schild}${
              // Heißt der Zeitplan wie der Raum, steht dasselbe Wort zweimal
              // nebeneinander. Einmal reicht.
              attrs.zeitplan && attrs.zeitplan !== raum
                ? `<span class="planschild" title="Zeitplan">${
                    this._esc(attrs.zeitplan)}</span>` : ""}
          </div>
          <div class="grund">${grund}</div>
        </div>
        <div class="z1-wert">
          <span class="wert">${wert}<small>${Number.isNaN(zahl) ? "" : "%"}</small></span>
          <span class="lage">${stellungstext(r.sensor.state, inv)}</span>
        </div>
      </div>
      ${c.show_helfer ? this._helfer(attrs.helfer || [], r.name) : ""}
      <div class="z3">
        <span class="dann">${dann}</span>
        <span class="knoepfe">${knoepfe}${sonne}${kippe}</span>
      </div>
    </div>`;
  }

  /* Ein Bedienelement für einen Schalter – oben wie in der Kachel derselbe
     Bauplan, damit nicht zweierlei Knöpfe für dieselbe Sache entstehen.
     `mit_namen`: oben steht der Name des Schalters (dort fehlt der Raum als
     Zusammenhang), in der Kachel nur seine Wirkung. */
  _chip(h, mit_namen, beschriftung) {
    const zustand = this._hass.states[h.entity_id];
    if (!zustand) return "";
    const wirkungen = h.wirkungen || [h.wirkung];
    const wirkungstext = wirkungen.map((w) => WIRKUNG[w] || w).join(" und ");
    const betrifft = h.rollos ? `\n${h.rollos.join(", ")}` : "";
    const titel = `${h.name} – gibt ${wirkungstext} frei${betrifft}\n${h.entity_id}`;

    if (h.optionen && h.optionen.length) {
      // In der Kachel steht die Wirkung, oben der Name: „Terrassentür
      // schliessen“ ist in der Kachel „Wohnzimmer – Terrassentür“ dreimal
      // dasselbe Wort und bricht die Zeile um, ohne etwas zu sagen.
      return `<label class="chip auswahl" title="${this._esc(titel)}">
        <span class="c-text">${this._esc(beschriftung
          || (mit_namen ? this._kurzname(h.name) : wirkungstext))}</span>
        <select data-auswahl="${h.entity_id}">${h.optionen.map((o) =>
          `<option value="${this._esc(o)}"${o === zustand.state ? " selected" : ""}>${this._esc(o)}</option>`
        ).join("")}</select></label>`;
    }
    const an = zustand.state === "on";
    const text = beschriftung
      || (mit_namen ? this._kurzname(h.name) : wirkungstext);
    return `<button class="chip ${an ? "an" : ""}" data-schalter="${h.entity_id}"
      data-an="${an ? "0" : "1"}" title="${this._esc(titel)}"
      ><span class="c-text">${this._esc(text)}</span></button>`;
  }

  _helfer(helfer, rolloName) {
    // Zwei Schalter desselben Rollos können dieselbe Wirkung haben – dann
    // stünde zweimal „schließen“ nebeneinander und niemand wüsste, welcher
    // welcher ist. In dem Fall kommt der Name des Schalters dazu, aber nur der
    // Teil, der etwas sagt: In der Kachel „Terrassentür“ ist „Terrassentür
    // schliessen“ zu drei Vierteln Wiederholung, und die Kachel ist schmal.
    const wirkung = (h) => (h.wirkungen || [h.wirkung])
      .map((w) => WIRKUNG[w] || w).join(" und ");
    const zaehler = {};
    helfer.forEach((h) => { const w = wirkung(h); zaehler[w] = (zaehler[w] || 0) + 1; });
    const teile = helfer.map((h) => {
      const w = wirkung(h);
      if (zaehler[w] < 2) return this._chip(h, false, null);
      const eigen = this._eigenname(h.name, rolloName);
      return this._chip(h, false, eigen ? `${w}: ${eigen}` : null);
    }).join("");
    // Auch ohne Schalter bleibt die Zeile stehen – leer, aber vorhanden. Sonst
    // wäre eine Kachel ohne Schalter niedriger als ihre Nachbarn, und die
    // Fußzeile säße in jeder Kachel woanders.
    if (!teile) return `<div class="chipzeile"></div>`;
    return `<div class="chipzeile"><span class="c-titel">gibt frei</span>${teile}</div>`;
  }

  _kurzname(name) {
    // „Helfer Rollo Terrassentür schliessen“ → „Terrassentür schliessen“.
    // Diese Vorsilben stehen in jedem der Helfer und sagen auf einer Karte,
    // die ohnehin „Rollos“ heißt, gar nichts.
    return String(name || "")
      .replace(/^Helfer\s*-?\s*/i, "")
      .replace(/^Rollosteuerung\s*-?\s*/i, "")
      .replace(/^Rollo\s+/i, "")
      .trim() || name;
  }

  _eigenname(name, rolloName) {
    // Was am Schalternamen übrig bleibt, wenn man den Namen des Rollos
    // abzieht – und nichts, wenn der Rest nur die Wirkung wiederholt.
    let rest = this._kurzname(name);
    String(rolloName || "").split(/\s+/).filter((w) => w.length > 3).forEach((w) => {
      rest = rest.replace(
        new RegExp(w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi"), " ");
    });
    rest = rest.replace(/\s+/g, " ").trim();
    return /^(schlie(ss|ß)en|(ö|oe)ffnen|auf|zu|rollo)?$/i.test(rest) ? "" : rest;
  }

  _uhr(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? ""
      : d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
  }

  _skala() {
    // Eine Zahl darf auch direkt in der Kartenkonfiguration stehen – wer
    // zwischen zwei Stufen liegt, soll nicht die Karte umbauen müssen.
    const wunsch = (this._config || {}).textgroesse;
    if (typeof wunsch === "number" && wunsch > 0)
      return Math.min(2.5, Math.max(0.7, wunsch));
    return TEXTSKALA[wunsch] ?? TEXTSKALA[DEFAULTS.textgroesse];
  }

  _esc(text) {
    return String(text === null || text === undefined ? "" : text)
      .replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;",
                                    '"': "&quot;" }[c]));
  }

  _stil() {
    return `<style>
      /* Der Messpunkt für die Breite. Er muss **über** dem liegen, was sich
         nach ihr richtet: Eine Container-Query fragt immer den nächsten
         Vorfahren mit container-type – ein Element kann nicht sein eigener
         Container sein. Stand er auf .raeume, blieben deren eigene Regeln
         wirkungslos, und die Karte hing bei einer Spalte fest. */
      /* Ohne das rechnet der Browser Rand und Polster einer Kachel zur
         Spaltenbreite hinzu – bei schmalen Karten stand jede Kachel 24 px über
         den Rand hinaus. Ein Schattenbaum erbt keinen Reset von der Seite. */
      *{box-sizing:border-box}

      /* Die Textskala. Sie steht als Vorgabe hier, damit die Karte auch dann
         etwas anzeigt, wenn die Konfiguration noch nicht durch ist – das
         Kartenelement selbst überschreibt sie. */
      ha-card{--skala:1.2; display:block; overflow:hidden; container-type:inline-size;
        /* Home Assistant bringt keine verlässliche Grünvariable mit; die
           meisten Themes setzen --success-color, sonst dieses Grün. */
        --an-farbe:var(--success-color, #43a047)}
      .rand{padding:14px 16px 12px}

      .kopf{display:flex; align-items:center; gap:10px; flex-wrap:wrap}
      .k-icon{--mdc-icon-size:calc(26px * var(--skala)); flex:none;
        color:var(--state-icon-color, var(--primary-color))}
      .k-text{flex:1 1 auto; min-width:110px}
      .k-titel{font-size:calc(1.15rem * var(--skala)); font-weight:500; line-height:1.25;
        color:var(--primary-text-color)}
      .k-status{font-size:calc(.8rem * var(--skala)); color:var(--secondary-text-color)}
      .k-rechts{display:flex; gap:12px; font-size:calc(.8rem * var(--skala)); flex-wrap:wrap;
        color:var(--secondary-text-color)}
      .k-rechts span{display:inline-flex; align-items:center; gap:3px;
        white-space:nowrap}
      .k-rechts ha-icon{--mdc-icon-size:16px}

      .warnung{display:flex; gap:8px; align-items:flex-start; margin-top:10px;
        padding:8px 10px; border-radius:8px; font-size:calc(.84rem * var(--skala));
        color:var(--primary-text-color);
        border-left:3px solid var(--warning-color,#e0a44a);
        background:rgba(224,164,74,.16)}
      .warnung.rauch{border-left-color:var(--error-color,#e36d6d);
        background:rgba(227,109,109,.16)}
      .warnung ha-icon{--mdc-icon-size:18px; flex:none;
        color:var(--warning-color,#e0a44a)}
      .warnung.rauch ha-icon{color:var(--error-color,#e36d6d)}

      .funktionen{display:flex; gap:6px; flex-wrap:wrap; margin-top:12px}
      .fn{display:inline-flex; align-items:center; gap:5px; cursor:pointer;
        border:1px solid var(--divider-color); background:none; border-radius:18px;
        padding:4px 11px; font-size:calc(.8rem * var(--skala)); font-weight:500; font-family:inherit;
        color:var(--secondary-text-color)}
      .fn ha-icon{--mdc-icon-size:calc(16px * var(--skala))}
      .fn:hover{color:var(--primary-text-color)}
      /* Dieselbe Farbe wie bei den Schaltern in den Kacheln: an ist grün.
         Die Themenfarbe wäre hier zwar hübscher, sagt aber nichts – ein
         Schalter, dessen Stellung man an der Farbe nicht abliest, ist keiner. */
      .fn.an{background:var(--an-farbe); border-color:transparent;
        color:var(--text-primary-color,#fff)}

      .naechster{display:flex; align-items:center; gap:6px; margin-top:10px;
        font-size:calc(.8rem * var(--skala)); color:var(--secondary-text-color)}
      .naechster ha-icon{--mdc-icon-size:15px; flex:none}

      /* ── Die geteilten Schalter, einmal oben ── */
      .freigaben{margin-top:12px; padding-top:10px;
        border-top:1px solid var(--divider-color)}
      .f-titel{font-size:calc(.7rem * var(--skala)); letter-spacing:.06em; text-transform:uppercase;
        color:var(--secondary-text-color); opacity:.8; margin-bottom:6px}
      .f-liste{display:flex; gap:5px; flex-wrap:wrap; align-items:center}
      .raumtitel{font-size:calc(.68rem * var(--skala)); letter-spacing:.09em; text-transform:uppercase;
        color:var(--secondary-text-color); opacity:.85; font-weight:600;
        padding:8px 0 4px; border-bottom:1px solid var(--divider-color);
        margin-bottom:8px}
      /* Der Zeitplanname steht bei den Zustandsschildern am Namen, nicht in
         der Fußzeile. Dort stritt er mit der Uhrzeit um die Breite, und
         verloren hat regelmäßig die Uhrzeit – also die Tatsache gegen die
         Beschriftung. Am Namen ist er außerdem, was er ist: eine Eigenschaft
         des Rollos, nicht des nächsten Schaltpunkts. */
      /* Der Zeitplanname steht bei den Schildern am Namen. In der Fußzeile
         stritt er mit der Uhrzeit um die Breite, und verloren hat regelmäßig
         die Uhrzeit – also die Tatsache gegen die Beschriftung. */
      .planschild{display:inline-block; padding:0 7px; border-radius:12px;
        background:rgba(127,127,127,.2); color:var(--secondary-text-color);
        font-size:calc(.64rem * var(--skala)); font-weight:600;
        white-space:nowrap; flex:none}

      /* ── Ein Chip, ein Aussehen – oben wie in der Kachel ── */
      .chip{display:inline-flex; align-items:center; gap:5px; cursor:pointer;
        border:1px solid var(--divider-color); background:none; border-radius:14px;
        padding:2px 9px 2px 7px; font-family:inherit; font-weight:500;
        font-size:calc(.74rem * var(--skala)); color:var(--secondary-text-color); line-height:1.5;
        max-width:100%; min-width:0; flex:0 1 auto}
      /* Der Punkt davor sagt an oder aus. Ein bloß etwas hellerer Hintergrund
         reicht dafür nicht – ein Schalter, dessen Stellung man raten muss, ist
         kein Schalter. */
      .chip::before{content:""; width:7px; height:7px; border-radius:50%; flex:none;
        background:currentColor; opacity:.3}
      .chip:hover{color:var(--primary-text-color)}
      /* Grün heißt: gibt frei. Das ist die eine Farbe, die man ohne Nachdenken
         als „geht“ liest – ein Schalter, dessen Stellung man erst suchen muss,
         ist keiner. */
      .chip.an{color:var(--primary-text-color); border-color:var(--an-farbe);
        background:color-mix(in srgb, var(--an-farbe) 18%, transparent)}
      .chip.an::before{background:var(--an-farbe); opacity:1}
      .chip.auswahl{padding-right:3px; cursor:default; border-color:var(--an-farbe)}
      .chip.auswahl::before{background:var(--an-farbe); opacity:1}
      .c-text{overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
        min-width:2.5ch}
      .chip select{border:none; background:none; font-family:inherit;
        font-size:calc(.74rem * var(--skala)); color:var(--primary-text-color); cursor:pointer;
        padding:1px 2px; max-width:110px; min-width:0; flex:0 1 auto}
      .chip select:focus{outline:none}
      /* Eine Reihe, immer. Umbrechen würde die Kachel wachsen lassen und
         damit ihre ganze Nachbarschaft mitziehen – also stauchen sich die
         Schalter lieber und schneiden ihren Text ab; der volle Name steht im
         Tooltip. Die Mindesthöhe hält den Platz frei, auch wenn ein Rollo gar
         keinen Schalter hat, damit die Fußzeile überall gleich sitzt. */
      .chipzeile{display:flex; gap:5px; flex-wrap:nowrap; align-items:center;
        margin-top:7px; min-height:calc(26px * var(--skala)); overflow:hidden}
      .c-titel{font-size:calc(.7rem * var(--skala)); color:var(--secondary-text-color); opacity:.75;
        white-space:nowrap; flex:0 50 auto; min-width:0;
        overflow:hidden; text-overflow:ellipsis}

      /* ── Kacheln oder Zeilen, je nach Platz ──
         Eine Karte in einer schmalen Dashboard-Spalte ist etwas anderes als
         eine über die volle Fensterbreite. Dort zerfielen zehn Rollos in sechs
         schmale Spalten mit großen Löchern dazwischen – und jede Kachel
         quetschte ihren Text in drei Zeilen, während rechts anderthalbtausend
         Pixel leer blieben.

         Deshalb misst die Karte ihren eigenen Platz: schmal Kacheln
         untereinander, mittel zwei nebeneinander, breit eine Zeile je Rollo.
         Zeilen sind bei viel Breite das Richtige – man liest sie von links
         nach rechts wie eine Liste, statt sechs Kacheln abzusuchen. */
      /* Gleiche Höhe für alles, was nebeneinander steht: Die Raumblöcke einer
         Zeile werden auf dieselbe Höhe gezogen (align-items:stretch), der Block
         gibt sie an sein Raster weiter (flex:1), und grid-auto-rows:1fr teilt
         sie gleichmäßig auf die Kacheln auf. Ohne diese Kette richtet sich jede
         Kachel nach ihrem eigenen Inhalt, und die Reihe franst aus. */
      /* Untereinander, jede Gruppe über die volle Breite. Die Kacheln darin
         liegen in einem Raster mit fester Spaltenbreite – daher sind sie
         überall gleich breit, ohne dass die Karte ihre eigene Spaltenzahl
         ausrechnen müsste. */
      .raeume{--spalte:calc(300px * var(--skala)); display:flex;
        flex-direction:column; gap:2px; padding:0 12px 12px}
      .raumgruppe{min-width:0; display:flex; flex-direction:column}
      .gruppe{display:grid; gap:10px 14px; align-items:stretch; grid-auto-rows:1fr;
        /* minmax(min(…,100%),…): Eine „auto"-Spalte schrumpft nie unter den
           Mindestinhalt ihrer Kacheln – die Kachel stand dann über den Rand
           hinaus, statt ihren Text abzuschneiden. Der 100-Prozent-Deckel hält
           sie auf einem schmalen Telefon in der Karte. */
        grid-template-columns:repeat(auto-fill,
          minmax(min(var(--spalte), 100%), 1fr))}
      .raum{display:flex; flex-direction:column;
        border:1px solid var(--divider-color); border-radius:10px;
        padding:10px 11px 8px}
      /* Automatik aus heißt: Der Planer fährt dieses Rollo nicht. Es heißt
         nicht, dass das Rollo weg ist – Stellung, Name und Tasten stimmen
         weiter. Die halbe Deckkraft über der ganzen Kachel las sich wie
         „nicht verfügbar". Gedimmt wird deshalb nur, was tatsächlich ruht:
         die Begründung und der nächste Schaltpunkt. Der gestrichelte Rand
         sagt den Rest. */
      .raum.ruht{border-style:dashed}
      .raum.ruht .grund, .raum.ruht .dann{opacity:.5}

      .z1{display:flex; align-items:flex-start; gap:10px}
      .z1-text{flex:1 1 auto; min-width:0}
      .namenzeile{display:flex; align-items:baseline; gap:6px; min-width:0;
        flex-wrap:wrap}
      /* Umbrechen statt abschneiden: „Wohnzimmer – Terrassentür“ ist der
         Name, an dem man die Kachel erkennt – „Wohnzimmer – …“ ist keiner. */
      .name{font-size:calc(1rem * var(--skala)); font-weight:500; color:var(--primary-text-color);
        min-width:0; overflow-wrap:anywhere; line-height:1.25}
      /* Feste Höhen für die Abschnitte, damit in jeder Kachel dasselbe an
         derselben Stelle steht – auch wenn eine Begründung kürzer ist oder ein
         Rollo gar keine Schalter hat. */
      .grund{font-size:calc(.76rem * var(--skala)); color:var(--secondary-text-color); margin-top:2px;
        display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;
        overflow:hidden; min-height:2.4em}
      .z1-wert{display:flex; flex-direction:column; align-items:flex-end; flex:none}
      .wert{font-size:calc(1.5rem * var(--skala)); font-weight:300; line-height:1.1;
        color:var(--primary-text-color); font-variant-numeric:tabular-nums}
      .wert small{font-size:.62em; color:var(--secondary-text-color); margin-left:1px}
      .lage{font-size:calc(.7rem * var(--skala)); color:var(--secondary-text-color)}
      .schild{font-size:calc(.66rem * var(--skala)); font-weight:600; padding:1px 7px; border-radius:18px;
        white-space:nowrap; letter-spacing:.02em; flex:none;
        background:rgba(127,127,127,.22); color:var(--primary-text-color)}
      /* Der Raum ist eine Einordnung, kein Zustand – deshalb blasser als die
         Zustandsschilder daneben und ohne eigene Farbe. */
      .raumschild{font-size:calc(.64rem * var(--skala)); font-weight:500;
        padding:1px 7px; border-radius:18px; white-space:nowrap; flex:none;
        border:1px solid var(--divider-color); color:var(--secondary-text-color)}
      .s-rauch{background:rgba(227,109,109,.3)}
      .s-fluchtweg{background:rgba(227,109,109,.45); color:var(--primary-text-color)}
      .warnung .schwer{font-weight:600}
      .s-fenster,.s-manuell{background:rgba(224,164,74,.3)}

      /* Die Tastenzeile wird mit dem Finger bedient, nicht mit der Maus: Am
         Wandtablett war die alte Fläche von 24 px kaum zu treffen. Sie wächst
         mit der Textskala mit, weil eine große Schrift auf einen weiter
         entfernten Betrachter deutet. */
      .knoepfe{display:flex; gap:calc(3px * var(--skala)); flex:none;
        margin-left:auto}
      .tipp{border:none; background:none; cursor:pointer;
        display:inline-flex; align-items:center; justify-content:center;
        min-width:calc(34px * var(--skala)); min-height:calc(34px * var(--skala));
        padding:0; border-radius:10px; color:var(--secondary-text-color)}
      .tipp:hover{color:var(--primary-text-color); background:rgba(127,127,127,.18)}
      /* Auf dem Tablett gibt es kein „hover" – dort ist der Druck die einzige
         Rückmeldung, die man bekommt. */
      .tipp:active{background:rgba(127,127,127,.3)}
      .tipp.an{color:var(--an-farbe)}
      .tipp ha-icon{--mdc-icon-size:calc(22px * var(--skala)); display:block}

      .z3{display:flex; align-items:center; gap:6px; margin-top:auto;
        padding-top:7px; font-size:calc(.75rem * var(--skala)); color:var(--secondary-text-color)}
      .dann{flex:1 1 auto; min-width:0; overflow:hidden; text-overflow:ellipsis;
        white-space:nowrap}

      /* ── Rollladen vor Fenster oder Tür ──
         Die Eigenschaft --zu geht von 0 % (ganz offen) bis 100 % (ganz
         geschlossen); der Panzer hängt von oben herunter, darunter kommt die
         Öffnung zum Vorschein.

         Beide Bilder stecken in einer Box gleicher Höhe, damit in einer
         Kachelreihe nichts springt. Der Unterschied steckt in zwei Dingen: Die
         Tür reicht bis zur Bodenlinie hinunter, das Fenster hängt darüber in
         der Wand – und die Tür hat einen sichtbaren Flügelrahmen mit Griff.
         Ohne den Rahmen war sie nur ein schmales hohes Rechteck mit einem
         Griff an der Seite, und das sieht aus wie ein Kühlschrank.

         Die Farben folgen bewusst nicht dem Farbschema: Das ist kein
         Bedienelement, sondern das Bild eines Gegenstands. Ein Rollladen ist
         hellgrau, und was dahinterliegt, ist Himmel. */
      .bild{height:40px; display:flex; align-items:flex-start; flex:none;
        position:relative; padding-bottom:3px}
      .bild::after{content:""; position:absolute; left:-2px; right:-2px; bottom:0;
        height:1.5px; border-radius:1px; background:currentColor; opacity:.35}
      .rollo{position:relative; border-radius:2px; overflow:hidden;
        border:1px solid rgba(0,0,0,.45);
        background:linear-gradient(160deg,#7fb4d8,#4a7fa5)}
      .rollo.fenster{height:74%; width:calc(40px*1.16); margin-top:5%}
      .rollo.tuer{height:calc(100% - 3px); width:calc(40px*.76)}
      /* Die Zarge: an drei Seiten, **unten offen**. Genau daran erkennt man
         eine Tür – ein umlaufender Rahmen ist ein Fensterrahmen, und die Tür
         wirkte damit wie ein Kasten, der über dem Boden schwebt. */
      .rollo .fluegel{position:absolute; inset:0; border:2px solid #e2e7ec;
        border-bottom:none; border-radius:1px 1px 0 0}
      .rollo .griff{position:absolute; right:3px; top:47%; width:4px; height:1.5px;
        border-radius:1px; background:#3d4750}
      .rollo .panzer{position:absolute; left:0; right:0; top:0; height:var(--zu,0%);
        transition:height .6s ease; box-shadow:0 1px 3px rgba(0,0,0,.5);
        background:repeating-linear-gradient(to bottom,#cfd6de 0 3px,#9aa5b1 3px 4px)}
      /* Die Endleiste – ohne sie sieht der Panzer aus wie eine Schraffur */
      .rollo .panzer::after{content:""; position:absolute; left:0; right:0; bottom:0;
        height:2px; background:#7d8894}
      /* Der Kasten, in dem der Panzer aufgerollt liegt: auch bei ganz offenem
         Rollo sichtbar, sonst fehlte dem Bild oben der Abschluss. */
      .rollo .kasten{position:absolute; left:0; right:0; top:0; height:4px;
        background:linear-gradient(to bottom,#b8c1cb,#8e99a5)}

      /* Die Tastenzeile wird mit dem Finger bedient, nicht mit der Maus: Am
         Wandtablett war die alte Fläche von 24 px kaum zu treffen. Sie wächst
         mit der Textskala mit, weil eine große Schrift auf einen weiter
         entfernten Betrachter deutet. */
      .knoepfe{display:flex; gap:calc(3px * var(--skala)); flex:none;
        margin-left:auto}
      .tipp{border:none; background:none; cursor:pointer;
        display:inline-flex; align-items:center; justify-content:center;
        min-width:calc(34px * var(--skala)); min-height:calc(34px * var(--skala));
        padding:0; border-radius:10px; color:var(--secondary-text-color)}
      .tipp:hover{color:var(--primary-text-color); background:rgba(127,127,127,.18)}
      /* Auf dem Tablett gibt es kein „hover" – dort ist der Druck die einzige
         Rückmeldung, die man bekommt. */
      .tipp:active{background:rgba(127,127,127,.3)}
      .tipp.an{color:var(--an-farbe)}
      .tipp ha-icon{--mdc-icon-size:calc(22px * var(--skala)); display:block}

      .z3{display:flex; align-items:center; gap:6px; margin-top:7px;
        padding-top:6px; border-top:1px solid var(--divider-color);
        font-size:calc(.75rem * var(--skala)); color:var(--secondary-text-color)}
      .dann{flex:1 1 auto; min-width:0; overflow:hidden; text-overflow:ellipsis;
        white-space:nowrap}

      /* Kacheln, so viele nebeneinander wie hineinpassen. Die Mindestbreite
         ist bewusst großzügig: Bei 240 Pixeln zerfiel eine breite Karte in
         sechs schmale Spalten, in denen jeder Text dreizeilig umbrach. So
         bleiben es wenige, ruhige Kacheln, in denen alles lesbar steht. */


      .leer{padding:14px 0; color:var(--secondary-text-color); font-size:calc(.85rem * var(--skala));
        text-align:center}
      code{font-size:.85em}
    </style>`;
  }
}

/* ═══════════════════════════════════════════════════════════════════════
   Der Editor – die Karte einstellen, ohne YAML zu schreiben.

   Bewusst ohne Fremdbausteine: Ein Karteneditor, der `ha-form` oder Lit
   voraussetzt, geht kaputt, sobald Home Assistant daran etwas ändert. Reines
   DOM überlebt das.
   ═══════════════════════════════════════════════════════════════════════ */

const SCHALTER_FELDER = [
  ["show_funktionen", "Die Knöpfe oben (Automatik, Hitzeschutz, Urlaub, Fluchtweg)"],
  ["show_naechster", "Nächster Wechsel im ganzen Haus"],
  ["show_stoerungen", "Störungen melden"],
  ["show_helfer", "Freigabeschalter an den Kacheln"],
  ["allow_fahren", "Pfeiltasten zum Fahren"],
  ["gruppieren", "Nach Gruppen ordnen"],
];

class RolloplanerCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...DEFAULTS, ...config };
    this._zeichnen();
  }

  set hass(hass) { this._hass = hass; this._zeichnen(); }

  /* Welche Gruppen gibt es? Aus den Sensoren des Planers – so steht im Editor
     immer das, was das Add-on gerade führt, ohne zweite Konfiguration. */
  _gruppen() {
    const gefunden = [];
    for (const eid of Object.keys(this._hass?.states || {})) {
      if (!eid.startsWith("sensor.rolloplaner_rollo_")) continue;
      const a = this._hass.states[eid].attributes || {};
      const name = a.gruppe || a.raum || "";
      if (name && !gefunden.includes(name)) gefunden.push(name);
    }
    gefunden.sort((a, b) => a.localeCompare(b, "de"));
    // Was in der Konfiguration steht, kommt zuerst – in ihrer Reihenfolge.
    const gewaehlt = this._config.gruppen || this._config.raeume || null;
    if (!gewaehlt) return gefunden.map((n) => ({ name: n, an: true }));
    return [...gewaehlt.filter((n) => gefunden.includes(n)).map((n) => ({ name: n, an: true })),
            ...gefunden.filter((n) => !gewaehlt.includes(n)).map((n) => ({ name: n, an: false }))];
  }

  _melden(aenderung) {
    this._config = { ...this._config, ...aenderung };
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: this._config }, bubbles: true, composed: true,
    }));
    this._zeichnen();
  }

  _zeichnen() {
    if (!this._config) return;
    const c = this._config;
    const gruppen = this._gruppen();
    const alleAn = gruppen.every((g) => g.an);

    this.innerHTML = `<style>
      .rp-e{display:flex; flex-direction:column; gap:14px; padding:4px 0}
      .rp-e label{display:flex; flex-direction:column; gap:4px; font-size:.85rem;
        color:var(--secondary-text-color)}
      .rp-e input[type=text], .rp-e select{padding:8px 10px; border-radius:8px;
        border:1px solid var(--divider-color); background:var(--card-background-color);
        color:var(--primary-text-color); font:inherit; font-size:.95rem}
      .rp-e .haken{flex-direction:row; align-items:center; gap:10px;
        color:var(--primary-text-color); font-size:.92rem; cursor:pointer}
      .rp-e .haken input{margin:0}
      .rp-e h4{margin:6px 0 0; font-size:.8rem; letter-spacing:.06em;
        text-transform:uppercase; color:var(--secondary-text-color); font-weight:600}
      .rp-e .zeile{display:flex; align-items:center; gap:8px; padding:5px 8px;
        border:1px solid var(--divider-color); border-radius:8px}
      .rp-e .zeile span{flex:1 1 auto; color:var(--primary-text-color); font-size:.92rem}
      .rp-e .zeile button{border:none; background:none; cursor:pointer; padding:4px 8px;
        border-radius:6px; color:var(--secondary-text-color); font-size:1rem}
      .rp-e .zeile button:hover{background:rgba(127,127,127,.18)}
      .rp-e .hinweis{font-size:.78rem; color:var(--secondary-text-color); margin:0}
    </style>
    <div class="rp-e">
      <label>Überschrift
        <input type="text" id="rp-titel" value="${(c.title || "").replace(/"/g, "&quot;")}"></label>

      <label>Schriftgröße
        <select id="rp-groesse">
          ${Object.keys(TEXTSKALA).map((k) => `<option value="${k}"
            ${c.textgroesse === k ? "selected" : ""}>${k} (${TEXTSKALA[k]}×)</option>`).join("")}
        </select></label>
      <p class="hinweis">Größer heißt auch breitere Kacheln und größere
        Tasten – gedacht für ein Wandtablett, das man aus anderthalb Metern
        abliest.</p>

      <h4>Was die Karte zeigt</h4>
      ${SCHALTER_FELDER.map(([feld, text]) => `<label class="haken">
        <input type="checkbox" data-feld="${feld}" ${c[feld] ? "checked" : ""}>
        ${text}</label>`).join("")}

      <h4>Gruppen: Auswahl und Reihenfolge</h4>
      ${gruppen.length ? gruppen.map((g, i) => `<div class="zeile">
        <input type="checkbox" data-gruppe="${g.name.replace(/"/g, "&quot;")}"
               ${g.an ? "checked" : ""}>
        <span>${g.name}</span>
        <button data-hoch="${i}" ${i ? "" : "disabled"} title="nach oben">↑</button>
        <button data-runter="${i}" ${i === gruppen.length - 1 ? "" : ""}
                ${i === gruppen.length - 1 ? "disabled" : ""} title="nach unten">↓</button>
      </div>`).join("")
        : `<p class="hinweis">Noch keine Gruppen gefunden. Der Planer legt sie
             im Reiter <i>Gruppen</i> an.</p>`}
      <p class="hinweis">${alleAn
        ? "Alle Gruppen werden gezeigt. Die Reihenfolge hier gilt vor der aus dem Add-on."
        : "Nur die angehakten Gruppen erscheinen auf dieser Karte."}</p>
    </div>`;

    this.querySelector("#rp-titel").onchange = (e) =>
      this._melden({ title: e.target.value });
    this.querySelector("#rp-groesse").onchange = (e) =>
      this._melden({ textgroesse: e.target.value });
    this.querySelectorAll("[data-feld]").forEach((el) => {
      el.onchange = () => this._melden({ [el.dataset.feld]: el.checked });
    });

    const reihenfolge = () => [...this.querySelectorAll("[data-gruppe]")]
      .map((el) => el.dataset.gruppe);
    const gewaehlte = () => [...this.querySelectorAll("[data-gruppe]")]
      .filter((el) => el.checked).map((el) => el.dataset.gruppe);

    this.querySelectorAll("[data-gruppe]").forEach((el) => {
      el.onchange = () => {
        const an = gewaehlte();
        // Alle angehakt und in der Reihenfolge des Alphabets heißt: keine
        // Einschränkung. Dann bleibt `gruppen` leer, und die Karte folgt der
        // Ordnung aus dem Add-on.
        const alle = reihenfolge();
        this._melden({ gruppen: an.length === alle.length ? null : an, raeume: null });
      };
    });
    const schieben = (von, nach) => {
      const alle = reihenfolge();
      const [x] = alle.splice(von, 1);
      alle.splice(nach, 0, x);
      const an = new Set(gewaehlte());
      this._melden({ gruppen: alle.filter((n) => an.has(n)), raeume: null });
    };
    this.querySelectorAll("[data-hoch]").forEach((el) => {
      el.onclick = () => schieben(Number(el.dataset.hoch), Number(el.dataset.hoch) - 1);
    });
    this.querySelectorAll("[data-runter]").forEach((el) => {
      el.onclick = () => schieben(Number(el.dataset.runter), Number(el.dataset.runter) + 1);
    });
  }
}

customElements.define("rolloplaner-card-editor", RolloplanerCardEditor);
customElements.define("rolloplaner-card", RolloplanerCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "rolloplaner-card",
  name: "Rolloplaner",
  description: "Räume, Funktionsschalter und der nächste Wechsel des Rolloplaner Add-ons",
  preview: true,
});
