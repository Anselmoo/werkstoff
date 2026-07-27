from extract.run import extract

def apply():
    payload = extract()
    # BROKEN WIRE: extract emits "rows", this reads "records".
    return [r for r in payload["records"]]
