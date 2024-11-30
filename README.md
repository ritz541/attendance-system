# Attendance System 2.0

A simple and secure attendance tracking system for educational institutions. The system allows teachers to generate random words that students must enter within a time limit to mark their attendance.

## Features

- Teacher can generate random secure words
- 1-minute time limit for attendance submission
- Students enter roll number and generated word
- Export attendance data in CSV or Excel format
- No login required
- Only tracks present students

## Technical Requirements

- Python 3.8+
- MongoDB
- Flask
- Modern web browser

## Installation

1. Clone the repository
2. Install MongoDB and ensure it's running on localhost:27017
3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

## Running the Application

1. Start MongoDB service
2. Run the Flask application:
```bash
python app.py
```
3. Open your browser and navigate to `http://localhost:5000`

## Usage

### Teacher Section
1. Click on the "Teacher" tab
2. Click "Generate New Word" button
3. Share the generated word with students
4. After students submit their attendance, download the data in CSV or Excel format

### Student Section
1. Click on the "Student" tab
2. Enter your roll number
3. Enter the word shared by the teacher
4. Submit within 1 minute

## Data Format
The exported attendance data includes:
- Roll Number
- Word
- Timestamp
