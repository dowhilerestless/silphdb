import os
import requests
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS")
}


def seed_vintage_151_cards():
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        print("📡 Fetching Vintage 151 Definitions from Pokemon TCG API...")

        # Querying specifically for Gen 1 Pokémon in the classic WotC sets
        query = 'nationalPokedexNumbers:[1 TO 151] (set.id:base1 OR set.id:base2 OR set.id:base3 OR set.id:base4 OR set.id:base5)'
        page = 1
        more_pages = True
        total_staged = 0

        while more_pages:
            url = f"https://api.pokemontcg.io/v2/cards?q={query}&page={page}&pageSize=250"
            response = requests.get(url)
            response.raise_for_status()

            data = response.json()
            cards_data = data['data']

            if not cards_data:
                more_pages = False
                break

            for c in cards_data:
                printed_name = c['name']

                dex_numbers = c.get('nationalPokedexNumbers', [None])
                pokedex_number = dex_numbers[0] if dex_numbers else 0

                set_id = c['set']['id'].upper()
                card_number = c.get('number', '0')
                artist = c.get('artist', 'Unknown')

                print_run = "Unlimited"
                language = "EN"

                # --- NEW: Extracting Rarity & Calculating Finish ---
                rarity = c.get('rarity', 'Unknown')
                finish = "Holo" if "Holo" in rarity else "Non-Holo"

                # Keeping the ID mathematically unique for Holo/Non-Holo overlaps
                definition_id = f"{pokedex_number}-{set_id}-{card_number}-{language}-{print_run[:3].upper()}"

                cur.execute(
                    """
                    INSERT INTO cards (definition_id, pokedex_number, set_id, card_number, print_run, language, finish, rarity, artist, printed_name)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (definition_id) DO UPDATE SET 
                        pokedex_number = EXCLUDED.pokedex_number,
                        set_id = EXCLUDED.set_id,
                        card_number = EXCLUDED.card_number,
                        print_run = EXCLUDED.print_run,
                        language = EXCLUDED.language,
                        finish = EXCLUDED.finish,
                        rarity = EXCLUDED.rarity,
                        artist = EXCLUDED.artist,
                        printed_name = EXCLUDED.printed_name;
                    """,
                    (definition_id, pokedex_number, set_id.lower(), card_number,
                     print_run, language, finish, rarity, artist, printed_name)
                )
                total_staged += 1

            print(
                f"📦 Page {page} Staged. Total definitions parsed: {total_staged}")

            if len(cards_data) < 250:
                more_pages = False
            else:
                page += 1

        print("🚀 Sending COMMIT to SilphDB...")
        conn.commit()
        print(
            f"🏆 Transaction successful. {total_staged} Vintage Card Definitions loaded.")

    except Exception as e:
        print(f"❌ Error detected. Rolling back transaction: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            cur.close()
            conn.close()


if __name__ == "__main__":
    seed_vintage_151_cards()
