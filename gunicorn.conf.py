def post_worker_init(worker):
    """Inicializa banco e recursos extras uma vez por worker."""
    from app import init_db, app
    from iso9001 import register_iso9001

    init_db()
    register_iso9001(app)
