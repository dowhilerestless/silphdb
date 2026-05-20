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


def get_generation(pkmn_id):
    """Maps Pokedex ID to its respective Generation (Gen 1-9)."""
    if 1 <= pkmn_id <= 151:
        return 1
    if 152 <= pkmn_id <= 251:
        return 2
    if 252 <= pkmn_id <= 386:
        return 3
    if 387 <= pkmn_id <= 493:
        return 4
    if 494 <= pkmn_id <= 649:
        return 5
    if 650 <= pkmn_id <= 721:
        return 6
    if 722 <= pkmn_id <= 809:
        return 7
    if 810 <= pkmn_id <= 905:
        return 8
    if pkmn_id >= 906:
        return 9
    return 0


def seed_pokedex():
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        print("📡 Connecting to PokeAPI (Species Mode)...")
        limit = 1025
        response = requests.get(
            f"https://pokeapi.co/api/v2/pokemon-species?limit={limit}")
        response.raise_for_status()
        results = response.json()['results']

        print(f"✅ Found {len(results)} species. Processing transaction...")

        for index, entry in enumerate(results, start=1):
            species_data = requests.get(entry['url']).json()
            pkmn_id = species_data['id']
            name = entry['name'].capitalize()

            # --- NEW: Extract Evolution Chain ID ---
            evo_chain_id = None
            evo_data = species_data.get('evolution_chain')
            if evo_data:
                evo_url = evo_data['url']
                # Extracts the '1' from 'https://pokeapi.co/api/v2/evolution-chain/1/'
                evo_chain_id = int(evo_url.rstrip('/').split('/')[-1])

            variety_url = species_data['varieties'][0]['pokemon']['url']
            pkmn_data = requests.get(variety_url).json()

            types = [t['type']['name'].capitalize()
                     for t in pkmn_data['types']]
            primary = types[0]
            secondary = types[1] if len(types) > 1 else None

            gen = get_generation(pkmn_id)

            # --- UPDATED: Insert Statement now includes evolution_chain_id ---
            cur.execute(
                """
                INSERT INTO pokedex (pokedex_number, pokemon_name, generation, primary_type, secondary_type, evolution_chain_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (pokedex_number) 
                DO UPDATE SET 
                    pokemon_name = EXCLUDED.pokemon_name,
                    primary_type = EXCLUDED.primary_type,
                    secondary_type = EXCLUDED.secondary_type,
                    evolution_chain_id = EXCLUDED.evolution_chain_id;
                """,
                (pkmn_id, name, gen, primary, secondary, evo_chain_id)
            )

            if index % 100 == 0:
                print(f"📦 Staged: {index}/{len(results)}...")

        print("🚀 Sending COMMIT to SilphDB...")
        conn.commit()
        print("🏆 Transaction successful. Pokedex is fully loaded.")

    except Exception as e:
        print(f"❌ Error detected. Rolling back transaction: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            cur.close()
            conn.close()


if __name__ == "__main__":
    seed_pokedex()
