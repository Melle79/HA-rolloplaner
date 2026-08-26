/* Rolloplaner-Card – Lovelace Custom Card für das Rolloplaner Add-on
 *
 * Minimale Konfiguration:
 *   type: custom:rolloplaner-card
 *
 * Die Karte findet ihre Räume selbst: Alles, was als `sensor.rolloplaner_raum_*`
 * in Home Assistant steht, taucht auf. Geschaltet wird über die Schalter, die
 * das Add-on per MQTT anlegt – die Karte kennt keine eigene Logik und keinen
 * eigenen Zustand.
 *
 * Sie tritt an die Stelle der Kachelreihe aus neun `input_boolean`-Helfern.
 * Der Unterschied ist mehr als kosmetisch: Ein Helfer war nur eine Bedingung
 * in einer Automation, die zu ihrer Uhrzeit lief – wer ihn umlegte, bewegte
 * nie ein Rollo. Diese Schalter greifen sofort.
 */
const CARD_VERSION = "1.0.0";
console.info(`%c ROLLOPLANER-CARD %c v${CARD_VERSION} `,
  "color:#06172a;background:#5aa9e6;font-weight:700", "color:#5aa9e6;background:#1f2630");

const DEFAULTS = {
  title: "Rollos",
  show_funktionen: true,
  show_raeume: true,
  show_naechster: true,
  show_stoerungen: true,
  allow_fahren: true,
  raeume: null,          // null = alle, sonst Liste von Raumnamen
};

const FUNKTIONEN = [
  ["switch.rolloplaner_automatik", "Automatik", "mdi:home-automation"],
  ["switch.rolloplaner_beschattung", "Hitzeschutz", "mdi:sun-thermometer"],
  ["switch.rolloplaner_urlaubssimulation", "Urlaubssimulation", "mdi:shield-home"],
];

const ZUSTAND_TEXT = {
  plan: "Zeitplan", beschattung: "Hitzeschutz", urlaub: "Urlaub",
  rauch: "Rauchsperre", fenster: "Fenster offen", manuell: "Handbetrieb",
  aus: "aus", gesperrt: "gesperrt", ohne_plan: "kein Plan",
  nur_schliessen: "nur schließen",
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

  getCardSize() { return 5; }

  static getStubConfig() { return { ...DEFAULTS }; }

  set hass(hass) {
    this._hass = hass;
    const status = hass.states["sensor.rolloplaner_status"];
    const raeume = this._raeumeSammeln(hass);
    // Nur neu zeichnen, wenn sich wirklich etwas geändert hat – sonst verliert
    // jeder Klick auf einen Schalter den Fokus, während die Karte sich unter
    // den Fingern neu aufbaut.
    const signatur = JSON.stringify([
      status && status.state,
      FUNKTIONEN.map(([e]) => hass.states[e] && hass.states[e].state),
      raeume.map((r) => [r.sensor.state, r.sensor.attributes.zustand,
                         r.sensor.attributes.begruendung,
                         r.schalter && r.schalter.state]),
      hass.states["sensor.rolloplaner_naechster_wechsel"]?.state,
      hass.states["binary_sensor.rolloplaner_stoerung"]?.state,
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
          name: (sensor.attributes.friendly_name || e).replace(/^Rollo\s+/, ""),
          sensor,
          schalter: hass.states[schalterId] || null,
        };
      })
      .filter((r) => !gewuenscht || gewuenscht.includes(r.name))
      .sort((a, b) => a.name.localeCompare(b.name, "de"));
  }

  _schalten(entityId, an) {
    this._hass.callService("switch", an ? "turn_on" : "turn_off",
      { entity_id: entityId });
  }

  _fahrbefehl(raumId, position) {
    // Der Raum wird über seine ID angesprochen, nicht über den Namen: Ein
    // umbenannter Raum behält seine ID, und die Karte muss nicht raten.
    this._hass.callService("mqtt", "publish", {
      topic: "rolloplaner/cmd",
      payload: JSON.stringify({ befehl: "fahren", raum: raumId, position }),
    });
  }

  _render(status, raeume) {
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    const c = this._config;

    if (!status) {
      this.shadowRoot.innerHTML = `<ha-card><div class="leer">
        Entitäten des Rolloplaner Add-ons nicht gefunden
        (<code>sensor.rolloplaner_status</code>). Läuft das Add-on, und ist
        MQTT eingerichtet?</div></ha-card>${this._stil()}`;
      return;
    }

    const a = status.attributes || {};
    const rauch = this._hass.states["binary_sensor.rolloplaner_rauchsperre"];
    const stoerung = this._hass.states["binary_sensor.rolloplaner_stoerung"];
    const naechster = this._hass.states["sensor.rolloplaner_naechster_wechsel"];

    let kopf = `<div class="kopf">
      <div class="k-links">
        <ha-icon icon="mdi:window-shutter"></ha-icon>
        <div>
          <div class="k-titel">${c.title}</div>
          <div class="k-status">${status.state}</div>
        </div>
      </div>
      <div class="k-rechts">
        ${a.sonnenaufgang ? `<span title="Sonnenaufgang">
          <ha-icon icon="mdi:weather-sunset-up"></ha-icon>
          ${this._uhr(a.sonnenaufgang)}</span>` : ""}
        ${a.sonnenuntergang ? `<span title="Sonnenuntergang">
          <ha-icon icon="mdi:weather-sunset-down"></ha-icon>
          ${this._uhr(a.sonnenuntergang)}</span>` : ""}
        ${a.aussentemperatur !== null && a.aussentemperatur !== undefined
          ? `<span><ha-icon icon="mdi:thermometer"></ha-icon>
             ${a.aussentemperatur} °C</span>` : ""}
      </div>
    </div>`;

    let warnung = "";
    if (rauch && rauch.state === "on") {
      warnung += `<div class="warnung rauch"><ha-icon icon="mdi:smoke-detector-variant-alert">
        </ha-icon>Rauchsperre – der Planer fasst gerade kein Rollo an.
        ${this._esc(rauch.attributes.grund || "")}</div>`;
    }
    if (c.show_stoerungen && stoerung && stoerung.state === "on") {
      warnung += `<div class="warnung">
        <ha-icon icon="mdi:window-shutter-alert"></ha-icon>
        <div>${(stoerung.attributes.meldungen || []).map((m) =>
          `<div>${this._esc(m)}</div>`).join("")}</div></div>`;
    }

    let funktionen = "";
    if (c.show_funktionen) {
      funktionen = `<div class="funktionen">` + FUNKTIONEN.map(([entityId, name, icon]) => {
        const zustand = this._hass.states[entityId];
        if (!zustand) return "";
        const an = zustand.state === "on";
        return `<button class="fn ${an ? "an" : ""}" data-schalter="${entityId}"
                        data-an="${an ? "0" : "1"}">
          <ha-icon icon="${icon}"></ha-icon><span>${name}</span></button>`;
      }).join("") + `</div>`;
    }

    let naechsterHtml = "";
    if (c.show_naechster && naechster && naechster.state
        && naechster.state !== "kein Wechsel geplant") {
      naechsterHtml = `<div class="naechster">
        <ha-icon icon="mdi:clock-outline"></ha-icon>
        <span>Als Nächstes: ${this._esc(naechster.state)}</span></div>`;
    }

    let raumHtml = "";
    if (c.show_raeume) {
      raumHtml = `<div class="raeume">` + raeume.map((r) => {
        const attrs = r.sensor.attributes || {};
        const zustand = attrs.zustand || "plan";
        const an = !r.schalter || r.schalter.state === "on";
        const wert = Number(r.sensor.state);
        const breite = Number.isNaN(wert) ? 0 : Math.max(0, Math.min(100, wert));
        return `<div class="raum ${an ? "" : "ausgeschaltet"}">
          <div class="r-kopf">
            <span class="r-name">${this._esc(r.name)}</span>
            <span class="r-schild s-${zustand}">${ZUSTAND_TEXT[zustand] || zustand}</span>
            <span class="r-wert">${stellungstext(r.sensor.state)}</span>
          </div>
          <div class="balken"><i style="width:${breite}%"></i></div>
          <div class="r-fuss">
            <span class="r-grund">${this._esc(attrs.begruendung || "")}</span>
            ${attrs.naechste_uhrzeit
              ? `<span class="r-dann">${stellungstext(attrs.naechste_stellung)}
                 um ${this._esc(attrs.naechste_uhrzeit)}</span>` : ""}
            ${c.allow_fahren && attrs.raum_id ? `
              <button class="kipp" data-fahren="${attrs.raum_id}" data-position="100"
                      title="öffnen"><ha-icon icon="mdi:arrow-up"></ha-icon></button>
              <button class="kipp" data-fahren="${attrs.raum_id}" data-position="0"
                      title="schließen"><ha-icon icon="mdi:arrow-down"></ha-icon></button>` : ""}
            ${r.schalter ? `<button class="kipp ${an ? "an" : ""}"
                data-schalter="${r.schalter.entity_id}" data-an="${an ? "0" : "1"}"
                title="Automatik für diesen Raum">
                <ha-icon icon="mdi:${an ? "check" : "close"}"></ha-icon></button>` : ""}
          </div>
        </div>`;
      }).join("") + `</div>`;
      if (!raeume.length) {
        raumHtml = `<div class="leer">Noch kein Raum eingerichtet.</div>`;
      }
    }

    this.shadowRoot.innerHTML = `<ha-card>
      ${kopf}${warnung}${funktionen}${naechsterHtml}${raumHtml}
    </ha-card>${this._stil()}`;

    this.shadowRoot.querySelectorAll("[data-schalter]").forEach((el) => {
      el.addEventListener("click", () =>
        this._schalten(el.dataset.schalter, el.dataset.an === "1"));
    });
    this.shadowRoot.querySelectorAll("[data-fahren]").forEach((el) => {
      el.addEventListener("click", () =>
        this._fahrbefehl(el.dataset.fahren, Number(el.dataset.position)));
    });
  }

  _uhr(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? ""
      : d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
  }

  _esc(text) {
    return String(text ?? "").replace(/[&<>"]/g,
      (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }

  _stil() {
    return `<style>
      ha-card{padding:12px 16px 16px}
      .kopf{display:flex; align-items:center; gap:12px; flex-wrap:wrap;
        padding-bottom:10px; border-bottom:1px solid var(--divider-color)}
      .k-links{display:flex; align-items:center; gap:10px; flex:1; min-width:150px}
      .k-links ha-icon{--mdc-icon-size:26px; color:var(--state-icon-color,#5aa9e6)}
      .k-titel{font-size:1.05rem; font-weight:600; line-height:1.2}
      .k-status{font-size:.82rem; color:var(--secondary-text-color)}
      .k-rechts{display:flex; gap:12px; font-size:.82rem;
        color:var(--secondary-text-color); flex-wrap:wrap}
      .k-rechts span{display:inline-flex; align-items:center; gap:3px}
      .k-rechts ha-icon{--mdc-icon-size:16px}

      .warnung{display:flex; gap:8px; align-items:flex-start; margin-top:10px;
        padding:8px 10px; border-radius:8px; font-size:.84rem;
        background:var(--warning-color,#e0a44a); color:#20160a}
      .warnung.rauch{background:var(--error-color,#e36d6d); color:#2a0f0f}
      .warnung ha-icon{--mdc-icon-size:18px; flex:none}

      .funktionen{display:flex; gap:8px; flex-wrap:wrap; margin-top:12px}
      .fn{display:inline-flex; align-items:center; gap:6px; border:1px solid
        var(--divider-color); background:transparent; color:var(--secondary-text-color);
        border-radius:20px; padding:5px 12px; font-size:.84rem; font-weight:500;
        cursor:pointer; font-family:inherit}
      .fn ha-icon{--mdc-icon-size:17px}
      .fn:hover{border-color:var(--primary-text-color); color:var(--primary-text-color)}
      .fn.an{background:var(--primary-color,#5aa9e6); border-color:transparent;
        color:var(--text-primary-color,#fff)}

      .naechster{display:flex; align-items:center; gap:6px; margin-top:12px;
        font-size:.84rem; color:var(--secondary-text-color)}
      .naechster ha-icon{--mdc-icon-size:16px}

      .raeume{margin-top:12px; display:grid; gap:10px}
      .raum{padding:8px 10px; border-radius:10px;
        background:var(--secondary-background-color)}
      .raum.ausgeschaltet{opacity:.5}
      .r-kopf{display:flex; align-items:center; gap:8px}
      .r-name{font-weight:600; font-size:.92rem; flex:1; min-width:0;
        overflow:hidden; text-overflow:ellipsis; white-space:nowrap}
      .r-wert{font-size:.92rem; font-variant-numeric:tabular-nums}
      .r-schild{font-size:.7rem; font-weight:600; padding:1px 8px; border-radius:20px;
        background:var(--divider-color); color:var(--secondary-text-color);
        white-space:nowrap}
      .s-beschattung{background:#3d3016; color:#e8c07d}
      .s-urlaub{background:#173a2c; color:#79d3a8}
      .s-rauch{background:#3f1d1d; color:#f0a0a0}
      .s-fenster{background:#2f2a45; color:#b8aae4}
      .s-manuell{background:#2f3540; color:#b5bdc9}

      .balken{height:5px; border-radius:3px; background:var(--divider-color);
        overflow:hidden; margin:6px 0}
      .balken > i{display:block; height:100%; border-radius:3px;
        background:var(--primary-color,#5aa9e6)}
      .r-fuss{display:flex; align-items:center; gap:8px; font-size:.78rem;
        color:var(--secondary-text-color)}
      .r-grund{flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis;
        white-space:nowrap}
      .r-dann{white-space:nowrap}
      .kipp{border:none; background:transparent; cursor:pointer; padding:2px;
        color:var(--secondary-text-color); border-radius:6px}
      .kipp.an{color:var(--primary-color,#5aa9e6)}
      .kipp ha-icon{--mdc-icon-size:18px; display:block}

      .leer{padding:16px 0; color:var(--secondary-text-color); font-size:.86rem;
        text-align:center}
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
