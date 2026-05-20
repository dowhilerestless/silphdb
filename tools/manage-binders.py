import os
import psycopg2
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


def manage_sets(conn, cur, binder_id):
    """Sub-menu for adding/removing sets from a specific binder."""
    while True:
        # Fetch currently linked sets
        cur.execute("""
            SELECT bs.set_id, s.set_name 
            FROM binder_sets bs
            LEFT JOIN sets s ON bs.set_id = s.set_id
            WHERE bs.binder_id = %s
        """, (binder_id,))
        current_sets = cur.fetchall()

        print(f"\n--- 📂 Linked Sets for Binder [{binder_id}] ---")
        if not current_sets:
            print("  (No sets linked yet)")
        else:
            for s in current_sets:
                set_name = s[1] if s[1] else "Unknown Set"
                print(f"  • {s[0]} ({set_name})")

        action = inquirer.select(
            message="Manage Sets:",
            choices=["Add Set", "Remove Set", "Back to Main Menu"]
        ).execute()

        if action == "Back to Main Menu":
            break

        elif action == "Add Set":
            # Fetch all available sets from the main DB to let them pick
            cur.execute(
                "SELECT set_id, set_name, series FROM sets ORDER BY release_date DESC")
            all_sets = cur.fetchall()

            # Filter out sets that are already in the binder
            current_set_ids = [s[0] for s in current_sets]
            available_sets = [
                s for s in all_sets if s[0] not in current_set_ids]

            if not available_sets:
                print("❌ No more available sets to add.")
                continue

            set_choices = [
                {"name": f"[{s[2]}] {s[1]} ({s[0]})", "value": s[0]} for s in available_sets]

            set_to_add = inquirer.fuzzy(
                message="Select Set to Add:",
                choices=set_choices,
                match_exact=False,
            ).execute()

            cur.execute(
                "INSERT INTO binder_sets (binder_id, set_id) VALUES (%s, %s)", (binder_id, set_to_add))
            conn.commit()
            print(f"✅ Added {set_to_add} to binder {binder_id}.")

        elif action == "Remove Set":
            if not current_sets:
                print("❌ No sets to remove.")
                continue

            remove_choices = [
                {"name": f"{s[0]} ({s[1]})", "value": s[0]} for s in current_sets]
            set_to_remove = inquirer.select(
                message="Select Set to Remove:",
                choices=remove_choices
            ).execute()

            cur.execute(
                "DELETE FROM binder_sets WHERE binder_id = %s AND set_id = %s", (binder_id, set_to_remove))
            conn.commit()
            print(f"🗑️ Removed {set_to_remove} from binder {binder_id}.")


def main():
    conn = get_db_connection()
    cur = conn.cursor()

    print("--- 📚 SilphDB Binder Manager ---")

    try:
        while True:
            print("\n" + "="*35)

            main_action = inquirer.select(
                message="Main Menu:",
                choices=["Create New Binder",
                         "Edit Existing Binder", "Delete Binder", "Exit"]
            ).execute()

            if main_action == "Exit":
                break

            elif main_action == "Create New Binder":
                binder_id = inquirer.text(
                    message="Binder ID (e.g., '151', 'johto-master'):"
                ).execute().lower().replace(" ", "-")

                display_name = inquirer.text(
                    message="Display Name (e.g., 'Kanto Master Set'):"
                ).execute()

                max_dex = inquirer.text(
                    message="Max Pokedex Number (e.g., 151, 251):",
                    default="151",
                    validate=NumberValidator(),
                    invalid_message="Must be a number."
                ).execute()

                try:
                    cur.execute("""
                        INSERT INTO binders (binder_id, display_name, max_pokedex_id) 
                        VALUES (%s, %s, %s)
                    """, (binder_id, display_name, int(max_dex)))
                    conn.commit()
                    print(f"\n✅ Binder '{binder_id}' created successfully!")

                    manage_now = inquirer.confirm(
                        message="Link sets to this binder now?", default=True).execute()
                    if manage_now:
                        manage_sets(conn, cur, binder_id)

                except psycopg2.IntegrityError:
                    conn.rollback()
                    print(f"❌ Binder ID '{binder_id}' already exists!")

            elif main_action in ["Edit Existing Binder", "Delete Binder"]:
                # Fetch existing binders
                cur.execute(
                    "SELECT binder_id, display_name, max_pokedex_id FROM binders ORDER BY binder_id ASC")
                binders = cur.fetchall()

                if not binders:
                    print("❌ No binders exist in the database.")
                    continue

                binder_choices = [
                    {"name": f"{b[1]} ({b[0]}) - Max Dex: {b[2]}", "value": b[0]} for b in binders]

                selected_binder = inquirer.select(
                    message=f"Select Binder to {main_action.split()[0]}:",
                    choices=binder_choices
                ).execute()

                if main_action == "Delete Binder":
                    confirm = inquirer.confirm(
                        message=f"⚠️ WARNING: Delete binder '{selected_binder}'? This cannot be undone.", default=False).execute()
                    if confirm:
                        # Must delete from mapping table first due to foreign key constraints
                        cur.execute(
                            "DELETE FROM binder_sets WHERE binder_id = %s", (selected_binder,))
                        cur.execute(
                            "DELETE FROM binders WHERE binder_id = %s", (selected_binder,))
                        conn.commit()
                        print(
                            f"🗑️ Binder '{selected_binder}' deleted completely.")

                elif main_action == "Edit Existing Binder":
                    edit_action = inquirer.select(
                        message="What do you want to edit?",
                        choices=[
                            "Edit Core Details (Name/Max Dex)", "Manage Linked Sets", "Cancel"]
                    ).execute()

                    if edit_action == "Manage Linked Sets":
                        manage_sets(conn, cur, selected_binder)

                    elif edit_action == "Edit Core Details (Name/Max Dex)":
                        # Fetch current details
                        cur.execute(
                            "SELECT display_name, max_pokedex_id FROM binders WHERE binder_id = %s", (selected_binder,))
                        current_data = cur.fetchone()

                        new_name = inquirer.text(
                            message="Display Name:",
                            default=current_data[0]
                        ).execute()

                        new_max = inquirer.text(
                            message="Max Pokedex Number:",
                            default=str(current_data[1]),
                            validate=NumberValidator()
                        ).execute()

                        cur.execute("""
                            UPDATE binders 
                            SET display_name = %s, max_pokedex_id = %s 
                            WHERE binder_id = %s
                        """, (new_name, int(new_max), selected_binder))
                        conn.commit()
                        print(f"✅ Binder '{selected_binder}' updated.")

    except Exception as e:
        print(f"\n❌ A fatal error occurred: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()
        print("👋 Exiting SilphDB Binder Manager.")


if __name__ == "__main__":
    main()
