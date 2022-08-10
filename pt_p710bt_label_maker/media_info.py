from typing import Dict

#: Mapping of tape width (mm) to pixels; value of 4 denotes 3.5mm tape
TAPE_MM_TO_PX: Dict[int, int] = {
    24: 128,
    18: 112,
    12: 70,
    9: 50,
    6: 32,
    4: 24  # really 3.5mm
}

#: Mapping of tape with (mm) to left and right margin pixel counts
TAPE_MM_TO_MARGIN_PX: Dict[int, int] = {
    24: 0,
    18: 8,
    12: 29,
    9: 39,
    6: 48,
    4: 52
}
