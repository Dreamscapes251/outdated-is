import os
import ctypes
import ctypes.wintypes
import logging
import struct


class Screenshot:
    _log = logging.getLogger('Screenshot')

    @classmethod
    def _capture_pil(cls, output_path: str) -> bool:
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab(all_screens=True)
            img.save(output_path, 'PNG')
            cls._log.info(f'Screenshot (PIL) saved to {output_path}')
            return True
        except Exception as e:
            cls._log.debug(f'PIL screenshot failed: {e}')
            return False

    @classmethod
    def _capture_ctypes(cls, output_path: str) -> bool:
        try:
            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32

            # Make process DPI-aware for accurate coords
            try:
                user32.SetProcessDPIAware()
            except Exception:
                pass

            width = user32.GetSystemMetrics(78)   # SM_CXVIRTUALSCREEN
            height = user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
            left = user32.GetSystemMetrics(76)    # SM_XVIRTUALSCREEN
            top = user32.GetSystemMetrics(77)     # SM_YVIRTUALSCREEN

            if width == 0 or height == 0:
                width = user32.GetSystemMetrics(0)
                height = user32.GetSystemMetrics(1)
                left = 0
                top = 0

            hdc_screen = user32.GetDC(0)
            hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
            hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
            old_bmp = gdi32.SelectObject(hdc_mem, hbmp)

            SRCCOPY = 0x00CC0020
            gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_screen, left, top, SRCCOPY)

            # Build BMP in memory
            bmp_info_size = 40
            bmp_header_size = 14
            row_size = ((width * 3 + 3) // 4) * 4
            pixel_data_size = row_size * height
            file_size = bmp_header_size + bmp_info_size + pixel_data_size

            # BITMAPINFOHEADER
            bmi = struct.pack('<IiiHHIIiiII',
                              bmp_info_size,  # biSize
                              width,          # biWidth
                              -height,        # biHeight (negative = top-down)
                              1,              # biPlanes
                              24,             # biBitCount
                              0,              # biCompression (BI_RGB)
                              pixel_data_size,
                              0, 0, 0, 0)

            # Allocate buffer for pixel data
            pixel_buf = ctypes.create_string_buffer(pixel_data_size)

            class BITMAPINFOHEADER(ctypes.Structure):
                _fields_ = [
                    ('biSize', ctypes.wintypes.DWORD),
                    ('biWidth', ctypes.c_long),
                    ('biHeight', ctypes.c_long),
                    ('biPlanes', ctypes.wintypes.WORD),
                    ('biBitCount', ctypes.wintypes.WORD),
                    ('biCompression', ctypes.wintypes.DWORD),
                    ('biSizeImage', ctypes.wintypes.DWORD),
                    ('biXPelsPerMeter', ctypes.c_long),
                    ('biYPelsPerMeter', ctypes.c_long),
                    ('biClrUsed', ctypes.wintypes.DWORD),
                    ('biClrImportant', ctypes.wintypes.DWORD),
                ]

            bmi_struct = BITMAPINFOHEADER()
            bmi_struct.biSize = bmp_info_size
            bmi_struct.biWidth = width
            bmi_struct.biHeight = -height
            bmi_struct.biPlanes = 1
            bmi_struct.biBitCount = 24
            bmi_struct.biCompression = 0
            bmi_struct.biSizeImage = pixel_data_size

            gdi32.GetDIBits(hdc_mem, hbmp, 0, height, pixel_buf,
                           ctypes.byref(bmi_struct), 0)

            # BMP file header
            bmp_file_header = struct.pack('<2sIHHI',
                                          b'BM',
                                          file_size,
                                          0, 0,
                                          bmp_header_size + bmp_info_size)

            # Write BMP then convert or just save as BMP
            bmp_path = output_path.replace('.png', '.bmp')
            with open(bmp_path, 'wb') as f:
                f.write(bmp_file_header)
                f.write(bmi)
                f.write(pixel_buf.raw)

            # Try converting BMP to PNG with PIL
            try:
                from PIL import Image
                img = Image.open(bmp_path)
                img.save(output_path, 'PNG')
                os.remove(bmp_path)
            except ImportError:
                # No PIL, keep as BMP
                if bmp_path != output_path:
                    os.rename(bmp_path, output_path.replace('.png', '.bmp'))

            # Cleanup GDI
            gdi32.SelectObject(hdc_mem, old_bmp)
            gdi32.DeleteObject(hbmp)
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(0, hdc_screen)

            cls._log.info(f'Screenshot (ctypes) saved')
            return True
        except Exception as e:
            cls._log.debug(f'ctypes screenshot failed: {e}')
            return False

    @classmethod
    def run(cls, output_dir: str) -> None:
        out = os.path.join(output_dir, 'Screenshot')
        os.makedirs(out, exist_ok=True)
        output_path = os.path.join(out, 'screenshot.png')

        if not cls._capture_pil(output_path):
            cls._capture_ctypes(output_path)
