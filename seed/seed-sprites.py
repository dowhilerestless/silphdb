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

    print("🏁 Heist Complete. All assets secured locally.")


if __name__ == "__main__":
    scrape_sprites()
