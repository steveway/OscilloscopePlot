from .base_parser import OscilloscopeCSVParser
from .siglent_parser import SiglentCSVParser
from .batronix_parser import BatronixCSVParser
from .batronix_display_parser import BatronixDisplayCSVParser
from .rigol_parser import RigolCSVParser
from .rigol_arb_parser import RigolArbCSVParser

# List of all available parsers
AVAILABLE_PARSERS = [
    SiglentCSVParser(),
    BatronixCSVParser(),
    BatronixDisplayCSVParser(),
    RigolCSVParser(),
    RigolArbCSVParser()
]
