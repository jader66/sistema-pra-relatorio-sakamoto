def post_worker_init(worker):
    from app import app, init_db

    # app.py currently registers init_db() with before_request. Remove that
    # hook so PostgreSQL schema changes are not attempted on every request.
    funcs = app.before_request_funcs.get(None, [])
    app.before_request_funcs[None] = [f for f in funcs if f.__name__ != 'startup']

    # Run schema creation/migration once after the worker has loaded the app.
    init_db()
