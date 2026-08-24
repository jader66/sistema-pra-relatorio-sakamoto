import io, os, csv, secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, redirect, url_for, session, render_template_string, send_file, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import create_engine, String, Integer, DateTime, Text, LargeBinary, ForeignKey, Boolean, or_, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

APP='Sakamoto | Manutenção'
DB=os.getenv('DATABASE_URL','sqlite:///sistema.db')
if DB.startswith('postgres://'): DB=DB.replace('postgres://','postgresql+psycopg://',1)
if DB.startswith('postgresql://'): DB=DB.replace('postgresql://','postgresql+psycopg://',1)
engine=create_engine(DB,pool_pre_ping=True)
Session=sessionmaker(bind=engine,expire_on_commit=False)
class Base(DeclarativeBase: pass
class User(Base):
    __tablename__='users'; id:Mapped[int]=mapped_column(primary_key=True); name:Mapped[str]=mapped_column(String(120)); username:Mapped[str]=mapped_column(String(80),unique=True,index=True); password_hash:Mapped[str]=mapped_column(String(255)); role:Mapped[str]=mapped_column(String(20),default='funcionario'); active:Mapped[bool]=mapped_column(Boolean,default=True); failed:Mapped[int]=mapped_column(Integer,default=0); locked_until:Mapped[datetime|None]=mapped_column(DateTime,nullable=True); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.now); last_login:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
class Order(Base):
    __tablename__='orders'; id:Mapped[int]=mapped_column(primary_key=True); number:Mapped[str]=mapped_column(String(40),unique=True,index=True); product:Mapped[str]=mapped_column(String(160)); client_sector:Mapped[str]=mapped_column(String(160),default=''); problem:Mapped[str]=mapped_column(Text,default=''); priority:Mapped[str]=mapped_column(String(30),default='normal'); status:Mapped[str]=mapped_column(String(30),default='aguardando'); responsible_id:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True); created_by:Mapped[int]=mapped_column(ForeignKey('users.id')); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.now); started_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True); finished_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True); parts:Mapped[str]=mapped_column(Text,default=''); notes:Mapped[str]=mapped_column(Text,default=''); photo:Mapped[bytes|None]=mapped_column(LargeBinary,nullable=True); photo_name:Mapped[str|None]=mapped_column(String(255),nullable=True)
class Audit(Base):
    __tablename__='audit'; id:Mapped[int]=mapped_column(primary_key=True); user_id:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True); action:Mapped[str]=mapped_column(String(100)); details:Mapped[str]=mapped_column(Text,default=''); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.now)
Base.metadata.create_all(engine)
app=Flask(__name__); app.secret_key=os.getenv('SECRET_KEY',secrets.token_hex(32)); app.config['MAX_CONTENT_LENGTH']=12*1024*1024
ROLES={'admin':'Administrador','chefe':'Chefe','funcionario':'Funcionário'}
def log(db,action,details=''): db.add(Audit(user_id=session.get('uid'),action=action,details=details))
def auth(f):
    @wraps(f)
    def w(*a,**k): return redirect(url_for('login')) if not session.get('uid') else f(*a,**k)
    return w
def manager(f):
    @wraps(f)
    def w(*a,**k): return abort(403) if session.get('role') not in ('admin','chefe') else f(*a,**k)
    return w

def first_setup():
    with Session() as db: return db.query(User).count()==0
LOGIN='''<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sakamoto</title><style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#061006;font-family:Arial;color:#fff}.box{width:min(440px,92vw);padding:35px;border:1px solid #3e7131;border-radius:24px;background:#071107;text-align:center;box-shadow:0 0 70px #54ff0022}.logo{font-size:42px;font-weight:900;color:#ffd500}.sub{color:#65ff20;letter-spacing:3px;font-size:10px;margin:5px 0 25px}.field{text-align:left;margin:12px 0}.field label{font-size:11px;color:#aebaa9}.field input,.field select{width:100%;padding:14px;margin-top:6px;border:1px solid #29442a;border-radius:11px;background:#0b180b;color:#fff}.btn{width:100%;padding:14px;border:0;border-radius:11px;background:linear-gradient(90deg,#ffd500,#75ff16);font-weight:900;cursor:pointer}.flash{background:#481b1b;padding:10px;border-radius:9px}</style></head><body><div class="box"><div class="logo">SAKAMOTO</div><div class="sub">VARIEDADES E TECNOLOGIA</div>{% for m in get_flashed_messages() %}<p class="flash">{{m}}</p>{% endfor %}{% if setup %}<h2>Primeira configuração</h2><p>Crie agora a sua conta de Administrador.</p><form method="post" action="/setup"><div class="field"><label>NOME</label><input name="name" required></div><div class="field"><label>USUÁRIO</label><input name="username" required></div><div class="field"><label>SENHA</label><input type="password" name="password" minlength="8" required></div><div class="field"><label>CONFIRMAR SENHA</label><input type="password" name="confirm" minlength="8" required></div><button class="btn">CRIAR CONTA ADMINISTRADOR</button></form>{% else %}<h2>Acesso ao sistema</h2><form method="post"><div class="field"><label>USUÁRIO</label><input name="username" autocomplete="username" required></div><div class="field"><label>SENHA</label><input type="password" name="password" autocomplete="current-password" required></div><button class="btn">ENTRAR</button></form>{% endif %}</div></body></html>'''
@app.route('/login',methods=['GET','POST'])
def login():
    if first_setup(): return redirect(url_for('setup'))
    if request.method=='POST':
        with Session() as db:
            u=db.query(User).filter(func.lower(User.username)==request.form.get('username','').strip().lower()).first()
            if not u or not u.active or (u.locked_until and u.locked_until>datetime.now()) or not check_password_hash(u.password_hash,request.form.get('password','')): flash('Usuário ou senha inválidos.'); return render_template_string(LOGIN,setup=False)
            u.failed=0;u.locked_until=None;u.last_login=datetime.now();session.update(uid=u.id,name=u.name,username=u.username,role=u.role);log(db,'LOGIN',u.username);db.commit()
        return redirect('/dashboard')
    return render_template_string(LOGIN,setup=False)
@app.route('/setup',methods=['GET','POST'])
def setup():
    if not first_setup(): return redirect(url_for('login'))
    if request.method=='POST':
        if request.form.get('password')!=request.form.get('confirm'): flash('As senhas não coincidem.'); return render_template_string(LOGIN,setup=True)
        if len(request.form.get('password',''))<8: flash('A senha deve ter pelo menos 8 caracteres.'); return render_template_string(LOGIN,setup=True)
        with Session() as db:
            u=User(name=request.form['name'].strip(),username=request.form['username'].strip().lower(),password_hash=generate_password_hash(request.form['password']),role='admin');db.add(u);db.commit();session.update(uid=u.id,name=u.name,username=u.username,role='admin');log(db,'CRIAR_ADMIN_INICIAL',u.username);db.commit()
        return redirect('/dashboard')
    return render_template_string(LOGIN,setup=True)
@app.route('/')
def index(): return redirect('/setup' if first_setup() else ('/dashboard' if session.get('uid') else '/login'))
@app.route('/logout')
def logout(): session.clear();return redirect('/login')
@app.route('/dashboard')
@auth
def dashboard(): return render_template_string('<h1>Dashboard</h1><p>Bem-vindo, {{name}}.</p><p><a href="/usuarios">Usuários</a> · <a href="/logout">Sair</a></p>',name=session['name'])
@app.route('/usuarios')
@auth
@manager
def usuarios():
    with Session() as db: us=db.query(User).order_by(User.name).all()
    return render_template_string('''<h1>Usuários</h1><h2>Criar usuário</h2><form method="post" action="/usuarios/criar"><input name="name" placeholder="Nome" required><input name="username" placeholder="Login" required><input name="password" type="password" placeholder="Senha" minlength="8" required><select name="role"><option value="funcionario">Funcionário</option><option value="chefe">Chefe</option>{% if session.role=='admin' %}<option value="admin">Administrador</option>{% endif %}</select><button>Criar usuário</button></form><hr><table>{% for u in us %}<tr><td>{{u.name}}</td><td>{{u.username}}</td><td>{{roles[u.role]}}</td><td>{{'Ativo' if u.active else 'Inativo'}}</td></tr>{% endfor %}</table>''',us=us,roles=ROLES)
@app.route('/usuarios/criar',methods=['POST'])
@auth
@manager
def criar_usuario():
    role=request.form.get('role','funcionario')
    if session['role']=='chefe' and role=='admin': abort(403)
    with Session() as db:
        if db.query(User).filter(func.lower(User.username)==request.form['username'].strip().lower()).first(): flash('Esse login já existe.');return redirect('/usuarios')
        u=User(name=request.form['name'].strip(),username=request.form['username'].strip().lower(),password_hash=generate_password_hash(request.form['password']),role=role);db.add(u);log(db,'CRIAR_USUARIO',u.username);db.commit()
    flash('Usuário criado com sucesso.');return redirect('/usuarios')
@app.errorhandler(403)
def e403(e): return 'Acesso negado',403
if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.getenv('PORT',5000)),debug=False)
