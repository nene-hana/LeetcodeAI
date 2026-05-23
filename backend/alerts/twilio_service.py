import os

from twilio.rest import Client

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_number = os.getenv("TWILIO_PHONE_NUMBER")

client = Client(account_sid, auth_token)


def make_call(to_number: str, audio_url: str):
    twilio_number = os.getenv("TWILIO_PHONE_NUMBER", "")
    # Remove 'whatsapp:' prefix if it exists when making a voice call
    from_number = twilio_number.replace("whatsapp:", "") if twilio_number else twilio_number
    
    call = client.calls.create(
        to=to_number,
        from_=from_number,
        twiml=f"<Response><Play>{audio_url}</Play></Response>",
    )

    return call.sid

def send_whatsapp_message(to_number: str, body: str):
    twilio_number = os.getenv("TWILIO_PHONE_NUMBER", "")
    formatted_to = to_number if to_number.startswith("whatsapp:") else f"whatsapp:{to_number}"
    formatted_from = twilio_number if twilio_number.startswith("whatsapp:") else f"whatsapp:{twilio_number}"
    
    message = client.messages.create(
        from_=formatted_from,
        body=body,
        to=formatted_to
    )
    return message.sid
