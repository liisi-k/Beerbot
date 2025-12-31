import os
from flask import Flask, request, jsonify

STUDENT_EMAIL = "likask@taltech.ee"
ALGORITHM_NAME = "StabiilneAnkur"
VERSION = "v1.1.8"

# Soovitud varu nädalates 
WEEKS_OF_SUPPLY_TARGET = 2.7
# Silumise aken 
SMOOTHING_WINDOW = 3
# Korrektsioonifaktor
CORRECTION_FACTOR = 0.24
# ---------------------------------------------------------------------


app = Flask(__name__)

@app.route("/api/decision", methods=["POST"])
def handle_decision_request():
    try:
        data = request.get_json()
        if not data:
            return "Bad Request: No JSON payload", 400

        if data.get("handshake") is True:
            return jsonify(handle_handshake())
        
        return jsonify(handle_weekly_step(data))

    except Exception as e:
        app.logger.error(f"An error occurred: {e}")
        return "Internal Server Error", 500

def handle_handshake():
    return {
        "ok": True,
        "student_email": STUDENT_EMAIL,
        "algorithm_name": ALGORITHM_NAME,
        "version": VERSION,
        "supports": {
            "blackbox": True,  
            "glassbox": True  
        },
        "message": "BeerBot ready"
    }

def handle_weekly_step(data):
    mode = data.get("mode")
    weeks_data = data.get("weeks", [])

    if not weeks_data:
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
    else: 
        orders = calculate_blackbox_orders(weeks_data)
        
    return {"orders": orders}


def calculate_blackbox_orders(weeks_data):
    roles = ["retailer", "wholesaler", "distributor", "factory"]
    orders = {}
    current_week_number = weeks_data[-1]['week']

    for role in roles:
        # 1. Andmete kogumine
        role_history = [week['roles'][role] for week in weeks_data]
        current_state = role_history[-1]
        
        # 2. Nõudluse silumine
        demand_history = [state['incoming_orders'] for state in role_history]
        window = min(current_week_number, SMOOTHING_WINDOW)
        smoothed_demand = sum(demand_history[-window:]) / window

        # 3. Laoseisu ja torujuhtme hindamine
        effective_inventory = current_state['inventory'] - current_state['backlog']
        
        # Torujuhtme (supply line) lihtsustatud hindamine:
        supply_line = 0
        if current_week_number > 1:
            last_week_orders = weeks_data[-2].get('orders', {})
            supply_line = last_week_orders.get(role, 0)
            
        # 4. Otsuse tegemine "Order-Up-To" poliitika alusel
        desired_inventory_level = smoothed_demand * WEEKS_OF_SUPPLY_TARGET
        inventory_adjustment = (desired_inventory_level - effective_inventory - supply_line) * CORRECTION_FACTOR
        order_quantity = smoothed_demand + inventory_adjustment
        orders[role] = max(0, int(round(order_quantity)))

    return orders


def calculate_glassbox_orders(weeks_data):
    orders = {}
    current_week_number = weeks_data[-1]['week']

    # 1. Määra kindlaks tegelik kliendi nõudlus ja silu see
    retailer_history = [week['roles']['retailer'] for week in weeks_data]
    customer_demand_history = [state['incoming_orders'] for state in retailer_history]
    
    window = min(current_week_number, SMOOTHING_WINDOW)
    smoothed_customer_demand = sum(customer_demand_history[-window:]) / window

    # 2. Jaemüüja kasutab parimat BlackBox loogikat, kuna tema on kliendile kõige lähemal
    retailer_blackbox_orders = calculate_blackbox_orders(weeks_data)
    orders['retailer'] = retailer_blackbox_orders['retailer']

    # 3. Ülejäänud ahela lülid kasutavad "pass-through" (läbivoolu) strateegiat.

    # Hulgimüüja tellib selle, mida jaemüüja temalt küsis
    orders['wholesaler'] = weeks_data[-1]['roles']['wholesaler']['incoming_orders']
    
    # Tarnija tellib selle, mida hulgimüüja temalt küsis
    orders['distributor'] = weeks_data[-1]['roles']['distributor']['incoming_orders']
    
    # Tehas toodab selle, mida tarnija temalt küsis
    orders['factory'] = weeks_data[-1]['roles']['factory']['incoming_orders']
    
    for role, quantity in orders.items():
        orders[role] = max(0, int(quantity))
        
    return orders