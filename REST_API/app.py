from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error
from werkzeug.security import check_password_hash, generate_password_hash
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # TODO: Ändra detta till en slumpmässig hemlig nyckel

# Konfigurera JWT secret key. I en riktig applikation bör du använda en mer komplex och säker nyckel, och den bör inte hårdkodas i koden.
app.config['JWT_SECRET_KEY'] = 'your_jwt_secret_key'

# skapa JWTManager instans och koppla den till Flask appen
jwt = JWTManager(app)

# Databaskonfiguration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',  # Ändra detta till ditt MySQL-användarnamn
    'password': '',  # Ändra detta till ditt MySQL-lösenord
    'database': 'api'  # TODO: Ändra detta till ditt databasnamn
}

def get_db_connection():
    """Skapa och returnera en databasanslutning"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Fel vid anslutning till MySQL: {e}")
        return None
    
@app.route('/', methods=['GET'])
def index():
    return '''<h1>Documentation</h1>
    <ul><li>GET /users</li></ul>'''

# @app.route('/users', methods=['GET'])
# def get_users(): 
#     users = [
#         {'id': 1, 'name': 'Alice'},
#         {'id': 2, 'name': 'Bob'},
#         {'id': 3, 'name': 'Charlie'}
#     ]
#     return jsonify(users)

@app.route('/users', methods=['GET'])
@jwt_required()
def get_users(): 
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    sql = "SELECT age, email, id, name, username FROM users"
    cursor.execute(sql)
    users = cursor.fetchall()

    return jsonify(users)

@app.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """Get all users"""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    # hämta ENDAST user med id
    sql = "SELECT * FROM users WHERE id = %s"
    cursor.execute(sql, (user_id,))
    user = cursor.fetchone()

    user.pop('password', None) # ta bort password innan vi skickar tillbaka user info
   
    if not user: # saknades personen i databasen?
        return jsonify({'error': 'User not found'}), 404
    else:
        return jsonify(user)


@app.route('/users/age?<int:user_age>', methods=['GET'])
@jwt_required()
def get_user_age():
    user_age = request.args.get('age')
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    # hämta ENDAST user med id
    sql = "SELECT * FROM users WHERE age = %s"
    cursor.execute(sql, (user_age,))
    user = cursor.fetchall()
   
    if not user: # saknades personen i databasen?
        return jsonify({'error': 'User not found'}), 404
    else:
        return jsonify(user)

# API-4: Validering av data och felhantering
@app.route('/users/create', methods=['POST'])
@jwt_required()
def create_user():
    data = request.get_json(silent=True)

    if is_valid_user_data(data):
        # Logik för databas här...
        data = request.get_json()  # Hämta data från requesten.
        username = data.get('username')
        name = data.get('name')
        age = data.get('age')
        password = data.get('password')
        email = data.get('email')

        connection = get_db_connection()

        if not connection:  # ← Kontrollera om anslutningen misslyckades
            return jsonify({'error': 'Database connection failed'}), 500

        cursor = connection.cursor()
        sql = "INSERT INTO users (username, name, age, password, email) VALUES (%s, %s, %s, %s, %s)"
        cursor.execute(sql, (username, name, age, generate_password_hash(password), email))
            
        connection.commit() # commit() gör klart skrivningen till databasen
        user_id = cursor.lastrowid # cursor.lastrowid innehåller id på raden som skapades i DB

        user = {
        'username': username,
        'name': name,
        'age': age,
        'password': password,
        'id': user_id,
        'email': email
        }

        return jsonify({"message": "User created", "user": user}), 201
    else:
        # Returnera ett JSON-objekt med felmeddelandet och statuskod 422
        return jsonify({"error": "Invalid user data"}), 422

def is_valid_user_data(data):
    if "username" in data and "age" in data and "name" in data:
        if not isinstance(data["username"], str):
            return False
        if not isinstance(data["age"], int):
            return False
        if not isinstance(data["name"], str):
            return False
        if not isinstance(data["email"], str):
            return False
        return True
    return False


@app.route('/users/<int:user_id>', methods=['PUT'])
@jwt_required()
def update_user(user_id):
    # 1. Hämta data från body (req.body)
    data = request.get_json(silent=True)

    connection = get_db_connection()
   
    #lägg till verifiering av data här vid behov, skicka t.ex. status 400
    username = data.get('username')
    password = data.get('password')
    name = data.get('name')
    age = data.get('age')
    email = data.get('email')
    id = data.get('user_id')
    # skapa databaskoppling (kod bortklippt) och använd UPDATE för att uppdatera databasen
    sql = """UPDATE users SET username = %s, password = %s, name = %s, age = %s, email = %s WHERE id = %s"""
   
    # 3. Kör frågan med en tupel av värden
    cursor = connection.cursor()
    cursor.execute(sql, (username, generate_password_hash(password), name, age, email, user_id))
   
    connection.commit()
   
    # Kontrollera om någon rad faktiskt uppdaterades
    if cursor.rowcount == 0:
        return jsonify({"error": "Användaren hittades inte"}), 404

    connection.close()

    return jsonify({"message": "Användare uppdaterad", "id": user_id}), 200


@app.route('/login', methods=['POST'])
def login():
    """User login"""
    data = request.get_json()
    user_name = data.get('username')
    password = data.get('password')
   
    connection = get_db_connection()
       
    cursor = connection.cursor(dictionary=True)
    sql = "SELECT * FROM users WHERE username = %s"
    cursor.execute(sql, (user_name,))
    user = cursor.fetchone()

    if not user or not check_password_hash(user['password'], password):
        return jsonify({'error': 'Invalid username or password'}), 401
    if 'password' in user: # ta bort password innan vi skickar tillbaka user info
        del user['password']

    access_token = create_access_token(identity=user_name)
    # Skicka tillbaka JWT
    return jsonify(access_token=access_token), 200

    return jsonify({
        'message': 'Login successful',
        'user': user
    })

@app.route('/protected', methods=['GET'])
@jwt_required()
def protected():
    # Hämta identity från JWT, i det här fallet användarnamnet som vi satte som identity när vi skapade token
    current_user = get_jwt_identity()
    # Det här är för att visa att vi kan hämta hela JWT payloaden
    print(get_jwt())
    return jsonify(logged_in_as=current_user), 200


if __name__ == '__main__':
    app.run(debug=True)