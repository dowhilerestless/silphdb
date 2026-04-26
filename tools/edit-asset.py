import os
import psycopg2
from dotenv import load_dotenv
from InquirerPy import inquirer

load_dotenv()

MAX_NOTE_LENGTH = 120


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

    print("--- 📝 SilphDB Asset Editor ---")

    try:
        # STEP 1: Search Inventory
        search_term = inquirer.text(
            message="Search Inventory by Pokemon Name:").execute()

        # Join assets and cards to get human-readable names
        cur.execute("""
            SELECT a.asset_id, c.printed_name, c.set_id, c.print_run, a.storage_location, a.is_active_display 
            FROM assets a
            JOIN cards c ON a.definition_id = c.definition_id
            WHERE c.printed_name ILIKE %s
            ORDER BY c.printed_name ASC
        """, (f"%{search_term}%",))

        results = cur.fetchall()

        if not results:
            print("❌ No assets found matching that name.")
            return

        # Format choices for the user
        choices = []
        for r in results:
            asset_id = r[0]
            name = r[1]
            set_id = r[2]
            run = r[3]
            loc = r[4]
            status = "👁️  Active" if r[5] else "📦 Vault"

            display_str = f"{name} [{set_id.upper()}] ({run}) | Loc: {loc} | {status}"
            choices.append({"name": display_str, "value": asset_id})

        selected_asset_id = inquirer.select(
            message="Select Asset to Edit:",
            choices=choices
        ).execute()

        # STEP 2: Fetch Current Asset Data
        cur.execute("""
            SELECT storage_location, is_active_display, has_swirl, curator_notes, 
                   surface_grade, corners_grade, edges_grade, centering_grade
            FROM assets 
            WHERE asset_id = %s
        """, (selected_asset_id,))

        current_data = cur.fetchone()

        loc, active, swirl, notes, surf, corn, edge, cent = current_data

        # Helper to convert None to empty string for the prompt
        def safe_str(val): return str(val) if val is not None else ""

        print("\n✏️  Press Enter to keep current values, or type to overwrite.")

        # STEP 3: Prompt for New Values (pre-filled with current)
        new_loc = inquirer.text(
            message="Storage Location:", default=safe_str(loc)).execute()
        new_active = inquirer.confirm(
            message="Actively Displayed?", default=active).execute()
        new_swirl = inquirer.confirm(
            message="Has Swirl?", default=swirl).execute()

        # The native InquirerPy validation lock for editing
        new_notes = inquirer.text(
            message=f"Curator Notes (Max {MAX_NOTE_LENGTH} chars):",
            default=safe_str(notes),
            validate=lambda result: len(result) <= MAX_NOTE_LENGTH,
            invalid_message=f"Notes must be {MAX_NOTE_LENGTH} characters or fewer."
        ).execute()

        print("\n  ↳ Subgrades (1-10). Leave blank to clear/skip.")

        def get_grade(name, current_val):
            ans = inquirer.text(
                message=f"    {name} Grade:",
                default=safe_str(current_val),
                validate=lambda x: x == "" or (
                    x.isdigit() and 1 <= int(x) <= 10),
                invalid_message="Must be an integer between 1 and 10."
            ).execute()
            return int(ans) if ans else None

        new_surf = get_grade("Surface", surf)
        new_corn = get_grade("Corners", corn)
        new_edge = get_grade("Edges", edge)
        new_cent = get_grade("Centering", cent)

        # STEP 4: Execute Update
        print("\n🚀 Updating SilphDB...")

        cur.execute("""
            UPDATE assets
            SET storage_location = %s,
                is_active_display = %s,
                has_swirl = %s,
                curator_notes = %s,
                surface_grade = %s,
                corners_grade = %s,
                edges_grade = %s,
                centering_grade = %s
            WHERE asset_id = %s
        """, (new_loc, new_active, new_swirl, new_notes, new_surf, new_corn, new_edge, new_cent, selected_asset_id))

        conn.commit()
        print(f"✅ Successfully updated Asset ID: {selected_asset_id}")

    except Exception as e:
        print(f"❌ Error updating asset: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
