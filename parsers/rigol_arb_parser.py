import pandas as pd
import numpy as np
from .base_parser import OscilloscopeCSVParser

class RigolArbCSVParser(OscilloscopeCSVParser):
    def can_parse(self, first_lines):
        # Rigol Arb files start with this specific header
        return any('RIGOL:CSV DATA FILE' in line for line in first_lines)
        
    def parse(self, file_path):
        metadata = {}
        data_start = 0
        
        # Read and parse metadata
        with open(file_path, 'r') as f:
            lines = f.readlines()
            
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:  # Skip empty lines
                continue
                
            if ':' in line and i < 10:  # Only parse metadata in first few lines
                key, value = line.split(':', 1)
                metadata[key] = value
            elif line[0].isdigit():  # Found start of data
                data_start = i
                break
        
        # Get sample rate from metadata
        sample_rate = float(metadata.get('Sample Rate', '1'))  # Default to 1 if not found
        
        # Read the voltage values
        voltage_values = []
        for line in lines[data_start:]:
            line = line.strip()
            if line and line[0].isdigit():  # Only process lines that start with a number
                try:
                    voltage_values.append(float(line))
                except ValueError:
                    continue
        
        # Create time values based on sample rate
        time_values = np.arange(len(voltage_values)) / sample_rate
        
        # Create DataFrame with our standard column names
        data = pd.DataFrame({
            'Second': time_values,
            'Value': voltage_values
        })
        
        return metadata, data
