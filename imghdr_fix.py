# Fix для отсутствующего модуля imghdr в Python 3.13+
# Этот файл должен быть в той же директории что и main.py

import sys

class ImghdrMock:
    @staticmethod
    def what(file, h=None):
        """Мокап функции what из imghdr"""
        try:
            if h is None:
                if hasattr(file, 'read'):
                    h = file.read(32)
                    file.seek(0)
                elif isinstance(file, str):
                    with open(file, 'rb') as f:
                        h = f.read(32)
                else:
                    h = file[:32]
            
            if len(h) < 32:
                return None
                
            # Простые проверки форматов
            if h.startswith(b'\x89PNG\r\n\x1a\n'):
                return 'png'
            elif h.startswith(b'\xff\xd8'):
                return 'jpeg'
            elif h[:6] in (b'GIF87a', b'GIF89a'):
                return 'gif'
            elif h.startswith(b'BM'):
                return 'bmp'
            elif h.startswith(b'RIFF') and h[8:12] == b'WEBP':
                return 'webp'
        except:
            pass
        return None

# Создаем фиктивный модуль
sys.modules['imghdr'] = ImghdrMock()
