SQL = 'SELECT * FROM orders WHERE customer_id = %s ORDER BY created_at DESC'


def by_customer(rows, cid):
    return sorted((r for r in rows if r['customer_id'] == cid),
                  key=lambda r: r['created_at'], reverse=True)
