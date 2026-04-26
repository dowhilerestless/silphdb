import pygame
import sys
import os
import requests
from datetime import datetime

SCREEN_WIDTH = 792
SCREEN_HEIGHT = 272
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (150, 150, 150)

SPRITE_CACHE = {}

API_BASE_URL = "http://127.0.0.1:8000"


def fetch_page_data(binder_profile, page_number):
    """Hits your actual FastAPI backend for the live PostgreSQL data."""
    try:
        url = f"{API_BASE_URL}/api/binder/{binder_profile}/page/{page_number}"
        response = requests.get(url, timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"API Error: {e}")
    return None


def format_date(date_str):
    """Converts 2023-11-12 to Nov 12, 2023"""
    if not date_str:
        return "Unknown"
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return d.strftime("%b %d, %Y").replace(" 0", " ")
    except:
        return date_str


def get_pokemon_sprite(pokedex_number):
    if pokedex_number in SPRITE_CACHE:
        return SPRITE_CACHE[pokedex_number]
    try:
        sprite_path = f"sprites/{pokedex_number}.png"
        if os.path.exists(sprite_path):
            sprite = pygame.image.load(sprite_path).convert_alpha()
            sprite = pygame.transform.scale(sprite, (80, 80))
            SPRITE_CACHE[pokedex_number] = sprite
            return sprite
    except Exception as e:
        print(f"Sprite fail for #{pokedex_number}: {e}")
    return None


def get_silhouette(sprite):
    """Turns a loaded sprite into a pure black silhouette for uncollected cards."""
    if not sprite:
        return None
    mask = pygame.mask.from_surface(sprite)
    return mask.to_surface(setcolor=(0, 0, 0, 255), unsetcolor=(0, 0, 0, 0))


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
    text_surf = font.render(text, True, text_color)
    text_rect = text_surf.get_rect(center=rect.center)
    surface.blit(text_surf, text_rect)


def main():
    print("🎮 Booting High-Density Data Archive...")
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("SilphDB - Data Dense UI (Live API)")

    header_font = load_retro_font(16)
    title_font = load_retro_font(14)
    body_font = load_retro_font(9)
    micro_font = load_retro_font(8)

    current_row = 0
    total_rows = 3
    current_page = 1

    page_data = fetch_page_data("151", current_page)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_DOWN:
                    current_row = (current_row + 1) % total_rows
                elif event.key == pygame.K_UP:
                    current_row = (current_row - 1) % total_rows
                elif event.key == pygame.K_RIGHT:
                    if current_page < 17:
                        current_page += 1
                        current_row = 0
                        page_data = fetch_page_data("151", current_page)
                elif event.key == pygame.K_LEFT:
                    if current_page > 1:
                        current_page -= 1
                        current_row = 0
                        page_data = fetch_page_data("151", current_page)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    current_row = (current_row - 1) % total_rows
                    current_row = (current_row + 1) % total_rows

        screen.fill(WHITE)
        pygame.draw.rect(
            screen, BLACK, (2, 2, SCREEN_WIDTH - 4, SCREEN_HEIGHT - 4), 4)
        pygame.draw.rect(
            screen, BLACK, (8, 8, SCREEN_WIDTH - 16, SCREEN_HEIGHT - 16), 1)

        if not page_data:
            screen.blit(header_font.render(
                "SilphDB: API OFFLINE or LOADING", True, BLACK), (16, 16))
            pygame.display.flip()
            continue

        nav_text = f"SilphDB: Page {page_data.get('page_number', current_page)} - Row: {current_row + 1}/3"
        screen.blit(header_font.render(nav_text, True, BLACK), (16, 16))

        pygame.draw.line(screen, BLACK, (8, 40), (SCREEN_WIDTH - 8, 40), 4)

        col_width = (SCREEN_WIDTH - 16) // 3
        start_index = current_row * 3
        end_index = start_index + 3

        active_slots = page_data.get("slots", [])[start_index:end_index]

        for i, slot in enumerate(active_slots):
            col_x = 8 + (i * col_width)

            if i > 0:
                pygame.draw.line(screen, BLACK, (col_x, 40),
                                 (col_x, SCREEN_HEIGHT - 8), 4)

            is_collected = slot.get('asset_id') is not None

            sprite_x = col_x + 10
            sprite_y = 50

            sprite = get_pokemon_sprite(slot['pokedex_number'])
            if sprite:
                if is_collected:
                    screen.blit(sprite, (sprite_x, sprite_y))
                else:
                    silhouette = get_silhouette(sprite)
                    screen.blit(silhouette, (sprite_x, sprite_y))

            text_x = col_x + 95

            dex_num = f"No. {slot['pokedex_number']:03d}"
            screen.blit(micro_font.render(dex_num, True, BLACK), (text_x, 50))

            if is_collected:
                grade = slot.get('surface_grade')
                badge_y = 47
                if grade:
                    badge_w = 45
                    badge_x = col_x + col_width - 10 - badge_w
                    draw_retro_box(screen, pygame.Rect(
                        badge_x, badge_y, badge_w, 14), f"PSA{grade}", micro_font, invert=True)
                else:
                    badge_w = 30
                    badge_x = col_x + col_width - 10 - badge_w
                    draw_retro_box(screen, pygame.Rect(
                        badge_x, badge_y, badge_w, 14), "RAW", micro_font)

            title_str = slot.get('printed_name') or slot.get(
                'pokemon_name') or "UNKNOWN"
            screen.blit(title_font.render(
                title_str.upper(), True, BLACK), (text_x, 66))

            meta_y = 86
            line_step = 14

            if is_collected:
                date_str = format_date(slot.get('event_date'))
                screen.blit(micro_font.render(
                    f"ACQ: {date_str}", True, BLACK), (text_x, meta_y))

                source = slot.get('counterparty') or 'Unknown'
                screen.blit(micro_font.render(
                    f"FRM: {source[:11]}", True, BLACK), (text_x, meta_y + line_step))

                cost = slot.get('item_cost')
                if cost and float(cost) > 0:
                    cost_text = f"CST: ${float(cost):,.2f}"
                else:
                    cost_text = "CST: [GIFT/TRADE]"
                screen.blit(micro_font.render(cost_text, True, BLACK),
                            (text_x, meta_y + line_step * 2))
            else:
                screen.blit(micro_font.render(
                    "ACQ: ?", True, BLACK), (text_x, meta_y))
                screen.blit(micro_font.render("FRM: ?", True, BLACK),
                            (text_x, meta_y + line_step))
                screen.blit(micro_font.render("CST: ?", True, BLACK),
                            (text_x, meta_y + line_step * 2))

            pygame.draw.line(screen, BLACK, (col_x + 10, 135),
                             (col_x + col_width - 10, 135), 2)

            details_x = col_x + 10
            y_offset = 145

            if is_collected:
                if slot.get('has_swirl'):
                    draw_retro_box(screen, pygame.Rect(
                        col_x + col_width - 65, y_offset, 55, 18), "*SWIRL", body_font)

                notes = slot.get('curator_notes')
                if notes:
                    words = notes.split()
                    lines = []
                    current_line = ""

                    max_text_width = col_width - 20

                    for word in words:
                        test_line = current_line + word + " "
                        if micro_font.size(test_line)[0] < max_text_width:
                            current_line = test_line
                        else:
                            lines.append(current_line.strip())
                            current_line = word + " "
                    if current_line:
                        lines.append(current_line.strip())

                    MAX_LINES = 4
                    if len(lines) > MAX_LINES:
                        lines = lines[:MAX_LINES]
                        if len(lines[-1]) > 3:
                            lines[-1] = lines[-1][:-3] + "..."
                        else:
                            lines[-1] = "..."

                    note_y = y_offset + 22
                    for line in lines:
                        screen.blit(micro_font.render(
                            line, True, BLACK), (details_x, note_y))
                        note_y += 14

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
