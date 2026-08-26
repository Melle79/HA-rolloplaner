"""Liefert die Lovelace-Karte mit dem Add-on aus.

Die Karte wird beim Start nach `www/` der Home-Assistant-Konfiguration kopiert
und als Lovelace-Ressource registriert. Damit ist keine getrennte Installation
über HACS mehr nötig, und Karte und Add-on sind immer versionsgleich.

Bewusst defensiv: Ist die Karte bereits aus einer anderen Quelle registriert
(typischerweise HACS unter `/hacsfiles/…`), wird **nichts** angelegt. Zwei
Registrierungen desselben Custom Elements führen zu
`customElements.define(): already defined` und können das Dashboard lahmlegen.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil

_LOGGER = logging.getLogger(__name__)

CARD_FILE = "rolloplaner-card.js"
CARD_SOURCE = os.environ.get("CARD_SOURCE", "/app/card/" + CARD_FILE)

# Je nach map-Eintrag liegt die HA-Konfiguration an einer dieser Stellen
CONFIG_DIRS = ("/homeassistant", "/config")

WS_URL = "ws://supervisor/core/websocket"
TIMEOUT = 15


def _config_dir() -> str | None:
    """Verzeichnis der Home-Assistant-Konfiguration, sofern beschreibbar."""
    for d in CONFIG_DIRS:
        if os.path.isdir(d) and os.access(d, os.W_OK):
            return d
    return None


def _digest(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:8]


def _copy_card(config_dir: str) -> tuple[str, bool]:
    """Karte nach www/ kopieren. Liefert (Kennung, kopiert?)."""
    www = os.path.join(config_dir, "www")
    os.makedirs(www, exist_ok=True)
    target = os.path.join(www, CARD_FILE)
    digest = _digest(CARD_SOURCE)
    if os.path.exists(target) and _digest(target) == digest:
        return digest, False
    shutil.copyfile(CARD_SOURCE, target)
    return digest, True


# ---------------------------------------------------------------- Lovelace

def _ws_call(sock, payload: dict, msg_id: int) -> dict:
    sock.send(json.dumps({**payload, "id": msg_id}))
    while True:
        msg = json.loads(sock.recv())
        if msg.get("id") == msg_id:
            return msg


def _register(url: str) -> None:
    """Ressource anlegen oder ihre URL aktualisieren."""
    import websocket  # nur hier importiert, damit ein Fehlen den Start nicht bricht

    token = os.environ.get("SUPERVISOR_TOKEN", "")
    if not token:
        _LOGGER.warning("Karte: SUPERVISOR_TOKEN fehlt – Ressource nicht registrierbar")
        return

    sock = websocket.create_connection(WS_URL, timeout=TIMEOUT)
    try:
        json.loads(sock.recv())  # auth_required
        sock.send(json.dumps({"type": "auth", "access_token": token}))
        if json.loads(sock.recv()).get("type") != "auth_ok":
            _LOGGER.warning("Karte: Anmeldung an der Home-Assistant-API fehlgeschlagen")
            return

        listed = _ws_call(sock, {"type": "lovelace/resources"}, 1)
        items = listed.get("result") or []
        eigene = [r for r in items if CARD_FILE in r.get("url", "") and "/local/" in r.get("url", "")]
        fremde = [r for r in items if CARD_FILE in r.get("url", "") and "/local/" not in r.get("url", "")]

        if fremde and not eigene:
            _LOGGER.warning(
                "Karte: bereits aus anderer Quelle eingebunden (%s) – das Add-on legt "
                "keine zweite Ressource an. Entferne die alte Einbindung (z. B. in HACS), "
                "dann übernimmt das Add-on beim nächsten Start.",
                ", ".join(r["url"] for r in fremde),
            )
            return

        if eigene:
            aktuell = eigene[0]
            if aktuell.get("url") == url:
                _LOGGER.info("Karte: Ressource bereits aktuell (%s)", url)
                return
            res = _ws_call(sock, {"type": "lovelace/resources/update",
                                  "resource_id": aktuell["id"],
                                  "url": url, "res_type": "module"}, 2)
            _LOGGER.info("Karte: Ressource aktualisiert → %s", url) if res.get("success") \
                else _LOGGER.warning("Karte: Aktualisieren fehlgeschlagen: %s", res.get("error"))
            return

        res = _ws_call(sock, {"type": "lovelace/resources/create",
                              "url": url, "res_type": "module"}, 3)
        if res.get("success"):
            _LOGGER.info("Karte: als Lovelace-Ressource registriert (%s)", url)
        else:
            _LOGGER.warning("Karte: Registrieren fehlgeschlagen: %s", res.get("error"))
    finally:
        sock.close()


def sync() -> None:
    """Karte bereitstellen und registrieren. Fehler bleiben folgenlos."""
    try:
        if not os.path.exists(CARD_SOURCE):
            _LOGGER.warning("Karte: Quelldatei %s fehlt", CARD_SOURCE)
            return
        config_dir = _config_dir()
        if config_dir is None:
            _LOGGER.info(
                "Karte: kein Schreibzugriff auf die Home-Assistant-Konfiguration – "
                "die Karte wird nicht mitgeliefert (map: homeassistant_config:rw fehlt)"
            )
            return

        digest, kopiert = _copy_card(config_dir)
        if kopiert:
            _LOGGER.info("Karte nach %s/www/%s kopiert", config_dir, CARD_FILE)
        _register(f"/local/{CARD_FILE}?v={digest}")
    except Exception as err:  # noqa: BLE001 – darf den Add-on-Start nie verhindern
        _LOGGER.warning("Karte konnte nicht bereitgestellt werden: %s", err)
