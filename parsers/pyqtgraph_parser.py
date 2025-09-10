import pandas as pd
from pathlib import Path
from typing import Optional, Callable
from .base_parser import OscilloscopeCSVParser

class PyqtgraphCSVParser(OscilloscopeCSVParser):
    """
    Parser for CSV files exported by PyQtGraph's Export/CSV tool.

    Typical structure:
        x0000,y0000
        0.000000, 0.123456
        0.000002, 0.234567
        ...

    This parser treats the first column as time (seconds) and the second as value (voltage or arbitrary units).
    Units are not embedded in the file, so the viewer will fall back to defaults unless set elsewhere.
    """

    def can_parse(self, first_lines):
        if not first_lines:
            return False
        # Look at the very first non-empty line
        header = None
        for line in first_lines:
            line = (line or '').strip()
            if line:
                header = line
                break
        if not header:
            return False
        parts = [p.strip().lower() for p in header.split(',')]
        if len(parts) < 2:
            return False
        # Common pyqtgraph pattern: headers like x, y OR x####, y####
        starts_with_xy = parts[0].startswith('x') and parts[1].startswith('y')
        if starts_with_xy:
            return True
        # As a fallback, if the first two non-header lines appear to be numeric pairs, accept
        # but only if no other known headers (like 'second', 'time(') are present
        known_time_markers = ('second', 'time(')
        if any(k in parts[0] for k in known_time_markers):
            return False
        # Try to parse a couple of subsequent lines as numbers
        numeric_pair_count = 0
        for line in first_lines[1:]:
            line = (line or '').strip()
            if not line:
                continue
            vals = [v.strip() for v in line.split(',')[:2]]
            try:
                float(vals[0].replace(' ', ''))
                float(vals[1].replace(' ', ''))
                numeric_pair_count += 1
                if numeric_pair_count >= 2:
                    return True
            except Exception:
                break
        return False

    def parse(self, file_path, progress_callback: Optional[Callable[[int, int, str], None]] = None):
        metadata = {
            'format': 'PyQtGraph Export'
        }

        if progress_callback:
            progress_callback(0, 100, 'Analyzing file...')

        # Detect whether the first line is a header with x/y labels
        with open(file_path, 'r') as f:
            first_line = (f.readline() or '').strip()
        parts = [p.strip().lower() for p in first_line.split(',')]
        has_xy_header = len(parts) >= 2 and parts[0].startswith('x') and parts[1].startswith('y')

        # Estimate rows for progress reporting
        try:
            file_size = Path(file_path).stat().st_size
            sample_size = 2000
            total_length = 0
            lines_read = 0
            with open(file_path, 'r') as f:
                # Skip header if present
                if has_xy_header:
                    next(f)
                for _ in range(sample_size):
                    try:
                        line = next(f)
                        total_length += len(line.encode('utf-8'))
                        lines_read += 1
                    except StopIteration:
                        break
            if lines_read > 0 and total_length > 0:
                avg_line_len = total_length / lines_read
                estimated_total_rows = max(1, int((file_size - (len(first_line) + 2)) / max(avg_line_len, 1)))
            else:
                estimated_total_rows = 1
        except Exception:
            estimated_total_rows = 1

        if progress_callback:
            progress_callback(5, 100, 'Reading data...')

        chunks = []
        chunk_size = 100_000
        rows_processed = 0

        if has_xy_header:
            # Read with header, keep only first two columns
            for chunk in pd.read_csv(
                file_path,
                usecols=[0, 1],
                chunksize=chunk_size,
            ):
                # Normalize to standard columns
                x = pd.to_numeric(chunk.iloc[:, 0], errors='coerce')
                y = pd.to_numeric(chunk.iloc[:, 1], errors='coerce')
                norm = pd.DataFrame({'Second': x, 'Value': y})
                norm = norm.dropna(subset=['Second', 'Value'])
                chunks.append(norm)
                rows_processed += len(norm)
                if progress_callback:
                    prog = min(95, int(10 + 80 * (rows_processed / max(estimated_total_rows, 1))))
                    progress_callback(prog, 100, f'Reading data... (approximately {rows_processed:,} points)')
        else:
            # No header: treat first two columns as data
            for chunk in pd.read_csv(
                file_path,
                header=None,
                names=['Second', 'Value'],
                usecols=[0, 1],
                chunksize=chunk_size,
            ):
                chunk['Second'] = pd.to_numeric(chunk['Second'], errors='coerce')
                chunk['Value'] = pd.to_numeric(chunk['Value'], errors='coerce')
                norm = chunk.dropna(subset=['Second', 'Value'])
                chunks.append(norm)
                rows_processed += len(norm)
                if progress_callback:
                    prog = min(95, int(10 + 80 * (rows_processed / max(estimated_total_rows, 1))))
                    progress_callback(prog, 100, f'Reading data... (approximately {rows_processed:,} points)')

        if not chunks:
            raise ValueError('No data rows found in PyQtGraph CSV file')

        if progress_callback:
            progress_callback(97, 100, 'Combining data...')

        data = pd.concat(chunks, ignore_index=True)

        if progress_callback:
            progress_callback(100, 100, f'Done! Total points: {len(data):,}')

        return metadata, data
