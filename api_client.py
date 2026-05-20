import requests

API_BASE_URL = "http://127.0.0.1:8000"


def fetch_page_data(binder_profile, page_number, mode="BINDER"):
    try:
        url = f"{API_BASE_URL}/api/binder/{binder_profile}/page/{page_number}"
        response = requests.get(url, params={"mode": mode}, timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"API Error: {e}")
    return None


def fetch_binder_stats(binder_profile, mode="BINDER"):
    try:
        url = f"{API_BASE_URL}/api/binder/{binder_profile}/stats"
        response = requests.get(url, params={"mode": mode}, timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"API Error: {e}")
    return None


def fetch_vitals_data(binder_profile, mode="BINDER"):
    try:
        url = f"{API_BASE_URL}/api/binder/{binder_profile}/stats/vitals"
        response = requests.get(url, params={"mode": mode}, timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"API Error: {e}")
    return None


def fetch_archetypes_data(binder_profile, mode="BINDER"):
    try:
        url = f"{API_BASE_URL}/api/binder/{binder_profile}/stats/archetypes"
        response = requests.get(url, params={"mode": mode}, timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"API Error: {e}")
    return None


def fetch_sourcing_data(binder_profile, mode="BINDER"):
    try:
        url = f"{API_BASE_URL}/api/binder/{binder_profile}/stats/sourcing"
        response = requests.get(url, params={"mode": mode}, timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"API Error: {e}")
    return None


def fetch_lineage_data(binder_profile, mode="BINDER"):
    try:
        url = f"{API_BASE_URL}/api/binder/{binder_profile}/stats/lineage"
        response = requests.get(url, params={"mode": mode}, timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"API Error: {e}")
    return None


def fetch_archive_data(binder_profile, mode="BINDER"):
    try:
        url = f"{API_BASE_URL}/api/binder/{binder_profile}/stats/archive"
        response = requests.get(url, params={"mode": mode}, timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"API Error: {e}")
    return None


def fetch_collected_assets(binder_profile, mode="BINDER"):
    try:
        url = f"{API_BASE_URL}/api/binder/{binder_profile}/collection/collected"
        response = requests.get(url, params={"mode": mode}, timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"API Error: {e}")
    return []


def fetch_transactions(binder_profile, tx_type, mode="BINDER"):
    try:
        url = f"{API_BASE_URL}/api/binder/{binder_profile}/transactions/{tx_type}"
        response = requests.get(url, params={"mode": mode}, timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"API Error: {e}")
    return None


def fetch_cost_deepdive(binder_id, mode="BINDER"):
    try:
        url = f"{API_BASE_URL}/api/binder/{binder_id}/deepdive/cost"
        response = requests.get(url, params={"mode": mode}, timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetching cost deepdive: {e}")
    return None


def fetch_overhead_deepdive(binder_id, mode="BINDER"):
    try:
        url = f"{API_BASE_URL}/api/binder/{binder_id}/deepdive/overhead"
        response = requests.get(url, params={"mode": mode}, timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetching overhead deepdive: {e}")
    return None


def fetch_forecast_deepdive(binder_id, mode="BINDER"):
    try:
        url = f"{API_BASE_URL}/api/binder/{binder_id}/deepdive/forecast"
        response = requests.get(url, params={"mode": mode}, timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetching forecast deepdive: {e}")
    return None


def fetch_netspend_deepdive(binder_id, mode="BINDER"):
    try:
        url = f"{API_BASE_URL}/api/binder/{binder_id}/deepdive/netspend"
        response = requests.get(url, params={"mode": mode}, timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetching netspend deepdive: {e}")
    return None


def fetch_missing_targets(binder_id, mode="BINDER"):
    try:
        url = f"{API_BASE_URL}/api/binder/{binder_id}/deepdive/missing"
        response = requests.get(url, params={"mode": mode}, timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetching missing targets: {e}")
    return None


def fetch_holo_deepdive(binder_id, mode="BINDER"):
    try:
        url = f"{API_BASE_URL}/api/binder/{binder_id}/deepdive/holo"
        response = requests.get(url, params={"mode": mode}, timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetching holo deepdive: {e}")
    return None


def fetch_extremes_deepdive(binder_id, mode="BINDER"):
    try:
        url = f"{API_BASE_URL}/api/binder/{binder_id}/deepdive/extremes"
        response = requests.get(url, params={"mode": mode}, timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetching extremes deepdive: {e}")
    return None


def fetch_sourcing_leaders_deepdive(binder_id, mode="BINDER"):
    try:
        url = f"{API_BASE_URL}/api/binder/{binder_id}/deepdive/sourcing_leaders"
        response = requests.get(url, params={"mode": mode}, timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetching sourcing leaders deepdive: {e}")
    return None


def fetch_top_seller_ledger(binder_id, mode="BINDER"):
    try:
        url = f"{API_BASE_URL}/api/binder/{binder_id}/deepdive/top_seller_ledger"
        response = requests.get(url, params={"mode": mode}, timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetching top seller ledger: {e}")
    return None


def fetch_top_funded_ledger(binder_id, mode="BINDER"):
    try:
        url = f"{API_BASE_URL}/api/binder/{binder_id}/deepdive/top_funded_ledger"
        response = requests.get(url, params={"mode": mode}, timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetching top funded ledger: {e}")
    return None


def fetch_lineage_deepdive(binder_id, mode="BINDER"):
    try:
        url = f"{API_BASE_URL}/api/binder/{binder_id}/deepdive/lineage"
        response = requests.get(url, params={"mode": mode}, timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetching lineage deepdive: {e}")
    return None


def fetch_archive_deepdive(binder_id, mode="BINDER"):
    try:
        url = f"{API_BASE_URL}/api/binder/{binder_id}/deepdive/archive"
        response = requests.get(url, params={"mode": mode}, timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetching archive deepdive: {e}")
    return None
