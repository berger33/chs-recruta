from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status':'ok'}

def test_docs_available():
    assert client.get('/docs').status_code == 200

def test_auth_required():
    assert client.get('/api/candidates').status_code == 401
