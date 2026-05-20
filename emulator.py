import pygame
import sys
from datetime import datetime
import random
import api_client
from components import *

# --- NEW 4.58" IPS DISPLAY DIMENSIONS ---
SCREEN_WIDTH = 960
SCREEN_HEIGHT = 320

anim_vitals = {}

API_BASE_URL = "http://127.0.0.1:8000"

# --- APP STATES ---
STATE_MENU = "menu"
STATE_COLLECTION = "collection"
STATE_STATS = "stats"


def main():
    print("🎮 Booting SilphDB (IPS 960x320 Profile)...")
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("SilphDB")

    header_font = load_retro_font(18)
    title_font = load_retro_font(16)
    micro_font = load_retro_font(10)
    boot_font = load_retro_font(32)

    # State variables
    app_state = "boot"
    binder_id = "151"
    current_mode = "BINDER"

    # BOOT SEQUENCE VARIABLES
    boot_progress = 0.0
    boot_target = 0.0
    boot_start_time = pygame.time.get_ticks()
    wait_start_time = 0
    last_chunk_time = 0
    # Phases: black_screen -> loading -> wait -> fade_white -> fade_menu -> done
    boot_phase = "black_screen"
    fade_alpha = 0

    # Menu State
    menu_options = ["COLLECTION", "STATS", "EXIT"]  # <-- Added EXIT
    menu_index = 0
    stats_page = 0
    vitals_data = None
    stats_data = api_client.fetch_binder_stats(binder_id, mode=current_mode)

    # Collection State
    current_row = 0
    collection_total_rows = 3
    current_page = 1
    page_data = None

    # --- NEW: STATS SELECTION STATE ---
    selected_stat_index = 0
    c1, c2, c3 = 36, 380, 700  # Shifted 20px to the right to fit the arrow
    PAGE_STATS_POSITIONS = {
        # Added (c3, 210) to the end of Page 1
        1: [(c1, 60), (c1, 150), (c1, 210), (c2, 60), (c2, 150), (c2, 210), (c3, 60), (c3, 150), (c3, 210)],
        2: [(c1, 60), (c1, 150), (c2, 60), (c2, 150), (c3, 60), (c3, 150)],
        3: [(c1, 60), (c1, 130), (c1, 210), (c2, 60), (c2, 130), (c2, 210), (c3, 60), (c3, 130), (c3, 210)],
        4: [(c1, 60), (c1, 130), (c1, 210), (c2, 60), (c2, 130), (c2, 210), (c3, 60), (c3, 130), (c3, 210)],
        5: [(c1, 60), (c1, 130), (c1, 210), (c2, 60), (c2, 130), (c2, 210), (c3, 60), (c3, 130)]
    }

    # --- NEW: STAT DETAIL MODAL ---
    show_stat_modal = False
    modal_data = None
    modal_scroll_offset = 0
    STAT_TITLES = {
        # Added "COLLECTOR STATUS" to the end of Page 1
        1: ["TOTAL SPEND", "COST PER CARD", "LOGISTICS OVERHEAD", "TOTAL SOLD", "FORECASTED COMPLETION", "TRADES/GIFTS", "NET SPEND", "REMAINING TARGETS", "COLLECTOR STATUS"],
        2: ["RARITY SKEW", "HOLO VS NON-HOLO", "CONDITION ARCHETYPE", "MOST EXPENSIVE HIT", "ACQUISITION STRATEGY", "CHEAPEST PURCHASE"],
        3: ["PLATFORM ARCHETYPE", "VOLUME LEADER", "SPEND LEADER", "SOURCING SPREAD", "MOST TRANSACTIONS WITH", "MOST FUNDING FOR", "MOST ACTIVE ON", "MEDIAN ASSET COST", "TOP 5 INDEX"],
        4: ["FULLY EVOLVED", "THE TEASE", "STRANDED ORPHANS", "SET ARCHETYPE", "DNA DISTRIBUTION", "ELEMENTAL SKEW", "OVERALL BINDER CONDITION", "THE BLEMISH", "PAGE DENSITY"],
        5: ["OLDEST MEMORY", "NEWEST MEMORY", "LONGEST STREAK", "MOST COLLECTED ARTIST", "COSMIC ANOMALIES", "DOCUMENTATION RATE", "LONGEST NOTE", "CURATOR'S LOG"]
    }

    # --- NEW: ANIMATION SETUP ---
    clock = pygame.time.Clock()
    display_pct = 0.0
    display_col = 0.0
    anim_vitals = {}

    # --- NEW: PAGE 2 VARIABLES ---
    arch_data = None
    anim_arch = {}

    # --- NEW: PAGE 3 VARIABLES ---
    source_data = None
    anim_source = {}

    # --- NEW: PAGE 4 VARIABLES ---
    lineage_data = None
    anim_lineage = {}

    # --- NEW: PAGE 5 VARIABLES ---
    archive_data = None
    anim_archive = {}

    # --- NEW: ROTATING MENU STATS ---
    rotating_stats = []
    last_rotate_time = 0
    rotate_index = 0
    stats_loaded_for_menu = False

    # --- NEW: ROTATING MENU COLLECTION ---
    rotating_collection = []
    last_col_rotate_time = 0
    col_rotate_index = 0
    collection_loaded_for_menu = False

    # --- NEW: LOAD SET ICONS (ORIGINAL COLORS) ---
    set_icons = {}

    # We map both the TCG API set IDs (base2, base3, base4)
    # and the literal names just in case your DB uses either format.
    icon_files = {
        'base2': 'icon_jungle.png',
        'jungle': 'icon_jungle.png',
        'base3': 'icon_fossil.png',
        'fossil': 'icon_fossil.png',
        'base4': 'icon_base2.png',
        'base set 2': 'icon_base2.png'
    }

    for key, filename in icon_files.items():
        try:
            # Load the image and retain the alpha channel
            img = pygame.image.load(f"sprites/{filename}").convert_alpha()
            # Scale down to a clean 20x20 icon
            img = pygame.transform.smoothscale(img, (20, 20))

            # REMOVED THE BLACK FILL MULTIPLY LINE HERE

            set_icons[key] = img
        except Exception as e:
            pass  # Fails silently if the icon hasn't been downloaded yet

    running = True
    while running:
        # Cap the framerate at 60 FPS so the animation speed is consistent
        clock.tick(60)

        # --- NEW: PRE-FETCH ALL DATA BEHIND THE WHITE SCREEN ---
        if app_state == STATE_MENU:
            if not collection_loaded_for_menu:
                rotating_collection = api_client.fetch_collected_assets(
                    binder_id, mode=current_mode)
                if rotating_collection:
                    random.shuffle(rotating_collection)
                collection_loaded_for_menu = True

            if not stats_loaded_for_menu:
                if not vitals_data:
                    vitals_data = api_client.fetch_vitals_data(binder_id, mode=current_mode) or {
                        "error": True}
                if not arch_data:
                    arch_data = api_client.fetch_archetypes_data(binder_id, mode=current_mode) or {
                        "error": True}
                if not source_data:
                    source_data = api_client.fetch_sourcing_data(binder_id, mode=current_mode) or {
                        "error": True}
                if not lineage_data:
                    lineage_data = api_client.fetch_lineage_data(binder_id, mode=current_mode) or {
                        "error": True}
                if not archive_data:
                    archive_data = api_client.fetch_archive_data(binder_id, mode=current_mode) or {
                        "error": True}

                rotating_stats = get_available_stats(
                    vitals_data, arch_data, source_data, lineage_data, archive_data)
                random.shuffle(rotating_stats)
                stats_loaded_for_menu = True

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                # GLOBAL NAVIGATION
                if event.key == pygame.K_ESCAPE:
                    if show_stat_modal:
                        show_stat_modal = False
                    elif app_state != STATE_MENU:
                        app_state = STATE_MENU
                        stats_data = api_client.fetch_binder_stats(
                            binder_id, mode=current_mode)
                        display_pct = 0.0
                        display_col = 0.0
                        boot_phase = "done"
                        anim_vitals.clear()
                        stats_page = 1
                        selected_stat_index = 0

                # MENU NAVIGATION
                elif app_state == STATE_MENU:
                    if event.key == pygame.K_DOWN:
                        menu_index = (menu_index + 1) % len(menu_options)
                    elif event.key == pygame.K_UP:
                        menu_index = (menu_index - 1) % len(menu_options)
                    elif event.key == pygame.K_RETURN:
                        if menu_index == 0:
                            app_state = STATE_COLLECTION
                            if not page_data:
                                page_data = api_client.fetch_page_data(
                                    binder_id, current_page, mode=current_mode)
                        elif menu_index == 1:
                            app_state = STATE_STATS
                            stats_page = 1
                            anim_vitals.clear()
                        elif menu_index == 2:
                            running = False

                # COLLECTION NAVIGATION
                elif app_state == STATE_COLLECTION:
                    if event.key == pygame.K_DOWN:
                        current_row = (current_row + 1) % collection_total_rows
                    elif event.key == pygame.K_UP:
                        current_row = (current_row - 1) % collection_total_rows
                    elif event.key == pygame.K_RIGHT:
                        if current_page < 17:
                            current_page += 1
                            current_row = 0
                            page_data = api_client.fetch_page_data(
                                binder_id, current_page, mode=current_mode)
                    elif event.key == pygame.K_LEFT:
                        if current_page > 1:
                            current_page -= 1
                            current_row = 0
                            page_data = api_client.fetch_page_data(
                                binder_id, current_page, mode=current_mode)

               # --- STATS NAVIGATION ---
                elif app_state == STATE_STATS:
                    if show_stat_modal:
                        if event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                            show_stat_modal = False
                            modal_data = None          # Reset on close
                            modal_scroll_offset = 0
                        elif event.key == pygame.K_DOWN:
                            modal_scroll_offset += 1
                        elif event.key == pygame.K_UP:
                            modal_scroll_offset = max(
                                0, modal_scroll_offset - 1)
                        # Page jump shortcuts for fast scrolling / Sprite Pagination
                        elif event.key == pygame.K_PAGEDOWN or event.key == pygame.K_RIGHT:
                            # --- NEW: CUSTOM PAGINATION FOR SPRITE VIEWS ---
                            if stats_page == 4 and selected_stat_index in [0, 1, 2]:
                                modal_scroll_offset += 1
                            else:
                                modal_scroll_offset += 5
                        elif event.key == pygame.K_PAGEUP or event.key == pygame.K_LEFT:
                            if stats_page == 4 and selected_stat_index in [0, 1, 2]:
                                modal_scroll_offset = max(
                                    0, modal_scroll_offset - 1)
                            else:
                                modal_scroll_offset = max(
                                    0, modal_scroll_offset - 5)
                    else:
                        if event.key == pygame.K_RETURN:
                            # --- NEW: MODE TOGGLE LOGIC ---
                            if selected_stat_index == -1:
                                current_mode = "COLLECTION" if current_mode == "BINDER" else "BINDER"
                                # Wipe the cached data to force a fresh API call on the next frame
                                vitals_data = arch_data = source_data = lineage_data = archive_data = None
                                # Clear animations to trigger the lerping effect again
                                anim_vitals.clear()
                                anim_arch.clear()
                                anim_source.clear()
                                anim_lineage.clear()
                                anim_archive.clear()
                            else:
                                show_stat_modal = True
                                modal_data = None
                                modal_scroll_offset = 0
                        elif event.key == pygame.K_RIGHT:
                            if stats_page < 5:
                                stats_page += 1
                                selected_stat_index = 0
                                anim_arch.clear()
                                anim_source.clear()
                                anim_lineage.clear()
                                anim_archive.clear()
                        elif event.key == pygame.K_LEFT:
                            if stats_page > 1:
                                stats_page -= 1
                                selected_stat_index = 0
                                anim_vitals.clear()
                                anim_arch.clear()
                                anim_source.clear()
                                anim_lineage.clear()
                                anim_archive.clear()
                        elif event.key == pygame.K_DOWN:
                            max_idx = len(
                                PAGE_STATS_POSITIONS.get(stats_page, [])) - 1
                            # --- NEW: Wrap logic supporting -1 ---
                            if selected_stat_index == -1:
                                selected_stat_index = 0
                            elif selected_stat_index < max_idx:
                                selected_stat_index += 1
                            else:
                                selected_stat_index = -1  # Wrap to the mode toggle
                        elif event.key == pygame.K_UP:
                            max_idx = len(
                                PAGE_STATS_POSITIONS.get(stats_page, [])) - 1
                            # --- NEW: Wrap logic supporting -1 ---
                            if selected_stat_index == -1:
                                selected_stat_index = max_idx
                            elif selected_stat_index > 0:
                                selected_stat_index -= 1
                            else:
                                selected_stat_index = -1

        # --- RENDERING ---
        # Only draw the standard white background if we aren't in the black boot screen
        if app_state != "boot":
            screen.fill(WHITE)
            pygame.draw.rect(
                screen, BLACK, (2, 2, SCREEN_WIDTH - 4, SCREEN_HEIGHT - 4), 4)
            pygame.draw.rect(
                screen, BLACK, (8, 8, SCREEN_WIDTH - 16, SCREEN_HEIGHT - 16), 1)

        # ---------------------------------------------------------
        # RENDER: BOOT SEQUENCE
        # ---------------------------------------------------------
        if app_state == "boot":
            screen.fill(BLACK)
            now = pygame.time.get_ticks()

            # Phase 0: Initial Black Screen Delay (Holds for 1.5 seconds)
            if boot_phase == "black_screen":
                if now - boot_start_time > 1500:
                    boot_phase = "loading"
                    last_chunk_time = now

            # Phase 1: Fake Chunk Loading
            elif boot_phase == "loading":
                if now - last_chunk_time > random.randint(100, 350):
                    boot_target += random.randint(15, 35)
                    last_chunk_time = now
                    if boot_target >= 100:
                        boot_target = 100

                # Smoothly animate the bar to the new chunk target
                boot_progress += (boot_target - boot_progress) * 0.15
                if boot_progress >= 99.5:
                    boot_progress = 100
                    boot_phase = "loading_done_wait"
                    wait_start_time = now

            # Phase 2: Pause at 100% (Holds for 500ms)
            elif boot_phase == "loading_done_wait":
                if now - wait_start_time > 500:
                    boot_phase = "fade_white"

            # Draw Title and Progress Bar ONLY after the black_screen phase
            if boot_phase != "black_screen":
                # Draw Centered Title
                title_surf = boot_font.render("SilphDB", True, WHITE)
                title_rect = title_surf.get_rect(
                    center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 20))
                screen.blit(title_surf, title_rect)

                # Draw Progress Bar (Exact width of the text)
                bar_w = title_rect.width
                bar_h = 10
                bar_x = title_rect.x
                bar_y = title_rect.bottom + 10

                pygame.draw.rect(
                    screen, WHITE, (bar_x, bar_y, bar_w, bar_h), 1)
                fill_width = int((bar_w - 2) * (boot_progress / 100))
                if fill_width > 0:
                    pygame.draw.rect(
                        screen, WHITE, (bar_x + 1, bar_y + 1, fill_width, bar_h - 2))

            # Phase 3: Fade to White Effect
            if boot_phase == "fade_white":
                fade_alpha += 5
                if fade_alpha >= 255:
                    fade_alpha = 255
                    boot_phase = "fade_menu"
                    app_state = STATE_MENU  # Kick over to the menu rendering!

                # Draw a white box over everything with increasing opacity
                fade_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
                fade_surface.fill(WHITE)
                fade_surface.set_alpha(fade_alpha)
                screen.blit(fade_surface, (0, 0))

        # ---------------------------------------------------------
        # RENDER: MENU (HOME SCREEN)
        # ---------------------------------------------------------
        elif app_state == STATE_MENU:
            # 1. Header (Title & Restored Compact Progress Bar)
            screen.blit(header_font.render(
                f"SilphDB - BINDER: {binder_id}", True, BLACK), (16, 16))

            if stats_data:
                target_pct = stats_data['percentage']
                target_col = stats_data['collected']
                tot = stats_data['total']

                # ANIMATION MATH (LERP) - Locked until boot finishes!
                if boot_phase == "done":
                    easing_speed = 0.05
                    display_pct += (target_pct - display_pct) * easing_speed
                    display_col += (target_col - display_col) * easing_speed

                    if abs(target_pct - display_pct) < 0.1:
                        display_pct = target_pct
                    if abs(target_col - display_col) < 0.1:
                        display_col = target_col

                # Compact Progress Bar
                bar_w = 200
                bar_h = 16
                bar_x = SCREEN_WIDTH - bar_w - 16
                bar_y = 16

                pygame.draw.rect(
                    screen, BLACK, (bar_x, bar_y, bar_w, bar_h), 2)

                fill_width = int((bar_w - 4) * (display_pct / 100))
                if fill_width > 0:
                    pygame.draw.rect(
                        screen, BLACK, (bar_x + 2, bar_y + 2, fill_width, bar_h - 4))

                pct_surf = micro_font.render(
                    f"{int(display_col)}/{tot} ({display_pct:.1f}%)", True, BLACK)
                screen.blit(
                    pct_surf, (bar_x - pct_surf.get_width() - 8, bar_y + 2))
            else:
                err_surf = micro_font.render("API OFFLINE", True, BLACK)
                screen.blit(err_surf, (SCREEN_WIDTH -
                            err_surf.get_width() - 16, 18))

            # Horizontal Header Line
            pygame.draw.line(screen, BLACK, (8, 44), (SCREEN_WIDTH - 8, 44), 4)

            # The two vertical column dividers (3 equal parts: 320, 640)
            pygame.draw.line(screen, BLACK, (322, 44),
                             (322, SCREEN_HEIGHT - 8), 4)
            pygame.draw.line(screen, BLACK, (636, 44),
                             (636, SCREEN_HEIGHT - 8), 4)

            # --- COLUMN 1: CRYSTAL STYLE MENU ---
            line_spacing = 45

            longest_word = max([title_font.size(opt)[0]
                               for opt in menu_options])
            total_block_height = (len(menu_options) - 1) * \
                line_spacing + title_font.size(menu_options[0])[1]

            col1_width = 312
            col1_height = SCREEN_HEIGHT - 44

            menu_x = 8 + (col1_width - longest_word) // 2 + 10
            menu_y = 44 + (col1_height - total_block_height) // 2

            for i, option in enumerate(menu_options):
                if i == menu_index:
                    point_x = menu_x - 24
                    point_y = menu_y + i * line_spacing + 2
                    pygame.draw.polygon(screen, BLACK, [
                        (point_x, point_y),
                        (point_x, point_y + 14),
                        (point_x + 12, point_y + 7)
                    ])

                screen.blit(title_font.render(
                    option, True, BLACK), (menu_x, menu_y + i * line_spacing))

            # --- COLUMN 2: ROTATING HIGHLIGHTS ---
            if menu_index == 1:
                # 1. Fetch all data lazily if not already loaded
                if not stats_loaded_for_menu:
                    # Draw a loading state so the UI doesn't freeze blankly

                    if not vitals_data:
                        vitals_data = api_client.fetch_vitals_data(
                            binder_id, mode=current_mode) or {"error": True}
                    if not arch_data:
                        arch_data = api_client.fetch_archetypes_data(
                            binder_id, mode=current_mode) or {"error": True}
                    if not source_data:
                        source_data = api_client.fetch_sourcing_data(
                            binder_id, mode=current_mode) or {"error": True}
                    if not lineage_data:
                        lineage_data = api_client.fetch_lineage_data(
                            binder_id, mode=current_mode) or {"error": True}
                    if not archive_data:
                        archive_data = api_client.fetch_archive_data(
                            binder_id, mode=current_mode) or {"error": True}

                    rotating_stats = get_available_stats(
                        vitals_data, arch_data, source_data, lineage_data, archive_data)
                    random.shuffle(rotating_stats)  # Randomize the order!
                    stats_loaded_for_menu = True
                    last_rotate_time = pygame.time.get_ticks()

                # 2. Render the rotating stat if available
                if rotating_stats:
                    now = pygame.time.get_ticks()
                    time_in_cycle = now - last_rotate_time

                    # --- ANIMATION TIMINGS ---
                    slide_in_duration = 600   # 0.6 seconds to snap in
                    rest_duration = 3500      # 3.5 seconds of chill time
                    slide_out_duration = 500  # 0.5 seconds to slide up and away
                    total_duration = slide_in_duration + rest_duration + slide_out_duration

                    # Advance to the next stat when the full cycle is done
                    if time_in_cycle >= total_duration:
                        rotate_index = (rotate_index + 1) % len(rotating_stats)
                        last_rotate_time = now
                        time_in_cycle = 0

                    # --- EASING MATH ---
                    y_anim_offset = 0
                    slide_distance = 200  # Pixels to drop below/above the center point

                    if time_in_cycle < slide_in_duration:
                        # 1. Slide In (from bottom) using Cubic Ease Out
                        t = time_in_cycle / slide_in_duration
                        ease_out = 1 - (1 - t)**3
                        y_anim_offset = slide_distance * (1 - ease_out)

                    elif time_in_cycle < slide_in_duration + rest_duration:
                        # 2. Resting State
                        y_anim_offset = 0

                    else:
                        # 3. Slide Out (to top) using Quadratic Ease In
                        # Changed to t**2 for a crisper exit without the hesitation
                        t = (time_in_cycle - slide_in_duration -
                             rest_duration) / slide_out_duration
                        ease_in = t**2
                        y_anim_offset = -slide_distance * ease_in

                    stat = rotating_stats[rotate_index]

                    # Base coordinates exactly matching Stats pages
                    col2_x = 380

                    # --- THE FIX ---
                    # Explicitly rounding prevents Pygame's float truncation
                    # from causing a 1-pixel twitch when moving negatively
                    y_start = 145 + int(round(y_anim_offset))

                    # --- CLIPPING MASK ---
                    # Prevents the text from drawing outside the center column or over the header/footer bounds
                    # Rect format: (x, y, width, height)
                    screen.set_clip(pygame.Rect(324, 46, 310, 264))

                    # Draw Title
                    screen.blit(micro_font.render(
                        stat['label'], True, GRAY), (col2_x, y_start))

                    # Draw Main Value
                    if stat.get('val1_font') == 'wrap':
                        draw_wrapped_text(
                            screen, stat['val1'], title_font, BLACK, col2_x, y_start + 15, max_width=240)
                    else:
                        f1 = header_font if stat.get(
                            'val1_font') == 'header' else title_font
                        screen.blit(
                            f1.render(stat['val1'], True, BLACK), (col2_x, y_start + 15))

                    # Draw Sub-Value (if present)
                    if 'val2' in stat:
                        f2 = micro_font if stat.get(
                            'val2_font') == 'micro' else title_font
                        y_val2 = y_start + 35
                        screen.blit(
                            f2.render(stat['val2'], True, BLACK), (col2_x, y_val2))

                    # Remove the clipping mask so the rest of the UI can draw normally
                    screen.set_clip(None)

            # --- MENU HOVER: COLLECTION ROTATION ---
            elif menu_index == 0:
                # 1. Fetch collection data lazily
                if not collection_loaded_for_menu:

                    rotating_collection = api_client.fetch_collected_assets(
                        binder_id, mode=current_mode)
                    if rotating_collection:
                        random.shuffle(rotating_collection)  # Randomize!
                    collection_loaded_for_menu = True
                    last_col_rotate_time = pygame.time.get_ticks()

                # 2. Render the rotating collected asset
                if rotating_collection:
                    now = pygame.time.get_ticks()
                    time_in_cycle = now - last_col_rotate_time

                    # --- ANIMATION TIMINGS ---
                    slide_in_duration = 600
                    rest_duration = 3500
                    slide_out_duration = 500
                    total_duration = slide_in_duration + rest_duration + slide_out_duration

                    if time_in_cycle >= total_duration:
                        col_rotate_index = (
                            col_rotate_index + 1) % len(rotating_collection)
                        last_col_rotate_time = now
                        time_in_cycle = 0

                    # --- EASING MATH ---
                    y_anim_offset = 0
                    slide_distance = 200

                    if time_in_cycle < slide_in_duration:
                        t = time_in_cycle / slide_in_duration
                        ease_out = 1 - (1 - t)**3
                        y_anim_offset = slide_distance * (1 - ease_out)
                    elif time_in_cycle < slide_in_duration + rest_duration:
                        y_anim_offset = 0
                    else:
                        t = (time_in_cycle - slide_in_duration -
                             rest_duration) / slide_out_duration
                        ease_in = t**2
                        y_anim_offset = -slide_distance * ease_in

                    slot = rotating_collection[col_rotate_index]

                    # --- CLIPPING MASK ---
                    screen.set_clip(pygame.Rect(324, 46, 310, 264))

                    # Center alignment logic
                    col_x = 344
                    base_y = 60 + int(round(y_anim_offset))

                    sprite_x = col_x - 30
                    sprite_y = base_y

                    sprite = get_pokemon_sprite(
                        slot['pokedex_number'], size=(120, 120))
                    if sprite:
                        screen.blit(sprite, (sprite_x, sprite_y))

                    text_x = sprite_x + 115
                    dex_num = f"No. {slot['pokedex_number']:03d}"
                    screen.blit(micro_font.render(
                        dex_num, False, BLACK), (text_x, base_y + 20))

                    grading_status = slot.get('grading_status')
                    badge_y = base_y + 17
                    if grading_status == "Graded":
                        grade = slot.get('surface_grade')
                        badge_text = f"PSA {grade if grade else '?'}"
                        invert_badge = True
                    else:
                        raw_cond = slot.get('raw_condition') or "UKN"
                        badge_text = f"RAW {raw_cond}"
                        invert_badge = False

                    text_width = micro_font.size(badge_text)[0]
                    badge_w = text_width + 12
                    badge_x = 636 - 12 - badge_w  # Align to the right edge of Col 2

                    draw_retro_box(screen, pygame.Rect(
                        badge_x, badge_y, badge_w, 18), badge_text, micro_font, invert=invert_badge)

                    # Indicators (Holo/Swirl)
                    indicators = []
                    finish_type = slot.get('finish')
                    if finish_type == 'Holo':
                        indicators.append("H")
                    elif finish_type == 'Reverse-Holo':
                        indicators.append("RH")
                    if slot.get('has_swirl'):
                        indicators.append("S")

                    if indicators:
                        dex_width = micro_font.size(dex_num)[0]
                        left_bound = text_x + dex_width
                        available_width = badge_x - left_bound
                        step = available_width / (len(indicators) + 1)
                        for idx, ind_text in enumerate(indicators):
                            ind_surf = micro_font.render(ind_text, True, BLACK)
                            center_x = left_bound + (step * (idx + 1))
                            ind_draw_x = center_x - (ind_surf.get_width() / 2)
                            screen.blit(ind_surf, (ind_draw_x, base_y + 20))

                    title_str = slot.get('printed_name') or slot.get(
                        'pokemon_name') or "UNKNOWN"
                    screen.blit(title_font.render(title_str.upper(),
                                True, BLACK), (text_x, base_y + 38))

                    meta_y = base_y + 60
                    line_step = 16

                    date_str = format_date(slot.get('event_date'))
                    screen.blit(micro_font.render(
                        f"ACQ: {date_str}", True, BLACK), (text_x, meta_y))

                    source = slot.get('platform') or 'Unknown'
                    screen.blit(micro_font.render(
                        f"FRM: {source[:15]}", True, BLACK), (text_x, meta_y + line_step))

                    cost = slot.get('item_cost')
                    cost_text = f"CST: ${float(cost):,.2f}" if cost and float(
                        cost) > 0 else "CST: [GIFT/TRADE]"
                    screen.blit(micro_font.render(cost_text, True,
                                BLACK), (text_x, meta_y + line_step * 2))

                    # --- NEW: DRAW SET ICON ---
                    set_id = str(slot.get('set_id', '')).lower()
                    if set_id in set_icons:
                        icon_img = set_icons[set_id]
                        # Align to the right edge (624) and rest 4px above the line (base_y + 110)
                        icon_x = 624 - icon_img.get_width()
                        icon_y = (base_y + 110) - 4 - icon_img.get_height()
                        screen.blit(icon_img, (icon_x, icon_y))

                    pygame.draw.line(
                        screen, BLACK, (336, base_y + 110), (624, base_y + 110), 2)

                    notes = slot.get('curator_notes')
                    if notes:
                        words = notes.split()
                        lines, current_line = [], ""
                        max_text_width = 280

                        for word in words:
                            test_line = current_line + word + " "
                            if micro_font.size(test_line)[0] < max_text_width:
                                current_line = test_line
                            else:
                                lines.append(current_line)
                                current_line = word + " "

                        if current_line.strip():
                            lines.append(current_line)

                        if len(lines) > 10:
                            lines = lines[:10]
                            lines[-1] = lines[-1].strip() + "..."

                        note_y = base_y + 120
                        for line in lines:
                            screen.blit(micro_font.render(
                                line.strip(), True, BLACK), (336, note_y))
                            note_y += 14

                    screen.set_clip(None)

            # --- NEW: MENU HOVER EXIT ---
            elif menu_index == 2:
                # Center the text perfectly in the middle column
                text_surf = header_font.render("Goodbye!", True, BLACK)
                center_x = 324 + (310 // 2)
                center_y = 44 + ((SCREEN_HEIGHT - 44) // 2)
                text_rect = text_surf.get_rect(center=(center_x, center_y))
                screen.blit(text_surf, text_rect)

            # --- COLUMN 3: LATEST ACQUISITION ---
            if stats_data and stats_data.get('latest_asset'):
                slot = stats_data['latest_asset']
                col_x = 640
                col_width = 320

                screen.blit(micro_font.render(
                    "LATEST ACQUISITION:", True, GRAY), (col_x + 12, 60))

                sprite_x = col_x - 20
                sprite_y = 60

                sprite = get_pokemon_sprite(
                    slot['pokedex_number'], size=(120, 120))
                if sprite:
                    screen.blit(sprite, (sprite_x, sprite_y))

                text_x = sprite_x + 120
                dex_num = f"No. {slot['pokedex_number']:03d}"
                screen.blit(micro_font.render(
                    dex_num, False, BLACK), (text_x, 80))

                grading_status = slot.get('grading_status')
                badge_y = 77
                if grading_status == "Graded":
                    grade = slot.get('surface_grade')
                    badge_text = f"PSA {grade if grade else '?'}"
                    invert_badge = True
                else:
                    raw_cond = slot.get('raw_condition') or "UKN"
                    badge_text = f"RAW {raw_cond}"
                    invert_badge = False

                text_width = micro_font.size(badge_text)[0]
                badge_w = text_width + 12
                badge_x = col_x + col_width - 12 - badge_w

                draw_retro_box(screen, pygame.Rect(
                    badge_x, badge_y, badge_w, 18), badge_text, micro_font, invert=invert_badge)

                indicators = []
                finish_type = slot.get('finish')
                if finish_type == 'Holo':
                    indicators.append("H")
                elif finish_type == 'Reverse-Holo':
                    indicators.append("RH")
                if slot.get('has_swirl'):
                    indicators.append("S")

                if indicators:
                    dex_width = micro_font.size(dex_num)[0]
                    left_bound = text_x + dex_width
                    available_width = badge_x - left_bound
                    step = available_width / (len(indicators) + 1)
                    for idx, ind_text in enumerate(indicators):
                        ind_surf = micro_font.render(ind_text, True, BLACK)
                        center_x = left_bound + (step * (idx + 1))
                        ind_draw_x = center_x - (ind_surf.get_width() / 2)
                        screen.blit(ind_surf, (ind_draw_x, 80))

                title_str = slot.get('printed_name') or slot.get(
                    'pokemon_name') or "UNKNOWN"
                screen.blit(title_font.render(
                    title_str.upper(), True, BLACK), (text_x, 98))

                meta_y = 120
                line_step = 16

                date_str = format_date(slot.get('event_date'))
                screen.blit(micro_font.render(
                    f"ACQ: {date_str}", True, BLACK), (text_x, meta_y))

                source = slot.get('platform') or 'Unknown'
                screen.blit(micro_font.render(
                    f"FRM: {source[:15]}", True, BLACK), (text_x, meta_y + line_step))

                cost = slot.get('item_cost')
                cost_text = f"CST: ${float(cost):,.2f}" if cost and float(
                    cost) > 0 else "CST: [GIFT/TRADE]"
                screen.blit(micro_font.render(cost_text, True, BLACK),
                            (text_x, meta_y + line_step * 2))

                # --- NEW: DRAW SET ICON ---
                set_id = str(slot.get('set_id', '')).lower()
                if set_id in set_icons:
                    icon_img = set_icons[set_id]
                    # Align to the right edge of the column and rest 4px above the line (170)
                    icon_x = (col_x + col_width - 12) - icon_img.get_width()
                    icon_y = 170 - 4 - icon_img.get_height()
                    screen.blit(icon_img, (icon_x, icon_y))

                pygame.draw.line(screen, BLACK, (col_x + 12, 170),
                                 (col_x + col_width - 12, 170), 2)

                notes = slot.get('curator_notes')
                if notes:
                    words = notes.split()
                    lines, current_line = [], ""
                    max_text_width = col_width - 24

                    for word in words:
                        test_line = current_line + word + " "
                        if micro_font.size(test_line)[0] < max_text_width:
                            current_line = test_line
                        else:
                            lines.append(current_line)
                            current_line = word + " "

                    if current_line.strip():
                        lines.append(current_line)

                    if len(lines) > 10:
                        lines = lines[:10]
                        lines[-1] = lines[-1].strip() + "..."

                    note_y = 180
                    for line in lines:
                        screen.blit(micro_font.render(
                            line.strip(), True, BLACK), (col_x + 12, note_y))
                        note_y += 14

            # 3. Fade Menu In Effect (Drops the white overlay opacity)
            if boot_phase == "fade_menu":
                fade_alpha -= 5
                if fade_alpha <= 0:
                    fade_alpha = 0
                    boot_phase = "done"  # Boot is completely finished!

                fade_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
                fade_surface.fill(WHITE)
                fade_surface.set_alpha(fade_alpha)
                screen.blit(fade_surface, (0, 0))

        # ---------------------------------------------------------
        # RENDER: STATS
        # ---------------------------------------------------------
        elif app_state == STATE_STATS:
            if stats_page == 1 and not vitals_data:
                vitals_data = api_client.fetch_vitals_data(
                    binder_id, mode=current_mode)
                # Fallback to prevent infinite API pinging if the backend is offline
                if not vitals_data:
                    vitals_data = {"error": True}

            screen.blit(header_font.render(
                f"SilphDB STATS - PAGE {stats_page}/5", True, BLACK), (16, 16))

            # --- NEW: DRAW MODE TOGGLE ---
            mode_text = f"MODE: {current_mode}"
            mode_surf = header_font.render(mode_text, True, BLACK)
            mode_x = SCREEN_WIDTH - mode_surf.get_width() - 16
            mode_y = 16
            screen.blit(mode_surf, (mode_x, mode_y))
            # -----------------------------

            if stats_page == 1:
                if not vitals_data:
                    screen.blit(title_font.render(
                        "LOADING VITALS...", True, BLACK), (40, 100))
                else:
                    # --- ANIMATION INITIALIZATION ---
                    if not anim_vitals:
                        anim_vitals = {
                            'spent': 0.0, 'sold': 0.0, 'net': 0.0, 'pct': 0.0,
                            'true_avg': 0.0, 'overhead': 0.0, 'overhead_pct': 0.0,
                            'cards_left': 0.0, 'momentum': 0.0, 'hustle': 0.0,
                            'eta_m': 0.0, 'eta_y': float(datetime.now().year)
                        }

                    # --- MATH LERPING (Easing) ---
                    ease = 0.05

                    def ease_val(current, target):
                        try:
                            clean_target = str(target).replace(
                                ',', '').replace('$', '')
                            target = float(clean_target)
                        except (ValueError, TypeError):
                            target = 0.0
                        distance = target - current
                        if abs(distance) < 0.005:
                            return target
                        return current + (distance * ease)

                    anim_vitals['spent'] = ease_val(
                        anim_vitals['spent'], vitals_data.get('spent', 0))
                    anim_vitals['sold'] = ease_val(
                        anim_vitals['sold'], vitals_data.get('sold', 0))
                    anim_vitals['net'] = ease_val(
                        anim_vitals['net'], vitals_data.get('net', 0))
                    anim_vitals['pct'] = ease_val(
                        anim_vitals['pct'], vitals_data.get('percentage', 0))
                    anim_vitals['true_avg'] = ease_val(
                        anim_vitals['true_avg'], vitals_data.get('true_average', 0))
                    anim_vitals['overhead'] = ease_val(
                        anim_vitals['overhead'], vitals_data.get('overhead', 0))
                    anim_vitals['overhead_pct'] = ease_val(
                        anim_vitals['overhead_pct'], vitals_data.get('overhead_pct', 0))
                    anim_vitals['cards_left'] = ease_val(
                        anim_vitals['cards_left'], vitals_data.get('cards_left', 0))
                    anim_vitals['momentum'] = ease_val(
                        anim_vitals['momentum'], vitals_data.get('thirty_day_velocity', 0))
                    anim_vitals['hustle'] = ease_val(
                        anim_vitals['hustle'], vitals_data.get('zero_cost_count', 0))

                    # Parse and ease ETA Date
                    target_eta = vitals_data.get('eta', '')
                    display_eta = target_eta
                    if " " in target_eta and target_eta.split()[0] in MONTHS:
                        parts = target_eta.split()
                        target_m_idx = MONTHS.index(parts[0])
                        target_y = int(parts[1])
                        anim_vitals['eta_m'] = ease_val(
                            anim_vitals['eta_m'], target_m_idx)
                        anim_vitals['eta_y'] = ease_val(
                            anim_vitals['eta_y'], target_y)
                        display_eta = f"{MONTHS[int(anim_vitals['eta_m'])]} {int(anim_vitals['eta_y'])}"

                    # --- COLUMN 1: FINANCIALS (X = 16) ---
                    col1_x = 36
                    screen.blit(micro_font.render(
                        "TOTAL SPEND", True, GRAY), (col1_x, 60))
                    screen.blit(header_font.render(
                        f"${anim_vitals['spent']:,.2f}", True, BLACK), (col1_x, 75))

                    spend_level_text = vitals_data.get('spend_level', '')
                    screen.blit(micro_font.render(
                        f"({spend_level_text})", True, BLACK), (col1_x, 95))

                    screen.blit(micro_font.render(
                        "COST PER CARD", True, GRAY), (col1_x, 150))
                    screen.blit(title_font.render(
                        f"${anim_vitals['true_avg']:.2f} / ASSET", True, BLACK), (col1_x, 165))

                    screen.blit(micro_font.render(
                        "LOGISTICS OVERHEAD (TAX+SHIP)", True, GRAY), (col1_x, 210))
                    screen.blit(title_font.render(
                        f"${anim_vitals['overhead']:,.2f} ({int(anim_vitals['overhead_pct'])}%)", True, BLACK), (col1_x, 225))

                    # --- COLUMN 2: VELOCITY (X = 360) ---
                    col2_x = 380
                    screen.blit(micro_font.render(
                        "TOTAL SOLD", True, GRAY), (col2_x, 60))
                    screen.blit(header_font.render(
                        f"${anim_vitals['sold']:,.2f}", True, BLACK), (col2_x, 75))

                    # --- NEW ADDITION ---
                    sold_level_text = vitals_data.get('sold_level', '')
                    screen.blit(micro_font.render(
                        f"({sold_level_text})", True, BLACK), (col2_x, 95))

                    screen.blit(micro_font.render(
                        "FORECASTED COMPLETION", True, GRAY), (col2_x, 150))
                    screen.blit(title_font.render(
                        display_eta, True, BLACK), (col2_x, 165))

                    screen.blit(micro_font.render(
                        "TRADES/GIFTS", True, GRAY), (col2_x, 210))
                    screen.blit(title_font.render(
                        f"{int(anim_vitals['hustle'])} ASSETS", True, BLACK), (col2_x, 225))

                    # --- COLUMN 3: RECORDS & HUSTLE (X = 680) ---
                    col3_x = 700
                    screen.blit(micro_font.render(
                        "NET SPEND", True, GRAY), (col3_x, 60))

                    # Handles negative formatting smoothly
                    net_str = f"-${abs(anim_vitals['net']):,.2f}" if anim_vitals['net'] < 0 else f"${anim_vitals['net']:,.2f}"
                    screen.blit(header_font.render(
                        net_str, True, BLACK), (col3_x, 75))

                    net_level_text = vitals_data.get('net_level', '')
                    screen.blit(micro_font.render(
                        f"({net_level_text})", True, BLACK), (col3_x, 95))

                    screen.blit(micro_font.render(
                        "REMAINING TARGETS", True, GRAY), (col3_x, 150))

                    screen.blit(title_font.render(
                        f"{int(anim_vitals['cards_left'])}", True, BLACK), (col3_x, 165))

                    screen.blit(micro_font.render(
                        "COLLECTOR STATUS", True, GRAY), (col3_x, 210))

                    status_text = vitals_data.get(
                        'collector_status', 'UNKNOWN')
                    draw_wrapped_text(
                        screen, status_text, title_font, BLACK, col3_x, 225, max_width=240)

            # ---------------------------------------------------------
            # PAGE 2: ARCHETYPES & SKEWS
            # ---------------------------------------------------------
            elif stats_page == 2:
                if not arch_data:
                    arch_data = api_client.fetch_archetypes_data(
                        binder_id, mode=current_mode)
                    if not arch_data:
                        arch_data = {"error": True}

                if arch_data.get("error"):
                    screen.blit(title_font.render(
                        "LOADING ARCHETYPES...", True, BLACK), (40, 100))
                else:
                    if not anim_arch:
                        anim_arch = {
                            'holo': 0.0, 'non_holo': 0.0,
                            'me_cost': 0.0, 'ch_cost': 0.0
                        }

                    # --- MATH LERPING (Easing) ---
                    ease = 0.05

                    def ease_val(current, target):
                        try:
                            clean_target = str(target).replace(
                                ',', '').replace('$', '')
                            target = float(clean_target)
                        except (ValueError, TypeError):
                            target = 0.0
                        distance = target - current
                        if abs(distance) < 0.005:
                            return target
                        return current + (distance * ease)

                    anim_arch['holo'] = ease_val(
                        anim_arch['holo'], arch_data.get('holo_pct', 0))
                    anim_arch['non_holo'] = ease_val(
                        anim_arch['non_holo'], arch_data.get('non_holo_pct', 0))

                    if arch_data.get('most_expensive'):
                        anim_arch['me_cost'] = ease_val(
                            anim_arch['me_cost'], arch_data['most_expensive']['item_amount'])
                    if arch_data.get('cheapest'):
                        anim_arch['ch_cost'] = ease_val(
                            anim_arch['ch_cost'], arch_data['cheapest']['item_amount'])

                    # --- COLUMN 1: RARITY SKEW (X = 16) ---
                    col1_x = 36
                    screen.blit(micro_font.render(
                        "RARITY SKEW", True, GRAY), (col1_x, 60))
                    draw_wrapped_text(
                        screen, arch_data['rarity_label'], title_font, BLACK, col1_x, 75, max_width=300)

                    screen.blit(micro_font.render(
                        "HOLO VS NON-HOLO RATIO", True, GRAY), (col1_x, 150))
                    screen.blit(title_font.render(
                        f"HOLO: {anim_arch['holo']:.1f}%", True, BLACK), (col1_x, 165))
                    screen.blit(title_font.render(
                        f"NON-HOLO: {anim_arch['non_holo']:.1f}%", True, BLACK), (col1_x, 185))

                    # --- COLUMN 2: COLLECTOR TYPE (X = 360) ---
                    col2_x = 380
                    screen.blit(micro_font.render(
                        "CONDITION ARCHETYPE", True, GRAY), (col2_x, 60))
                    draw_wrapped_text(
                        screen, arch_data['condition_label'], title_font, BLACK, col2_x, 75, max_width=280)

                    screen.blit(micro_font.render(
                        "MOST EXPENSIVE HIT", True, GRAY), (col2_x, 150))
                    if arch_data.get('most_expensive'):
                        me_name = arch_data['most_expensive']['printed_name'].upper(
                        )
                        screen.blit(title_font.render(
                            me_name, True, BLACK), (col2_x, 165))
                        screen.blit(title_font.render(
                            f"${anim_arch['me_cost']:,.2f}", True, BLACK), (col2_x, 185))
                    else:
                        screen.blit(title_font.render(
                            "NO DATA", True, BLACK), (col2_x, 165))

                    # --- COLUMN 3: ACQUISITION STRATEGY (X = 680) ---
                    col3_x = 700
                    screen.blit(micro_font.render(
                        "ACQUISITION STRATEGY", True, GRAY), (col3_x, 60))
                    draw_wrapped_text(
                        screen, arch_data['hunter_label'], title_font, BLACK, col3_x, 75, max_width=240)

                    screen.blit(micro_font.render(
                        "CHEAPEST PURCHASE", True, GRAY), (col3_x, 150))
                    if arch_data.get('cheapest'):
                        ch_name = arch_data['cheapest']['printed_name'].upper()
                        screen.blit(title_font.render(
                            ch_name, True, BLACK), (col3_x, 165))
                        screen.blit(title_font.render(
                            f"${anim_arch['ch_cost']:,.2f}", True, BLACK), (col3_x, 185))
                    else:
                        screen.blit(title_font.render(
                            "NO DATA", True, BLACK), (col3_x, 165))

            # ---------------------------------------------------------
            # PAGE 3: THE SOURCING MAP
            # ---------------------------------------------------------
            elif stats_page == 3:
                if not source_data:
                    source_data = api_client.fetch_sourcing_data(
                        binder_id, mode=current_mode)
                    if not source_data:
                        source_data = {"error": True}

                if source_data.get("error"):
                    screen.blit(title_font.render(
                        "LOADING SOURCING MAP...", True, BLACK), (40, 100))
                else:
                    if not anim_source:
                        anim_source = {
                            'vol_count': 0.0, 'spend_amt': 0.0,
                            'reg_count': 0.0, 'ben_amt': 0.0,
                            'unique': 0.0, 'median': 0.0, 'top_heavy': 0.0
                        }

                    # --- MATH LERPING (Easing) ---
                    ease = 0.05

                    def ease_val(current, target):
                        try:
                            target = float(str(target).replace(
                                ',', '').replace('$', ''))
                        except:
                            target = 0.0
                        distance = target - current
                        if abs(distance) < 0.005:
                            return target
                        return current + (distance * ease)

                    anim_source['vol_count'] = ease_val(
                        anim_source['vol_count'], source_data.get('vol_leader_count', 0))
                    anim_source['spend_amt'] = ease_val(
                        anim_source['spend_amt'], source_data.get('spend_leader_amount', 0))
                    anim_source['reg_count'] = ease_val(
                        anim_source['reg_count'], source_data.get('reg_seller_count', 0))
                    anim_source['ben_amt'] = ease_val(
                        anim_source['ben_amt'], source_data.get('ben_seller_amount', 0))
                    anim_source['unique'] = ease_val(
                        anim_source['unique'], source_data.get('unique_sellers', 0))
                    anim_source['median'] = ease_val(
                        anim_source['median'], source_data.get('median_cost', 0))
                    anim_source['top_heavy'] = ease_val(
                        anim_source['top_heavy'], source_data.get('top_heavy_pct', 0))

                    # --- COLUMN 1: PLATFORM ECOSYSTEM (X = 16) ---
                    col1_x = 36
                    screen.blit(micro_font.render(
                        "PLATFORM ARCHETYPE", True, GRAY), (col1_x, 60))
                    draw_wrapped_text(
                        screen, source_data['plat_archetype'], title_font, BLACK, col1_x, 75, max_width=300)

                    screen.blit(micro_font.render(
                        "VOLUME LEADER", True, GRAY), (col1_x, 130))
                    plat_name = str(
                        source_data['vol_leader_name']).upper()[:15]
                    screen.blit(title_font.render(
                        plat_name, True, BLACK), (col1_x, 145))
                    screen.blit(title_font.render(
                        f"{int(anim_source['vol_count'])} ASSETS", True, BLACK), (col1_x, 165))

                    screen.blit(micro_font.render(
                        "SPEND LEADER", True, GRAY), (col1_x, 210))
                    spend_name = str(
                        source_data['spend_leader_name']).upper()[:15]
                    screen.blit(title_font.render(
                        spend_name, True, BLACK), (col1_x, 225))
                    screen.blit(title_font.render(
                        f"${anim_source['spend_amt']:,.2f}", True, BLACK), (col1_x, 245))

                    # --- COLUMN 2: COUNTERPARTY NETWORK (X = 360) ---
                    col2_x = 380
                    screen.blit(micro_font.render(
                        "SOURCING SPREAD", True, GRAY), (col2_x, 60))
                    tot_assets = source_data['total_assets']
                    draw_wrapped_text(
                        screen, f"{tot_assets} ASSETS ACROSS {int(anim_source['unique'])} UNIQUE SELLERS", title_font, BLACK, col2_x, 75, max_width=280)

                    screen.blit(micro_font.render(
                        "MOST TRANSACTIONS WITH", True, GRAY), (col2_x, 130))
                    reg_name = str(source_data['reg_seller_name']).upper()[:20]
                    screen.blit(title_font.render(
                        reg_name, True, BLACK), (col2_x, 145))
                    screen.blit(micro_font.render(
                        f"{int(anim_source['reg_count'])} ASSETS", True, BLACK), (col2_x, 165))

                    screen.blit(micro_font.render(
                        "MOST FUNDING FOR", True, GRAY), (col2_x, 210))
                    ben_name = str(source_data['ben_seller_name']).upper()[:20]
                    screen.blit(title_font.render(
                        ben_name, True, BLACK), (col2_x, 225))
                    screen.blit(micro_font.render(
                        f"${anim_source['ben_amt']:,.2f}", True, BLACK), (col2_x, 245))

                    # --- COLUMN 3: MARKET & TEMPORAL SKEW (X = 680) ---
                    col3_x = 700
                    screen.blit(micro_font.render(
                        "MOST ACTIVE ON", True, GRAY), (col3_x, 60))
                    screen.blit(title_font.render(
                        f"{source_data['busiest_day']}S", True, BLACK), (col3_x, 75))

                    screen.blit(micro_font.render(
                        "MEDIAN ASSET COST", True, GRAY), (col3_x, 130))
                    screen.blit(title_font.render(
                        f"${anim_source['median']:,.2f}", True, BLACK), (col3_x, 145))

                    screen.blit(micro_font.render(
                        "TOP 5 INDEX", True, GRAY), (col3_x, 210))
                    screen.blit(title_font.render(
                        f"{anim_source['top_heavy']:.1f}% OF TOTAL", True, BLACK), (col3_x, 225))
                    screen.blit(title_font.render(
                        "SPEND", True, BLACK), (col3_x, 245))

            # ---------------------------------------------------------
            # PAGE 4: THE LINEAGE & LOGIC
            # ---------------------------------------------------------
            elif stats_page == 4:
                if not lineage_data:
                    lineage_data = api_client.fetch_lineage_data(
                        binder_id, mode=current_mode)
                    if not lineage_data:
                        lineage_data = {"error": True}

                if lineage_data.get("error"):
                    screen.blit(title_font.render(
                        "LOADING LINEAGE MAP...", True, BLACK), (40, 100))
                else:
                    # --- ADD THIS MISSING BLOCK BACK IN ---
                    if not anim_lineage:
                        anim_lineage = {
                            'completed': 0.0, 'one_away': 0.0, 'orphans': 0.0,
                            'dna_pcts': [0.0, 0.0, 0.0],
                            'dense_pct': 0.0, 'ghost_pct': 0.0
                        }

                    # --- MATH LERPING (Easing) ---
                    ease = 0.05

                    def ease_val(current, target):
                        try:
                            target = float(target)
                        except:
                            target = 0.0
                        distance = target - current
                        if abs(distance) < 0.005:
                            return target
                        return current + (distance * ease)

                    anim_lineage['completed'] = ease_val(
                        anim_lineage['completed'], lineage_data.get('completed_lines', 0))
                    anim_lineage['one_away'] = ease_val(
                        anim_lineage['one_away'], lineage_data.get('one_away', 0))
                    anim_lineage['orphans'] = ease_val(
                        anim_lineage['orphans'], lineage_data.get('orphans', 0))
                    anim_lineage['dense_pct'] = ease_val(
                        anim_lineage['dense_pct'], lineage_data.get('densest_page_pct', 0))
                    anim_lineage['ghost_pct'] = ease_val(
                        anim_lineage['ghost_pct'], lineage_data.get('ghost_page_pct', 0))

                    dist_data = lineage_data.get('set_distribution', [])
                    for i in range(len(dist_data)):
                        if i < len(anim_lineage['dna_pcts']):
                            anim_lineage['dna_pcts'][i] = ease_val(
                                anim_lineage['dna_pcts'][i], dist_data[i]['pct'])

                    # --- COLUMN 1: THE EVOLUTIONARY TREE (X = 16) ---
                    col1_x = 36
                    screen.blit(micro_font.render(
                        "FULLY EVOLVED", True, GRAY), (col1_x, 60))
                    screen.blit(title_font.render(
                        f"{int(anim_lineage['completed'])} FAMILIES", True, BLACK), (col1_x, 75))

                    screen.blit(micro_font.render(
                        "ONE CARD AWAY", True, GRAY), (col1_x, 130))
                    screen.blit(title_font.render(
                        f"{int(anim_lineage['one_away'])} FAMILIES", True, BLACK), (col1_x, 145))

                    screen.blit(micro_font.render(
                        "STRANDED ORPHANS", True, GRAY), (col1_x, 210))
                    screen.blit(title_font.render(
                        f"{int(anim_lineage['orphans'])} POKEMON", True, BLACK), (col1_x, 225))

                   # --- COLUMN 2: SET DNA & ELEMENTAL BIAS (X = 360) ---
                    col2_x = 380
                    screen.blit(micro_font.render(
                        "SET ARCHETYPE", True, GRAY), (col2_x, 60))
                    draw_wrapped_text(
                        screen, lineage_data['set_archetype'], title_font, BLACK, col2_x, 75, max_width=280)

                    screen.blit(micro_font.render(
                        "DNA DISTRIBUTION", True, GRAY), (col2_x, 130))
                    set_y = 145
                    for i, dist in enumerate(lineage_data.get('set_distribution', [])):
                        if i < len(anim_lineage['dna_pcts']):
                            # Dynamically construct the string with the animated number
                            set_str = f"{dist['name']}: {int(anim_lineage['dna_pcts'][i])}%"
                            screen.blit(micro_font.render(
                                set_str, True, BLACK), (col2_x, set_y))
                            set_y += 20

                    screen.blit(micro_font.render(
                        "ELEMENTAL SKEW", True, GRAY), (col2_x, 210))
                    screen.blit(title_font.render(
                        lineage_data['elemental_skew'], True, BLACK), (col2_x, 225))

                    # --- COLUMN 3: QUALITY CONTROL & GRID HEALTH (X = 680) ---
                    col3_x = 700
                    screen.blit(micro_font.render(
                        "OVERALL BINDER CONDITION", True, GRAY), (col3_x, 60))
                    binder_cond_str = str(
                        lineage_data.get('avg_binder_cond', 'UKN'))
                    screen.blit(title_font.render(
                        binder_cond_str, True, BLACK), (col3_x, 75))

                    screen.blit(micro_font.render(
                        "THE BLEMISH", True, GRAY), (col3_x, 130))

                    draw_wrapped_text(
                        screen, lineage_data['weakest_link'], title_font, BLACK, col3_x, 145, max_width=240)

                    screen.blit(micro_font.render(
                        "PAGE DENSITY", True, GRAY), (col3_x, 210))

                    dense_num = lineage_data.get('densest_page_num', '?')
                    ghost_num = lineage_data.get('ghost_page_num', '?')

                    # Dynamically construct the strings
                    dense_str = f"DENSEST: PAGE {dense_num} ({int(anim_lineage['dense_pct'])}%)"
                    ghost_str = f"EMPTIEST: PAGE {ghost_num} ({int(anim_lineage['ghost_pct'])}%)"

                    screen.blit(micro_font.render(
                        dense_str, True, BLACK), (col3_x, 225))
                    screen.blit(micro_font.render(
                        ghost_str, True, BLACK), (col3_x, 245))

            # ---------------------------------------------------------
            # PAGE 5: THE MEMORY ARCHIVE
            # ---------------------------------------------------------
            elif stats_page == 5:
                if not archive_data:
                    archive_data = api_client.fetch_archive_data(
                        binder_id, mode=current_mode)
                    if not archive_data:
                        archive_data = {"error": True}

                if archive_data.get("error"):
                    screen.blit(title_font.render(
                        "LOADING ARCHIVE...", True, BLACK), (40, 100))
                else:
                    if not anim_archive:
                        anim_archive = {
                            'streak': 0.0, 'swirls': 0.0,
                            'doc_rate': 0.0, 'words': 0.0,
                            'manifesto_words': 0.0
                        }

                    # --- MATH LERPING (Easing) ---
                    ease = 0.05

                    def ease_val(current, target):
                        try:
                            target = float(target)
                        except:
                            target = 0.0
                        distance = target - current
                        if abs(distance) < 0.005:
                            return target
                        return current + (distance * ease)

                    anim_archive['streak'] = ease_val(
                        anim_archive['streak'], archive_data.get('max_streak', 0))
                    anim_archive['swirls'] = ease_val(
                        anim_archive['swirls'], archive_data.get('swirl_count', 0))
                    anim_archive['doc_rate'] = ease_val(
                        anim_archive['doc_rate'], archive_data.get('doc_rate', 0))
                    anim_archive['words'] = ease_val(
                        anim_archive['words'], archive_data.get('total_words', 0))
                    anim_archive['words'] = ease_val(
                        anim_archive['words'], archive_data.get('total_words', 0))
                    anim_archive['manifesto_words'] = ease_val(
                        anim_archive['manifesto_words'], archive_data.get('longest_note_words', 0))

                    # --- COLUMN 1: THE TIMELINE (X = 16) ---
                    col1_x = 36
                    screen.blit(micro_font.render(
                        "OLDEST MEMORY (FIRST ACQ)", True, GRAY), (col1_x, 60))
                    screen.blit(title_font.render(
                        archive_data['oldest_date'], True, BLACK), (col1_x, 75))

                    screen.blit(micro_font.render(
                        "NEWEST MEMORY (LAST ACQ)", True, GRAY), (col1_x, 130))
                    screen.blit(title_font.render(
                        archive_data['newest_date'], True, BLACK), (col1_x, 145))

                    screen.blit(micro_font.render(
                        "LONGEST ACQUISITION STREAK", True, GRAY), (col1_x, 210))
                    screen.blit(title_font.render(
                        f"{int(anim_archive['streak'])} CONSECUTIVE DAYS", True, BLACK), (col1_x, 225))

                    # --- COLUMN 2: THE CURATOR'S EYE (X = 360) ---
                    col2_x = 380
                    screen.blit(micro_font.render(
                        "MOST COLLECTED ARTIST", True, GRAY), (col2_x, 60))
                    screen.blit(title_font.render(
                        archive_data['top_artist'], True, BLACK), (col2_x, 75))

                    screen.blit(micro_font.render(
                        "COSMIC ANOMALIES", True, GRAY), (col2_x, 130))
                    screen.blit(title_font.render(
                        f"{int(anim_archive['swirls'])} SWIRLS FOUND", True, BLACK), (col2_x, 145))

                    screen.blit(micro_font.render(
                        "DOCUMENTATION RATE", True, GRAY), (col2_x, 210))
                    screen.blit(title_font.render(
                        f"{anim_archive['doc_rate']:.1f}% OF BINDER", True, BLACK), (col2_x, 225))

                    # --- COLUMN 3: SENTIMENT & STORIES (X = 680) ---
                    col3_x = 700
                    screen.blit(micro_font.render(
                        "LONGEST NOTE", True, GRAY), (col3_x, 60))

                    # --- NEW: Split into two lines ---
                    screen.blit(title_font.render(
                        archive_data['longest_note_pkmn'], True, BLACK), (col3_x, 75))
                    screen.blit(micro_font.render(
                        f"({int(anim_archive['manifesto_words'])} WORDS)", True, BLACK), (col3_x, 95))

                    screen.blit(micro_font.render(
                        "CURATOR'S LOG", True, GRAY), (col3_x, 130))
                    draw_wrapped_text(
                        screen, f"{int(anim_archive['words']):,} TOTAL WORDS", title_font, BLACK, col3_x, 145, max_width=240)

            # --- BOTTOM CORNER NAVIGATION ---
            nav_y = SCREEN_HEIGHT - 24
            if stats_page > 1:
                screen.blit(micro_font.render(
                    "[<-] BACK", True, BLACK), (16, nav_y))
            else:
                screen.blit(micro_font.render(
                    "[ESC] MAIN MENU", True, GRAY), (16, nav_y))

            if stats_page <= 5:
                if stats_page == 1:
                    next_str = "NEXT: ARCHETYPES [->]"
                elif stats_page == 2:
                    next_str = "NEXT: SOURCING [->]"
                elif stats_page == 3:
                    next_str = "NEXT: LINEAGE [->]"
                elif stats_page == 4:
                    next_str = "NEXT: ARCHIVE [->]"
                else:
                    next_str = "END OF STATS"

                next_text = micro_font.render(next_str, True, BLACK)
                screen.blit(next_text, (SCREEN_WIDTH -
                            next_text.get_width() - 16, nav_y))

        # --- NEW: DRAW SELECTION ARROW ---
            if 1 <= stats_page <= 5:
                if selected_stat_index == -1:
                    # Point to the Mode Toggle in the top right
                    mode_str = f"MODE: {current_mode}"
                    target_x = SCREEN_WIDTH - \
                        header_font.size(mode_str)[0] - 16
                    target_y = 16
                else:
                    # Point to a standard grid stat
                    positions = PAGE_STATS_POSITIONS.get(stats_page, [])
                    if positions and selected_stat_index < len(positions):
                        target_x, target_y = positions[selected_stat_index]
                    else:
                        target_x, target_y = -100, -100  # Hide if invalid

                # Draw the arrow
                point_x = target_x - 20
                point_y = target_y + 1
                pygame.draw.polygon(screen, BLACK, [
                    (point_x, point_y),
                    (point_x, point_y + 14),
                    (point_x + 12, point_y + 7)
                ])

            # --- BOTTOM CORNER NAVIGATION ---
            # (Your existing bottom corner navigation code should be right below this)
            nav_y = SCREEN_HEIGHT - 24

            # --- NEW: STAT DETAIL MODAL OVERLAY ---
            if show_stat_modal:
                # 1. Dim the background UI
                overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
                overlay.set_alpha(180)  # 0-255 opacity
                overlay.fill(BLACK)
                screen.blit(overlay, (0, 0))

                # 2. Dimensions (Slightly smaller than the screen)
                modal_w = 860
                modal_h = 260
                modal_x = (SCREEN_WIDTH - modal_w) // 2
                modal_y = (SCREEN_HEIGHT - modal_h) // 2

                # 3. The Negative Space Shadow (Pure White Halo)
                pygame.draw.rect(screen, WHITE, (modal_x - 6,
                                 modal_y - 6, modal_w + 12, modal_h + 12))

                # 4. Main Modal Background
                pygame.draw.rect(
                    screen, WHITE, (modal_x, modal_y, modal_w, modal_h))

                # 5. Outer Black Border
                pygame.draw.rect(
                    screen, BLACK, (modal_x, modal_y, modal_w, modal_h), 4)

                # 6. Inner Black Border
                pygame.draw.rect(screen, BLACK, (modal_x + 6,
                                 modal_y + 6, modal_w - 12, modal_h - 12), 1)

                # 7. Get the correct title based on what they clicked
                page_titles = STAT_TITLES.get(stats_page, [])
                display_title = page_titles[selected_stat_index] if selected_stat_index < len(
                    page_titles) else "STAT DETAIL"

                # Dynamic overrides for the Ledgers
                if stats_page == 3 and selected_stat_index == 4 and modal_data and not modal_data.get("error"):
                    s_name = modal_data.get("seller_name", "UNKNOWN").upper()
                    display_title = f"MOST TRANSACTIONS WITH {s_name}"
                elif stats_page == 3 and selected_stat_index == 5 and modal_data and not modal_data.get("error"):
                    s_name = modal_data.get("seller_name", "UNKNOWN").upper()
                    display_title = f"MOST FUNDING FOR {s_name}"

                # 8. Render Header
                screen.blit(header_font.render(
                    f"{display_title}", True, BLACK), (modal_x + 24, modal_y + 24))
                pygame.draw.line(screen, BLACK, (modal_x + 16, modal_y + 50),
                                 (modal_x + modal_w - 16, modal_y + 50), 2)

                # 9. Render Body Content
                # Index 0 = TOTAL SPEND, Index 3 = TOTAL SOLD, Index 5 = TRADES/GIFTS
                if stats_page == 1 and selected_stat_index in [0, 3, 5]:
                    if selected_stat_index == 0:
                        tx_type = "spend"
                    elif selected_stat_index == 3:
                        tx_type = "sold"
                    else:
                        tx_type = "zero_cost"

                    # Lazy load the data
                    if modal_data is None:
                        screen.blit(title_font.render(
                            "FETCHING TRANSACTIONS...", True, GRAY), (modal_x + 24, modal_y + 80))
                        pygame.display.flip()
                        modal_data = api_client.fetch_transactions(
                            binder_id, tx_type, mode=current_mode)
                        if modal_data is None:
                            modal_data = []

                    if not modal_data:
                        # Empty State
                        no_data_surf = micro_font.render(
                            "No Data Available", True, GRAY)
                        screen.blit(no_data_surf, (modal_x + (modal_w - no_data_surf.get_width()
                                                              ) // 2, modal_y + (modal_h - no_data_surf.get_height()) // 2))
                    else:
                        # List Configuration
                        list_y_start = modal_y + 60
                        list_h = modal_h - 106
                        row_h = 22
                        visible_rows = list_h // row_h
                        total_rows = len(modal_data)

                        max_offset = max(0, total_rows - visible_rows)
                        if modal_scroll_offset > max_offset:
                            modal_scroll_offset = max_offset

                        # Draw Column Headers
                        screen.blit(micro_font.render(
                            "DATE", True, GRAY), (modal_x + 24, list_y_start))
                        screen.blit(micro_font.render(
                            "ASSET", True, GRAY), (modal_x + 200, list_y_start))

                        # Split header logic based on the view
                        if selected_stat_index == 5:  # Trades/Gifts
                            screen.blit(micro_font.render(
                                "COUNTERPARTY", True, GRAY), (modal_x + 460, list_y_start))
                        else:  # Total Spend / Total Sold
                            screen.blit(micro_font.render(
                                "PLATFORM", True, GRAY), (modal_x + 460, list_y_start))
                            screen.blit(micro_font.render(
                                "AMOUNT", True, GRAY), (modal_x + 740, list_y_start))

                        pygame.draw.line(screen, GRAY, (modal_x + 16, list_y_start + 14),
                                         (modal_x + modal_w - 30, list_y_start + 14), 1)

                        clip_rect = pygame.Rect(
                            modal_x + 16, list_y_start + 16, modal_w - 30, list_h)
                        screen.set_clip(clip_rect)

                        draw_y = list_y_start + 20
                        for i in range(modal_scroll_offset, min(total_rows, modal_scroll_offset + visible_rows + 1)):
                            row = modal_data[i]

                            # Shared Date and Asset Name (Short date format)
                            date_str = format_date_short(row.get('event_date'))
                            name = str(row.get('printed_name')
                                       or "Unknown")[:30]

                            screen.blit(title_font.render(
                                date_str, True, BLACK), (modal_x + 24, draw_y))
                            screen.blit(title_font.render(
                                name, True, BLACK), (modal_x + 200, draw_y))

                            # Split data rendering based on the view
                            if selected_stat_index == 5:  # Trades/Gifts
                                c_party = str(
                                    row.get('counterparty') or "Unknown")[:25]
                                screen.blit(title_font.render(
                                    c_party, True, BLACK), (modal_x + 460, draw_y))
                            else:  # Total Spend / Total Sold
                                plat = str(row.get('platform')
                                           or "Unknown")[:15]
                                raw_amt = float(row.get('item_amount', 0))
                                amt = f"${raw_amt:,.2f}"

                                screen.blit(title_font.render(
                                    plat, True, BLACK), (modal_x + 460, draw_y))
                                screen.blit(title_font.render(
                                    amt, True, BLACK), (modal_x + 740, draw_y))

                            draw_y += row_h

                        screen.set_clip(None)

                        # Draw Dynamic Scrollbar
                        track_x = modal_x + modal_w - 20
                        track_y = list_y_start + 16
                        track_h = list_h

                        pygame.draw.rect(
                            screen, GRAY, (track_x, track_y, 4, track_h))

                        if total_rows > visible_rows:
                            thumb_h = max(
                                20, int(track_h * (visible_rows / total_rows)))
                            thumb_y = track_y + \
                                ((modal_scroll_offset / max_offset)
                                 * (track_h - thumb_h))
                            pygame.draw.rect(
                                screen, BLACK, (track_x - 2, thumb_y, 8, thumb_h))
                        else:
                            pygame.draw.rect(
                                screen, BLACK, (track_x - 2, track_y, 8, track_h))
                # --- NEW: COST PER CARD DEEP DIVE ---
                elif stats_page == 1 and selected_stat_index == 1:
                    # Lazy load data
                    if modal_data is None:
                        screen.blit(title_font.render(
                            "CALCULATING EFFICIENCY...", True, GRAY), (modal_x + 24, modal_y + 80))
                        pygame.display.flip()
                        modal_data = api_client.fetch_cost_deepdive(
                            binder_id, mode=current_mode)
                        if modal_data is None:
                            modal_data = {"error": True}

                    if modal_data.get("error"):
                        screen.blit(micro_font.render(
                            "NO DATA AVAILABLE", True, GRAY), (modal_x + 24, modal_y + 80))
                    else:
                        # 1. The Restatement (Massive Font)
                        screen.blit(micro_font.render(
                            "CURRENT TRUE AVERAGE", True, GRAY), (modal_x + 24, modal_y + 80))
                        screen.blit(boot_font.render(
                            f"${modal_data['true_average']:,.2f}", True, BLACK), (modal_x + 24, modal_y + 100))

                        # 2. The Math Breakdown
                        math_x = modal_x + 350
                        screen.blit(micro_font.render(
                            "THE MATH", True, GRAY), (math_x, modal_y + 80))

                        math_str = f"${modal_data['total_spent']:,.2f}/{modal_data['paid_assets']} CARDS"
                        screen.blit(title_font.render(
                            math_str, True, BLACK), (math_x, modal_y + 95))

                        # 3. Paid vs Free Split
                        screen.blit(micro_font.render(
                            "ACQUISITION SPLIT", True, GRAY), (math_x, modal_y + 135))

                        paid_str = f"PAID: {modal_data['paid_assets']} CARDS"
                        free_str = f"FREE: {modal_data['free_assets']} CARDS (GIFTS/TRADES)"

                        screen.blit(title_font.render(
                            paid_str, True, BLACK), (math_x, modal_y + 150))
                        screen.blit(title_font.render(
                            free_str, True, BLACK), (math_x, modal_y + 170))

                        # 4. Highlight raw impact
                        impact_str = f"*Raw Average (Including Free Assets): ${modal_data['raw_average']:,.2f}"
                        screen.blit(micro_font.render(
                            impact_str, True, GRAY), (math_x, modal_y + 195))

                # --- NEW: LOGISTICS OVERHEAD DEEP DIVE ---
                elif stats_page == 1 and selected_stat_index == 2:
                    # Lazy load data
                    if modal_data is None:
                        screen.blit(title_font.render(
                            "ANALYZING LEAKAGE...", True, GRAY), (modal_x + 24, modal_y + 80))
                        pygame.display.flip()
                        modal_data = api_client.fetch_overhead_deepdive(
                            binder_id, mode=current_mode)
                        if modal_data is None:
                            modal_data = {"error": True}

                    if modal_data.get("error"):
                        screen.blit(micro_font.render(
                            "NO DATA AVAILABLE", True, GRAY), (modal_x + 24, modal_y + 80))
                    else:
                        # 1. Total Overhead (Massive Font)
                        screen.blit(micro_font.render(
                            "TOTAL DEAD MONEY", True, GRAY), (modal_x + 24, modal_y + 80))
                        screen.blit(boot_font.render(
                            f"${modal_data['total_overhead']:,.2f}", True, BLACK), (modal_x + 24, modal_y + 100))

                        # 2. Tax vs. Postage Split
                        split_str = f"POSTAGE: {modal_data['shipping_pct']:.0f}% TAX: {modal_data['tax_pct']:.0f}%"
                        screen.blit(micro_font.render(
                            "OVERHEAD SPLIT", True, GRAY), (modal_x + 24, modal_y + 160))
                        screen.blit(title_font.render(
                            split_str, True, BLACK), (modal_x + 24, modal_y + 175))

                        # 3. Per-Asset Leakage
                        screen.blit(micro_font.render(
                            "FRICTION COST PER ASSET", True, GRAY), (modal_x + 24, modal_y + 205))
                        screen.blit(title_font.render(
                            f"+${modal_data['per_asset_leakage']:.2f} PER CARD", True, BLACK), (modal_x + 24, modal_y + 220))

                        # 4. Platform Efficiency Ranking
                        rank_x = modal_x + 390
                        screen.blit(micro_font.render(
                            "LOWEST OVERHEAD", True, GRAY), (rank_x, modal_y + 80))

                        rank_y = modal_y + 105
                        platforms = modal_data.get('platform_ranking', [])

                        if not platforms:
                            screen.blit(title_font.render(
                                "NO PLATFORM DATA FOUND.", True, GRAY), (rank_x, rank_y))
                        else:
                            # Show up to 5 platforms
                            for i, plat in enumerate(platforms[:5]):
                                rank_str = f"{i+1}."
                                name_str = f"{plat['name']}"

                                # Format nicely: 1. EBAY ........... 12.5% ($45.00)
                                val_str = f"{plat['overhead_pct']:.1f}% (${plat['overhead_amt']:,.2f})"

                                screen.blit(title_font.render(
                                    rank_str, True, GRAY), (rank_x, rank_y))
                                screen.blit(title_font.render(
                                    name_str, True, BLACK), (rank_x + 30, rank_y))
                                screen.blit(title_font.render(
                                    val_str, True, BLACK), (rank_x + 220, rank_y))

                                rank_y += 24

                # --- NEW: FORECASTED COMPLETION DEEP DIVE ---
                elif stats_page == 1 and selected_stat_index == 4:
                    # Lazy load data
                    if modal_data is None:
                        screen.blit(title_font.render(
                            "CALCULATING TRAJECTORY...", True, GRAY), (modal_x + 24, modal_y + 80))
                        pygame.display.flip()
                        modal_data = api_client.fetch_forecast_deepdive(
                            binder_id, mode=current_mode)
                        if modal_data is None:
                            modal_data = {"error": True}

                    if modal_data.get("error"):
                        screen.blit(micro_font.render(
                            "NO DATA AVAILABLE", True, GRAY), (modal_x + 24, modal_y + 80))
                    else:
                        # 1. Burn Rate (Massive Font)
                        screen.blit(micro_font.render(
                            "MONTHLY BURN RATE (90D AVG)", True, GRAY), (modal_x + 24, modal_y + 80))
                        screen.blit(boot_font.render(
                            f"${modal_data['burn_rate_monthly']:,.2f}", True, BLACK), (modal_x + 24, modal_y + 100))

                        # 2. Velocity Shifts
                        shift_x = modal_x + 390
                        screen.blit(micro_font.render(
                            "VELOCITY SHIFT", True, GRAY), (shift_x, modal_y + 80))

                        shift_str = f"{modal_data['shift_dir']} {modal_data['shift_pct']:.0f}% {modal_data['shift_word']} VS 90-DAY AVG"
                        screen.blit(title_font.render(
                            shift_str, True, BLACK), (shift_x, modal_y + 95))

                        detail_str = f"({modal_data['count_30d']} CARDS THIS MONTH VS {modal_data['velocity_90d_avg']:.1f} AVG)"
                        screen.blit(micro_font.render(
                            detail_str, True, GRAY), (shift_x, modal_y + 115))

                        # 3. Estimated Milestone
                        screen.blit(micro_font.render(
                            "PROJECTED 100% COMPLETION", True, GRAY), (shift_x, modal_y + 160))

                        if modal_data['cards_left'] > 0:
                            target_str = f"{modal_data['eta_str']}"
                        else:
                            target_str = "BINDER IS 100% COMPLETE"

                        screen.blit(title_font.render(
                            target_str, True, BLACK), (shift_x, modal_y + 175))

                        # Subtext for targets
                        if modal_data['cards_left'] > 0:
                            screen.blit(micro_font.render(
                                f"BASED ON {modal_data['cards_left']} REMAINING TARGETS", True, GRAY), (shift_x, modal_y + 195))

                # --- NEW: NET SPEND / HUSTLE PORTFOLIO ---
                elif stats_page == 1 and selected_stat_index == 6:
                    # Lazy load data
                    if modal_data is None:
                        screen.blit(title_font.render(
                            "CALCULATING ROI...", True, GRAY), (modal_x + 24, modal_y + 80))
                        pygame.display.flip()
                        modal_data = api_client.fetch_netspend_deepdive(
                            binder_id, mode=current_mode)
                        if modal_data is None:
                            modal_data = {"error": True}

                    if modal_data.get("error"):
                        screen.blit(micro_font.render(
                            "NO DATA AVAILABLE", True, GRAY), (modal_x + 24, modal_y + 80))
                    else:
                        # 1. Net Spend (Massive Font - Left Side)
                        screen.blit(micro_font.render(
                            "OVERALL NET SPEND", True, GRAY), (modal_x + 24, modal_y + 80))

                        # Grab the eased net spend value we already calculated for the main page
                        net = anim_vitals.get('net', 0)
                        net_str = f"-${abs(net):,.2f}" if net < 0 else f"${net:,.2f}"
                        screen.blit(boot_font.render(net_str, True,
                                    BLACK), (modal_x + 24, modal_y + 100))

                        # Subsidized Assets (Moved underneath)
                        screen.blit(micro_font.render(
                            "SUBSIDIZED ASSETS (FREE CARDS)", True, GRAY), (modal_x + 24, modal_y + 160))
                        screen.blit(title_font.render(
                            f"{modal_data['subsidized_cards']:.1f} CARDS", True, BLACK), (modal_x + 24, modal_y + 175))

                        # 2. Arbitrage ROI (Massive Font - Right Side)
                        roi_x = modal_x + 390
                        screen.blit(micro_font.render(
                            "ARBITRAGE ROI", True, GRAY), (roi_x, modal_y + 80))

                        roi_pct = modal_data['roi_pct']
                        roi_str = f"+{roi_pct:.1f}%" if roi_pct > 0 else f"{roi_pct:.1f}%"
                        screen.blit(boot_font.render(roi_str, True,
                                    BLACK), (roi_x, modal_y + 100))

                        # Total Flip Revenue underneath
                        screen.blit(micro_font.render(
                            "TOTAL FLIP REVENUE", True, GRAY), (roi_x, modal_y + 160))
                        screen.blit(title_font.render(
                            f"${modal_data['total_revenue']:,.2f}", True, BLACK), (roi_x, modal_y + 175))

                # --- NEW: REMAINING TARGETS LIST ---
                elif stats_page == 1 and selected_stat_index == 7:
                    # Lazy load the data
                    if modal_data is None:
                        screen.blit(title_font.render(
                            "FETCHING TARGETS...", True, GRAY), (modal_x + 24, modal_y + 80))
                        pygame.display.flip()
                        modal_data = api_client.fetch_missing_targets(
                            binder_id, mode=current_mode)
                        if modal_data is None:
                            modal_data = []

                    if not modal_data:
                        no_data_surf = micro_font.render(
                            "NO TARGETS REMAINING!", True, GRAY)
                        screen.blit(no_data_surf, (modal_x + (modal_w - no_data_surf.get_width()
                                                              ) // 2, modal_y + (modal_h - no_data_surf.get_height()) // 2))
                    else:
                        # List Configuration
                        list_y_start = modal_y + 60
                        list_h = modal_h - 106
                        row_h = 22
                        visible_rows = list_h // row_h
                        total_rows = len(modal_data)

                        max_offset = max(0, total_rows - visible_rows)
                        if modal_scroll_offset > max_offset:
                            modal_scroll_offset = max_offset

                        # Draw Column Headers
                        screen.blit(micro_font.render(
                            "DEX NO.", True, GRAY), (modal_x + 24, list_y_start))
                        screen.blit(micro_font.render(
                            "POKEMON", True, GRAY), (modal_x + 200, list_y_start))
                        screen.blit(micro_font.render(
                            "PRIMARY TYPE", True, GRAY), (modal_x + 460, list_y_start))

                        pygame.draw.line(screen, GRAY, (modal_x + 16, list_y_start + 14),
                                         (modal_x + modal_w - 30, list_y_start + 14), 1)

                        clip_rect = pygame.Rect(
                            modal_x + 16, list_y_start + 16, modal_w - 30, list_h)
                        screen.set_clip(clip_rect)

                        draw_y = list_y_start + 20
                        for i in range(modal_scroll_offset, min(total_rows, modal_scroll_offset + visible_rows + 1)):
                            row = modal_data[i]

                            dex_str = f"#{row['pokedex_number']:03d}"
                            name = str(row['pokemon_name']).upper()
                            ptype = str(
                                row.get('primary_type', 'UNKNOWN')).upper()

                            screen.blit(title_font.render(
                                dex_str, True, BLACK), (modal_x + 24, draw_y))
                            screen.blit(title_font.render(
                                name, True, BLACK), (modal_x + 200, draw_y))
                            screen.blit(title_font.render(
                                ptype, True, BLACK), (modal_x + 460, draw_y))

                            draw_y += row_h

                        screen.set_clip(None)

                        # Draw Dynamic Scrollbar
                        track_x = modal_x + modal_w - 20
                        track_y = list_y_start + 16
                        track_h = list_h

                        pygame.draw.rect(
                            screen, GRAY, (track_x, track_y, 4, track_h))

                        if total_rows > visible_rows:
                            thumb_h = max(
                                20, int(track_h * (visible_rows / total_rows)))
                            thumb_y = track_y + \
                                ((modal_scroll_offset / max_offset)
                                 * (track_h - thumb_h))
                            pygame.draw.rect(
                                screen, BLACK, (track_x - 2, thumb_y, 8, thumb_h))
                        else:
                            pygame.draw.rect(
                                screen, BLACK, (track_x - 2, track_y, 8, track_h))

                    # --- NEW: COLLECTOR STATUS DEEP DIVE ---
                elif stats_page == 1 and selected_stat_index == 8:
                    lbl = vitals_data.get('collector_status', 'UNKNOWN')

                    # Reverse engineer the explanation from the api.py logic
                    if lbl in ["OBSESSED", "ALMOST THERE", "CLOSING IN"]:
                        exp = "Your collection is over 70% complete. Your status is currently driven by your proximity to 100% completion rather than cost efficiency."
                    elif lbl in ["FINANCIALLY RECKLESS", "TILT BUYING", "OVERPAYING FOR CONVENIENCE", "IMPULSIVE BUYER"]:
                        exp = "Your average cost per card is over 20% higher than the portfolio's median cost. Your status is driven by a willingness to pay premiums or impulsive momentum."
                    elif lbl in ["MARKET ASSASSIN", "EFFICIENT HUNTER", "SPREADSHEET WARRIOR", "PATIENT SNIPER"]:
                        exp = "Your average cost per card is well below the mathematical median. Your status reflects highly disciplined, value-focused sourcing."
                    elif lbl in ["ON A MISSION", "DIALED IN"]:
                        exp = "You have high 30-day velocity (8+ recent acquisitions) while still building the bulk of your binder. You are heavily driven by current momentum."
                    elif lbl in ["COLLECTION ABANDONED", "CASUALLY COLLECTING"]:
                        exp = "You have little to no recent acquisitions in the last 30 days. Your status is driven by collection inactivity."
                    else:
                        exp = "You are currently building your collection at a standard pace without extreme efficiency or momentum biases."

                    screen.blit(micro_font.render(
                        "BEHAVIORAL CLASSIFICATION", True, GRAY), (modal_x + 24, modal_y + 80))
                    screen.blit(boot_font.render(lbl, True, BLACK),
                                (modal_x + 24, modal_y + 100))
                    draw_wrapped_text(
                        screen, exp, title_font, BLACK, modal_x + 24, modal_y + 140, max_width=800)

                # ---------------------------------------------------------
                # PAGE 2 MODALS: THE COLLECTOR DNA
                # ---------------------------------------------------------

                # --- NEW: RARITY SKEW (Simple Screen) ---
                elif stats_page == 2 and selected_stat_index == 0:
                    lbl = arch_data.get('rarity_label', 'BALANCED COLLECTOR')
                    if lbl in ["HOLO ADDICT", "MAGPIE SYNDROME"]:
                        exp = "Your collection consists of over 60% Holo or Reverse-Holo finishes, indicating a strong bias toward premium prints."
                    elif lbl in ["AVOIDING EXPENSIVE CARDS", "MATTE FINISH MINIMALIST"]:
                        exp = "Your collection consists of over 75% Non-Holo finishes, indicating you prioritize volume or bulk over shiny premiums."
                    else:
                        exp = "You maintain a balanced distribution of finishes without an extreme mathematical skew toward holos or bulk."

                    screen.blit(micro_font.render(
                        "BEHAVIORAL CLASSIFICATION", True, GRAY), (modal_x + 24, modal_y + 80))
                    screen.blit(boot_font.render(lbl, True, BLACK),
                                (modal_x + 24, modal_y + 100))
                    draw_wrapped_text(
                        screen, exp, title_font, BLACK, modal_x + 24, modal_y + 140, max_width=800)

                # --- NEW: HOLO VS NON-HOLO ---
                elif stats_page == 2 and selected_stat_index == 1:
                    if modal_data is None:
                        screen.blit(title_font.render(
                            "CALCULATING FINISH RATIOS...", True, GRAY), (modal_x + 24, modal_y + 80))
                        pygame.display.flip()
                        modal_data = api_client.fetch_holo_deepdive(binder_id, mode=current_mode) or {
                            "error": True}

                    if modal_data.get("error"):
                        screen.blit(micro_font.render(
                            "NO DATA AVAILABLE", True, GRAY), (modal_x + 24, modal_y + 80))
                    else:
                        # Column 1: Averages
                        col1_x = modal_x + 24

                        screen.blit(micro_font.render(
                            "AVG HOLO COST", True, GRAY), (col1_x, modal_y + 80))
                        screen.blit(header_font.render(
                            f"${modal_data['holo_avg']:,.2f}", True, BLACK), (col1_x, modal_y + 95))

                        screen.blit(micro_font.render(
                            "AVG NON-HOLO COST", True, GRAY), (col1_x, modal_y + 140))
                        screen.blit(header_font.render(
                            f"${modal_data['non_avg']:,.2f}", True, BLACK), (col1_x, modal_y + 155))

                        prem_diff = modal_data['holo_avg'] - \
                            modal_data['non_avg']
                        screen.blit(micro_font.render(
                            "HOLO PREMIUM", True, GRAY), (col1_x, modal_y + 200))
                        screen.blit(header_font.render(
                            f"+${prem_diff:,.2f}", True, BLACK), (col1_x, modal_y + 215))

                        # Column 2: Spend Allocation
                        col2_x = modal_x + 320

                        screen.blit(micro_font.render(
                            "TOTAL HOLO SPEND", True, GRAY), (col2_x, modal_y + 80))
                        screen.blit(header_font.render(
                            f"${modal_data['holo_spend']:,.2f}", True, BLACK), (col2_x, modal_y + 95))

                        screen.blit(micro_font.render(
                            "TOTAL NON-HOLO SPEND", True, GRAY), (col2_x, modal_y + 140))
                        screen.blit(header_font.render(
                            f"${modal_data['non_spend']:,.2f}", True, BLACK), (col2_x, modal_y + 155))

                        # Column 3: Completion
                        col3_x = modal_x + 600

                        screen.blit(micro_font.render(
                            "HOLO COMPLETION", True, GRAY), (col3_x, modal_y + 80))
                        screen.blit(header_font.render(
                            f"{modal_data['holo_collected']} / {modal_data['holo_total']}", True, BLACK), (col3_x, modal_y + 95))

                        screen.blit(micro_font.render(
                            "NON-HOLO COMPLETION", True, GRAY), (col3_x, modal_y + 140))
                        screen.blit(header_font.render(
                            f"{modal_data['non_collected']} / {modal_data['non_total']}", True, BLACK), (col3_x, modal_y + 155))

                # --- NEW: CONDITION ARCHETYPE (Simple Screen) ---
                elif stats_page == 2 and selected_stat_index == 2:
                    lbl = arch_data.get('condition_label', 'PRAGMATIC TRAINER')
                    if lbl in ["CONDITION SNOB (NM/M)", "LOUPE INSPECTOR"]:
                        exp = "Your assets have an average condition score of 8.0 (Near Mint) or higher. You clearly prioritize high-end quality over filling binder slots."
                    elif lbl in ["BINDER FILLER (LP/MP)", "WASHING MACHINE SURVIVOR"]:
                        exp = "Your assets have an average condition score of 5.0 (Moderately Played) or lower. You are optimizing for price and completion over condition."
                    else:
                        exp = "Your assets average around Lightly Played (LP). You balance acceptable condition with cost-effective purchasing."

                    screen.blit(micro_font.render("QUALITY ASSURANCE",
                                True, GRAY), (modal_x + 24, modal_y + 80))
                    screen.blit(boot_font.render(lbl, True, BLACK),
                                (modal_x + 24, modal_y + 100))
                    draw_wrapped_text(
                        screen, exp, title_font, BLACK, modal_x + 24, modal_y + 140, max_width=800)

                # --- NEW: MOST EXPENSIVE HIT ---
                elif stats_page == 2 and selected_stat_index == 3:
                    if modal_data is None:
                        screen.blit(title_font.render(
                            "CALCULATING GRAIL METRICS...", True, GRAY), (modal_x + 24, modal_y + 80))
                        pygame.display.flip()
                        modal_data = api_client.fetch_extremes_deepdive(binder_id, mode=current_mode) or {
                            "error": True}

                    if modal_data.get("error") or not modal_data.get("most_expensive"):
                        screen.blit(micro_font.render(
                            "NO DATA AVAILABLE", True, GRAY), (modal_x + 24, modal_y + 80))
                    else:
                        exp_item = modal_data['most_expensive']

                        # Left: Dominance & Premium
                        screen.blit(micro_font.render(
                            "PORTFOLIO DOMINANCE", True, GRAY), (modal_x + 24, modal_y + 80))
                        dom_pct = (float(
                            exp_item['item_amount']) / modal_data['total_spend'] * 100) if modal_data['total_spend'] > 0 else 0
                        screen.blit(boot_font.render(
                            f"{dom_pct:.1f}%", True, BLACK), (modal_x + 24, modal_y + 100))
                        screen.blit(micro_font.render(
                            "OF YOUR ENTIRE BINDER SPEND IS", True, GRAY), (modal_x + 24, modal_y + 140))
                        screen.blit(micro_font.render(
                            "TIED UP IN THIS SINGLE CARD.", True, GRAY), (modal_x + 24, modal_y + 155))

                        prem = float(exp_item['item_amount']) - \
                            modal_data['true_average']
                        screen.blit(title_font.render(
                            f"NM PREMIUM: +${prem:,.2f}", True, BLACK), (modal_x + 24, modal_y + 180))
                        screen.blit(micro_font.render(
                            "(VS TRUE AVERAGE)", True, GRAY), (modal_x + 24, modal_y + 200))

                        # Right: Acquisition Story
                        r_x = modal_x + 390
                        screen.blit(micro_font.render(
                            "THE ACQUISITION STORY", True, GRAY), (r_x, modal_y + 80))
                        screen.blit(title_font.render(
                            exp_item['printed_name'].upper(), True, BLACK), (r_x, modal_y + 100))
                        screen.blit(title_font.render(
                            f"COST: ${float(exp_item['item_amount']):,.2f}", True, BLACK), (r_x, modal_y + 120))

                        screen.blit(micro_font.render(
                            f"PLATFORM:     {exp_item['platform']}", True, GRAY), (r_x, modal_y + 160))
                        screen.blit(micro_font.render(
                            f"COUNTERPARTY: {exp_item['counterparty']}", True, GRAY), (r_x, modal_y + 180))
                        date_str = format_date_short(exp_item['event_date'])
                        screen.blit(micro_font.render(
                            f"SECURED ON:   {date_str}", True, GRAY), (r_x, modal_y + 200))

                # --- NEW: ACQUISITION STRATEGY (Simple Screen) ---
                elif stats_page == 2 and selected_stat_index == 4:
                    lbl = arch_data.get('hunter_label', 'STANDARD ENTHUSIAST')
                    if lbl in ["BULK HOARDER", "CARDBOARD RECYCLER"]:
                        exp = "You acquire over 3 cards per event at an average cost below $20. You prefer hunting bulk lots and consolidated collections."
                    elif lbl in ["SNIPER / HUNTER", "BOUNTY HUNTER"]:
                        exp = "You average fewer than 1.5 cards per event at a high cost (over $40). You are highly targeted, picking off expensive singles one by one."
                    else:
                        exp = "Your acquisitions show a standard balance between multi-card lots and targeted single purchases."

                    screen.blit(micro_font.render(
                        "PURCHASING TACTICS", True, GRAY), (modal_x + 24, modal_y + 80))
                    screen.blit(boot_font.render(lbl, True, BLACK),
                                (modal_x + 24, modal_y + 100))
                    draw_wrapped_text(
                        screen, exp, title_font, BLACK, modal_x + 24, modal_y + 140, max_width=800)

                # --- NEW: CHEAPEST PURCHASE ---
                elif stats_page == 2 and selected_stat_index == 5:
                    if modal_data is None:
                        screen.blit(title_font.render(
                            "CALCULATING THE STEAL INDEX...", True, GRAY), (modal_x + 24, modal_y + 80))
                        pygame.display.flip()
                        modal_data = api_client.fetch_extremes_deepdive(binder_id, mode=current_mode) or {
                            "error": True}

                    if modal_data.get("error") or not modal_data.get("cheapest"):
                        screen.blit(micro_font.render(
                            "NO DATA AVAILABLE", True, GRAY), (modal_x + 24, modal_y + 80))
                    else:
                        chp_item = modal_data['cheapest']

                        # Left: Steal Index
                        screen.blit(micro_font.render(
                            "THE STEAL INDEX", True, GRAY), (modal_x + 24, modal_y + 80))

                        # Calculate how much cheaper it is compared to the True Average
                        steal_diff = modal_data['true_average'] - \
                            float(chp_item['item_amount'])
                        steal_pct = (
                            steal_diff / modal_data['true_average'] * 100) if modal_data['true_average'] > 0 else 0

                        screen.blit(boot_font.render(
                            f"-{steal_pct:.1f}%", True, BLACK), (modal_x + 24, modal_y + 100))
                        screen.blit(micro_font.render(
                            "CHEAPER THAN YOUR PORTFOLIO'S", True, GRAY), (modal_x + 24, modal_y + 140))
                        screen.blit(micro_font.render(
                            "TRUE AVERAGE COST PER CARD.", True, GRAY), (modal_x + 24, modal_y + 155))

                        screen.blit(title_font.render(
                            f"SAVINGS: ${steal_diff:,.2f}", True, BLACK), (modal_x + 24, modal_y + 180))
                        screen.blit(micro_font.render(
                            "(VS TRUE AVERAGE)", True, GRAY), (modal_x + 24, modal_y + 200))

                        # Right: Acquisition Story
                        r_x = modal_x + 390
                        screen.blit(micro_font.render(
                            "THE ACQUISITION STORY", True, GRAY), (r_x, modal_y + 80))
                        screen.blit(title_font.render(
                            chp_item['printed_name'].upper(), True, BLACK), (r_x, modal_y + 100))
                        screen.blit(title_font.render(
                            f"COST: ${float(chp_item['item_amount']):,.2f}", True, BLACK), (r_x, modal_y + 120))

                        screen.blit(micro_font.render(
                            f"PLATFORM:     {chp_item['platform']}", True, GRAY), (r_x, modal_y + 160))
                        screen.blit(micro_font.render(
                            f"COUNTERPARTY: {chp_item['counterparty']}", True, GRAY), (r_x, modal_y + 180))
                        date_str = format_date_short(chp_item['event_date'])
                        screen.blit(micro_font.render(
                            f"SECURED ON:   {date_str}", True, GRAY), (r_x, modal_y + 200))

                # ---------------------------------------------------------
                # PAGE 3 MODALS: THE SOURCING MAP
                # ---------------------------------------------------------

                # --- NEW: PLATFORM ARCHETYPE (Simple Screen) ---
                elif stats_page == 3 and selected_stat_index == 0:
                    lbl = source_data.get('plat_archetype', 'UNKNOWN')
                    if lbl in ["CORPORATE SPONSOR", "SYNDICATE BUYER", "TRADE CARTEL"]:
                        exp = "Over 80% of your binder's volume was sourced from a single ecosystem. You have consolidated your purchasing power into one dominant lane."
                    elif "LOYALIST" in lbl or "PREFERS" in lbl:
                        exp = "Over 50% of your binder's volume was sourced from a single platform, showing a clear preference for its market dynamics and availability."
                    else:
                        exp = "Your acquisitions are highly diversified. No single platform accounts for more than 50% of your collection, indicating you hunt wherever the deals are."

                    screen.blit(micro_font.render(
                        "BEHAVIORAL CLASSIFICATION", True, GRAY), (modal_x + 24, modal_y + 80))
                    screen.blit(boot_font.render(lbl, True, BLACK),
                                (modal_x + 24, modal_y + 100))
                    draw_wrapped_text(
                        screen, exp, title_font, BLACK, modal_x + 24, modal_y + 140, max_width=800)

                # --- NEW: VOLUME LEADER ---
                elif stats_page == 3 and selected_stat_index == 1:
                    if modal_data is None:
                        screen.blit(title_font.render(
                            "CALCULATING VOLUME...", True, GRAY), (modal_x + 24, modal_y + 80))
                        pygame.display.flip()
                        modal_data = api_client.fetch_sourcing_leaders_deepdive(binder_id, mode=current_mode) or {
                            "error": True}

                    if modal_data.get("error") or not modal_data.get("vol_leader"):
                        screen.blit(micro_font.render(
                            "NO DATA AVAILABLE", True, GRAY), (modal_x + 24, modal_y + 80))
                    else:
                        vl = modal_data['vol_leader']

                        # Left: The Leader & Volume Count
                        screen.blit(micro_font.render(
                            "VOLUME LEADER", True, GRAY), (modal_x + 24, modal_y + 80))
                        screen.blit(boot_font.render(
                            vl['name'].upper(), True, BLACK), (modal_x + 24, modal_y + 100))

                        vol_str = f"{vl['volume']} ASSETS"
                        screen.blit(title_font.render(
                            vol_str, True, BLACK), (modal_x + 24, modal_y + 140))

                        # Right: Portfolio Dominance (Percentage shifted here)
                        r_x = modal_x + 390
                        screen.blit(micro_font.render(
                            "PORTFOLIO DOMINANCE", True, GRAY), (r_x, modal_y + 80))
                        screen.blit(boot_font.render(
                            f"{vl['vol_pct']:.1f}%", True, BLACK), (r_x, modal_y + 100))
                        screen.blit(title_font.render(
                            "OF BINDER VOLUME", True, BLACK), (r_x, modal_y + 140))

                # --- NEW: SPEND LEADER ---
                elif stats_page == 3 and selected_stat_index == 2:
                    if modal_data is None:
                        screen.blit(title_font.render(
                            "CALCULATING SPEND...", True, GRAY), (modal_x + 24, modal_y + 80))
                        pygame.display.flip()
                        modal_data = api_client.fetch_sourcing_leaders_deepdive(binder_id, mode=current_mode) or {
                            "error": True}

                    if modal_data.get("error") or not modal_data.get("spend_leader"):
                        screen.blit(micro_font.render(
                            "NO DATA AVAILABLE", True, GRAY), (modal_x + 24, modal_y + 80))
                    else:
                        sl = modal_data['spend_leader']

                        # Left: The Leader & Total Spend
                        screen.blit(micro_font.render(
                            "SPEND LEADER", True, GRAY), (modal_x + 24, modal_y + 80))
                        screen.blit(boot_font.render(
                            sl['name'].upper(), True, BLACK), (modal_x + 24, modal_y + 100))

                        spend_str = f"${sl['spend']:,.2f}"
                        screen.blit(title_font.render(
                            spend_str, True, BLACK), (modal_x + 24, modal_y + 140))

                        # Right: Avg Cost Per Card
                        r_x = modal_x + 390
                        # Calculate the average cost on the fly
                        sl_avg_cost = sl['spend'] / \
                            sl['volume'] if sl['volume'] > 0 else 0

                        screen.blit(micro_font.render(
                            "AVERAGE COST PER CARD:", True, GRAY), (r_x, modal_y + 80))
                        screen.blit(boot_font.render(
                            f"${sl_avg_cost:,.2f}", True, BLACK), (r_x, modal_y + 100))

                # --- NEW: SOURCING SPREAD (Market Breakdown Table) ---
                elif stats_page == 3 and selected_stat_index == 3:
                    if modal_data is None:
                        screen.blit(title_font.render(
                            "MAPPING ECOSYSTEM...", True, GRAY), (modal_x + 24, modal_y + 80))
                        pygame.display.flip()
                        modal_data = api_client.fetch_sourcing_leaders_deepdive(binder_id, mode=current_mode) or {
                            "error": True}

                    if modal_data.get("error") or not modal_data.get("spread"):
                        screen.blit(micro_font.render(
                            "NO DATA AVAILABLE", True, GRAY), (modal_x + 24, modal_y + 80))
                    else:
                        spread = modal_data['spread']

                        # List Configuration
                        list_y_start = modal_y + 60
                        list_h = modal_h - 106
                        row_h = 22
                        visible_rows = list_h // row_h
                        total_rows = len(spread)

                        max_offset = max(0, total_rows - visible_rows)
                        if modal_scroll_offset > max_offset:
                            modal_scroll_offset = max_offset

                        # Draw Column Headers
                        screen.blit(micro_font.render(
                            "RANK", True, GRAY), (modal_x + 24, list_y_start))
                        screen.blit(micro_font.render(
                            "COUNTERPARTY", True, GRAY), (modal_x + 120, list_y_start))
                        screen.blit(micro_font.render(
                            "TOTAL ASSETS SOURCED", True, GRAY), (modal_x + 560, list_y_start))

                        pygame.draw.line(screen, GRAY, (modal_x + 16, list_y_start + 14),
                                         (modal_x + modal_w - 30, list_y_start + 14), 1)

                        clip_rect = pygame.Rect(
                            modal_x + 16, list_y_start + 16, modal_w - 30, list_h)
                        screen.set_clip(clip_rect)

                        draw_y = list_y_start + 20
                        for i in range(modal_scroll_offset, min(total_rows, modal_scroll_offset + visible_rows + 1)):
                            row = spread[i]

                            rank_str = f"{i+1}"
                            name_str = str(
                                row.get('name', 'UNKNOWN')).upper()[:40]
                            count_str = f"{row.get('count', 0)} CARDS"

                            screen.blit(title_font.render(
                                rank_str, True, BLACK), (modal_x + 24, draw_y))
                            screen.blit(title_font.render(
                                name_str, True, BLACK), (modal_x + 120, draw_y))
                            screen.blit(title_font.render(
                                count_str, True, BLACK), (modal_x + 560, draw_y))

                            draw_y += row_h

                        screen.set_clip(None)

                        # Draw Dynamic Scrollbar
                        track_x = modal_x + modal_w - 20
                        track_y = list_y_start + 16
                        track_h = list_h

                        pygame.draw.rect(
                            screen, GRAY, (track_x, track_y, 4, track_h))

                        if total_rows > visible_rows:
                            thumb_h = max(
                                20, int(track_h * (visible_rows / total_rows)))
                            thumb_y = track_y + \
                                ((modal_scroll_offset / max_offset)
                                 * (track_h - thumb_h))
                            pygame.draw.rect(
                                screen, BLACK, (track_x - 2, thumb_y, 8, thumb_h))
                        else:
                            pygame.draw.rect(
                                screen, BLACK, (track_x - 2, track_y, 8, track_h))

                # --- NEW: MOST TRANSACTIONS WITH [SELLER] (VIP Ledger) ---
                elif stats_page == 3 and selected_stat_index == 4:
                    if modal_data is None:
                        screen.blit(title_font.render(
                            "FETCHING LEDGER...", True, GRAY), (modal_x + 24, modal_y + 80))
                        pygame.display.flip()
                        modal_data = api_client.fetch_top_seller_ledger(binder_id, mode=current_mode) or {
                            "error": True}

                    if modal_data.get("error") or not modal_data.get("transactions"):
                        no_data_surf = micro_font.render(
                            "No Transactions Found", True, GRAY)
                        screen.blit(no_data_surf, (modal_x + (modal_w - no_data_surf.get_width()
                                                              ) // 2, modal_y + (modal_h - no_data_surf.get_height()) // 2))
                    else:
                        tx_list = modal_data['transactions']
                        list_y_start = modal_y + 60
                        list_h = modal_h - 106
                        row_h = 22
                        visible_rows = list_h // row_h
                        total_rows = len(tx_list)

                        max_offset = max(0, total_rows - visible_rows)
                        if modal_scroll_offset > max_offset:
                            modal_scroll_offset = max_offset

                        # Draw Column Headers (Same format as Page 1 Spend/Sold)
                        screen.blit(micro_font.render(
                            "DATE", True, GRAY), (modal_x + 24, list_y_start))
                        screen.blit(micro_font.render(
                            "ASSET", True, GRAY), (modal_x + 200, list_y_start))
                        screen.blit(micro_font.render(
                            "PLATFORM", True, GRAY), (modal_x + 460, list_y_start))
                        screen.blit(micro_font.render(
                            "AMOUNT", True, GRAY), (modal_x + 740, list_y_start))

                        pygame.draw.line(screen, GRAY, (modal_x + 16, list_y_start + 14),
                                         (modal_x + modal_w - 30, list_y_start + 14), 1)

                        clip_rect = pygame.Rect(
                            modal_x + 16, list_y_start + 16, modal_w - 30, list_h)
                        screen.set_clip(clip_rect)

                        draw_y = list_y_start + 20
                        for i in range(modal_scroll_offset, min(total_rows, modal_scroll_offset + visible_rows + 1)):
                            row = tx_list[i]

                            date_str = format_date_short(row.get('event_date'))
                            name = str(row.get('printed_name')
                                       or "Unknown")[:30]
                            plat = str(row.get('platform') or "Unknown")[:15]

                            raw_amt = float(row.get('item_amount', 0))
                            amt = f"${raw_amt:,.2f}"

                            screen.blit(title_font.render(
                                date_str, True, BLACK), (modal_x + 24, draw_y))
                            screen.blit(title_font.render(
                                name, True, BLACK), (modal_x + 200, draw_y))
                            screen.blit(title_font.render(
                                plat, True, BLACK), (modal_x + 460, draw_y))
                            screen.blit(title_font.render(
                                amt, True, BLACK), (modal_x + 740, draw_y))

                            draw_y += row_h

                        screen.set_clip(None)

                        # Draw Dynamic Scrollbar
                        track_x = modal_x + modal_w - 20
                        track_y = list_y_start + 16
                        track_h = list_h

                        pygame.draw.rect(
                            screen, GRAY, (track_x, track_y, 4, track_h))

                        if total_rows > visible_rows:
                            thumb_h = max(
                                20, int(track_h * (visible_rows / total_rows)))
                            thumb_y = track_y + \
                                ((modal_scroll_offset / max_offset)
                                 * (track_h - thumb_h))
                            pygame.draw.rect(
                                screen, BLACK, (track_x - 2, thumb_y, 8, thumb_h))
                        else:
                            pygame.draw.rect(
                                screen, BLACK, (track_x - 2, track_y, 8, track_h))

                # --- NEW: MOST FUNDING FOR [SELLER] (Capital Ledger) ---
                elif stats_page == 3 and selected_stat_index == 5:
                    if modal_data is None:
                        screen.blit(title_font.render(
                            "FETCHING LEDGER...", True, GRAY), (modal_x + 24, modal_y + 80))
                        pygame.display.flip()
                        modal_data = api_client.fetch_top_funded_ledger(binder_id, mode=current_mode) or {
                            "error": True}

                    if modal_data.get("error") or not modal_data.get("transactions"):
                        no_data_surf = micro_font.render(
                            "No Transactions Found", True, GRAY)
                        screen.blit(no_data_surf, (modal_x + (modal_w - no_data_surf.get_width()
                                                              ) // 2, modal_y + (modal_h - no_data_surf.get_height()) // 2))
                    else:
                        tx_list = modal_data['transactions']

                        # Add Share of Wallet to the Top Right of the Modal Header
                        share_str = f"{modal_data.get('share_of_wallet', 0):.1f}% (${modal_data.get('seller_spend', 0):,.2f})"
                        share_surf = title_font.render(share_str, True, BLACK)
                        screen.blit(share_surf, (modal_x + modal_w -
                                    24 - share_surf.get_width(), modal_y + 24))

                        list_y_start = modal_y + 60
                        list_h = modal_h - 106
                        row_h = 22
                        visible_rows = list_h // row_h
                        total_rows = len(tx_list)

                        max_offset = max(0, total_rows - visible_rows)
                        if modal_scroll_offset > max_offset:
                            modal_scroll_offset = max_offset

                        screen.blit(micro_font.render(
                            "DATE", True, GRAY), (modal_x + 24, list_y_start))
                        screen.blit(micro_font.render(
                            "ASSET", True, GRAY), (modal_x + 200, list_y_start))
                        screen.blit(micro_font.render(
                            "PLATFORM", True, GRAY), (modal_x + 460, list_y_start))
                        screen.blit(micro_font.render(
                            "AMOUNT", True, GRAY), (modal_x + 740, list_y_start))

                        pygame.draw.line(screen, GRAY, (modal_x + 16, list_y_start + 14),
                                         (modal_x + modal_w - 30, list_y_start + 14), 1)

                        clip_rect = pygame.Rect(
                            modal_x + 16, list_y_start + 16, modal_w - 30, list_h)
                        screen.set_clip(clip_rect)

                        draw_y = list_y_start + 20
                        for i in range(modal_scroll_offset, min(total_rows, modal_scroll_offset + visible_rows + 1)):
                            row = tx_list[i]

                            date_str = format_date_short(row.get('event_date'))
                            name = str(row.get('printed_name')
                                       or "Unknown")[:30]
                            plat = str(row.get('platform') or "Unknown")[:15]
                            raw_amt = float(row.get('item_amount', 0))
                            amt = f"${raw_amt:,.2f}"

                            screen.blit(title_font.render(
                                date_str, True, BLACK), (modal_x + 24, draw_y))
                            screen.blit(title_font.render(
                                name, True, BLACK), (modal_x + 200, draw_y))
                            screen.blit(title_font.render(
                                plat, True, BLACK), (modal_x + 460, draw_y))
                            screen.blit(title_font.render(
                                amt, True, BLACK), (modal_x + 740, draw_y))

                            draw_y += row_h

                        screen.set_clip(None)

                        track_x = modal_x + modal_w - 20
                        track_y = list_y_start + 16
                        track_h = list_h
                        pygame.draw.rect(
                            screen, GRAY, (track_x, track_y, 4, track_h))
                        if total_rows > visible_rows:
                            thumb_h = max(
                                20, int(track_h * (visible_rows / total_rows)))
                            thumb_y = track_y + \
                                ((modal_scroll_offset / max_offset)
                                 * (track_h - thumb_h))
                            pygame.draw.rect(
                                screen, BLACK, (track_x - 2, thumb_y, 8, thumb_h))
                        else:
                            pygame.draw.rect(
                                screen, BLACK, (track_x - 2, track_y, 8, track_h))

                # --- NEW: MOST ACTIVE ON (Temporal Heatmap) ---
                elif stats_page == 3 and selected_stat_index == 6:
                    if modal_data is None:
                        screen.blit(title_font.render(
                            "MAPPING TEMPORAL DATA...", True, GRAY), (modal_x + 24, modal_y + 80))
                        pygame.display.flip()
                        modal_data = api_client.fetch_sourcing_leaders_deepdive(binder_id, mode=current_mode) or {
                            "error": True}

                    if modal_data.get("error") or not modal_data.get("day_counts"):
                        screen.blit(micro_font.render(
                            "NO DATA AVAILABLE", True, GRAY), (modal_x + 24, modal_y + 80))
                    else:
                        screen.blit(micro_font.render(
                            "PURCHASE FREQUENCY BY DAY OF WEEK", True, GRAY), (modal_x + 24, modal_y + 60))

                        counts = modal_data['day_counts']
                        max_val = max(counts) if counts else 1

                        days = ["S", "M", "T", "W", "T", "F", "S"]

                        # Graph configuration (Centered in the modal, matching Page 4)
                        bar_w = 50
                        spacing = 40
                        total_graph_w = (len(counts) * bar_w) + \
                            ((len(counts) - 1) * spacing)
                        graph_x = modal_x + (modal_w - total_graph_w) // 2
                        graph_y = modal_y + 200  # Base of the bars
                        max_bar_h = 100

                        for i, count in enumerate(counts):
                            # Scale the bar height to a max of 100 pixels
                            bar_h = int((count / max_val) *
                                        max_bar_h) if max_val > 0 else 0
                            curr_x = graph_x + i * (bar_w + spacing)

                            # Draw Bar (grows UP from graph_y)
                            pygame.draw.rect(
                                screen, BLACK, (curr_x, graph_y - bar_h, bar_w, bar_h))

                            # Draw Day Label below the bar, perfectly centered
                            lbl_surf = title_font.render(days[i], True, BLACK)
                            screen.blit(
                                lbl_surf, (curr_x + (bar_w - lbl_surf.get_width()) // 2, graph_y + 10))

                            # Draw Exact Count just above the bar, perfectly centered
                            if count > 0:
                                count_surf = micro_font.render(
                                    str(count), True, GRAY)
                                screen.blit(
                                    count_surf, (curr_x + (bar_w - count_surf.get_width()) // 2, graph_y - bar_h - 15))

                # --- NEW: MEDIAN ASSET COST (Spending Signature) ---
                elif stats_page == 3 and selected_stat_index == 7:
                    if modal_data is None:
                        screen.blit(title_font.render(
                            "ANALYZING SPENDING SIGNATURE...", True, GRAY), (modal_x + 24, modal_y + 80))
                        pygame.display.flip()
                        modal_data = api_client.fetch_sourcing_leaders_deepdive(binder_id, mode=current_mode) or {
                            "error": True}

                    if modal_data.get("error") or not modal_data.get("price_buckets"):
                        screen.blit(micro_font.render(
                            "NO DATA AVAILABLE", True, GRAY), (modal_x + 24, modal_y + 80))
                    else:
                        # Left: Price Bracket Distribution (Text List)
                        screen.blit(micro_font.render(
                            "PRICE BRACKET DISTRIBUTION", True, GRAY), (modal_x + 24, modal_y + 70))

                        buckets = modal_data['price_buckets']
                        bar_y = modal_y + 100

                        for label, count in buckets.items():
                            screen.blit(title_font.render(
                                label, True, BLACK), (modal_x + 24, bar_y))
                            screen.blit(title_font.render(
                                f"{count} CARDS", True, BLACK), (modal_x + 250, bar_y))
                            bar_y += 26

                        # Vertical divider line
                        pygame.draw.line(
                            screen, GRAY, (modal_x + 400, modal_y + 70), (modal_x + 400, modal_y + 230), 2)

                        # Right: The Middle Card
                        mid_x = modal_x + 430
                        screen.blit(micro_font.render(
                            "THE MIDDLE CARD (EXACT MEDIAN)", True, GRAY), (mid_x, modal_y + 70))

                        mid_card = modal_data.get("middle_card")
                        if mid_card:
                            screen.blit(boot_font.render(
                                f"${float(mid_card['item_amount']):,.2f}", True, BLACK), (mid_x, modal_y + 90))
                            screen.blit(title_font.render(
                                mid_card['printed_name'].upper(), True, BLACK), (mid_x, modal_y + 130))
                            date_str = format_date_short(
                                mid_card['event_date'])
                            screen.blit(micro_font.render(
                                f"ACQUIRED: {date_str} VIA {mid_card['platform'].upper()}", True, GRAY), (mid_x, modal_y + 150))

                # --- NEW: TOP 5 INDEX (The Grail Impact) ---
                elif stats_page == 3 and selected_stat_index == 8:
                    if modal_data is None:
                        screen.blit(title_font.render(
                            "FETCHING HEAVY HITTERS...", True, GRAY), (modal_x + 24, modal_y + 80))
                        pygame.display.flip()
                        modal_data = api_client.fetch_sourcing_leaders_deepdive(binder_id, mode=current_mode) or {
                            "error": True}

                    if modal_data.get("error") or not modal_data.get("top_5_assets"):
                        screen.blit(micro_font.render(
                            "NO DATA AVAILABLE", True, GRAY), (modal_x + 24, modal_y + 80))
                    else:
                        top5 = modal_data['top_5_assets']

                        list_y_start = modal_y + 60

                        # Draw Column Headers
                        screen.blit(micro_font.render(
                            "RANK", True, GRAY), (modal_x + 24, list_y_start))
                        screen.blit(micro_font.render(
                            "ASSET", True, GRAY), (modal_x + 120, list_y_start))
                        screen.blit(micro_font.render(
                            "COST", True, GRAY), (modal_x + 560, list_y_start))
                        screen.blit(micro_font.render(
                            "% OF TOTAL", True, GRAY), (modal_x + 740, list_y_start))

                        pygame.draw.line(screen, GRAY, (modal_x + 16, list_y_start + 14),
                                         (modal_x + modal_w - 30, list_y_start + 14), 1)

                        draw_y = list_y_start + 20
                        for i, row in enumerate(top5):
                            rank_str = f"#{i+1}"
                            name_str = str(
                                row.get('printed_name', 'UNKNOWN')).upper()[:40]
                            cost_str = f"${float(row.get('item_amount', 0)):,.2f}"
                            pct_str = f"{row.get('spend_pct', 0):.1f}%"

                            screen.blit(title_font.render(
                                rank_str, True, BLACK), (modal_x + 24, draw_y))
                            screen.blit(title_font.render(
                                name_str, True, BLACK), (modal_x + 120, draw_y))
                            screen.blit(title_font.render(
                                cost_str, True, BLACK), (modal_x + 560, draw_y))
                            screen.blit(title_font.render(
                                pct_str, True, BLACK), (modal_x + 740, draw_y))

                            draw_y += 22

                # ---------------------------------------------------------
                # PAGE 4 MODALS: LINEAGE & LOGIC
                # ---------------------------------------------------------

                # --- NEW: EVOLUTIONARY VIEWS (Indexes 0, 1, 2) ---
                elif stats_page == 4 and selected_stat_index in [0, 1, 2]:
                    if modal_data is None:
                        screen.blit(title_font.render(
                            "MAPPING DNA...", True, GRAY), (modal_x + 24, modal_y + 80))
                        pygame.display.flip()
                        modal_data = api_client.fetch_lineage_deepdive(binder_id, mode=current_mode) or {
                            "error": True}

                    if modal_data.get("error"):
                        screen.blit(micro_font.render(
                            "NO DATA AVAILABLE", True, GRAY), (modal_x + 24, modal_y + 80))
                    else:
                        if selected_stat_index == 0:
                            chain_list = modal_data['completed_chains']
                            title_prefix = "FULLY EVOLVED"
                            sub_text = f"{modal_data['evol_dominance']:.1f}% OF CARDS BELONG TO COMPLETED FAMILIES"
                        elif selected_stat_index == 1:
                            chain_list = modal_data['one_away_chains']
                            title_prefix = "ONE CARD AWAY"
                            sub_text = "CATCH THE SILHOUETTES TO COMPLETE THESE FAMILIES"
                        else:
                            chain_list = modal_data['orphan_chains']
                            title_prefix = "STRANDED ORPHANS"
                            sub_text = f"{modal_data['missing_in_orphans']} ADDITIONS NEEDED FOR TOTAL FAMILY INTEGRATION"

                        total_chains = len(chain_list)

                        if total_chains == 0:
                            no_data_surf = micro_font.render(
                                "NO FAMILIES MEET THIS CRITERIA", True, GRAY)
                            screen.blit(
                                no_data_surf, (modal_x + (modal_w - no_data_surf.get_width()) // 2, modal_y + 120))
                        else:
                            # Infinite Wrap-around pagination!
                            current_idx = modal_scroll_offset % total_chains

                            # Headers
                            screen.blit(micro_font.render(
                                f"{title_prefix} (FAMILY {current_idx + 1} OF {total_chains})", True, GRAY), (modal_x + 24, modal_y + 60))
                            screen.blit(title_font.render(
                                sub_text, True, BLACK), (modal_x + 24, modal_y + 75))

                            # Draw Navigation Arrows on the edges
                            screen.blit(micro_font.render(
                                "<", True, BLACK), (modal_x + 24, modal_y + 150))
                            screen.blit(micro_font.render(
                                ">", True, BLACK), (modal_x + modal_w - 40, modal_y + 150))

                            members = chain_list[current_idx]
                            num_members = len(members)
                            spacing = modal_w / (num_members + 1)

                            for i, mem in enumerate(members):
                                cx = modal_x + spacing * (i + 1)

                                # 1. Draw Sprite or Silhouette
                                sprite = get_pokemon_sprite(
                                    mem['dex'], size=(120, 120))
                                if sprite:
                                    if mem['collected']:
                                        screen.blit(
                                            sprite, (cx - 60, modal_y + 80))
                                    else:
                                        silhouette = get_silhouette(sprite)
                                        screen.blit(
                                            silhouette, (cx - 60, modal_y + 80))

                                # 2. Draw Text (Name and Dex)
                                name_surf = title_font.render(
                                    mem['name'].upper(), True, BLACK)
                                screen.blit(
                                    name_surf, (cx - name_surf.get_width()//2, modal_y + 190))

                                dex_surf = micro_font.render(
                                    f"#{mem['dex']:03d}", True, GRAY)
                                screen.blit(
                                    dex_surf, (cx - dex_surf.get_width()//2, modal_y + 210))

                # --- NEW: SET ARCHETYPE (Simple Screen) ---
                elif stats_page == 4 and selected_stat_index == 3:
                    lbl = lineage_data.get('set_archetype', 'UNKNOWN')
                    if "PURIST" in lbl:
                        exp = "Over 70% of your binder belongs to a single set print run. You are highly loyal to a specific era."
                    elif "LEANING" in lbl:
                        exp = "Over 40% of your binder belongs to a single set, showing a strong but not exclusive preference."
                    else:
                        exp = "Your collection is balanced across multiple sets without a single dominant era."

                    screen.blit(micro_font.render(
                        "BEHAVIORAL CLASSIFICATION", True, GRAY), (modal_x + 24, modal_y + 80))
                    screen.blit(boot_font.render(lbl, True, BLACK),
                                (modal_x + 24, modal_y + 100))
                    draw_wrapped_text(
                        screen, exp, title_font, BLACK, modal_x + 24, modal_y + 140, max_width=800)

                # --- NEW: DNA DISTRIBUTION (Set Breakdown) ---
                elif stats_page == 4 and selected_stat_index == 4:
                    if modal_data is None:
                        screen.blit(title_font.render(
                            "MAPPING DNA...", True, GRAY), (modal_x + 24, modal_y + 80))
                        pygame.display.flip()
                        modal_data = api_client.fetch_lineage_deepdive(binder_id, mode=current_mode) or {
                            "error": True}

                    if modal_data.get("error"):
                        screen.blit(micro_font.render(
                            "NO DATA AVAILABLE", True, GRAY), (modal_x + 24, modal_y + 80))
                    else:
                        # Left: Set List
                        screen.blit(micro_font.render(
                            "SET DISTRIBUTION (BY VOLUME)", True, GRAY), (modal_x + 24, modal_y + 70))

                        sets = modal_data['set_distribution']
                        bar_y = modal_y + 100

                        for s in sets:
                            screen.blit(title_font.render(s['set_name'].upper()[
                                        :15], True, BLACK), (modal_x + 24, bar_y))
                            screen.blit(title_font.render(
                                f"{s['count']} CARDS", True, BLACK), (modal_x + 250, bar_y))
                            bar_y += 26

                        # Right: Set Loyalty
                        right_x = modal_x + 430
                        screen.blit(micro_font.render(
                            "SET LOYALTY", True, GRAY), (right_x, modal_y + 70))

                        top_set = modal_data['top_set']
                        screen.blit(header_font.render(
                            f"{modal_data['top_set_pct']:.1f}% {top_set['set_name'].upper()}", True, BLACK), (right_x, modal_y + 90))

                # --- NEW: ELEMENTAL SKEW ---
                elif stats_page == 4 and selected_stat_index == 5:
                    if modal_data is None:
                        screen.blit(title_font.render(
                            "MAPPING ELEMENTS...", True, GRAY), (modal_x + 24, modal_y + 80))
                        pygame.display.flip()
                        modal_data = api_client.fetch_lineage_deepdive(binder_id, mode=current_mode) or {
                            "error": True}

                    if modal_data.get("error"):
                        screen.blit(micro_font.render(
                            "NO DATA AVAILABLE", True, GRAY), (modal_x + 24, modal_y + 80))
                    else:
                        screen.blit(micro_font.render(
                            "PRIMARY TYPING", True, GRAY), (modal_x + 24, modal_y + 70))

                        types = modal_data['collected_types']
                        bar_y = modal_y + 95
                        for i, t in enumerate(types[:6]):  # Top 6 Types
                            screen.blit(title_font.render(
                                f"{i+1}. {t['primary_type'].upper()}", True, BLACK), (modal_x + 24, bar_y))
                            screen.blit(title_font.render(
                                f"{t['count']} CARDS", True, BLACK), (modal_x + 200, bar_y))
                            bar_y += 22

                        pygame.draw.line(
                            screen, GRAY, (modal_x + 400, modal_y + 70), (modal_x + 400, modal_y + 230), 2)

                        # Right: Missing Elements
                        right_x = modal_x + 430
                        screen.blit(micro_font.render(
                            "THE MISSING ELEMENTS (0% REPRESENTATION)", True, GRAY), (right_x, modal_y + 70))

                        missing = modal_data['missing_types']
                        if not missing:
                            screen.blit(title_font.render(
                                "ALL TYPES PRESENT.", True, BLACK), (right_x, modal_y + 100))
                        else:
                            m_y = modal_y + 95
                            # Show up to 6 missing
                            for i, t in enumerate(missing[:6]):
                                screen.blit(title_font.render(
                                    f"X   {t.upper()}", True, GRAY), (right_x, m_y))
                                m_y += 22

                # --- NEW: OVERALL BINDER CONDITION (Centered Vertical Bar Graph) ---
                elif stats_page == 4 and selected_stat_index == 6:
                    if modal_data is None:
                        screen.blit(title_font.render(
                            "ANALYZING QUALITY...", True, GRAY), (modal_x + 24, modal_y + 80))
                        pygame.display.flip()
                        modal_data = api_client.fetch_lineage_deepdive(binder_id, mode=current_mode) or {
                            "error": True}

                    if modal_data.get("error"):
                        screen.blit(micro_font.render(
                            "NO DATA AVAILABLE", True, GRAY), (modal_x + 24, modal_y + 80))
                    else:
                        screen.blit(micro_font.render(
                            "PHYSICAL QUALITY DISTRIBUTION", True, GRAY), (modal_x + 24, modal_y + 60))

                        dist = modal_data['cond_dist']
                        labels = ["M", "NM", "LP", "MP", "HP", "DMG"]
                        keys = ["cond_m", "cond_nm", "cond_lp",
                                "cond_mp", "cond_hp", "cond_dmg"]
                        counts = [dist[k] for k in keys]

                        max_val = max(counts) if counts else 1

                        # Graph configuration (Centered in the modal)
                        bar_w = 50
                        spacing = 40
                        total_graph_w = (len(counts) * bar_w) + \
                            ((len(counts) - 1) * spacing)
                        graph_x = modal_x + (modal_w - total_graph_w) // 2
                        graph_y = modal_y + 200  # Base of the bars
                        max_bar_h = 100

                        for i, count in enumerate(counts):
                            # Scale the bar height to a max of 100 pixels
                            bar_h = int((count / max_val) *
                                        max_bar_h) if max_val > 0 else 0
                            curr_x = graph_x + i * (bar_w + spacing)

                            # Draw Bar (grows UP from graph_y)
                            pygame.draw.rect(
                                screen, BLACK, (curr_x, graph_y - bar_h, bar_w, bar_h))

                            # Draw Condition Label below the bar, centered under the bar
                            lbl_surf = title_font.render(
                                labels[i], True, BLACK)
                            screen.blit(
                                lbl_surf, (curr_x + (bar_w - lbl_surf.get_width()) // 2, graph_y + 10))

                            # Draw Exact Count just above the bar, centered
                            if count > 0:
                                count_surf = micro_font.render(
                                    str(count), True, GRAY)
                                screen.blit(
                                    count_surf, (curr_x + (bar_w - count_surf.get_width()) // 2, graph_y - bar_h - 15))

                # --- NEW: THE BLEMISH (Weakest Link) ---
                elif stats_page == 4 and selected_stat_index == 7:
                    if modal_data is None:
                        screen.blit(title_font.render(
                            "FINDING THE WEAKEST LINK...", True, GRAY), (modal_x + 24, modal_y + 80))
                        pygame.display.flip()
                        modal_data = api_client.fetch_lineage_deepdive(binder_id, mode=current_mode) or {
                            "error": True}

                    if modal_data.get("error") or not modal_data.get("blemish"):
                        screen.blit(micro_font.render(
                            "NO DATA AVAILABLE", True, GRAY), (modal_x + 24, modal_y + 80))
                    else:
                        blem = modal_data['blemish']

                        screen.blit(micro_font.render(
                            "LOWEST CONDITION CARD", True, GRAY), (modal_x + 24, modal_y + 80))
                        screen.blit(boot_font.render(
                            blem['cond_label'].upper(), True, BLACK), (modal_x + 24, modal_y + 100))
                        screen.blit(title_font.render(
                            blem['pokemon_name'].upper(), True, BLACK), (modal_x + 24, modal_y + 140))

                        r_x = modal_x + 390
                        screen.blit(micro_font.render(
                            "THE JUSTIFICATION", True, GRAY), (r_x, modal_y + 80))
                        screen.blit(title_font.render(
                            f"COST: ${float(blem['item_amount']):,.2f}", True, BLACK), (r_x, modal_y + 100))

                        diff = modal_data['true_average'] - \
                            float(blem['item_amount'])
                        screen.blit(micro_font.render(
                            f"(${diff:,.2f} CHEAPER THAN BINDER AVERAGE)", True, GRAY), (r_x, modal_y + 120))

                        screen.blit(micro_font.render(
                            f"PLATFORM: {blem['platform']}", True, GRAY), (r_x, modal_y + 160))
                        date_str = format_date_short(blem['event_date'])
                        screen.blit(micro_font.render(
                            f"SECURED ON: {date_str}", True, GRAY), (r_x, modal_y + 180))

                # --- NEW: PAGE DENSITY (Grid Health) ---
                elif stats_page == 4 and selected_stat_index == 8:
                    if modal_data is None:
                        screen.blit(title_font.render(
                            "ANALYZING GRID...", True, GRAY), (modal_x + 24, modal_y + 80))
                        pygame.display.flip()
                        modal_data = api_client.fetch_lineage_deepdive(binder_id, mode=current_mode) or {
                            "error": True}

                    if modal_data.get("error"):
                        screen.blit(micro_font.render(
                            "NO DATA AVAILABLE", True, GRAY), (modal_x + 24, modal_y + 80))
                    else:
                        # Left: Densest vs Ghost
                        screen.blit(micro_font.render(
                            "THE DENSEST PAGE", True, GRAY), (modal_x + 24, modal_y + 80))
                        dense = modal_data['densest_page']
                        screen.blit(boot_font.render(
                            f"PAGE {dense['num']}", True, BLACK), (modal_x + 24, modal_y + 95))
                        screen.blit(title_font.render(
                            f"{dense['count']} / 9 SLOTS FILLED", True, BLACK), (modal_x + 24, modal_y + 135))

                        screen.blit(micro_font.render(
                            "THE EMPTIEST PAGE", True, GRAY), (modal_x + 24, modal_y + 175))
                        ghost = modal_data['ghost_page']
                        screen.blit(title_font.render(
                            f"PAGE {ghost['num']} ({ghost['count']} / 9 SLOTS)", True, BLACK), (modal_x + 24, modal_y + 190))

                        # Right: The Desert (Gap)
                        r_x = modal_x + 390
                        gap = modal_data['max_gap']
                        screen.blit(micro_font.render(
                            "LARGEST BINDER GAP", True, GRAY), (r_x, modal_y + 80))
                        screen.blit(header_font.render(
                            f"{gap['size']} CONTINUOUS EMPTY SLOTS", True, BLACK), (r_x, modal_y + 100))

                        if gap['size'] > 0:
                            screen.blit(micro_font.render(
                                f"BETWEEN POKEDEX #{gap['start']:03d} AND #{gap['end']:03d}", True, GRAY), (r_x, modal_y + 124))
                        else:
                            screen.blit(title_font.render(
                                "NO GAPS FOUND.", True, BLACK), (r_x, modal_y + 140))

                # ---------------------------------------------------------
                # PAGE 5 MODALS: THE MEMORY ARCHIVE
                # ---------------------------------------------------------

                # --- NEW: THE GENESIS & THE VANGUARD (Indexes 0 & 1) ---
                elif stats_page == 5 and selected_stat_index in [0, 1]:
                    if modal_data is None:
                        screen.blit(title_font.render(
                            "ACCESSING ARCHIVES...", True, GRAY), (modal_x + 24, modal_y + 80))
                        pygame.display.flip()
                        modal_data = api_client.fetch_archive_deepdive(binder_id, mode=current_mode) or {
                            "error": True}

                    if modal_data.get("error"):
                        screen.blit(micro_font.render(
                            "NO DATA AVAILABLE", True, GRAY), (modal_x + 24, modal_y + 80))
                    else:
                        is_genesis = (selected_stat_index == 0)
                        target = modal_data['oldest'] if is_genesis else modal_data['newest']

                        # --- LEFT SIDE: Collection View Replica (No lines) ---
                        col_width = 300
                        col_x = modal_x + 32

                        sprite_x = col_x - 8
                        sprite_y = modal_y + 70
                        sprite = get_pokemon_sprite(
                            target['pokedex_number'], size=[120, 120])
                        if sprite:
                            screen.blit(sprite, (sprite_x, sprite_y))

                        text_x = col_x + 120
                        dex_num = f"No. {target['pokedex_number']:03d}"
                        screen.blit(micro_font.render(
                            dex_num, False, BLACK), (text_x, sprite_y + 18))

                        # Badge Alignment
                        grading_status = target.get('grading_status')
                        badge_y = sprite_y + 15
                        if grading_status == "Graded":
                            grade = target.get('surface_grade')
                            badge_text = f"PSA {grade if grade else '?'}"
                            invert_badge = True
                        else:
                            raw_cond = target.get('raw_condition') or "UKN"
                            badge_text = f"RAW {raw_cond}"
                            invert_badge = False

                        text_width = micro_font.size(badge_text)[0]
                        badge_w = text_width + 12
                        badge_x = text_x + col_width - badge_w - 40
                        draw_retro_box(screen, pygame.Rect(
                            badge_x, badge_y, badge_w, 18), badge_text, micro_font, invert=invert_badge)

                        # Indicators
                        indicators = []
                        finish_type = target.get('finish')
                        if finish_type == 'Holo':
                            indicators.append("H")
                        elif finish_type == 'Reverse-Holo':
                            indicators.append("RH")
                        if target.get('has_swirl'):
                            indicators.append("S")

                        if indicators:
                            dex_width = micro_font.size(dex_num)[0]
                            left_bound = text_x + dex_width
                            available_width = badge_x - left_bound
                            step = available_width / (len(indicators) + 1)
                            for idx, ind_text in enumerate(indicators):
                                ind_surf = micro_font.render(
                                    ind_text, True, BLACK)
                                center_x = left_bound + (step * (idx + 1))
                                screen.blit(
                                    ind_surf, (center_x - (ind_surf.get_width() / 2), sprite_y + 18))

                        title_str = target.get('printed_name') or target.get(
                            'pokemon_name') or "UNKNOWN"
                        screen.blit(title_font.render(
                            title_str.upper(), True, BLACK), (text_x, sprite_y + 36))

                        meta_y = sprite_y + 58
                        line_step = 16
                        date_str = format_date(target.get('event_date'))
                        screen.blit(micro_font.render(
                            f"ACQ: {date_str}", True, BLACK), (text_x, meta_y))
                        source = target.get('platform') or 'Unknown'
                        screen.blit(micro_font.render(
                            f"FRM: {source[:11]}", True, BLACK), (text_x, meta_y + line_step))
                        cost = target.get('item_amount')
                        cost_text = f"CST: ${float(cost):,.2f}" if cost and float(
                            cost) > 0 else "CST: [GIFT/TRADE]"
                        screen.blit(micro_font.render(
                            cost_text, True, BLACK), (text_x, meta_y + line_step * 2))

                        # --- RIGHT SIDE: The Twist ---
                        r_x = modal_x + 480
                        if is_genesis:
                            screen.blit(micro_font.render(
                                "TIME IN VAULT", True, GRAY), (r_x, modal_y + 80))
                            screen.blit(boot_font.render(
                                f"{modal_data['days_in_vault']} DAYS", True, BLACK), (r_x, modal_y + 100))
                        else:
                            screen.blit(micro_font.render(
                                "THE COOLDOWN", True, GRAY), (r_x, modal_y + 80))
                            screen.blit(boot_font.render(
                                f"{modal_data['cooldown']} DAYS", True, BLACK), (r_x, modal_y + 100))
                            screen.blit(micro_font.render(
                                "TIME ELAPSED BETWEEN THIS PURCHASE", True, GRAY), (r_x, modal_y + 140))
                            screen.blit(micro_font.render(
                                "AND THE ONE IMMEDIATELY PRIOR.", True, GRAY), (r_x, modal_y + 155))

                # --- NEW: THE BINGE (Longest Streak) ---
                elif stats_page == 5 and selected_stat_index == 2:
                    if modal_data is None:
                        screen.blit(title_font.render(
                            "ANALYZING BEHAVIOR...", True, GRAY), (modal_x + 24, modal_y + 80))
                        pygame.display.flip()
                        modal_data = api_client.fetch_archive_deepdive(binder_id, mode=current_mode) or {
                            "error": True}

                    if modal_data.get("error"):
                        screen.blit(micro_font.render(
                            "NO DATA AVAILABLE", True, GRAY), (modal_x + 24, modal_y + 80))
                    else:
                        binge = modal_data['binge']

                        screen.blit(micro_font.render(
                            "LONGEST ACQUISITION STREAK", True, GRAY), (modal_x + 24, modal_y + 80))
                        screen.blit(boot_font.render(
                            f"{binge['days']} DAYS", True, BLACK), (modal_x + 24, modal_y + 100))

                        start_str = format_date(binge['start'])
                        end_str = format_date(binge['end'])
                        screen.blit(title_font.render(
                            f"{start_str} - {end_str}", True, BLACK), (modal_x + 24, modal_y + 140))

                        r_x = modal_x + 480
                        screen.blit(micro_font.render(
                            "THE FINANCES", True, GRAY), (r_x, modal_y + 80))
                        screen.blit(header_font.render(
                            f"${binge['spend']:,.2f} SPENT", True, BLACK), (r_x, modal_y + 100))
                        screen.blit(title_font.render(
                            f"ACROSS {binge['count']} ASSETS", True, BLACK), (r_x, modal_y + 125))

                # --- NEW: THE GALLERY (Top Artist) ---
                elif stats_page == 5 and selected_stat_index == 3:
                    if modal_data is None:
                        screen.blit(title_font.render(
                            "FETCHING ARTISTS...", True, GRAY), (modal_x + 24, modal_y + 80))
                        pygame.display.flip()
                        modal_data = api_client.fetch_archive_deepdive(binder_id, mode=current_mode) or {
                            "error": True}

                    if modal_data.get("error"):
                        screen.blit(micro_font.render(
                            "NO DATA AVAILABLE", True, GRAY), (modal_x + 24, modal_y + 80))
                    else:
                        gal = modal_data['gallery']

                        # Left Side
                        screen.blit(micro_font.render(
                            "VISUAL MONOPOLY", True, GRAY), (modal_x + 24, modal_y + 80))
                        screen.blit(title_font.render(
                            gal['top_artist'].upper(), True, BLACK), (modal_x + 24, modal_y + 100))
                        screen.blit(micro_font.render(
                            f"{gal['top_pct']:.1f}% OF BINDER", True, BLACK), (modal_x + 24, modal_y + 120))

                        screen.blit(micro_font.render(
                            "RUNNER UP ARTIST:", True, GRAY), (modal_x + 24, modal_y + 180))
                        screen.blit(title_font.render(
                            gal['runner_up'].upper(), True, BLACK), (modal_x + 24, modal_y + 195))

                        # Right Side Ledger
                        r_x = modal_x + 310
                        cards = gal['cards']
                        list_y_start = modal_y + 60
                        list_h = modal_h - 106
                        row_h = 22
                        visible_rows = list_h // row_h
                        total_rows = len(cards)

                        max_offset = max(0, total_rows - visible_rows)
                        if modal_scroll_offset > max_offset:
                            modal_scroll_offset = max_offset

                        screen.blit(micro_font.render(
                            "ASSET", True, GRAY), (r_x + 10, list_y_start))
                        screen.blit(micro_font.render(
                            "PLATFORM", True, GRAY), (r_x + 280, list_y_start))
                        screen.blit(micro_font.render(
                            "COST", True, GRAY), (r_x + 400, list_y_start))

                        pygame.draw.line(screen, GRAY, (r_x, list_y_start + 14),
                                         (modal_x + modal_w - 30, list_y_start + 14), 1)

                        # FIXED: Calculate correct width for the clipping window to avoid cutting off the cost
                        clip_w = (modal_x + modal_w - 30) - r_x
                        clip_rect = pygame.Rect(
                            r_x, list_y_start + 16, clip_w, list_h)
                        screen.set_clip(clip_rect)

                        draw_y = list_y_start + 20
                        for i in range(modal_scroll_offset, min(total_rows, modal_scroll_offset + visible_rows + 1)):
                            c = cards[i]
                            screen.blit(title_font.render(str(c['printed_name']).upper()[
                                        :25], True, BLACK), (r_x + 10, draw_y))
                            screen.blit(title_font.render(str(c['platform'])[
                                        :12], True, BLACK), (r_x + 280, draw_y))
                            screen.blit(title_font.render(
                                f"${float(c['item_amount'] or 0):,.2f}", True, BLACK), (r_x + 400, draw_y))
                            draw_y += row_h

                        screen.set_clip(None)

                        # FIXED: Add missing scrollbar
                        track_x = modal_x + modal_w - 20
                        track_y = list_y_start + 16
                        track_h = list_h
                        pygame.draw.rect(
                            screen, GRAY, (track_x, track_y, 4, track_h))
                        if total_rows > visible_rows:
                            thumb_h = max(
                                20, int(track_h * (visible_rows / total_rows)))
                            thumb_y = track_y + \
                                ((modal_scroll_offset / max_offset)
                                 * (track_h - thumb_h))
                            pygame.draw.rect(
                                screen, BLACK, (track_x - 2, thumb_y, 8, thumb_h))
                        else:
                            pygame.draw.rect(
                                screen, BLACK, (track_x - 2, track_y, 8, track_h))

                # --- NEW: COSMIC ANOMALIES (Swirls) ---
                elif stats_page == 5 and selected_stat_index == 4:
                    if modal_data is None:
                        screen.blit(title_font.render(
                            "SCANNING FOR SWIRLS...", True, GRAY), (modal_x + 24, modal_y + 80))
                        pygame.display.flip()
                        modal_data = api_client.fetch_archive_deepdive(binder_id, mode=current_mode) or {
                            "error": True}

                    if modal_data.get("error"):
                        screen.blit(micro_font.render(
                            "NO DATA AVAILABLE", True, GRAY), (modal_x + 24, modal_y + 80))
                    else:
                        swirls = modal_data['swirls']

                        screen.blit(micro_font.render(
                            "SWIRL DENSITY", True, GRAY), (modal_x + 24, modal_y + 80))
                        screen.blit(boot_font.render(
                            f"{swirls['density']:.1f}%", True, BLACK), (modal_x + 24, modal_y + 100))
                        screen.blit(micro_font.render(
                            "OF YOUR HOLO/REV-HOLO INVENTORY", True, GRAY), (modal_x + 24, modal_y + 140))
                        screen.blit(micro_font.render(
                            "CONTAINS A CONFIRMED SWIRL.", True, GRAY), (modal_x + 24, modal_y + 155))

                        r_x = modal_x + 360
                        cards = swirls['cards']
                        list_y_start = modal_y + 60
                        list_h = modal_h - 106
                        row_h = 22
                        visible_rows = list_h // row_h
                        total_rows = len(cards)

                        max_offset = max(0, total_rows - visible_rows)
                        if modal_scroll_offset > max_offset:
                            modal_scroll_offset = max_offset

                        screen.blit(micro_font.render(
                            "ASSET", True, GRAY), (r_x + 10, list_y_start))
                        screen.blit(micro_font.render(
                            "FINISH", True, GRAY), (r_x + 280, list_y_start))
                        pygame.draw.line(screen, GRAY, (r_x, list_y_start + 14),
                                         (modal_x + modal_w - 30, list_y_start + 14), 1)

                        clip_rect = pygame.Rect(
                            r_x, list_y_start + 16, modal_w - r_x - 30, list_h)
                        screen.set_clip(clip_rect)

                        draw_y = list_y_start + 20
                        for i in range(modal_scroll_offset, min(total_rows, modal_scroll_offset + visible_rows + 1)):
                            c = cards[i]
                            screen.blit(title_font.render(str(c['printed_name']).upper()[
                                        :25], True, BLACK), (r_x + 10, draw_y))
                            screen.blit(title_font.render(
                                str(c['finish']).upper(), True, BLACK), (r_x + 280, draw_y))
                            draw_y += row_h

                        screen.set_clip(None)

                # --- NEW: MISSING LORE (High-Value Blanks) ---
                elif stats_page == 5 and selected_stat_index == 5:
                    if modal_data is None:
                        screen.blit(title_font.render(
                            "FINDING GAPS...", True, GRAY), (modal_x + 24, modal_y + 80))
                        pygame.display.flip()
                        modal_data = api_client.fetch_archive_deepdive(binder_id, mode=current_mode) or {
                            "error": True}

                    if modal_data.get("error"):
                        screen.blit(micro_font.render(
                            "NO DATA AVAILABLE", True, GRAY), (modal_x + 24, modal_y + 80))
                    else:
                        blanks = modal_data['blanks']

                        # FIXED: Show centered message if documentation rate is 100%
                        if not blanks:
                            msg_surf = title_font.render(
                                "ALL CARDS HAVE A NOTE", True, GRAY)
                            screen.blit(msg_surf, (modal_x + (modal_w - msg_surf.get_width()) //
                                        2, modal_y + (modal_h - msg_surf.get_height()) // 2))
                        else:
                            list_y_start = modal_y + 60
                            list_h = modal_h - 106
                            row_h = 22
                            visible_rows = list_h // row_h
                            total_rows = len(blanks)

                            max_offset = max(0, total_rows - visible_rows)
                            if modal_scroll_offset > max_offset:
                                modal_scroll_offset = max_offset

                            screen.blit(micro_font.render(
                                "ASSET (MOST EXPENSIVE WITHOUT LORE)", True, GRAY), (modal_x + 24, list_y_start))
                            screen.blit(micro_font.render(
                                "PLATFORM", True, GRAY), (modal_x + 400, list_y_start))
                            screen.blit(micro_font.render(
                                "COST", True, GRAY), (modal_x + 600, list_y_start))
                            screen.blit(micro_font.render(
                                "STATUS", True, GRAY), (modal_x + 740, list_y_start))

                            pygame.draw.line(screen, GRAY, (modal_x + 16, list_y_start + 14),
                                             (modal_x + modal_w - 30, list_y_start + 14), 1)

                            clip_rect = pygame.Rect(
                                modal_x + 16, list_y_start + 16, modal_w - 30, list_h)
                            screen.set_clip(clip_rect)

                            draw_y = list_y_start + 20
                            for i in range(modal_scroll_offset, min(total_rows, modal_scroll_offset + visible_rows + 1)):
                                c = blanks[i]
                                screen.blit(title_font.render(str(c['printed_name']).upper()[
                                            :35], True, BLACK), (modal_x + 24, draw_y))
                                screen.blit(title_font.render(str(c['platform']).upper()[
                                            :15], True, BLACK), (modal_x + 400, draw_y))
                                screen.blit(title_font.render(
                                    f"${float(c['item_amount'] or 0):,.2f}", True, BLACK), (modal_x + 600, draw_y))
                                screen.blit(micro_font.render(
                                    "[NEEDS LORE]", True, GRAY), (modal_x + 740, draw_y + 2))
                                draw_y += row_h

                            screen.set_clip(None)

                            # Add Scrollbar for Blanks Table
                            track_x = modal_x + modal_w - 20
                            track_y = list_y_start + 16
                            track_h = list_h
                            pygame.draw.rect(
                                screen, GRAY, (track_x, track_y, 4, track_h))
                            if total_rows > visible_rows:
                                thumb_h = max(
                                    20, int(track_h * (visible_rows / total_rows)))
                                thumb_y = track_y + \
                                    ((modal_scroll_offset / max_offset)
                                     * (track_h - thumb_h))
                                pygame.draw.rect(
                                    screen, BLACK, (track_x - 2, thumb_y, 8, thumb_h))
                            else:
                                pygame.draw.rect(
                                    screen, BLACK, (track_x - 2, track_y, 8, track_h))

                # --- NEW: THE MANIFESTO (Longest Note Text) ---
                elif stats_page == 5 and selected_stat_index == 6:
                    if modal_data is None:
                        screen.blit(title_font.render(
                            "RETRIEVING TEXT...", True, GRAY), (modal_x + 24, modal_y + 80))
                        pygame.display.flip()
                        modal_data = api_client.fetch_archive_deepdive(binder_id, mode=current_mode) or {
                            "error": True}

                    if modal_data.get("error") or not modal_data.get("manifesto"):
                        screen.blit(micro_font.render(
                            "NO NOTES FOUND.", True, GRAY), (modal_x + 24, modal_y + 80))
                    else:
                        man = modal_data['manifesto']

                        # Header details
                        screen.blit(micro_font.render(
                            "SUBJECT", True, GRAY), (modal_x + 24, modal_y + 60))
                        screen.blit(header_font.render(
                            str(man['printed_name']).upper(), True, BLACK), (modal_x + 24, modal_y + 75))
                        screen.blit(micro_font.render(
                            f"({man['word_count']} WORDS)", True, BLACK), (modal_x + 400, modal_y + 80))
                        pygame.draw.line(
                            screen, GRAY, (modal_x + 16, modal_y + 100), (modal_x + modal_w - 30, modal_y + 100), 1)

                        # Wrap and Scroll Text
                        text = man['curator_notes']
                        words = text.split()
                        lines, current_line = [], ""
                        max_w = modal_w - 60

                        for w in words:
                            test = current_line + w + " "
                            if title_font.size(test)[0] < max_w:
                                current_line = test
                            else:
                                lines.append(current_line)
                                current_line = w + " "
                        if current_line.strip():
                            lines.append(current_line)

                        list_y_start = modal_y + 105
                        list_h = modal_h - 130
                        row_h = 20
                        visible_rows = list_h // row_h
                        total_rows = len(lines)

                        max_offset = max(0, total_rows - visible_rows)
                        if modal_scroll_offset > max_offset:
                            modal_scroll_offset = max_offset

                        clip_rect = pygame.Rect(
                            modal_x + 16, list_y_start, modal_w - 30, list_h)
                        screen.set_clip(clip_rect)

                        draw_y = list_y_start + 5
                        for i in range(modal_scroll_offset, min(total_rows, modal_scroll_offset + visible_rows + 1)):
                            screen.blit(title_font.render(
                                lines[i].strip(), True, BLACK), (modal_x + 24, draw_y))
                            draw_y += row_h

                        screen.set_clip(None)

                # --- NEW: VERBOSITY INDEX (Curator's Log) ---
                elif stats_page == 5 and selected_stat_index == 7:
                    if modal_data is None:
                        screen.blit(title_font.render(
                            "CALCULATING...", True, GRAY), (modal_x + 24, modal_y + 80))
                        pygame.display.flip()
                        modal_data = api_client.fetch_archive_deepdive(binder_id, mode=current_mode) or {
                            "error": True}

                    if modal_data.get("error"):
                        screen.blit(micro_font.render(
                            "NO DATA AVAILABLE", True, GRAY), (modal_x + 24, modal_y + 80))
                    else:
                        verb = modal_data['verbosity']
                        list_y_start = modal_y + 60
                        list_h = modal_h - 106
                        row_h = 22
                        visible_rows = list_h // row_h
                        total_rows = len(verb)

                        max_offset = max(0, total_rows - visible_rows)
                        if modal_scroll_offset > max_offset:
                            modal_scroll_offset = max_offset

                        screen.blit(micro_font.render(
                            "RANK", True, GRAY), (modal_x + 24, list_y_start))
                        screen.blit(micro_font.render(
                            "ASSET", True, GRAY), (modal_x + 100, list_y_start))
                        screen.blit(micro_font.render(
                            "QUALITY", True, GRAY), (modal_x + 460, list_y_start))
                        screen.blit(micro_font.render(
                            "WORD COUNT", True, GRAY), (modal_x + 600, list_y_start))

                        pygame.draw.line(screen, GRAY, (modal_x + 16, list_y_start + 14),
                                         (modal_x + modal_w - 30, list_y_start + 14), 1)

                        clip_rect = pygame.Rect(
                            modal_x + 16, list_y_start + 16, modal_w - 30, list_h)
                        screen.set_clip(clip_rect)

                        draw_y = list_y_start + 20
                        for i in range(modal_scroll_offset, min(total_rows, modal_scroll_offset + visible_rows + 1)):
                            c = verb[i]
                            screen.blit(title_font.render(
                                f"#{i+1}", True, BLACK), (modal_x + 24, draw_y))
                            screen.blit(title_font.render(str(c['printed_name']).upper()[
                                        :35], True, BLACK), (modal_x + 100, draw_y))
                            screen.blit(title_font.render(
                                str(c['cond_label']).upper(), True, BLACK), (modal_x + 460, draw_y))
                            screen.blit(title_font.render(
                                f"{c['word_count']} WORDS", True, BLACK), (modal_x + 600, draw_y))
                            draw_y += row_h

                        screen.set_clip(None)

                        # FIXED: Add missing scrollbar
                        track_x = modal_x + modal_w - 20
                        track_y = list_y_start + 16
                        track_h = list_h
                        pygame.draw.rect(
                            screen, GRAY, (track_x, track_y, 4, track_h))
                        if total_rows > visible_rows:
                            thumb_h = max(
                                20, int(track_h * (visible_rows / total_rows)))
                            thumb_y = track_y + \
                                ((modal_scroll_offset / max_offset)
                                 * (track_h - thumb_h))
                            pygame.draw.rect(
                                screen, BLACK, (track_x - 2, thumb_y, 8, thumb_h))
                        else:
                            pygame.draw.rect(
                                screen, BLACK, (track_x - 2, track_y, 8, track_h))

                else:
                    screen.blit(title_font.render(
                        "DETAILED METRICS UNAVAILABLE IN CURRENT VIEW.", True, GRAY), (modal_x + 24, modal_y + 80))
                    screen.blit(micro_font.render(
                        "This module will display a granular breakdown, historical trends, and transaction logs.", True, GRAY), (modal_x + 24, modal_y + 105))

                # 10. Footer Navigation
                screen.blit(micro_font.render(
                    "[ESC / ENTER] CLOSE WINDOW", True, BLACK), (modal_x + 24, modal_y + modal_h - 24))

        # ---------------------------------------------------------
        # RENDER: COLLECTION
        # ---------------------------------------------------------
        elif app_state == STATE_COLLECTION:
            if not page_data:
                screen.blit(header_font.render(
                    "SilphDB: LOADING...", True, BLACK), (16, 16))
                pygame.display.flip()
                continue

            nav_text = f"SilphDB: Page {page_data.get('page_number', current_page)} - Row: {current_row + 1}/3"
            screen.blit(header_font.render(nav_text, True, BLACK), (16, 16))
            pygame.draw.line(screen, BLACK, (8, 44), (SCREEN_WIDTH - 8, 44), 4)

            col_width = (SCREEN_WIDTH - 16) // 3
            start_index = current_row * 3
            end_index = start_index + 3

            active_slots = page_data.get("slots", [])[start_index:end_index]

            for i, slot in enumerate(active_slots):
                col_x = 8 + (i * col_width)

                if i > 0:
                    pygame.draw.line(screen, BLACK, (col_x, 44),
                                     (col_x, SCREEN_HEIGHT - 8), 4)

                if i == len(active_slots) - 1 and i < 2:
                    right_x = col_x + col_width
                    pygame.draw.line(screen, BLACK, (right_x, 44),
                                     (right_x, SCREEN_HEIGHT - 8), 4)

                is_collected = slot.get('asset_id') is not None

                # --- TOP LEFT: SPRITE ---
                sprite_x = col_x - 8
                sprite_y = 38
                sprite = get_pokemon_sprite(
                    slot['pokedex_number'], size=[120, 120])
                if sprite:
                    if is_collected:
                        screen.blit(sprite, (sprite_x, sprite_y))
                    else:
                        silhouette = get_silhouette(sprite)
                        screen.blit(silhouette, (sprite_x, sprite_y))

                # --- TOP RIGHT: NAME & NUMBER & GRADE ---
                text_x = col_x + 104
                dex_num = f"No. {slot['pokedex_number']:03d}"
                screen.blit(micro_font.render(
                    dex_num, False, BLACK), (text_x, 56))

                if is_collected:
                    grading_status = slot.get('grading_status')
                    badge_y = 53

                    if grading_status == "Graded":
                        grade = slot.get('surface_grade')
                        badge_text = f"PSA {grade if grade else '?'}"
                        invert_badge = True
                    else:
                        raw_cond = slot.get('raw_condition') or "UKN"
                        badge_text = f"RAW {raw_cond}"
                        invert_badge = False

                    text_width = micro_font.size(badge_text)[0]
                    badge_w = text_width + 12
                    badge_x = col_x + col_width - 12 - badge_w

                    draw_retro_box(screen, pygame.Rect(
                        badge_x, badge_y, badge_w, 18), badge_text, micro_font, invert=invert_badge)

                    indicators = []
                    finish_type = slot.get('finish')
                    if finish_type == 'Holo':
                        indicators.append("H")
                    elif finish_type == 'Reverse-Holo':
                        indicators.append("RH")
                    if slot.get('has_swirl'):
                        indicators.append("S")

                    if indicators:
                        dex_width = micro_font.size(dex_num)[0]
                        left_bound = text_x + dex_width
                        available_width = badge_x - left_bound
                        step = available_width / (len(indicators) + 1)

                        for idx, ind_text in enumerate(indicators):
                            ind_surf = micro_font.render(ind_text, True, BLACK)
                            center_x = left_bound + (step * (idx + 1))
                            ind_draw_x = center_x - (ind_surf.get_width() / 2)
                            screen.blit(ind_surf, (ind_draw_x, 56))

                title_str = slot.get('printed_name') or slot.get(
                    'pokemon_name') or "UNKNOWN"
                screen.blit(title_font.render(
                    title_str.upper(), True, BLACK), (text_x, 74))

                # --- TOP RIGHT: METADATA ---
                meta_y = 96
                line_step = 16

                if is_collected:
                    date_str = format_date(slot.get('event_date'))
                    screen.blit(micro_font.render(
                        f"ACQ: {date_str}", True, BLACK), (text_x, meta_y))
                    source = slot.get('platform') or 'Unknown'
                    screen.blit(micro_font.render(
                        f"FRM: {source[:11]}", True, BLACK), (text_x, meta_y + line_step))
                    cost = slot.get('item_cost')
                    cost_text = f"CST: ${float(cost):,.2f}" if cost and float(
                        cost) > 0 else "CST: [GIFT/TRADE]"
                    screen.blit(micro_font.render(cost_text, True,
                                BLACK), (text_x, meta_y + line_step * 2))
                else:
                    screen.blit(micro_font.render(
                        "ACQ: ?", True, BLACK), (text_x, meta_y))
                    screen.blit(micro_font.render("FRM: ?", True,
                                BLACK), (text_x, meta_y + line_step))
                    screen.blit(micro_font.render("CST: ?", True,
                                BLACK), (text_x, meta_y + line_step * 2))

                # --- NEW: DRAW SET ICON ---
                if is_collected:
                    # Safely grab the set_id from the slot data
                    set_id = str(slot.get('set_id', '')).lower()

                    if set_id in set_icons:
                        icon_img = set_icons[set_id]
                        # Position: Align to the right margin, resting 4px above the horizontal line
                        icon_x = col_x + col_width - 12 - icon_img.get_width()
                        icon_y = 148 - 4 - icon_img.get_height()
                        screen.blit(icon_img, (icon_x, icon_y))

                # Horizontal Divider Line
                pygame.draw.line(screen, BLACK, (col_x + 12, 148),
                                 (col_x + col_width - 12, 148), 2)

                # --- BOTTOM: NOTES ---
                details_x = col_x + 12
                y_offset = 158

                if is_collected:
                    notes = slot.get('curator_notes')
                    if notes:
                        words = notes.split()
                        lines, current_line = [], ""
                        max_text_width = col_width - 24

                        for word in words:
                            test_line = current_line + word + " "
                            if micro_font.size(test_line)[0] < max_text_width:
                                current_line = test_line
                            else:
                                lines.append(current_line)
                                current_line = word + " "

                        if current_line.strip():
                            lines.append(current_line)

                        if len(lines) > 10:
                            lines = lines[:10]
                            last_line = lines[-1].strip()
                            while micro_font.size(last_line + "...")[0] > max_text_width and len(last_line) > 0:
                                last_line = last_line[:-1]
                            lines[-1] = last_line.strip() + "..."

                        note_y = y_offset + 5
                        for line in lines:
                            screen.blit(micro_font.render(
                                line.strip(), True, BLACK), (details_x, note_y))
                            note_y += 14

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
