import pymysql.cursors
from ..mod_check import app


@app.task
def check(host, port, username, password, db):
    result = None
    connection = None

    try:
        connection = pymysql.connect(host=host,
                                     port=port,
                                     user=username,
                                     password=password,
                                     db=db,
                                     charset='utf8mb4',
                                     autocommit=True,
                                     cursorclass=pymysql.cursors.DictCursor)

        with connection.cursor() as cursor:
            cursor.execute('SELECT @@version AS version')
            res = cursor.fetchone()

            if isinstance(res, dict):
                result = res.get('version', None)
    except pymysql.Error:
        result = False
    finally:
        if connection is not None:
            connection.close()

    return result
