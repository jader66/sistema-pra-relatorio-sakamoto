def post_worker_init(worker):
    """Initialize the database once per Gunicorn worker."""
    from app import init_db

    init_db()
