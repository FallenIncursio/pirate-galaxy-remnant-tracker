from __future__ import annotations

import re
from datetime import UTC, datetime

from .model import Snapshot

LABELS = {
    'vega.name': 'Vega', 'antares.name': 'Antares', 'gemini.name': 'Gemini', 'mizar.name': 'Mizar',
    'sol.name': 'Sol', 'draconis.name': 'Draconis', 'sirius.name': 'Sirius',
    '$taucetimantis.name': 'Tau Ceti / Oort', 'tauceti.name': 'Tau Ceti',
    'vega1planet': 'Axiom', 'vega2planet': 'Kalabesh', 'vega3planet': 'Colossus',
    'vega3moon1planet': 'Lyris', 'vega4planet': 'Aurora', 'vega4moon1planet': 'Phobos',
    'vega5planet': 'Dante', 'vegajunkyardplanet': 'Asteroiden Schrottplatz',
    'antares1planet': 'Antares 1', 'antares2planet': 'Remo', 'antares5planet': 'Goya',
    'antares3planet': 'Lustra', 'antares4planet': 'Terasa',
    'sol1planet': 'Mars',
    'sol2planet': 'Merkur', 'sol3planet': 'Erde', 'sol3moon1planet': 'Mond',
    'sol4planet': 'Venus', 'sol5planet': 'Jupiter', 'sol6planet': 'Saturn',
    'sol7planet': 'Neptun', 'sol8planet': 'Uranus',
    'mizar1planet': 'Baumar', 'mizar3planet': 'Ob', 'mizar4planet': 'Cosmo',
    'mizar2planet': 'Molikar', 'draconis2planet': 'Mantis Hive',
    'draconis1planet': 'Gazica', 'draconis3planet': 'Valkion', 'draconis4planet': 'Arkon',
    'gemini1planet': 'Desai', 'gemini2planet': 'Iga',
    'gemini3planet': 'Prosperous', 'gemini4planet': 'Commerce Central', 'gemini5planet': 'Technatoria',
    'mantis1planet': 'Erebos', 'sol3invadedplanet': 'Erde (in Aufruhr)',
    'tauceti1planet': 'Vénar', 'tauceti2planet': 'Calon',
    '$item.category.activeitem.tank': 'Item der Tank-Klasse',
    '$item.category.activeitem.storm': 'Item der Storm-Klasse',
    '$item.category.activeitem.hijacker': 'Item der Räuber-Klasse',
    '$item.category.activeitem.defender': 'Item der Verteidiger-Klasse',
    '$item.category.activeitem.medic': 'Item der Engineer-Klasse',
    '$item.category.activeitem.energizer': 'Item der Enervator-Klasse',
    '$item.category.activeitem.shock': 'Item der Shock-Klasse',
    '$item.category.activeitem.sniper': 'Item der Sniper-Klasse',
    '$item.category.shipupgrade.alloy': 'Legierungs-Upgrade',
    '$item.category.shipupgrade.itemslot': 'Komponenten-Slot-Upgrade',
}


def safe(value: str, limit: int = 120) -> str:
    value = value[:limit].replace('@', '@\u200b')
    return re.sub(r'([\\`*_~|<>])', r'\\\1', value)


def label(value: str | None) -> str:
    return safe(LABELS.get(value, value) if value else 'unbekannt', 100)


def payload(snapshot: Snapshot | None, *, server: str, username: str, poll_seconds: int,
            now_ms: int, delta: list[str] = (), problem: str | None = None) -> dict:
    count = len(snapshot.carriers) if snapshot else 0
    status = f'🟠 {safe(problem, 180)}' if problem else '🟢 Verbunden'
    description = f'{status} · **{count} Träger** · Aktualisierung alle {poll_seconds // 60} Minuten'
    if snapshot:
        description += f'\nDatenstand: <t:{snapshot.observed_ms // 1000}:F> · <t:{snapshot.observed_ms // 1000}:R>'
    else:
        description += '\nNoch kein bestätigter Datenstand.'
    filename = f'remnants-{now_ms}.png'
    alternative = f'Remnant-Träger auf {server}. ' + (problem + '. ' if problem else '')
    for carrier in (snapshot.carriers if snapshot else ()):
        health = 'unbekannt' if carrier.hp is None else f'{carrier.hp} Prozent'
        alternative += (f'{carrier.name}: {LABELS.get(carrier.system, carrier.system) or "System unbekannt"}, '
                        f'{LABELS.get(carrier.planet, carrier.planet) or "Planet unbekannt"}, '
                        f'{LABELS.get(carrier.category, carrier.category) or "Beute unbekannt"}, HP {health}. ')
    if delta and not problem:
        meaningful = [line for line in delta if line not in ('Keine Änderungen seit dem letzten Abruf', 'Erster erfasster Stand')]
        if meaningful:
            description += '\n' + safe(' · '.join(meaningful), 350)
    return {'username': username[:80], 'allowed_mentions': {'parse': []},
            'attachments': [{'id': 0, 'filename': filename, 'description': alternative[:1024]}],
            'embeds': [{'title': f'Remnant-Träger · {safe(server, 80)}', 'description': description,
                        'color': 0xE69A35 if problem else 0xE9C653, 'fields': [],
                        'image': {'url': 'attachment://' + filename},
                        'timestamp': datetime.fromtimestamp(now_ms / 1000, UTC).isoformat()}]}
