import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
NOW = 1800000000000


def event():
    return copy.deepcopy({'event': 'snapshot', 'realm_id': 2, 'observed_at_ms': NOW, 'fresh_session': True, 'carriers': [
        {'carrierName': 'SC-Example', 'spawnTime': NOW - 3600000, 'carrierType': 'regular',
         'starSystem': 'mizar.name', 'blueprintCategory': None, 'planet': None,
         'HPStatus': None, 'timer_remaining': 600000, 'timer_hidden': False}]})
