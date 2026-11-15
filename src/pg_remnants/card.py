from __future__ import annotations

import re
from datetime import UTC, datetime

from .model import Snapshot

LABELS = {
    'vega.name': 'Vega', 'antares.name': 'Antares', 'gemini.name': 'Gemini', 'mizar.name': 'Mizar',
    'sol.name': 'Sol', 'draconis.name': 'Draconis', 'sirius.name': 'Sirius',
    '$taucetimantis.name': 'Tau Ceti / Oort', 'tauceti.name': 'Tau Ceti',
    'mizar2planet': 'Molikar', 'draconis2planet': 'Mantis Hive',
    'mantis1planet': 'Erebos', 'sol3invadedplanet': 'Erde (in Aufruhr)',
    '$item.category.activeitem.tank': 'Item der Tank-Klasse',
    '$item.category.activeitem.storm': 'Item der Storm-Klasse',
    '$item.category.activeitem.hijacker': 'Item der Räuber-Klasse',
    '$item.category.activeitem.defender': 'Item der Verteidiger-Klasse',
    '$item.category.activeitem.shock': 'Item der Shock-Klasse',
    '$item.category.activeitem.sniper': 'Item der Sniper-Klasse',
    '$item.category.shipupgrade.alloy': 'Legierungs-Upgrade',
}


def safe(value: str, limit: int = 120) -> str:
    value = value[:limit].replace('@', '@\u200b')
    return re.sub(r'([\\`*_~|<>])', r'\\\1', value)


def label(value: str | None) -> str:
    return safe(LABELS.get(value, value) if value else 'unbekannt', 100)


def payload(snapshot: Snapshot | None, *, server: str, username: str, poll_seconds: int,
            now_ms: int, delta: list[str] = (), problem: str | None = None) -> dict:
    stale = problem is not None
    count = len(snapshot.carriers) if snapshot else 0
    status = f'🟠 {problem}' if stale else '🟢 Verbunden'
    description = f'{status} · **{count} Träger** · Aktualisierung alle {poll_seconds // 60} Minuten'
    if snapshot:
        description += f'\nDatenstand: <t:{snapshot.observed_ms // 1000}:F> · <t:{snapshot.observed_ms // 1000}:R>'
    else:
        description += '\nNoch kein bestätigter Datenstand.'
    fields = []
    for carrier in (snapshot.carriers[:15] if snapshot else ()):
        health = 'unbekannt' if carrier.hp is None else f'{carrier.hp} %'
        departure = 'unbekannt' if carrier.departure_ms is None else f'<t:{carrier.departure_ms // 1000}:R>'
        if stale and carrier.departure_ms is not None:
            departure = f'<t:{carrier.departure_ms // 1000}:t> (letzter Stand)'
        value = (f'**{label(carrier.system)}** · {label(carrier.planet)}\n'
                 f'{label(carrier.category)}\nHP: **{health}** · Abflug: {departure}\n'
                 f'Gemeldeter Spawn: <t:{carrier.spawn_ms // 1000}:f>')
        fields.append({'name': ('🟣 ' if carrier.kind == 'boss' else '🟡 ') + safe(carrier.name),
                       'value': value[:600], 'inline': False})
    if count > 15:
        description += f'\nAnzeige: 15 von {count}; vollständiger Stand im lokalen Verlauf.'
    if delta and not stale:
        fields.append({'name': 'Seit dem letzten Abruf', 'value': '\n'.join(safe(s, 150) for s in delta)[:900], 'inline': False})
    # Discord caps the aggregate embed text at 6000 characters.
    while sum(len(f['name']) + len(f['value']) for f in fields) + len(description) > 5600:
        fields.pop()
        if 'Gekürzte' not in description:
            description += '\nGekürzte Anzeige; vollständiger Stand im lokalen Verlauf.'
    return {'username': username[:80], 'allowed_mentions': {'parse': []},
            'embeds': [{'title': f'Remnant-Träger · {safe(server, 80)}', 'description': description,
                        'color': 0xE69A35 if stale else 0x3AC7A4, 'fields': fields,
                        'timestamp': datetime.fromtimestamp(now_ms / 1000, UTC).isoformat(),
                        'footer': {'text': 'Pirate Galaxy Remnant Tracker · Unbekannt bleibt unbekannt'}}]}
