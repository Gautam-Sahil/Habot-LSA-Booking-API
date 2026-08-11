import pytest
import datetime
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from api.models import Parent, LSA_Profile, Booking, Skill

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def setup_data():
    parent = Parent.objects.create(name="Jane Doe", email="jane@test.com")
    skill = Skill.objects.create(name="Autism Support")
    lsa = LSA_Profile.objects.create(name="John Smith", hourly_rate=50.00)
    lsa.skills.add(skill)
    return parent, lsa

@pytest.mark.django_db
def test_1_lsa_search_all(api_client, setup_data):
    url = reverse('lsa-search')
    response = api_client.get(url)
    assert response.status_code == 200
    assert len(response.data) == 1

@pytest.mark.django_db
def test_2_lsa_search_filter(api_client, setup_data):
    url = reverse('lsa-search')
    response = api_client.get(f"{url}?skill=Autism")
    assert response.status_code == 200
    assert response.data[0]['skills'][0]['name'] == "Autism Support"

@pytest.mark.django_db
def test_3_create_booking_success(api_client, setup_data):
    parent, lsa = setup_data
    url = reverse('booking-create')
    now = timezone.now()
    data = {
        "parent": parent.id,
        "lsa": lsa.id,
        "start_time": now + datetime.timedelta(days=1),
        "end_time": now + datetime.timedelta(days=1, hours=1)
    }
    response = api_client.post(url, data)
    assert response.status_code == 201
    assert response.data['status'] == 'PENDING'

@pytest.mark.django_db
def test_4_prevent_double_booking(api_client, setup_data):
    parent, lsa = setup_data
    now = timezone.now()
    start = now + datetime.timedelta(days=2)
    end = start + datetime.timedelta(hours=2)
    
    # Create the first booking
    Booking.objects.create(parent=parent, lsa=lsa, start_time=start, end_time=end)

    # Attempt to book overlapping time
    url = reverse('booking-create')
    data = {
        "parent": parent.id,
        "lsa": lsa.id,
        "start_time": start + datetime.timedelta(hours=1), # Overlaps by 1 hour
        "end_time": end + datetime.timedelta(hours=1)
    }
    response = api_client.post(url, data)
    assert response.status_code == 400
    assert "already booked" in str(response.data)

@pytest.mark.django_db
def test_5_payment_webhook(api_client, setup_data):
    parent, lsa = setup_data
    now = timezone.now()
    booking = Booking.objects.create(
        parent=parent, lsa=lsa, 
        start_time=now + datetime.timedelta(days=3), 
        end_time=now + datetime.timedelta(days=3, hours=1)
    )

    url = reverse('payment-webhook')
    data = {
        "booking_id": str(booking.id),
        "status": "SUCCESS",
        "transaction_id": "txn_12345"
    }
    response = api_client.post(url, data, format='json')
    assert response.status_code == 200
    
    # Verify the database actually updated the status
    booking.refresh_from_db()
    assert booking.status == 'CONFIRMED'