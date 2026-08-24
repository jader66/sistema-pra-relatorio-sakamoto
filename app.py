import os, secrets
from datetime import datetime
from functools import wraps
from flask import Flask, request, redirect, url_for, session, render_template_string, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import create_engine, String, Integer, DateTime, Boolean, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DB=os.getenv('DATABASE_URL','sqlite:///sistema.db')
if DB.startswith('postgres://'): DB=DB.replace('postgres://','postgresql+psycopg://',1)
if DB.startswith('postgresql://'): DB=DB.replace('postgresql://','postgresql+psycopg://',1)
engine=create_engine(DB,pool_pre_ping=True)
Session=sessionmaker(bind=engine,expire_on_commit=False)
class Base(DeclarativeBase): pass
class User(Base):
    __tablename__='users'
    id:Mapped[int]=mapped_column(primary_key=True)
    name:Mapped[str]=mapped_column(String(120))
    username:Mapped[str]=mapped_column(String(80),unique=True,index=True)
    password_hash:Mapped[str]=mapped_column(String(255))
    role:Mapped[str]=mapped_column(String(20),default='funcionario')
    active:Mapped[bool]=mapped_column(Boolean,default=True)
    failed:Mapped[int]=mapped_column(Integer,default=0)
    locked_until:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.now)
Base.metadata.create_all(engine)
app=Flask(__name__)
app.secret_key=os.getenv('SECRET_KEY',secrets.token_hex(32))
ROLES={'admin':'Administrador','chefe':'Chefe','funcionario':'Funcionário'}

def count_users():
    with Session() as db: return db.query(User).count()
def auth(f):
    @wraps(f)
    def w(*a,**k):
        if not session.get('uid'): return redirect('/login')
        return f(*a,**k)
    return w
def manager(f):
    @wraps(f)
    def w(*a,**k):
        if session.get('role') not in ('admin','chefe'): abort(403)
        return f(*a,**k)
    return w

PAGE='''<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sakamoto | Manutenção</title><style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#061006;font-family:Arial;color:#fff}.box{width:min(430px,92vw);padding:36px;border:1px solid #3e7131;border-radius:24px;background:#071107;text-align:center;box-shadow:0 0 70px #54ff0022}.logo{font-size:42px;font-weight:900;color:#ffd500}.sub{color:#65ff20;letter-spacing:3px;font-size:10px;margin:5px 0 25px}.field{text-align:left;margin:12px 0}.field label{font-size:11px;color:#aebaa9}.field input,.field select{box-sizing:border-box;width:100%;padding:14px;margin-top:6px;border:1px solid #29442a;border-radius:11px;background:#0b180b;color:#fff}.btn{width:100%;padding:14px;border:0;border-radius:11px;background:linear-gradient(90deg,#ffd500,#75ff16);font-weight:900;cursor:pointer}.link{display:block;margin-top:18px;color:#8cff65;text-decoration:none}.msg{background:#481b1b;padding:10px;border-radius:9px}</style></head><body><div class="box"><div class="logo">SAKAMOTO</div><div class="sub">VARIEDADES E TECNOLOGIA</div>{% for m in get_flashed_messages() %}<p class="msg">{{m}}</p>{% endfor %}{{content|safe}}</div></body></html>'''

def login_html():
    return render_template_string(PAGE,content='''<h2>Acesso ao sistema</h2><form method="post"><div class="field"><label>USUÁRIO</label><input name="username" autocomplete="username" required></div><div class="field"><label>SENHA</label><input type="password" name="password" autocomplete="current-password" required></div><button class="btn">ENTRAR</button></form><a class="link" href="/criar-conta">➕ Criar conta</a>''')

def setup_html():
    return render_template_string(PAGE,content='''<h2>Criar conta</h2><p>Crie sua conta de Administrador.</p><form method="post"><div class="field"><label>NOME</label><input name="name" required></div><div class="field"><label>USUÁRIO</label><input name="username" required></div><div class="field"><label>SENHA</label><input type="password" name="password" minlength="8" required></div><div class="field"><label>CONFIRMAR SENHA</label><input type="password" name="confirm" minlength="8" required></div><button class="btn">CRIAR CONTA</button></form><a class="link" href="/login">Voltar para o login</a>''')

@app.route('/')
def index(): return redirect('/login')
@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        with Session() as db:
            u=db.query(User).filter(func.lower(User.username)==request.form.get('username','').strip().lower()).first()
            if not u or not u.active or not check_password_hash(u.password_hash,request.form.get('password','')):
                flash('Usuário ou senha inválidos.'); return login_html()
            session.update(uid=u.id,name=u.name,username=u.username,role=u.role)
        return redirect('/dashboard')
    return login_html()
@app.route('/criar-conta',methods=['GET','POST'])
def criar_conta():
    if count_users()>0:
        flash('A criação inicial já foi concluída. Novas contas devem ser criadas pelo Administrador.'); return redirect('/login')
    if request.method=='POST':
        if request.form['password']!=request.form['confirm']: flash('As senhas não coincidem.'); return setup_html()
        if len(request.form['password'])<8: flash('A senha deve ter pelo menos 8 caracteres.'); return setup_html()
        with Session() as db:
            u=User(name=request.form['name'].strip(),username=request.form['username'].strip().lower(),password_hash=generate_password_hash(request.form['password']),role='admin')
            db.add(u); db.commit(); session.update(uid=u.id,name=u.name,username=u.username,role='admin')
        return redirect('/dashboard')
    return setup_html()
@app.route('/dashboard')
@auth
def dashboard():
    return render_template_string('<h1>Dashboard Sakamoto</h1><p>Bem-vindo, {{name}} — {{role}}</p><p><a href="/usuarios">👥 Usuários</a> · <a href="/logout">Sair</a></p>',name=session['name'],role=ROLES[session['role']])
@app.route('/usuarios')
@auth
@manager
def usuarios():
    with Session() as db: users=db.query(User).order_by(User.name).all()
    return render_template_string('''<h1>👥 Usuários</h1><h2>➕ Criar usuário</h2><form method="post" action="/usuarios/criar"><input name="name" placeholder="Nome" required><input name="username" placeholder="Login" required><input name="password" type="password" placeholder="Senha" minlength="8" required><select name="role"><option value="funcionario">Funcionário</option><option value="chefe">Chefe</option>{% if session.role=='admin' %}<option value="admin">Administrador</option>{% endif %}</select><button>Criar usuário</button></form><hr>{% for u in users %}<p><b>{{u.name}}</b> — {{u.username}} — {{roles[u.role]}}</p>{% endfor %}<a href="/dashboard">Voltar</a>''',users=users,roles=ROLES)
@app.route('/usuarios/criar',methods=['POST'])
@auth
@manager
def criar_usuario():
    role=request.form.get('role','funcionario')
    if session['role']=='chefe' and role=='admin': abort(403)
    with Session() as db:
        if db.query(User).filter(func.lower(User.username)==request.form['username'].strip().lower()).first(): flash('Esse login já existe.'); return redirect('/usuarios')
        db.add(User(name=request.form['name'].strip(),username=request.form['username'].strip().lower(),password_hash=generate_password_hash(request.form['password']),role=role)); db.commit()
    flash('Usuário criado com sucesso.'); return redirect('/usuarios')
@app.route('/logout')
def logout(): session.clear(); return redirect('/login')
@app.errorhandler(403)
def forbidden(e): return 'Acesso negado',403
if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.getenv('PORT',5000)),debug=False)
