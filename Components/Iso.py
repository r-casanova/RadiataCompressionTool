import struct
import json
import shutil
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Default level: INFO. Change to DEBUG for more verbose output
    format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

ISO_PARAMS = dict(
        seed=0x13578642,
        signature=0x27D51556,
        toc_offset=0x3C6C1800,
        total_entries=0x1200,
        sector=0x800
    )
HEADERS = {
    b'SLZ'  : '.slz',      # Compressed file
    b'SLE'  : '.sle',      # Encrypted compressed file
    b'Kods' : '.kods',    # Custom archive (4 bytes)
    b'SEQW' : '.seqw',    # Sound data (4 bytes)
    b'FAS'  : '.fas',
    b'EVD'  : '.evd',
    b'RCP'  : '.rcp',      # Table of IDs
    b'VIB'  : '.vib',
    b'FIS'  : '.fis',
    b'RBAD' : '.rbad',    # Radiata Background Animation Data (4 bytes)
    b'TGILP': '.tgilp',  # Container for map animation data (5 bytes)
    b'FPS'  : '.fps',
    b'IDOM' : '.idom',
    b'RCAD' : '.rcad',
    b'RTA'  : '.rta',
    b'0MPA' : '.mpa',     # Sprite animation data (4 bytes)
    b'RLF'  : '.rlf',
    b'RMF'  : '.rmf',
    b'RMAC' : '.rmac',
    b'1bcb' : '.bcb',
    (0x000010).to_bytes(3, 'little'): ".010",
    (0x000020).to_bytes(3, 'little'): ".020",
    (0xD51556).to_bytes(3, 'little'): ".idx",
    (0x225277).to_bytes(3, 'little'): ".fmv",
    (0x000000).to_bytes(3, 'little'): ".000",
}
###------------------------- Unpacking -----------------------------###

def _unscramble_toc(scrambled_toc:bytes, seed:int, total_entries:int) -> list:
    toc = list(struct.unpack("<%dI" % (total_entries * 3), scrambled_toc))
    key = seed
 
    for i in range(total_entries):
        toc[0*total_entries + i] ^= key
        key ^= (key << 1) & 0xFFFFFFFF
        
        toc[1*total_entries + i] ^= key
        key ^= (~seed) & 0xFFFFFFFF
        
        toc[2*total_entries + i] ^= key    
        key ^= ((key << 2) ^ seed) & 0xFFFFFFFF

    return toc


def _scramble_toc(toc: list, seed: int, total_entries: int) -> bytes:
    key = seed
    for i in range(total_entries):
        toc[0*total_entries + i] ^= key
        key ^= (key << 1) & 0xFFFFFFFF
        toc[1*total_entries + i] ^= key
        key ^= (~seed) & 0xFFFFFFFF
        toc[2*total_entries + i] ^= key
        key ^= ((key << 2) ^ seed) & 0xFFFFFFFF
    return struct.pack("<%dI" % (total_entries * 3), *toc)


def _get_extension(sector_data:bytes, sector_index:int) -> str:
    for magic, ext in sorted(HEADERS.items(), key=lambda x: -len(x[0])):
        if sector_data.startswith(magic): # scan matching header largest to smallest
            return ext # known header
        
    if len(sector_data) >= 20: # radiata pk3 check
        offset_header = int.from_bytes(sector_data[0x10:0x14], 'little')
        pk3_magic = 0x004E000
        if offset_header % pk3_magic == 0: # header is pk3 divisible
            return '.pk3' # pk3 header
    
    logger.debug(f"Unknown header {int.from_bytes(sector_data[:3], 'little'):#010x} at sector {sector_index}")
    return ".bin" # unknown header


def unpack_iso(iso_path: Path, out_dir: Path, progress_callback=None, save_metadata=True, name_overrides: dict = None):
    params = ISO_PARAMS
    out_dir.mkdir(exist_ok=True, parents=True)

    with open(iso_path, "rb") as iso:
        iso.seek(params["toc_offset"])
        signature = struct.unpack("<I", iso.read(4))[0]
        if signature != params["signature"]:
            raise RuntimeError("Not a Radiata Stories ISO")
        logger.info("Found Radiata Stories ISO")

        total_entries = params["total_entries"]
        iso.seek(params["toc_offset"])
        scrambled_toc = iso.read(total_entries * 3 * 4)
        if len(scrambled_toc) < total_entries * 3 * 4:
            raise ValueError('ISO is too small; toc data invalid')

        toc = _unscramble_toc(scrambled_toc, params["seed"], total_entries)
        logger.info(f'Unscrambled toc with {total_entries} entries.')
        original_toc0 = toc[0]
        toc[0] = params["toc_offset"] // params["sector"]

        metadata = []
        for sector_index in range(total_entries):
            try:
                # For metadata: preserve the original unscrambled toc[0] (before override)
                meta_lba = original_toc0 if sector_index == 0 else toc[sector_index]
                raw_size = toc[total_entries + sector_index]
                raw_flags = toc[2 * total_entries + sector_index]
                # For extraction: use the overridden toc[0] (= toc_offset / sector)
                lba  = toc[sector_index] & 0xFFFFFF
                size = raw_size & 0xFFFFFF
                if size == 0:
                    metadata.append({
                        "index": sector_index,
                        "raw_lba": meta_lba,
                        "raw_size": raw_size,
                        "raw_flags": raw_flags,
                        "lba_masked": lba,
                        "size_masked": size,
                        "filename": None,
                    })
                    continue

                iso.seek(lba * params['sector'])
                first_sector = iso.read(params['sector'])
                ext = _get_extension(first_sector, sector_index)

                label = name_overrides.get(sector_index, "") if name_overrides else ""
                filename = f"{sector_index:04d}_{label}{ext}" if label else f"{sector_index:04d}{ext}"
                out_file = out_dir.joinpath(filename)
                with open(out_file, 'wb') as f:
                    f.write(first_sector)
                    for _ in range(size-1):
                        f.write(iso.read(params['sector']))

                metadata.append({
                    "index": sector_index,
                    "raw_lba": meta_lba,
                    "raw_size": raw_size,
                    "raw_flags": raw_flags,
                    "lba_masked": lba,
                    "size_masked": size,
                    "filename": filename,
                })

                if progress_callback and sector_index % 100 == 0:
                    progress_callback(sector_index, total_entries)

            except Exception as e:
                logger.error(f'Error extracting index {sector_index} at LBA {hex(lba)}: {e}')

        if save_metadata:
            meta_path = out_dir / "toc_metadata.json"
            with open(meta_path, "w") as f:
                json.dump({
                    "seed": params["seed"],
                    "toc_offset": params["toc_offset"],
                    "total_entries": total_entries,
                    "sector_size": params["sector"],
                    "entries": metadata,
                }, f, indent=2)
            logger.info(f"Saved TOC metadata to {meta_path}")


###------------------------- Packing --------------------------------###

def _find_file_by_index(directory: Path, index: int) -> Path | None:
    """Find an extracted file by its 4-digit index prefix."""
    prefix = f"{index:04d}"
    for path in directory.iterdir():
        if path.name.startswith(prefix) and path.name[4:5] in ('', '.', '_'):
            return path
    return None


def pack_iso(extracted_dir: Path, output_iso: Path, original_iso: Path, progress_callback=None):
    meta_path = extracted_dir / "toc_metadata.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Metadata file not found: {meta_path}")

    with open(meta_path) as f:
        meta = json.load(f)

    seed = meta["seed"]
    toc_offset = meta["toc_offset"]
    total_entries = meta["total_entries"]
    sector_size = meta["sector_size"]
    entries = meta["entries"]

    logger.info(f"Copying original ISO to {output_iso}")
    shutil.copy2(original_iso, output_iso)

    with open(output_iso, "r+b") as iso:
        for entry in entries:
            if entry["size_masked"] == 0:
                continue
            file_path = _find_file_by_index(extracted_dir, entry["index"])
            if file_path is None:
                logger.warning(f"Missing file for index {entry['index']}, skipping")
                continue

            lba = entry["lba_masked"]
            iso.seek(lba * sector_size)
            iso.write(file_path.read_bytes())

            if progress_callback and entry["index"] % 100 == 0:
                progress_callback(entry["index"], total_entries)

        toc = [0] * (total_entries * 3)
        for entry in entries:
            idx = entry["index"]
            toc[idx] = entry["raw_lba"]
            toc[total_entries + idx] = entry["raw_size"]
            toc[2 * total_entries + idx] = entry["raw_flags"]

        scrambled = _scramble_toc(toc, seed, total_entries)
        iso.seek(toc_offset)
        iso.write(scrambled)

    idx_file = _find_file_by_index(extracted_dir, 0)
    if idx_file:
        idx_file.write_bytes(scrambled)
        logger.info(f"Updated {idx_file.name} to match repacked TOC")

    logger.info(f"Packed ISO written to {output_iso}")

