import os
import psycopg2
from dotenv import load_dotenv
from InquirerPy import inquirer
from InquirerPy.validator import NumberValidator
from datetime import datetime

load_dotenv()

MAX_NOTE_LENGTH = 240


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS")
    )


def add_asset(conn, cur):
    print("\n--- 📂 Add New Asset (Acquisition) ---")

    while True:
        try:
            print("\n" + "-"*35 + "\n")

            # --- STEP 1: Card Definition Search & Fallback ---
            search_term = inquirer.text(
                message="Search Seeded Cards (Name or Definition ID):").execute()

            cur.execute("""
                SELECT definition_id, printed_name, set_id, card_number, artist 
                FROM cards 
                WHERE printed_name ILIKE %s OR definition_id ILIKE %s
                ORDER BY printed_name ASC LIMIT 15
            """, (f"%{search_term}%", f"%{search_term}%"))
            results = cur.fetchall()

            selected_def_id = None

            if results:
                choices = [{"name": f"[{r[2].upper()}] {r[1]} #{r[3]} (Art: {r[4]})",
                            "value": r[0]} for r in results]
                choices.append(
                    {"name": "❌ NOT FOUND - ENTER MANUALLY", "value": "MANUAL"})

                selection = inquirer.select(
                    message="Select Card Definition:",
                    choices=choices
                ).execute()

                selected_def_id = selection
            else:
                print("❌ No definitions found in API seed.")
                selected_def_id = "MANUAL"

            # MANUAL ESCAPE HATCH
            if selected_def_id == "MANUAL":
                print("\n--- 🛠️ MANUAL ESCAPE HATCH: DEFINE NEW CARD ---")

                pkmn_search = inquirer.text(
                    message="Search Pokedex Name:").execute().capitalize()
                cur.execute(
                    "SELECT pokedex_number, pokemon_name FROM pokedex WHERE pokemon_name LIKE %s", (f"%{pkmn_search}%",))
                pkmn_results = cur.fetchall()

                if not pkmn_results:
                    print("❌ Pokemon not found. Aborting entry.")
                    continue

                pkmn_choice = inquirer.select(
                    message="Select Pokemon:",
                    choices=[{"name": f"#{r[0]} {r[1]}", "value": r[0]}
                             for r in pkmn_results]
                ).execute()

                default_name = next(r[1]
                                    for r in pkmn_results if r[0] == pkmn_choice)
                printed_name = inquirer.text(
                    message="Printed Card Name:", default=default_name).execute()

                cur.execute(
                    "SELECT set_id, set_name, series FROM sets ORDER BY release_date DESC")
                sets_data = cur.fetchall()
                set_choices = [
                    {"name": f"[{s[2]}] {s[1]} ({s[0]})", "value": s[0]} for s in sets_data]

                selected_set_id = inquirer.fuzzy(
                    message="Select Set:",
                    choices=set_choices,
                    match_exact=False,
                ).execute()

                card_num = inquirer.text(
                    message="Card Number (e.g., 4/102):").execute()

                set_lower = selected_set_id.lower()
                if set_lower == 'base1':
                    run_choices = ["Unlimited", "1st Edition", "Shadowless"]
                elif any(prefix in set_lower for prefix in ['base', 'gym', 'neo']):
                    run_choices = ["Unlimited", "1st Edition"]
                else:
                    run_choices = ["Unlimited",
                                   "Reverse Holo", "Promo", "Staff"]

                print_run = inquirer.select(
                    message="Print Run:", choices=run_choices).execute()
                lang = inquirer.select(message="Language:", choices=[
                                       "EN", "JP", "ES"]).execute()
                finish = inquirer.select(message="Finish:", choices=[
                                         "Holo", "Non-Holo", "Reverse-Holo"]).execute()
                artist = inquirer.text(message="Artist:").execute()

                selected_def_id = f"{pkmn_choice}-{selected_set_id.upper()}-{card_num}-{lang}-{print_run[:3].upper()}".replace(
                    " ", "")

                print("\n🚀 Injecting Custom Definition to SilphDB...")
                cur.execute("""
                    INSERT INTO cards (definition_id, pokedex_number, set_id, card_number, print_run, language, finish, artist, printed_name)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (definition_id) DO UPDATE SET artist = EXCLUDED.artist;
                """, (selected_def_id, pkmn_choice, selected_set_id, card_num, print_run, lang, finish, artist, printed_name))

            # --- STEP 2: Acquisition Event ---
            print("\n--- 💸 LOGGING ACQUISITION EVENT ---")
            today_str = datetime.now().strftime("%Y-%m-%d")
            event_date = inquirer.text(
                message="Event Date (YYYY-MM-DD):", default=today_str).execute()

            event_type = inquirer.select(message="Event Type:", choices=[
                                         "Purchase", "Trade", "Gift"]).execute()
            platform = inquirer.text(
                message="Platform (e.g., eBay, TCGPlayer, LCS):").execute()
            counterparty = inquirer.text(
                message="Seller/Counterparty Name:").execute()

            cost, shipping, tax = 0.0, 0.0, 0.0

            if event_type == "Purchase":
                cost_input = inquirer.text(
                    message="Item Amount:",
                    default="0.00",
                    validate=lambda result: result.replace(
                        '.', '', 1).isdigit()
                ).execute()
                cost = float(cost_input)

                shipping_input = inquirer.text(
                    message="Shipping Amount:",
                    default="0.00",
                    validate=lambda result: result.replace(
                        '.', '', 1).isdigit(),
                ).execute()
                shipping = float(shipping_input)

                tax_input = inquirer.text(
                    message="Tax Amount:",
                    default="0.00",
                    validate=lambda result: result.replace(
                        '.', '', 1).isdigit(),
                ).execute()
                tax = float(tax_input)

            elif event_type == "Trade":
                shipping_input = inquirer.text(
                    message="Shipping Amount (if applicable):",
                    default="0.00",
                    validate=lambda result: result.replace(
                        '.', '', 1).isdigit(),
                ).execute()
                shipping = float(shipping_input)

            # --- STEP 3: Asset Details ---
            print("\n--- 📦 LOGGING ASSET DETAILS ---")
            location = inquirer.text(
                message="Storage Location (e.g., Binder A1, Vault):").execute()
            is_active = inquirer.confirm(
                message="Is this actively displayed?", default=True).execute()
            has_swirl = inquirer.confirm(
                message="Does it have a swirl?", default=False).execute()

            grading_status = inquirer.select(message="Grading Status:", choices=[
                                             "Raw", "Graded"]).execute()

            raw_cond = None
            surface, corners, edges, centering = None, None, None, None

            if grading_status == "Raw":
                raw_cond = inquirer.select(
                    message="Raw Condition:",
                    choices=["M", "NM", "LP", "MP", "HP", "DMG", "UKN"]
                ).execute()
            else:
                print(
                    "  ↳ Enter subgrades (1-10). Press Enter to skip a specific subgrade.")

                def get_grade(name):
                    ans = inquirer.text(
                        message=f"    {name} Grade:",
                        validate=lambda x: x == "" or (
                            x.isdigit() and 1 <= int(x) <= 10)
                    ).execute()
                    return int(ans) if ans else None

                surface = get_grade("Surface")
                corners = get_grade("Corners")
                edges = get_grade("Edges")
                centering = get_grade("Centering")

            notes = inquirer.text(
                message=f"Curator Notes (Max {MAX_NOTE_LENGTH} chars):",
                validate=lambda result: len(result) <= MAX_NOTE_LENGTH
            ).execute()

            # --- DATABASE TRANSACTION ---
            print("\n🚀 Writing to SilphDB...")

            cur.execute("""
                INSERT INTO events (event_date, event_type, platform, counterparty, item_amount, shipping_amount, tax_amount)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING event_id;
            """, (event_date, event_type, platform, counterparty, cost, shipping, tax))
            event_id = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO assets (
                    definition_id, acquisition_event_id, storage_location, is_active_display, 
                    has_swirl, curator_notes, grading_status, raw_condition, 
                    surface_grade, corners_grade, edges_grade, centering_grade
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s::grading_enum, %s::condition_enum, %s, %s, %s, %s);
            """, (selected_def_id, event_id, location, is_active, has_swirl, notes, grading_status, raw_cond, surface, corners, edges, centering))

            conn.commit()
            print(
                f"✅ Successfully archived Asset {selected_def_id} in {location}.")

        except Exception as e:
            print(f"\n❌ Error archiving asset: {e}")
            conn.rollback()

        print()
        add_another = inquirer.confirm(
            message="Add another?", default=False).execute()
        if not add_another:
            break


def edit_asset(conn, cur):
    print("\n--- 📝 Edit Existing Asset ---")

    try:
        search_term = inquirer.text(
            message="Search Inventory by Pokemon Name:").execute()

        cur.execute("""
            SELECT a.asset_id, c.printed_name, c.set_id, c.print_run, a.storage_location, a.is_active_display 
            FROM assets a
            JOIN cards c ON a.definition_id = c.definition_id
            WHERE c.printed_name ILIKE %s AND a.disposition_event_id IS NULL
            ORDER BY c.printed_name ASC
        """, (f"%{search_term}%",))

        results = cur.fetchall()

        if not results:
            print("❌ No active assets found matching that name.")
            return

        choices = []
        for r in results:
            asset_id, name, set_id, run, loc, is_active = r
            status = "👁️  Active" if is_active else "📦 Vault"
            display_str = f"{name} [{set_id.upper()}] ({run}) | Loc: {loc} | {status}"
            choices.append({"name": display_str, "value": asset_id})

        selected_asset_id = inquirer.select(
            message="Select Asset to Edit:",
            choices=choices
        ).execute()

        # Fetch both Asset and associated Acquisition Event data
        cur.execute("""
            SELECT a.storage_location, a.is_active_display, a.has_swirl, a.curator_notes, 
                   a.grading_status, a.raw_condition, a.surface_grade, a.corners_grade, a.edges_grade, a.centering_grade,
                   a.acquisition_event_id,
                   e.event_date, e.event_type, e.platform, e.counterparty, e.item_amount, e.shipping_amount, e.tax_amount
            FROM assets a
            LEFT JOIN events e ON a.acquisition_event_id = e.event_id
            WHERE a.asset_id = %s
        """, (selected_asset_id,))

        current_data = cur.fetchone()
        (loc, active, swirl, notes, g_status, r_cond, surf, corn, edge, cent,
         event_id, e_date, e_type, e_plat, e_counter, e_cost, e_ship, e_tax) = current_data

        def safe_str(val): return str(val) if val is not None else ""

        print("\n✏️  Press Enter to keep current values, or type to overwrite.")

        # --- Edit Acquisition Event Details ---
        print("\n--- 💸 Edit Acquisition Event ---")
        new_e_date = inquirer.text(
            message="Event Date (YYYY-MM-DD):", default=safe_str(e_date)).execute()

        new_e_type = inquirer.select(
            message="Event Type:",
            choices=["Purchase", "Trade", "Gift"],
            default=e_type if e_type else "Purchase"
        ).execute()

        new_e_plat = inquirer.text(
            message="Platform (e.g., eBay, TCGPlayer, LCS):", default=safe_str(e_plat)).execute()
        new_e_counter = inquirer.text(
            message="Seller/Counterparty Name:", default=safe_str(e_counter)).execute()

        new_e_cost, new_e_ship, new_e_tax = 0.0, 0.0, 0.0

        if new_e_type == "Purchase":
            cost_input = inquirer.text(
                message="Item Amount:",
                default=safe_str(e_cost) if e_cost else "0.00",
                validate=lambda result: result.replace('.', '', 1).isdigit()
            ).execute()
            new_e_cost = float(cost_input)

            shipping_input = inquirer.text(
                message="Shipping Amount:",
                default=safe_str(e_ship) if e_ship else "0.00",
                validate=lambda result: result.replace('.', '', 1).isdigit(),
            ).execute()
            new_e_ship = float(shipping_input)

            tax_input = inquirer.text(
                message="Tax Amount:",
                default=safe_str(e_tax) if e_tax else "0.00",
                validate=lambda result: result.replace('.', '', 1).isdigit(),
            ).execute()
            new_e_tax = float(tax_input)

        elif new_e_type == "Trade":
            shipping_input = inquirer.text(
                message="Shipping Amount (if applicable):",
                default=safe_str(e_ship) if e_ship else "0.00",
                validate=lambda result: result.replace('.', '', 1).isdigit(),
            ).execute()
            new_e_ship = float(shipping_input)

        # --- Edit Asset Details ---
        print("\n--- 📦 Edit Asset Details ---")
        new_loc = inquirer.text(
            message="Storage Location:", default=safe_str(loc)).execute()
        new_active = inquirer.confirm(
            message="Actively Displayed?", default=active).execute()
        new_swirl = inquirer.confirm(
            message="Has Swirl?", default=swirl).execute()

        # Grading Status Edit
        new_g_status = inquirer.select(
            message="Grading Status:",
            choices=["Raw", "Graded"],
            default=g_status if g_status else "Raw"
        ).execute()

        new_r_cond = r_cond
        new_surf, new_corn, new_edge, new_cent = surf, corn, edge, cent

        if new_g_status == "Raw":
            new_r_cond = inquirer.select(
                message="Raw Condition:",
                choices=["M", "NM", "LP", "MP", "HP", "DMG", "UKN"],
                default=r_cond if r_cond else "NM"
            ).execute()
            new_surf, new_corn, new_edge, new_cent = None, None, None, None
        else:
            new_r_cond = None
            print("\n  ↳ Subgrades (1-10). Leave blank to clear/skip.")

            def get_grade(name, current_val):
                ans = inquirer.text(
                    message=f"    {name} Grade:",
                    default=safe_str(current_val),
                    validate=lambda x: x == "" or (
                        x.isdigit() and 1 <= int(x) <= 10)
                ).execute()
                return int(ans) if ans else None

            new_surf = get_grade("Surface", surf)
            new_corn = get_grade("Corners", corn)
            new_edge = get_grade("Edges", edge)
            new_cent = get_grade("Centering", cent)

        new_notes = inquirer.text(
            message=f"Curator Notes (Max {MAX_NOTE_LENGTH} chars):",
            default=safe_str(notes),
            validate=lambda result: len(result) <= MAX_NOTE_LENGTH
        ).execute()

        print("\n🚀 Updating SilphDB...")

        # UPDATE EVENTS TABLE
        if event_id:
            cur.execute("""
                UPDATE events
                SET event_date = %s, event_type = %s, platform = %s, counterparty = %s, 
                    item_amount = %s, shipping_amount = %s, tax_amount = %s
                WHERE event_id = %s
            """, (new_e_date, new_e_type, new_e_plat, new_e_counter, new_e_cost, new_e_ship, new_e_tax, event_id))

        # UPDATE ASSETS TABLE
        cur.execute("""
            UPDATE assets
            SET storage_location = %s,
                is_active_display = %s,
                has_swirl = %s,
                curator_notes = %s,
                grading_status = %s::grading_enum,
                raw_condition = %s::condition_enum,
                surface_grade = %s,
                corners_grade = %s,
                edges_grade = %s,
                centering_grade = %s
            WHERE asset_id = %s
        """, (new_loc, new_active, new_swirl, new_notes, new_g_status, new_r_cond, new_surf, new_corn, new_edge, new_cent, selected_asset_id))

        conn.commit()
        print(f"✅ Successfully updated Asset ID: {selected_asset_id}")

    except Exception as e:
        print(f"❌ Error updating asset: {e}")
        conn.rollback()


def log_disposition(conn, cur):
    print("\n--- 📤 Log Asset Disposition (Sale / Trade / Lost) ---")

    try:
        search_term = inquirer.text(
            message="Search Inventory to Dispose (Pokemon Name):").execute()

        # Only search active assets that haven't been disposed of yet
        cur.execute("""
            SELECT a.asset_id, c.printed_name, c.set_id, c.print_run, a.storage_location 
            FROM assets a
            JOIN cards c ON a.definition_id = c.definition_id
            WHERE c.printed_name ILIKE %s AND a.disposition_event_id IS NULL
            ORDER BY c.printed_name ASC
        """, (f"%{search_term}%",))

        results = cur.fetchall()

        if not results:
            print("❌ No active assets found matching that name.")
            return

        choices = []
        for r in results:
            asset_id, name, set_id, run, loc = r
            display_str = f"{name} [{set_id.upper()}] ({run}) | Loc: {loc}"
            choices.append({"name": display_str, "value": asset_id})

        selected_asset_id = inquirer.select(
            message="Select Asset:",
            choices=choices
        ).execute()

        event_type = inquirer.select(
            message="Disposition Type:",
            choices=["Sale", "Trade", "Lost"]
        ).execute()

        today_str = datetime.now().strftime("%Y-%m-%d")
        event_date = inquirer.text(
            message="Date (YYYY-MM-DD):", default=today_str).execute()

        platform = None
        counterparty = None
        cost, shipping, tax = 0.0, 0.0, 0.0

        if event_type in ["Sale", "Trade"]:
            platform = inquirer.text(
                message="Platform (e.g., eBay, TCGPlayer, LCS):").execute()
            counterparty = inquirer.text(
                message="Buyer/Counterparty Name:").execute()

            if event_type == "Sale":
                cost_input = inquirer.text(
                    message="Sale Amount (Revenue):",
                    default="0.00",
                    validate=lambda result: result.replace(
                        '.', '', 1).isdigit()
                ).execute()
                cost = float(cost_input)

                shipping_input = inquirer.text(
                    message="Shipping Amount Collected:",
                    default="0.00",
                    validate=lambda result: result.replace(
                        '.', '', 1).isdigit()
                ).execute()
                shipping = float(shipping_input)

                tax_input = inquirer.text(
                    message="Tax Collected:",
                    default="0.00",
                    validate=lambda result: result.replace(
                        '.', '', 1).isdigit()
                ).execute()
                tax = float(tax_input)

        print("\n🚀 Writing to SilphDB...")

        cur.execute("""
            INSERT INTO events (event_date, event_type, platform, counterparty, item_amount, shipping_amount, tax_amount)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING event_id;
        """, (event_date, event_type, platform, counterparty, cost, shipping, tax))
        new_event_id = cur.fetchone()[0]

        cur.execute("""
            UPDATE assets
            SET disposition_event_id = %s,
                is_active_display = FALSE,
                storage_location = 'Disposed'
            WHERE asset_id = %s
        """, (new_event_id, selected_asset_id))

        conn.commit()
        print(
            f"✅ Successfully logged {event_type} for Asset ID: {selected_asset_id}")

    except Exception as e:
        print(f"❌ Error logging disposition: {e}")
        conn.rollback()


def main():
    conn = get_db_connection()
    cur = conn.cursor()

    print("--- 💼 SilphDB Asset Manager ---")

    while True:
        try:
            print("\n" + "="*35)
            action = inquirer.select(
                message="Main Menu:",
                choices=["Add New Asset", "Edit Existing Asset",
                         "Log Asset Disposition", "Exit"]
            ).execute()

            if action == "Exit":
                break
            elif action == "Add New Asset":
                add_asset(conn, cur)
            elif action == "Edit Existing Asset":
                edit_asset(conn, cur)
            elif action == "Log Asset Disposition":
                log_disposition(conn, cur)

        except KeyboardInterrupt:
            print("\n\n⚠️ Operation cancelled. Returning to main menu...")
            conn.rollback()
            continue

        except Exception as e:
            print(f"\n❌ An error occurred: {e}")
            conn.rollback()

    cur.close()
    conn.close()
    print("👋 Exiting SilphDB Asset Manager.")


if __name__ == "__main__":
    main()
