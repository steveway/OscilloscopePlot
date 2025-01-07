import pandas as pd
from .base_parser import OscilloscopeCSVParser

class BatronixCSVParser(OscilloscopeCSVParser):
    def can_parse(self, first_lines):
        # Batronix files start with this specific header
        return any('time difference to trigger in s' in line for line in first_lines)
        
    def parse(self, file_path):
        metadata = {}
        header_found = False
        
        # Find the data header line
        with open(file_path, 'r') as f:
            lines = f.readlines()
            
        for i, line in enumerate(lines):
            if 'time in s,CH1 in V' in line:
                header_found = True
                header_line = i
                break
                
        if not header_found:
            raise ValueError("Could not find data header in Batronix CSV file")
            
        # Store metadata
        metadata['format'] = 'Batronix'
        for line in lines[:header_line]:
            line = line.strip()
            if line:
                metadata[line] = []
                
        # Read data starting from the header line
        data = pd.read_csv(file_path, skiprows=header_line)
        # Rename columns to match our standard format
        data = data.rename(columns={'time in s': 'Second', 'CH1 in V': 'Value'})
        
        return metadata, data
