import pandas as pd
from .base_parser import OscilloscopeCSVParser

class SiglentCSVParser(OscilloscopeCSVParser):
    def can_parse(self, first_lines):
        # Siglent files start with "Record Length" and contain model info
        return (any('Record Length' in line for line in first_lines) and
                any('Model Number' in line for line in first_lines))
        
    def parse(self, file_path):
        metadata = {}
        metadata_lines = []
        
        # Read metadata
        with open(file_path, 'r') as f:
            for i, line in enumerate(f):
                if 'Second,Value' in line:
                    break
                metadata_lines.append(line)
                
        # Parse metadata
        for line in metadata_lines:
            if ',' in line:
                key, *values = line.strip().split(',')
                metadata[key] = values
        
        # Read data
        data = pd.read_csv(file_path, skiprows=len(metadata_lines),
                          dtype={'Second': float, 'Value': float})
        
        return metadata, data
