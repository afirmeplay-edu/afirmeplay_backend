from app import create_app
from app.models.reportAggregate import ReportAggregate
import json

TEST_ID = '9d5ea14f-be9f-4b2d-abee-c38ae564addf'
CITY_ID = 'f252f786-cac5-439f-b0b1-8e3e558f2636'

app = create_app()
with app.app_context():
    agg = ReportAggregate.query.filter_by(test_id=TEST_ID, scope_type='city', scope_id=CITY_ID).first()
    if not agg:
        print('Aggregate not found')
    else:
        print('student_count:', agg.student_count)
        payload = agg.payload or {}
        total_alunos = payload.get('total_alunos')
        niveis = payload.get('niveis_aprendizagem')
        print('total_alunos:', json.dumps(total_alunos, indent=2, ensure_ascii=False))
        print('niveis_aprendizagem:', json.dumps(niveis, indent=2, ensure_ascii=False))
