from flask import Blueprint, jsonify
from app.models.subject import Subject
from app import db
import logging

bp = Blueprint('subjects', __name__, url_prefix="/subjects")

@bp.route('', methods=['GET'])
def list_subjects():
    try:
        subjects = Subject.query.all()
        
        return jsonify([{
            'id': subject.id,
            'name': subject.name
        } for subject in subjects]), 200

    except Exception as e:
        logging.error(f"Error listing subjects: {str(e)}", exc_info=True)
        return jsonify({"error": "Error listing subjects", "details": str(e)}), 500 