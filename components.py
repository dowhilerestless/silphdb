import pygame
import os
from datetime import datetime

# --- SHARED CONSTANTS ---
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (150, 150, 150)

MONTHS = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
          "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]

SPRITE_CACHE = {}

# --- TEXT & UI RENDERERS ---


def load_retro_font(size):
    font_path = "pixel.ttf"
    if os.path.exists(font_path):
        return pygame.font.Font(font_path, size)
    return pygame.font.SysFont("courier", size, bold=True)


def draw_retro_box(surface, rect, text, font, invert=False):
    bg_color = BLACK if invert else WHITE
    text_color = WHITE if invert else BLACK
    pygame.draw.rect(surface, BLACK, rect, 2)
    pygame.draw.rect(surface, bg_color, (rect.x + 2, rect.y +
                     2, rect.width - 4, rect.height - 4))
    text_surf = font.render(text, False, text_color)
    text_rect = text_surf.get_rect(center=rect.center)
    surface.blit(text_surf, text_rect)


def draw_wrapped_text(surface, text, font, color, x, y, max_width, line_spacing=18):
    """Draws text on the screen, wrapping to a new line if it exceeds max_width."""
    words = str(text).split(' ')
    lines = []
    current_line = ""

    for word in words:
        test_line = current_line + word + " "
        if font.size(test_line)[0] <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word + " "

    if current_line.strip():
        lines.append(current_line)

    for i, line in enumerate(lines):
        surface.blit(font.render(line.strip(), True, color),
                     (x, y + i * line_spacing))

# --- SPRITE HANDLERS ---


def get_pokemon_sprite(pokedex_number, size=(80, 80)):
    cache_key = f"{pokedex_number}_{size[0]}x{size[1]}"
    if cache_key in SPRITE_CACHE:
        return SPRITE_CACHE[cache_key]
    try:
        sprite_path = f"sprites/{pokedex_number}.png"
        if os.path.exists(sprite_path):
            sprite = pygame.image.load(sprite_path).convert_alpha()
            sprite = pygame.transform.scale(sprite, size)
            SPRITE_CACHE[cache_key] = sprite
            return sprite
    except Exception as e:
        print(f"Sprite fail for #{pokedex_number}: {e}")
    return None


def get_silhouette(sprite):
    if not sprite:
        return None
    mask = pygame.mask.from_surface(sprite)
    return mask.to_surface(setcolor=(0, 0, 0, 255), unsetcolor=(0, 0, 0, 0))

# --- FORMATTING HELPERS ---


def format_date(date_str):
    if not date_str:
        return "Unknown"
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return d.strftime("%b %d, %Y").replace(" 0", " ")
    except:
        return date_str


def format_date_short(date_str):
    if not date_str:
        return "Unknown"
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return d.strftime("%m/%d/%y")
    except:
        return date_str

# --- DATA MUNGING ---


def get_available_stats(vitals, arch, source, lineage, archive):
    """Parses raw API data into the format needed for the rotating menu highlights."""
    stats = []
    if vitals and not vitals.get('error'):
        stats.append({'label': "TOTAL SPEND", 'val1': f"${vitals.get('spent', 0):,.2f}",
                     'val1_font': 'header', 'val2': f"({vitals.get('spend_level', '')})", 'val2_font': 'micro'})
        stats.append({'label': "TOTAL SOLD", 'val1': f"${vitals.get('sold', 0):,.2f}",
                     'val1_font': 'header', 'val2': f"({vitals.get('sold_level', '')})", 'val2_font': 'micro'})
        net = vitals.get('net', 0)
        net_str = f"-${abs(net):,.2f}" if net < 0 else f"${net:,.2f}"
        stats.append({'label': "NET SPEND", 'val1': net_str, 'val1_font': 'header',
                     'val2': f"({vitals.get('net_level', '')})", 'val2_font': 'micro'})
        stats.append({'label': "COST PER CARD",
                     'val1': f"${vitals.get('true_average', 0):.2f} / ASSET", 'val1_font': 'title'})
        stats.append({'label': "COLLECTION VELOCITY",
                     'val1': f"{int(vitals.get('thirty_day_velocity', 0))} SECURED", 'val1_font': 'title'})

    if arch and not arch.get('error'):
        stats.append({'label': "RARITY SKEW", 'val1': arch.get(
            'rarity_label', ''), 'val1_font': 'wrap'})
        stats.append({'label': "CONDITION ARCHETYPE", 'val1': arch.get(
            'condition_label', ''), 'val1_font': 'wrap'})
        if arch.get('most_expensive'):
            stats.append({'label': "MOST EXPENSIVE HIT", 'val1': arch['most_expensive']['printed_name'].upper(
            ), 'val1_font': 'title', 'val2': f"${arch['most_expensive']['item_amount']:,.2f}", 'val2_font': 'title'})

    if source and not source.get('error'):
        stats.append({'label': "PLATFORM ARCHETYPE", 'val1': source.get(
            'plat_archetype', ''), 'val1_font': 'wrap'})
        stats.append({'label': "MOST ACTIVE ON",
                     'val1': f"{source.get('busiest_day', '')}S", 'val1_font': 'title'})

    if lineage and not lineage.get('error'):
        stats.append({'label': "FULLY EVOLVED",
                     'val1': f"{lineage.get('completed_lines', 0)} FAMILIES", 'val1_font': 'title'})
        stats.append({'label': "OVERALL BINDER CONDITION", 'val1': str(
            lineage.get('avg_binder_cond', 'UKN')), 'val1_font': 'title'})

    if archive and not archive.get('error'):
        stats.append({'label': "MOST COLLECTED ARTIST", 'val1': archive.get(
            'top_artist', ''), 'val1_font': 'title'})
        stats.append({'label': "COSMIC ANOMALIES",
                     'val1': f"{archive.get('swirl_count', 0)} SWIRLS FOUND", 'val1_font': 'title'})
        stats.append({'label': "LONGEST NOTE", 'val1': archive.get('longest_note_pkmn', ''), 'val1_font': 'title',
                     'val2': f"({archive.get('longest_note_words', 0)} WORDS)", 'val2_font': 'micro'})

    return stats
