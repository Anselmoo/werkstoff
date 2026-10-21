def consume(broker, handler):
    msg = broker.get()
    handler(msg)
    broker.ack(msg)
