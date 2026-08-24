import os, secrets
from datetime import datetime
from functools import wraps
from flask import Flask, request, redirect, session, render_template_string, flash, abort
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
    __tablename__='users'; id:Mapped[int]=mapped_column(primary_key=True); name:Mapped[str]=mapped_column(String(120)); username:Mapped[str]=mapped_column(String(80),unique=True,index=True); password_hash:Mapped[str]=mapped_column(String(255)); role:Mapped[str]=mapped_column(String(20),default='funcionario'); active:Mapped[bool]=mapped_column(Boolean,default=True); failed:Mapped[int]=mapped_column(Integer,default=0); locked_until:Mapped[datetime|None]=mapped_column(DateTime,nullable=True); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.now)
Base.metadata.create_all(engine)
app=Flask(__name__); app.secret_key=os.getenv('SECRET_KEY',secrets.token_hex(32))
ROLES={'admin':'Administrador','chefe':'Chefe','funcionario':'Funcionário'}

def count_users():
    with Session() as db: return db.query(User).count()
def auth(f):
    @wraps(f)
    def w(*a,**k): return f(*a,**k) if session.get('uid') else redirect('/login')
    return w
def manager(f):
    @wraps(f)
    def w(*a,**k): return f(*a,**k) if session.get('role') in ('admin','chefe') else abort(403)
    return w

STYLE='''<style>*{box-sizing:border-box}body{margin:0;background:#071007;color:#eef7ed;font-family:Inter,Arial,sans-serif}.app{display:flex;min-height:100vh}.side{width:245px;background:#0b160b;border-right:1px solid #203821;padding:22px 14px;position:fixed;inset:0 auto 0 0}.brand{font-size:27px;font-weight:900;color:#ffd500;padding:10px 14px}.brand small{display:block;color:#73ff3e;font-size:8px;letter-spacing:2px;margin-top:4px}.nav{margin-top:25px}.nav a{display:block;color:#b8c5b6;text-decoration:none;padding:13px 14px;border-radius:10px;margin:4px 0}.nav a:hover,.nav a.active{background:#182719;color:#fff}.main{margin-left:245px;flex:1}.top{height:72px;border-bottom:1px solid #203821;display:flex;align-items:center;justify-content:flex-end;padding:0 28px;gap:18px}.user{font-weight:700}.content{padding:28px;max-width:1400px;margin:auto}.title{font-size:28px;margin:0 0 6px}.muted{color:#8fa08d}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:24px 0}.card{background:#0d1a0d;border:1px solid #213c22;border-radius:16px;padding:20px}.num{font-size:31px;font-weight:900}.label{color:#9eac9b;font-size:13px;margin-top:5px}.grid{display:grid;grid-template-columns:2fr 1fr;gap:18px}.panel{background:#0d1a0d;border:1px solid #213c22;border-radius:16px;padding:20px}.btn{display:inline-block;border:0;border-radius:10px;padding:11px 15px;background:#ffd500;color:#151b0b;font-weight:800;text-decoration:none;cursor:pointer}.btn.green{background:#74ff35}.table{width:100%;border-collapse:collapse}.table th,.table td{padding:13px 10px;text-align:left;border-bottom:1px solid #213521}.badge{display:inline-block;padding:5px 9px;border-radius:99px;background:#203820;font-size:11px}.actions{display:flex;gap:8px;flex-wrap:wrap}.form{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}.field label{display:block;font-size:11px;color:#9fac9b;margin-bottom:6px}.field input,.field select,.field textarea{width:100%;padding:12px;border:1px solid #29452a;border-radius:9px;background:#081308;color:#fff}.field.full{grid-column:1/-1}.form button{grid-column:1/-1}.login{min-height:100vh;display:grid;place-items:center}.loginbox{width:min(440px,92vw);padding:35px;border:1px solid #3e7131;border-radius:24px;background:#071107;box-shadow:0 0 70px #54ff0022}.logo{text-align:center;font-size:42px;font-weight:900;color:#ffd500}.sub{text-align:center;color:#65ff20;letter-spacing:3px;font-size:10px;margin:5px 0 25px}.flash{background:#4b2020;padding:10px;border-radius:9px}.link{display:block;text-align:center;margin-top:18px;color:#8cff65;text-decoration:none}@media(max-width:900px){.side{width:72px}.brand{font-size:0}.brand:before{content:'S';font-size:28px}.brand small{display:none}.nav span{display:none}.main{margin-left:72px}.cards{grid-template-columns:repeat(2,1fr)}.grid{grid-template-columns:1fr}.form{grid-template-columns:1fr}}'''

def shell(content):
    return render_template_string('<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sakamoto | Manutenção</title>'+STYLE+'</head><body><div class="app"><aside class="side"><div class="brand">SAKAMOTO<small>VARIEDADES E TECNOLOGIA</small></div><nav class="nav"><a href="/dashboard">📊 <span>Dashboard</span></a><a href="/servicos">🛠️ <span>Ordens de serviço</span></a><a href="/produtos">📦 <span>Produtos</span></a>{% if session.role in ["admin","chefe"] %}<a href="/usuarios">👥 <span>Usuários</span></a>{% endif %}<a href="/relatorios">📄 <span>Relatórios</span></a><a href="/historico">🕘 <span>Histórico</span></a><a href="/configuracoes">⚙️ <span>Configurações</span></a></nav></aside><main class="main"><header class="top"><span>🔔 Notificações</span><span class="user">{{session.name}}</span><a href="/logout" class="btn">Sair</a></header><section class="content">'+content+'</section></main></div></body></html>')

def login_page(setup=False):
    body='''<div class="login"><div class="loginbox"><div class="logo">SAKAMOTO</div><div class="sub">VARIEDADES E TECNOLOGIA</div>{% for m in get_flashed_messages() %}<p class="flash">{{m}}</p>{% endfor %}'''
    if setup: body+='''<h2>Crie sua conta de Administrador</h2><p class="muted">Essa será a conta principal do sistema.</p><form method="post" action="/criar-conta"><div class="field"><label>NOME</label><input name="name" required></div><div class="field"><label>USUÁRIO</label><input name="username" required></div><div class="field"><label>SENHA</label><input type="password" name="password" minlength="8" required></div><div class="field"><label>CONFIRMAR SENHA</label><input type="password" name="confirm" minlength="8" required></div><br><button class="btn green" style="width:100%">CRIAR CONTA ADMINISTRADOR</button></form>'''
    else: body+='''<h2>Acesso ao sistema</h2><form method="post"><div class="field"><label>USUÁRIO</label><input name="username" autocomplete="username" required></div><br><div class="field"><label>SENHA</label><input type="password" name="password" autocomplete="current-password" required></div><br><button class="btn green" style="width:100%">ENTRAR</button></form><a class="link" href="/criar-conta">➕ Criar conta</a>'''
    body+='</div></div>'
    return render_template_string('<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sakamoto</title>'+STYLE+'</head><body>'+body+'</body></html>')

@app.route('/')
def index(): return redirect('/login')
@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        with Session() as db:
            u=db.query(User).filter(func.lower(User.username)==request.form.get('username','').strip().lower()).first()
            if not u or not u.active or not check_password_hash(u.password_hash,request.form.get('password','')): flash('Usuário ou senha inválidos.'); return login_page()
            session.update(uid=u.id,name=u.name,username=u.username,role=u.role)
        return redirect('/dashboard')
    return login_page()
@app.route('/criar-conta',methods=['GET','POST'])
def criar_conta():
    if count_users()>0: flash('A conta inicial já foi criada. Novos usuários devem ser cadastrados pelo Administrador.'); return redirect('/login')
    if request.method=='POST':
        if request.form['password']!=request.form['confirm']: flash('As senhas não coincidem.'); return login_page(True)
        with Session() as db:
            u=User(name=request.form['name'].strip(),username=request.form['username'].strip().lower(),password_hash=generate_password_hash(request.form['password']),role='admin'); db.add(u); db.commit(); session.update(uid=u.id,name=u.name,username=u.username,role='admin')
        return redirect('/dashboard')
    return login_page(True)
@app.route('/dashboard')
@auth
def dashboard():
    with Session() as db:
        total=db.query(User).count(); ativos=db.query(User).filter(User.active==True).count()
    return shell('''<h1 class="title">Dashboard</h1><p class="muted">Visão geral do Sistema Sakamoto</p><div class="cards"><div class="card"><div class="num">0</div><div class="label">Produtos aguardando</div></div><div class="card"><div class="num">0</div><div class="label">Em manutenção</div></div><div class="card"><div class="num">0</div><div class="label">Finalizados</div></div><div class="card"><div class="num">0</div><div class="label">Urgentes</div></div></div><div class="grid"><div class="panel"><h3>📈 Atividade</h3><p class="muted">Os indicadores de serviços aparecerão aqui conforme as ordens forem cadastradas.</p></div><div class="panel"><h3>👥 Equipe</h3><div class="num">{{total}}</div><div class="label">Usuários cadastrados · {{ativos}} ativos</div><br><a class="btn" href="/usuarios">Gerenciar usuários</a></div></div>''',total=total,ativos=ativos)
@app.route('/usuarios')
@auth
@manager
def usuarios():
    with Session() as db: users=db.query(User).order_by(User.name).all()
    return shell('''<h1 class="title">Usuários</h1><p class="muted">Cadastre pessoas e defina o cargo. Somente o Administrador pode criar outro Administrador.</p><div class="panel"><form class="form" method="post" action="/usuarios/criar"><div class="field"><label>NOME COMPLETO</label><input name="name" required></div><div class="field"><label>LOGIN</label><input name="username" required></div><div class="field"><label>SENHA INICIAL</label><input name="password" type="password" minlength="8" required></div><div class="field"><label>CARGO</label><select name="role"><option value="funcionario">Funcionário</option><option value="chefe">Chefe</option>{% if session.role=='admin' %}<option value="admin">Administrador</option>{% endif %}</select></div><button class="btn green">➕ Criar usuário</button></form></div><br><div class="panel"><table class="table"><tr><th>Nome</th><th>Login</th><th>Cargo</th><th>Status</th></tr>{% for u in users %}<tr><td>{{u.name}}</td><td>{{u.username}}</td><td><span class="badge">{{roles[u.role]}}</span></td><td>{{'Ativo' if u.active else 'Inativo'}}</td></tr>{% endfor %}</table></div>''',users=users,roles=ROLES)
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
@app.route('/servicos')
@auth
def servicos(): return shell('''<h1 class="title">Ordens de serviço</h1><p class="muted">Controle de produtos, consertos, responsáveis e prazos.</p><div class="panel"><div class="actions"><a class="btn green" href="/servicos/novo">➕ Atribuir serviço</a><span class="badge">Normal</span><span class="badge">Pouca urgência</span><span class="badge">Urgente</span></div><br><p class="muted">Nenhuma ordem cadastrada ainda.</p></div>''')
@app.route('/servicos/novo')
@auth
@manager
def novo_servico(): return shell('''<h1 class="title">➕ Atribuir serviço</h1><div class="panel"><form class="form"><div class="field"><label>PRODUTO</label><input placeholder="Nome do produto"></div><div class="field"><label>CLIENTE / SETOR</label><input></div><div class="field full"><label>PROBLEMA / SERVIÇO</label><textarea rows="4"></textarea></div><div class="field"><label>RESPONSÁVEL</label><select><option>Selecione o usuário</option></select></div><div class="field"><label>PRIORIDADE</label><select><option>Normal</option><option>Pouca urgência</option><option>Urgente</option></select></div><button class="btn green">ATRIBUIR SERVIÇO</button></form></div>''')
@app.route('/produtos')
@auth
def produtos(): return shell('<h1 class="title">Produtos</h1><div class="panel"><p class="muted">Cadastro e acompanhamento dos produtos em manutenção.</p></div>')
@app.route('/relatorios')
@auth
def relatorios(): return shell('<h1 class="title">Relatórios</h1><div class="panel"><p>Filtros por funcionário, período, status e prioridade.</p><p class="muted">PDF, Excel/CSV e impressão serão disponibilizados conforme as ordens forem cadastradas.</p></div>')
@app.route('/historico')
@auth
def historico(): return shell('<h1 class="title">Histórico</h1><div class="panel"><p class="muted">Registro de criação, atribuição, início, alterações e finalização.</p></div>')
@app.route('/configuracoes')
@auth
def configuracoes(): return shell('''<h1 class="title">Configurações</h1><div class="grid"><div class="panel"><h3>👤 Minha conta</h3><p><b>Nome:</b> {{session.name}}</p><p><b>Login:</b> {{session.username}}</p><p><b>Cargo:</b> {{ROLES[session.role]}}</p></div><div class="panel"><h3>🔐 Segurança</h3><p class="muted">Senhas são armazenadas protegidas por hash e nunca são exibidas.</p></div></div><br><div class="panel"><h3>Permissões</h3><p>👑 Administrador — acesso total e define cargos.</p><p>🧑‍💼 Chefe — gerencia equipe e pode atribuir serviços.</p><p>👷 Funcionário — executa serviços atribuídos a ele.</p></div>''',ROLES=ROLES)
@app.route('/logout')
def logout(): session.clear(); return redirect('/login')
@app.errorhandler(403)
def forbidden(e): return shell('<h1>Acesso negado</h1><p>Você não tem permissão para esta área.</p>'),403
if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.getenv('PORT',5000)),debug=False)