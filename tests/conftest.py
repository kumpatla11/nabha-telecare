import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from app import app, db

@pytest.fixture
def client(tmp_path):
    app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI=f'sqlite:///{tmp_path}/test.db', SECRET_KEY='test')
    with app.app_context():
        db.drop_all(); db.create_all()
        from app import seed_data
        seed_data()
    with app.test_client() as client:
        yield client
    with app.app_context(): db.drop_all()
