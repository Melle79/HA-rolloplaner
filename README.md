# Roller Shutter Planner · Rolloplaner

A Home Assistant add-on for roller shutters: one schedule per cover, by clock
time or by the position of the sun — with its own Lovelace card.

[![Add repository to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FMelle79%2FHA-rolloplaner)

> 📖 Full manual: **[DOCS.md](rolloplaner/DOCS.md)** (German) ·
> 🇩🇪 Auf Deutsch: **[README.de.md](README.de.md)**

Instead of three automations per cover there is one switching point: “close at
sunset, no later than 20:30, on school days”. The planner recalculates on
every cycle, moves only when a point is **newly due** — and writes down why.

![Today: every cover with position, reason and next change](rolloplaner/doku/bilder/en/uebersicht.png)

The interface has four areas: **Today**, **Daily schedule**, **Programs**
and **Settings**. Every cover has its own page; switches and conditions sit
where they take effect.

## Installation

Add this address as an add-on repository in Home Assistant
(*Settings → Add-ons → Add-on Store → ⋮ → Repositories*):

```
https://github.com/Melle79/HA-rolloplaner
```

**Roller Shutter Planner** then appears in the store. The add-on brings its own
Lovelace card; there is no separate HACS installation.

## What the planner does

**One schedule per cover**, switching by clock time **or** by the position of
the sun. It can take days off, public holidays and “tomorrow is a day off”
into account, and a switching point may depend on a condition — on a switch
the planner creates itself.

![The daily schedule: one bar per cover, midnight to midnight](rolloplaner/doku/bilder/en/tagesablauf.png)

Tapping a bar opens its schedule as sentences:

![A shared schedule: open at 06:30 on school days, closed at sunset](rolloplaner/doku/bilder/en/zeitplan.png)

The unit of control is **the cover**, not the room — in any house where a room
has a window *and* a balcony door there is no other way. Above it sit
**groups** (floors, for instance) for everything that belongs together: they
can carry a shared schedule that adds to the individual ones, and a release
switch for the whole set.

![Floors: assign and order covers, switch each floor on and off](rolloplaner/doku/bilder/en/gruppen.png)

![Switches: what each one applies to, with renaming](rolloplaner/doku/bilder/en/schalter.png)

On top of that:

* **Heat shield** by sun direction — closes part way when the sun stands in
  *this* window and it is warm outside. Switchable per cover.
* **Window lock** — nothing closes while a contact is open. On a balcony door
  that is the difference between “closed” and “locked out”.
* **Holiday**: keep everything closed, or simulate presence with jitter.
* **Watchdog** that reports a motor that stopped responding or is stuck.
* **Dry run**: calculates and logs but moves nothing — to run alongside the
  automations you already have.

## Christmas time

From the first Sunday of Advent to Epiphany the lights are on in the evening.
The *Christmas time* program switches any lights and sockets on at sunset (or
dusk, or a set time) and off at 22:30. The covers in front stay open or at an
intermediate position until then and close with the lights; the same in the
morning before opening. Every year by itself, and switchable by hand at any
time.

![The Christmas time program with lights and a position per cover](rolloplaner/doku/bilder/en/weihnachtszeit.png)

The add-on reads existing shutter automations and proposes what it would make
of them. **Nothing is taken over on its own.**

## Escape route on a smoke alarm

When a smoke detector triggers, the planner opens **every** cover — overriding
automation, schedule and manual operation — and sends a message to the phone
saying which covers are open and which were **not reachable**. The message
names the detector's room, not just its name. After that it runs no switching
point that would close the way out again.

![The smoke alarm tab: lock, escape route release, detectors and notification path](rolloplaner/doku/bilder/en/rauchalarm.png)

The smoke alarm has a **tab of its own**. It is too important to sit inside the
settings.

## The card

`custom:rolloplaner-card` — one tile per cover, with a **simulated shutter**
instead of a bar: a bar says “65 %”, but not whether the shutter is up or
down. In front of a door it looks different than in front of a window.

![The card with every cover, ordered by floor](rolloplaner/doku/bilder/en/karte.png)

Operated straight from the tile: **open · stop · close** (the stop in the
middle, the way it sits on every handset), a **slider** for everything in
between, automation, heat shield — and the release switches the switching
points hang on. Stop and slider only appear where the motor supports them: a
button that does nothing is worse than no button. At the end of travel, the
button leading there is greyed out.

**Or slim**, one line per cover: picture, name, position and the same buttons,
without the reason and the schedule. Together with the cut by room this makes
a small card per room — there you want to switch, not to read why the planner
did something two hours ago.

![A slim card for one room: one line per cover](rolloplaner/doku/bilder/en/karte-zimmer.png)

Everything is set in the **card editor**, without YAML: text size (meant for a
wall tablet), what the card shows, which rooms and groups appear in which
order — and the label of each cover, because where the room is already in the
heading, “window left” is enough.

## Bilingual

Planner, setup, card and card editor speak **German and English**. The add-on
and its setup follow Home Assistant or the setting under *Settings →
Language*; the card follows the **viewer** — the wall tablet shows German while
an English-speaking guest sees the same card in English. A third language is
one more table, no `gettext` and no build step.

## In detail

[rolloplaner/DOCS.md](rolloplaner/DOCS.md) — the manual. It explains not only
what the buttons do but why the decisions fell the way they did: why it
switches on the edge and not on the level, why the planner computes the sun
times itself, and what “off” means in each case. *Currently German only.*

[rolloplaner/CHANGELOG.md](rolloplaner/CHANGELOG.md) — what has changed.

## Licence

MIT
