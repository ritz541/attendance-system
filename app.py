from flask import Flask, render_template, request, jsonify, send_file
from datetime import datetime, timedelta, timezone
import random
import string
import pandas as pd
from pymongo import MongoClient
import os
import io
from bson import ObjectId
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# MongoDB setup using environment variables
try:
    client = MongoClient(os.getenv('MONGO_URI'), serverSelectionTimeoutMS=2000)
    # Verify connection
    client.server_info()
    db = client[os.getenv('DATABASE_NAME')]
    attendance_collection = db[os.getenv('ATTENDANCE_COLLECTION')]
    word_collection = db[os.getenv('WORD_COLLECTION')]
    permanent_records = db[os.getenv('PERMANENT_RECORDS_COLLECTION')]
except Exception as e:
    print(f"MongoDB Connection Error: {e}")

def get_current_time():
    """Get current time in UTC with timezone information"""
    return datetime.now(timezone.utc)

def format_time_for_humans(timestamp):
    # Convert UTC to local time
    local_time = timestamp.astimezone()
    return {
        'date': local_time.strftime("%d %B %Y"),
        'time': local_time.strftime("%I:%M %p")
    }

def is_word_valid(word_doc):
    if not word_doc:
        return False
        
    current_time = get_current_time()
    end_time = word_doc['end_time']
    
    # Convert to UTC if not already
    if isinstance(end_time, datetime) and end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)
        
    return current_time <= end_time

def generate_random_word(length=8):
    # Characters to use for random word generation
    lowercase = string.ascii_lowercase
    numbers = string.digits
    special_chars = '$#@&'
    all_chars = lowercase + numbers + special_chars
    
    # Ensure at least one of each type
    word = (
        random.choice(lowercase) +
        random.choice(numbers) +
        random.choice(special_chars) +
        ''.join(random.choice(all_chars) for _ in range(length - 3))
    )
    
    # Shuffle the word
    word_list = list(word)
    random.shuffle(word_list)
    return ''.join(word_list)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_word', methods=['POST'])
def generate_word():
    try:
        subject_name = request.json.get('subject_name')
        if not subject_name:
            return jsonify({'error': 'Subject name is required'}), 400

        current_time = get_current_time()
        end_time = current_time + timedelta(minutes=1)
        
        # Generate new word and store with time window
        word = generate_random_word()
        word_doc = {
            'word': word,
            'subject_name': subject_name,
            'start_time': current_time,
            'end_time': end_time,
            'date': current_time.strftime('%Y-%m-%d'),
            'day': current_time.strftime('%A')
        }
        
        word_collection.insert_one(word_doc)
        
        return jsonify({
            'word': word,
            'subject_name': subject_name,
            'created_at': current_time.isoformat(),
            'expiry_time': end_time.isoformat()
        })
    except Exception as e:
        print(f"Error generating word: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/submit_attendance', methods=['POST'])
def submit_attendance():
    try:
        data = request.get_json()
        roll_number = data.get('roll_number')
        word = data.get('word')

        if not roll_number or not word:
            return jsonify({'status': 'error', 'message': 'Roll number and word are required'}), 400

        # Check if word exists and is valid
        word_doc = word_collection.find_one({'word': word})
        if not word_doc:
            return jsonify({'status': 'error', 'message': 'Invalid word'}), 400

        if not is_word_valid(word_doc):
            return jsonify({'status': 'error', 'message': 'Word has expired'}), 400

        # Check if attendance already marked
        existing_attendance = permanent_records.find_one({
            'roll_number': roll_number,
            'word': word
        })
        if existing_attendance:
            return jsonify({'status': 'error', 'message': 'Attendance already marked'}), 400

        # Mark attendance
        current_time = get_current_time()
        human_time = format_time_for_humans(current_time)
        attendance_record = {
            'roll_number': roll_number,
            'word': word,
            'subject_name': word_doc['subject_name'],
            'timestamp': current_time,
            'date': human_time['date'],
            'time': human_time['time']
        }
        
        permanent_records.insert_one(attendance_record)
        return jsonify({'status': 'success', 'message': 'Attendance marked successfully'}), 200

    except Exception as e:
        print(f"Error submitting attendance: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/check_word_status', methods=['GET'])
def check_word_status():
    try:
        word = request.args.get('word')
        if not word:
            return jsonify({'valid': False})
            
        # Find word document
        word_doc = word_collection.find_one({'word': word})
        
        if not word_doc or not is_word_valid(word_doc):
            return jsonify({'valid': False})
            
        return jsonify({
            'valid': True,
            'subject_name': word_doc['subject_name'],
            'expiry_time': word_doc['end_time'].isoformat()
        })
    except Exception as e:
        print(f"Error checking word status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/download_attendance', methods=['GET'])
def download_attendance():
    try:
        format_type = request.args.get('format', 'csv')
        filename = request.args.get('filename', 'attendance')
        subject = request.args.get('subject')
        
        if not subject:
            return jsonify({'status': 'error', 'message': 'Subject name is required'}), 400
            
        # Get today's date in UTC
        today = get_current_time().strftime('%Y-%m-%d')
            
        # Get attendance records for this subject from today
        records = list(permanent_records.find({
            'subject_name': subject,
            'timestamp': {'$gte': datetime.strptime(today, '%Y-%m-%d').replace(tzinfo=timezone.utc)}
        }, {'_id': 0, 'word': 0, 'timestamp': 0}))  # Exclude unnecessary fields
        
        if not records:
            return jsonify({'status': 'error', 'message': 'No attendance records found for today'}), 404
        
        df = pd.DataFrame(records)
        
        # Reorder columns
        columns_order = ['roll_number', 'subject_name', 'date', 'time']
        df = df[columns_order]
        
        # Rename columns for better readability
        df.columns = ['Roll No', 'Subject', 'Date', 'Time']
        
        buffer = io.BytesIO()
        
        if format_type == 'excel':
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Attendance')
                worksheet = writer.sheets['Attendance']
                for column in worksheet.columns:
                    max_length = 0
                    column = [cell for cell in column]
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(cell.value)
                        except:
                            pass
                    adjusted_width = (max_length + 2)
                    worksheet.column_dimensions[column[0].column_letter].width = adjusted_width
            
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            file_ext = 'xlsx'
        else:
            df.to_csv(buffer, index=False)
            mimetype = 'text/csv'
            file_ext = 'csv'
        
        buffer.seek(0)
        return send_file(
            buffer,
            mimetype=mimetype,
            as_attachment=True,
            download_name=f'{filename}.{file_ext}'
        )
    except Exception as e:
        print(f"Error downloading attendance: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/download')
def download_page():
    return render_template('download.html')

if __name__ == '__main__':
    app.run(debug=True)
