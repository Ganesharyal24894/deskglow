"""Controller presets — generated — do not edit.

Source: presets/controllers/*.json. Regenerate with `python scripts/gen_presets.py`.
Frames are tuples of byte values and placeholder names (see each preset's ranges).
"""

PRESETS = {
    'elk-bledom': {
        'id': 'elk-bledom',
        'name': 'ELK-BLEDOM / MELK family',
        'service_uuids': ('0000fff0-0000-1000-8000-00805f9b34fb',),
        'name_hints': ('MELK', 'ELK', 'LEDBLE', 'LED-BLE', 'LEDBle', 'BLEDOM', 'LED', 'SP', 'KS', 'iDeal', 'Triones', 'QHM'),
        'write_uuid': '0000fff3-0000-1000-8000-00805f9b34fb',
        'notify_uuid': '0000fff4-0000-1000-8000-00805f9b34fb',
        'ranges': {'r': (0, 255), 'g': (0, 255), 'b': (0, 255), 'brightness': (0, 100), 'speed': (0, 100), 'effect': (0, 255)},
        'frames': {'power_on': (126, 0, 4, 240, 0, 1, 255, 0, 239), 'power_off': (126, 0, 4, 0, 0, 0, 255, 0, 239), 'color': (126, 0, 5, 3, 'r', 'g', 'b', 0, 239), 'brightness': (126, 0, 1, 'brightness', 0, 0, 0, 0, 239), 'effect': (126, 0, 3, 'effect', 3, 0, 0, 0, 239), 'speed': (126, 0, 2, 'speed', 0, 0, 0, 0, 239), 'status_query': (126, 0, 0, 0, 0, 0, 0, 0, 239)},
        'default_effect': 'fade-colors',
        'effects': {'jump-rgb': 135, 'jump-colors': 136, 'fade-rgb': 137, 'fade-colors': 138, 'fade-red': 139, 'fade-green': 140, 'fade-blue': 141, 'fade-yellow': 142, 'fade-cyan': 143, 'fade-magenta': 144, 'fade-white': 145, 'fade-red-green': 146, 'fade-red-blue': 147, 'fade-green-blue': 148, 'blink-colors': 149, 'blink-red': 150, 'blink-green': 151, 'blink-blue': 152, 'blink-yellow': 153, 'blink-cyan': 154, 'blink-magenta': 155, 'blink-white': 156},
    },
}
