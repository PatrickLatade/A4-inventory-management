from flask import Blueprint, render_template, request, redirect, session, url_for, flash, jsonify
from services.transactions_service import add_transaction
from services.inventory_service import get_unique_categories
from services.transactions_service import add_item_to_db
from db.database import get_db
from datetime import datetime

# Define the blueprint
transaction_bp = Blueprint('transaction', __name__)

@transaction_bp.route("/transaction/out")
def transaction_out():
    conn = get_db()
    # We fetch items so the user can select them in the dropdown/search
    payment_methods = conn.execute("SELECT * FROM payment_methods").fetchall()
    mechanics = conn.execute("SELECT id, name FROM mechanics WHERE is_active = 1").fetchall()
    conn.close()
    return render_template("transactions/out.html", payment_methods=payment_methods, mechanics=mechanics)

@transaction_bp.route("/transaction/in")
def transaction_in():
    # Check if a 'selected_id' was passed in the URL
    prefilled_id = request.args.get('selected_id')
    
    # We pass it to the template
    return render_template("transactions/in.html", prefilled_id=prefilled_id)

@transaction_bp.route("/transaction/items")
def manage_items():
    # 1. Ask the chef for the categories
    categories = get_unique_categories()
    
    # 2. Serve the page, handing the categories to the HTML
    return render_template("transactions/items.html", categories=categories)

@transaction_bp.route("/items/add", methods=["POST"])
def add_item():
    # 1. Collect the form data into a dictionary
    form_data = {
        'name': request.form.get("name"),
        'category': request.form.get("category"),
        'description': request.form.get("description"),
        'pack_size': request.form.get("pack_size"),
        'vendor_price': request.form.get("vendor_price") or 0,
        'cost_per_piece': request.form.get("cost_per_piece") or 0,
        'selling_price': request.form.get("a4s_selling_price") or 0,
        'markup': request.form.get("markup") or 0,
        'reorder_level': request.form.get("reorder_level") or 0,
        'vendor': request.form.get("vendor"),
        'mechanic': request.form.get("mechanic")
    }

    # 2. Hand it to the Service to save it
    # This now returns the new item's ID (though we aren't using it yet)
    new_item_id = add_item_to_db(form_data)

    # 3. Redirect to the items list to confirm it was added
    return redirect(url_for('transaction.transaction_in', selected_id=new_item_id))

@transaction_bp.route("/inventory/in", methods=["POST"])
def process_transaction_in():
    item_id = request.form.get("item_id")
    quantity = request.form.get("quantity")
    
    current_user_id = session.get("user_id")
    current_username = session.get("username") 

    if item_id and quantity:
        try:
            qty_int = int(quantity)
            # Call service to log transaction and update current_stock
            add_transaction(
                item_id=item_id,
                quantity=qty_int,
                transaction_type='IN',
                user_id=current_user_id,
                user_name=current_username
            )
            # SUCCESS: Category is 'success' (matches your Green CSS)
            flash(f"Stock updated! Received {qty_int} unit(s).", "success")
            
        except ValueError:
            flash("Invalid quantity. Please enter a number.", "danger")
        except Exception as e:
            flash(f"System Error: {str(e)}", "danger")
    else:
        flash("Missing item selection or quantity.", "danger")

    return redirect(url_for('transaction.transaction_in'))

@transaction_bp.route("/transaction/out/save", methods=["POST"])
def save_transaction_out():
    data = request.get_json()
    conn = get_db()
    
    # 1. TIME LOGIC
    now_obj = datetime.now()
    raw_date = data.get('transaction_date')
    current_minute = now_obj.strftime("%Y-%m-%d %H:%M")

    if raw_date:
        clean_time = raw_date.replace('T', ' ')
        if clean_time[:16] == current_minute or not raw_date:
            clean_time = now_obj.strftime("%Y-%m-%d %H:%M:%S")
        elif len(clean_time) == 16:
            clean_time += ":00"
    else:
        clean_time = now_obj.strftime("%Y-%m-%d %H:%M:%S")

    try:
        conn.execute("BEGIN")

        # 2. Insert into SALES
        cursor = conn.execute("""
            INSERT INTO sales (
                sales_number, customer_name, total_amount, 
                payment_method_id, reference_no, status, 
                notes, user_id, transaction_date, mechanic_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('sales_number'), 
            data.get('customer_name'), 
            data.get('total_amount'),
            data.get('payment_method_id'),
            data.get('reference_no'),
            'Unresolved' if str(data.get('payment_method_id')) == '5' else 'Paid',
            data.get('notes'), 
            session.get('user_id'), 
            clean_time,
            data.get('mechanic_id') or None
        ))
        
        new_sale_id = cursor.lastrowid 

        # 3. Loop PHYSICAL items (Stock items)
        for item in data.get('items', []):
            # Calculate discount amount
            original_price = float(item.get('original_price', 0))
            final_price = float(item.get('final_price', 0))
            discount_percent_whole = float(item.get('discount_percent', 0))
            
            # Convert discount from whole number (10) to decimal (0.10) for consistency with markup
            discount_percent_decimal = discount_percent_whole / 100
            discount_amount = original_price - final_price
            
            # 3A. Save to inventory_transactions (with ORIGINAL price)
            add_transaction(
                item_id=item['item_id'],
                quantity=item['quantity'],
                transaction_type='OUT',
                user_id=session.get('user_id'),
                user_name=session.get('username'),
                reference_id=new_sale_id, 
                reference_type='SALE',
                change_reason='CUSTOMER_PURCHASE',
                unit_price=original_price,  # <-- THE FIX: Use original price here
                transaction_date=clean_time,
                external_conn=conn
            )
            
            # 3B. Save to sales_items (with discount tracking)
            conn.execute("""
                INSERT INTO sales_items (
                    sale_id, item_id, quantity, 
                    original_unit_price, discount_percent, discount_amount, final_unit_price,
                    discounted_by, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                new_sale_id,
                item['item_id'],
                item['quantity'],
                original_price,
                discount_percent_decimal,  # Store as decimal (0.10 instead of 10.0)
                discount_amount,
                final_price,
                session.get('user_id') if discount_percent_whole > 0 else None,
                clean_time  # Use the same timestamp as other tables
            ))

        # --- FIX: MOVED OUTSIDE THE LOOP ---
        service_subtotal = 0 

        # 4. Loop LABOR items (Services)
        for service in data.get('services', []):
            price = float(service.get('price', 0))
            service_subtotal += price

            conn.execute("""
                INSERT INTO sales_services (sale_id, service_id, price)
                VALUES (?, ?, ?)
            """, (
                new_sale_id, 
                service['service_id'], 
                price
            ))

        # 5. Update main Sale with the subtotal
        conn.execute("""
            UPDATE sales SET service_fee = ? WHERE id = ?
        """, (service_subtotal, new_sale_id))

        conn.commit()
        
        flash(f"Sale #{data.get('sales_number')} recorded successfully!", "success")
        return jsonify({"status": "success"}), 200

    except Exception as e:
        conn.rollback()
        print(f"DATABASE ERROR: {str(e)}") 
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()