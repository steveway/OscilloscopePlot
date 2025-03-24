import pandas as pd
from pathlib import Path
from .base_parser import OscilloscopeCSVParser

class BatronixCSVParser(OscilloscopeCSVParser):
    def can_parse(self, first_lines):
        # Batronix files start with this specific header
        return any('time difference to trigger in s' in line for line in first_lines)
        
    def parse(self, file_path, progress_callback=None):
        metadata = {}
        header_found = False
        header_line = 0
        
        if progress_callback:
            progress_callback(0, 100, "Reading file structure...")
        
        # First pass: find header and collect metadata
        with open(file_path, 'r') as f:
            for i, line in enumerate(f):
                if line.startswith('time in s'):
                    header_found = True
                    header_line = i + 1  # Skip past the header line itself
                    break
                    
                # Store non-empty lines as metadata
                line = line.strip()
                if line:
                    metadata[line] = []
                    
                if progress_callback and i % 1000 == 0:
                    progress_callback(5, 100, "Scanning header...")
                
        if not header_found:
            raise ValueError("Could not find data header in Batronix CSV file")
            
        # Store format info
        metadata['format'] = 'Batronix'
        
        if progress_callback:
            progress_callback(15, 100, "Reading data...")
            
        # Read data in chunks
        chunks = []
        chunk_size = 100000  # Adjust based on memory constraints
        
        # Second pass: read data starting after the header line
        try:
            # Estimate total rows using file size and average line length
            file_size = Path(file_path).stat().st_size
            
            # Read a small sample to estimate average line length
            sample_size = 1000
            total_length = 0
            lines_read = 0
            
            with open(file_path, 'r') as f:
                # Skip header
                for _ in range(header_line):
                    next(f)
                    
                # Read sample lines
                for _ in range(sample_size):
                    try:
                        line = next(f)
                        total_length += len(line.encode('utf-8'))  # Count bytes not characters
                        lines_read += 1
                    except StopIteration:
                        break
            
            if lines_read > 0:
                avg_line_length = total_length / lines_read
                estimated_total_rows = int((file_size - (header_line * avg_line_length)) / avg_line_length)
            else:
                estimated_total_rows = 1  # Fallback if file is very small
                
            rows_processed = 0
            
            for chunk in pd.read_csv(file_path, skiprows=header_line,
                                   names=['Second', 'Value'],  # Use our column names directly
                                   chunksize=chunk_size):
                chunks.append(chunk)
                rows_processed += len(chunk)
                if progress_callback:
                    progress = min(90, int(20 + 70 * (rows_processed / estimated_total_rows)))
                    progress_callback(progress, 100, 
                                   f"Reading data... (approximately {rows_processed:,} points)")
            
            if progress_callback:
                progress_callback(90, 100, "Combining data chunks...")
                
            # Combine all chunks
            data = pd.concat(chunks, ignore_index=True)
            
            if progress_callback:
                progress_callback(100, 100, f"Done! Total points: {len(data):,}")
            
            return metadata, data
            
        except Exception as e:
            raise ValueError(f"Error reading Batronix CSV data: {str(e)}")
