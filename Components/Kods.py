import struct
import re
from pathlib import Path
from typing import Any, Optional, Tuple

# TODO external payload research/support

###---------------------------- Packing ----------------------------###

def start_kods_packing(input_dir: Path, output_path: Path, original_kods: Path) -> None:
    # Validations
    if not input_dir.is_dir():
        raise ValueError(f'Input must be a directory: {input_dir}')
    if not original_kods.is_file():
        raise ValueError(f'Original .kods not found: {original_kods}')
    with open(original_kods, 'rb') as f:
        raw_original = f.read()
    if not raw_original[:4] == b'Kods':
        raise ValueError('Original file is missing kods header')
    # Determine original parameters
    params = parse_header(raw_original)
    original_length = len(raw_original)

    extended_raw: Optional[bytes] = None
    if params['extended_table']:
        ext_start = params["table_base"] + params['num_offsets'] * params["alignment"]
        ext_size = params['num_offsets'] * params["alignment"]
        extended_raw = raw_original[ext_start : ext_start + ext_size]
        print(f"Template from original: {params['num_offsets']} slots + extended table ({ext_size} bytes)")

    data_blocks = prepare_data_blocks(input_dir, params['num_offsets'] - 1)
    raw_tail = load_tail(input_dir)
    best_params = analyze_kods_outcomes(data_blocks, params)
    kods_header = create_kods_header(best_params)
    offsets, final_blocks = calculate_offsets(data_blocks, best_params)

    packed_length = pack_kods(output_path, kods_header, best_params, final_blocks, offsets, extended_raw, raw_tail)

    report_sectors(original_length, packed_length)


def prepare_data_blocks(input_dir: Path, num_entries: int) -> list:
    file_map: dict[int, bytes] = {}
    pattern = re.compile(r'_([0-9A-Fa-f]{4})\.bin$', re.IGNORECASE)
    for p in input_dir.glob("*.bin"):
        m = pattern.search(p.name)
        if m:
            idx = int(m.group(1), 16)
            if idx < num_entries:
                file_map[idx] = p.read_bytes()

    return [file_map.get(i, b'') for i in range(num_entries)]


def load_tail(input_dir: Path):
    tail_file = list(input_dir.glob('*_tail.bin'))
    if tail_file:
        tail = tail_file[0].read_bytes()
        print(f'Found tail will append: {tail_file[0].name} ({len(tail)} bytes)')
        return tail
    return None


def analyze_kods_outcomes(data_blocks: list, original_params: dict) -> dict[str,Any]:
    # Get data
    unique_blocks = {}
    total_unique_size = 0
    for block in data_blocks:
        if block and block not in unique_blocks:
            unique_blocks[block] = True
            total_unique_size += len(block)    

    num_entries = len(data_blocks) + 1
    entry_type = original_params['entry_type']
    alignment = 2 if entry_type else 4
    format = '<H' if entry_type else '<I'
    sentinel = 0xFFFF if entry_type else 0xFFFFFFFF

    table_size = original_params['table_base']+ (num_entries * alignment * (2 if original_params['extended_table'] else 1))

    print(f"Analyzing {len(data_blocks)} files ({total_unique_size / 1024:.2f} KB unique data)...")

    best_parameters = None
    # Find best shift
    test_shifts = sorted(list(set([original_params['shift'], 2, 4, 11] + list(range(2, 13)))))    
    for shift in test_shifts:
        denominator = 2 ** shift
        table_padding = (denominator - (table_size % denominator)) % denominator

        current_offset = table_padding
        possible = True
        for block in data_blocks:
            if not block: continue
            if (current_offset >> shift) >= sentinel:
                possible = False
            current_offset += (len(block) + (denominator - 1) & ~(denominator - 1))
        if possible:
            best_parameters = {
                'shift': shift,
                'entry_type': entry_type,
                'alignment': alignment,
                'extended_table': original_params['extended_table'],
                'denominator': denominator,
                'padding': table_padding,
                'num_offsets': num_entries,
                'format': format,
                'sentinel': 0xFFFF if entry_type else 0xFFFFFFFF,
                'reason': f"Safe {original_params['format']} table with shift {shift}"
            }
        if shift >= original_params['shift']:
            break

    if not best_parameters:
        raise ValueError('Archive data is too large for the required table size!')
    
    return best_parameters


def create_kods_header(params: dict) -> int:
    kods_header = (
            (params['num_offsets'] & 0xFFFF) | 
            ((params['shift'] & 0xF) << 16) | 
            ((params['entry_type'] & 0x3) << 20) | 
            (int(params['extended_table']) << 29) | 
            (0 << 30) | # TODO potential external payload flag
            (0 << 31) # runtime flag
        )
    return kods_header


def calculate_offsets(data_blocks: list[Optional[bytes]], params: dict) -> Tuple[list[int], list[bytes]]:
    pos = params['padding']
    shifted_offsets = []
    final_data_blobs = []
    hash_map = {}

    for block in data_blocks:
        if not block: # Handle NULL entries
            shifted_offsets.append(params['sentinel'])
            continue
            
        block_hash = hash(block)
        if block_hash in hash_map: 
            shifted_offsets.append(hash_map[block_hash])
        else: # new entry
            shifted_offsets.append(pos >> params['shift'])
            hash_map[block_hash] = pos >> params['shift']
            final_data_blobs.append(block)
            
            pos += len(block)
            padding = (params['denominator'] - (pos % params['denominator'])) % params['denominator']
            pos += padding
            
            # Add padding to the block itself to keep the file pointer math simple
            final_data_blobs[-1] += (b'\x00' * padding)

    shifted_offsets.append(pos >> params['shift'])
    return shifted_offsets, final_data_blobs


def pack_kods(output_path: Path, kods_header: int, params: dict, data_blocks: list[bytes], offsets: list[int], extended_raw: Optional[bytes], raw_tail: Optional[bytes]) -> int:
    out_file = output_path / 'repack.bin'
    with open(out_file, 'wb') as f:
        f.write(b'Kods')
        f.write(struct.pack('<I', kods_header))
        for offset in offsets: # write standard table
            f.write(struct.pack(params['format'], offset))

        if params['extended_table'] and extended_raw: # write extended table
            expected = params["num_offsets"] * params["alignment"]
            to_write = extended_raw[:expected] + b"\x00" * (expected - len(extended_raw))
            f.write(to_write[:expected])
            print(f"Preserved extended table from original ({expected} bytes)")
    
        # TODO External payload output

        f.write(b'\x00' * params['padding'])
        for block in data_blocks:
            f.write(block)
        
        if raw_tail:
            f.write(raw_tail)
            print(f"Appended tail after data ({len(raw_tail)} bytes)")

        sector_size = 0x800
        sector_padding = (sector_size - (f.tell() % sector_size)) % sector_size
        if sector_padding:
            f.write(b'\x00' * sector_padding)

    print(f'Repacked .kods to {output_path}.\nStatistics; Number of offsets:{params["num_offsets"]} Entry type:{params["entry_type"]}')

    with open(out_file, 'rb') as f:
        return len(f.read())


def report_sectors(original_length: int, packed_length: int) -> None:
    sector_size = 0x800

    original_sectors = (original_length + sector_size - 1) // sector_size
    packed_sectors = (packed_length + sector_size - 1) // sector_size
    sector_diff = original_sectors - packed_sectors

    if sector_diff > 0:
        print(f'SECTOR SIZE CHANGED! Saved {sector_diff} sectors ({sector_diff * 2 // 1024} bytes)')
    elif sector_diff < 0:
        print(f'SECTOR SIZE CHANGED! Grew by {abs(sector_diff)} sectors ({abs(sector_diff) * 2 // 1024})')
    else:
        print('Maintained sector size of original.')

###---------------------------- Unpack -----------------------------###

def start_kods_unpacking(kods_path: Path, output_path: Path) -> None:
    # Check inputs
    with open(kods_path, 'rb') as f:
        raw_kods = f.read()
    if raw_kods[:4] != b'Kods':
        raise ValueError('Header mismatch')
    # Perform unpacking
    params = parse_header(raw_kods)
    print(params)

    offsets = get_offsets(raw_kods, params)
    extract_kods(raw_kods, output_path, kods_path.stem, params, offsets)




def get_offsets(raw_kods: bytes, params: dict) -> list[int]:
    if params['extended_table']:
        table_size = params['table_base'] + (params['num_offsets'] * params['alignment'] * 2)
    else:
        table_size = params['table_base'] + (params['num_offsets'] * params['alignment'])

    params['null_entries'] = set()
    params['null_count'] = 0
    offsets = []
    for index in range(params['num_offsets']): # Calculate payload offsets
        pos = params['table_base'] + (index * params['alignment'])
        raw_offset = struct.unpack_from(params['format'], raw_kods, pos)[0]
        if raw_offset == params['sentinel']: # Empty payload
            offsets.append(-1)
            params['null_entries'].add(index)
            params['null_count'] += 1
        else:
            absolute_offset = table_size + (raw_offset << params['shift'])
            offsets.append(absolute_offset)
    return offsets


def extract_kods(raw_kods: bytes, output_path: Path, kods_name: str, params: dict, offsets: list[int]) -> None:
    output_path.mkdir(parents=True, exist_ok=True)
    extracted = 0
    seen = {} # map (start, end) to filename to detect duplicates

    for i in range(len(offsets) - 1):
        start = offsets[i]
        if start == -1: continue # Skip Nulls
        
        # The 'end' is the next valid offset, but limited by the EOF marker (offsets[-1])
        end = -1
        for j in range(i + 1, len(offsets)):
            if offsets[j] != -1:
                end = offsets[j]
                break
        
        if end == -1 or start >= end: continue

        # Deduplication check for extraction
        if (start, end) in seen:
            print(f"  Alias Found: {i:04X} points to same data as {seen[(start, end)]}")
            continue
        
        segment = raw_kods[start:end]
        if segment.strip(b'\x00'):
            out_name = f'{kods_name}_{i:04X}.bin'
            (output_path / out_name).write_bytes(segment)
            seen[(start, end)] = out_name
            extracted += 1

    last_offset = offsets[-1]
    if last_offset < len(raw_kods):
        tail = raw_kods[last_offset:]
        if tail.strip(b'\x00'):
            tail_path = output_path / f'{kods_name}_tail.bin'
            tail_path.write_bytes(tail)
            print(f"  Tail extracted → {tail_path.name} ({len(tail)} bytes)")

    print(f"Finished — {extracted} unique files extracted.")    
    
###------------------------ Utility ---------------------------###

def parse_header(raw_kods: bytes) -> dict[str,Any]:
    header = struct.unpack_from('<I', raw_kods, 4)[0]
    entry_type = (header >> 20) & 0x3
    if entry_type not in (0,1):
        raise ValueError(f'Unsupported entry_type:{entry_type}')
    if (header >> 31) & 1:
        print('WARNING: Runtime flag set, offsets might be runtime RAM pointers.')

    return {
            'num_offsets': header & 0xFFFF,
            'shift': (header >> 16) & 0xF,
            'entry_type': entry_type,
            'extended_table': (header >> 29) & 1,
            'external_payload': (header >> 30) & 1,
            'runtime_flag': (header >> 31) & 1,
            'alignment': 2 if entry_type else 4,
            'format': '<H' if entry_type else '<I',
            'sentinel': 0xFFFF if entry_type else 0xFFFFFFFF, 
            'table_base': 8,
            }

