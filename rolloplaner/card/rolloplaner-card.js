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
const CARD_VERSION = "2.1.0";
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
  raeume: null,             // null = alle, sonst Liste von Raumnamen
  gruppieren: true,         // nach Raum ordnen
};

const FUNKTIONEN = [
  ["switch.rolloplaner_automatik", "Automatik", "mdi:home-automation"],
  ["switch.rolloplaner_beschattung", "Hitzeschutz", "mdi:sun-thermometer"],
  ["switch.rolloplaner_urlaubssimulation", "Urlaub", "mdi:shield-home"],
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
  fenster: "Fenster offen", manuell: "Handbetrieb", aus: "aus",
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
                         r.schalter && r.schalter.state]),
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
    const gewuenscht = this._config.raeume;
    return Object.keys(hass.states)
      .filter((e) => e.startsWith("sensor.rolloplaner_rollo_"))
      .map((e) => {
        const sensor = hass.states[e];
        const schalterId = e.replace(/^sensor\./, "switch.") + "_an";
        return {
          id: e,
          // Home Assistant stellt den Gerätenamen voran: aus „Rollo Büro“ wird
          // „Rolloplaner Rollo Büro“. Beides muss weg, sonst steht auf jeder
          // Zeile zweimal dasselbe.
          name: (sensor.attributes.friendly_name || e)
            .replace(/^Rolloplaner\s+/, "").replace(/^Rollo\s+/, ""),
          raum: sensor.attributes.raum || "",
          sensor,
          schalter: hass.states[schalterId] || null,
        };
      })
      .filter((r) => !gewuenscht || gewuenscht.includes(r.raum))
      .sort((a, b) => (a.raum || "").localeCompare(b.raum || "", "de")
                      || a.name.localeCompare(b.name, "de"));
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
      this.shadowRoot.innerHTML = `<ha-card><div class="rand"><div class="leer">
        Entitäten des Rolloplaner Add-ons nicht gefunden
        (<code>sensor.rolloplaner_status</code>). Läuft das Add-on, und ist
        MQTT eingerichtet?</div></div></ha-card>${this._stil()}`;
      return;
    }

    const a = status.attributes || {};
    const rauch = this._hass.states["binary_sensor.rolloplaner_rauchsperre"];
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
    if (rauch && rauch.state === "on") {
      warnung += `<div class="warnung rauch">
        <ha-icon icon="mdi:smoke-detector-variant-alert"></ha-icon>
        <div>Rauchsperre – der Planer fasst gerade kein Rollo an.
        ${this._esc(rauch.attributes.grund || "")}</div></div>`;
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
        // Ein durchgehendes Raster mit Raumüberschriften darin: Ein eigenes
        // Raster je Raum ließe die Kachel eines Einzelrollos über die ganze
        // Breite laufen.
        const nachRaum = new Map();
        rollos.forEach((r) => {
          const raum = r.raum || "Ohne Bereich";
          if (!nachRaum.has(raum)) nachRaum.set(raum, []);
          nachRaum.get(raum).push(r);
        });
        rolloHtml = `<div class="raeume">${[...nachRaum].map(([raum, liste]) =>
          `<div class="raumtitel">${this._esc(raum)}</div>`
          + liste.map((r) => this._rollo(r)).join("")).join("")}</div>`;
      } else {
        rolloHtml = `<div class="raeume">${rollos.map((r) => this._rollo(r)).join("")}</div>`;
      }
    }

    this.shadowRoot.innerHTML = `<ha-card>
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

    const zahl = Number(r.sensor.state);
    const wert = Number.isNaN(zahl) ? "–" : zahl;

    return `<div class="raum ${an ? "" : "ruht"}">
      <div class="z1">
        ${rollobild(attrs.stellung_ha === null || attrs.stellung_ha === undefined
                    ? r.sensor.state : attrs.stellung_ha, attrs.art)}
        <div class="z1-text">
          <div class="namenzeile">
            <span class="name" title="${this._esc(r.name)}">${this._esc(r.name)}</span>${schild}
          </div>
          <div class="grund">${this._esc(attrs.begruendung || "")}</div>
        </div>
        <div class="z1-wert">
          <span class="wert">${wert}<small>${Number.isNaN(zahl) ? "" : "%"}</small></span>
          <span class="lage">${stellungstext(r.sensor.state, inv)}</span>
        </div>
      </div>
      ${c.show_helfer ? this._helfer(attrs.helfer || []) : ""}
      <div class="z3">
        <span class="dann">${attrs.zeitplan
          ? `<span class="planschild">${this._esc(attrs.zeitplan)}</span> ` : ""}${dann}</span>
        <span class="knoepfe">${knoepfe}${kippe}</span>
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

  _helfer(helfer) {
    // Zwei Schalter desselben Raumes können dieselbe Wirkung haben – dann
    // stünde zweimal „schließen“ nebeneinander und niemand wüsste, welcher
    // welcher ist. In dem Fall kommt der Name des Schalters dazu.
    const wirkung = (h) => (h.wirkungen || [h.wirkung])
      .map((w) => WIRKUNG[w] || w).join(" und ");
    const zaehler = {};
    helfer.forEach((h) => { const w = wirkung(h); zaehler[w] = (zaehler[w] || 0) + 1; });
    const teile = helfer.map((h) => {
      const w = wirkung(h);
      return this._chip(h, false,
        zaehler[w] > 1 ? `${w}: ${this._kurzname(h.name)}` : null);
    }).join("");
    if (!teile) return "";
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

  _uhr(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? ""
      : d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
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
      ha-card{display:block; overflow:hidden; container-type:inline-size}
      .rand{padding:14px 16px 12px}

      .kopf{display:flex; align-items:center; gap:10px; flex-wrap:wrap}
      .k-icon{--mdc-icon-size:26px; flex:none;
        color:var(--state-icon-color, var(--primary-color))}
      .k-text{flex:1 1 auto; min-width:110px}
      .k-titel{font-size:1.15rem; font-weight:500; line-height:1.25;
        color:var(--primary-text-color)}
      .k-status{font-size:.8rem; color:var(--secondary-text-color)}
      .k-rechts{display:flex; gap:12px; font-size:.8rem; flex-wrap:wrap;
        color:var(--secondary-text-color)}
      .k-rechts span{display:inline-flex; align-items:center; gap:3px;
        white-space:nowrap}
      .k-rechts ha-icon{--mdc-icon-size:16px}

      .warnung{display:flex; gap:8px; align-items:flex-start; margin-top:10px;
        padding:8px 10px; border-radius:8px; font-size:.84rem;
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
        padding:4px 11px; font-size:.8rem; font-weight:500; font-family:inherit;
        color:var(--secondary-text-color)}
      .fn ha-icon{--mdc-icon-size:16px}
      .fn:hover{color:var(--primary-text-color)}
      .fn.an{background:var(--primary-color); border-color:transparent;
        color:var(--text-primary-color,#fff)}

      .naechster{display:flex; align-items:center; gap:6px; margin-top:10px;
        font-size:.8rem; color:var(--secondary-text-color)}
      .naechster ha-icon{--mdc-icon-size:15px; flex:none}

      /* ── Die geteilten Schalter, einmal oben ── */
      .freigaben{margin-top:12px; padding-top:10px;
        border-top:1px solid var(--divider-color)}
      .f-titel{font-size:.7rem; letter-spacing:.06em; text-transform:uppercase;
        color:var(--secondary-text-color); opacity:.8; margin-bottom:6px}
      .f-liste{display:flex; gap:5px; flex-wrap:wrap; align-items:center}
      .raumtitel{grid-column:1/-1; font-size:.68rem; letter-spacing:.09em;
        text-transform:uppercase; color:var(--secondary-text-color); opacity:.85;
        font-weight:600; padding:6px 0 3px; border-bottom:1px solid var(--divider-color)}
      .raumtitel:first-child{padding-top:0}
      .planschild{display:inline-block; padding:0 6px; border-radius:12px;
        background:rgba(127,127,127,.2); color:var(--secondary-text-color);
        font-size:.68rem; font-weight:600}

      /* ── Ein Chip, ein Aussehen – oben wie in der Kachel ── */
      .chip{display:inline-flex; align-items:center; gap:5px; cursor:pointer;
        border:1px solid var(--divider-color); background:none; border-radius:14px;
        padding:2px 9px 2px 7px; font-family:inherit; font-weight:500;
        font-size:.74rem; color:var(--secondary-text-color); line-height:1.5;
        max-width:100%}
      /* Der Punkt davor sagt an oder aus. Ein bloß etwas hellerer Hintergrund
         reicht dafür nicht – ein Schalter, dessen Stellung man raten muss, ist
         kein Schalter. */
      .chip::before{content:""; width:7px; height:7px; border-radius:50%; flex:none;
        background:currentColor; opacity:.3}
      .chip:hover{color:var(--primary-text-color)}
      .chip.an{color:var(--primary-text-color); border-color:var(--primary-color);
        background:rgba(127,127,127,.14)}
      .chip.an::before{background:var(--primary-color); opacity:1}
      .chip.auswahl{padding-right:3px; cursor:default}
      .chip.auswahl::before{background:var(--primary-color); opacity:1}
      .c-text{overflow:hidden; text-overflow:ellipsis; white-space:nowrap}
      .chip select{border:none; background:none; font-family:inherit;
        font-size:.74rem; color:var(--primary-text-color); cursor:pointer;
        padding:1px 2px; max-width:110px}
      .chip select:focus{outline:none}
      .chipzeile{display:flex; gap:5px; flex-wrap:wrap; align-items:center;
        margin-top:7px}
      .c-titel{font-size:.7rem; color:var(--secondary-text-color); opacity:.75}

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
      .raeume{display:grid; gap:8px; padding:0 12px 12px; align-items:stretch;
        grid-template-columns:1fr}
      .raum{display:flex; flex-direction:column;
        border:1px solid var(--divider-color); border-radius:10px;
        padding:10px 11px 8px}
      .raum.ruht{opacity:.5}

      .z1{display:flex; align-items:flex-start; gap:10px}
      .z1-text{flex:1 1 auto; min-width:0}
      .namenzeile{display:flex; align-items:baseline; gap:6px; min-width:0;
        flex-wrap:wrap}
      /* Umbrechen statt abschneiden: „Wohnzimmer – Terrassentür“ ist der
         Name, an dem man die Kachel erkennt – „Wohnzimmer – …“ ist keiner. */
      .name{font-size:1rem; font-weight:500; color:var(--primary-text-color);
        min-width:0; overflow-wrap:anywhere; line-height:1.25}
      .grund{font-size:.76rem; color:var(--secondary-text-color); margin-top:2px;
        display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;
        overflow:hidden}
      .z1-wert{display:flex; flex-direction:column; align-items:flex-end; flex:none}
      .wert{font-size:1.5rem; font-weight:300; line-height:1.1;
        color:var(--primary-text-color); font-variant-numeric:tabular-nums}
      .wert small{font-size:.62em; color:var(--secondary-text-color); margin-left:1px}
      .lage{font-size:.7rem; color:var(--secondary-text-color)}
      .schild{font-size:.66rem; font-weight:600; padding:1px 7px; border-radius:18px;
        white-space:nowrap; letter-spacing:.02em; flex:none;
        background:rgba(127,127,127,.22); color:var(--primary-text-color)}
      .s-rauch{background:rgba(227,109,109,.3)}
      .s-fenster,.s-manuell{background:rgba(224,164,74,.3)}

      .knoepfe{display:flex; gap:1px; flex:none}
      .tipp{border:none; background:none; cursor:pointer; padding:3px;
        border-radius:6px; color:var(--secondary-text-color); line-height:0}
      .tipp:hover{color:var(--primary-text-color); background:rgba(127,127,127,.18)}
      .tipp.an{color:var(--primary-color)}
      .tipp ha-icon{--mdc-icon-size:18px; display:block}

      .z3{display:flex; align-items:center; gap:8px; margin-top:auto;
        padding-top:7px; font-size:.75rem; color:var(--secondary-text-color)}
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

      .knoepfe{display:flex; gap:1px; flex:none}
      .tipp{border:none; background:none; cursor:pointer; padding:3px;
        border-radius:6px; color:var(--secondary-text-color); line-height:0}
      .tipp:hover{color:var(--primary-text-color); background:rgba(127,127,127,.18)}
      .tipp.an{color:var(--primary-color)}
      .tipp ha-icon{--mdc-icon-size:18px; display:block}

      .z3{display:flex; align-items:center; gap:8px; margin-top:7px;
        padding-top:6px; border-top:1px solid var(--divider-color);
        font-size:.75rem; color:var(--secondary-text-color)}
      .dann{flex:1 1 auto; min-width:0; overflow:hidden; text-overflow:ellipsis;
        white-space:nowrap}

      @container (min-width: 580px){
        .raeume{grid-template-columns:repeat(2, 1fr)}
      }
      @container (min-width: 880px){
        /* Ab hier: eine Zeile je Rollo über die ganze Breite.

           Als Raster mit festen Spalten, nicht als Flexbox: In einer Flexbox
           dehnte sich der Textteil über den ganzen freien Platz und drückte
           alles Übrige an den rechten Rand – dazwischen klaffte ein Loch von
           tausend Pixeln. Ein Raster verteilt den Platz stattdessen auf
           Spalten, die untereinander fluchten, und genau das macht eine Liste
           lesbar.

           display:contents auf .z1 hebt die eine Verschachtelung auf, die im
           Weg steht: So werden Bild, Text und Zahl Geschwister der Schalter
           und Knöpfe und lassen sich einzeln in Spalten legen. */
        .raeume{grid-template-columns:1fr; gap:0}
        /* Der Platz gehört dem Text: Nur seine Spalte wächst, alles Übrige
           ist so breit wie sein Inhalt. Damit rückt die rechte Seite als Block
           zusammen, statt sich über die halbe Karte zu verteilen. */
        /* Jede Spalte muss schrumpfen können. Die Breitenangabe „auto“ tut
           das nicht: Eine Spalte mit langem Inhalt – etwa die Auswahl der
           Terrassentür – macht das Raster dann breiter als die Karte, und
           rechts fällt die Stellung über den Rand hinaus. Mit minmax(0, …)
           darf sie schrumpfen, und die Zelle schneidet ab, was nicht passt. */
        .raum{display:grid; align-items:center; gap:6px 18px;
          grid-template-columns:auto minmax(0, 2fr) minmax(0, 1.1fr)
                                minmax(150px, auto) auto auto;
          border:none; border-bottom:1px solid var(--divider-color);
          border-radius:0; padding:7px 6px}
        .raum > *{min-width:0}
        .raum:last-child{border-bottom:none}
        .z1{display:contents}
        /* Jedes Feld nennt Spalte **und** Zeile. Ohne die Zeile setzt das
           Raster automatisch weiter – und weil die Stellung im HTML vor den
           Schaltern steht, aber in die letzte Spalte gehört, landete alles
           Nachfolgende in einer zweiten Zeile. */
        .bild{grid-column:1; grid-row:1}
        .z1-text{grid-column:2; grid-row:1; min-width:0; display:flex;
          align-items:baseline; gap:10px; flex-wrap:wrap}
        /* Name und Begründung nebeneinander statt untereinander: Eine Zeile,
           die halb so hoch ist, lässt sich als Liste überfliegen. */
        .grund{-webkit-line-clamp:1; margin-top:0; flex:1 1 auto}
        .chipzeile{grid-column:3; grid-row:1; margin-top:0; min-width:0;
          flex-wrap:nowrap; overflow:hidden; justify-content:flex-start}
        /* Die Fußzeile wird aufgelöst: Im Kachelmodus gehören Zeit und
           Knöpfe zusammen in eine Zeile, hier in zwei Spalten. */
        .z3{display:contents}
        .dann{grid-column:4; grid-row:1; text-align:right; white-space:nowrap}
        .knoepfe{grid-column:5; grid-row:1}
        .z1-wert{grid-column:6; grid-row:1; flex-direction:row;
          align-items:baseline; gap:5px; justify-content:flex-end;
          min-width:86px; white-space:nowrap}
        .wert{font-size:1.2rem}
        .raumtitel{padding-top:14px}
      }

      .leer{padding:14px 0; color:var(--secondary-text-color); font-size:.85rem;
        text-align:center}
      code{font-size:.85em}
    </style>`;
  }
}

customElements.define("rolloplaner-card", RolloplanerCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "rolloplaner-card",
  name: "Rolloplaner",
  description: "Räume, Funktionsschalter und der nächste Wechsel des Rolloplaner Add-ons",
  preview: true,
});
