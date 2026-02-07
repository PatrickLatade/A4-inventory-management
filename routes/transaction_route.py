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
    conn.close()
    return render_template("transactions/out.html", payment_methods=payment_methods)

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
    
    # 1. TIME LOGIC (remains the same)
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
        # 2. Start the Atomic Transaction
        conn.execute("BEGIN")

        # 3. Insert into SALES
        cursor = conn.execute("""
            INSERT INTO sales (sales_number, customer_name, total_amount, payment_method_id, reference_no, status, notes, user_id, transaction_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('sales_number'), 
            data.get('customer_name'), 
            data.get('total_amount'),
            data.get('payment_method_id'),
            data.get('reference_no'),
            'Unresolved' if str(data.get('payment_method_id')) == '5' else 'Paid',
            data.get('notes'), 
            session.get('user_id'), 
            clean_time
        ))
        
        # This is the ID from the Sales table
        new_sale_id = cursor.lastrowid 

        # 4. Loop items and call the Chef (add_transaction)
        # --- THE CHANGE HAPPENS HERE ---
        for item in data['items']:
            add_transaction(
                item_id=item['item_id'],
                quantity=item['quantity'],
                transaction_type='OUT',
                user_id=session.get('user_id'),
                user_name=session.get('username'),
                # RENAME: sale_id became reference_id
                reference_id=new_sale_id, 
                # ADD: We tell the ledger this ID belongs to a SALE
                reference_type='SALE',
                # ADD: A human-readable reason
                change_reason='CUSTOMER_PURCHASE',
                unit_price=item['price'],
                transaction_date=clean_time,
                external_conn=conn
            )

        conn.commit()
        flash(f"Sale #{data.get('sales_number')} recorded successfully!", "success")
        return jsonify({"status": "success"}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()