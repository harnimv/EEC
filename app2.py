from datetime import timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
DATABASE = 'mydatabase.db'
app.secret_key = 'your_super_secret_key'  # Change this to a secure key
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)  # Session timeout
app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = False  # Suppress debugger resource logs

# Function to get a database connection
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

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
            phone TEXT NOT NULL,
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
            flash('Passwords do not match!', 'error')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO users (name, email, phone, address, pin_code, password) VALUES (?, ?, ?, ?, ?, ?)",
                (name, email, phone, address, pin_code, hashed_password)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            flash('Email already registered!', 'error')
            return redirect(url_for('register'))
        finally:
            conn.close()

        flash('Account created successfully! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

# Route for user login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['name'] = user['name']
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password!', 'error')
            return redirect(url_for('login'))

    return render_template('login.html')

# Route for the dashboard
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect if not logged in

    user_id = session['user_id']
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    orders = conn.execute("SELECT * FROM purchases WHERE user_id = ?", (user_id,)).fetchall()
    conn.close()

    # Calculate the number of total, pending, and completed orders
    total_orders = len(orders)
    pending_orders = len([order for order in orders if order['status'] == 'pending'])
    completed_orders = len([order for order in orders if order['status'] == 'completed'])

    return render_template(
        'dashboard.html',
        user=user,
        orders=orders,
        total_orders=total_orders,
        pending_orders=pending_orders,
        completed_orders=completed_orders
    )

# Profile route
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect if not logged in

    user_id = session['user_id']
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()

    if not user:
        return "User not found!", 404  # Handle case where user is not found

    return render_template('profile.html', user=user)

# Update profile route
@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect if not logged in

    user_id = session['user_id']
    name = request.form['name']
    email = request.form['email']
    phone = request.form['phone']
    address = request.form['address']
    pin_code = request.form['pin_code']
    password = request.form['password']

    conn = get_db_connection()
    cursor = conn.cursor()

    # Update user information
    if password:
        hashed_password = generate_password_hash(password)
        cursor.execute(
            "UPDATE users SET name = ?, email = ?, phone = ?, address = ?, pin_code = ?, password = ? WHERE id = ?",
            (name, email, phone, address, pin_code, hashed_password, user_id)
        )
    else:
        cursor.execute(
            "UPDATE users SET name = ?, email = ?, phone = ?, address = ?, pin_code = ? WHERE id = ?",
            (name, email, phone, address, pin_code, user_id)
        )

    conn.commit()
    conn.close()

    # Update the session with the new name
    session['name'] = name

    flash('Profile updated successfully!', 'success')
    return redirect(url_for('profile'))

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

# Route for user logout
@app.route('/logout')
def logout():
    session.clear()  # Clear the session data
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('home'))

# Run the application
if __name__ == "__main__":
    app.run(debug=True)