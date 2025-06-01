from flask import Blueprint, request, jsonify
from app.models.studentClass import Class
from app import db
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import logging

bp = Blueprint('classes', __name__, url_prefix="/classes")

@bp.errorhandler(SQLAlchemyError)
def handle_db_error(error):
    db.session.rollback()
    logging.error(f"Database error: {str(error)}")
    return jsonify({"error": "Database error occurred", "details": str(error)}), 500

@bp.errorhandler(IntegrityError)
def handle_integrity_error(error):
    db.session.rollback()
    logging.error(f"Integrity error: {str(error)}")
    return jsonify({"error": "Data integrity error", "details": str(error)}), 400

@bp.errorhandler(Exception)
def handle_generic_error(error):
    logging.error(f"Unexpected error: {str(error)}", exc_info=True)
    return jsonify({"error": "An unexpected error occurred", "details": str(error)}), 500

@bp.route('/school/<string:school_id>', methods=['GET'])
@jwt_required()
def get_classes_by_school(school_id):
    try:
        classes = Class.query.filter_by(school_id=school_id).all()
        
        if not classes:
            return jsonify([]), 200  # Return empty list if no classes found

        return jsonify([{
            "id": c.id,
            "name": c.name,
            "school_id": c.school_id,
            "grade_id": str(c.grade_id) if c.grade_id else None,
            "students_count": len(c.students),
            "subjects_count": len(c.class_subjects),
            "tests_count": len(c.class_tests)
        } for c in classes]), 200

    except Exception as e:
        logging.error(f"Error getting classes by school: {str(e)}", exc_info=True)
        return jsonify({"error": "Error getting classes by school", "details": str(e)}), 500

@bp.route('', methods=['GET'])
@jwt_required()
def get_classes():
    try:
        classes = Class.query.all()
        return jsonify([{
            "id": c.id,
            "name": c.name,
            "school_id": c.school_id,
            "grade_id": str(c.grade_id) if c.grade_id else None
        } for c in classes]), 200
    except Exception as e:
        logging.error(f"Error getting classes: {str(e)}", exc_info=True)
        return jsonify({"error": "Error getting classes", "details": str(e)}), 500

@bp.route('/<string:class_id>', methods=['GET'])
@jwt_required()
def get_class(class_id):
    try:
        class_obj = Class.query.get(class_id)
        if not class_obj:
            return jsonify({"error": "Class not found"}), 404

        return jsonify({
            "id": class_obj.id,
            "name": class_obj.name,
            "school_id": class_obj.school_id,
            "grade_id": str(class_obj.grade_id) if class_obj.grade_id else None,
            "students": [{"id": s.id, "name": s.name} for s in class_obj.students],
            "class_subjects": [{"id": cs.id} for cs in class_obj.class_subjects],
            "class_tests": [{"id": ct.id} for ct in class_obj.class_tests]
        }), 200
    except Exception as e:
        logging.error(f"Error getting class: {str(e)}", exc_info=True)
        return jsonify({"error": "Error getting class", "details": str(e)}), 500

@bp.route('/<string:class_id>', methods=['PUT'])
@jwt_required()
def update_class(class_id):
    try:
        class_obj = Class.query.get(class_id)
        if not class_obj:
            return jsonify({"error": "Class not found"}), 404

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        if "name" in data:
            class_obj.name = data["name"]
        if "school_id" in data:
            class_obj.school_id = data["school_id"]
        if "grade_id" in data:
            class_obj.grade_id = data["grade_id"]

        db.session.commit()
        return jsonify({"message": "Class updated successfully"}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating class: {str(e)}", exc_info=True)
        return jsonify({"error": "Error updating class", "details": str(e)}), 500

@bp.route('/<string:class_id>', methods=['DELETE'])
@jwt_required()
def delete_class(class_id):
    try:
        class_obj = Class.query.get(class_id)
        if not class_obj:
            return jsonify({"error": "Class not found"}), 404

        db.session.delete(class_obj)
        db.session.commit()
        return jsonify({"message": "Class deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting class: {str(e)}", exc_info=True)
        return jsonify({"error": "Error deleting class", "details": str(e)}), 500

@bp.route('', methods=['POST'])
@jwt_required()
def create_class():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Validate required fields
        required_fields = ["name", "school_id"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        # Create new class
        new_class = Class(
            name=data["name"],
            school_id=data["school_id"],
            grade_id=data.get("grade_id")  # Optional field
        )

        db.session.add(new_class)
        db.session.commit()

        return jsonify({
            "message": "Class created successfully",
            "class": {
                "id": new_class.id,
                "name": new_class.name,
                "school_id": new_class.school_id,
                "grade_id": str(new_class.grade_id) if new_class.grade_id else None
            }
        }), 201

    except IntegrityError as e:
        db.session.rollback()
        logging.error(f"Integrity error while creating class: {str(e)}")
        return jsonify({"error": "Data integrity error", "details": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error creating class: {str(e)}", exc_info=True)
        return jsonify({"error": "Error creating class", "details": str(e)}), 500 