from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error
from werkzeug.security import check_password_hash, generate_password_hash
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt
from mysql.connector import IntegrityError

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
    
    #huvudroute som visar dokumentation av API:et, t.ex. vilka routes som finns och vad de gör.
@app.route('/', methods=['GET'])
def index():
    return '''<h1>Documentation</h1>
    <ul>
    <li><p>*GET /users - returnerar alla användare<p></li>
    <li><p>*GET /users/{id} - returnerar en specifik användare eller status 204 om användare saknas</p></li>
    <li><p>*GET /users/age?{age} - returnerar alla användare med en viss ålder</p></li>
    <li><p>POST /users - skapar en ny användare accepterar JSON obejkt på formatet. {"username":"" "name":"", "age": , "password":"", "email":""}. username är obligatoriskt ock ska vara unikt.</p></li>
    <li><p>*PUT /users/{id} - uppdaterar en användare. Accepterar JSON objekt på formatet, OBS! Username och email behöver vara unikt {"username":"" "name":"", "age":, "email":"", "password":""}</p></li>
    <li><p>POST /login - för inloggning. Returnerar en JWT som används som bearer token i anrop till routes skyddade med auth. Accepterar JSON objekt på formatet {"username": "", "password": ""}</p></li>
    <li><p>*GET /protected - en route som är skyddad med JWT auth   . Returnerar information om den inloggade användaren</p></li>
    <p> * = kräver JWT token i Authorization headern</p>
    </ul>'''

#visar alla users, kräver auth, returnerar 401 om ingen eller ogiltig token skickas med i headern
@app.route('/users', methods=['GET'])
@jwt_required()
def get_users(): 
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    sql = "SELECT age, email, id, name, username FROM users"
    cursor.execute(sql)
    users = cursor.fetchall()

    return jsonify(users)

#visar en user med id, kräver auth, returnerar 401 om ingen eller ogiltig token skickas med i headern, returnerar 404 om user saknas
@app.route('/users/<int:user_id>', methods=['GET'])
@jwt_required()
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

#visar alla users med en viss ålder, kräver auth, returnerar 401 om ingen eller ogiltig token skickas med i headern, returnerar 404 om user saknas  
@app.route('/users/age', methods=['GET'])
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

#skapar ny user, krväer auth, returnerar 401 om ingen eller ogiltig token skickas med i headern, returnerar 422 om data som skickas i body inte är valid, returnerar 409 om username eller email redan finns i databasen
# API-4: Validering av data och felhantering
@app.route('/users', methods=['POST'])
def create_user():
    data = request.get_json(silent=True)

    if is_valid_user_data(data):

        username = data.get('username')
        name = data.get('name')
        age = data.get('age')
        password = data.get('password')
        email = data.get('email')

        connection = get_db_connection()

        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500

        cursor = connection.cursor()

        sql = "INSERT INTO users (username, name, age, password, email) VALUES (%s, %s, %s, %s, %s)"

        try:
            cursor.execute(sql, (username, name, age, generate_password_hash(password), email))
            connection.commit()

        except IntegrityError as err:
            if err.errno == 1062:
                return jsonify({"error": "Username or email already in use"}), 409
            else:
                return jsonify({"error": "Database error"}), 500

        user_id = cursor.lastrowid

        user = {
            'username': username,
            'name': name,
            'age': age,
            'id': user_id,
            'email': email
        }

        return jsonify({"message": "User created", "user": user}), 201

    else:
        return jsonify({"error": "Invalid user data"}), 422

# En hjälpfunktion för att validera användardata
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

#update user by id, kräver auth.
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

#ger en bearer token som används för att autentisera routes som kräver auth, t.ex. GET /users
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

# En route som är skyddad med JWT auth. Returnerar information om den inloggade användaren
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