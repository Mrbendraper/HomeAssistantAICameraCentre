/* AI Camera Centre Card (bundled with the ai_camera_centre integration)
 * Shows a rolling multi-camera AI alert timeline fetched over the
 * Home Assistant websocket API.
 *
 * Config:
 *   type: custom:ai-camera-centre-card
 *   title: Camera Alerts   (optional)
 *   days: 7                (optional client-side window, default 7)
 */

class AICameraCentreCard extends HTMLElement {
  static getStubConfig() {
    return { title: "Camera Alerts", days: 7 };
  }

  setConfig(config) {
    this._config = { title: "Camera Alerts", days: 7, ...config };
    this._filter = "all";
    this._expanded = null;
    this._lightbox = null;
    this._alerts = [];
    this._error = null;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._loadedOnce) {
      this._loadedOnce = true;
      this._load();
    }
  }

  connectedCallback() {
    if (this._loadedOnce) this._load();
    this._timer = setInterval(() => this._load(), 5 * 60 * 1000);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
  }

  async _load() {
    if (!this._hass) return;
    try {
      const resp = await this._hass.callWS({ type: "ai_camera_centre/alerts" });
      const cutoff = Date.now() / 1000 - this._config.days * 86400;
      this._alerts = (resp.alerts || [])
        .filter((r) => Number(r.ts) >= cutoff)
        .sort((a, b) => b.ts - a.ts);
      this._error = null;
    } catch (e) {
      this._error =
        "Could not load alerts: " + (e.message || e.code || String(e));
    }
    this._render();
  }

  _esc(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  _scoreColor(score) {
    return score <= 3 ? "#22c55e" : score <= 6 ? "#f59e0b" : "#ef4444";
  }

  _dayLabel(ts) {
    const d = new Date(ts * 1000);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const day = new Date(d);
    day.setHours(0, 0, 0, 0);
    const diff = Math.round((today - day) / 86400000);
    if (diff === 0) return "Today";
    if (diff === 1) return "Yesterday";
    return d.toLocaleDateString(undefined, {
      weekday: "long",
      day: "numeric",
      month: "short",
    });
  }

  _time(ts) {
    return new Date(ts * 1000).toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  _cameras() {
    const map = new Map();
    for (const a of this._alerts) {
      if (!map.has(a.camera)) map.set(a.camera, a.camera_label || a.camera);
    }
    return map;
  }

  _render() {
    const c = this._config;
    const cams = this._cameras();
    const filtered =
      this._filter === "all"
        ? this._alerts
        : this._alerts.filter((a) => a.camera === this._filter);

    const groups = [];
    let current = null;
    for (const a of filtered) {
      const label = this._dayLabel(a.ts);
      if (!current || current.label !== label) {
        current = { label, items: [] };
        groups.push(current);
      }
      current.items.push(a);
    }

    const chips =
      `<button class="chip ${this._filter === "all" ? "on" : ""}" data-cam="all">All</button>` +
      [...cams.entries()]
        .map(
          ([id, label]) =>
            `<button class="chip ${this._filter === id ? "on" : ""}" data-cam="${this._esc(id)}">${this._esc(label)}</button>`
        )
        .join("");

    let body;
    if (this._error) {
      body = `<div class="empty">${this._esc(this._error)}</div>`;
    } else if (!filtered.length) {
      body = `<div class="empty">No alerts in the last ${c.days} days.</div>`;
    } else {
      body = groups
        .map(
          (g) =>
            `<div class="day">${this._esc(g.label)} <span class="count">${g.items.length}</span></div>` +
            g.items.map((a) => this._row(a)).join("")
        )
        .join("");
    }

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { padding: 12px 0 4px; }
        .header {
          display: flex; align-items: center; justify-content: space-between;
          padding: 0 16px 8px;
        }
        .title { font-size: 16px; font-weight: 500; color: var(--primary-text-color); }
        .refresh {
          background: none; border: none; cursor: pointer; padding: 4px;
          color: var(--secondary-text-color); font-size: 16px; line-height: 1;
        }
        .chips { display: flex; gap: 6px; flex-wrap: wrap; padding: 0 16px 10px; }
        .chip {
          border: 1px solid var(--divider-color); border-radius: 14px;
          background: none; color: var(--secondary-text-color);
          padding: 3px 12px; font-size: 12px; cursor: pointer;
        }
        .chip.on {
          background: var(--primary-color); border-color: var(--primary-color);
          color: var(--text-primary-color, #fff);
        }
        .day {
          padding: 8px 16px 4px; font-size: 12px; font-weight: 600;
          text-transform: uppercase; letter-spacing: 0.5px;
          color: var(--secondary-text-color);
        }
        .count {
          background: var(--divider-color); border-radius: 8px;
          padding: 1px 7px; font-size: 11px; margin-left: 4px;
        }
        .row {
          display: flex; gap: 10px; align-items: center;
          padding: 8px 16px; cursor: pointer;
        }
        .row:hover { background: var(--secondary-background-color); }
        .thumb {
          width: 72px; height: 48px; object-fit: cover; border-radius: 6px;
          background: var(--divider-color); flex-shrink: 0;
        }
        .meta { flex: 1; min-width: 0; }
        .line1 { display: flex; align-items: center; gap: 8px; margin-bottom: 2px; }
        .time { font-size: 12px; color: var(--secondary-text-color); white-space: nowrap; }
        .cam { font-size: 12px; font-weight: 600; color: var(--primary-text-color); white-space: nowrap; }
        .badge {
          font-size: 11px; font-weight: 700; color: #fff;
          border-radius: 9px; padding: 1px 7px; margin-left: auto;
        }
        .short {
          font-size: 13px; color: var(--primary-text-color);
          overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
        }
        .detail-panel { padding: 4px 16px 14px; }
        .detail-panel img {
          width: 100%; border-radius: 8px; margin-bottom: 10px; display: block;
          cursor: zoom-in;
        }
        .lightbox {
          position: fixed; inset: 0; z-index: 9999;
          background: rgba(0, 0, 0, 0.9);
          display: flex; align-items: center; justify-content: center;
          cursor: zoom-out;
        }
        .lightbox img {
          max-width: 96vw; max-height: 92vh; border-radius: 6px;
          box-shadow: 0 8px 40px rgba(0, 0, 0, 0.6);
        }
        .lb-close {
          position: fixed; top: 12px; right: 16px;
          background: none; border: none; color: #fff;
          font-size: 34px; line-height: 1; cursor: pointer; padding: 4px;
        }
        .detail-text {
          font-size: 13px; line-height: 1.6; color: var(--primary-text-color);
          margin-bottom: 10px;
        }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 8px; }
        .cardlet {
          background: var(--secondary-background-color); border-radius: 8px;
          padding: 8px 10px;
        }
        .cardlet-label {
          color: var(--secondary-text-color); font-size: 10px;
          text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 3px;
        }
        .cardlet-value { color: var(--primary-text-color); font-size: 12px; }
        .risk {
          background: var(--secondary-background-color); border-radius: 8px;
          border-left: 3px solid #f59e0b; padding: 8px 10px;
        }
        .risk .cardlet-label { color: #f59e0b; }
        .empty {
          padding: 20px 16px; text-align: center; font-size: 13px;
          color: var(--secondary-text-color);
        }
      </style>
      <ha-card>
        <div class="header">
          <span class="title">${this._esc(c.title)}</span>
          <button class="refresh" title="Refresh">&#x21bb;</button>
        </div>
        <div class="chips">${chips}</div>
        ${body}
      </ha-card>
      ${
        this._lightbox
          ? `<div class="lightbox"><button class="lb-close" title="Close">&times;</button>
             <img src="${this._esc(this._lightbox)}"></div>`
          : ""
      }
    `;

    this.shadowRoot.querySelector(".refresh").addEventListener("click", () => this._load());
    this.shadowRoot.querySelectorAll(".chip").forEach((el) =>
      el.addEventListener("click", () => {
        this._filter = el.dataset.cam;
        this._expanded = null;
        this._render();
      })
    );
    this.shadowRoot.querySelectorAll(".row").forEach((el) =>
      el.addEventListener("click", () => {
        const id = el.dataset.id;
        this._expanded = this._expanded === id ? null : id;
        this._render();
      })
    );
    this.shadowRoot.querySelectorAll(".detail-img").forEach((el) =>
      el.addEventListener("click", (ev) => {
        ev.stopPropagation();
        this._lightbox = el.dataset.full;
        this._render();
      })
    );
    const lb = this.shadowRoot.querySelector(".lightbox");
    if (lb) {
      lb.addEventListener("click", () => {
        this._lightbox = null;
        this._render();
      });
    }
  }

  _row(a) {
    const id = a.camera + "_" + a.ts;
    const color = this._scoreColor(Number(a.score) || 1);
    let html = `
      <div class="row" data-id="${this._esc(id)}">
        <img class="thumb" src="${this._esc(a.image)}" loading="lazy"
             onerror="this.style.visibility='hidden'">
        <div class="meta">
          <div class="line1">
            <span class="time">${this._time(a.ts)}</span>
            <span class="cam">${this._esc(a.camera_label || a.camera)}</span>
            <span class="badge" style="background:${color}">${this._esc(a.score)}/10</span>
          </div>
          <div class="short">${this._esc(a.short)}</div>
        </div>
      </div>`;
    if (this._expanded === id) {
      const hasGate = a.gate_state && a.gate_state !== "n/a";
      const known = a.known_person && a.known_person !== "none" ? a.known_person : null;
      html += `
      <div class="detail-panel">
        <img class="detail-img" src="${this._esc(a.image)}"
             data-full="${this._esc(a.image)}"
             onerror="this.style.display='none'">
        <div class="detail-text">${this._esc(a.detail)}</div>
        <div class="grid">
          ${known ? `<div class="cardlet"><div class="cardlet-label">Recognised</div>
            <div class="cardlet-value">&#128100; ${this._esc(known)}</div></div>` : ""}
          <div class="cardlet"><div class="cardlet-label">Direction</div>
            <div class="cardlet-value">${this._esc(a.direction || "unknown")}</div></div>
          <div class="cardlet"><div class="cardlet-label">Activity</div>
            <div class="cardlet-value">${this._esc(a.activity || "unknown")}</div></div>
          <div class="cardlet"><div class="cardlet-label">Carrying</div>
            <div class="cardlet-value">${this._esc(a.carrying || "unknown")}</div></div>
          ${hasGate ? `<div class="cardlet"><div class="cardlet-label">Gate</div>
            <div class="cardlet-value">${this._esc(a.gate_state)}</div></div>` : ""}
        </div>
        ${hasGate && a.gate_risk && a.gate_risk !== "n/a"
          ? `<div class="risk"><div class="cardlet-label">&#9888;&#65039; Risk Assessment</div>
             <div class="cardlet-value">${this._esc(a.gate_risk)}</div></div>`
          : ""}
      </div>`;
    }
    return html;
  }

  getCardSize() {
    return 6;
  }
}

customElements.define("ai-camera-centre-card", AICameraCentreCard);
// Legacy alias so dashboards created before the rename keep working.
if (!customElements.get("alert-history-card")) {
  customElements.define("alert-history-card", class extends AICameraCentreCard {});
}

/* Known-people management card: upload/delete reference photos for the
 * household members and regulars added on the integration page. The AI
 * compares these photos against motion captures to recognise known people. */
class AICameraCentrePeopleCard extends HTMLElement {
  static getStubConfig() {
    return { title: "Known People" };
  }

  setConfig(config) {
    this._config = { title: "Known People", ...config };
    this._visitors = [];
    this._error = null;
    this._busy = false;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._loadedOnce) {
      this._loadedOnce = true;
      this._load();
    }
  }

  connectedCallback() {
    if (this._loadedOnce) this._load();
  }

  async _load() {
    if (!this._hass) return;
    try {
      const resp = await this._hass.callWS({ type: "ai_camera_centre/visitors" });
      this._visitors = resp.visitors || [];
      this._error = null;
    } catch (e) {
      this._error =
        "Could not load known people: " + (e.message || e.code || String(e));
    }
    this._render();
  }

  _esc(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  async _upload(visitorId, file) {
    if (!file || !this._hass) return;
    this._busy = true;
    this._error = null;
    this._render();
    try {
      const fd = new FormData();
      fd.append("visitor_id", visitorId);
      fd.append("file", file);
      const resp = await this._hass.fetchWithAuth(
        "/api/ai_camera_centre/known_photo",
        { method: "POST", body: fd }
      );
      if (!resp.ok) {
        throw new Error((await resp.text()) || "HTTP " + resp.status);
      }
      await this._load();
    } catch (e) {
      this._error = "Upload failed: " + (e.message || String(e));
    } finally {
      this._busy = false;
      this._render();
    }
  }

  async _delete(visitorId, filename) {
    if (!this._hass) return;
    try {
      await this._hass.callWS({
        type: "ai_camera_centre/delete_visitor_photo",
        visitor_id: visitorId,
        filename,
      });
      await this._load();
    } catch (e) {
      this._error = "Delete failed: " + (e.message || e.code || String(e));
      this._render();
    }
  }

  _person(v) {
    const photos = (v.photos || [])
      .map(
        (p) => `
        <div class="photo">
          <img src="${this._esc(p.url)}" loading="lazy"
               onerror="this.parentNode.style.display='none'">
          <button class="photo-del" title="Remove photo"
                  data-vid="${this._esc(v.visitor_id)}"
                  data-file="${this._esc(p.filename)}">&times;</button>
        </div>`
      )
      .join("");
    return `
      <div class="person">
        <div class="person-head">
          <span class="person-name">${this._esc(v.name || v.visitor_id)}</span>
          <label class="add-btn">
            + Add photo
            <input class="upload-input" type="file" accept="image/*"
                   data-vid="${this._esc(v.visitor_id)}" hidden>
          </label>
        </div>
        ${
          v.description
            ? `<div class="person-desc">${this._esc(v.description)}</div>`
            : ""
        }
        <div class="photos">${
          photos || `<div class="no-photos">No reference photos yet.</div>`
        }</div>
      </div>`;
  }

  _render() {
    const c = this._config;
    let body;
    if (this._error) {
      body = `<div class="empty">${this._esc(this._error)}</div>`;
    } else if (!this._visitors.length) {
      body = `<div class="empty">No known people yet. Add household members and
        regulars from Settings &rarr; Devices &amp; Services &rarr; AI Camera
        Centre &rarr; Add known visitor, then upload their photos here.</div>`;
    } else {
      body = this._visitors.map((v) => this._person(v)).join("");
    }

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { padding: 12px 0 8px; }
        .header {
          display: flex; align-items: center; justify-content: space-between;
          padding: 0 16px 8px;
        }
        .title { font-size: 16px; font-weight: 500; color: var(--primary-text-color); }
        .refresh {
          background: none; border: none; cursor: pointer; padding: 4px;
          color: var(--secondary-text-color); font-size: 16px; line-height: 1;
        }
        .person { padding: 10px 16px; border-top: 1px solid var(--divider-color); }
        .person-head {
          display: flex; align-items: center; justify-content: space-between;
          gap: 8px;
        }
        .person-name { font-size: 14px; font-weight: 600; color: var(--primary-text-color); }
        .person-desc {
          font-size: 12px; color: var(--secondary-text-color);
          margin: 2px 0 6px;
        }
        .add-btn {
          border: 1px solid var(--primary-color); color: var(--primary-color);
          border-radius: 14px; padding: 3px 12px; font-size: 12px;
          cursor: pointer; white-space: nowrap;
        }
        .add-btn:hover { background: var(--secondary-background-color); }
        .photos { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
        .photo { position: relative; width: 84px; height: 84px; }
        .photo img {
          width: 100%; height: 100%; object-fit: cover; border-radius: 8px;
          background: var(--divider-color);
        }
        .photo-del {
          position: absolute; top: -6px; right: -6px;
          width: 20px; height: 20px; border-radius: 50%;
          border: none; background: #ef4444; color: #fff;
          font-size: 14px; line-height: 1; cursor: pointer;
          display: flex; align-items: center; justify-content: center;
        }
        .no-photos { font-size: 12px; color: var(--secondary-text-color); }
        .empty {
          padding: 20px 16px; text-align: center; font-size: 13px;
          line-height: 1.5; color: var(--secondary-text-color);
        }
        .busy { padding: 6px 16px; font-size: 12px; color: var(--secondary-text-color); }
      </style>
      <ha-card>
        <div class="header">
          <span class="title">${this._esc(c.title)}</span>
          <button class="refresh" title="Refresh">&#x21bb;</button>
        </div>
        ${this._busy ? `<div class="busy">Uploading&hellip;</div>` : ""}
        ${body}
      </ha-card>
    `;

    this.shadowRoot
      .querySelector(".refresh")
      .addEventListener("click", () => this._load());
    this.shadowRoot.querySelectorAll(".upload-input").forEach((el) =>
      el.addEventListener("change", (ev) => {
        const file = ev.target.files && ev.target.files[0];
        if (file) this._upload(el.dataset.vid, file);
        ev.target.value = "";
      })
    );
    this.shadowRoot.querySelectorAll(".photo-del").forEach((el) =>
      el.addEventListener("click", () =>
        this._delete(el.dataset.vid, el.dataset.file)
      )
    );
  }

  getCardSize() {
    return 4;
  }
}

customElements.define("ai-camera-centre-people-card", AICameraCentrePeopleCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "ai-camera-centre-card",
  name: "AI Camera Centre Card",
  description: "Rolling multi-camera AI alert timeline (ai_camera_centre integration)",
});
window.customCards.push({
  type: "ai-camera-centre-people-card",
  name: "AI Camera Centre People",
  description:
    "Upload and manage reference photos of known people (ai_camera_centre integration)",
});
