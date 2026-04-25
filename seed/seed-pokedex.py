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
    if 1 <= pkmn_id <= 151: return 1
    if 152 <= pkmn_id <= 251: return 2
    if 252 <= pkmn_id <= 386: return 3
    if 387 <= pkmn_id <= 493: return 4
    if 494 <= pkmn_id <= 649: return 5
    if 650 <= pkmn_id <= 721: return 6
    if 722 <= pkmn_id <= 809: return 7
    if 810 <= pkmn_id <= 905: return 8
    if pkmn_id >= 906: return 9
    return 0

def seed_pokedex():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        print("Connecting to PokeAPI...")
        limit = 1025 
        response = requests.get(f"https://pokeapi.co/api/v2/pokemon?limit={limit}")
        results = response.json()['results']
        
        print(f"✅ Found {len(results)} entries. Starting ingestion...")

        for index, entry in enumerate(results, start=1):
            pkmn_data = requests.get(entry['url']).json()
            
            pkmn_id = pkmn_data['id']
            if pkmn_id > 10000:
                continue

            name = pkmn_data['name'].capitalize()
            gen = get_generation(pkmn_id)
            
            types = [t['type']['name'].capitalize() for t in pkmn_data['types']]
            primary = types[0]
            secondary = types[1] if len(types) > 1 else None

            cur.execute(
                """
                INSERT INTO pokedex (pokedex_number, pokemon_name, generation, primary_type, secondary_type)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (pokedex_number) DO NOTHING;
                """,
                (pkmn_id, name, gen, primary, secondary)
            )

            if index % 20 == 0:
                print(f"Progress: {index}/{len(results)} processed...")

        conn.commit()
        print("\nSilphDB Seeding Complete! The Pokedex is fully loaded.")

    except Exception as e:
        print(f"❌ Error during seeding: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()

if __name__ == "__main__":
    seed_pokedex()