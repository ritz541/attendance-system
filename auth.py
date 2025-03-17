from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask import request, jsonify, session, redirect, url_for

def teacher_required(f):
    """Decorator to protect routes that require teacher authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        teacher_email = request.cookies.get('teacher_email')
        if not teacher_email:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated