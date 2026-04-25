import os
import psycopg2
from uuid import uuid4
from dotenv import load_dotenv
from InquirerPy import inquirer
from InquirerPy.validator import NumberValidator

load_dotenv()


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS")
    )


def main():
    conn = get_db_connection()
    cur = conn.cursor()

    print("--- 📂 SilphDB Add Asset Wizard ---")

    while True:
        try:
            print("\n" + "-"*35 + "\n")

            # STEP 1: Identification
            search_term = inquirer.text(
                message="Search Pokemon Name:").execute().capitalize()
            cur.execute(
                "SELECT pokedex_number, pokemon_name FROM pokedex WHERE pokemon_name LIKE %s", (f"%{search_term}%",))
            results = cur.fetchall()

            if not results:
                print("❌ No Pokemon found with that name.")
                # Skip to the prompt at the bottom instead of exiting
            else:
                pkmn_choice = inquirer.select(
                    message="Select Pokemon:",
                    choices=[{"name": f"#{r[0]} {r[1]}", "value": r[0]}
                             for r in results]
                ).execute()

                default_name = next(r[1]
                                    for r in results if r[0] == pkmn_choice)

                printed_name = inquirer.text(
                    message="Printed Card Name (Edit if it's 'Dark', 'Sabrina\\'s', etc.):",
                    default=default_name
                ).execute()

                cur.execute(
                    "SELECT set_id, set_name, series FROM sets ORDER BY release_date DESC")
                sets_data = cur.fetchall()

                set_choices = [
                    {"name": f"[{s[2]}] {s[1]} ({s[0]})", "value": s[0]}
                    for s in sets_data
                ]

                selected_set_id = inquirer.fuzzy(
                    message="Select Set:",
                    choices=set_choices,
                    match_exact=False,
                ).execute()

                # STEP 2: Card Definition
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
                    message="Print Run:",
                    choices=run_choices
                ).execute()

                lang = inquirer.select(message="Language:", choices=[
                                       "EN", "JP", "ES"]).execute()
                finish = inquirer.select(message="Finish:", choices=[
                                         "Holo", "Non-Holo", "Reverse-Holo"]).execute()
                artist = inquirer.text(message="Artist:").execute()

                def_id = f"{pkmn_choice}-{selected_set_id.upper()}-{lang}-{print_run[:3].upper()}".replace(
                    " ", "")

                # STEP 3: Acquisition Event
                event_date = inquirer.text(
                    message="Event Date (YYYY-MM-DD):", default="2026-04-25").execute()

                event_type = inquirer.select(
                    message="Event Type:",
                    choices=["Purchase", "Trade", "Gift"]
                ).execute()

                # Set default financial baselines
                cost = 0.0
                shipping = 0.0
                tax = 0.0

                # Only prompt for money if money changed hands
                if event_type == "Purchase":
                    cost_input = inquirer.text(
                        message="Item Cost:",
                        validate=lambda result: result.replace(
                            '.', '', 1).isdigit(),
                        invalid_message="Input must be a number (e.g., 15.50)"
                    ).execute()
                    cost = float(cost_input)

                    shipping_input = inquirer.text(
                        message="Shipping Cost:",
                        default="0.00",
                        validate=lambda result: result.replace(
                            '.', '', 1).isdigit(),
                    ).execute()
                    shipping = float(shipping_input)

                    tax_input = inquirer.text(
                        message="Tax:",
                        default="0.00",
                        validate=lambda result: result.replace(
                            '.', '', 1).isdigit(),
                    ).execute()
                    tax = float(tax_input)

                elif event_type == "Trade":
                    shipping_input = inquirer.text(
                        message="Shipping Cost (if applicable):",
                        default="0.00",
                        validate=lambda result: result.replace(
                            '.', '', 1).isdigit(),
                    ).execute()
                    shipping = float(shipping_input)

                source = inquirer.text(
                    message="Counterparty/Source (e.g., Uncle John, eBay, LCS):").execute()

                # STEP 4: Asset Details
                location = inquirer.text(
                    message="Storage Location (e.g., Binder A1, Vault):").execute()

                is_active = inquirer.confirm(
                    message="Is this actively displayed?", default=True).execute()
                has_swirl = inquirer.confirm(
                    message="Does it have a swirl?", default=False).execute()

                # Conditional Subgrades
                is_graded = inquirer.confirm(
                    message="Is this card graded with subgrades?", default=False).execute()

                surface, corners, edges, centering = None, None, None, None

                if is_graded:
                    print(
                        "  ↳ Enter subgrades (1-10). Press Enter to skip a specific subgrade.")

                    def get_grade(name):
                        ans = inquirer.text(
                            message=f"    {name} Grade:",
                            validate=lambda x: x == "" or (
                                x.isdigit() and 1 <= int(x) <= 10),
                            invalid_message="Must be an integer between 1 and 10."
                        ).execute()
                        return int(ans) if ans else None

                    surface = get_grade("Surface")
                    corners = get_grade("Corners")
                    edges = get_grade("Edges")
                    centering = get_grade("Centering")

                notes = inquirer.text(message="Curator Notes:").execute()

                # --- DATABASE TRANSACTION ---
                print("\n🚀 Writing to SilphDB...")

                cur.execute("""
                    INSERT INTO cards (definition_id, pokedex_number, set_id, card_number, print_run, language, finish, artist, printed_name)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (definition_id) DO UPDATE SET artist = EXCLUDED.artist
                    RETURNING definition_id;
                """, (def_id, pkmn_choice, selected_set_id, card_num, print_run, lang, finish, artist, printed_name))

                cur.execute("""
                    INSERT INTO acquisition_events (event_date, event_type, counterparty, item_cost, shipping_cost, tax_cost)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING event_id;
                """, (event_date, event_type, source, cost, shipping, tax))
                event_id = cur.fetchone()[0]

                cur.execute("""
                    INSERT INTO assets (
                        definition_id, event_id, storage_location, is_active_display, 
                        has_swirl, curator_notes, surface_grade, corners_grade, edges_grade, centering_grade
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, (def_id, event_id, location, is_active, has_swirl, notes, surface, corners, edges, centering))

                conn.commit()
                print(f"✅ Successfully archived Asset {def_id} in {location}.")

        except Exception as e:
            print(f"\n❌ Error archiving asset: {e}")
            conn.rollback()

        # This will trigger whether the try block succeeded OR threw an exception
        print()
        add_another = inquirer.confirm(
            message="Add another?", default=False).execute()

        if not add_another:
            break

    # Clean up once the loop is broken
    cur.close()
    conn.close()
    print("👋 Exiting SilphDB Add Asset Wizard.")


if __name__ == "__main__":
    main()
