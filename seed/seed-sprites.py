import os
import requests
import time


def scrape_sprites():
    os.makedirs("sprites", exist_ok=True)
    print("🚀 Initiating Sprite Heist...")

    for dex_num in range(1, 152):
        file_path = f"sprites/{dex_num}.png"

        if os.path.exists(file_path):
            continue

        url = f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/versions/generation-i/red-blue/transparent/{dex_num}.png"
        response = requests.get(url)

        if response.status_code == 200:
            with open(file_path, "wb") as f:
                f.write(response.content)
            print(f"✅ Secured #{dex_num:03d}")
        else:
            print(f"❌ Failed to get #{dex_num}")

        time.sleep(0.1)

    print("🏁 Sprite Heist Complete.")


def scrape_set_symbols():
    os.makedirs("sprites", exist_ok=True)
    print("\n🚀 Initiating Set Icon Extraction...")

    # Official Pokémon TCG API symbol URLs
    # Base Set 2 uses the 'base4' endpoint
    symbols = {
        "base2": "https://images.pokemontcg.io/base4/symbol.png",
        "jungle": "https://images.pokemontcg.io/base2/symbol.png",
        "fossil": "https://images.pokemontcg.io/base3/symbol.png"
    }

    for set_name, url in symbols.items():
        file_path = f"sprites/icon_{set_name}.png"

        if os.path.exists(file_path):
            print(f"⏩ Skipped {set_name.upper()} icon (Already exists)")
            continue

        response = requests.get(url)

        if response.status_code == 200:
            with open(file_path, "wb") as f:
                f.write(response.content)
            print(f"✅ Secured {set_name.upper()} icon")
        else:
            print(f"❌ Failed to get {set_name.upper()} icon")

        # Be polite to the TCG API
        time.sleep(0.5)

    print("🏁 Set Icon Extraction Complete.")


if __name__ == "__main__":
    scrape_sprites()
    scrape_set_symbols()
    print("\n📦 All assets secured locally.")
