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
try:
    init_db()
except Exception:
    app.logger.exception('Database initialization failed during startup')

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
STYLE='''<style>*{box-sizing:border-box}body{margin:0;background:#061006;color:#eef7ed;font-family:Inter,Arial,sans-serif}.login{min-height:100vh;display:grid;place-items:center;padding:24px;background:radial-gradient(circle at 50% 10%,#123d14,#061006 55%)}.box{width:min(470px,94vw);padding:34px;border:1px solid #20e84a;border-radius:24px;background:#071307ee;box-shadow:0 20px 80px #0008}.logo{text-align:center;font-size:42px;font-weight:950}.logo b,.brand b{color:#53ff20}.sub{text-align:center;color:#69ff36;font-size:11px;letter-spacing:3px;margin:6px 0 28px}.field{margin:12px 0}.field label{display:block;font-size:11px;color:#9eae9a;margin-bottom:7px}input,select,textarea{width:100%;padding:13px;border:1px solid #315936;border-radius:10px;background:#081408;color:#fff}.btn{display:inline-block;border:0;border-radius:10px;padding:12px 17px;background:#ffd21a;color:#111;font-weight:900;text-decoration:none;cursor:pointer}.green{background:#35ed24}.full{width:100%}.link{display:block;text-align:center;margin-top:17px;color:#72ff4b;text-decoration:none}.flash{background:#542323;padding:11px;border-radius:9px}.app{display:flex;min-height:100vh}.side{width:245px;background:#0a150a;border-right:1px solid #1e351f;padding:20px 13px;position:fixed;inset:0 auto 0 0}.brand{padding:10px 14px;font-size:27px;font-weight:950;color:#fff}.brand small{display:block;color:#68ff3a;font-size:8px;letter-spacing:2px}.nav{margin-top:22px}.nav a{display:block;padding:13px 14px;margin:4px 0;color:#b7c4b5;text-decoration:none;border-radius:10px}.nav a:hover{background:#172619;color:#fff}.main{margin-left:245px;flex:1}.top{height:72px;border-bottom:1px solid #1d331e;display:flex;justify-content:flex-end;align-items:center;gap:18px;padding:0 28px}.content{padding:28px;max-width:1500px;margin:auto}.muted{color:#8e9f8c}.cards{display:grid;grid-template-columns:repeat(5,1fr);gap:16px;margin:24px 0}.card,.panel{background:#0c190c;border:1px solid #203b21;border-radius:16px;padding:20px}.num{font-size:31px;font-weight:900}.label{font-size:13px;color:#99a996;margin-top:5px}.grid{display:grid;grid-template-columns:2fr 1fr;gap:18px}.form{display:grid;grid-template-columns:1fr 1fr;gap:14px}.fullcol{grid-column:1/-1}.table{width:100%;border-collapse:collapse}.table th,.table td{padding:12px;border-bottom:1px solid #203620;text-align:left}.badge{display:inline-block;padding:5px 9px;border-radius:99px;background:#1d381e;font-size:11px}.actions{display:flex;gap:8px;flex-wrap:wrap}.photos{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}.photos img{width:100%;height:150px;object-fit:cover;border-radius:12px;border:1px solid #315936}@media(max-width:850px){.side{width:72px}.brand{font-size:0}.brand:before{content:'S';font-size:28px}.brand small,.nav span{display:none}.main{margin-left:72px}.cards{grid-template-columns:1fr 1fr}.grid,.form{grid-template-columns:1fr}}
</style>'''
def login_html(create=False):
    extra='''<h2>Crie sua conta</h2><p class="muted">A primeira conta será Administrador. Depois os cargos são definidos pelo Administrador.</p><form method="post"><div class="field"><label>NOME</label><input name="name" required></div><div class="field"><label>USUÁRIO</label><input name="username" required></div><div class="field"><label>SENHA</label><input type="password" name="password" minlength="8" required></div><div class="field"><label>CONFIRMAR SENHA</label><input type="password" name="confirm" minlength="8" required></div><button class="btn green full">CRIAR CONTA ADMINISTRADOR</button></form><a class="link" href="/login">Voltar ao login</a>''' if create else '''<h2>Login</h2><form method="post"><div class="field"><label>USUÁRIO</label><input name="username" autocomplete="username" required></div><div class="field"><label>SENHA</label><input type="password" name="password" autocomplete="current-password" required></div><button class="btn green full">ENTRAR</button></form><a class="link" href="/criar-conta">➕ Criar conta</a>'''
    return render_template_string(f'''<!doctype html><html lang="pt-br"><head><meta charset="utf-8">{STYLE}</head><body><div class="login"><div class="box"><div class="logo"><b>SAKA</b>MOTO</div><div class="sub">SISTEMA DE CONTROLE E MANUTENÇÃO</div>{{% for m in get_flashed_messages() %}}<p class="flash">{{{{m}}}}</p>{{% endfor %}}{extra}</div></div></body></html>''')
def shell(content,**ctx):
    return render_template_string(f'''<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sakamoto | Manutenção</title>{STYLE}</head><body><div class="app"><aside class="side"><div class="brand"><b>SAKA</b>MOTO<small>MANUTENÇÃO</small></div><nav class="nav"><a href="/dashboard">📊 <span>Dashboard</span></a><a href="/servicos">🛠️ <span>Ordens de serviço</span></a><a href="/produtos">📦 <span>Produtos</span></a>{{% if session.role in ['admin','chefe'] %}}<a href="/usuarios">👥 <span>Funcionários</span></a>{{% endif %}}<a href="/relatorios">📄 <span>Relatórios</span></a><a href="/historico">🕘 <span>Histórico</span></a><a href="/configuracoes">⚙️ <span>Configurações</span></a></nav></aside><main class="main"><header class="top"><span>🔔</span><b>{{{{session.name}}}}</b><span class="badge">{{{{roles[session.role]}}}}</span><a class="btn" href="/logout">Sair</a></header><section class="content">{content}</section></main></div></body></html>''',roles=ROLES,**ctx)

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
@app.get('/logout')
def logout(): session.clear();return redirect('/login')

@app.get('/dashboard')
@auth
def dashboard():
    with db() as d:
        q=d.query(Service)
        if session['role']=='funcionario': q=q.filter(Service.responsible_id==session['uid'])
        services=q.all();pending=sum(s.status=='Pendente' for s in services);active=sum(s.status=='Em andamento' for s in services);finished=sum(s.status=='Finalizado' for s in services);urgent=sum(priority_for(s)=='Urgente' for s in services);products=d.query(Product).count()
    return shell('''<h1>Dashboard</h1><p class="muted">Controle das manutenções</p>{% if session.role in ['admin','chefe'] %}<div class="actions"><a class="btn green" href="/usuarios">👤 Criar usuário</a><a class="btn" href="/servicos/novo">🛠️ Nova manutenção</a></div>{% endif %}<div class="cards"><div class="card"><div class="num">{{products}}</div><div class="label">Equipamentos cadastrados</div></div><div class="card"><div class="num">{{pending}}</div><div class="label">Aguardando</div></div><div class="card"><div class="num">{{active}}</div><div class="label">Em manutenção</div></div><div class="card"><div class="num">{{finished}}</div><div class="label">Finalizados</div></div><div class="card"><div class="num">{{urgent}}</div><div class="label">Urgentes</div></div></div><div class="panel"><h3>Fluxo</h3><p class="muted">Cadastrar equipamento → atribuir manutenção → iniciar → consertar → finalizar → histórico.</p></div>''',products=products,pending=pending,active=active,finished=finished,urgent=urgent)

@app.get('/criar-usuario')
@auth
@manager
def criar_usuario_pagina(): return redirect('/usuarios')

@app.get('/usuarios')
@auth
@manager
def usuarios():
    with db() as d: users=d.query(User).order_by(User.name).all()
    return shell('''<h1>Funcionários e usuários</h1><div class="actions"><a class="btn green" href="#novo-usuario">➕ Criar usuário</a></div><br><div class="panel" id="novo-usuario"><form class="form" method="post" action="/usuarios/criar"><div class="field"><label>NOME</label><input name="name" required></div><div class="field"><label>LOGIN</label><input name="username" required></div><div class="field"><label>SENHA</label><input name="password" type="password" minlength="8" required></div><div class="field"><label>CARGO</label><select name="role"><option value="funcionario">Funcionário</option><option value="chefe">Chefe</option>{% if session.role=='admin' %}<option value="admin">Administrador</option>{% endif %}</select></div><button class="btn green fullcol">➕ Criar usuário</button></form></div><br><div class="panel"><table class="table"><tr><th>Nome</th><th>Login</th><th>Cargo</th><th>Status</th><th>Ação</th></tr>{% for u in users %}<tr><td>{{u.name}}</td><td>{{u.username}}</td><td>{{roles[u.role]}}</td><td>{{'Ativo' if u.active else 'Desativado'}}</td><td>{% if session.role=='admin' %}<a class="btn" href="/usuarios/{{u.id}}">Editar</a>{% endif %}</td></tr>{% endfor %}</table></div>''',users=users)
@app.post('/usuarios/criar')
@auth
@manager
def criar_usuario():
    role=request.form.get('role','funcionario')
    if role not in ROLES: abort(400)
    if session['role']=='chefe' and role!='funcionario': abort(403)
    with db() as d:
        username=request.form.get('username','').strip().lower(); name=request.form.get('name','').strip(); password=request.form.get('password','')
        if not name or not username or len(password)<8: flash('Preencha nome, login e senha com pelo menos 8 caracteres.');return redirect('/usuarios')
        if d.query(User).filter(func.lower(User.username)==username).first(): flash('Esse login já existe.');return redirect('/usuarios')
        d.add(User(name=name,username=username,password_hash=generate_password_hash(password),role=role));d.commit();log(d,'CRIAR_USUARIO',f'{username} | {role}');d.commit();flash('Usuário criado com sucesso.');return redirect('/usuarios')
@app.route('/usuarios/<int:uid>',methods=['GET','POST'])
@auth
@admin
def editar_usuario(uid):
    with db() as d:
        u=d.get(User,uid)
        if not u: abort(404)
        if request.method=='POST':
            u.name=request.form['name'].strip();u.role=request.form['role'];u.active=request.form.get('active')=='1'
            if request.form.get('password'): u.password_hash=generate_password_hash(request.form['password'])
            d.commit();log(d,'EDITAR_USUARIO',f'{u.username} -> {u.role}');d.commit();flash('Usuário atualizado.');return redirect('/usuarios')
    return shell('''<h1>Editar usuário</h1><div class="panel"><form method="post" class="form"><div class="field"><label>NOME</label><input name="name" value="{{u.name}}" required></div><div class="field"><label>LOGIN</label><input value="{{u.username}}" disabled></div><div class="field"><label>CARGO</label><select name="role"><option value="funcionario" {% if u.role=='funcionario' %}selected{% endif %}>Funcionário</option><option value="chefe" {% if u.role=='chefe' %}selected{% endif %}>Chefe</option><option value="admin" {% if u.role=='admin' %}selected{% endif %}>Administrador</option></select></div><div class="field"><label>STATUS</label><select name="active"><option value="1" {% if u.active %}selected{% endif %}>Ativo</option><option value="0" {% if not u.active %}selected{% endif %}>Desativado</option></select></div><div class="field fullcol"><label>NOVA SENHA (opcional)</label><input type="password" name="password" minlength="8"></div><button class="btn green fullcol">Salvar alterações</button></form></div>''',u=u)

@app.route('/produtos',methods=['GET','POST'])
@auth
def produtos():
    with db() as d:
        if request.method=='POST':
            if session['role'] not in ('admin','chefe'): abort(403)
            p=Product(name=request.form['name'].strip(),code=request.form.get('code','').strip(),sector=request.form.get('sector','').strip(),description=request.form.get('description','').strip(),priority=request.form.get('priority','Normal'));d.add(p);d.commit();count=add_photos(d,request.files.getlist('photos'),product_id=p.id);log(d,'CADASTRAR_PRODUTO',f'{p.name} | {count} foto(s)');d.commit();flash('Equipamento cadastrado para manutenção.');return redirect(f'/produtos/{p.id}')
        products=d.query(Product).order_by(Product.created_at.desc()).all();open_ids={p.id for p in products if d.query(Service).filter(Service.product_id==p.id,Service.status!='Finalizado').first()}
    return shell('''<h1>📦 Equipamentos para manutenção</h1>{% if session.role in ['admin','chefe'] %}<div class="panel"><h3>➕ Cadastrar equipamento</h3><form class="form" method="post" enctype="multipart/form-data"><div class="field"><label>NOME DO EQUIPAMENTO</label><input name="name" required></div><div class="field"><label>CÓDIGO / PATRIMÔNIO</label><input name="code"></div><div class="field"><label>CLIENTE / SETOR</label><input name="sector"></div><div class="field"><label>PRIORIDADE</label><select name="priority"><option>Normal</option><option>Pouca urgência</option><option>Urgente</option></select></div><div class="field fullcol"><label>PROBLEMA / DESCRIÇÃO</label><textarea name="description" rows="3"></textarea></div><div class="field fullcol"><label>📷 FOTOS DO EQUIPAMENTO</label><input type="file" name="photos" accept="image/jpeg,image/png,image/webp,image/gif" multiple></div><button class="btn green fullcol">CADASTRAR EQUIPAMENTO</button></form></div><br>{% endif %}<div class="panel"><table class="table"><tr><th>Equipamento</th><th>Patrimônio</th><th>Setor</th><th>Prioridade</th><th>Status</th><th></th></tr>{% for p in products %}<tr><td>{{p.name}}</td><td>{{p.code}}</td><td>{{p.sector}}</td><td>{{p.priority}}</td><td>{% if p.id in open_ids %}Em manutenção{% else %}Sem serviço{% endif %}</td><td><a class="btn" href="/produtos/{{p.id}}">Abrir</a></td></tr>{% else %}<tr><td colspan="6">Nenhum produto cadastrado.</td></tr>{% endfor %}</table></div>''',products=products,open_ids=open_ids)

@app.route('/produtos/<int:pid>',methods=['GET','POST'])
@auth
def produto_detalhe(pid):
    with db() as d:
        p=d.get(Product,pid)
        if not p: abort(404)
        if request.method=='POST':
            if session['role'] not in ('admin','chefe'): abort(403)
            p.name=request.form['name'].strip();p.code=request.form.get('code','').strip();p.sector=request.form.get('sector','').strip();p.description=request.form.get('description','').strip();p.priority=request.form.get('priority','Normal');add_photos(d,request.files.getlist('photos'),product_id=p.id);d.query(Service).filter(Service.product_id==p.id,Service.status!='Finalizado').update({'priority':p.priority},synchronize_session=False);log(d,'EDITAR_PRODUTO',f'{p.id} - {p.name}');d.commit();flash('Produto atualizado.');return redirect(f'/produtos/{pid}')
        services=d.query(Service).filter(Service.product_id==pid).order_by(Service.created_at.desc()).all();photos=d.query(Photo).filter(Photo.product_id==pid).order_by(Photo.created_at.desc()).all()
    return shell('''<h1>📦 {{p.name}}</h1><div class="grid"><div><div class="panel"><h3>Ficha do equipamento</h3><p><b>Patrimônio:</b> {{p.code or '-'}}</p><p><b>Setor:</b> {{p.sector or '-'}}</p><p><b>Problema:</b> {{p.description or '-'}}</p><p><b>Status:</b> {% if services and services[0].status!='Finalizado' %}Em manutenção{% else %}Sem serviço / Disponível{% endif %}</p><p><b>Prioridade:</b> {{p.priority}}</p>{% if session.role in ['admin','chefe'] %}<form method="post" enctype="multipart/form-data" class="form"><div class="field"><label>NOME</label><input name="name" value="{{p.name}}" required></div><div class="field"><label>PATRIMÔNIO</label><input name="code" value="{{p.code}}"></div><div class="field"><label>SETOR</label><input name="sector" value="{{p.sector}}"></div><div class="field"><label>PRIORIDADE</label><select name="priority"><option {% if p.priority=='Normal' %}selected{% endif %}>Normal</option><option {% if p.priority=='Pouca urgência' %}selected{% endif %}>Pouca urgência</option><option {% if p.priority=='Urgente' %}selected{% endif %}>Urgente</option></select></div><div class="field fullcol"><label>DESCRIÇÃO</label><textarea name="description">{{p.description}}</textarea></div><div class="field fullcol"><label>📷 ADICIONAR FOTOS</label><input type="file" name="photos" accept="image/*" multiple></div><button class="btn green fullcol">Salvar produto</button></form>{% endif %}</div><br><div class="panel"><h3>📷 Fotos</h3><div class="photos">{% for ph in photos %}<a href="/fotos/{{ph.id}}"><img src="/fotos/{{ph.id}}"></a>{% else %}<p class="muted">Nenhuma foto.</p>{% endfor %}</div></div></div><div class="panel"><h3>🛠️ Histórico</h3>{% if session.role in ['admin','chefe'] %}<a class="btn green full" href="/servicos/novo?product_id={{p.id}}">Atribuir manutenção</a><br><br>{% endif %}{% for s in services %}<p><a class="btn full" href="/servicos/{{s.id}}">OS-{{'%05d'%s.id}} — {{priority_for(s)}} — {{s.status}}</a></p>{% else %}<p class="muted">Sem serviço registrado.</p>{% endfor %}</div></div>''',p=p,services=services,photos=photos,priority_for=priority_for)

@app.get('/fotos/<int:photo_id>')
@auth
def foto(photo_id):
    with db() as d:
        ph=d.get(Photo,photo_id)
        if not ph: abort(404)
        return send_file(io.BytesIO(ph.data),mimetype=ph.mime,download_name=ph.filename)

@app.route('/servicos/novo',methods=['GET','POST'])
@auth
@manager
def servico_novo():
    with db() as d:
        products=d.query(Product).order_by(Product.name).all();users=d.query(User).filter(User.active==True).order_by(User.name).all();selected=request.args.get('product_id')
        if request.method=='POST':
            pid=request.form.get('product_id') or None
            p=d.get(Product,int(pid)) if pid and pid.isdigit() else None
            if not p: flash('Sem serviço: selecione um produto já cadastrado.');return redirect('/servicos/novo')
            s=Service(product_id=p.id,client=request.form.get('client','').strip(),problem=request.form['problem'].strip(),priority=request.form.get('priority','Normal'),responsible_id=int(request.form['responsible_id']),created_by=session['uid']);d.add(s);d.commit();count=add_photos(d,request.files.getlist('photos'),service_id=s.id);log(d,'CRIAR_OS',f'OS-{s.id:05d} | {p.name} | {count} foto(s)');d.commit();flash('Manutenção enviada.');return redirect(f'/servicos/{s.id}')
    return shell('''<h1>🛠️ Enviar manutenção</h1>{% if products %}<div class="panel"><form method="post" enctype="multipart/form-data" class="form"><div class="field fullcol"><label>PRODUTO CADASTRADO</label><select name="product_id" required><option value="">Selecione um produto...</option>{% for p in products %}<option value="{{p.id}}" {% if selected==p.id|string %}selected{% endif %}>{{p.name}} — {{p.code or 'sem patrimônio'}} — {{p.sector or 'sem setor'}}</option>{% endfor %}</select></div><div class="field"><label>CLIENTE / SETOR</label><input name="client"></div><div class="field"><label>FUNCIONÁRIO RESPONSÁVEL</label><select name="responsible_id" required>{% for u in users %}<option value="{{u.id}}">{{u.name}} — {{roles[u.role]}}</option>{% endfor %}</select></div><div class="field"><label>PRIORIDADE</label><select name="priority"><option>Normal</option><option>Pouca urgência</option><option>Urgente</option></select></div><div class="field fullcol"><label>PROBLEMA / SERVIÇO</label><textarea name="problem" rows="5" required></textarea></div><div class="field fullcol"><label>📷 FOTOS DO PROBLEMA / EQUIPAMENTO</label><input type="file" name="photos" accept="image/*" multiple></div><button class="btn green fullcol">ENVIAR MANUTENÇÃO</button></form></div>{% else %}<div class="panel"><h2>Sem serviço</h2><p class="muted">Nenhum produto/equipamento foi cadastrado.</p><a class="btn green" href="/produtos">📦 Cadastrar produto primeiro</a></div>{% endif %}''',products=products,users=users,selected=selected)

@app.route('/servicos',methods=['GET'])
@auth
def servicos():
    with db() as d:
        q=d.query(Service)
        if session['role']=='funcionario': q=q.filter(Service.responsible_id==session['uid'])
        services=q.order_by(Service.created_at.desc()).all();users=d.query(User).filter(User.active==True).all();products=d.query(Product).order_by(Product.name).all()
    return shell('''<h1>Ordens de serviço</h1>{% if session.role in ['admin','chefe'] %}<a class="btn green" href="/servicos/novo">➕ Atribuir serviço</a><br><br>{% endif %}<div class="panel"><table class="table"><tr><th>OS</th><th>Produto</th><th>Prioridade</th><th>Status</th><th>Responsável</th><th>Ação</th></tr>{% for s in services %}<tr><td>OS-{{'%05d'%s.id}}</td><td>{% for p in products if p.id==s.product_id %}{{p.name}}{% else %}Sem produto{% endfor %}</td><td>{{priority_for(s)}}</td><td>{{s.status}}</td><td>{% for u in users if u.id==s.responsible_id %}{{u.name}}{% endfor %}</td><td><a class="btn" href="/servicos/{{s.id}}">Abrir</a></td></tr>{% else %}<tr><td colspan="6">Nenhum serviço atribuído.</td></tr>{% endfor %}</table></div>''',services=services,users=users,products=products,priority_for=priority_for)

@app.route('/servicos/<int:sid>',methods=['GET','POST'])
@auth
def servico_detalhe(sid):
    with db() as d:
        s=d.get(Service,sid)
        if not s: abort(404)
        if session['role']=='funcionario' and s.responsible_id!=session['uid']: abort(403)
        if request.method=='POST':
            action=request.form.get('action')
            now=datetime.utcnow()
            if action=='iniciar': s.status='Em andamento';s.started_at=now;log(d,'INICIAR_OS',f'OS-{s.id:05d}')
            elif action=='finalizar':
                s.status='Finalizado';s.finished_at=now;s.work_done=request.form.get('work_done','').strip();s.notes=request.form.get('notes','').strip();add_photos(d,request.files.getlist('photos'),service_id=s.id);log(d,'FINALIZAR_OS',f'OS-{s.id:05d} | {s.work_done} | {s.notes}')
            elif action=='prioridade' and session['role'] in ('admin','chefe'): s.priority=request.form.get('priority','Normal');log(d,'ALTERAR_PRIORIDADE_OS',f'OS-{s.id:05d} | {s.priority}')
            d.commit();flash('Ordem de serviço atualizada.');return redirect(f'/servicos/{sid}')
        p=d.get(Product,s.product_id) if s.product_id else None;u=d.get(User,s.responsible_id) if s.responsible_id else None;photos=d.query(Photo).filter(Photo.service_id==sid).order_by(Photo.created_at.desc()).all()
    return shell('''<h1>OS-{{'%05d'%s.id}}</h1><div class="grid"><div><div class="panel"><h3>Dados da manutenção</h3><p><b>Cliente:</b> {{s.client or '-'}}</p><p><b>Produto:</b> {{p.name if p else 'Sem produto'}}</p><p><b>Patrimônio:</b> {{p.code if p else '-'}}</p><p><b>Problema:</b> {{s.problem}}</p><p><b>Responsável:</b> {{u.name if u else '-'}}</p><p><b>Status:</b> {{s.status}}</p><p><b>Prioridade:</b> {{priority_for(s)}}</p><p><b>Início:</b> {{s.started_at.strftime('%d/%m/%Y %H:%M:%S') if s.started_at else '-'}}</p><p><b>Finalização:</b> {{s.finished_at.strftime('%d/%m/%Y %H:%M:%S') if s.finished_at else '-'}}</p></div>{% if s.status!='Finalizado' %}<div class="panel"><h3>Ações</h3>{% if not s.started_at %}<form method="post"><input type="hidden" name="action" value="iniciar"><button class="btn green">▶ Iniciar agora</button></form>{% endif %}{% if s.started_at %}<form method="post" enctype="multipart/form-data" class="form"><input type="hidden" name="action" value="finalizar"><div class="field fullcol"><label>O QUE FOI FEITO</label><textarea name="work_done" rows="5" required></textarea></div><div class="field fullcol"><label>OBSERVAÇÃO DA FINALIZAÇÃO</label><textarea name="notes" rows="4"></textarea></div><div class="field fullcol"><label>📷 FOTOS DA FINALIZAÇÃO</label><input type="file" name="photos" accept="image/*" multiple></div><button class="btn green fullcol">✓ Finalizar na hora atual</button></form>{% endif %}</div>{% endif %}{% if session.role in ['admin','chefe'] and s.status!='Finalizado' %}<div class="panel"><h3>Prioridade</h3><form method="post"><input type="hidden" name="action" value="prioridade"><select name="priority"><option {% if s.priority=='Normal' %}selected{% endif %}>Normal</option><option {% if s.priority=='Pouca urgência' %}selected{% endif %}>Pouca urgência</option><option {% if s.priority=='Urgente' %}selected{% endif %}>Urgente</option></select> <button class="btn">Salvar prioridade</button></form></div>{% endif %}<div class="panel"><h3>📷 Fotos</h3><div class="photos">{% for ph in photos %}<a href="/fotos/{{ph.id}}"><img src="/fotos/{{ph.id}}"></a>{% else %}<p class="muted">Nenhuma foto.</p>{% endfor %}</div></div></div><div class="panel"><h3>Resultado</h3><p><b>O que foi feito:</b><br>{{s.work_done or '-'}}</p><p><b>Observação da finalização:</b><br>{{s.notes or '-'}}</p></div></div>''',s=s,p=p,u=u,photos=photos,priority_for=priority_for)

@app.get('/relatorios')
@auth
def relatorios():
    with db() as d:
        q=d.query(Service)
        start=request.args.get('start');end=request.args.get('end');rid=request.args.get('responsible_id');status=request.args.get('status');priority=request.args.get('priority')
        if start: q=q.filter(Service.created_at>=datetime.fromisoformat(start))
        if end: q=q.filter(Service.created_at<datetime.fromisoformat(end)+timedelta(days=1))
        if rid and rid.isdigit(): q=q.filter(Service.responsible_id==int(rid))
        if status: q=q.filter(Service.status==status)
        if priority: q=q.filter(Service.priority==priority)
        if session['role']=='funcionario': q=q.filter(Service.responsible_id==session['uid'])
        services=q.order_by(Service.created_at.desc()).all();users=d.query(User).order_by(User.name).all();products=d.query(Product).order_by(Product.name).all()
    return shell('''<h1>Relatórios</h1><div class="panel"><form class="form"><div class="field"><label>INÍCIO</label><input type="date" name="start" value="{{request.args.get('start','')}}"></div><div class="field"><label>FIM</label><input type="date" name="end" value="{{request.args.get('end','')}}"></div>{% if session.role in ['admin','chefe'] %}<div class="field"><label>FUNCIONÁRIO</label><select name="responsible_id"><option value="">Todos</option>{% for u in users %}<option value="{{u.id}}">{{u.name}}</option>{% endfor %}</select></div>{% endif %}<div class="field"><label>STATUS</label><select name="status"><option value="">Todos</option><option>Pendente</option><option>Em andamento</option><option>Finalizado</option></select></div><div class="field"><label>PRIORIDADE</label><select name="priority"><option value="">Todas</option><option>Normal</option><option>Pouca urgência</option><option>Urgente</option></select></div><button class="btn green fullcol">Filtrar</button></form></div><br><div class="actions"><a class="btn green" href="{{url_for('relatorio_csv',**request.args)}}">⬇ CSV</a><a class="btn green" href="{{url_for('relatorio_xlsx',**request.args)}}">⬇ Excel</a><a class="btn" href="{{url_for('relatorio_pdf',**request.args)}}">⬇ PDF</a><button class="btn" onclick="window.print()">🖨 Imprimir</button></div><br><div class="panel"><table class="table"><tr><th>OS</th><th>Cliente</th><th>Produto</th><th>Responsável</th><th>Prioridade</th><th>O que foi feito</th><th>Observação</th><th>Início</th><th>Finalização</th><th>Status</th></tr>{% for s in services %}<tr><td>OS-{{'%05d'%s.id}}</td><td>{{s.client or '-'}}</td><td>{% for p in products if p.id==s.product_id %}{{p.name}}{% else %}-{% endfor %}</td><td>{% for u in users if u.id==s.responsible_id %}{{u.name}}{% else %}-{% endfor %}</td><td>{{priority_for(s)}}</td><td>{{s.work_done or '-'}}</td><td>{{s.notes or '-'}}</td><td>{{s.started_at.strftime('%d/%m/%Y %H:%M') if s.started_at else '-'}}</td><td>{{s.finished_at.strftime('%d/%m/%Y %H:%M') if s.finished_at else '-'}}</td><td>{{s.status}}</td></tr>{% else %}<tr><td colspan="10">Nenhum serviço.</td></tr>{% endfor %}</table></div>''',services=services,users=users,products=products,priority_for=priority_for)

def filtered_services():
    with db() as d:
        q=d.query(Service);start=request.args.get('start');end=request.args.get('end');rid=request.args.get('responsible_id');status=request.args.get('status');priority=request.args.get('priority')
        if start:q=q.filter(Service.created_at>=datetime.fromisoformat(start))
        if end:q=q.filter(Service.created_at<datetime.fromisoformat(end)+timedelta(days=1))
        if rid and rid.isdigit():q=q.filter(Service.responsible_id==int(rid))
        if status:q=q.filter(Service.status==status)
        if priority:q=q.filter(Service.priority==priority)
        if session['role']=='funcionario':q=q.filter(Service.responsible_id==session['uid'])
        return q.order_by(Service.created_at.desc()).all()
@app.get('/relatorios.csv')
@auth
def relatorio_csv():
    services=filtered_services();out=io.StringIO();w=csv.writer(out);w.writerow(['OS','Cliente','Produto','Responsável','Prioridade','O que foi feito','Observação','Início','Finalização','Status'])
    with db() as d:
        for s in services:
            p=d.get(Product,s.product_id) if s.product_id else None;u=d.get(User,s.responsible_id) if s.responsible_id else None;w.writerow([f'OS-{s.id:05d}',s.client,p.name if p else '-',u.name if u else '-',priority_for(s),s.work_done or '-',s.notes or '-',s.started_at.strftime('%d/%m/%Y %H:%M:%S') if s.started_at else '-',s.finished_at.strftime('%d/%m/%Y %H:%M:%S') if s.finished_at else '-',s.status])
    return send_file(io.BytesIO(out.getvalue().encode('utf-8-sig')),mimetype='text/csv',as_attachment=True,download_name='relatorio.csv')
@app.get('/relatorios.xlsx')
@auth
def relatorio_xlsx():
    services=filtered_services();wb=Workbook();ws=wb.active;ws.title='Relatório';ws.append(['OS','Cliente','Produto','Responsável','Prioridade','O que foi feito','Observação','Início','Finalização','Status'])
    with db() as d:
        for s in services:
            p=d.get(Product,s.product_id) if s.product_id else None;u=d.get(User,s.responsible_id) if s.responsible_id else None;ws.append([f'OS-{s.id:05d}',s.client,p.name if p else '-',u.name if u else '-',priority_for(s),s.work_done or '-',s.notes or '-',s.started_at.strftime('%d/%m/%Y %H:%M:%S') if s.started_at else '-',s.finished_at.strftime('%d/%m/%Y %H:%M:%S') if s.finished_at else '-',s.status])
    bio=io.BytesIO();wb.save(bio);bio.seek(0);return send_file(bio,mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',as_attachment=True,download_name='relatorio.xlsx')
@app.get('/relatorios.pdf')
@auth
def relatorio_pdf():
    services=filtered_services();bio=io.BytesIO();c=canvas.Canvas(bio,pagesize=A4);y=810;c.setFont('Helvetica-Bold',12);c.drawString(40,y,'Relatório de Manutenções');y-=24;c.setFont('Helvetica',8)
    with db() as d:
        for s in services:
            p=d.get(Product,s.product_id) if s.product_id else None;u=d.get(User,s.responsible_id) if s.responsible_id else None
            lines=[f'OS-{s.id:05d} | Cliente: {s.client or "-"}',f'Produto: {p.name if p else "-"} | Responsável: {u.name if u else "-"}',f'Prioridade: {priority_for(s)} | Status: {s.status}',f'O que foi feito: {s.work_done or "-"}',f'Observação: {s.notes or "-"}',f'Início: {s.started_at.strftime("%d/%m/%Y %H:%M:%S") if s.started_at else "-"} | Finalização: {s.finished_at.strftime("%d/%m/%Y %H:%M:%S") if s.finished_at else "-"}']
            for line in lines:
                if y<60:c.showPage();y=810;c.setFont('Helvetica',8)
                c.drawString(40,y,line[:125]);y-=12
            y-=8
    c.save();bio.seek(0);return send_file(bio,mimetype='application/pdf',as_attachment=True,download_name='relatorio.pdf')

@app.get('/historico')
@auth
def historico():
    with db() as d:
        q=d.query(Audit).order_by(Audit.created_at.desc())
        if session['role']=='funcionario': q=q.filter(Audit.user_id==session['uid'])
        rows=q.limit(300).all();users=d.query(User).all();by_id={u.id:u.name for u in users}
    return shell('''<h1>Histórico</h1><div class="panel"><table class="table"><tr><th>Data</th><th>Usuário</th><th>Ação</th><th>Detalhes</th></tr>{% for r in rows %}<tr><td>{{r.created_at.strftime('%d/%m/%Y %H:%M:%S')}}</td><td>{{by_id.get(r.user_id,'Sistema')}}</td><td>{{r.action}}</td><td>{{r.details}}</td></tr>{% endfor %}</table></div>''',rows=rows,by_id=by_id)
@app.route('/configuracoes',methods=['GET','POST'])
@auth
def configuracoes():
    if request.method=='POST':
        with db() as d:
            u=d.get(User,session['uid'])
            if not check_password_hash(u.password_hash,request.form['current_password']): flash('Senha atual incorreta.');return redirect('/configuracoes')
            if request.form['new_password']!=request.form['confirm_password']: flash('As senhas não coincidem.');return redirect('/configuracoes')
            if len(request.form['new_password'])<8: flash('A nova senha deve ter pelo menos 8 caracteres.');return redirect('/configuracoes')
            u.password_hash=generate_password_hash(request.form['new_password']);d.commit();log(d,'ALTERAR_SENHA',u.username);d.commit();flash('Senha alterada.');return redirect('/configuracoes')
    return shell('''<h1>Configurações</h1><div class="grid"><div class="panel"><h3>Minha conta</h3><p><b>Nome:</b> {{session.name}}</p><p><b>Login:</b> {{session.username}}</p><p><b>Cargo:</b> {{roles[session.role]}}</p></div><div class="panel"><h3>Alterar senha</h3><form method="post"><div class="field"><label>SENHA ATUAL</label><input type="password" name="current_password" required></div><div class="field"><label>NOVA SENHA</label><input type="password" name="new_password" minlength="8" required></div><div class="field"><label>CONFIRMAR NOVA SENHA</label><input type="password" name="confirm_password" minlength="8" required></div><button class="btn green full">Alterar senha</button></form></div></div><br><div class="panel"><h3>Cargos</h3><p>👑 <b>Administrador:</b> acesso total e define os cargos.</p><p>🧑‍💼 <b>Chefe:</b> gerencia equipe e pode atribuir manutenções.</p><p>👷 <b>Funcionário:</b> vê e executa somente os trabalhos atribuídos a ele.</p></div>''',roles=ROLES)

@app.get('/health')
def health():
    try:
        with db() as d:return {'ok':True,'database':'connected','users':d.query(User).count(),'services':d.query(Service).count(),'products':d.query(Product).count()}
    except Exception as e:return {'ok':False,'error':str(e)},500

if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.getenv('PORT','5000')))
