# products/paystack.py
import requests
from django.conf import settings

PAYSTACK_INIT_URL = 'https://api.paystack.co/transaction/initialize'

def initiate_paystack_payment(email, amount, reference, callback_url):
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "email": email,
        "amount": int(amount * 100),  # Paystack expects amount in kobo
        "reference": reference,
        "callback_url": callback_url,
    }

    response = requests.post(PAYSTACK_INIT_URL, json=data, headers=headers)
    response_data = response.json()

    if response.status_code == 200 and response_data['status']:
        return response_data['data']['authorization_url']  # Paystack payment link
    else:
        return None
