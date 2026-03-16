import struct
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


def unpack_iso(iso_path: Path, out_dir: Path, progress_callback=None):
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
        toc[0] = params["toc_offset"] // params["sector"]

        for sector_index in range(total_entries):
            try:
                lba  = toc[sector_index]
                size = toc[total_entries + sector_index]
                if size == 0:
                    continue

                iso.seek(lba * params['sector'])
                first_sector = iso.read(params['sector'])
                ext = _get_extension(first_sector, sector_index)

                out_file = out_dir.joinpath(f"{sector_index:04d}{ext}")
                with open(out_file, 'wb') as f:
                    f.write(first_sector)
                    for _ in range(size-1):
                        f.write(iso.read(params['sector']))
                if progress_callback and sector_index % 100 == 0:
                    progress_callback(sector_index, total_entries)
                    
            except Exception as e:
                logger.error(f'Error extracting index {sector_index} at LBA {hex(lba)}: {e}')

