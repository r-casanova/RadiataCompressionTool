# RadiataCompressionTool
A modding tool for radiata stories that can compress/decompress all slz/sle file. 

Not built for speed, built to be close to the original game's compressor which proritizes decompression speeds.

Achieves compression/decompression through header parsing, meaning files that have embedded or nonchained compressed files will need to be split to their own file before this tool can load them.

