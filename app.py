import streamlit as st
import sqlite3
import hashlib
import secrets
import pandas as pd
from datetime import datetime
import re
import os

# ==================== PASSWORD HASHING ====================

def hash_password(password):
    """Hash password using SHA-256 with salt"""
    salt = secrets.token_hex(16)
    hash_obj = hashlib.sha256((password + salt).encode())
    return f"{salt}:{hash_obj.hexdigest()}"

def verify_password(password, hashed_password):
    """Verify password against hash"""
    try:
        salt, stored_hash = hashed_password.split(':')
        hash_obj = hashlib.sha256((password + salt).encode())
        return hash_obj.hexdigest() == stored_hash
    except:
        return False

# ==================== DATABASE SETUP ====================

def init_database():
    """Initialize SQLite database with all tables"""
    conn = sqlite3.connect('bookexchange.db')
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            address TEXT,
            phone TEXT,
            bio TEXT,
            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            is_admin INTEGER DEFAULT 0,
            reputation_score INTEGER DEFAULT 0,
            total_exchanges INTEGER DEFAULT 0,
            last_login TIMESTAMP
        )
    ''')
    
    # Categories table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Categories (
            category_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_name TEXT UNIQUE NOT NULL,
            description TEXT
        )
    ''')
    
    # Books table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Books (
            book_id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            category_id INTEGER,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            isbn TEXT,
            book_condition TEXT NOT NULL,
            description TEXT,
            image_url TEXT,
            status TEXT DEFAULT 'Available',
            views_count INTEGER DEFAULT 0,
            request_count INTEGER DEFAULT 0,
            posted_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES Users(user_id),
            FOREIGN KEY (category_id) REFERENCES Categories(category_id)
        )
    ''')
    
    # Exchanges table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Exchanges (
            exchange_id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            requester_id INTEGER NOT NULL,
            owner_id INTEGER NOT NULL,
            status TEXT DEFAULT 'Pending',
            request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            approval_date TIMESTAMP,
            completion_date TIMESTAMP,
            cancellation_date TIMESTAMP,
            meeting_location TEXT,
            meeting_time TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (book_id) REFERENCES Books(book_id),
            FOREIGN KEY (requester_id) REFERENCES Users(user_id),
            FOREIGN KEY (owner_id) REFERENCES Users(user_id)
        )
    ''')
    
    # Reviews table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Reviews (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            exchange_id INTEGER NOT NULL,
            reviewer_id INTEGER NOT NULL,
            reviewed_user_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT,
            review_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (exchange_id) REFERENCES Exchanges(exchange_id),
            FOREIGN KEY (reviewer_id) REFERENCES Users(user_id),
            FOREIGN KEY (reviewed_user_id) REFERENCES Users(user_id)
        )
    ''')
    
    # Notifications table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Notifications (
            notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            related_id INTEGER,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES Users(user_id)
        )
    ''')
    
    # Wishlist table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Wishlist (
            wishlist_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            book_id INTEGER NOT NULL,
            added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES Users(user_id),
            FOREIGN KEY (book_id) REFERENCES Books(book_id),
            UNIQUE(user_id, book_id)
        )
    ''')
    
    # Insert default categories
    categories = [
        'Fiction', 'Non-Fiction', 'Mystery', 'Science Fiction', 
        'Fantasy', 'Romance', 'Thriller', 'Biography', 
        'History', 'Self-Help', 'Poetry', 'Children', 
        'Young Adult', 'Educational'
    ]
    
    for cat in categories:
        cursor.execute('INSERT OR IGNORE INTO Categories (category_name) VALUES (?)', (cat,))
    
    # Create admin user if not exists (password: admin123)
    admin_exists = cursor.execute("SELECT user_id FROM Users WHERE username = 'admin'").fetchone()
    if not admin_exists:
        admin_password = hash_password('admin123')
        cursor.execute("""
            INSERT INTO Users (username, email, password_hash, full_name, is_admin)
            VALUES (?, ?, ?, ?, ?)
        """, ('admin', 'admin@bookexchange.com', admin_password, 'System Administrator', 1))
    
    conn.commit()
    conn.close()

# Initialize database
init_database()

def get_db_connection():
    """Get database connection"""
    return sqlite3.connect('bookexchange.db')

def execute_query(query, params=None, fetch=True):
    """Execute SQL query"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        if fetch and query.strip().upper().startswith('SELECT'):
            columns = [description[0] for description in cursor.description]
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            conn.close()
            return results
        else:
            conn.commit()
            conn.close()
            return True
    except Exception as e:
        conn.rollback()
        conn.close()
        st.error(f"Database error: {e}")
        return None if fetch else False

# ==================== USER FUNCTIONS ====================

def register_user(username, email, password, full_name, address=None, phone=None, bio=None):
    """Register new user"""
    existing = execute_query(
        "SELECT user_id FROM Users WHERE email = ? OR username = ?",
        (email, username)
    )
    if existing:
        return False, "Email or username already exists"
    
    hashed = hash_password(password)
    
    success = execute_query("""
        INSERT INTO Users (username, email, password_hash, full_name, address, phone, bio)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (username, email, hashed, full_name, address, phone, bio), fetch=False)
    
    if success:
        return True, "Registration successful"
    return False, "Registration failed"

def login_user(email, password):
    """Authenticate user"""
    user = execute_query(
        "SELECT user_id, username, password_hash, is_admin FROM Users WHERE email = ? AND is_active = 1",
        (email,)
    )
    
    if user and verify_password(password, user[0]['password_hash']):
        execute_query(
            "UPDATE Users SET last_login = CURRENT_TIMESTAMP WHERE user_id = ?",
            (user[0]['user_id'],), fetch=False
        )
        return True, user[0]
    return False, None

def get_user_profile(user_id):
    """Get user profile"""
    user = execute_query("""
        SELECT user_id, username, email, full_name, address, phone, bio, 
               join_date, reputation_score, total_exchanges
        FROM Users WHERE user_id = ?
    """, (user_id,))
    return user[0] if user else None

def update_user_profile(user_id, full_name, address, phone, bio):
    """Update user profile"""
    return execute_query("""
        UPDATE Users 
        SET full_name = ?, address = ?, phone = ?, bio = ?
        WHERE user_id = ?
    """, (full_name, address, phone, bio, user_id), fetch=False)

# ==================== BOOK FUNCTIONS ====================

def get_categories():
    """Get all categories"""
    cats = execute_query("SELECT category_name FROM Categories ORDER BY category_name")
    return [cat['category_name'] for cat in cats] if cats else []

def add_book(owner_id, title, author, category, condition, description, isbn=None, image_url=None):
    """Add a new book"""
    cat = execute_query(
        "SELECT category_id FROM Categories WHERE category_name = ?",
        (category,)
    )
    category_id = cat[0]['category_id'] if cat else None
    
    return execute_query("""
        INSERT INTO Books (owner_id, category_id, title, author, isbn, book_condition, description, image_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (owner_id, category_id, title, author, isbn, condition, description, image_url), fetch=False)

def get_all_available_books():
    """Get all available books"""
    books = execute_query("""
        SELECT b.*, u.username as owner_name, u.reputation_score, c.category_name
        FROM Books b
        JOIN Users u ON b.owner_id = u.user_id
        LEFT JOIN Categories c ON b.category_id = c.category_id
        WHERE b.status = 'Available'
        ORDER BY b.posted_date DESC
    """)
    return books if books else []

def get_user_books(user_id):
    """Get user's books"""
    books = execute_query("""
        SELECT b.*, c.category_name
        FROM Books b
        LEFT JOIN Categories c ON b.category_id = c.category_id
        WHERE b.owner_id = ?
        ORDER BY b.posted_date DESC
    """, (user_id,))
    return books if books else []

def get_book_by_id(book_id):
    """Get book details"""
    book = execute_query("""
        SELECT b.*, u.username as owner_name, u.email as owner_email, 
               u.reputation_score, u.phone, c.category_name
        FROM Books b
        JOIN Users u ON b.owner_id = u.user_id
        LEFT JOIN Categories c ON b.category_id = c.category_id
        WHERE b.book_id = ?
    """, (book_id,))
    return book[0] if book else None

def update_book(book_id, title, author, condition, description):
    """Update book"""
    return execute_query("""
        UPDATE Books 
        SET title = ?, author = ?, book_condition = ?, description = ?, updated_date = CURRENT_TIMESTAMP
        WHERE book_id = ?
    """, (title, author, condition, description, book_id), fetch=False)

def delete_book(book_id):
    """Delete book"""
    return execute_query("DELETE FROM Books WHERE book_id = ?", (book_id,), fetch=False)

def search_books(search_term, category=None, condition=None):
    """Search books"""
    query = """
        SELECT b.*, u.username as owner_name, c.category_name
        FROM Books b
        JOIN Users u ON b.owner_id = u.user_id
        LEFT JOIN Categories c ON b.category_id = c.category_id
        WHERE (b.title LIKE ? OR b.author LIKE ?) AND b.status = 'Available'
    """
    params = [f'%{search_term}%', f'%{search_term}%']
    
    if category and category != 'All':
        query += " AND c.category_name = ?"
        params.append(category)
    if condition and condition != 'All':
        query += " AND b.book_condition = ?"
        params.append(condition)
    
    query += " ORDER BY b.posted_date DESC"
    books = execute_query(query, tuple(params))
    return books if books else []

# ==================== EXCHANGE FUNCTIONS ====================

def create_exchange_request(book_id, requester_id, meeting_location=None, notes=None):
    """Create exchange request"""
    book = execute_query(
        "SELECT owner_id, status FROM Books WHERE book_id = ?",
        (book_id,)
    )
    
    if not book:
        return False, "Book not found"
    
    if book[0]['status'] != 'Available':
        return False, "Book is not available"
    
    if book[0]['owner_id'] == requester_id:
        return False, "You cannot request your own book"
    
    success = execute_query("""
        INSERT INTO Exchanges (book_id, requester_id, owner_id, meeting_location, notes)
        VALUES (?, ?, ?, ?, ?)
    """, (book_id, requester_id, book[0]['owner_id'], meeting_location, notes), fetch=False)
    
    if success:
        execute_query(
            "UPDATE Books SET status = 'Requested', updated_date = CURRENT_TIMESTAMP WHERE book_id = ?",
            (book_id,), fetch=False
        )
        
        execute_query("""
            INSERT INTO Notifications (user_id, type, title, message, related_id)
            VALUES (?, 'Exchange_Request', 'New Exchange Request', 
                    'Someone wants to exchange your book', ?)
        """, (book[0]['owner_id'], book_id), fetch=False)
        
        return True, "Request sent successfully"
    
    return False, "Failed to send request"

def get_user_exchanges(user_id):
    """Get user exchanges"""
    exchanges = execute_query("""
        SELECT e.*, b.title as book_title, b.author,
               u1.username as requester_name,
               u2.username as owner_name
        FROM Exchanges e
        JOIN Books b ON e.book_id = b.book_id
        JOIN Users u1 ON e.requester_id = u1.user_id
        JOIN Users u2 ON e.owner_id = u2.user_id
        WHERE e.requester_id = ? OR e.owner_id = ?
        ORDER BY e.request_date DESC
    """, (user_id, user_id))
    return exchanges if exchanges else []

def update_exchange_status(exchange_id, status, user_id):
    """Update exchange status"""
    exchange = execute_query(
        "SELECT owner_id, requester_id, book_id FROM Exchanges WHERE exchange_id = ?",
        (exchange_id,)
    )
    
    if not exchange:
        return False, "Exchange not found"
    
    exchange = exchange[0]
    
    if status == 'Approved' and exchange['owner_id'] != user_id:
        return False, "Only owner can approve requests"
    elif status == 'Cancelled' and exchange['requester_id'] != user_id:
        return False, "Only requester can cancel"
    
    if status == 'Approved':
        success = execute_query("""
            UPDATE Exchanges SET status = 'Approved', approval_date = CURRENT_TIMESTAMP
            WHERE exchange_id = ?
        """, (exchange_id,), fetch=False)
        
        if success:
            execute_query(
                "UPDATE Books SET status = 'Reserved' WHERE book_id = ?",
                (exchange['book_id'],), fetch=False
            )
            execute_query("""
                INSERT INTO Notifications (user_id, type, title, message, related_id)
                VALUES (?, 'Exchange_Response', 'Request Approved', 
                        'Your exchange request has been approved!', ?)
            """, (exchange['requester_id'], exchange_id), fetch=False)
            return True, "Exchange approved"
    
    elif status == 'Completed':
        success = execute_query("""
            UPDATE Exchanges SET status = 'Completed', completion_date = CURRENT_TIMESTAMP
            WHERE exchange_id = ?
        """, (exchange_id,), fetch=False)
        
        if success:
            execute_query(
                "UPDATE Books SET status = 'Exchanged' WHERE book_id = ?",
                (exchange['book_id'],), fetch=False
            )
            execute_query("""
                UPDATE Users SET total_exchanges = total_exchanges + 1
                WHERE user_id IN (?, ?)
            """, (exchange['owner_id'], exchange['requester_id']), fetch=False)
            return True, "Exchange completed"
    
    elif status == 'Rejected':
        success = execute_query("""
            UPDATE Exchanges SET status = 'Rejected', cancellation_date = CURRENT_TIMESTAMP
            WHERE exchange_id = ?
        """, (exchange_id,), fetch=False)
        
        if success:
            execute_query(
                "UPDATE Books SET status = 'Available' WHERE book_id = ?",
                (exchange['book_id'],), fetch=False
            )
            return True, "Exchange rejected"
    
    elif status == 'Cancelled':
        success = execute_query("""
            UPDATE Exchanges SET status = 'Cancelled', cancellation_date = CURRENT_TIMESTAMP
            WHERE exchange_id = ?
        """, (exchange_id,), fetch=False)
        
        if success:
            execute_query(
                "UPDATE Books SET status = 'Available' WHERE book_id = ?",
                (exchange['book_id'],), fetch=False
            )
            return True, "Exchange cancelled"
    
    return False, "Failed to update"

# ==================== NOTIFICATION FUNCTIONS ====================

def get_notifications(user_id):
    """Get user notifications"""
    notifications = execute_query("""
        SELECT * FROM Notifications 
        WHERE user_id = ? 
        ORDER BY created_at DESC
    """, (user_id,))
    return notifications if notifications else []

def mark_notification_read(notification_id):
    """Mark notification as read"""
    return execute_query(
        "UPDATE Notifications SET is_read = 1 WHERE notification_id = ?",
        (notification_id,), fetch=False
    )

# ==================== REVIEW FUNCTIONS ====================

def add_review(exchange_id, reviewer_id, reviewed_user_id, rating, comment):
    """Add review"""
    return execute_query("""
        INSERT INTO Reviews (exchange_id, reviewer_id, reviewed_user_id, rating, comment)
        VALUES (?, ?, ?, ?, ?)
    """, (exchange_id, reviewer_id, reviewed_user_id, rating, comment), fetch=False)

def get_user_stats(user_id):
    """Get user statistics"""
    stats = execute_query("""
        SELECT 
            (SELECT COUNT(*) FROM Books WHERE owner_id = ?) as total_books,
            (SELECT COUNT(*) FROM Exchanges WHERE requester_id = ? OR owner_id = ?) as total_exchanges,
            (SELECT COUNT(*) FROM Exchanges WHERE (requester_id = ? OR owner_id = ?) AND status = 'Completed') as completed_exchanges,
            (SELECT AVG(rating) FROM Reviews WHERE reviewed_user_id = ?) as avg_rating,
            (SELECT reputation_score FROM Users WHERE user_id = ?) as reputation
    """, (user_id, user_id, user_id, user_id, user_id, user_id, user_id))
    
    return stats[0] if stats else None

# ==================== WISHLIST FUNCTIONS ====================

def add_to_wishlist(user_id, book_id):
    """Add to wishlist"""
    return execute_query(
        "INSERT OR IGNORE INTO Wishlist (user_id, book_id) VALUES (?, ?)",
        (user_id, book_id), fetch=False
    )

def remove_from_wishlist(user_id, book_id):
    """Remove from wishlist"""
    return execute_query(
        "DELETE FROM Wishlist WHERE user_id = ? AND book_id = ?",
        (user_id, book_id), fetch=False
    )

def get_wishlist(user_id):
    """Get wishlist"""
    wishlist = execute_query("""
        SELECT w.*, b.title, b.author, b.book_condition, b.status, u.username as owner_name
        FROM Wishlist w
        JOIN Books b ON w.book_id = b.book_id
        JOIN Users u ON b.owner_id = u.user_id
        WHERE w.user_id = ?
        ORDER BY w.added_date DESC
    """, (user_id,))
    return wishlist if wishlist else []

# ==================== ADMIN FUNCTIONS ====================

def get_system_stats():
    """Get system statistics"""
    stats = execute_query("""
        SELECT 
            (SELECT COUNT(*) FROM Users) as total_users,
            (SELECT COUNT(*) FROM Books) as total_books,
            (SELECT COUNT(*) FROM Exchanges) as total_exchanges,
            (SELECT COUNT(*) FROM Exchanges WHERE status = 'Completed') as completed_exchanges,
            (SELECT COUNT(*) FROM Exchanges WHERE status = 'Pending') as pending_exchanges,
            (SELECT AVG(rating) FROM Reviews) as avg_rating
    """)
    return stats[0] if stats else None

def get_all_users():
    """Get all users"""
    users = execute_query("""
        SELECT user_id, username, email, full_name, join_date, is_active, 
               is_admin, reputation_score, total_exchanges
        FROM Users
        ORDER BY join_date DESC
    """)
    return users if users else []

def update_user_status(user_id, is_active):
    """Update user status"""
    return execute_query(
        "UPDATE Users SET is_active = ? WHERE user_id = ?",
        (1 if is_active else 0, user_id), fetch=False
    )

# ==================== PAGE COMPONENTS ====================

def show_home():
    """Home page"""
    st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .book-card {
        background-color: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
        border: 1px solid #e0e0e0;
    }
    .status-badge {
        padding: 0.25rem 0.5rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: bold;
        display: inline-block;
        background-color: #10b981;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="main-header">
        <h1>📚 Welcome to BookExchange</h1>
        <p>Share books, discover new reads, and connect with fellow book lovers!</p>
    </div>
    """, unsafe_allow_html=True)
    
    stats = get_system_stats()
    if stats:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Users", stats['total_users'])
        with col2:
            st.metric("Books Available", stats['total_books'])
        with col3:
            st.metric("Total Exchanges", stats['total_exchanges'])
        with col4:
            st.metric("Completed", stats['completed_exchanges'])
    
    st.subheader("📖 Featured Books")
    books = get_all_available_books()
    
    if books:
        for i in range(0, min(len(books), 6), 3):
            cols = st.columns(3)
            for j in range(3):
                if i + j < len(books):
                    book = books[i + j]
                    with cols[j]:
                        with st.container():
                            st.markdown(f"""
                            <div class="book-card">
                                <h4>{book['title'][:50]}</h4>
                                <p><strong>By:</strong> {book['author'][:30]}</p>
                                <p><strong>Owner:</strong> {book['owner_name']}</p>
                                <p><strong>Condition:</strong> {book['book_condition']}</p>
                                <span class="status-badge">{book['status']}</span>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            if st.button(f"View Details", key=f"view_{book['book_id']}"):
                                st.session_state.selected_book = book['book_id']
                                st.session_state.page = "book_details"
                                st.rerun()
    else:
        st.info("No books available yet. Be the first to add a book!")
    
    st.subheader("🚀 How It Works")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("### 1. 📝 Register\nCreate your free account")
    with col2:
        st.markdown("### 2. 📚 Add Books\nList books to exchange")
    with col3:
        st.markdown("### 3. 🤝 Exchange\nRequest and meet readers")

def show_login():
    """Login page"""
    st.title("🔐 Login to Your Account")
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        with st.form("login_form"):
            email = st.text_input("Email Address")
            password = st.text_input("Password", type="password")
            
            if st.form_submit_button("Login", use_container_width=True):
                if email and password:
                    success, user = login_user(email, password)
                    if success:
                        st.session_state.authenticated = True
                        st.session_state.user_id = user['user_id']
                        st.session_state.username = user['username']
                        st.session_state.is_admin = user['is_admin']
                        st.success("Login successful!")
                        st.session_state.page = "dashboard"
                        st.rerun()
                    else:
                        st.error("Invalid email or password")
        
        st.markdown("---")
        if st.button("Create New Account", use_container_width=True):
            st.session_state.page = "register"
            st.rerun()

def show_register():
    """Registration page"""
    st.title("📝 Create New Account")
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        with st.form("register_form"):
            username = st.text_input("Username *")
            email = st.text_input("Email *")
            full_name = st.text_input("Full Name *")
            password = st.text_input("Password *", type="password")
            confirm = st.text_input("Confirm Password *", type="password")
            phone = st.text_input("Phone Number")
            address = st.text_area("Address")
            bio = st.text_area("Bio")
            
            if st.form_submit_button("Register", use_container_width=True):
                if len(username) < 3:
                    st.error("Username must be at least 3 characters")
                elif not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
                    st.error("Invalid email format")
                elif len(password) < 6:
                    st.error("Password must be at least 6 characters")
                elif password != confirm:
                    st.error("Passwords do not match")
                else:
                    success, msg = register_user(username, email, password, full_name, address, phone, bio)
                    if success:
                        st.success(msg)
                        st.session_state.page = "login"
                        st.rerun()
                    else:
                        st.error(msg)

def show_dashboard():
    """Dashboard"""
    st.title(f"📊 Welcome back, {st.session_state.username}!")
    
    stats = get_user_stats(st.session_state.user_id)
    if stats:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("My Books", int(stats['total_books']))
        with col2:
            st.metric("Total Exchanges", int(stats['total_exchanges']))
        with col3:
            st.metric("Completed", int(stats['completed_exchanges']))
        with col4:
            rating = stats['avg_rating'] if stats['avg_rating'] else 0
            st.metric("Rating", f"{rating:.1f} ⭐")
    
    st.subheader("📋 Recent Activity")
    exchanges = get_user_exchanges(st.session_state.user_id)
    
    if exchanges:
        for ex in exchanges[:5]:
            with st.container():
                col1, col2, col3 = st.columns([2,2,1])
                with col1:
                    st.write(f"**{ex['book_title']}**")
                    st.write(f"by {ex['author']}")
                with col2:
                    if ex['requester_id'] == st.session_state.user_id:
                        st.write(f"Requested from: {ex['owner_name']}")
                    else:
                        st.write(f"Requested by: {ex['requester_name']}")
                with col3:
                    status_icons = {'Pending': '🟡', 'Approved': '🔵', 'Completed': '🟢', 'Rejected': '🔴'}
                    icon = status_icons.get(ex['status'], '⚪')
                    st.write(f"{icon} {ex['status']}")
                st.divider()
    else:
        st.info("No exchanges yet. Start browsing books!")
    
    st.subheader("⚡ Quick Actions")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("➕ Add New Book", use_container_width=True):
            st.session_state.page = "add_book"
            st.rerun()
    with col2:
        if st.button("🔍 Browse Books", use_container_width=True):
            st.session_state.page = "browse"
            st.rerun()

def show_add_book():
    """Add book page"""
    st.title("➕ Add a New Book")
    
    with st.form("add_book_form"):
        title = st.text_input("Book Title *")
        author = st.text_input("Author *")
        
        categories = get_categories()
        category = st.selectbox("Category *", categories)
        
        condition = st.selectbox("Condition *", ["New", "Like New", "Good", "Fair", "Poor"])
        description = st.text_area("Description")
        isbn = st.text_input("ISBN (Optional)")
        image_url = st.text_input("Image URL (Optional)")
        
        if st.form_submit_button("Add Book", use_container_width=True):
            if title and author:
                success = add_book(
                    st.session_state.user_id, title, author, category, 
                    condition, description, isbn, image_url
                )
                if success:
                    st.success("Book added successfully!")
                    st.session_state.page = "my_books"
                    st.rerun()
                else:
                    st.error("Failed to add book")
            else:
                st.error("Please fill in all required fields")

def show_my_books():
    """My books page"""
    st.title("📚 My Books")
    
    books = get_user_books(st.session_state.user_id)
    
    if not books:
        st.info("You haven't added any books yet.")
        if st.button("Add Your First Book"):
            st.session_state.page = "add_book"
            st.rerun()
    else:
        for book in books:
            with st.expander(f"📖 {book['title']} - {book['author']}"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**Condition:** {book['book_condition']}")
                    st.write(f"**Status:** {book['status']}")
                    if book['description']:
                        st.write(f"**Description:** {book['description']}")
                with col2:
                    if st.button(f"Edit", key=f"edit_{book['book_id']}"):
                        st.session_state.edit_book = book
                        st.session_state.page = "edit_book"
                        st.rerun()
                    if st.button(f"Delete", key=f"delete_{book['book_id']}"):
                        if delete_book(book['book_id']):
                            st.success("Book deleted!")
                            st.rerun()

def show_browse_books():
    """Browse books page"""
    st.title("🔍 Browse Books")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        search_term = st.text_input("Search by title or author")
    with col2:
        categories = ["All"] + get_categories()
        category = st.selectbox("Category", categories)
    with col3:
        conditions = ["All", "New", "Like New", "Good", "Fair", "Poor"]
        condition = st.selectbox("Condition", conditions)
    
    if search_term:
        books = search_books(search_term, category if category != "All" else None, 
                            condition if condition != "All" else None)
    else:
        books = get_all_available_books()
        if category != "All":
            books = [b for b in books if b.get('category_name') == category]
        if condition != "All":
            books = [b for b in books if b.get('book_condition') == condition]
    
    if not books:
        st.info("No books found matching your criteria.")
    else:
        for book in books:
            with st.container():
                col1, col2, col3 = st.columns([3, 2, 1])
                with col1:
                    st.markdown(f"### {book['title']}")
                    st.write(f"*by {book['author']}*")
                    st.write(f"📚 {book.get('category_name', 'Uncategorized')} | 📖 {book['book_condition']}")
                with col2:
                    st.write(f"**Owner:** {book['owner_name']}")
                    st.write(f"⭐ Rating: {book.get('reputation_score', 0)}")
                with col3:
                    if st.button(f"Request Book", key=f"req_{book['book_id']}"):
                        st.session_state.request_book = book['book_id']
                        st.session_state.page = "request_book"
                        st.rerun()
                    if st.button(f"Add to Wishlist", key=f"wish_{book['book_id']}"):
                        add_to_wishlist(st.session_state.user_id, book['book_id'])
                        st.success("Added to wishlist!")
                st.divider()

def show_my_exchanges():
    """My exchanges page"""
    st.title("🔄 My Exchanges")
    
    exchanges = get_user_exchanges(st.session_state.user_id)
    
    if not exchanges:
        st.info("No exchange requests yet.")
        return
    
    tab1, tab2, tab3, tab4 = st.tabs(["Pending", "Approved", "Completed", "All"])
    
    with tab1:
        pending = [e for e in exchanges if e['status'] == 'Pending']
        for ex in pending:
            display_exchange(ex)
    
    with tab2:
        approved = [e for e in exchanges if e['status'] == 'Approved']
        for ex in approved:
            display_exchange(ex)
    
    with tab3:
        completed = [e for e in exchanges if e['status'] == 'Completed']
        for ex in completed:
            display_exchange(ex)
    
    with tab4:
        for ex in exchanges:
            display_exchange(ex)

def display_exchange(exchange):
    """Display exchange details"""
    with st.container():
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            st.markdown(f"**{exchange['book_title']}**")
            st.write(f"by {exchange['author']}")
        with col2:
            if exchange['requester_id'] == st.session_state.user_id:
                st.write(f"Requested from: {exchange['owner_name']}")
                is_owner = False
            else:
                st.write(f"Requested by: {exchange['requester_name']}")
                is_owner = True
            st.write(f"Date: {exchange['request_date']}")
        with col3:
            status_icons = {'Pending': '🟡', 'Approved': '🔵', 'Completed': '🟢', 'Rejected': '🔴', 'Cancelled': '⚪'}
            icon = status_icons.get(exchange['status'], '⚪')
            st.write(f"{icon} {exchange['status']}")
            
            if exchange['status'] == 'Pending' and is_owner:
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button(f"Approve", key=f"app_{exchange['exchange_id']}"):
                        success, msg = update_exchange_status(
                            exchange['exchange_id'], 'Approved', st.session_state.user_id
                        )
                        if success:
                            st.success(msg)
                            st.rerun()
                with col_b:
                    if st.button(f"Reject", key=f"rej_{exchange['exchange_id']}"):
                        success, msg = update_exchange_status(
                            exchange['exchange_id'], 'Rejected', st.session_state.user_id
                        )
                        if success:
                            st.success(msg)
                            st.rerun()
            
            elif exchange['status'] == 'Pending' and not is_owner:
                if st.button(f"Cancel Request", key=f"can_{exchange['exchange_id']}"):
                    success, msg = update_exchange_status(
                        exchange['exchange_id'], 'Cancelled', st.session_state.user_id
                    )
                    if success:
                        st.success(msg)
                        st.rerun()
            
            elif exchange['status'] == 'Approved':
                if st.button(f"Mark Complete", key=f"comp_{exchange['exchange_id']}"):
                    success, msg = update_exchange_status(
                        exchange['exchange_id'], 'Completed', st.session_state.user_id
                    )
                    if success:
                        st.success(msg)
                        st.rerun()
            
            elif exchange['status'] == 'Completed':
                if st.button(f"Add Review", key=f"rev_{exchange['exchange_id']}"):
                    st.session_state.review_exchange = exchange
                    st.session_state.page = "add_review"
                    st.rerun()
        
        st.divider()

def show_notifications():
    """Notifications page"""
    st.title("🔔 Notifications")
    
    notifications = get_notifications(st.session_state.user_id)
    
    if not notifications:
        st.info("No notifications yet.")
        return
    
    for notif in notifications:
        with st.container():
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"**{notif['title']}**")
                st.write(notif['message'])
                st.caption(notif['created_at'])
            with col2:
                if not notif['is_read']:
                    if st.button(f"Mark Read", key=f"read_{notif['notification_id']}"):
                        mark_notification_read(notif['notification_id'])
                        st.rerun()
            st.divider()

def show_profile():
    """Profile page"""
    st.title("👤 My Profile")
    
    user = get_user_profile(st.session_state.user_id)
    
    if not user:
        st.error("User not found")
        return
    
    with st.form("profile_form"):
        full_name = st.text_input("Full Name", user['full_name'])
        phone = st.text_input("Phone", user['phone'] if user['phone'] else "")
        address = st.text_area("Address", user['address'] if user['address'] else "")
        bio = st.text_area("Bio", user['bio'] if user['bio'] else "")
        
        if st.form_submit_button("Update Profile"):
            if update_user_profile(st.session_state.user_id, full_name, address, phone, bio):
                st.success("Profile updated!")
                st.rerun()
            else:
                st.error("Failed to update profile")
    
    st.subheader("📊 Statistics")
    stats = get_user_stats(st.session_state.user_id)
    if stats:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Books Listed", int(stats['total_books']))
        with col2:
            st.metric("Exchanges", int(stats['total_exchanges']))
        with col3:
            rating = stats['avg_rating'] if stats['avg_rating'] else 0
            st.metric("Rating", f"{rating:.1f} ⭐")
    
    st.subheader("💝 My Wishlist")
    wishlist = get_wishlist(st.session_state.user_id)
    
    if wishlist:
        for book in wishlist:
            with st.container():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**{book['title']}** by {book['author']}")
                    st.write(f"Owner: {book['owner_name']} | Condition: {book['book_condition']}")
                with col2:
                    if st.button(f"Remove", key=f"rem_wish_{book['book_id']}"):
                        remove_from_wishlist(st.session_state.user_id, book['book_id'])
                        st.rerun()
                st.divider()
    else:
        st.info("Your wishlist is empty")

def show_admin_dashboard():
    """Admin dashboard"""
    if not st.session_state.is_admin:
        st.error("Access denied. Admin only.")
        return
    
    st.title("🔧 Admin Dashboard")
    
    stats = get_system_stats()
    if stats:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Users", stats['total_users'])
        with col2:
            st.metric("Total Books", stats['total_books'])
        with col3:
            st.metric("Total Exchanges", stats['total_exchanges'])
        with col4:
            st.metric("Pending Exchanges", stats['pending_exchanges'])
    
    st.subheader("👥 User Management")
    users = get_all_users()
    
    if users:
        for user in users:
            with st.expander(f"{user['username']} - {user['email']}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Full Name:** {user['full_name']}")
                    st.write(f"**Joined:** {user['join_date']}")
                    st.write(f"**Reputation:** {user['reputation_score']}")
                with col2:
                    st.write(f"**Exchanges:** {user['total_exchanges']}")
                    status = "Active" if user['is_active'] else "Inactive"
                    st.write(f"**Status:** {status}")
                    if st.button(f"Toggle Status", key=f"toggle_{user['user_id']}"):
                        update_user_status(user['user_id'], not user['is_active'])
                        st.rerun()

def show_add_review():
    """Add review page"""
    if 'review_exchange' not in st.session_state:
        st.session_state.page = "my_exchanges"
        st.rerun()
        return
    
    exchange = st.session_state.review_exchange
    
    st.title("⭐ Add Review")
    
    if exchange['requester_id'] == st.session_state.user_id:
        reviewed_user = exchange['owner_name']
        reviewed_id = exchange['owner_id']
    else:
        reviewed_user = exchange['requester_name']
        reviewed_id = exchange['requester_id']
    
    st.write(f"Exchange for: **{exchange['book_title']}**")
    st.write(f"Exchange with: **{reviewed_user}**")
    
    with st.form("review_form"):
        rating = st.slider("Rating", 1, 5, 5)
        comment = st.text_area("Comment")
        
        if st.form_submit_button("Submit Review"):
            success = add_review(
                exchange['exchange_id'],
                st.session_state.user_id,
                reviewed_id,
                rating,
                comment
            )
            if success:
                st.success("Review submitted!")
                del st.session_state.review_exchange
                st.session_state.page = "my_exchanges"
                st.rerun()
            else:
                st.error("Failed to submit review")

def show_request_book():
    """Request book page"""
    if 'request_book' not in st.session_state:
        st.session_state.page = "browse"
        st.rerun()
        return
    
    book = get_book_by_id(st.session_state.request_book)
    
    if not book:
        st.error("Book not found")
        st.session_state.page = "browse"
        st.rerun()
        return
    
    st.title(f"📖 Request: {book['title']}")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"### Book Details")
        st.write(f"**Author:** {book['author']}")
        st.write(f"**Category:** {book.get('category_name', 'Uncategorized')}")
        st.write(f"**Condition:** {book['book_condition']}")
        if book['description']:
            st.write(f"**Description:** {book['description']}")
    
    with col2:
        st.markdown(f"### Owner Details")
        st.write(f"**Name:** {book['owner_name']}")
        st.write(f"**Rating:** ⭐ {book.get('reputation_score', 0)}")
        st.write(f"**Contact:** {book['phone'] if book['phone'] else 'Not provided'}")
    
    with st.form("request_form"):
        meeting_location = st.text_input("Meeting Location (Optional)")
        notes = st.text_area("Additional Notes (Optional)")
        
        if st.form_submit_button("Send Request"):
            success, msg = create_exchange_request(
                book['book_id'],
                st.session_state.user_id,
                meeting_location,
                notes
            )
            if success:
                st.success(msg)
                del st.session_state.request_book
                st.session_state.page = "my_exchanges"
                st.rerun()
            else:
                st.error(msg)

def show_edit_book():
    """Edit book page"""
    if 'edit_book' not in st.session_state:
        st.session_state.page = "my_books"
        st.rerun()
        return
    
    book = st.session_state.edit_book
    
    st.title(f"✏️ Edit: {book['title']}")
    
    with st.form("edit_book_form"):
        title = st.text_input("Title", book['title'])
        author = st.text_input("Author", book['author'])
        condition = st.selectbox("Condition", ["New", "Like New", "Good", "Fair", "Poor"], 
                                 index=["New", "Like New", "Good", "Fair", "Poor"].index(book['book_condition']))
        description = st.text_area("Description", book['description'] if book['description'] else "")
        
        if st.form_submit_button("Update Book"):
            if update_book(book['book_id'], title, author, condition, description):
                st.success("Book updated!")
                del st.session_state.edit_book
                st.session_state.page = "my_books"
                st.rerun()
            else:
                st.error("Failed to update book")

def show_book_details():
    """Book details page"""
    if 'selected_book' not in st.session_state:
        st.session_state.page = "home"
        st.rerun()
        return
    
    book = get_book_by_id(st.session_state.selected_book)
    
    if not book:
        st.error("Book not found")
        st.session_state.page = "home"
        st.rerun()
        return
    
    st.title(f"📖 {book['title']}")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Book Information")
        st.write(f"**Author:** {book['author']}")
        st.write(f"**Category:** {book.get('category_name', 'Uncategorized')}")
        st.write(f"**Condition:** {book['book_condition']}")
        st.write(f"**Status:** {book['status']}")
        if book['description']:
            st.write(f"**Description:** {book['description']}")
    
    with col2:
        st.markdown("### Owner Information")
        st.write(f"**Name:** {book['owner_name']}")
        st.write(f"**Rating:** ⭐ {book.get('reputation_score', 0)}")
    
    if st.session_state.authenticated and book['owner_id'] != st.session_state.user_id and book['status'] == 'Available':
        if st.button("Request This Book", use_container_width=True):
            st.session_state.request_book = book['book_id']
            st.session_state.page = "request_book"
            st.rerun()
    
    if st.button("Back to Browse"):
        st.session_state.page = "browse"
        st.rerun()

# ==================== MAIN APPLICATION ====================

def main():
    """Main application"""
    
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'username' not in st.session_state:
        st.session_state.username = None
    if 'is_admin' not in st.session_state:
        st.session_state.is_admin = False
    if 'page' not in st.session_state:
        st.session_state.page = "home"
    
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/000000/books.png", width=80)
        st.title("📚 BookExchange")
        
        if st.session_state.authenticated:
            st.write(f"Welcome, **{st.session_state.username}**!")
            
            notifications = get_notifications(st.session_state.user_id)
            unread = len([n for n in notifications if not n['is_read']]) if notifications else 0
            
            menu_options = {
                "home": "🏠 Home",
                "browse": "🔍 Browse Books",
                "dashboard": "📊 Dashboard",
                "my_books": "📚 My Books",
                "add_book": "➕ Add Book",
                "my_exchanges": "🔄 My Exchanges",
                "notifications": f"🔔 Notifications ({unread})" if unread > 0 else "🔔 Notifications",
                "profile": "👤 Profile",
                "logout": "🚪 Logout"
            }
            
            if st.session_state.is_admin:
                menu_options["admin"] = "🔧 Admin Panel"
            
            for key, label in menu_options.items():
                if st.button(label, use_container_width=True, key=f"nav_{key}"):
                    if key == "logout":
                        st.session_state.authenticated = False
                        st.session_state.user_id = None
                        st.session_state.username = None
                        st.session_state.is_admin = False
                        st.session_state.page = "home"
                    else:
                        st.session_state.page = key
                    st.rerun()
        else:
            if st.button("🏠 Home", use_container_width=True):
                st.session_state.page = "home"
                st.rerun()
            if st.button("🔐 Login", use_container_width=True):
                st.session_state.page = "login"
                st.rerun()
            if st.button("📝 Register", use_container_width=True):
                st.session_state.page = "register"
                st.rerun()
    
    # Page routing
    pages = {
        "home": show_home,
        "login": show_login,
        "register": show_register,
        "dashboard": show_dashboard,
        "add_book": show_add_book,
        "my_books": show_my_books,
        "browse": show_browse_books,
        "my_exchanges": show_my_exchanges,
        "notifications": show_notifications,
        "profile": show_profile,
        "admin": show_admin_dashboard,
        "add_review": show_add_review,
        "request_book": show_request_book,
        "edit_book": show_edit_book,
        "book_details": show_book_details
    }
    
    current_page = st.session_state.page
    if current_page in pages:
        pages[current_page]()
    else:
        show_home()

if __name__ == "__main__":
    main()
