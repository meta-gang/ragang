class ANSIStyler:
    FORE_COLORS = {
        "black": 30, "red": 31, "green": 32, "yellow": 33,
        "blue": 34, "magenta": 35, "cyan": 36, "white": 37,
        'light-black': 90, 'light-red': 91, 'light-green': 92, 'light-yellow': 93,
        'light-blue': 94, 'light-magenta': 95, 'light-cyan': 96, 'light-white': 97
    }
    BACK_COLORS = {
        "black": 40, "red": 41, "green": 42, "yellow": 43,
        "blue": 44, "magenta": 45, "cyan": 46, "white": 47,
        'light-black': 100, 'light-red': 101, 'light-green': 102, 'light-yellow': 103,
        'light-blue': 104, 'light-magenta': 105, 'light-cyan': 106, 'light-white': 107
    }
    FONT_STYLES = {
        "bold": 1, "faint": 2, "underline": 4, "blink": 5,
        "reverse": 7, "strike": 9, "normal": 0
    }

    @staticmethod
    def style(text: str, fore_color: str = None, back_color: str = None, font_style: str = 'normal'):
        codes = []
        if font_style in ANSIStyler.FONT_STYLES:
            codes.append(str(ANSIStyler.FONT_STYLES[font_style]))
        if fore_color in ANSIStyler.FORE_COLORS:
            codes.append(str(ANSIStyler.FORE_COLORS[fore_color]))
        if back_color in ANSIStyler.BACK_COLORS:
            codes.append(str(ANSIStyler.BACK_COLORS[back_color]))
        code_seq = ";".join(codes)
        return f"\033[{code_seq}m{text}\033[0m"
