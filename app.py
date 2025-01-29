from flask import Flask, jsonify, request
import mysql.connector
from config import DB_CONFIG
from datetime import datetime

app = Flask(__name__)

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

@app.route('/session', methods=['POST'])
def add_session():
    data = request.get_json()
    
    trainer_id = data.get('trainer_id')
    member_id = data.get('member_id')
    session_date = data.get('session_date')
    start_time = data.get('start_time')
    end_time = data.get('end_time')
    
    if not all([trainer_id, member_id, session_date, start_time, end_time]):
        return jsonify({"error": "All fields are required"}), 400
    try:
        start_time_dt = datetime.strptime(start_time, "%H:%M:%S")
        end_time_dt = datetime.strptime(end_time, "%H:%M:%S")
        
        if end_time_dt <= start_time_dt:
            return jsonify({"error": "End time must be after start time"}), 400
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
                       SELECT COUNT(*) AS overlap_count FROM sessions
                       WHERE trainer_id = %s AND session_date = %s
                       AND ((start_time<=%s AND end_time>%s) OR (start_time<%s AND end_time>=%s))
                       """, (trainer_id, session_date, start_time, start_time, end_time, end_time))
        overlap = cursor.fetchone()['overlap_count']
        
        if overlap>0:
            return jsonify({"error": "Trainer has an overlapping session"}), 400

        cursor.execute("""
    SELECT SUM(TIMESTAMPDIFF(MINUTE, start_time, end_time)) AS total_minutes
    FROM sessions
    WHERE trainer_id = %s AND session_date = %s
""", (trainer_id, session_date)) 

        total_minutes = cursor.fetchone()['total_minutes'] or 0
        
        cursor.execute("SELECT working_hours FROM trainers WHERE id = %s", (trainer_id,))
        trainer_working_hours = cursor.fetchone()
        
        if not trainer_working_hours:
            return jsonify({"error": "Trainer not found"}), 400
        
        max_working_minutes = trainer_working_hours['working_hours']*60
        session_duration = (end_time_dt - start_time_dt).seconds // 60
        
        if total_minutes + session_duration>max_working_minutes:
            return jsonify({"error": "Trainer exceeds daiy working hours"}), 400
        
        cursor.execute("""
    INSERT INTO sessions (trainer_id, member_id, session_date, start_time, end_time)
    VALUES (%s, %s, %s, %s, %s)
""", (trainer_id, member_id, session_date, start_time, end_time))  

        conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({"message": "Training session added successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/member', methods=['POST'])
def register_member():
    data = request.get_json()

    name = data.get('name')
    email = data.get('email')
    phone = data.get('phone')
    age = data.get('age')
    gender = data.get('gender')

    if not all([name, email, phone, age, gender]):
        return jsonify({"error": "All fields are required"}), 400
    
    if gender not in ["Male", "Female", "Other"]:
        return jsonify({"error": "Invalid gender. Choose Male, Female, or Other."}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 🔹 Check if email or phone already exists
        cursor.execute("SELECT * FROM members WHERE email = %s OR phone = %s", (email, phone))
        existing_member = cursor.fetchone()
        if existing_member:
            return jsonify({"error": "Member with this email or phone already exists"}), 400

        # 🔹 Insert new member
        cursor.execute("""
            INSERT INTO members (name, email, phone, age, gender)
            VALUES (%s, %s, %s, %s, %s)
        """, (name, email, phone, age, gender))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({"message": "Member registered successfully"}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/trainer/<int:trainer_id>', methods=['GET'])
def get_trainer(trainer_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM trainers WHERE id = %s", (trainer_id,))
    trainer = cursor.fetchone()

    cursor.close()
    connection.close()

    if trainer:
        return jsonify(trainer)
    else:
        return jsonify({"message": "Trainer not found"}), 404

if __name__ == '__main__':
    app.run(debug=True)
