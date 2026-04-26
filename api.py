import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

load_dotenv()

app = FastAPI(
    title="SilphDB Embedded API",
    description="Backend engine for the physical binder hardware display.",
    version="1.0.0"
)

app.mount("/sprites", StaticFiles(directory="sprites"), name="sprites")


def get_db_connection():
    try:
        return psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            cursor_factory=RealDictCursor
        )
    except Exception as e:
        print(f"Database connection error: {e}")
        return None


BINDER_PROFILES = {
    "151": ("base1", "base2", "base3", "basep"),
    "rocket": ("tr1",),
    "gym": ("g1", "g2")
}


@app.get("/")
def read_root():
    return {"status": "SilphDB API is online."}


@app.get("/api/asset/{asset_id}")
def get_asset_provenance(asset_id: str):
    """
    Fetches the full provenance and metadata for a specific physical asset.
    Perfect for populating the binder's digital ticker.
    """
    conn = get_db_connection()
    if not conn:
        raise HTTPException(
            status_code=500, detail="Database connection failed")

    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT 
                c.printed_name,
                c.set_id,
                c.print_run,
                a.storage_location,
                a.curator_notes,
                a.surface_grade,
                a.corners_grade,
                a.edges_grade,
                a.centering_grade,
                ae.event_date,
                ae.counterparty,
                ae.item_cost
            FROM assets a
            JOIN cards c ON a.definition_id = c.definition_id
            JOIN acquisition_events ae ON a.event_id = ae.event_id
            WHERE a.asset_id = %s
        """, (asset_id,))

        result = cur.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Asset not found")

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()


@app.get("/api/binder/{binder_id}/page/{page_num}")
def get_binder_page(binder_id: str, page_num: int):
    """
    Fetches 9 slots for a binder page based on a predefined Binder Profile.
    Supports multiple sets per binder using a SQL IN clause.
    """
    if binder_id not in BINDER_PROFILES:
        raise HTTPException(
            status_code=404, detail="Binder profile not recognized.")

    if page_num < 1 or page_num > 17:
        raise HTTPException(
            status_code=400, detail="Page must be between 1 and 17")

    allowed_sets = BINDER_PROFILES[binder_id]

    start_dex = ((page_num - 1) * 9) + 1
    end_dex = page_num * 9

    conn = get_db_connection()
    if not conn:
        raise HTTPException(
            status_code=500, detail="Database connection failed")

    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT 
                p.pokedex_number,
                p.pokemon_name,
                c.printed_name,
                c.set_id,
                c.print_run,
                a.asset_id,
                a.has_swirl,
                a.surface_grade,
                a.corners_grade,
                a.edges_grade,
                a.centering_grade,
                a.curator_notes,
                ae.event_date,
                ae.item_cost,
                ae.counterparty
            FROM pokedex p
            -- IN clause allows the card to be from Base, Jungle, Fossil, or Promo
            LEFT JOIN cards c ON p.pokedex_number = c.pokedex_number AND c.set_id IN %s
            LEFT JOIN assets a ON c.definition_id = a.definition_id AND a.is_active_display = TRUE
            LEFT JOIN acquisition_events ae ON a.event_id = ae.event_id
            WHERE p.pokedex_number BETWEEN %s AND %s
            ORDER BY p.pokedex_number ASC
        """, (allowed_sets, start_dex, end_dex))

        results = cur.fetchall()

        payload = {
            "binder_profile": binder_id,
            "included_sets": allowed_sets,
            "page_number": page_num,
            "pokedex_range": f"#{start_dex} - #{end_dex}",
            "slots": results
        }

        return payload

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()
