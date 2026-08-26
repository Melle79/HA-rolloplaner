/* Rolloplaner-Card – Lovelace Custom Card für das Rolloplaner Add-on
 *
 * Minimale Konfiguration:
 *   type: custom:rolloplaner-card
 *
 * Die Karte findet ihre Räume selbst: Alles, was als `sensor.rolloplaner_raum_*`
 * in Home Assistant steht, taucht auf. Geschaltet wird über die Entitäten, die
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
const CARD_VERSION = "1.1.0";
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
};

const FUNKTIONEN = [
  ["switch.rolloplaner_automatik", "Automatik", "mdi:home-automation"],
  ["switch.rolloplaner_beschattung", "Hitzeschutz", "mdi:sun-thermometer"],
  ["switch.rolloplaner_urlaubssimulation", "Urlaub", "mdi:shield-home"],
];

const ZUSTAND_TEXT = {
  beschattung: "Hitzeschutz", urlaub: "Urlaub", rauch: "Rauchsperre",
  fenster: "Fenster offen", manuell: "Handbetrieb", aus: "aus",
  gesperrt: "gesperrt", ohne_plan: "kein Plan", nur_schliessen: "nur schließen",
};

function stellungstext(p) {
  if (p === null || p === undefined || p === "unknown" || p === "") return "–";
  const n = Number(p);
  if (Number.isNaN(n)) return "–";
  if (n >= 100) return "offen";
  if (n <= 0) return "zu";
  return `${n} %`;
}

class RolloplanerCard extends HTMLElement {
  setConfig(config) {
    this._config = { ...DEFAULTS, ...config };
  }

  getCardSize() { return 4 + (this._raeumeAnzahl || 0); }

  static getStubConfig() { return { ...DEFAULTS }; }

  set hass(hass) {
    this._hass = hass;
    const status = hass.states["sensor.rolloplaner_status"];
    const raeume = this._raeumeSammeln(hass);
    this._raeumeAnzahl = raeume.length;
    // Nur neu zeichnen, wenn sich wirklich etwas geändert hat – sonst klappt
    // jede Auswahlliste zu, während man noch darin liest.
    const signatur = JSON.stringify([
      status && status.state,
      FUNKTIONEN.map(([e]) => hass.states[e] && hass.states[e].state),
      raeume.map((r) => [r.sensor.state, r.sensor.attributes.zustand,
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
    this._render(status, raeume);
  }

  _raeumeSammeln(hass) {
    const gewuenscht = this._config.raeume;
    return Object.keys(hass.states)
      .filter((e) => e.startsWith("sensor.rolloplaner_raum_"))
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
          sensor,
          schalter: hass.states[schalterId] || null,
        };
      })
      .filter((r) => !gewuenscht || gewuenscht.includes(r.name))
      .sort((a, b) => a.name.localeCompare(b.name, "de"));
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

  _fahrbefehl(raumId, position) {
    // Der Raum wird über seine ID angesprochen, nicht über den Namen: Ein
    // umbenannter Raum behält seine ID, und die Karte muss nicht raten.
    this._hass.callService("mqtt", "publish", {
      topic: "rolloplaner/cmd",
      payload: JSON.stringify({ befehl: "fahren", raum: raumId, position }),
    });
  }

  // -------------------------------------------------------------- Zeichnen ---

  _render(status, raeume) {
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

    let raumHtml = "";
    if (c.show_raeume) {
      raumHtml = raeume.length
        ? `<div class="raeume">${raeume.map((r) => this._raum(r)).join("")}</div>`
        : `<div class="rand"><div class="leer">Noch kein Raum eingerichtet.</div></div>`;
    }

    this.shadowRoot.innerHTML = `<ha-card>
      <div class="rand">${kopf}${warnung}${funktionen}${naechsterHtml}</div>
      ${raumHtml}
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

  _raum(r) {
    const c = this._config;
    const attrs = r.sensor.attributes || {};
    const zustand = attrs.zustand || "plan";
    const an = !r.schalter || r.schalter.state === "on";

    // Das Schild nur, wenn es etwas zu sagen hat: „Zeitplan“ an jedem der
    // sieben Räume ist keine Auskunft, sondern Grundrauschen – und es verdeckt
    // die eine Zeile, auf der wirklich „Hitzeschutz“ steht.
    const schild = ZUSTAND_TEXT[zustand]
      ? `<span class="schild s-${zustand}">${ZUSTAND_TEXT[zustand]}</span>` : "";

    const dann = attrs.naechste_uhrzeit
      ? `<span class="dann">${stellungstext(attrs.naechste_stellung)} um ${this._esc(attrs.naechste_uhrzeit)}</span>`
      : "";

    const knoepfe = c.allow_fahren && attrs.raum_id ? `
      <button class="tipp" data-fahren="${attrs.raum_id}" data-position="100"
              title="öffnen"><ha-icon icon="mdi:arrow-up"></ha-icon></button>
      <button class="tipp" data-fahren="${attrs.raum_id}" data-position="0"
              title="schließen"><ha-icon icon="mdi:arrow-down"></ha-icon></button>` : "";
    const kippe = r.schalter ? `<button class="tipp ${an ? "an" : ""}"
        data-schalter="${r.schalter.entity_id}" data-an="${an ? "0" : "1"}"
        title="Automatik für ${this._esc(r.name)}">
        <ha-icon icon="mdi:${an ? "robot" : "robot-off"}"></ha-icon></button>` : "";

    return `<div class="raum ${an ? "" : "ruht"}">
      <div class="z1">
        <span class="name">${this._esc(r.name)}</span>
        ${schild}
        <span class="wert">${stellungstext(r.sensor.state)}</span>
        <span class="knoepfe">${knoepfe}${kippe}</span>
      </div>
      <div class="z2">
        <span class="grund">${this._esc(attrs.begruendung || "")}</span>
        ${dann}
      </div>
      ${c.show_helfer ? this._helfer(attrs.helfer || []) : ""}
    </div>`;
  }

  _helfer(helfer) {
    if (!helfer.length) return "";
    const teile = helfer.map((h) => {
      const zustand = this._hass.states[h.entity_id];
      if (!zustand) return "";
      const kurz = this._kurzname(h.name);
      if (h.optionen && h.optionen.length) {
        return `<label class="helfer"><span>${this._esc(kurz)}</span>
          <select data-auswahl="${h.entity_id}">${h.optionen.map((o) =>
            `<option value="${this._esc(o)}"${o === zustand.state ? " selected" : ""}>${this._esc(o)}</option>`
          ).join("")}</select></label>`;
      }
      const an = zustand.state === "on";
      return `<button class="helfer knopf ${an ? "an" : ""}"
        data-schalter="${h.entity_id}" data-an="${an ? "0" : "1"}"
        >${this._esc(kurz)}</button>`;
    }).join("");
    return teile ? `<div class="helferzeile">${teile}</div>` : "";
  }

  _kurzname(name) {
    // „Helfer - Rollo EG schließen“ → „EG schließen“. Diese Vorsilben stehen in
    // jedem der Helfer und sagen auf einer Karte, die ohnehin „Rollos“ heißt,
    // gar nichts.
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
      ha-card{display:block; overflow:hidden}
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

      /* Kein eigener Zeilenhintergrund: In einem hellen Theme wäre er ein
         dunkler Fremdkörper, in einem dunklen ein Loch. Trennlinien nehmen die
         Farbe des Themes an und sehen überall richtig aus. */
      .raeume{border-top:1px solid var(--divider-color)}
      .raum{padding:9px 16px 10px; border-bottom:1px solid var(--divider-color)}
      .raum:last-child{border-bottom:none}
      .raum.ruht{opacity:.45}

      .z1{display:flex; align-items:center; gap:8px}
      .name{font-size:.95rem; font-weight:500; color:var(--primary-text-color);
        flex:1 1 auto; min-width:0; overflow:hidden; text-overflow:ellipsis;
        white-space:nowrap}
      .wert{font-size:.9rem; color:var(--primary-text-color); white-space:nowrap;
        font-variant-numeric:tabular-nums}
      .schild{font-size:.68rem; font-weight:600; padding:1px 7px; border-radius:18px;
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

      .z2{display:flex; align-items:baseline; gap:10px; margin-top:1px;
        font-size:.78rem; color:var(--secondary-text-color)}
      .grund{flex:1 1 auto; min-width:0; overflow:hidden; text-overflow:ellipsis;
        white-space:nowrap}
      .dann{white-space:nowrap; flex:none}

      .helferzeile{display:flex; gap:6px; flex-wrap:wrap; margin-top:7px;
        align-items:center}
      .helfer{font-size:.74rem; color:var(--secondary-text-color)}
      .helfer.knopf{display:inline-flex; align-items:center; gap:5px;
        cursor:pointer; border:1px solid var(--divider-color); background:none;
        border-radius:14px; padding:2px 9px 2px 7px; font-family:inherit;
        font-weight:500}
      /* Der Punkt davor sagt an oder aus. Ein bloß etwas hellerer Hintergrund
         reicht dafür nicht – in Svens Theme waren „an“ und „aus“ auf einen
         Blick nicht zu unterscheiden, und ein Schalter, dessen Stellung man
         raten muss, ist kein Schalter. */
      .helfer.knopf::before{content:""; width:7px; height:7px; border-radius:50%;
        flex:none; background:currentColor; opacity:.3}
      .helfer.knopf:hover{color:var(--primary-text-color)}
      .helfer.knopf.an{color:var(--primary-text-color);
        border-color:var(--primary-color); background:rgba(127,127,127,.14)}
      .helfer.knopf.an::before{background:var(--primary-color); opacity:1}
      label.helfer{display:inline-flex; align-items:center; gap:5px;
        border:1px solid var(--divider-color); border-radius:14px;
        padding:1px 4px 1px 9px}
      label.helfer select{border:none; background:none; font-family:inherit;
        font-size:.74rem; color:var(--primary-text-color); cursor:pointer;
        padding:2px}
      label.helfer select:focus{outline:none}

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
