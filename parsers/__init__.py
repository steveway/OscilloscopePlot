from .base_parser import OscilloscopeCSVParser
from .siglent_parser import SiglentCSVParser
from .batronix_parser import BatronixCSVParser
from .batronix_display_parser import BatronixDisplayCSVParser
from .rigol_parser import RigolCSVParser
from .rigol_arb_parser import RigolArbCSVParser
from .pyqtgraph_parser import PyqtgraphCSVParser

# List of all available parsers
AVAILABLE_PARSERS = [
    SiglentCSVParser(),
    BatronixCSVParser(),
    BatronixDisplayCSVParser(),
    RigolCSVParser(),
    RigolArbCSVParser(),
    # Keep PyQtGraph last as a generic fallback for 2-column x,y CSVs
    PyqtgraphCSVParser(),
]
