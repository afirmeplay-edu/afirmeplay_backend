from flask import Blueprint, jsonify
from app.models.subject import Subject
from app.models.test import Test
from app.models.classTest import ClassTest
from app.models.studentClass import Class
from app.models.answerSheetGabarito import AnswerSheetGabarito
from app import db
import logging
import re
from typing import Optional

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


@bp.route('/by-school/<string:school_id>', methods=['GET'])
def list_subjects_by_school(school_id):
    try:
        school_id = (school_id or "").strip()
        if not school_id:
            return jsonify([]), 200

        subjects_by_key = {}

        def add_subject(subject_id: Optional[str], subject_name: Optional[str]):
            name = (subject_name or "").strip()
            if not name:
                return
            key = name.lower()
            if key in subjects_by_key:
                return
            sid = (subject_id or "").strip()
            if not sid:
                slug = re.sub(r"[^a-z0-9]+", "-", key).strip("-")
                sid = f"name:{slug or 'subject'}"
            subjects_by_key[key] = {"id": sid, "name": name}

        school_subjects = (
            db.session.query(Subject.id, Subject.name)
            .join(Test, Test.subject == Subject.id)
            .join(ClassTest, ClassTest.test_id == Test.id)
            .join(Class, Class.id == ClassTest.class_id)
            .filter(Class.school_id == school_id)
            .distinct()
            .all()
        )
        for subject_id, subject_name in school_subjects:
            add_subject(str(subject_id) if subject_id else None, subject_name)

        class_ids = [
            str(row[0])
            for row in db.session.query(Class.id).filter(Class.school_id == school_id).all()
            if row and row[0]
        ]
        gabaritos_query = AnswerSheetGabarito.query.filter(
            (AnswerSheetGabarito.school_id == school_id)
            | (AnswerSheetGabarito.class_id.in_(class_ids) if class_ids else False)
        )
        for gabarito in gabaritos_query.all():
            blocks = (((gabarito.blocks_config or {}).get("topology") or {}).get("blocks")) or []
            for block in blocks:
                block_subject_id = str(block.get("subject_id") or "").strip() or None
                block_subject_name = (block.get("subject_name") or "").strip() or None
                if not block_subject_name and block_subject_id:
                    subject = Subject.query.get(block_subject_id)
                    block_subject_name = (subject.name if subject else "") or None
                add_subject(block_subject_id, block_subject_name)

        ordered = sorted(subjects_by_key.values(), key=lambda s: s["name"].lower())
        return jsonify(ordered), 200
    except Exception as e:
        logging.error(f"Error listing subjects by school: {str(e)}", exc_info=True)
        return jsonify({"error": "Error listing subjects by school", "details": str(e)}), 500