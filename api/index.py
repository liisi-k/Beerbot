import os
from flask import Flask, request, jsonify

# --- Konfiguratsioon ---------------------------------------------------
STUDENT_EMAIL = "likask@taltech.ee"
ALGORITHM_NAME = "StabiilneAnkur"
VERSION = "v1.1.0"

# --- Otsustusalgoritmi parameetrid (saad neid tuunida) -------------
# Soovitud varu nädalates (kui mitme nädala jagu nõudlust soovid laos hoida)
WEEKS_OF_SUPPLY_TARGET = 4 
# Silumise aken (mitme viimase nädala keskmist nõudlust vaatame)
SMOOTHING_WINDOW = 4
# Korrektsioonifaktor (kui agressiivselt laoseisu korrigeerida, 0.0-1.0)
CORRECTION_FACTOR = 0.5
# ---------------------------------------------------------------------


app = Flask(__name__)

@app.route("/api/decision", methods=["POST"])
def handle_decision_request():
    """
    Põhiline lõpp-punkt, mis käsitleb nii 'handshake' kui ka iganädalasi päringuid.
    """
    try:
        data = request.get_json()
        if not data:
            return "Bad Request: No JSON payload", 400

        # Kontrollime, kas tegemist on handshake päringuga
        if data.get("handshake") is True:
            return jsonify(handle_handshake())
        
        # Kui ei, siis on see iganädalane simulatsiooni samm
        return jsonify(handle_weekly_step(data))

    except Exception as e:
        # Vigade logimine aitab arenduses probleeme leida
        app.logger.error(f"An error occurred: {e}")
        return "Internal Server Error", 500

def handle_handshake():
    """
    Koostab ja tagastab korrektse handshake vastuse.
    """
    return {
        "ok": True,
        "student_email": STUDENT_EMAIL,
        "algorithm_name": ALGORITHM_NAME,
        "version": VERSION,
        "supports": {
            "blackbox": True,  # Toetame BlackBox režiimi
            "glassbox": True   # Toetame ka GlassBox režiimi
        },
        "message": "BeerBot ready"
    }

def handle_weekly_step(data):
    """
    Töötleb iganädalasi andmeid ja delegeerib otsustamise vastavalt mängu režiimile.
    """
    mode = data.get("mode")
    weeks_data = data.get("weeks", [])

    if not weeks_data:
        # Esimesel nädalal tellime konservatiivse baaskoguse, kuna ajalugu puudub.
        default_order = 10
        return {
            "orders": {
                "retailer": default_order,
                "wholesaler": default_order,
                "distributor": default_order,
                "factory": default_order,
            }
        }

    if mode == "glassbox":
        orders = calculate_glassbox_orders(weeks_data)
    else:  # Vaikimisi või "blackbox" režiim
        orders = calculate_blackbox_orders(weeks_data)
        
    return {"orders": orders}


def calculate_blackbox_orders(weeks_data):
    """
    Arvutab tellimused BlackBox režiimi jaoks.
    Iga roll teeb otsuseid ainult oma andmete põhjal, kasutades "Order-Up-To"
    ja silutud nõudluse strateegiat.
    """
    roles = ["retailer", "wholesaler", "distributor", "factory"]
    orders = {}
    
    current_week_number = weeks_data[-1]['week']

    for role in roles:
        # 1. Andmete kogumine
        role_history = [week['roles'][role] for week in weeks_data]
        current_state = role_history[-1]
        
        # 2. Nõudluse silumine (liikuv keskmine)
        demand_history = [state['incoming_orders'] for state in role_history]
        window = min(current_week_number, SMOOTHING_WINDOW)
        smoothed_demand = sum(demand_history[-window:]) / window

        # 3. Laoseisu ja torujuhtme hindamine
        effective_inventory = current_state['inventory'] - current_state['backlog']
        
        # Torujuhtme (supply line) lihtsustatud hindamine:
        # Eeldame, et tarneaeg on 2 nädalat. Seega on teel see, mis eelmisel nädalal telliti.
        supply_line = 0
        if current_week_number > 1:
            last_week_orders = weeks_data[-2].get('orders', {})
            supply_line = last_week_orders.get(role, 0)
            
        # 4. Otsuse tegemine "Order-Up-To" poliitika alusel
        # Soovitud tase = mitme nädala nõudluse varu + torujuhe
        desired_inventory_level = smoothed_demand * WEEKS_OF_SUPPLY_TARGET
        
        # Korrigeerime laoseisu puudujääki/ülejääki järk-järgult
        inventory_adjustment = (desired_inventory_level - effective_inventory - supply_line) * CORRECTION_FACTOR
        
        # Lõplik tellimus = oodatav nõudlus + korrektsioon
        order_quantity = smoothed_demand + inventory_adjustment
        
        # Tagame, et tellimus on mittenegatiivne täisarv
        orders[role] = max(0, int(round(order_quantity)))

    return orders


def calculate_glassbox_orders(weeks_data):
    """
    Arvutab tellimused GlassBox režiimi jaoks.
    See strateegia kasutab ära täielikku infot tarneahelast.
    Kõik rollid reageerivad tegelikule lõpptarbija nõudlusele.
    """
    orders = {}
    current_week_number = weeks_data[-1]['week']

    # 1. Määra kindlaks tegelik kliendi nõudlus ja silu see
    # See on jaemüüja sissetulevate tellimuste ajalugu.
    retailer_history = [week['roles']['retailer'] for week in weeks_data]
    customer_demand_history = [state['incoming_orders'] for state in retailer_history]
    
    window = min(current_week_number, SMOOTHING_WINDOW)
    smoothed_customer_demand = sum(customer_demand_history[-window:]) / window

    # 2. Jaemüüja kasutab parimat BlackBox loogikat, kuna tema on kliendile kõige lähemal
    retailer_blackbox_orders = calculate_blackbox_orders(weeks_data)
    orders['retailer'] = retailer_blackbox_orders['retailer']

    # 3. Ülejäänud ahela lülid kasutavad "pass-through" (läbivoolu) strateegiat.
    # Nad tellivad täpselt selle koguse, mille nende vahetu klient neilt tellis.
    # See on väga efektiivne viis piitsalöögi efekti vältimiseks.
    
    # Hulgimüüja tellib selle, mida jaemüüja temalt küsis
    orders['wholesaler'] = weeks_data[-1]['roles']['wholesaler']['incoming_orders']
    
    # Tarnija tellib selle, mida hulgimüüja temalt küsis
    orders['distributor'] = weeks_data[-1]['roles']['distributor']['incoming_orders']
    
    # Tehas toodab selle, mida tarnija temalt küsis
    orders['factory'] = weeks_data[-1]['roles']['factory']['incoming_orders']
    
    # Tagame, et kõik tellimused on mittenegatiivsed täisarvud
    for role, quantity in orders.items():
        orders[role] = max(0, int(quantity))
        
    return orders