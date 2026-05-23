import os
import time
import cv2
import numpy as np
from bs4 import BeautifulSoup
import cloudscraper

# --- CONFIGURATION ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(SCRIPT_DIR, "templates")

if not os.path.exists(TEMPLATE_DIR):
    os.makedirs(TEMPLATE_DIR)

CARD_WIDTH = 734
CARD_HEIGHT = 1024


def build_unlimited_vault():
    print("="*50)
    print(" 🏦 BUILDING STRICT UNLIMITED VAULT (ARMORED SCRAPER) 🏦")
    print("="*50)

    # THE FIX: Explicitly spoof a real Windows Desktop Chrome instance
    # to bypass Cloudflare Turnstile TLS fingerprinting.
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )

    back_url = "https://upload.wikimedia.org/wikipedia/en/3/3b/Pokemon_Trading_Card_Game_cardback.jpg"
    print("\nDownloading Master Back...")
    resp = scraper.get(back_url)
    if resp.status_code == 200:
        img_arr = np.asarray(bytearray(resp.content), dtype=np.uint8)
        img = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)
        resized = cv2.resize(img, (CARD_WIDTH, CARD_HEIGHT))
        cv2.imwrite(os.path.join(TEMPLATE_DIR, "master_back.jpg"), resized)

    sets = ["pokemon-base-set", "pokemon-jungle", "pokemon-fossil"]

    for set_name in sets:
        print(f"\nFetching {set_name.upper()}...")
        url = f"https://www.pricecharting.com/console/{set_name}"

        try:
            req = scraper.get(url, timeout=15)
            soup = BeautifulSoup(req.text, 'html.parser')
        except Exception as e:
            print(f"Failed to fetch set index: {e}")
            continue

        table = soup.find('table', {'id': 'games_table'})
        if not table:
            print("Could not find games table. Blocked by Cloudflare?")
            continue

        links = table.find_all('a')
        print(f"Found {len(links)} total items. Filtering for Unlimited...")

        test_count = 0

        for link in links:
            href = link.get('href')
            if not href or "/game/" not in href:
                continue

            card_name = link.text.strip()
            if not card_name:
                continue

            href_lower = href.lower()
            name_lower = card_name.lower()

            if "[" in card_name or "(" in card_name:
                continue

            blacklist = [
                "1st", "shadowless", "pack", "box", "deck", "error",
                "print", "prerelease", "theme", "sealed", "japanese",
                "promo", "e3", "red-cheeks", "yellow-cheeks", "wrapper",
                "empty", "ticket", "rule", "complete"
            ]

            if any(bad_word in href_lower for bad_word in blacklist):
                continue
            if any(bad_word in name_lower for bad_word in blacklist):
                continue

            if href.startswith("http"):
                card_url = href
            else:
                card_url = f"https://www.pricecharting.com{href}"

            filename = href.split('/')[-1] + ".jpg"
            filepath = os.path.join(TEMPLATE_DIR, filename)

            if os.path.exists(filepath):
                continue

            print(f"  -> Downloading {card_name}...")

            try:
                time.sleep(1)  # Polite human delay
                card_req = scraper.get(card_url, timeout=15)

                if card_req.status_code != 200:
                    print(
                        f"     * Failed! HTTP Status: {card_req.status_code}")
                    continue

                card_soup = BeautifulSoup(card_req.text, 'html.parser')

                if card_soup.title and "moment" in card_soup.title.text.lower():
                    print("     * BLOCKED BY CLOUDFLARE! (TLS Fingerprint detected)")
                    continue

                # --- NEW: HIGH-RES EXTRACTION ---
                img_url = None

                # Attempt 1: Target the hidden high-res modal you found in the DOM
                large_modal = card_soup.find("div", id="js-dialog-large-image")
                if large_modal:
                    large_img = large_modal.find("img")
                    if large_img and large_img.get("src"):
                        img_url = large_img["src"]

                # Attempt 2: Fallback to the cover image, but hack the URL to demand the 1600px version
                if not img_url:
                    cover = card_soup.select_one(".cover img")
                    if cover and cover.get("src"):
                        img_url = cover["src"].replace("240.jpg", "1600.jpg")

                # Attempt 3: Fallback to OG Meta, hacking the URL
                if not img_url:
                    img_tag = card_soup.find("meta", property="og:image")
                    if img_tag and img_tag.get("content"):
                        img_url = img_tag["content"].replace(
                            "240.jpg", "1600.jpg")

                if not img_url:
                    print(f"     * Failed! Could not extract high-res image URL.")
                    continue

                # Fix relative image URLs if they exist
                if not img_url.startswith("http"):
                    img_url = f"https://www.pricecharting.com{img_url}"

                img_resp = scraper.get(img_url, timeout=15)

                if img_resp.status_code == 200:
                    img_arr = np.asarray(
                        bytearray(img_resp.content), dtype=np.uint8)
                    img = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)

                    if img is not None:
                        resized = cv2.resize(img, (CARD_WIDTH, CARD_HEIGHT))
                        cv2.imwrite(filepath, resized)
                        print(f"     [SUCCESS] Saved {filename}")
                        test_count += 1
                    else:
                        print("     * Failed to decode image bytes.")
                else:
                    print(
                        f"     * Failed to download image. HTTP {img_resp.status_code}")

            except Exception as e:
                print(f"     * Error on {card_name}: {e}")

            if test_count >= 5:
                print(
                    f"\n  -> Test limit reached for {set_name}! Moving to next set...")
                break

    print("\n" + "="*50)
    print(" Test Vault Construction Complete!")
    print("="*50)


if __name__ == "__main__":
    build_unlimited_vault()
