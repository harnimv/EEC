from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from config import ENV

app = Flask(__name__)
DATABASE = 'mydatabase.db'
app.secret_key = 'your_super_secret_key'  # Change this to a secure key

# Function to get a database connection
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# Route to display users
@app.route('/users')
def get_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    conn.close()
    return render_template('users.html', users=users)

# Route to add a user
@app.route('/add_user', methods=['POST'])
def add_user():
    username = request.form['username']
    password = request.form['password']

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
    conn.commit()
    conn.close()

    return redirect(url_for('get_users'))  # Redirect to the user list

# Route to display purchases
@app.route('/purchases')
def get_purchases():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM purchases")
    purchases = cursor.fetchall()
    conn.close()
    return render_template('purchases.html', purchases=purchases)

# Route for the home page
@app.route('/home')
@app.route('/')
def home():
    return render_template('index.html')

# Route for user registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        address = request.form['address']
        pin_code = request.form['pin_code']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            return "Passwords do not match!", 400

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("INSERT INTO users (name, email, phone, address, pin_code, password) VALUES (?, ?, ?, ?, ?, ?)", 
                           (name, email, phone, address, pin_code, hashed_password))
            conn.commit()
        except sqlite3.IntegrityError:
            return "Email already registered!", 400  # Handle duplicate email

        conn.close()
        return redirect(url_for('login'))

    return render_template('register.html')

# Route for user login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['name'] = user['name']
            return redirect(url_for('dashboard'))
        else:
            return "Invalid email or password!", 401

    return render_template('login.html')

# Route for the dashboard
@app.route('/dashboard', methods=['GET'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect if not logged in

    user_id = session['user_id']
    
    conn = get_db_connection()
    user = conn.execute("SELECT name, email FROM users WHERE id = ?", (user_id,)).fetchone()
    orders = conn.execute("SELECT * FROM purchases WHERE user_id = ?", (user_id,)).fetchall()
    stock = []  # Placeholder for stock data
    conn.close()

    return render_template('dashboard.html', user=user, orders=orders, stock=stock)


# API to view all orders
@app.route('/view_orders', methods=['GET'])
def view_orders():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401  # Return error if not logged in

    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch all orders from the purchases table
    cursor.execute("SELECT * FROM purchases")
    orders = cursor.fetchall()
    conn.close()

    # Convert orders to a list of dictionaries
    orders_list = [dict(order) for order in orders]

    # Return the orders as a JSON response
    return jsonify(orders_list)

# Route to handle purchase form submission
@app.route('/add_purchase', methods=['POST'])
def add_purchase():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect if not logged in

    user_id = session['user_id']
    product_name = request.form['product_name']
    quantity = int(request.form['quantity'])
    price = float(request.form['price'])
    total_price = quantity * price
    status = request.form.get('status', 'pending')  # Default to 'pending' if status is not provided

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO purchases (user_id, product_name, quantity, price, total_price, status) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, product_name, quantity, price, total_price, status)
    )
    conn.commit()
    conn.close()

    return redirect(url_for('dashboard'))  # Redirect to the dashboard after adding the purchase

# API to get all purchases
@app.route('/api/purchases', methods=['GET'])
def api_get_purchases():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401  # Return error if not logged in

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM purchases WHERE user_id = ?", (user_id,))
    purchases = cursor.fetchall()
    conn.close()

    # Convert purchases to a list of dictionaries
    purchases_list = [dict(purchase) for purchase in purchases]
    return jsonify(purchases_list)

# API to add a new purchase
@app.route('/api/purchases', methods=['POST'])
def api_add_purchase():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401  # Return error if not logged in

    user_id = session['user_id']
    data = request.json
    product_name = data.get('product_name')
    quantity = int(data.get('quantity'))
    price = float(data.get('price'))
    total_price = quantity * price
    status = data.get('status', 'pending')  # Default to 'pending' if status is not provided

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO purchases (user_id, product_name, quantity, price, total_price, status) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, product_name, quantity, price, total_price, status)
    )
    conn.commit()
    conn.close()

    return jsonify({
        "message": "Purchase added successfully",
        "product_name": product_name,
        "quantity": quantity,
        "price": price,
        "total_price": total_price,
        "status": status
    }), 201

# Route for user logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Route to create tables (for development purposes)
@app.route("/create_tables")
def create_tables():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # Create Users Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone_no TEXT NOT NULL,
            address TEXT NOT NULL,
            pin_code TEXT NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    # Create Purchases Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            total_price REAL NOT NULL,
            status TEXT CHECK(status IN ('pending', 'completed')) DEFAULT 'pending',
            purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create Stock Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            available_quantity INTEGER NOT NULL
        )
    ''')

    conn.commit()  # Save changes
    conn.close()   # Close connection
    print("Tables created successfully!")

    return {
        "message": "Tables created"
    }


# Route to create a new order
@app.route('/create_order', methods=['GET', 'POST'])
def create_order():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect if not logged in

    if request.method == 'POST':
        user_id = session['user_id']
        product_name = request.form['product_name']
        quantity = int(request.form['quantity'])
        price = float(request.form['price'])
        total_price = quantity * price
        status = request.form.get('status', 'pending')  # Default to 'pending' if status is not provided

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO purchases (user_id, product_name, quantity, price, total_price, status) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, product_name, quantity, price, total_price, status)
        )
        conn.commit()
        conn.close()

        return redirect(url_for('orders_page'))  # Redirect to the orders page after creating the order

    return render_template('create_order.html')

# Route to fetch and display orders
@app.route('/orders')
def orders_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect if not logged in

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM purchases WHERE user_id = ?", (user_id,))
    orders = cursor.fetchall()
    conn.close()

    return render_template('orders.html', orders=orders)


if __name__ == '__main__':
    app.run(debug=True)