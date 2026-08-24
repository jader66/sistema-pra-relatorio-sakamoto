import os
import sqlite3
import csv
from datetime import datetime
from functools import wraps
from flask import Flask, request, redirect, url_for, session, render_template_string, send_file, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'sistema.db')
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'troque-esta-chave-no-render')
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
ROLES = {'administrador', 'chefe', 'funcionario'}


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def init_db():
    conn = db()
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'funcionario',
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor_id INTEGER,
        action TEXT NOT NULL,
        target_username TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(actor_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT NOT NULL,
        description TEXT,
        photo TEXT,
        urgency TEXT NOT NULL DEFAULT 'normal',
        status TEXT NOT NULL DEFAULT 'aguardando',
        created_at TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT,
        created_by INTEGER,
        assigned_to INTEGER,
        notes TEXT
    );
    CREATE TABLE IF NOT EXISTS autosaves (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        content TEXT,
        saved_at TEXT NOT NULL
    );
    ''')
    # Migração para instalações antigas.
    cols = {r['name'] for r in conn.execute('PRAGMA table_info(users)').fetchall()}
    if 'active' not in cols:
        conn.execute('ALTER TABLE users ADD COLUMN active INTEGER NOT NULL DEFAULT 1')
    if 'created_at' not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN created_at TEXT NOT NULL DEFAULT ''")
    conn.execute("UPDATE users SET created_at=? WHERE created_at='' OR created_at IS NULL", (now(),))
    # Converte os perfis antigos para os novos nomes.
    conn.execute("UPDATE users SET role='chefe' WHERE role='boss'")
    conn.execute("UPDATE users SET role='funcionario' WHERE role='employee'")
    if conn.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0:
        conn.execute('INSERT INTO users(name,username,password_hash,role,active,created_at) VALUES(?,?,?,?,?,?)',
                     ('Administrador', 'admin', generate_password_hash('123456'), 'administrador', 1, now()))
        conn.execute('INSERT INTO users(name,username,password_hash,role,active,created_at) VALUES(?,?,?,?,?,?)',
                     ('Chefe', 'chefe', generate_password_hash('123456'), 'chefe', 1, now()))
        conn.execute('INSERT INTO users(name,username,password_hash,role,active,created_at) VALUES(?,?,?,?,?,?)',
                     ('Funcionário 1', 'funcionario1', generate_password_hash('123456'), 'funcionario', 1, now()))
    conn.commit()
    conn.close()


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapper


def manager_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if session.get('role') not in ('administrador', 'chefe'):
            flash('Somente administrador ou chefe pode acessar esta área.')
            return redirect(url_for('dashboard'))
        return fn(*args, **kwargs)
    return wrapper


def audit(action, target=None):
    conn = db()
    conn.execute('INSERT INTO audit_logs(actor_id,action,target_username,created_at) VALUES(?,?,?,?)',
                 (session.get('user_id'), action, target, now()))
    conn.commit()
    conn.close()


def priority(created_at, manual):
    try:
        age_days = (datetime.now() - datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')).days
    except ValueError:
        age_days = 0
    base = {'normal': 1, 'pouca urgência': 2, 'urgente': 3}.get(manual, 1)
    score = min(3, base + (1 if age_days >= 3 else 0) + (1 if age_days >= 7 else 0))
    return {1: 'normal', 2: 'pouca urgência', 3: 'urgente'}[score]


@app.route('/')
def index():
    return redirect(url_for('dashboard')) if 'user_id' in session else redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        conn = db()
        user = conn.execute('SELECT * FROM users WHERE username=? AND active=1', (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password_hash'], password):
            session.update(user_id=user['id'], username=user['username'], name=user['name'], role=user['role'])
            audit('LOGIN', username)
            return redirect(url_for('dashboard'))
        flash('Usuário ou senha inválidos.')
    return render_template_string(LOGIN_HTML)


@app.route('/logout')
def logout():
    if session.get('user_id'):
        audit('LOGOUT', session.get('username'))
    session.clear()
    return redirect(url_for('login'))


@app.route('/usuarios', methods=['GET', 'POST'])
@login_required
@manager_required
def users():
    conn = db()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'funcionario')
        if not name or not username or len(password) < 6 or role not in ROLES:
            flash('Preencha todos os campos. A senha deve ter pelo menos 6 caracteres.')
        else:
            try:
                conn.execute('INSERT INTO users(name,username,password_hash,role,active,created_at) VALUES(?,?,?,?,?,?)',
                             (name, username, generate_password_hash(password), role, 1, now()))
                conn.commit()
                audit('CRIAR_USUARIO', username)
                flash('Usuário criado e salvo no banco de dados.')
            except sqlite3.IntegrityError:
                flash('Esse login já existe.')
    rows = conn.execute('SELECT id,name,username,role,active,created_at FROM users ORDER BY name').fetchall()
    conn.close()
    return render_template_string(USERS_HTML, users=rows)


@app.route('/usuarios/<int:user_id>/toggle', methods=['POST'])
@login_required
@manager_required
def toggle_user(user_id):
    conn = db()
    user = conn.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    if user and user['id'] != session['user_id']:
        new_status = 0 if user['active'] else 1
        conn.execute('UPDATE users SET active=? WHERE id=?', (new_status, user_id))
        conn.commit()
        audit('ALTERAR_STATUS_USUARIO', user['username'])
    conn.close()
    return redirect(url_for('users'))


@app.route('/usuarios/logins')
@login_required
@manager_required
def login_history():
    conn = db()
    logs = conn.execute('''SELECT l.*, u.name actor_name FROM audit_logs l
                           LEFT JOIN users u ON u.id=l.actor_id
                           ORDER BY l.created_at DESC LIMIT 500''').fetchall()
    conn.close()
    return render_template_string(LOGS_HTML, logs=logs)


@app.route('/dashboard')
@login_required
def dashboard():
    conn = db()
    manager = session['role'] in ('administrador', 'chefe')
    if manager:
        items = conn.execute('''SELECT i.*, u.name assigned_name FROM items i
                                LEFT JOIN users u ON u.id=i.assigned_to
                                ORDER BY i.status='finalizado', i.created_at''').fetchall()
        repaired = conn.execute("SELECT COUNT(*) FROM items WHERE status='finalizado'").fetchone()[0]
    else:
        items = conn.execute('''SELECT i.*, u.name assigned_name FROM items i
                                LEFT JOIN users u ON u.id=i.assigned_to
                                WHERE i.assigned_to=? OR i.created_by=?
                                ORDER BY i.status='finalizado', i.created_at''',
                               (session['user_id'], session['user_id'])).fetchall()
        repaired = conn.execute("SELECT COUNT(*) FROM items WHERE status='finalizado' AND assigned_to=?",
                                (session['user_id'],)).fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM items WHERE status!='finalizado'").fetchone()[0]
    waiting = conn.execute("SELECT COUNT(*) FROM items WHERE status='aguardando'").fetchone()[0]
    repairing = conn.execute("SELECT COUNT(*) FROM items WHERE status='consertando'").fetchone()[0]
    conn.close()
    rows = [dict(i) | {'priority_label': priority(i['created_at'], i['urgency'])} for i in items]
    return render_template_string(DASHBOARD_HTML, items=rows, total=total, waiting=waiting,
                                  repairing=repairing, repaired=repaired, manager=manager,
                                  user_name=session['name'], role=session['role'])


@app.route('/item/novo', methods=['GET', 'POST'])
@login_required
def new_item():
    if request.method == 'POST':
        product = request.form.get('product_name', '').strip()
        if not product:
            flash('Informe o nome do produto.')
            return redirect(url_for('new_item'))
        photo_name = None
        photo = request.files.get('photo')
        if photo and photo.filename and photo.filename.rsplit('.', 1)[-1].lower() in ALLOWED_EXTENSIONS:
            photo_name = secure_filename(f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{photo.filename}")
            photo.save(os.path.join(UPLOAD_DIR, photo_name))
        conn = db()
        cur = conn.execute('''INSERT INTO items(product_name,description,photo,urgency,status,created_at,created_by)
                              VALUES(?,?,?,?,?,?,?)''',
                           (product, request.form.get('description'), photo_name,
                            request.form.get('urgency', 'normal'), 'aguardando', now(), session['user_id']))
        item_id = cur.lastrowid
        conn.execute('INSERT INTO autosaves(item_id,user_id,content,saved_at) VALUES(?,?,?,?)',
                     (item_id, session['user_id'], request.form.get('description', ''), now()))
        conn.commit()
        conn.close()
        audit('CRIAR_ITEM', product)
        flash('Item cadastrado e salvo automaticamente.')
        return redirect(url_for('dashboard'))
    return render_template_string(ITEM_HTML)


@app.route('/item/<int:item_id>/iniciar', methods=['POST'])
@login_required
def start_item(item_id):
    conn = db()
    item = conn.execute('SELECT * FROM items WHERE id=?', (item_id,)).fetchone()
    manager = session['role'] in ('administrador', 'chefe')
    if not item or (not manager and item['assigned_to'] not in (None, session['user_id']) and item['created_by'] != session['user_id']):
        conn.close()
        return 'Não autorizado', 403
    conn.execute("UPDATE items SET status='consertando', started_at=COALESCE(started_at,?), assigned_to=COALESCE(assigned_to,?) WHERE id=?",
                 (now(), session['user_id'], item_id))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))


@app.route('/item/<int:item_id>/finalizar', methods=['POST'])
@login_required
def finish_item(item_id):
    conn = db()
    item = conn.execute('SELECT * FROM items WHERE id=?', (item_id,)).fetchone()
    manager = session['role'] in ('administrador', 'chefe')
    if not item or (not manager and item['assigned_to'] != session['user_id']):
        conn.close()
        return 'Não autorizado', 403
    conn.execute("UPDATE items SET status='finalizado', finished_at=?, notes=? WHERE id=?",
                 (now(), request.form.get('notes', ''), item_id))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))


@app.route('/autosave/<int:item_id>', methods=['POST'])
@login_required
def autosave(item_id):
    content = request.get_json(silent=True) or {}
    conn = db()
    item = conn.execute('SELECT * FROM items WHERE id=?', (item_id,)).fetchone()
    if not item:
        conn.close()
        return {'ok': False}, 404
    conn.execute('INSERT INTO autosaves(item_id,user_id,content,saved_at) VALUES(?,?,?,?)',
                 (item_id, session['user_id'], content.get('content', ''), now()))
    conn.commit()
    conn.close()
    return {'ok': True, 'saved_at': now()}


@app.route('/relatorio')
@login_required
def report():
    start = request.args.get('inicio', datetime.now().strftime('%Y-%m-01'))
    end = request.args.get('fim', datetime.now().strftime('%Y-%m-%d'))
    conn = db()
    query = '''SELECT i.*, u.name assigned_name FROM items i
               LEFT JOIN users u ON u.id=i.assigned_to
               WHERE date(i.created_at) BETWEEN date(?) AND date(?)'''
    params = [start, end]
    if session['role'] == 'funcionario':
        query += ' AND (i.assigned_to=? OR i.created_by=?)'
        params += [session['user_id'], session['user_id']]
    rows = conn.execute(query + ' ORDER BY i.created_at DESC', params).fetchall()
    conn.close()
    return render_template_string(REPORT_HTML, rows=rows, start=start, end=end)


@app.route('/relatorio/csv')
@login_required
def report_csv():
    start = request.args.get('inicio', datetime.now().strftime('%Y-%m-01'))
    end = request.args.get('fim', datetime.now().strftime('%Y-%m-%d'))
    conn = db()
    query = '''SELECT i.product_name,i.urgency,i.status,i.created_at,i.started_at,i.finished_at,
               u.name assigned_name,i.notes FROM items i LEFT JOIN users u ON u.id=i.assigned_to
               WHERE date(i.created_at) BETWEEN date(?) AND date(?)'''
    params = [start, end]
    if session['role'] == 'funcionario':
        query += ' AND (i.assigned_to=? OR i.created_by=?)'
        params += [session['user_id'], session['user_id']]
    rows = conn.execute(query + ' ORDER BY i.created_at DESC', params).fetchall()
    conn.close()
    path = os.path.join(BASE_DIR, 'relatorio.csv')
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(['Produto','Urgência','Status','Entrada','Início','Finalização','Responsável','Observações'])
        writer.writerows([tuple(r) for r in rows])
    return send_file(path, as_attachment=True, download_name=f'relatorio_{start}_{end}.csv')


LOGIN_HTML = '''<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><title>Acesso</title>
<style>body{font-family:Arial;background:#f3f4f6;display:grid;place-items:center;height:100vh}.box{background:white;padding:30px;border-radius:14px;width:340px;box-shadow:0 5px 25px #0001}input,button{width:100%;padding:11px;margin:7px 0;box-sizing:border-box}button{background:#111827;color:white;border:0;border-radius:8px}</style></head>
<body><div class="box"><h2>Sistema de Manutenção</h2>{% for m in get_flashed_messages() %}<p>{{m}}</p>{% endfor %}<form method="post"><input name="username" placeholder="Usuário" autocomplete="username" required><input type="password" name="password" placeholder="Senha" autocomplete="current-password" required><button>Entrar</button></form></div></body></html>'''

USERS_HTML = '''<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><title>Usuários</title>
<style>body{font-family:Arial;background:#f6f7f9}.wrap{max-width:1000px;margin:30px auto}.box{background:white;padding:20px;border-radius:12px;margin-bottom:20px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}input,select,button{padding:10px;margin:5px;width:calc(100% - 20px);box-sizing:border-box}button{background:#111827;color:white;border:0;border-radius:7px}table{width:100%;border-collapse:collapse}td,th{padding:9px;border-bottom:1px solid #ddd}</style></head>
<body><div class="wrap"><h2>Gerenciar usuários</h2>{% for m in get_flashed_messages() %}<div class="box">{{m}}</div>{% endfor %}<div class="grid"><div class="box"><h3>Criar usuário</h3><form method="post"><input name="name" placeholder="Nome completo" required><input name="username" placeholder="Login" required><input type="password" name="password" placeholder="Senha (mín. 6 caracteres)" required><select name="role"><option value="funcionario">Funcionário</option><option value="chefe">Chefe</option><option value="administrador">Administrador</option></select><button>Criar e salvar usuário</button></form></div>
<div class="box"><h3>Usuários cadastrados</h3><table><tr><th>Nome</th><th>Login</th><th>Perfil</th><th>Status</th></tr>{% for u in users %}<tr><td>{{u.name}}</td><td>{{u.username}}</td><td>{{u.role}}</td><td>{{'Ativo' if u.active else 'Bloqueado'}}{% if u.id != session['user_id'] %}<form method="post" action="/usuarios/{{u.id}}/toggle"><button>{{'Bloquear' if u.active else 'Ativar'}}</button></form>{% endif %}</td></tr>{% endfor %}</table></div></div><p><a href="/usuarios/logins">Ver histórico de logins/criação</a> · <a href="/dashboard">Voltar ao dashboard</a></p></div></body></html>'''

LOGS_HTML = '''<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><title>Histórico</title><style>body{font-family:Arial;margin:30px}table{width:100%;border-collapse:collapse}th,td{padding:9px;border-bottom:1px solid #ddd;text-align:left}</style></head><body><h2>Histórico de acesso e ações</h2><table><tr><th>Data/Hora</th><th>Usuário</th><th>Ação</th><th>Login afetado</th></tr>{% for l in logs %}<tr><td>{{l.created_at}}</td><td>{{l.actor_name or 'Sistema'}}</td><td>{{l.action}}</td><td>{{l.target_username or '—'}}</td></tr>{% endfor %}</table><p><a href="/usuarios">Voltar</a></p></body></html>'''

DASHBOARD_HTML = '''<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><title>Dashboard</title><style>body{font-family:Arial;margin:0;background:#f6f7f9;color:#111827}.top{background:#111827;color:white;padding:16px 24px;display:flex;justify-content:space-between}.wrap{max-width:1200px;margin:25px auto;padding:0 15px}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:15px}.card{background:white;padding:20px;border-radius:12px}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:15px;margin-top:20px}.item{background:white;padding:18px;border-radius:12px;border-left:6px solid #9ca3af}.urgente{border-left-color:#dc2626}.pouca\ urgência{border-left-color:#f59e0b}.btn{display:inline-block;padding:9px 12px;background:#111827;color:white;text-decoration:none;border-radius:7px;border:0;cursor:pointer}.tag{padding:4px 8px;border-radius:99px;background:#e5e7eb;font-size:12px}.muted{color:#6b7280}</style></head>
<body><div class="top"><b>Sistema de Manutenção</b><span>{{user_name}} · {{role}} · <a style="color:white" href="/logout">Sair</a></span></div><div class="wrap"><p><a class="btn" href="/item/novo">+ Cadastrar item</a> <a class="btn" href="/relatorio">Relatórios</a>{% if manager %} <a class="btn" href="/usuarios">Usuários</a>{% endif %}</p><div class="cards"><div class="card"><b>{{total}}</b><br>Produtos para arrumar</div><div class="card"><b>{{waiting}}</b><br>Aguardando</div><div class="card"><b>{{repairing}}</b><br>Em conserto</div><div class="card"><b>{{repaired}}</b><br>Já arrumados</div></div><div class="grid">{% for i in items %}<div class="item {{i.priority_label}}"><h3>{{i.product_name}}</h3><p>{{i.description or ''}}</p><span class="tag">{{i.priority_label}}</span> <span class="tag">{{i.status}}</span><p class="muted">Entrada: {{i.created_at}}<br>Início: {{i.started_at or '—'}}<br>Finalização: {{i.finished_at or '—'}}<br>Responsável: {{i.assigned_name or 'Não atribuído'}}</p>{% if i.status != 'finalizado' %}<form method="post" action="/item/{{i.id}}/iniciar"><button class="btn">Iniciar</button></form>{% if i.status == 'consertando' %}<form method="post" action="/item/{{i.id}}/finalizar"><input name="notes" placeholder="Observação final"><button class="btn">Finalizar</button></form>{% endif %}{% endif %}</div>{% endfor %}</div></div></body></html>'''

ITEM_HTML = '''<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><title>Novo item</title><style>body{font-family:Arial;background:#f6f7f9}.box{max-width:650px;margin:35px auto;background:white;padding:25px;border-radius:14px}input,textarea,select,button{width:100%;padding:11px;margin:7px 0;box-sizing:border-box}button{background:#111827;color:white;border:0;border-radius:8px}</style></head><body><div class="box"><h2>Cadastrar item para manutenção</h2><form method="post" enctype="multipart/form-data"><input name="product_name" placeholder="Nome do produto" required><textarea name="description" placeholder="Problema / descrição" rows="6"></textarea><select name="urgency"><option>normal</option><option>pouca urgência</option><option>urgente</option></select><input type="file" name="photo" accept="image/*"><button>Salvar item</button></form><a href="/dashboard">Voltar</a></div></body></html>'''

REPORT_HTML = '''<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><title>Relatório</title><style>body{font-family:Arial;margin:25px}table{width:100%;border-collapse:collapse}th,td{padding:8px;border:1px solid #ddd;text-align:left}button,a{padding:9px}</style></head><body><h2>Relatório de manutenção</h2><form><input type="date" name="inicio" value="{{start}}"><input type="date" name="fim" value="{{end}}"><button>Filtrar</button> <a href="/relatorio/csv?inicio={{start}}&fim={{end}}">Baixar CSV</a> <button type="button" onclick="window.print()">Imprimir</button></form><table><tr><th>Produto</th><th>Urgência</th><th>Status</th><th>Entrada</th><th>Início</th><th>Finalização</th><th>Responsável</th><th>Observações</th></tr>{% for r in rows %}<tr><td>{{r.product_name}}</td><td>{{r.urgency}}</td><td>{{r.status}}</td><td>{{r.created_at}}</td><td>{{r.started_at or '—'}}</td><td>{{r.finished_at or '—'}}</td><td>{{r.assigned_name or '—'}}</td><td>{{r.notes or ''}}</td></tr>{% endfor %}</table><p><a href="/dashboard">Voltar</a></p></body></html>'''

init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
