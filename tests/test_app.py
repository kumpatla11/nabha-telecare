from datetime import datetime, timedelta

def login(client, email='patient@nabha-telecare.local', password='Patient@123', role='patient'):
    return client.post('/login', data={'identifier':email,'password':password,'role':role}, follow_redirects=True)

def test_home_and_doctors(client):
    assert client.get('/').status_code == 200
    assert b'Nabha TeleCare' in client.get('/').data
    assert client.get('/api/doctors').json['doctors']

def test_booking_and_double_booking(client):
    login(client)
    when=(datetime.now()+timedelta(days=2)).replace(second=0,microsecond=0).isoformat()
    payload={'doctor_id':1,'scheduled_for':when,'reason':'Persistent cough'}
    assert client.post('/api/appointments', json=payload).status_code == 201
    assert client.post('/api/appointments', json=payload).status_code == 409

def test_role_protection(client):
    assert client.get('/admin/dashboard').status_code in (302, 401)
    login(client, 'doctor@nabha-telecare.local', 'Doctor@123', 'doctor')
    assert client.get('/doctor/dashboard').status_code == 200

def test_pdf_route_requires_auth(client):
    assert client.get('/prescription/1/pdf').status_code in (302, 401, 404)
