import pandas as pd
from pathlib import Path
from .base_parser import OscilloscopeCSVParser

class SiglentCSVParser(OscilloscopeCSVParser):
    def can_parse(self, first_lines):
        # Siglent files start with "Record Length" and contain model info
        return (any('Record Length' in line for line in first_lines) and
                any('Model Number' in line for line in first_lines))
        
    def parse(self, file_path, progress_callback=None):
        metadata = {}
        metadata_lines = []
        file_size = Path(file_path).stat().st_size
        
        if progress_callback:
            progress_callback(0, 100, "Reading metadata...")
        
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
        
        if progress_callback:
            progress_callback(10, 100, "Reading data...")
            
        # Read data in chunks to show progress
        chunks = []
        chunk_size = 100000  # Adjust based on memory constraints
        
        for chunk in pd.read_csv(file_path, skiprows=len(metadata_lines),
                               dtype={'Second': float, 'Value': float},
                               chunksize=chunk_size):
            chunks.append(chunk)
            if progress_callback:
                # Calculate progress based on number of chunks read
                current_size = sum(len(c) for c in chunks) * chunk.memory_usage(deep=True).sum()
                progress = min(90, int(10 + 80 * (current_size / file_size)))
                progress_callback(progress, 100, f"Reading data... ({len(chunks) * chunk_size:,} points)")
        
        if progress_callback:
            progress_callback(90, 100, "Combining data chunks...")
            
        # Combine all chunks
        data = pd.concat(chunks, ignore_index=True)
        
        if progress_callback:
            progress_callback(100, 100, "Done!")
        
        return metadata, data
