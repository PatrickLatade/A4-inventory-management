from flask import Blueprint, render_template, request, redirect, session, url_for
from services.transactions_service import add_transaction
from services.inventory_service import get_items_with_stock

# Define the blueprint
transaction_bp = Blueprint('transaction', __name__)

@transaction_bp.route("/transaction/out")
def transaction_out():
    # We fetch items so the user can select them in the dropdown/search
    items = get_items_with_stock()
    return render_template("transactions/out.html", items=items)

@transaction_bp.route("/transaction/in")
def transaction_in():
    # We'll pass items anyway so you have the data ready when you want to make the search dynamic later
    items = get_items_with_stock()
    return render_template("transactions/in.html", items=items)

@transaction_bp.route("/transaction/items")
def manage_items():
    # Renders the page where you'll eventually handle adding new items
    items = get_items_with_stock()
    return render_template("transactions/items.html", items=items)

@transaction_bp.route("/transaction/submit", methods=["POST"])
def submit_transaction():
    # This is where the form sends the data
    user_id = session.get("user_id")
    user_name = session.get("username")
    
    # Process the data (you'll eventually loop through multiple items here)
    # add_transaction(...)
    
    return redirect(url_for('index'))