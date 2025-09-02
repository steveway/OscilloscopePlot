import pandas as pd
from pathlib import Path
from typing import Optional, Callable
from .base_parser import OscilloscopeCSVParser
import re


class BatronixDisplayCSVParser(OscilloscopeCSVParser):
    """
    Parser for Batronix Display Data export files that contain min/max envelopes.

    Expected file structure (first lines):
        start time in s,time difference in s
        -6.000000E-004,8.000000E-007
        time in s,CH1 minimum in V,CH1 maximum in V
        <data rows...>

    Output dataframe columns:
        Second: time in seconds (from "time in s")
        Value:  average of (CH1 minimum in V, CH1 maximum in V)
    """

    def can_parse(self, first_lines):
        if not first_lines:
            return False
        lines = [(line or '').lower() for line in first_lines]
        has_header1 = any('start time in s' in line for line in lines)
        # Accept any CHx min/max pair in the header lines
        header_line = next((l for l in lines if 'time in s' in l and 'minimum' in l and 'maximum' in l), '')
        # Look for any channel references like ch1, ch2, etc.
        has_any_channel = bool(re.search(r'ch\d+\s+minimum', header_line)) and bool(re.search(r'ch\d+\s+maximum', header_line))
        return has_header1 and (has_any_channel or ('ch1 minimum' in header_line and 'ch1 maximum' in header_line))

    def parse(self, file_path, progress_callback: Optional[Callable[[int, int, str], None]] = None):
        metadata = {}

        # Read first two lines to capture start time and dt
        with open(file_path, 'r') as f:
            line1 = f.readline().strip()  # "start time in s,time difference in s"
            line2 = f.readline().strip()  # values

        # Try to parse start time and dt for metadata
        try:
            parts = [p.strip() for p in line2.split(',')]
            if len(parts) >= 2:
                start_time = float(parts[0])
                time_diff = float(parts[1])
                metadata['Start Time (s)'] = [start_time]
                metadata['Time Step (s)'] = [time_diff]
        except Exception:
            pass

        # Units metadata for viewer axes
        metadata['Horizontal Units'] = ['s']
        metadata['Vertical Units'] = ['V']
        metadata['format'] = 'Batronix Display Data'

        # Progress init
        if progress_callback:
            progress_callback(0, 100, 'Reading data...')

        chunks = []
        chunk_size = 100000

        # Estimate total rows to provide smoother progress
        try:
            file_size = Path(file_path).stat().st_size
            # Estimate average data line length by sampling after the 3 header lines
            sample_size = 1000
            total_length = 0
            lines_read = 0
            with open(file_path, 'r') as f:
                # Skip first 3 lines (2 metadata + 1 data header)
                for _ in range(3):
                    next(f)
                for _ in range(sample_size):
                    try:
                        line = next(f)
                        total_length += len(line.encode('utf-8'))
                        lines_read += 1
                    except StopIteration:
                        break
            if lines_read > 0:
                avg_line_length = total_length / lines_read
                # Rough estimate: remaining size divided by avg length
                # Subtract an approximate size for the first 3 lines
                estimated_total_rows = max(1, int((file_size - 200) / avg_line_length))
            else:
                estimated_total_rows = 1
        except Exception:
            estimated_total_rows = 1

        rows_processed = 0

        # Read data starting after the first 2 lines (so pandas sees the third line as header)
        for chunk in pd.read_csv(
            file_path,
            skiprows=2,               # skip 2 metadata lines; keep header line
            chunksize=chunk_size,
        ):
            # Normalize columns by name regardless of exact casing/spaces
            cols_lower = {c.lower(): c for c in chunk.columns}
            time_col = cols_lower.get('time in s')
            if not time_col:
                raise ValueError('Missing "time in s" column in Display file header')

            # Find all channel min/max columns
            channel_pairs = {}
            for key, orig in cols_lower.items():
                m = re.search(r'^ch(\d+)\s+(minimum|maximum)\s+in\s+v$', key.strip())
                if m:
                    ch = int(m.group(1))
                    kind = m.group(2)  # minimum or maximum
                    channel_pairs.setdefault(ch, {})[kind] = orig

            if not channel_pairs:
                raise ValueError('No channel min/max columns found (expected e.g. "CH1 minimum in V", "CH1 maximum in V")')

            # Build base dataframe with time
            norm = pd.DataFrame({'Second': pd.to_numeric(chunk[time_col], errors='coerce')})

            # Track available channels
            available_channels = []

            # For each channel with both min and max, compute midline into Value_CHn
            for ch, pair in sorted(channel_pairs.items()):
                if 'minimum' in pair and 'maximum' in pair:
                    min_s = pd.to_numeric(chunk[pair['minimum']], errors='coerce')
                    max_s = pd.to_numeric(chunk[pair['maximum']], errors='coerce')
                    mid = (min_s + max_s) / 2.0
                    norm[f'Value_CH{ch}'] = mid
                    available_channels.append(ch)

            if not available_channels:
                raise ValueError('No complete min/max pairs found for any channel')

            # Choose primary channel for plotting: prefer CH1, else smallest channel number
            primary_ch = 1 if 1 in available_channels else min(available_channels)
            norm['Value'] = norm[f'Value_CH{primary_ch}']

            # Drop rows with NaNs in time or primary value
            norm = norm.dropna(subset=['Second', 'Value'])

            chunks.append(norm)
            rows_processed += len(norm)
            if progress_callback:
                # Scale rows processed against estimate
                progress = min(95, int(10 + 80 * (rows_processed / max(estimated_total_rows, 1))))
                progress_callback(progress, 100, f"Reading data... (approximately {rows_processed:,} points)")

        if not chunks:
            raise ValueError('No data rows found in Display file')

        if progress_callback:
            progress_callback(97, 100, 'Combining data chunks...')

        data = pd.concat(chunks, ignore_index=True)

        # Save channels metadata
        value_ch_cols = [c for c in data.columns if c.startswith('Value_CH')]
        channels = sorted(int(c.replace('Value_CH', '')) for c in value_ch_cols)
        if channels:
            metadata['Channels'] = channels

        if progress_callback:
            progress_callback(100, 100, f'Done! Total points: {len(data):,}')

        return metadata, data
