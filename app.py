import os, io, csv, secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, redirect, session, render_template_string, flash, abort, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import create_engine, String, Integer, DateTime, Boolean, Text, ForeignKey, LargeBinary, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from openpyxl import Workbook

DATABASE_URL=os.getenv('DATABASE_URL','sqlite:///sakamoto.db')
if DATABASE_URL.startswith('postgres://'): DATABASE_URL=DATABASE_URL.replace('postgres://','postgresql+psycopg://',1)
elif DATABASE_URL.startswith('postgresql://'): DATABASE_URL=DATABASE_URL.replace('postgresql://','postgresql+psycopg://',1)
engine=create_engine(DATABASE_URL,pool_pre_ping=True)
SessionLocal=sessionmaker(bind=engine,expire_on_commit=False)
class Base(DeclarativeBase): pass

class User(Base):
    __tablename__='users'
    id:Mapped[int]=mapped_column(primary_key=True); name:Mapped[str]=mapped_column(String(120)); username:Mapped[str]=mapped_column(String(80),unique=True,index=True); password_hash:Mapped[str]=mapped_column(String(255)); role:Mapped[str]=mapped_column(String(20),default='funcionario'); active:Mapped[bool]=mapped_column(Boolean,default=True); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class Product(Base):
    __tablename__='products'
    id:Mapped[int]=mapped_column(primary_key=True); name:Mapped[str]=mapped_column(String(160)); code:Mapped[str]=mapped_column(String(80),default=''); sector:Mapped[str]=mapped_column(String(160),default=''); description:Mapped[str]=mapped_column(Text,default=''); priority:Mapped[str]=mapped_column(String(30),default='Normal'); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class Service(Base):
    __tablename__='services'
    id:Mapped[int]=mapped_column(primary_key=True); product_id:Mapped[int|None]=mapped_column(ForeignKey('products.id'),nullable=True); client:Mapped[str]=mapped_column(String(160),default=''); problem:Mapped[str]=mapped_column(Text,default=''); priority:Mapped[str]=mapped_column(String(30),default='Normal'); status:Mapped[str]=mapped_column(String(30),default='Pendente'); responsible_id:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True); created_by:Mapped[int]=mapped_column(ForeignKey('users.id')); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow); started_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True); finished_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True); work_done:Mapped[str]=mapped_column(Text,default=''); notes:Mapped[str]=mapped_column(Text,default='')
class Photo(Base):
    __tablename__='photos'
    id:Mapped[int]=mapped_column(primary_key=True); product_id:Mapped[int|None]=mapped_column(ForeignKey('products.id'),nullable=True); service_id:Mapped[int|None]=mapped_column(ForeignKey('services.id'),nullable=True); filename:Mapped[str]=mapped_column(String(255)); mime:Mapped[str]=mapped_column(String(80)); data:Mapped[bytes]=mapped_column(LargeBinary); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class Audit(Base):
    __tablename__='audit'
    id:Mapped[int]=mapped_column(primary_key=True); user_id:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True); action:Mapped[str]=mapped_column(String(120)); details:Mapped[str]=mapped_column(Text,default=''); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class LoginAttempt(Base):
    __tablename__='login_attempts'
    id:Mapped[int]=mapped_column(primary_key=True); username:Mapped[str]=mapped_column(String(80),index=True); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

app=Flask(__name__); app.secret_key=os.getenv('SECRET_KEY') or secrets.token_hex(32)
ROLES={'admin':'Administrador','chefe':'Chefe','funcionario':'Funcionário'}
ALLOWED={'image/jpeg','image/png','image/webp','image/gif'}; MAX_PHOTO=8*1024*1024

def init_db():
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        if engine.dialect.name=='sqlite':
            pcols={r[1] for r in c.execute(text('PRAGMA table_info(products)')).fetchall()}
            scols={r[1] for r in c.execute(text('PRAGMA table_info(services)')).fetchall()}
            if 'priority' not in pcols: c.execute(text("ALTER TABLE products ADD COLUMN priority VARCHAR(30) DEFAULT 'Normal'"))
            if 'product_id' not in scols: c.execute(text("ALTER TABLE services ADD COLUMN product_id INTEGER"))
            if 'work_done' not in scols: c.execute(text("ALTER TABLE services ADD COLUMN work_done TEXT DEFAULT ''"))
        else:
            c.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS priority VARCHAR(30) DEFAULT 'Normal'"))
            c.execute(text("ALTER TABLE services ADD COLUMN IF NOT EXISTS product_id INTEGER"))
            c.execute(text("ALTER TABLE services ADD COLUMN IF NOT EXISTS work_done TEXT DEFAULT ''"))
    with SessionLocal() as d:
        try:
            rows=d.execute(text("SELECT id, product FROM services WHERE product_id IS NULL AND product IS NOT NULL AND product <> ''")).fetchall()
            for sid,pname in rows:
                p=d.query(Product).filter(func.lower(Product.name)==pname.lower()).first()
                if not p:
                    p=Product(name=pname);d.add(p);d.flush()
                d.execute(text("UPDATE services SET product_id=:pid WHERE id=:sid"),{'pid':p.id,'sid':sid})
            d.commit()
        except Exception:
            d.rollback()

def db(): return SessionLocal()
def log(d,action,details=''): d.add(Audit(user_id=session.get('uid'),action=action,details=details))
def auth(fn):
    @wraps(fn)
    def w(*a,**k): return fn(*a,**k) if session.get('uid') else redirect('/login')
    return w
def manager(fn):
    @wraps(fn)
    def w(*a,**k): return fn(*a,**k) if session.get('role') in ('admin','chefe') else abort(403)
    return w
def admin(fn):
    @wraps(fn)
    def w(*a,**k): return fn(*a,**k) if session.get('role')=='admin' else abort(403)
    return w
def priority_for(s):
    if s.status=='Finalizado': return s.priority
    age=(datetime.utcnow()-s.created_at).days
    if age>=7: return 'Urgente'
    if age>=3 and s.priority=='Normal': return 'Pouca urgência'
    return s.priority
def add_photos(d,files,product_id=None,service_id=None):
    count=0
    for f in files:
        if not f or not f.filename: continue
        if f.mimetype not in ALLOWED: flash(f'Formato não permitido: {f.filename}');continue
        data=f.read(MAX_PHOTO+1)
        if len(data)>MAX_PHOTO: flash(f'Foto maior que 8 MB: {f.filename}');continue
        d.add(Photo(product_id=product_id,service_id=service_id,filename=f.filename[:255],mime=f.mimetype,data=data));count+=1
    return count

# Keep the health endpoint independent from the database. This prevents a slow/unavailable
# PostgreSQL connection from making Gunicorn fail health checks with a 502.
_db_ready=False
@app.get('/status')
def status():
    return {'status':'ok','service':'sistema-manutencao-sakamoto'},200

@app.before_request
def ensure_database():
    global _db_ready
    if request.path == '/status':
        return None
    if not _db_ready:
        try:
            init_db()
            _db_ready=True
        except Exception:
            app.logger.exception('Database initialization failed')
            return ('Banco de dados indisponível. Verifique DATABASE_URL no Render.',503)
    return None

STYLE='''<style>*{box-sizing:border-box}body{margin:0;background:#061006;color:#eef7ed;font-family:Inter,Arial,sans-serif}.login{min-height:100vh;display:grid;place-items:center;padding:24px;background:radial-gradient(circle at 50% 10%,#123d14,#061006 55%)}.box{width:min(470px,94vw);padding:34px;border:1px solid #20e84a;border-radius:24px;background:#071307ee;box-shadow:0 20px 80px #0008}.logo{text-align:center;font-size:42px;font-weight:950}.logo b,.brand b{color:#53ff20}.sub{text-align:center;color:#69ff36;font-size:11px;letter-spacing:3px;margin:6px 0 28px}.field{margin:12px 0}.field label{display:block;font-size:11px;color:#9eae9a;margin-bottom:7px}input,select,textarea{width:100%;padding:13px;border:1px solid #315936;border-radius:10px;background:#081408;color:#fff}.btn{display:inline-block;border:0;border-radius:10px;padding:12px 17px;background:#ffd21a;color:#111;font-weight:900;text-decoration:none;cursor:pointer}.green{background:#35ed24}.full{width:100%}.link{display:block;text-align:center;margin-top:17px;color:#72ff4b;text-decoration:none}.flash{background:#542323;padding:11px;border-radius:9px}.app{display:flex;min-height:100vh}.side{width:245px;background:#0a150a;border-right:1px solid #1e351f;padding:20px 13px;position:fixed;inset:0 auto 0 0}.brand{padding:10px 14px;font-size:27px;font-weight:950;color:#fff}.brand small{display:block;color:#68ff3a;font-size:8px;letter-spacing:2px}.nav{margin-top:22px}.nav a{display:block;padding:13px 14px;margin:4px 0;color:#b7c4b5;text-decoration:none;border-radius:10px}.nav a:hover{background:#172619;color:#fff}.main{margin-left:245px;flex:1}.top{height:72px;border-bottom:1px solid #1d331e;display:flex;justify-content:flex-end;align-items:center;gap:18px;padding:0 28px}.content{padding:28px;max-width:1500px;margin:auto}.muted{color:#8e9f8c}.cards{display:grid;grid-template-columns:repeat(5,1fr);gap:16px;margin:24px 0}.card,.panel{background:#0c190c;border:1px solid #203b21;border-radius:16px;padding:20px}.num{font-size:31px;font-weight:900}.label{font-size:13px;color:#99a996;margin-top:5px}.grid{display:grid;grid-template-columns:2fr 1fr;gap:18px}.form{display:grid;grid-template-columns:1fr 1fr;gap:14px}.fullcol{grid-column:1/-1}.table{width:100%;border-collapse:collapse}.table th,.table td{padding:12px;border-bottom:1px solid #203620;text-align:left}.badge{display:inline-block;padding:5px 9px;border-radius:99px;background:#1d381e;font-size:11px}.actions{display:flex;gap:8px;flex-wrap:wrap}.photos{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}.photos img{width:100%;height:150px;object-fit:cover;border-radius:12px;border:1px solid #315936}@media(max-width:850px){.side{width:72px}.brand{font-size:0}.brand:before{content:'S';font-size:28px}.brand small,.nav span{display:none}.main{margin-left:72px}.cards{grid-template-columns:1fr 1fr}.grid,.form{grid-template-columns:1fr}}
</style>'''

def login_html(create=False):
    extra='''<h2>Crie sua conta</h2><p class="muted">A primeira conta será Administrador. Depois os cargos são definidos pelo Administrador.</p><form method="post"><div class="field"><label>NOME</label><input name="name" required></div><div class="field"><label>USUÁRIO</label><input name="username" required></div><div class="field"><label>SENHA</label><input type="password" name="password" minlength="8" required></div><div class="field"><label>CONFIRMAR SENHA</label><input type="password" name="confirm" minlength="8" required></div><button class="btn green full">CRIAR CONTA ADMINISTRADOR</button></form><a class="link" href="/login">Voltar ao login</a>''' if create else '''<h2>Login</h2><form method="post"><div class="field"><label>USUÁRIO</label><input name="username" autocomplete="username" required></div><div class="field"><label>SENHA</label><input type="password" name="password" autocomplete="current-password" required></div><button class="btn green full">ENTRAR</button></form><a class="link" href="/criar-conta">➕ Criar conta</a>'''
    return render_template_string(f'''<!doctype html><html lang="pt-br"><head><meta charset="utf-8">{STYLE}</head><body><div class="login"><div class="box"><div class="logo"><b>SAKA</b>MOTO</div><div class="sub">SISTEMA DE CONTROLE E MANUTENÇÃO</div>{{% for m in get_flashed_messages() %}}<p class="flash">{{{{m}}}}</p>{{% endfor %}}{extra}</div></div></body></html>''')

def shell(content,**ctx):
    return render_template_string(f'''<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><title>Sakamoto | Manutenção</title>{STYLE}</head><body><div class="app"><aside class="side"><div class="brand"><b>SAKA</b>MOTO<small>MANUTENÇÃO</small></div><nav class="nav"><a href="/dashboard">📊 <span>Dashboard</span></a><a href="/servicos">🛠️ <span>Ordens de serviço</span></a><a href="/produtos">📦 <span>Produtos</span></a>{{% if session.role in ['admin','chefe'] %}}<a href="/usuarios">👥 <span>Funcionários</span></a>{{% endif %}}<a href="/relatorios">📄 <span>Relatórios</span></a><a href="/historico">🕘 <span>Histórico</span></a><a href="/configuracoes">⚙️ <span>Configurações</span></a></nav></aside><main class="main"><header class="top"><span>🔔</span><b>{{{{session.name}}}}</b><span class="badge">{{{{roles[session.role]}}}}</span><a class="btn" href="/logout">Sair</a></header><section class="content">{content}</section></main></div></body></html>''',roles=ROLES,**ctx)

@app.get('/')
def index(): return redirect('/login')
@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        username=request.form.get('username','').strip().lower();now=datetime.utcnow()
        with db() as d:
            recent=d.query(LoginAttempt).filter(LoginAttempt.username==username,LoginAttempt.created_at>=now-timedelta(minutes=15)).count()
            if recent>=5: flash('Login temporariamente bloqueado. Tente novamente em alguns minutos.');return login_html()
            u=d.query(User).filter(func.lower(User.username)==username).first()
            if not u or not u.active or not check_password_hash(u.password_hash,request.form.get('password','')):
                d.add(LoginAttempt(username=username));d.commit();flash('Usuário ou senha inválidos.');return login_html()
            session.update(uid=u.id,name=u.name,username=u.username,role=u.role);log(d,'LOGIN',u.username);d.commit()
        return redirect('/dashboard')
    return login_html()
@app.route('/criar-conta',methods=['GET','POST'])
def criar_conta():
    with db() as d:
        if d.query(User).count()>0: flash('A conta inicial já existe. O Administrador cria os demais usuários.');return redirect('/login')
        if request.method=='POST':
            if request.form.get('password')!=request.form.get('confirm'): flash('As senhas não coincidem.');return login_html(True)
            if len(request.form.get('password',''))<8: flash('A senha deve ter pelo menos 8 caracteres.');return login_html(True)
            u=User(name=request.form['name'].strip(),username=request.form['username'].strip().lower(),password_hash=generate_password_hash(request.form['password']),role='admin');d.add(u);d.commit();session.update(uid=u.id,name=u.name,username=u.username,role='admin');log(d,'CRIAR_ADMIN_INICIAL',u.username);d.commit();return redirect('/dashboard')
    return login_html(True)

