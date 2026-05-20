import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timedelta
import random

load_dotenv()

app = FastAPI(
    title="SilphDB Embedded API",
    description="Backend engine for the physical binder hardware display.",
    version="1.2.1"
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


@app.get("/")
def read_root():
    return {"status": "SilphDB API is online."}


@app.get("/api/asset/{asset_id}")
def get_asset_provenance(asset_id: str):
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
                a.grading_status,
                a.raw_condition,
                a.surface_grade,
                a.corners_grade,
                a.edges_grade,
                a.centering_grade,
                e.event_date,
                e.platform,
                e.counterparty,
                e.item_amount
            FROM assets a
            JOIN cards c ON a.definition_id = c.definition_id
            JOIN events e ON a.acquisition_event_id = e.event_id
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


@app.get("/api/binder/{binder_id}/stats")
def get_binder_stats(binder_id: str, mode: str = "BINDER"):
    """Calculates completion percentage and fetches the latest acquisition."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(
            status_code=500, detail="Database connection failed")

    cur = conn.cursor()

    try:
        cur.execute(
            "SELECT max_pokedex_id FROM binders WHERE binder_id = %s", (binder_id,))
        binder_config = cur.fetchone()

        if not binder_config:
            raise HTTPException(
                status_code=404, detail="Binder profile not found.")

        max_dex = binder_config['max_pokedex_id']

        cur.execute(
            "SELECT set_id FROM binder_sets WHERE binder_id = %s", (binder_id,))
        allowed_sets = tuple(row['set_id'] for row in cur.fetchall())

        if not allowed_sets:
            return {"collected": 0, "total": max_dex, "percentage": 0, "latest_asset": None}

        display_filter = "AND a.is_active_display = TRUE" if mode == "BINDER" else ""

        # 1. Calculate Completion Stats
        cur.execute(f"""
            SELECT COUNT(DISTINCT p.pokedex_number) as collected_count
            FROM pokedex p
            JOIN cards c ON p.pokedex_number = c.pokedex_number
            JOIN assets a ON c.definition_id = a.definition_id
            WHERE p.pokedex_number <= %s 
              AND c.set_id IN %s 
              {display_filter}
        """, (max_dex, allowed_sets))

        collected = cur.fetchone()['collected_count']
        percentage = (collected / max_dex) * 100 if max_dex > 0 else 0

        # 2. Fetch the latest acquired asset in this binder
        cur.execute(f"""
            SELECT 
                p.pokedex_number,
                p.pokemon_name,
                c.printed_name,
                c.set_id,
                c.finish,        
                a.asset_id,
                a.has_swirl,
                a.surface_grade,
                a.grading_status,
                a.raw_condition,
                a.curator_notes,
                e.event_date,
                e.item_amount as item_cost,
                e.platform,
                e.counterparty as seller_name
            FROM pokedex p
            JOIN cards c ON p.pokedex_number = c.pokedex_number
            JOIN assets a ON c.definition_id = a.definition_id
            JOIN events e ON a.acquisition_event_id = e.event_id
            WHERE p.pokedex_number <= %s 
              AND c.set_id IN %s 
              {display_filter}
            ORDER BY e.event_date DESC, a.asset_id DESC
            LIMIT 1
        """, (max_dex, allowed_sets))

        latest_asset = cur.fetchone()

        return {
            "binder_id": binder_id,
            "collected": collected,
            "total": max_dex,
            "percentage": round(percentage, 1),
            "latest_asset": latest_asset
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()


@app.get("/api/binder/{binder_id}/page/{page_num}")
def get_binder_page(binder_id: str, page_num: int, mode: str = "BINDER"):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(
            status_code=500, detail="Database connection failed")

    cur = conn.cursor()

    try:
        cur.execute(
            "SELECT max_pokedex_id FROM binders WHERE binder_id = %s", (binder_id,))
        binder_config = cur.fetchone()

        if not binder_config:
            raise HTTPException(
                status_code=404, detail="Binder profile not found.")

        max_dex = binder_config['max_pokedex_id']

        cur.execute(
            "SELECT set_id FROM binder_sets WHERE binder_id = %s", (binder_id,))
        allowed_sets = tuple(row['set_id'] for row in cur.fetchall())

        start_dex = ((page_num - 1) * 9) + 1
        end_dex = min(page_num * 9, max_dex)

        if start_dex > max_dex:
            return {"slots": [], "page_number": page_num, "message": "End of Binder"}

        display_filter = "AND a.is_active_display = TRUE" if mode == "BINDER" else ""

        cur.execute(f"""
            SELECT DISTINCT ON (p.pokedex_number)
                p.pokedex_number,
                p.pokemon_name,
                c.printed_name,
                c.set_id,
                c.finish,        
                a.asset_id,
                a.has_swirl,
                a.surface_grade,
                a.curator_notes,
                a.grading_status,
                a.raw_condition,
                e.event_date,
                e.item_amount as item_cost,
                e.platform,
                e.counterparty as seller_name
            FROM pokedex p
            LEFT JOIN cards c ON p.pokedex_number = c.pokedex_number AND c.set_id IN %s
            LEFT JOIN assets a ON c.definition_id = a.definition_id {display_filter}
            LEFT JOIN events e ON a.acquisition_event_id = e.event_id
            WHERE p.pokedex_number BETWEEN %s AND %s
            ORDER BY p.pokedex_number ASC, a.asset_id DESC NULLS LAST
        """, (allowed_sets, start_dex, end_dex))

        results = cur.fetchall()

        return {
            "binder_id": binder_id,
            "page_number": page_num,
            "pokedex_range": f"#{start_dex} - #{end_dex}",
            "slots": results
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()


@app.get("/api/binder/{binder_id}/stats/vitals")
def get_vitals(binder_id: str, mode: str = "BINDER"):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(
            status_code=500, detail="Database connection failed")

    cur = conn.cursor()

    try:
        # Get binder config
        cur.execute(
            "SELECT max_pokedex_id FROM binders WHERE binder_id = %s", (binder_id,))
        binder_config = cur.fetchone()
        if not binder_config:
            raise HTTPException(status_code=404, detail="Binder not found")

        max_dex = binder_config['max_pokedex_id']

        # Get allowed sets
        cur.execute(
            "SELECT set_id FROM binder_sets WHERE binder_id = %s", (binder_id,))
        allowed_sets = tuple(row['set_id'] for row in cur.fetchall())
        if not allowed_sets:
            return {"error": "No sets mapped to this binder."}

        display_filter = "AND a.is_active_display = TRUE" if mode == "BINDER" else ""

        # 1. Aggregate Statistics (Updated to just use item_amount for Spend)
        cur.execute(f"""
            SELECT 
                COUNT(DISTINCT p.pokedex_number) as collected_count,
                SUM(e.item_amount) as total_spent, 
                SUM(e.shipping_amount + e.tax_amount) as total_overhead,
                COUNT(CASE WHEN e.event_date >= CURRENT_DATE - INTERVAL '30 days' THEN 1 END) as thirty_day_count,
                COUNT(CASE WHEN e.event_date >= CURRENT_DATE - INTERVAL '90 days' THEN 1 END) as ninety_day_count,
                COUNT(CASE WHEN e.item_amount = 0 THEN 1 END) as zero_cost_count
            FROM pokedex p
            JOIN cards c ON p.pokedex_number = c.pokedex_number
            JOIN assets a ON c.definition_id = a.definition_id
            JOIN events e ON a.acquisition_event_id = e.event_id
            WHERE p.pokedex_number <= %s AND c.set_id IN %s {display_filter}
        """, (max_dex, allowed_sets))

        core_stats = cur.fetchone()
        collected = core_stats['collected_count'] or 0
        total_spent = float(core_stats['total_spent'] or 0.0)

        # Calculate Total Sold (Items that have a disposition event)
        cur.execute("""
            SELECT COALESCE(SUM(e.item_amount), 0) as total_sold
            FROM events e
            JOIN assets a ON e.event_id = a.disposition_event_id
            JOIN cards c ON a.definition_id = c.definition_id
            WHERE c.set_id IN %s
        """, (allowed_sets,))
        sold_row = cur.fetchone()
        total_sold = float(sold_row['total_sold']) if sold_row else 0.0

        net_spend = total_spent - total_sold

        cards_left = max_dex - collected
        percentage = (collected / max_dex) * 100 if max_dex > 0 else 0

        # 2. Windowed Velocity ETA
        eta_str = "STALLED (NO RECENT ACTIVITY)"
        recent_acquisitions = core_stats['ninety_day_count'] or 0

        if recent_acquisitions > 0 and cards_left > 0:
            velocity_window = 90
            cards_per_day = recent_acquisitions / velocity_window
            days_to_completion = cards_left / cards_per_day
            eta_date = datetime.now() + timedelta(days=days_to_completion)
            eta_str = eta_date.strftime("%B %Y").upper()

        overhead = float(core_stats['total_overhead'] or 0.0)
        overhead_pct = (overhead / total_spent * 100) if total_spent > 0 else 0

        # Calculate true average
        paid_cards = collected - core_stats['zero_cost_count']
        true_average = total_spent / paid_cards if paid_cards > 0 else 0.0

        # --- NEW: STATUS & SPEND LEVEL LOGIC ---

        # 1. Calculate Median Cost (Ignoring zero-cost gifts/trades)
        cur.execute(f"""
            SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY e.item_amount) as median_cost
            FROM assets a
            JOIN cards c ON a.definition_id = c.definition_id
            JOIN events e ON a.acquisition_event_id = e.event_id
            WHERE e.item_amount > 0 AND c.set_id IN %s {display_filter}
        """, (allowed_sets,))
        median_row = cur.fetchone()
        median_cost = float(
            median_row['median_cost'] if median_row and median_row['median_cost'] else 0.0)

        # 2. Determine Efficiency
        efficiency = (true_average / median_cost) if median_cost > 0 else 1.0

        # 3. Determine Spend Level (With rotating spice)
        spent = float(total_spent)
        if spent <= 50:
            level_options = ["JUST BROWSING", "TESTING THE WATERS"]
        elif spent <= 150:
            level_options = ["GETTING INTO IT", "WARMING UP"]
        elif spent <= 300:
            level_options = [
                "YOU MEANT TO DO THIS?", "NO TURNING BACK"]
        elif spent <= 600:
            level_options = [
                "SUNK COST FALLACY", "IT'S GETTING REAL", "FUNDING THE POST OFFICE"]
        elif spent <= 1000:
            level_options = [
                "LASER FOCUSED", "HIDE THE WALLET"]
        elif spent <= 2000:
            level_options = [
                "RESPECT", "HEAVY HITTER"]
        else:
            level_options = [
                "SEEK HELP", "FINANCIALLY COMPROMISED", "LIQUIDATING THE 401K"]

        spend_level = random.choice(level_options)

        # --- NEW: Total Sold Level ---
        sold = float(total_sold)
        if sold <= 0:
            sold_options = ["DIAMOND HANDS", "HOARDER", "ONE-WAY BLACK HOLE"]
        elif sold <= 50:
            sold_options = ["CHUMP CHANGE", "SOLD A DUPE"]
        elif sold <= 200:
            sold_options = ["FLIPPING CASUALLY", "MAKING SPACE"]
        elif sold <= 500:
            sold_options = ["SIDE HUSTLE", "MERCHANT IN TRAINING"]
        elif sold <= 1000:
            sold_options = ["RESPECTABLE VENDOR", "LIQUIDATING ASSETS"]
        else:
            sold_options = ["ARBITRAGE KING",
                            "WOLF OF TCGPLAYER", "UNOFFICIAL LGS"]

        sold_level = random.choice(sold_options)

        # --- NEW: Net Spend Level ---
        net = float(net_spend)
        if net < 0:
            net_options = ["ACTUALLY PROFITABLE?!",
                           "INFINITE MONEY GLITCH", "PLAYING WITH HOUSE MONEY", "ACCIDENTAL ARBITRAGE"]
        elif net <= 50:
            net_options = ["BASICALLY FREE"]
        elif net <= 250:
            net_options = ["CHEAP ENTERTAINMENT", "MODEST DAMAGE"]
        elif net <= 600:
            net_options = ["ACCEPTABLE LOSSES", "COST OF DOING BUSINESS"]
        elif net <= 1200:
            net_options = [
                "COULD'VE BOUGHT SO MUCH ROTISSERIE CHICKEN", "OOF"]
        else:
            net_options = ["FINANCIAL RUIN",
                           "COULD'VE SPONSORED A SERVER RACK"]

        net_level = random.choice(net_options)

        # 4. Determine Priority Status
        momentum = core_stats['thirty_day_count'] or 0
        status_str = "DIRECTIONALLY CONFUSED"  # Default fallback

        if percentage >= 70:
            if percentage >= 95:
                status_str = "OBSESSED"
            elif percentage >= 85:
                status_str = "ALMOST THERE"
            else:
                status_str = "CLOSING IN"
        elif efficiency > 1.2:
            if efficiency > 1.5:
                status_str = "FINANCIALLY RECKLESS"
            elif efficiency > 1.3 and momentum >= 10:
                status_str = "TILT BUYING"
            elif efficiency > 1.3:
                status_str = "OVERPAYING FOR CONVENIENCE"
            else:
                status_str = "IMPULSIVE BUYER"
        elif efficiency < 0.9 and momentum >= 4:
            if momentum >= 10:
                status_str = "MARKET ASSASSIN"
            elif momentum >= 7:
                status_str = "EFFICIENT HUNTER"
            elif efficiency < 0.7:
                status_str = "SPREADSHEET WARRIOR"
            else:
                status_str = "PATIENT SNIPER"
        elif momentum >= 8 and percentage < 70:
            if momentum >= 12:
                status_str = "ON A MISSION"
            else:
                status_str = "DIALED IN"
        elif momentum <= 2:
            if momentum == 0:
                status_str = "COLLECTION ABANDONED"
            else:
                status_str = "CASUALLY COLLECTING"
        else:
            # Chaotic Fallback variations based on spend
            if spent > 500:
                status_str = "BUYING VIBES, NOT STRATEGY"
            else:
                status_str = "WANDERING COLLECTOR"

        return {
            "spent": total_spent,
            "sold": total_sold,
            "net": net_spend,
            "percentage": round(percentage, 1),
            "cards_left": cards_left,
            "eta": eta_str,
            "overhead": float(overhead),
            "overhead_pct": round(overhead_pct, 1),
            "true_average": round(true_average, 2),
            "thirty_day_velocity": momentum,
            "zero_cost_count": core_stats['zero_cost_count'],
            "spend_level": spend_level,
            "sold_level": sold_level,
            "net_level": net_level,
            "collector_status": status_str
        }

    finally:
        cur.close()
        conn.close()


@app.get("/api/binder/{binder_id}/stats/archetypes")
def get_archetypes(binder_id: str, mode: str = "BINDER"):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(
            status_code=500, detail="Database connection failed")

    cur = conn.cursor()

    try:
        cur.execute(
            "SELECT max_pokedex_id FROM binders WHERE binder_id = %s", (binder_id,))
        binder_config = cur.fetchone()
        if not binder_config:
            raise HTTPException(status_code=404, detail="Binder not found")

        max_dex = binder_config['max_pokedex_id']
        cur.execute(
            "SELECT set_id FROM binder_sets WHERE binder_id = %s", (binder_id,))
        allowed_sets = tuple(row['set_id'] for row in cur.fetchall())

        if not allowed_sets:
            return {"error": "No sets mapped to this binder."}

        display_filter = "AND a.is_active_display = TRUE" if mode == "BINDER" else ""

        # 1. Rarity Skew (Holo vs Non-Holo)
        cur.execute(f"""
            SELECT c.finish, COUNT(a.asset_id) as count
            FROM assets a
            JOIN cards c ON a.definition_id = c.definition_id
            JOIN pokedex p ON c.pokedex_number = p.pokedex_number
            WHERE p.pokedex_number <= %s AND c.set_id IN %s {display_filter}
            GROUP BY c.finish
        """, (max_dex, allowed_sets))

        finish_data = cur.fetchall()
        holo_count = sum(row['count'] for row in finish_data if row['finish'] in [
                         'Holo', 'Reverse-Holo'])
        non_holo_count = sum(row['count']
                             for row in finish_data if row['finish'] == 'Non-Holo')
        total_cards = holo_count + non_holo_count

        holo_pct = (holo_count / total_cards * 100) if total_cards > 0 else 0
        non_holo_pct = (non_holo_count / total_cards *
                        100) if total_cards > 0 else 0

        if holo_pct > 60:
            rarity_label = random.choice(["HOLO ADDICT", "MAGPIE SYNDROME"])
        elif non_holo_pct > 75:
            rarity_label = random.choice(
                ["AVOIDING EXPENSIVE CARDS", "MATTE FINISH MINIMALIST"])
        else:
            rarity_label = "BALANCED COLLECTOR"

        # 2. Collector Type (Condition Snob vs Binder Filler)
        cur.execute(f"""
            SELECT a.grading_status, a.raw_condition, a.surface_grade
            FROM assets a
            JOIN cards c ON a.definition_id = c.definition_id
            JOIN pokedex p ON c.pokedex_number = p.pokedex_number
            WHERE p.pokedex_number <= %s AND c.set_id IN %s {display_filter}
        """, (max_dex, allowed_sets))

        condition_data = cur.fetchall()
        cond_weights = {'M': 10, 'NM': 8, 'LP': 6,
                        'MP': 4, 'HP': 2, 'DMG': 1, 'UKN': 5}

        total_score = 0
        scored_cards = 0
        for row in condition_data:
            if row['grading_status'] == 'Graded' and row['surface_grade']:
                total_score += row['surface_grade']
                scored_cards += 1
            elif row['grading_status'] == 'Raw' and row['raw_condition']:
                total_score += cond_weights.get(row['raw_condition'], 5)
                scored_cards += 1

        avg_condition = (total_score / scored_cards) if scored_cards > 0 else 0

        if avg_condition >= 8:
            condition_label = random.choice(
                ["CONDITION SNOB (NM/M)", "LOUPE INSPECTOR"])
        elif avg_condition <= 5:
            condition_label = random.choice(
                ["BINDER FILLER (LP/MP)", "WASHING MACHINE SURVIVOR"])
        else:
            condition_label = "PRAGMATIC TRAINER"

        # 3. Hoarder vs Hunter
        cur.execute(f"""
            SELECT COUNT(a.asset_id) as total_assets, COUNT(DISTINCT e.event_id) as total_events, SUM(e.item_amount) as total_spend
            FROM assets a
            JOIN events e ON a.acquisition_event_id = e.event_id
            JOIN cards c ON a.definition_id = c.definition_id
            WHERE e.item_amount > 0 AND c.set_id IN %s {display_filter}
        """, (allowed_sets,))

        event_data = cur.fetchone()
        t_assets = event_data['total_assets'] or 0
        t_events = event_data['total_events'] or 0
        t_spend = event_data['total_spend'] or 0

        cards_per_event = (t_assets / t_events) if t_events > 0 else 0
        avg_cost = (t_spend / t_assets) if t_assets > 0 else 0

        if cards_per_event > 3 and avg_cost < 20:
            hunter_label = random.choice(
                ["BULK HOARDER", "CARDBOARD RECYCLER"])
        elif cards_per_event <= 1.5 and avg_cost > 40:
            hunter_label = random.choice(["SNIPER / HUNTER", "BOUNTY HUNTER"])
        else:
            hunter_label = "STANDARD ENTHUSIAST"

        # 4. Highest & Lowest Records
        cur.execute(f"""
            SELECT c.printed_name, e.item_amount, e.event_date
            FROM assets a
            JOIN cards c ON a.definition_id = c.definition_id
            JOIN events e ON a.acquisition_event_id = e.event_id
            WHERE e.item_amount > 0 AND c.set_id IN %s {display_filter}
            ORDER BY e.item_amount DESC LIMIT 1
        """, (allowed_sets,))
        most_expensive = cur.fetchone()

        cur.execute(f"""
            SELECT c.printed_name, e.item_amount, e.event_date
            FROM assets a
            JOIN cards c ON a.definition_id = c.definition_id
            JOIN events e ON a.acquisition_event_id = e.event_id
            WHERE e.item_amount > 0 AND c.set_id IN %s {display_filter}
            ORDER BY e.item_amount ASC LIMIT 1
        """, (allowed_sets,))
        cheapest = cur.fetchone()

        return {
            "holo_pct": round(holo_pct, 1),
            "non_holo_pct": round(non_holo_pct, 1),
            "rarity_label": rarity_label,
            "condition_label": condition_label,
            "hunter_label": hunter_label,
            "most_expensive": most_expensive,
            "cheapest": cheapest
        }

    finally:
        cur.close()
        conn.close()


@app.get("/api/binder/{binder_id}/stats/sourcing")
def get_sourcing_stats(binder_id: str, mode: str = "BINDER"):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(
            status_code=500, detail="Database connection failed")

    cur = conn.cursor()

    try:
        cur.execute(
            "SELECT max_pokedex_id FROM binders WHERE binder_id = %s", (binder_id,))
        binder_config = cur.fetchone()
        if not binder_config:
            raise HTTPException(status_code=404, detail="Binder not found")

        max_dex = binder_config['max_pokedex_id']
        cur.execute(
            "SELECT set_id FROM binder_sets WHERE binder_id = %s", (binder_id,))
        allowed_sets = tuple(row['set_id'] for row in cur.fetchall())

        if not allowed_sets:
            return {"error": "No sets mapped to this binder."}

        display_filter = "AND a.is_active_display = TRUE" if mode == "BINDER" else ""

        # 1. Platforms
        cur.execute(f"""
            SELECT e.platform, COUNT(a.asset_id) as volume, SUM(e.item_amount) as spent
            FROM assets a
            JOIN events e ON a.acquisition_event_id = e.event_id
            JOIN cards c ON a.definition_id = c.definition_id
            JOIN pokedex p ON c.pokedex_number = p.pokedex_number
            WHERE p.pokedex_number <= %s AND c.set_id IN %s {display_filter}
            GROUP BY e.platform
        """, (max_dex, allowed_sets))
        platforms = cur.fetchall()

        total_vol = sum(p['volume'] for p in platforms)
        total_spend = float(sum(p['spent'] for p in platforms) or 0)

        vol_leader = max(
            platforms, key=lambda x: x['volume']) if platforms else None
        spend_leader = max(
            platforms, key=lambda x: x['spent']) if platforms else None

        plat_archetype = "WANDERING NOMAD"
        if vol_leader:
            vol_pct = (vol_leader['volume'] / total_vol) * \
                100 if total_vol > 0 else 0
            name = (vol_leader['platform'] or "UNKNOWN").upper()
            if vol_pct > 80:
                if "EBAY" in name:
                    plat_archetype = "CORPORATE SPONSOR"
                elif "TCGPLAYER" in name:
                    plat_archetype = "SYNDICATE BUYER"
                elif "DISCORD" in name or "REDDIT" in name:
                    plat_archetype = "TRADE CARTEL"
                else:
                    plat_archetype = f"{name} LOYALIST"
            elif vol_pct > 50:
                plat_archetype = f"PREFERS {name}"
            else:
                plat_archetype = "OPPORTUNIST (DIVERSIFIED)"

        # 2. Sellers (Counterparties)
        cur.execute(f"""
            SELECT e.counterparty, COUNT(a.asset_id) as volume, SUM(e.item_amount) as spent
            FROM assets a
            JOIN events e ON a.acquisition_event_id = e.event_id
            JOIN cards c ON a.definition_id = c.definition_id
            JOIN pokedex p ON c.pokedex_number = p.pokedex_number
            WHERE p.pokedex_number <= %s AND c.set_id IN %s AND e.item_amount > 0 {display_filter}
            GROUP BY e.counterparty
        """, (max_dex, allowed_sets))
        sellers = cur.fetchall()

        reg_seller = max(
            sellers, key=lambda x: x['volume']) if sellers else None
        ben_seller = max(
            sellers, key=lambda x: x['spent']) if sellers else None
        unique_sellers = len(sellers)

        # 3. Spend Skew & Temporal Sourcing
        cur.execute(f"""
            SELECT e.item_amount, EXTRACT(DOW FROM e.event_date) as buy_day
            FROM assets a
            JOIN events e ON a.acquisition_event_id = e.event_id
            JOIN cards c ON a.definition_id = c.definition_id
            JOIN pokedex p ON c.pokedex_number = p.pokedex_number
            WHERE p.pokedex_number <= %s AND c.set_id IN %s AND e.item_amount > 0 {display_filter}
            ORDER BY e.item_amount DESC
        """, (max_dex, allowed_sets))
        all_purchases = cur.fetchall()

        top_5_spend = sum(float(row['item_amount'])
                          for row in all_purchases[:5])
        top_heavy_pct = (top_5_spend / total_spend *
                         100) if total_spend > 0 else 0

        amounts = sorted([float(row['item_amount']) for row in all_purchases])
        median_cost = amounts[len(amounts)//2] if amounts else 0

        days = [row['buy_day']
                for row in all_purchases if row['buy_day'] is not None]
        if days:
            import collections
            busiest_day_num = collections.Counter(days).most_common(1)[0][0]
            # PostgreSQL DOW: 0 = Sunday, 6 = Saturday
            day_names = ["SUNDAY", "MONDAY", "TUESDAY",
                         "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"]
            busiest_day = day_names[int(busiest_day_num)]
        else:
            busiest_day = "UNKNOWN"

        return {
            "vol_leader_name": vol_leader['platform'] if vol_leader else "N/A",
            "vol_leader_count": vol_leader['volume'] if vol_leader else 0,
            "spend_leader_name": spend_leader['platform'] if spend_leader else "N/A",
            "spend_leader_amount": float(spend_leader['spent']) if spend_leader else 0,
            "plat_archetype": plat_archetype,
            "reg_seller_name": reg_seller['counterparty'] if reg_seller else "N/A",
            "reg_seller_count": reg_seller['volume'] if reg_seller else 0,
            "ben_seller_name": ben_seller['counterparty'] if ben_seller else "N/A",
            "ben_seller_amount": float(ben_seller['spent']) if ben_seller else 0,
            "unique_sellers": unique_sellers,
            "total_assets": total_vol,
            "median_cost": float(median_cost),
            "top_heavy_pct": round(top_heavy_pct, 1),
            "busiest_day": busiest_day
        }

    finally:
        cur.close()
        conn.close()


@app.get("/api/binder/{binder_id}/stats/lineage")
def get_lineage_stats(binder_id: str, mode: str = "BINDER"):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(
            status_code=500, detail="Database connection failed")

    cur = conn.cursor()

    try:
        cur.execute(
            "SELECT max_pokedex_id FROM binders WHERE binder_id = %s", (binder_id,))
        binder_config = cur.fetchone()
        if not binder_config:
            raise HTTPException(status_code=404, detail="Binder not found")

        max_dex = binder_config['max_pokedex_id']
        cur.execute(
            "SELECT set_id FROM binder_sets WHERE binder_id = %s", (binder_id,))
        allowed_sets = tuple(row['set_id'] for row in cur.fetchall())

        if not allowed_sets:
            return {"error": "No sets mapped to this binder."}

        display_filter = "AND a.is_active_display = TRUE" if mode == "BINDER" else ""

        # 1. Evolutionary Lineage
        cur.execute("""
            SELECT evolution_chain_id, COUNT(pokedex_number) as total_in_chain
            FROM pokedex
            WHERE pokedex_number <= %s AND evolution_chain_id IS NOT NULL
            GROUP BY evolution_chain_id
        """, (max_dex,))
        family_sizes = {row['evolution_chain_id']
            : row['total_in_chain'] for row in cur.fetchall()}

        cur.execute(f"""
            SELECT p.evolution_chain_id, COUNT(DISTINCT p.pokedex_number) as collected_in_chain
            FROM pokedex p
            JOIN cards c ON p.pokedex_number = c.pokedex_number
            JOIN assets a ON c.definition_id = a.definition_id
            WHERE p.pokedex_number <= %s AND c.set_id IN %s {display_filter} AND p.evolution_chain_id IS NOT NULL
            GROUP BY p.evolution_chain_id
        """, (max_dex, allowed_sets))
        collected_sizes = {row['evolution_chain_id']
            : row['collected_in_chain'] for row in cur.fetchall()}

        completed_lines = 0
        one_away = 0
        orphans = 0

        for chain_id, total in family_sizes.items():
            if total > 1:  # We only care about species that actually evolve
                collected = collected_sizes.get(chain_id, 0)
                if collected == total:
                    completed_lines += 1
                elif collected == total - 1:
                    one_away += 1
                elif collected == 1:
                    orphans += 1

        # 2. Set DNA & Elemental Skew
        cur.execute(f"""
            SELECT s.set_name, COUNT(a.asset_id) as count
            FROM assets a
            JOIN cards c ON a.definition_id = c.definition_id
            JOIN sets s ON c.set_id = s.set_id
            JOIN pokedex p ON c.pokedex_number = p.pokedex_number
            WHERE p.pokedex_number <= %s AND c.set_id IN %s {display_filter}
            GROUP BY s.set_name
            ORDER BY count DESC
        """, (max_dex, allowed_sets))
        sets_data = cur.fetchall()

        total_cards = sum(row['count'] for row in sets_data)
        set_distribution = []
        for row in sets_data[:3]:
            pct = (row['count'] / total_cards * 100) if total_cards > 0 else 0
            set_distribution.append({
                "name": str(row['set_name']).upper(),
                "pct": float(pct)
            })

        set_archetype = "BALANCED ERA"
        if sets_data and total_cards > 0:
            top_set_pct = (sets_data[0]['count'] / total_cards) * 100
            top_set_name = str(sets_data[0]['set_name']).upper()
            if top_set_pct >= 70:
                set_archetype = f"{top_set_name} PURIST"
            elif top_set_pct >= 40:
                set_archetype = f"{top_set_name} LEANING"

        cur.execute(f"""
            SELECT p.primary_type, COUNT(a.asset_id) as count
            FROM assets a
            JOIN cards c ON a.definition_id = c.definition_id
            JOIN pokedex p ON c.pokedex_number = p.pokedex_number
            WHERE p.pokedex_number <= %s AND c.set_id IN %s {display_filter}
            GROUP BY p.primary_type
            ORDER BY count DESC LIMIT 1
        """, (max_dex, allowed_sets))
        type_data = cur.fetchone()
        elemental_skew = f"{type_data['primary_type'].upper()}-TYPE MAGNET" if type_data else "NO TYPE DATA"

        # 3. Quality Control & Grid Health
        cur.execute(f"""
            SELECT p.pokemon_name, a.raw_condition, a.surface_grade, a.grading_status
            FROM assets a
            JOIN cards c ON a.definition_id = c.definition_id
            JOIN pokedex p ON p.pokedex_number = c.pokedex_number
            WHERE p.pokedex_number <= %s AND c.set_id IN %s {display_filter}
        """, (max_dex, allowed_sets))
        condition_data = cur.fetchall()

        cond_weights = {'M': 10, 'NM': 8, 'LP': 6,
                        'MP': 4, 'HP': 2, 'DMG': 1, 'UKN': 5}
        total_score = 0
        weakest_score = 99
        weakest_link = "NONE"

        for row in condition_data:
            score = 5
            label = "UKN"
            if row['grading_status'] == 'Graded' and row['surface_grade']:
                score = row['surface_grade']
                label = f"PSA {score}"
            elif row['grading_status'] == 'Raw' and row['raw_condition']:
                score = cond_weights.get(row['raw_condition'], 5)
                label = row['raw_condition']

            total_score += score
            if score < weakest_score:
                weakest_score = score
                weakest_link = f"{str(row['pokemon_name']).upper()} ({label})"

        avg_binder_cond_num = (
            total_score / len(condition_data)) if condition_data else 0

        # Map the numeric average back to the closest condition label
        if avg_binder_cond_num == 0:
            avg_cond_label = "UKN"
        elif avg_binder_cond_num >= 9.0:
            avg_cond_label = "M"
        elif avg_binder_cond_num >= 7.0:
            avg_cond_label = "NM"
        elif avg_binder_cond_num >= 5.0:
            avg_cond_label = "LP"
        elif avg_binder_cond_num >= 3.0:
            avg_cond_label = "MP"
        elif avg_binder_cond_num >= 1.5:
            avg_cond_label = "HP"
        else:
            avg_cond_label = "DMG"

        # Grid Health (Pages 1-17)
        cur.execute(f"""
            SELECT FLOOR((p.pokedex_number - 1) / 9) + 1 AS page_num, COUNT(DISTINCT p.pokedex_number) as filled
            FROM assets a
            JOIN cards c ON a.definition_id = c.definition_id
            JOIN pokedex p ON c.pokedex_number = p.pokedex_number
            WHERE p.pokedex_number <= %s AND c.set_id IN %s {display_filter}
            GROUP BY page_num
        """, (max_dex, allowed_sets))
        page_data = cur.fetchall()

        densest_page_num = "NONE"
        densest_page_pct = 0.0
        ghost_page_num = "NONE"
        ghost_page_pct = 0.0

        import math
        total_pages_possible = math.ceil(max_dex / 9)
        page_dict = {int(row['page_num']): int(row['filled'])
                     for row in page_data}

        if page_dict:
            max_page = max(page_dict, key=page_dict.get)
            densest_page_num = max_page
            densest_page_pct = (page_dict[max_page] / 9) * 100

            min_page = min(page_dict, key=page_dict.get)
            ghost_page_num = min_page
            ghost_page_pct = (page_dict[min_page] / 9) * 100

        return {
            "completed_lines": completed_lines,
            "one_away": one_away,
            "orphans": orphans,
            "set_distribution": set_distribution,
            "set_archetype": set_archetype,
            "elemental_skew": elemental_skew,
            "avg_binder_cond": avg_cond_label,
            "weakest_link": weakest_link,
            "densest_page_num": densest_page_num,
            "densest_page_pct": densest_page_pct,
            "ghost_page_num": ghost_page_num,
            "ghost_page_pct": ghost_page_pct
        }

    finally:
        cur.close()
        conn.close()


@app.get("/api/binder/{binder_id}/stats/archive")
def get_archive_stats(binder_id: str, mode: str = "BINDER"):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(
            status_code=500, detail="Database connection failed")

    cur = conn.cursor()

    try:
        cur.execute(
            "SELECT max_pokedex_id FROM binders WHERE binder_id = %s", (binder_id,))
        binder_config = cur.fetchone()
        if not binder_config:
            raise HTTPException(status_code=404, detail="Binder not found")

        max_dex = binder_config['max_pokedex_id']
        cur.execute(
            "SELECT set_id FROM binder_sets WHERE binder_id = %s", (binder_id,))
        allowed_sets = tuple(row['set_id'] for row in cur.fetchall())

        if not allowed_sets:
            return {"error": "No sets mapped to this binder."}

        display_filter = "AND a.is_active_display = TRUE" if mode == "BINDER" else ""

        # 1. Temporal Reach & Streaks
        cur.execute(f"""
            SELECT DISTINCT e.event_date
            FROM events e
            JOIN assets a ON e.event_id = a.acquisition_event_id
            JOIN cards c ON a.definition_id = c.definition_id
            JOIN pokedex p ON c.pokedex_number = p.pokedex_number
            WHERE p.pokedex_number <= %s AND c.set_id IN %s {display_filter}
            ORDER BY e.event_date ASC
        """, (max_dex, allowed_sets))

        dates_data = cur.fetchall()
        dates = [row['event_date'] for row in dates_data if row['event_date']]

        oldest_date = dates[0].strftime(
            "%b %d, %Y").upper() if dates else "UNKNOWN"
        newest_date = dates[-1].strftime(
            "%b %d, %Y").upper() if dates else "UNKNOWN"

        max_streak = 0
        if dates:
            current_streak = 1
            max_streak = 1
            for i in range(1, len(dates)):
                delta = (dates[i] - dates[i-1]).days
                if delta == 1:
                    current_streak += 1
                    if current_streak > max_streak:
                        max_streak = current_streak
                elif delta > 1:
                    current_streak = 1

        # 2. The Curator's Eye (Artists & Swirls)
        cur.execute(f"""
            SELECT c.artist, COUNT(a.asset_id) as count
            FROM assets a
            JOIN cards c ON a.definition_id = c.definition_id
            JOIN pokedex p ON c.pokedex_number = p.pokedex_number
            WHERE p.pokedex_number <= %s AND c.set_id IN %s AND c.artist IS NOT NULL {display_filter}
            GROUP BY c.artist
            ORDER BY count DESC LIMIT 1
        """, (max_dex, allowed_sets))
        top_artist_data = cur.fetchone()
        top_artist = top_artist_data['artist'].upper(
        ) if top_artist_data else "UNKNOWN"

        cur.execute(f"""
            SELECT 
                COUNT(a.asset_id) as total_assets,
                COUNT(CASE WHEN a.has_swirl = TRUE THEN 1 END) as swirl_count,
                COUNT(CASE WHEN a.curator_notes IS NOT NULL AND a.curator_notes != '' THEN 1 END) as notes_count
            FROM assets a
            JOIN cards c ON a.definition_id = c.definition_id
            JOIN pokedex p ON c.pokedex_number = p.pokedex_number
            WHERE p.pokedex_number <= %s AND c.set_id IN %s {display_filter}
        """, (max_dex, allowed_sets))
        counts = cur.fetchone()

        total_assets = counts['total_assets'] or 0
        swirl_count = counts['swirl_count'] or 0
        doc_rate = (counts['notes_count'] / total_assets *
                    100) if total_assets > 0 else 0

        # 3. Sentiment & Stories (Curator Notes Analysis)
        cur.execute(f"""
            SELECT p.pokemon_name, a.curator_notes
            FROM assets a
            JOIN cards c ON a.definition_id = c.definition_id
            JOIN pokedex p ON p.pokedex_number = c.pokedex_number
            WHERE p.pokedex_number <= %s AND c.set_id IN %s AND a.curator_notes IS NOT NULL {display_filter}
        """, (max_dex, allowed_sets))
        notes_data = cur.fetchall()

        longest_note_pkmn = "NONE"
        longest_note_words = 0
        max_length = 0
        total_words = 0

        for row in notes_data:
            note = row['curator_notes']
            if note:
                word_count = len(note.split())
                total_words += word_count
                if len(note) > max_length:
                    max_length = len(note)
                    longest_note_pkmn = str(row['pokemon_name']).upper()
                    longest_note_words = word_count

        return {
            "oldest_date": oldest_date,
            "newest_date": newest_date,
            "max_streak": max_streak,
            "top_artist": top_artist,
            "swirl_count": swirl_count,
            "doc_rate": float(doc_rate),
            "longest_note_pkmn": longest_note_pkmn,
            "longest_note_words": longest_note_words,
            "total_words": total_words
        }
    finally:
        cur.close()
        conn.close()


@app.get("/api/binder/{binder_id}/collection/collected")
def get_all_collected(binder_id: str, mode: str = "BINDER"):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(
            status_code=500, detail="Database connection failed")

    cur = conn.cursor()

    try:
        cur.execute(
            "SELECT max_pokedex_id FROM binders WHERE binder_id = %s", (binder_id,))
        binder_config = cur.fetchone()
        if not binder_config:
            raise HTTPException(status_code=404, detail="Binder not found")

        max_dex = binder_config['max_pokedex_id']
        cur.execute(
            "SELECT set_id FROM binder_sets WHERE binder_id = %s", (binder_id,))
        allowed_sets = tuple(row['set_id'] for row in cur.fetchall())

        if not allowed_sets:
            return []

        display_filter = "AND a.is_active_display = TRUE" if mode == "BINDER" else ""

        cur.execute(f"""
            SELECT 
                p.pokedex_number,
                p.pokemon_name,
                c.printed_name,
                c.set_id,
                c.finish,        
                a.asset_id,
                a.has_swirl,
                a.surface_grade,
                a.grading_status,
                a.raw_condition,
                a.curator_notes,
                e.event_date,
                e.item_amount as item_cost,
                e.platform,
                e.counterparty as seller_name
            FROM pokedex p
            JOIN cards c ON p.pokedex_number = c.pokedex_number
            JOIN assets a ON c.definition_id = a.definition_id
            JOIN events e ON a.acquisition_event_id = e.event_id
            WHERE p.pokedex_number <= %s AND c.set_id IN %s {display_filter}
        """, (max_dex, allowed_sets))

        return cur.fetchall()

    finally:
        cur.close()
        conn.close()


@app.get("/api/binder/{binder_id}/transactions/{tx_type}")
def get_transactions(binder_id: str, tx_type: str, mode: str = "BINDER"):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(
            status_code=500, detail="Database connection failed")

    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT set_id FROM binder_sets WHERE binder_id = %s", (binder_id,))
        allowed_sets = tuple(row['set_id'] for row in cur.fetchall())

        if not allowed_sets:
            return []

        display_filter = "AND a.is_active_display = TRUE" if mode == "BINDER" else ""

        if tx_type == "spend":
            cur.execute(f"""
                SELECT c.printed_name, e.event_date, e.item_amount, e.platform, e.counterparty
                FROM assets a
                JOIN events e ON a.acquisition_event_id = e.event_id
                JOIN cards c ON a.definition_id = c.definition_id
                WHERE c.set_id IN %s {display_filter} AND e.item_amount > 0
                ORDER BY e.event_date DESC, e.event_id ASC
            """, (allowed_sets,))
        elif tx_type == "sold":
            cur.execute("""
                SELECT c.printed_name, e.event_date, e.item_amount, e.platform, e.counterparty
                FROM assets a
                JOIN events e ON a.disposition_event_id = e.event_id
                JOIN cards c ON a.definition_id = c.definition_id
                WHERE c.set_id IN %s AND e.item_amount > 0
                ORDER BY e.event_date DESC, e.event_id ASC
            """, (allowed_sets,))
        elif tx_type == "zero_cost":
            cur.execute(f"""
                SELECT c.printed_name, e.event_date, e.item_amount, e.platform, e.counterparty
                FROM assets a
                JOIN events e ON a.acquisition_event_id = e.event_id
                JOIN cards c ON a.definition_id = c.definition_id
                WHERE c.set_id IN %s {display_filter} AND e.item_amount = 0
                ORDER BY e.event_date DESC, e.event_id ASC
            """, (allowed_sets,))
        else:
            return []

        return cur.fetchall()

    finally:
        cur.close()
        conn.close()


@app.get("/api/binder/{binder_id}/deepdive/cost")
def get_cost_deepdive(binder_id: str, mode: str = "BINDER"):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(
            status_code=500, detail="Database connection failed")

    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT max_pokedex_id FROM binders WHERE binder_id = %s", (binder_id,))
        binder_config = cur.fetchone()
        if not binder_config:
            raise HTTPException(status_code=404, detail="Binder not found")

        max_dex = binder_config['max_pokedex_id']

        cur.execute(
            "SELECT set_id FROM binder_sets WHERE binder_id = %s", (binder_id,))
        allowed_sets = tuple(row['set_id'] for row in cur.fetchall())

        if not allowed_sets:
            return {"error": "No sets mapped."}

        display_filter = "AND a.is_active_display = TRUE" if mode == "BINDER" else ""

        cur.execute(f"""
            SELECT 
                COUNT(DISTINCT p.pokedex_number) as total_assets,
                SUM(e.item_amount) as total_spent,
                COUNT(CASE WHEN e.item_amount = 0 THEN 1 END) as free_assets,
                COUNT(CASE WHEN e.item_amount > 0 THEN 1 END) as paid_assets
            FROM pokedex p
            JOIN cards c ON p.pokedex_number = c.pokedex_number
            JOIN assets a ON c.definition_id = a.definition_id
            JOIN events e ON a.acquisition_event_id = e.event_id
            WHERE p.pokedex_number <= %s AND c.set_id IN %s {display_filter}
        """, (max_dex, allowed_sets))

        data = cur.fetchone()
        total_assets = data['total_assets'] or 0
        total_spent = float(data['total_spent'] or 0.0)
        free_assets = data['free_assets'] or 0
        paid_assets = data['paid_assets'] or 0

        true_avg = (total_spent / paid_assets) if paid_assets > 0 else 0.0
        raw_avg = (total_spent / total_assets) if total_assets > 0 else 0.0

        return {
            "true_average": true_avg,
            "raw_average": raw_avg,
            "total_spent": total_spent,
            "total_assets": total_assets,
            "paid_assets": paid_assets,
            "free_assets": free_assets
        }
    finally:
        cur.close()
        conn.close()


@app.get("/api/binder/{binder_id}/deepdive/overhead")
def get_overhead_deepdive(binder_id: str, mode: str = "BINDER"):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(
            status_code=500, detail="Database connection failed")

    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT max_pokedex_id FROM binders WHERE binder_id = %s", (binder_id,))
        binder_config = cur.fetchone()
        if not binder_config:
            raise HTTPException(status_code=404, detail="Binder not found")

        max_dex = binder_config['max_pokedex_id']
        cur.execute(
            "SELECT set_id FROM binder_sets WHERE binder_id = %s", (binder_id,))
        allowed_sets = tuple(row['set_id'] for row in cur.fetchall())

        if not allowed_sets:
            return {"error": "No sets mapped."}

        display_filter = "AND a.is_active_display = TRUE" if mode == "BINDER" else ""

        # 1. Global Overhead Stats
        cur.execute(f"""
            SELECT 
                COUNT(DISTINCT a.asset_id) as total_assets,
                SUM(e.shipping_amount) as total_shipping,
                SUM(e.tax_amount) as total_tax,
                SUM(e.shipping_amount + e.tax_amount) as total_overhead
            FROM pokedex p
            JOIN cards c ON p.pokedex_number = c.pokedex_number
            JOIN assets a ON c.definition_id = a.definition_id
            JOIN events e ON a.acquisition_event_id = e.event_id
            WHERE p.pokedex_number <= %s AND c.set_id IN %s {display_filter}
        """, (max_dex, allowed_sets))

        global_data = cur.fetchone()
        total_assets = global_data['total_assets'] or 0
        total_shipping = float(global_data['total_shipping'] or 0.0)
        total_tax = float(global_data['total_tax'] or 0.0)
        total_overhead = float(global_data['total_overhead'] or 0.0)

        shipping_pct = (total_shipping / total_overhead *
                        100) if total_overhead > 0 else 0
        tax_pct = (total_tax / total_overhead *
                   100) if total_overhead > 0 else 0
        per_asset_leakage = (
            total_overhead / total_assets) if total_assets > 0 else 0

        # 2. Platform Efficiency
        cur.execute(f"""
            SELECT 
                e.platform,
                SUM(e.shipping_amount + e.tax_amount) as plat_overhead,
                SUM(e.item_amount) as plat_spend
            FROM pokedex p
            JOIN cards c ON p.pokedex_number = c.pokedex_number
            JOIN assets a ON c.definition_id = a.definition_id
            JOIN events e ON a.acquisition_event_id = e.event_id
            WHERE p.pokedex_number <= %s AND c.set_id IN %s {display_filter} AND e.item_amount > 0
            GROUP BY e.platform
        """, (max_dex, allowed_sets))

        plat_data = cur.fetchall()
        platforms = []

        for row in plat_data:
            plat = row['platform'] or 'UNKNOWN'
            plat_spend = float(row['plat_spend'] or 0.0)
            plat_ovr = float(row['plat_overhead'] or 0.0)

            # Only rank platforms where we actually spent money
            if plat_spend > 0:
                pct = (plat_ovr / plat_spend) * 100
                platforms.append({
                    "name": str(plat).upper()[:15],
                    "overhead_pct": pct,
                    "overhead_amt": plat_ovr
                })

        # Sort from lowest overhead % (most efficient) to highest
        platforms.sort(key=lambda x: x['overhead_pct'])

        return {
            "total_overhead": total_overhead,
            "shipping_pct": shipping_pct,
            "tax_pct": tax_pct,
            "per_asset_leakage": per_asset_leakage,
            "platform_ranking": platforms
        }
    finally:
        cur.close()
        conn.close()


@app.get("/api/binder/{binder_id}/deepdive/forecast")
def get_forecast_deepdive(binder_id: str, mode: str = "BINDER"):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(
            status_code=500, detail="Database connection failed")

    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT max_pokedex_id FROM binders WHERE binder_id = %s", (binder_id,))
        binder_config = cur.fetchone()
        if not binder_config:
            raise HTTPException(status_code=404, detail="Binder not found")

        max_dex = binder_config['max_pokedex_id']
        cur.execute(
            "SELECT set_id FROM binder_sets WHERE binder_id = %s", (binder_id,))
        allowed_sets = tuple(row['set_id'] for row in cur.fetchall())

        if not allowed_sets:
            return {"error": "No sets mapped."}

        display_filter = "AND a.is_active_display = TRUE" if mode == "BINDER" else ""

        # Query trailing 30 and 90 day metrics
        cur.execute(f"""
            SELECT 
                COUNT(DISTINCT p.pokedex_number) as collected_count,
                COUNT(DISTINCT CASE WHEN e.event_date >= CURRENT_DATE - INTERVAL '30 days' THEN p.pokedex_number END) as count_30d,
                SUM(CASE WHEN e.event_date >= CURRENT_DATE - INTERVAL '30 days' THEN e.item_amount ELSE 0 END) as spend_30d,
                COUNT(DISTINCT CASE WHEN e.event_date >= CURRENT_DATE - INTERVAL '90 days' THEN p.pokedex_number END) as count_90d,
                SUM(CASE WHEN e.event_date >= CURRENT_DATE - INTERVAL '90 days' THEN e.item_amount ELSE 0 END) as spend_90d
            FROM pokedex p
            JOIN cards c ON p.pokedex_number = c.pokedex_number
            JOIN assets a ON c.definition_id = a.definition_id
            JOIN events e ON a.acquisition_event_id = e.event_id
            WHERE p.pokedex_number <= %s AND c.set_id IN %s {display_filter}
        """, (max_dex, allowed_sets))

        data = cur.fetchone()
        collected = data['collected_count'] or 0
        cards_left = max_dex - collected

        count_30d = data['count_30d'] or 0
        spend_90d = float(data['spend_90d'] or 0.0)
        count_90d = data['count_90d'] or 0

        # Calculate monthly averages based on the 90-day window
        burn_rate_monthly = spend_90d / 3.0
        velocity_90d_avg = count_90d / 3.0

        # Shift Calculation (Comparing last 30 days to the 90-day average)
        if velocity_90d_avg > 0:
            shift_pct = ((count_30d - velocity_90d_avg) /
                         velocity_90d_avg) * 100
        else:
            shift_pct = 100.0 if count_30d > 0 else 0.0

        shift_dir = "↑" if shift_pct >= 0 else "↓"
        shift_word = "FASTER" if shift_pct >= 0 else "SLOWER"

        # ETA Calculation
        eta_str = "STALLED (NO VELOCITY)"
        if count_90d > 0 and cards_left > 0:
            # Use exact 90-day math to match the Vitals page perfectly
            cards_per_day = count_90d / 90.0
            days_to_completion = cards_left / cards_per_day
            eta_date = datetime.now() + timedelta(days=days_to_completion)
            eta_str = eta_date.strftime("%B %Y").upper()
        elif cards_left <= 0:
            eta_str = "COMPLETED"

        return {
            "burn_rate_monthly": burn_rate_monthly,
            "shift_pct": abs(shift_pct),
            "shift_dir": shift_dir,
            "shift_word": shift_word,
            "count_30d": count_30d,
            "velocity_90d_avg": velocity_90d_avg,
            "eta_str": eta_str,
            "cards_left": cards_left
        }
    finally:
        cur.close()
        conn.close()


@app.get("/api/binder/{binder_id}/deepdive/netspend")
def get_netspend_deepdive(binder_id: str, mode: str = "BINDER"):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(
            status_code=500, detail="Database connection failed")

    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT set_id FROM binder_sets WHERE binder_id = %s", (binder_id,))
        allowed_sets = tuple(row['set_id'] for row in cur.fetchall())

        if not allowed_sets:
            return {"error": "No sets mapped."}

        display_filter = "AND a.is_active_display = TRUE" if mode == "BINDER" else ""

        # 1. True Average & Subsidized Assets
        cur.execute(f"""
            SELECT SUM(e.item_amount) as total_spent, COUNT(a.asset_id) as paid_assets
            FROM assets a
            JOIN events e ON a.acquisition_event_id = e.event_id
            JOIN cards c ON a.definition_id = c.definition_id
            WHERE c.set_id IN %s {display_filter} AND e.item_amount > 0
        """, (allowed_sets,))

        acq_data = cur.fetchone()
        spent = float(acq_data['total_spent'] or 0)
        paid_count = acq_data['paid_assets'] or 0
        true_avg = (spent / paid_count) if paid_count > 0 else 0

        # 2. Flipping ROI
        cur.execute("""
            SELECT 
                SUM(e_disp.item_amount) as total_revenue, 
                SUM(e_acq.item_amount) as total_cogs
            FROM assets a
            JOIN events e_disp ON a.disposition_event_id = e_disp.event_id
            JOIN events e_acq ON a.acquisition_event_id = e_acq.event_id
            JOIN cards c ON a.definition_id = c.definition_id
            WHERE c.set_id IN %s
        """, (allowed_sets,))

        roi_data = cur.fetchone()
        revenue = float(roi_data['total_revenue'] or 0)
        cogs = float(roi_data['total_cogs'] or 0)

        roi_pct = ((revenue - cogs) / cogs * 100) if cogs > 0 else 0
        subsidized_cards = (revenue / true_avg) if true_avg > 0 else 0

        # 3. Trailing 3-Month Cashflow
        cur.execute("""
            SELECT 
                TO_CHAR(e.event_date, 'YYYY-MM') as month,
                SUM(CASE WHEN e.event_id = a.acquisition_event_id THEN e.item_amount ELSE 0 END) as spent,
                SUM(CASE WHEN e.event_id = a.disposition_event_id THEN e.item_amount ELSE 0 END) as sold
            FROM events e
            JOIN assets a ON (e.event_id = a.acquisition_event_id OR e.event_id = a.disposition_event_id)
            JOIN cards c ON a.definition_id = c.definition_id
            WHERE c.set_id IN %s 
              AND e.event_date >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '2 months'
            GROUP BY month
            ORDER BY month ASC
        """, (allowed_sets,))

        cashflow_rows = cur.fetchall()
        cashflow = []
        for row in cashflow_rows:
            month_obj = datetime.strptime(row['month'], '%Y-%m')
            net = float(row['spent'] or 0) - float(row['sold'] or 0)
            cashflow.append({
                "month_label": month_obj.strftime('%B %Y').upper(),
                "spent": float(row['spent'] or 0),
                "sold": float(row['sold'] or 0),
                "net": net
            })

        return {
            "subsidized_cards": subsidized_cards,
            "total_revenue": revenue,
            "roi_pct": roi_pct,
            "cashflow": cashflow
        }
    finally:
        cur.close()
        conn.close()


@app.get("/api/binder/{binder_id}/deepdive/missing")
def get_missing_targets(binder_id: str, mode: str = "BINDER"):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(
            status_code=500, detail="Database connection failed")

    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT max_pokedex_id FROM binders WHERE binder_id = %s", (binder_id,))
        binder_config = cur.fetchone()
        if not binder_config:
            raise HTTPException(status_code=404, detail="Binder not found")

        max_dex = binder_config['max_pokedex_id']
        cur.execute(
            "SELECT set_id FROM binder_sets WHERE binder_id = %s", (binder_id,))
        allowed_sets = tuple(row['set_id'] for row in cur.fetchall())

        if not allowed_sets:
            return []

        display_filter = "AND a.is_active_display = TRUE" if mode == "BINDER" else ""

        # Find pokedex numbers up to max_dex that are NOT in active display assets for these sets
        cur.execute(f"""
            SELECT p.pokedex_number, p.pokemon_name, p.primary_type
            FROM pokedex p
            WHERE p.pokedex_number <= %s 
              AND p.pokedex_number NOT IN (
                  SELECT c.pokedex_number
                  FROM assets a
                  JOIN cards c ON a.definition_id = c.definition_id
                  WHERE c.set_id IN %s {display_filter}
              )
            ORDER BY p.pokedex_number ASC
        """, (max_dex, allowed_sets))

        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


@app.get("/api/binder/{binder_id}/deepdive/holo")
def get_holo_deepdive(binder_id: str, mode: str = "BINDER"):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(
            status_code=500, detail="Database connection failed")

    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT max_pokedex_id FROM binders WHERE binder_id = %s", (binder_id,))
        binder_config = cur.fetchone()
        if not binder_config:
            raise HTTPException(status_code=404, detail="Binder not found")

        max_dex = binder_config['max_pokedex_id']
        cur.execute(
            "SELECT set_id FROM binder_sets WHERE binder_id = %s", (binder_id,))
        allowed_sets = tuple(row['set_id'] for row in cur.fetchall())

        if not allowed_sets:
            return {"error": "No sets mapped."}

        display_filter = "AND a.is_active_display = TRUE" if mode == "BINDER" else ""

        # 1. Spend, Averages, and Collection Counts (Keeping the zero-cost fix!)
        cur.execute(f"""
            SELECT 
                CASE WHEN c.finish IN ('Holo', 'Reverse-Holo') THEN 'Holo' ELSE 'Non-Holo' END as rarity,
                SUM(CASE WHEN e.item_amount > 0 THEN e.item_amount ELSE 0 END) as total_spend,
                COUNT(CASE WHEN e.item_amount > 0 THEN a.asset_id END) as paid_assets,
                COUNT(DISTINCT p.pokedex_number) as distinct_collected
            FROM assets a
            JOIN events e ON a.acquisition_event_id = e.event_id
            JOIN cards c ON a.definition_id = c.definition_id
            JOIN pokedex p ON c.pokedex_number = p.pokedex_number
            WHERE p.pokedex_number <= %s AND c.set_id IN %s {display_filter}
            GROUP BY CASE WHEN c.finish IN ('Holo', 'Reverse-Holo') THEN 'Holo' ELSE 'Non-Holo' END
        """, (max_dex, allowed_sets))

        spend_data = cur.fetchall()
        holo_spend = 0.0
        holo_paid = 0
        holo_collected = 0
        non_spend = 0.0
        non_paid = 0
        non_collected = 0

        for row in spend_data:
            if row['rarity'] == 'Holo':
                holo_spend = float(row['total_spend'] or 0)
                holo_paid = row['paid_assets'] or 0
                holo_collected = row['distinct_collected'] or 0
            else:
                non_spend = float(row['total_spend'] or 0)
                non_paid = row['paid_assets'] or 0
                non_collected = row['distinct_collected'] or 0

        holo_avg = (holo_spend / holo_paid) if holo_paid > 0 else 0
        non_avg = (non_spend / non_paid) if non_paid > 0 else 0

        # 2. RESTORED: Total Possible in Set (for Completion Checklists)
        cur.execute("""
            SELECT 
                CASE WHEN finish IN ('Holo', 'Reverse-Holo') THEN 'Holo' ELSE 'Non-Holo' END as rarity,
                COUNT(DISTINCT pokedex_number) as total_possible
            FROM cards
            WHERE set_id IN %s AND pokedex_number <= %s
            GROUP BY CASE WHEN finish IN ('Holo', 'Reverse-Holo') THEN 'Holo' ELSE 'Non-Holo' END
        """, (allowed_sets, max_dex))

        totals_data = cur.fetchall()
        holo_total = 0
        non_total = 0
        for row in totals_data:
            if row['rarity'] == 'Holo':
                holo_total = row['total_possible'] or 0
            else:
                non_total = row['total_possible'] or 0

        return {
            "holo_spend": holo_spend,
            "holo_avg": holo_avg,
            "holo_collected": holo_collected,
            "holo_total": holo_total,
            "non_spend": non_spend,
            "non_avg": non_avg,
            "non_collected": non_collected,
            "non_total": non_total
        }
    finally:
        cur.close()
        conn.close()


@app.get("/api/binder/{binder_id}/deepdive/extremes")
def get_extremes_deepdive(binder_id: str, mode: str = "BINDER"):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(
            status_code=500, detail="Database connection failed")

    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT max_pokedex_id FROM binders WHERE binder_id = %s", (binder_id,))
        binder_config = cur.fetchone()
        if not binder_config:
            raise HTTPException(status_code=404, detail="Binder not found")

        max_dex = binder_config['max_pokedex_id']
        cur.execute(
            "SELECT set_id FROM binder_sets WHERE binder_id = %s", (binder_id,))
        allowed_sets = tuple(row['set_id'] for row in cur.fetchall())

        if not allowed_sets:
            return {"error": "No sets mapped."}

        display_filter = "AND a.is_active_display = TRUE" if mode == "BINDER" else ""

        # 1. Total Spend and True Average Baseline
        cur.execute(f"""
            SELECT SUM(e.item_amount) as total_spend, COUNT(a.asset_id) as paid_assets
            FROM assets a
            JOIN events e ON a.acquisition_event_id = e.event_id
            JOIN cards c ON a.definition_id = c.definition_id
            WHERE c.set_id IN %s AND e.item_amount > 0 {display_filter}
        """, (allowed_sets,))
        base_data = cur.fetchone()
        total_spend = float(base_data['total_spend'] or 0)
        paid_assets = base_data['paid_assets'] or 0
        true_average = (total_spend / paid_assets) if paid_assets > 0 else 0

        # 2. Most Expensive
        cur.execute(f"""
            SELECT c.printed_name, e.item_amount, e.event_date, e.platform, e.counterparty
            FROM assets a
            JOIN cards c ON a.definition_id = c.definition_id
            JOIN events e ON a.acquisition_event_id = e.event_id
            WHERE e.item_amount > 0 AND c.set_id IN %s {display_filter}
            ORDER BY e.item_amount DESC LIMIT 1
        """, (allowed_sets,))
        most_exp = cur.fetchone()

        # 3. Cheapest
        cur.execute(f"""
            SELECT c.printed_name, e.item_amount, e.event_date, e.platform, e.counterparty
            FROM assets a
            JOIN cards c ON a.definition_id = c.definition_id
            JOIN events e ON a.acquisition_event_id = e.event_id
            WHERE e.item_amount > 0 AND c.set_id IN %s {display_filter}
            ORDER BY e.item_amount ASC LIMIT 1
        """, (allowed_sets,))
        cheapest = cur.fetchone()

        return {
            "total_spend": total_spend,
            "true_average": true_average,
            "most_expensive": most_exp,
            "cheapest": cheapest
        }
    finally:
        cur.close()
        conn.close()


@app.get("/api/binder/{binder_id}/deepdive/top_seller_ledger")
def get_top_seller_ledger(binder_id: str, mode: str = "BINDER"):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(
            status_code=500, detail="Database connection failed")

    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT set_id FROM binder_sets WHERE binder_id = %s", (binder_id,))
        allowed_sets = tuple(row['set_id'] for row in cur.fetchall())

        if not allowed_sets:
            return {"seller_name": "UNKNOWN", "transactions": []}

        display_filter = "AND a.is_active_display = TRUE" if mode == "BINDER" else ""

        # 1. Identify the Top Seller by Volume
        cur.execute(f"""
            SELECT e.counterparty, COUNT(a.asset_id) as volume
            FROM assets a
            JOIN events e ON a.acquisition_event_id = e.event_id
            JOIN cards c ON a.definition_id = c.definition_id
            WHERE c.set_id IN %s AND e.item_amount > 0 AND e.counterparty IS NOT NULL {display_filter}
            GROUP BY e.counterparty
            ORDER BY volume DESC LIMIT 1
        """, (allowed_sets,))
        top_seller_row = cur.fetchone()

        if not top_seller_row:
            return {"seller_name": "UNKNOWN", "transactions": []}

        seller_name = top_seller_row['counterparty']

        # 2. Fetch all transactions for that seller
        cur.execute(f"""
            SELECT c.printed_name, e.event_date, e.item_amount, e.platform, e.counterparty
            FROM assets a
            JOIN events e ON a.acquisition_event_id = e.event_id
            JOIN cards c ON a.definition_id = c.definition_id
            WHERE c.set_id IN %s AND e.counterparty = %s {display_filter}
            ORDER BY e.event_date DESC, e.event_id ASC
        """, (allowed_sets, seller_name))

        return {
            "seller_name": seller_name,
            "transactions": cur.fetchall()
        }
    finally:
        cur.close()
        conn.close()


@app.get("/api/binder/{binder_id}/deepdive/sourcing_leaders")
def get_sourcing_leaders_deepdive(binder_id: str, mode: str = "BINDER"):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(
            status_code=500, detail="Database connection failed")

    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT set_id FROM binder_sets WHERE binder_id = %s", (binder_id,))
        allowed_sets = tuple(row['set_id'] for row in cur.fetchall())

        if not allowed_sets:
            return {"error": "No sets mapped."}

        display_filter = "AND a.is_active_display = TRUE" if mode == "BINDER" else ""

        # 1. Get Global Totals
        cur.execute(f"""
            SELECT COUNT(a.asset_id) as total_vol, SUM(e.item_amount) as total_spend
            FROM assets a
            JOIN events e ON a.acquisition_event_id = e.event_id
            JOIN cards c ON a.definition_id = c.definition_id
            WHERE c.set_id IN %s {display_filter}
        """, (allowed_sets,))
        totals = cur.fetchone()
        total_vol = totals['total_vol'] or 0
        total_spend = float(totals['total_spend'] or 0)

        # 2. Get Platform Stats
        cur.execute(f"""
            SELECT e.platform, COUNT(a.asset_id) as volume, SUM(e.item_amount) as spent
            FROM assets a
            JOIN events e ON a.acquisition_event_id = e.event_id
            JOIN cards c ON a.definition_id = c.definition_id
            WHERE c.set_id IN %s {display_filter}
            GROUP BY e.platform
            ORDER BY volume DESC
        """, (allowed_sets,))
        platforms = cur.fetchall()

        vol_leader = platforms[0] if platforms else None
        spend_leader = max(platforms, key=lambda x: float(
            x['spent'] or 0)) if platforms else None

        vol_stats = {}
        if vol_leader:
            v_vol = vol_leader['volume']
            v_spend = float(vol_leader['spent'] or 0)
            vol_stats = {
                "name": vol_leader['platform'] or "UNKNOWN",
                "volume": v_vol,
                "vol_pct": (v_vol / total_vol * 100) if total_vol > 0 else 0,
                "avg_cost": (v_spend / v_vol) if v_vol > 0 else 0
            }

        spend_stats = {}
        if spend_leader:
            s_vol = spend_leader['volume']
            s_spend = float(spend_leader['spent'] or 0)
            spend_stats = {
                "name": spend_leader['platform'] or "UNKNOWN",
                "spend": s_spend,
                "spend_pct": (s_spend / total_spend * 100) if total_spend > 0 else 0,
                "volume": s_vol
            }

        # 3. Format Spread
        cur.execute(f"""
            SELECT e.counterparty, COUNT(a.asset_id) as volume
            FROM assets a
            JOIN events e ON a.acquisition_event_id = e.event_id
            JOIN cards c ON a.definition_id = c.definition_id
            WHERE c.set_id IN %s AND e.counterparty IS NOT NULL {display_filter}
            GROUP BY e.counterparty
            ORDER BY volume DESC
        """, (allowed_sets,))
        counterparties = cur.fetchall()
        spread = [{"name": c['counterparty'] or "UNKNOWN",
                   "count": c['volume']} for c in counterparties]

        # 4. Temporal Heatmap (Day of Week distribution)
        cur.execute(f"""
            SELECT EXTRACT(DOW FROM e.event_date) as dow, COUNT(a.asset_id) as count
            FROM assets a
            JOIN events e ON a.acquisition_event_id = e.event_id
            JOIN cards c ON a.definition_id = c.definition_id
            WHERE c.set_id IN %s AND e.item_amount > 0 {display_filter}
            GROUP BY dow
        """, (allowed_sets,))
        dow_data = cur.fetchall()
        day_counts = [0] * 7
        for row in dow_data:
            if row['dow'] is not None:
                day_counts[int(row['dow'])] = row['count']

        # 5. Spending Signature (Price buckets & Middle Card & Top 5)
        cur.execute(f"""
            SELECT c.printed_name, e.item_amount, e.platform, e.event_date
            FROM assets a
            JOIN events e ON a.acquisition_event_id = e.event_id
            JOIN cards c ON a.definition_id = c.definition_id
            WHERE c.set_id IN %s AND e.item_amount > 0 {display_filter}
            ORDER BY e.item_amount ASC
        """, (allowed_sets,))
        all_purchases = cur.fetchall()

        buckets = {"< $10": 0, "$10 - $25": 0,
                   "$25 - $50": 0, "$50 - $100": 0, "$100+": 0}
        for p in all_purchases:
            amt = float(p['item_amount'])
            if amt < 10:
                buckets["< $10"] += 1
            elif amt < 25:
                buckets["$10 - $25"] += 1
            elif amt < 50:
                buckets["$25 - $50"] += 1
            elif amt < 100:
                buckets["$50 - $100"] += 1
            else:
                buckets["$100+"] += 1

        middle_card = all_purchases[len(
            all_purchases)//2] if all_purchases else None

        top_5_assets = sorted(all_purchases, key=lambda x: float(
            x['item_amount']), reverse=True)[:5]
        for t in top_5_assets:
            t['spend_pct'] = (float(t['item_amount']) /
                              total_spend * 100) if total_spend > 0 else 0

        return {
            "vol_leader": vol_stats,
            "spend_leader": spend_stats,
            "spread": spread,
            "day_counts": day_counts,
            "price_buckets": buckets,
            "middle_card": middle_card,
            "top_5_assets": top_5_assets,
            "total_spend": total_spend
        }
    finally:
        cur.close()
        conn.close()


@app.get("/api/binder/{binder_id}/deepdive/top_funded_ledger")
def get_top_funded_ledger(binder_id: str, mode: str = "BINDER"):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(
            status_code=500, detail="Database connection failed")

    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT set_id FROM binder_sets WHERE binder_id = %s", (binder_id,))
        allowed_sets = tuple(row['set_id'] for row in cur.fetchall())

        if not allowed_sets:
            return {"seller_name": "UNKNOWN", "transactions": [], "share_of_wallet": 0}

        display_filter = "AND a.is_active_display = TRUE" if mode == "BINDER" else ""

        cur.execute(f"""
            SELECT SUM(e.item_amount) as total_spend
            FROM assets a
            JOIN events e ON a.acquisition_event_id = e.event_id
            JOIN cards c ON a.definition_id = c.definition_id
            WHERE c.set_id IN %s AND e.item_amount > 0 {display_filter}
        """, (allowed_sets,))
        tot_row = cur.fetchone()
        total_spend = float(tot_row['total_spend'] or 0)

        cur.execute(f"""
            SELECT e.counterparty, SUM(e.item_amount) as spend
            FROM assets a
            JOIN events e ON a.acquisition_event_id = e.event_id
            JOIN cards c ON a.definition_id = c.definition_id
            WHERE c.set_id IN %s AND e.item_amount > 0 AND e.counterparty IS NOT NULL {display_filter}
            GROUP BY e.counterparty
            ORDER BY spend DESC LIMIT 1
        """, (allowed_sets,))
        top_seller_row = cur.fetchone()

        if not top_seller_row:
            return {"seller_name": "UNKNOWN", "transactions": [], "share_of_wallet": 0}

        seller_name = top_seller_row['counterparty']
        seller_spend = float(top_seller_row['spend'])
        share_of_wallet = (seller_spend / total_spend *
                           100) if total_spend > 0 else 0

        cur.execute(f"""
            SELECT c.printed_name, e.event_date, e.item_amount, e.platform, e.counterparty
            FROM assets a
            JOIN events e ON a.acquisition_event_id = e.event_id
            JOIN cards c ON a.definition_id = c.definition_id
            WHERE c.set_id IN %s AND e.counterparty = %s {display_filter}
            ORDER BY e.event_date DESC, e.event_id ASC
        """, (allowed_sets, seller_name))

        return {
            "seller_name": seller_name,
            "share_of_wallet": share_of_wallet,
            "seller_spend": seller_spend,
            "transactions": cur.fetchall()
        }
    finally:
        cur.close()
        conn.close()


@app.get("/api/binder/{binder_id}/deepdive/lineage")
def get_lineage_deepdive(binder_id: str, mode: str = "BINDER"):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(
            status_code=500, detail="Database connection failed")

    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT max_pokedex_id FROM binders WHERE binder_id = %s", (binder_id,))
        binder_config = cur.fetchone()
        if not binder_config:
            raise HTTPException(status_code=404, detail="Binder not found")

        max_dex = binder_config['max_pokedex_id']
        cur.execute(
            "SELECT set_id FROM binder_sets WHERE binder_id = %s", (binder_id,))
        allowed_sets = tuple(row['set_id'] for row in cur.fetchall())

        if not allowed_sets:
            return {"error": "No sets mapped."}

        display_filter = "AND a.is_active_display = TRUE" if mode == "BINDER" else ""

        # 1. Evolutionary Chains (with specific member data)
        cur.execute(f"""
            SELECT p.pokedex_number, p.pokemon_name, p.evolution_chain_id,
                   EXISTS (
                       SELECT 1 FROM assets a
                       JOIN cards c ON a.definition_id = c.definition_id
                       WHERE c.pokedex_number = p.pokedex_number
                       AND c.set_id IN %s {display_filter}
                   ) as collected
            FROM pokedex p
            WHERE p.pokedex_number <= %s AND p.evolution_chain_id IS NOT NULL
            ORDER BY p.evolution_chain_id, p.pokedex_number
        """, (allowed_sets, max_dex))
        chain_rows = cur.fetchall()

        import collections
        chains = collections.defaultdict(list)
        for row in chain_rows:
            chains[row['evolution_chain_id']].append({
                "dex": row['pokedex_number'],
                "name": row['pokemon_name'],
                "collected": row['collected']
            })

        completed_chains, one_away_chains, orphan_chains = [], [], []
        total_collected_in_completed = 0
        total_collected = 0

        for chain_id, members in chains.items():
            if len(members) > 1:
                col_count = sum(1 for m in members if m['collected'])
                total_collected += col_count
                if col_count == len(members):
                    completed_chains.append(members)
                    total_collected_in_completed += col_count
                elif col_count == len(members) - 1:
                    one_away_chains.append(members)
                elif col_count == 1:
                    orphan_chains.append(members)

        evol_dominance = (total_collected_in_completed /
                          total_collected * 100) if total_collected > 0 else 0
        total_missing_in_orphans = sum(
            len(chain) - 1 for chain in orphan_chains)

        # 2. Set Archetype & DNA
        cur.execute(f"""
            SELECT s.set_name, COUNT(a.asset_id) as count
            FROM assets a
            JOIN cards c ON a.definition_id = c.definition_id
            JOIN sets s ON c.set_id = s.set_id
            JOIN pokedex p ON c.pokedex_number = p.pokedex_number
            WHERE p.pokedex_number <= %s AND c.set_id IN %s {display_filter}
            GROUP BY s.set_name
            ORDER BY count DESC
        """, (max_dex, allowed_sets))
        sets_data = cur.fetchall()

        top_set = sets_data[0] if sets_data else {
            "set_name": "UNKNOWN", "count": 0}
        total_assets = sum(s['count'] for s in sets_data)
        top_set_pct = (top_set['count'] / total_assets *
                       100) if total_assets > 0 else 0

        # 3. Elemental Skew
        cur.execute(
            "SELECT DISTINCT primary_type FROM pokedex WHERE pokedex_number <= %s AND primary_type IS NOT NULL", (max_dex,))
        all_types = [r['primary_type'] for r in cur.fetchall()]

        cur.execute(f"""
            SELECT p.primary_type, COUNT(a.asset_id) as count
            FROM assets a
            JOIN cards c ON a.definition_id = c.definition_id
            JOIN pokedex p ON c.pokedex_number = p.pokedex_number
            WHERE p.pokedex_number <= %s AND c.set_id IN %s {display_filter}
            GROUP BY p.primary_type
            ORDER BY count DESC
        """, (max_dex, allowed_sets))
        collected_types_data = cur.fetchall()
        collected_types_dict = {r['primary_type']: r['count']
                                for r in collected_types_data}

        missing_types = [t for t in all_types if t not in collected_types_dict]

       # 4. Overall Binder Condition (FIXED: Cast enums to text to bypass strict validation)
        cur.execute(f"""
            SELECT
                COALESCE(SUM(CASE WHEN (grading_status::text = 'Graded' AND surface_grade >= 9) OR (grading_status::text = 'Raw' AND raw_condition::text = 'M') THEN 1 ELSE 0 END), 0) as cond_m,
                COALESCE(SUM(CASE WHEN (grading_status::text = 'Graded' AND surface_grade IN (7,8)) OR (grading_status::text = 'Raw' AND raw_condition::text = 'NM') THEN 1 ELSE 0 END), 0) as cond_nm,
                COALESCE(SUM(CASE WHEN (grading_status::text = 'Graded' AND surface_grade IN (5,6)) OR (grading_status::text = 'Raw' AND raw_condition::text = 'LP') THEN 1 ELSE 0 END), 0) as cond_lp,
                COALESCE(SUM(CASE WHEN (grading_status::text = 'Graded' AND surface_grade IN (3,4)) OR (grading_status::text = 'Raw' AND raw_condition::text = 'MP') THEN 1 ELSE 0 END), 0) as cond_mp,
                COALESCE(SUM(CASE WHEN (grading_status::text = 'Graded' AND surface_grade IN (1,2)) OR (grading_status::text = 'Raw' AND raw_condition::text = 'HP') THEN 1 ELSE 0 END), 0) as cond_hp,
                COALESCE(SUM(CASE WHEN raw_condition::text = 'DMG' THEN 1 ELSE 0 END), 0) as cond_dmg,
                COALESCE(SUM(CASE WHEN raw_condition::text = 'UKN' AND grading_status::text = 'Raw' THEN 1 ELSE 0 END), 0) as cond_ukn
            FROM assets a
            JOIN cards c ON a.definition_id = c.definition_id
            JOIN pokedex p ON c.pokedex_number = p.pokedex_number
            WHERE p.pokedex_number <= %s AND c.set_id IN %s {display_filter}
        """, (max_dex, allowed_sets))

        cond_dist = cur.fetchone()

        # 5. The Blemish
        cur.execute(f"""
            SELECT p.pokemon_name, a.raw_condition, a.surface_grade, a.grading_status,
                   e.event_date, e.platform, e.item_amount, c.printed_name
            FROM assets a
            JOIN cards c ON a.definition_id = c.definition_id
            JOIN pokedex p ON p.pokedex_number = c.pokedex_number
            JOIN events e ON a.acquisition_event_id = e.event_id
            WHERE p.pokedex_number <= %s AND c.set_id IN %s {display_filter}
        """, (max_dex, allowed_sets))
        all_cards = cur.fetchall()

        cond_weights = {'M': 10, 'NM': 8, 'LP': 6,
                        'MP': 4, 'HP': 2, 'DMG': 1, 'UKN': 5}
        blemish_card = None
        min_score = 99

        for row in all_cards:
            score = 5
            if row['grading_status'] == 'Graded' and row['surface_grade']:
                score = row['surface_grade']
            elif row['grading_status'] == 'Raw' and row['raw_condition']:
                score = cond_weights.get(row['raw_condition'], 5)

            if score < min_score:
                min_score = score
                # FIXED: Cast the read-only RealDictRow to a standard mutable python dict
                blemish_card = dict(row)
                blemish_card['cond_label'] = f"PSA {score}" if row[
                    'grading_status'] == 'Graded' else row['raw_condition']

        cur.execute(f"""
            SELECT SUM(e.item_amount) as total_spend, COUNT(a.asset_id) as paid_assets
            FROM assets a
            JOIN events e ON a.acquisition_event_id = e.event_id
            JOIN cards c ON a.definition_id = c.definition_id
            WHERE c.set_id IN %s AND e.item_amount > 0 {display_filter}
        """, (allowed_sets,))
        base_data = cur.fetchone()
        true_average = (float(base_data['total_spend'] or 0) /
                        base_data['paid_assets']) if base_data['paid_assets'] > 0 else 0

        # 6. Page Density (Grid Gaps)
        cur.execute(f"""
            SELECT FLOOR((p.pokedex_number - 1) / 9) + 1 AS page_num, COUNT(DISTINCT p.pokedex_number) as filled
            FROM assets a
            JOIN cards c ON a.definition_id = c.definition_id
            JOIN pokedex p ON c.pokedex_number = p.pokedex_number
            WHERE p.pokedex_number <= %s AND c.set_id IN %s {display_filter}
            GROUP BY page_num
        """, (max_dex, allowed_sets))
        page_dict = {int(row['page_num']): int(row['filled'])
                     for row in cur.fetchall()}

        densest_page = max(page_dict, key=page_dict.get) if page_dict else 1
        ghost_page = min(page_dict, key=page_dict.get) if page_dict else 1

        cur.execute(f"""
            SELECT DISTINCT p.pokedex_number
            FROM assets a
            JOIN cards c ON a.definition_id = c.definition_id
            JOIN pokedex p ON c.pokedex_number = p.pokedex_number
            WHERE p.pokedex_number <= %s AND c.set_id IN %s {display_filter}
            ORDER BY p.pokedex_number ASC
        """, (max_dex, allowed_sets))
        filled_dex = [r['pokedex_number'] for r in cur.fetchall()]

        max_gap = 0
        gap_start, gap_end = 1, 1
        if filled_dex:
            if filled_dex[0] > 1:
                max_gap = filled_dex[0] - 1
                gap_start, gap_end = 1, filled_dex[0] - 1
            for i in range(1, len(filled_dex)):
                gap = filled_dex[i] - filled_dex[i-1] - 1
                if gap > max_gap:
                    max_gap = gap
                    gap_start, gap_end = filled_dex[i-1] + 1, filled_dex[i] - 1
            if max_dex - filled_dex[-1] > max_gap:
                max_gap = max_dex - filled_dex[-1]
                gap_start, gap_end = filled_dex[-1] + 1, max_dex
        else:
            max_gap, gap_start, gap_end = max_dex, 1, max_dex

        return {
            "completed_chains": completed_chains,
            "one_away_chains": one_away_chains,
            "orphan_chains": orphan_chains,
            "evol_dominance": evol_dominance,
            "missing_in_orphans": total_missing_in_orphans,
            "top_set": top_set,
            "top_set_pct": top_set_pct,
            "set_distribution": sets_data[:5],
            "collected_types": collected_types_data,
            "missing_types": missing_types,
            "cond_dist": cond_dist,
            "blemish": blemish_card,
            "true_average": true_average,
            "densest_page": {"num": densest_page, "count": page_dict.get(densest_page, 0)},
            "ghost_page": {"num": ghost_page, "count": page_dict.get(ghost_page, 0)},
            "max_gap": {"size": max_gap, "start": gap_start, "end": gap_end}
        }
    finally:
        cur.close()
        conn.close()


@app.get("/api/binder/{binder_id}/deepdive/archive")
def get_archive_deepdive(binder_id: str, mode: str = "BINDER"):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(
            status_code=500, detail="Database connection failed")

    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT max_pokedex_id FROM binders WHERE binder_id = %s", (binder_id,))
        binder_config = cur.fetchone()
        if not binder_config:
            raise HTTPException(status_code=404, detail="Binder not found")

        max_dex = binder_config['max_pokedex_id']
        cur.execute(
            "SELECT set_id FROM binder_sets WHERE binder_id = %s", (binder_id,))
        allowed_sets = tuple(row['set_id'] for row in cur.fetchall())

        if not allowed_sets:
            return {"error": "No sets mapped."}

        display_filter = "AND a.is_active_display = TRUE" if mode == "BINDER" else ""

        # Fetch all active assets with complete metadata, sorted chronologically
        cur.execute(f"""
            SELECT p.pokedex_number, p.pokemon_name, c.printed_name, c.artist, c.finish,
                   a.asset_id, a.grading_status, a.surface_grade, a.raw_condition, a.has_swirl, a.curator_notes,
                   e.event_date, e.item_amount, e.platform
            FROM assets a
            JOIN cards c ON a.definition_id = c.definition_id
            JOIN pokedex p ON p.pokedex_number = c.pokedex_number
            JOIN events e ON a.acquisition_event_id = e.event_id
            WHERE p.pokedex_number <= %s AND c.set_id IN %s {display_filter}
            ORDER BY e.event_date ASC, a.asset_id ASC
        """, (max_dex, allowed_sets))

        all_assets = cur.fetchall()
        if not all_assets:
            return {"error": "No assets found."}

        # 1 & 2: Genesis & Vanguard
        oldest = all_assets[0]
        newest = all_assets[-1]
        second_newest = all_assets[-2] if len(all_assets) > 1 else None

        today = datetime.now().date()
        days_in_vault = (
            today - oldest['event_date']).days if oldest['event_date'] else 0

        if newest['event_date'] and second_newest and second_newest['event_date']:
            cooldown = (newest['event_date'] -
                        second_newest['event_date']).days
        else:
            cooldown = 0

        # 3: The Binge (Streak Analysis)
        date_groups = {}
        for a in all_assets:
            if not a['event_date']:
                continue
            d = a['event_date']
            if d not in date_groups:
                date_groups[d] = {'count': 0, 'spend': 0.0}
            date_groups[d]['count'] += 1
            date_groups[d]['spend'] += float(a['item_amount'] or 0)

        sorted_dates = sorted(date_groups.keys())
        max_streak_days, max_count, max_spend = 0, 0, 0
        binge_start, binge_end = None, None

        if sorted_dates:
            curr_streak = 1
            curr_count = date_groups[sorted_dates[0]]['count']
            curr_spend = date_groups[sorted_dates[0]]['spend']
            curr_start = sorted_dates[0]
            max_streak_days, max_count, max_spend = 1, curr_count, curr_spend
            binge_start, binge_end = curr_start, curr_start

            for i in range(1, len(sorted_dates)):
                d_prev = sorted_dates[i-1]
                d_curr = sorted_dates[i]
                if (d_curr - d_prev).days == 1:
                    curr_streak += 1
                    curr_count += date_groups[d_curr]['count']
                    curr_spend += date_groups[d_curr]['spend']
                else:
                    curr_streak = 1
                    curr_count = date_groups[d_curr]['count']
                    curr_spend = date_groups[d_curr]['spend']
                    curr_start = d_curr

                if curr_streak > max_streak_days:
                    max_streak_days = curr_streak
                    max_count = curr_count
                    max_spend = curr_spend
                    binge_start = curr_start
                    binge_end = d_curr

        binge_data = {
            "days": max_streak_days, "count": max_count, "spend": max_spend,
            "start": binge_start.isoformat() if binge_start else None,
            "end": binge_end.isoformat() if binge_end else None
        }

        # 4: The Gallery (Artists)
        artist_counts = {}
        for a in all_assets:
            art = a['artist']
            if art:
                artist_counts[art] = artist_counts.get(art, 0) + 1

        sorted_artists = sorted(artist_counts.items(),
                                key=lambda x: x[1], reverse=True)
        top_artist = sorted_artists[0][0] if sorted_artists else "UNKNOWN"
        top_count = sorted_artists[0][1] if sorted_artists else 0
        runner_up = sorted_artists[1][0] if len(sorted_artists) > 1 else "NONE"
        top_pct = (top_count / len(all_assets) * 100) if all_assets else 0

        gallery_cards = [a for a in all_assets if a['artist'] == top_artist]

        # 5: Swirl Registry
        swirl_cards = [a for a in all_assets if a['has_swirl']]
        holo_count = sum(1 for a in all_assets if a['finish'] in [
                         'Holo', 'Reverse-Holo'])
        swirl_density = (len(swirl_cards) / holo_count *
                         100) if holo_count > 0 else 0

        # 6: High-Value Blanks (Missing Lore)
        blanks = [a for a in all_assets if not a['curator_notes']
                  or not a['curator_notes'].strip()]
        blanks = sorted(blanks, key=lambda x: float(
            x['item_amount'] or 0), reverse=True)[:15]

        # 7 & 8: Text Analytics (Manifesto & Verbosity)
        with_notes = [a for a in all_assets if a['curator_notes']
                      and a['curator_notes'].strip()]
        for a in with_notes:
            a['word_count'] = len(a['curator_notes'].split())
            a['cond_label'] = f"PSA {a['surface_grade']}" if a['grading_status'] == 'Graded' else (
                a['raw_condition'] or "UKN")

        sorted_notes = sorted(
            with_notes, key=lambda x: x['word_count'], reverse=True)
        manifesto = sorted_notes[0] if sorted_notes else None
        verbosity = sorted_notes[:10]

        # Cleanup date objects for JSON serialization
        for collection in [gallery_cards, swirl_cards, blanks]:
            for item in collection:
                if isinstance(item.get('event_date'), datetime) or hasattr(item.get('event_date'), 'isoformat'):
                    item['event_date'] = item['event_date'].isoformat()

        if oldest and hasattr(oldest.get('event_date'), 'isoformat'):
            oldest['event_date'] = oldest['event_date'].isoformat()
        if newest and hasattr(newest.get('event_date'), 'isoformat'):
            newest['event_date'] = newest['event_date'].isoformat()

        return {
            "oldest": oldest, "days_in_vault": days_in_vault,
            "newest": newest, "cooldown": cooldown,
            "binge": binge_data,
            "gallery": {
                "top_artist": top_artist, "top_count": top_count, "top_pct": top_pct,
                "runner_up": runner_up, "cards": gallery_cards
            },
            "swirls": {"density": swirl_density, "cards": swirl_cards},
            "blanks": blanks,
            "manifesto": manifesto,
            "verbosity": verbosity
        }
    finally:
        cur.close()
        conn.close()
