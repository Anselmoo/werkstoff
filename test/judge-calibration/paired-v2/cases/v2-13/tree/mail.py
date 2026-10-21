from email.message import EmailMessage


def compose_reset(to, token):
    # TODO: confirm the relay's SPF record covers this sender before launch
    msg = EmailMessage()
    msg['From'] = 'no-reply@example.com'
    msg['To'] = to
    msg['Subject'] = 'Reset your password'
    msg.set_content(f'Reset it here: https://example.com/reset?t={token}\n')
    return msg
