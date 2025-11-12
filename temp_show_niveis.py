from app import create_app
from app.models.reportAggregate import ReportAggregate

TEST_ID = '9d5ea14f-be9f-4b2d-abee-c38ae564addf'
SCOPE_TYPE = 'school'
SCOPE_ID = '53aacc0c-98ce-43ba-b5e2-f65fedc37e95'

app = create_app()
with app.app_context():
    agg = ReportAggregate.query.filter_by(test_id=TEST_ID, scope_type=SCOPE_TYPE, scope_id=SCOPE_ID).first()
    if not agg:
        print('Aggregate not found')
    else:
        import json
        print('student_count:', agg.student_count)
        payload = agg.payload or {}
        niveis = payload.get('niveis_aprendizagem')
        print('niveis_aprendizagem:')
        print(json.dumps(niveis, indent=2, ensure_ascii=False))
