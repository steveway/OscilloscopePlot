import pandas as pd
import numpy as np
from pathlib import Path
from .base_parser import OscilloscopeCSVParser

class RigolArbCSVParser(OscilloscopeCSVParser):
    def can_parse(self, first_lines):
        # Rigol Arb files start with this specific header
        return any('RIGOL:CSV DATA FILE' in line for line in first_lines)
        
    def parse(self, file_path, progress_callback=None):
        metadata = {}
        file_size = Path(file_path).stat().st_size
        
        if progress_callback:
            progress_callback(0, 100, "Reading metadata...")
        
        # Read and parse metadata
        data_lines = []
        with open(file_path, 'r') as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:  # Skip empty lines
                    continue
                    
                if ':' in line and i < 10:  # Only parse metadata in first few lines
                    key, value = line.split(':', 1)
                    metadata[key] = value
                elif line[0].isdigit():  # Found start of data
                    data_lines.append(line)  # Keep this data line
                    break
        
        if progress_callback:
            progress_callback(10, 100, "Reading data values...")
            
        # Get sample rate from metadata
        sample_rate = float(metadata.get('Sample Rate', '1'))  # Default to 1 if not found
        number_of_data_points = int(metadata.get('DATA Number', '1'))
        current_data_point_position = 0
        
        # Read the voltage values in chunks
        voltage_values = []
        chunk_size = 100000
        current_chunk = []
        
        # Process the first data line we found
        if data_lines:
            try:
                current_chunk.append(float(data_lines[0]))
            except ValueError:
                pass
        
        # Continue reading the rest of the file
        with open(file_path, 'r') as f:
            # Skip to where we found the first data line
            for _ in range(len(metadata) + 1):  # +1 for the first data line we already processed
                f.readline()
                
            for line in f:
                line = line.strip()
                if line and line[0].isdigit():
                    try:
                        current_chunk.append(float(line))
                        if len(current_chunk) >= chunk_size:
                            voltage_values.extend(current_chunk)
                            current_data_point_position += len(current_chunk)
                            current_chunk = []
                            if progress_callback:
                                progress = min(90, int(10 + 80 * (current_data_point_position / number_of_data_points)))
                                progress_callback(progress, 100, 
                                               f"Reading values... ({len(voltage_values):,} points)")
                    except ValueError:
                        continue
                        
        # Add any remaining values
        if current_chunk:
            voltage_values.extend(current_chunk)
            current_data_point_position += len(current_chunk)
            
        if progress_callback:
            progress_callback(90, 100, "Creating DataFrame...")
            
        # Create time values based on sample rate
        time_values = np.arange(len(voltage_values)) / sample_rate
        
        # Create DataFrame with our standard column names
        data = pd.DataFrame({
            'Second': time_values,
            'Value': voltage_values
        })
        
        if progress_callback:
            progress_callback(100, 100, "Done!")
        
        return metadata, data
