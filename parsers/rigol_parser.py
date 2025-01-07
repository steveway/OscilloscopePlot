import pandas as pd
from .base_parser import OscilloscopeCSVParser

class RigolCSVParser(OscilloscopeCSVParser):
    def can_parse(self, first_lines):
        # Rigol files have a simple header with Time(s),CH1V
        return any('Time(s),CH1V' in line for line in first_lines)
        
    def parse(self, file_path):
        metadata = {'format': 'Rigol'}  # Minimal metadata since Rigol files don't include it
        
        # Read data and rename columns to match our standard format
        data = pd.read_csv(file_path)
        data = data.rename(columns={'Time(s)': 'Second', 'CH1V': 'Value'})
        
        return metadata, data
