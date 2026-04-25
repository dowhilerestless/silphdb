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


def seed_sets():
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        print("📡 Fetching Master Set List from Pokemon TCG API...")
        response = requests.get("https://api.pokemontcg.io/v2/sets")
        response.raise_for_status()
        sets_data = response.json()['data']

        print(f"✅ Found {len(sets_data)} official sets. Ingesting...")

        for s in sets_data:
            set_id = s['id']
            name = s['name']
            series = s['series']
            release_date = s.get('releaseDate', '1999/01/01').replace('/', '-')

            cur.execute(
                """
                INSERT INTO sets (set_id, set_name, series, release_date)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (set_id) DO UPDATE SET 
                    set_name = EXCLUDED.set_name,
                    series = EXCLUDED.series,
                    release_date = EXCLUDED.release_date;
                """,
                (set_id, name, series, release_date)
            )

        conn.commit()
        print("🏆 SilphDB Master Sets loaded successfully.")

    except Exception as e:
        print(f"❌ Error seeding sets: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            cur.close()
            conn.close()


if __name__ == "__main__":
    seed_sets()
