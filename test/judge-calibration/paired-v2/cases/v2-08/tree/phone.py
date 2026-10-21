CODES = {'CH': '41', 'DE': '49', 'FR': '33'}


def to_e164(number, country):
    digits = ''.join(ch for ch in number if ch.isdigit())
    return '+' + CODES[country] + digits
