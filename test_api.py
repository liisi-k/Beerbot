import requests
import json

# --- Seadistus ---
# See on sinu lokaalselt töötava serveri aadress ja lõpp-punkt
API_URL = "http://127.0.0.1:5000/api/decision"

# Andmed, mida me handshake päringus saadame
handshake_data = {
    "handshake": True,
    "ping": "hello",
    "seed": 2025
}

# --- Testi käivitamine ---
print(f"Saadan POST päringu aadressile: {API_URL}")
print(f"Saadetavad andmed: {json.dumps(handshake_data, indent=2)}")

try:
    # Saadame POST päringu, andes andmed kaasa JSON formaadis
    # `requests` teek hoolitseb ise "Content-Type: application/json" päise lisamise eest
    response = requests.post(API_URL, json=handshake_data)

    # Kontrollime, kas päring oli edukas (HTTP staatuskood 200)
    if response.status_code == 200:
        print("\n✅ EDU! Server vastas staatuskoodiga 200.")
        print("Serveri vastus:")
        # Prindime välja serveri saadetud JSON-vastuse ilusal kujul
        print(json.dumps(response.json(), indent=2))
    else:
        # Kui midagi läks valesti, näitame staatuskoodi ja vastuse sisu
        print(f"\n❌ VIGA! Server vastas staatuskoodiga: {response.status_code}")
        print("Serveri vastuse sisu:")
        print(response.text)

except requests.exceptions.ConnectionError as e:
    print("\n❌ VIGA! Ei saanud serveriga ühendust.")
    print("Veendu, et sinu Flaski server (app.py) töötab teises terminaliaknas!")
except Exception as e:
    print(f"\n❌ Ilmnes ootamatu viga: {e}")