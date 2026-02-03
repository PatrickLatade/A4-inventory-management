from flask import Blueprint, render_template, request, redirect, session, url_for, flash
from services.transactions_service import add_transaction
from services.inventory_service import get_items_with_stock
from services.inventory_service import get_items_with_stock, get_unique_categories
from services.transactions_service import add_item_to_db

# Define the blueprint
transaction_bp = Blueprint('transaction', __name__)

@transaction_bp.route("/transaction/out")
def transaction_out():
    # We fetch items so the user can select them in the dropdown/search
    items = get_items_with_stock()
    return render_template("transactions/out.html", items=items)

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