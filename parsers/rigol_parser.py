import pandas as pd
from pathlib import Path
from .base_parser import OscilloscopeCSVParser

class RigolCSVParser(OscilloscopeCSVParser):
    def can_parse(self, first_lines):
        # Rigol files have a simple header with Time(s),CH1V
        return any('Time(s),CH1V' in line for line in first_lines)
        
    def parse(self, file_path, progress_callback=None):
        metadata = {'format': 'Rigol'}  # Minimal metadata since Rigol files don't include it
        file_size = Path(file_path).stat().st_size
        
        if progress_callback:
            progress_callback(0, 100, "Reading data...")
            
        # Read data in chunks
        chunks = []
        chunk_size = 100000  # Adjust based on memory constraints
        
        for chunk in pd.read_csv(file_path, chunksize=chunk_size):
            chunks.append(chunk)
            if progress_callback:
                # Calculate progress based on number of chunks read
                current_size = sum(len(c) for c in chunks) * chunk.memory_usage(deep=True).sum()
                progress = min(90, int(80 * (current_size / file_size)))
                progress_callback(progress, 100, f"Reading data... ({len(chunks) * chunk_size:,} points)")
        
        if progress_callback:
            progress_callback(90, 100, "Processing data...")
            
        # Combine chunks and rename columns
        data = pd.concat(chunks, ignore_index=True)
        data = data.rename(columns={'Time(s)': 'Second', 'CH1V': 'Value'})
        
        if progress_callback:
            progress_callback(100, 100, "Done!")
        
        return metadata, data
