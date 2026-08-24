import os, secrets, csv, io
from datetime import datetime
from functools import wraps
from flask import Flask, request, redirect, session, render_template_string, flash, abort, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import create_engine, String, Integer, DateTime, Boolean, Text, ForeignKey, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///sakamoto.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

class Base(DeclarativeBase): pass
class User(Base):
    __tablename__="users"
    id:Mapped[int]=mapped_column(primary_key=True)
    name:Mapped[str]=mapped_column(String(120))
    username:Mapped[str]=mapped_column(String(80),unique=True,index=True)
    password_hash:Mapped[str]=mapped_column(String(255))
    role:Mapped[str]=mapped_column(String(20),default="funcionario")
    active:Mapped[bool]=mapped_column(Boolean,default=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class Product(Base):
    __tablename__="products"
    id:Mapped[int]=mapped_column(primary_key=True)
    name:Mapped[str]=mapped_column(String(160))
    code:Mapped[str]=mapped_column(String(80),default="")
    sector:Mapped[str]=mapped_column(String(160),default="")
    description:Mapped[str]=mapped_column(Text,default="")
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class Service(Base):
    __tablename__="services"
    id:Mapped[int]=mapped_column(primary_key=True)
    product:Mapped[str]=mapped_column(String(160))
    client:Mapped[str]=mapped_column(String(160),default="")
    problem:Mapped[str]=mapped_column(Text,default="")
    priority:Mapped[str]=mapped_column(String(30),default="Normal")
    status:Mapped[str]=mapped_column(String(30),default="Pendente")
    responsible_id:Mapped[int|None]=mapped_column(ForeignKey("users.id"),nullable=True)
    created_by:Mapped[int]=mapped_column(ForeignKey("users.id"))
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    started_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    finished_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    notes:Mapped[str]=mapped_column(Text,default="")
class Audit(Base):
    __tablename__="audit"
    id:Mapped[int]=mapped_column(primary_key=True)
    user_id:Mapped[int|None]=mapped_column(ForeignKey("users.id"),nullable=True)
    action:Mapped[str]=mapped_column(String(120))
    details:Mapped[str]=mapped_column(Text,default="")
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

app=Flask(__name__)
app.secret_key=os.getenv("SECRET_KEY") or secrets.token_hex(32)
ROLES={"admin":"Administrador","chefe":"Chefe","funcionario":"Funcionário"}

def init_db(): Base.metadata.create_all(engine)
@app.before_request
def ensure_db():
    try: init_db()
    except Exception: pass
def db(): return SessionLocal()
def log(d,action,details=""): d.add(Audit(user_id=session.get("uid"),action=action,details=details))
def auth(fn):
    @wraps(fn)
    def w(*a,**k): return fn(*a,**k) if session.get("uid") else redirect("/login")
    return w
def manager(fn):
    @wraps(fn)
    def w(*a,**k): return fn(*a,**k) if session.get("role") in ("admin","chefe") else abort(403)
    return w

STYLE="""<style>
*{box-sizing:border-box}body{margin:0;background:#061006;color:#eef7ed;font-family:Inter,Arial,sans-serif}.login{min-height:100vh;display:grid;place-items:center;padding:24px;background:radial-gradient(circle at 50% 10%,#123d14,#061006 55%)}.box{width:min(460px,94vw);padding:34px;border:1px solid #20e84a;border-radius:24px;background:#071307ee;box-shadow:0 20px 80px #0008}.logo{text-align:center;font-size:42px;font-weight:950;color:#fff}.logo b,.brand b{color:#53ff20}.sub{text-align:center;color:#69ff36;font-size:11px;letter-spacing:3px;margin:6px 0 28px}.field{margin:12px 0}.field label{display:block;font-size:11px;color:#9eae9a;margin-bottom:7px}input,select,textarea{width:100%;padding:13px;border:1px solid #315936;border-radius:10px;background:#081408;color:#fff}.btn{display:inline-block;border:0;border-radius:10px;padding:12px 17px;background:#ffd21a;color:#111;font-weight:900;text-decoration:none;cursor:pointer}.green{background:#35ed24}.full{width:100%}.link{display:block;text-align:center;margin-top:17px;color:#72ff4b;text-decoration:none}.flash{background:#542323;padding:11px;border-radius:9px}.app{display:flex;min-height:100vh}.side{width:245px;background:#0a150a;border-right:1px solid #1e351f;padding:20px 13px;position:fixed;inset:0 auto 0 0}.brand{padding:10px 14px;font-size:27px;font-weight:950;color:#fff}.brand small{display:block;color:#68ff3a;font-size:8px;letter-spacing:2px}.nav{margin-top:22px}.nav a{display:block;padding:13px 14px;margin:4px 0;color:#b7c4b5;text-decoration:none;border-radius:10px}.nav a:hover{background:#172619;color:#fff}.main{margin-left:245px;flex:1}.top{height:72px;border-bottom:1px solid #1d331e;display:flex;justify-content:flex-end;align-items:center;gap:18px;padding:0 28px}.content{padding:28px;max-width:1450px;margin:auto}.muted{color:#8e9f8c}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:24px 0}.card,.panel{background:#0c190c;border:1px solid #203b21;border-radius:16px;padding:20px}.num{font-size:31px;font-weight:900}.label{font-size:13px;color:#99a996;margin-top:5px}.grid{display:grid;grid-template-columns:2fr 1fr;gap:18px}.form{display:grid;grid-template-columns:1fr 1fr;gap:14px}.fullcol{grid-column:1/-1}.table{width:100%;border-collapse:collapse}.table th,.table td{padding:12px;border-bottom:1px solid #203620;text-align:left}.badge{display:inline-block;padding:5px 9px;border-radius:99px;background:#1d381e;font-size:11px}.actions{display:flex;gap:8px;flex-wrap:wrap}@media(max-width:850px){.side{width:72px}.brand{font-size:0}.brand:before{content:'S';font-size:28px}.brand small,.nav span{display:none}.main{margin-left:72px}.cards{grid-template-columns:1fr 1fr}.grid,.form{grid-template-columns:1fr}}
</style>"""

def login_html(create=False):
    extra=("""<h2>Crie sua conta</h2><p class="muted">A primeira conta recebe automaticamente o cargo de Administrador.</p><form method="post" action="/criar-conta"><div class="field"><label>NOME</label><input name="name" required></div><div class="field"><label>USUÁRIO</label><input name="username" required></div><div class="field"><label>SENHA</label><input type="password" name="password" minlength="8" required></div><div class="field"><label>CONFIRMAR SENHA</label><input type="password" name="confirm" minlength="8" required></div><button class="btn green full">CRIAR CONTA ADMINISTRADOR</button></form><a class="link" href="/login">Voltar ao login</a>""" if create else """<h2>Login</h2><form method="post"><div class="field"><label>USUÁRIO</label><input name="username" required></div><div class="field"><label>SENHA</label><input type="password" name="password" required></div><button class="btn green full">ENTRAR</button></form><a class="link" href="/criar-conta">➕ Criar conta</a>""")
    return render_template_string(f'''<!doctype html><html lang="pt-br"><head><meta charset="utf-8">{STYLE}</head><body><div class="login"><div class="box"><div class="logo"><b>SAKA</b>MOTO</div><div class="sub">SISTEMA DE CONTROLE E RELATÓRIOS</div>{{% for m in get_flashed_messages() %}}<p class="flash">{{{{m}}}}</p>{{% endfor %}}{extra}</div></div></body></html>''')

def shell(content,**ctx):
    return render_template_string(f'''<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><title>Sakamoto | Manutenção</title>{STYLE}</head><body><div class="app"><aside class="side"><div class="brand"><b>SAKA</b>MOTO<small>VARIEDADES E TECNOLOGIA</small></div><nav class="nav"><a href="/dashboard">📊 <span>Dashboard</span></a><a href="/servicos">🛠️ <span>Ordens de serviço</span></a><a href="/produtos">📦 <span>Produtos</span></a>{{% if session.role in ['admin','chefe'] %}}<a href="/usuarios">👥 <span>Usuários</span></a>{{% endif %}}<a href="/relatorios">📄 <span>Relatórios</span></a><a href="/historico">🕘 <span>Histórico</span></a><a href="/configuracoes">⚙️ <span>Configurações</span></a></nav></aside><main class="main"><header class="top"><span>🔔 Notificações</span><b>{{{{session.name}}}}</b><a class="btn" href="/logout">Sair</a></header><section class="content">{content}</section></main></div></body></html>''',**ctx)

@app.get("/")
def index(): return redirect("/login")
@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        try:
            with db() as d:
                u=d.query(User).filter(func.lower(User.username)==request.form.get("username","").strip().lower()).first()
                if not u or not u.active or not check_password_hash(u.password_hash,request.form.get("password","")): flash("Usuário ou senha inválidos.");return login_html()
                session.update(uid=u.id,name=u.name,username=u.username,role=u.role);log(d,"LOGIN",u.username);d.commit()
            return redirect("/dashboard")
        except Exception: flash("Banco de dados indisponível.");return login_html()
    return login_html()
@app.route("/criar-conta",methods=["GET","POST"])
def criar_conta():
    try:
        with db() as d:
            if d.query(User).count()>0: flash("A conta inicial já foi criada. Use o painel de Usuários.");return redirect("/login")
            if request.method=="POST":
                if request.form["password"]!=request.form["confirm"]: flash("As senhas não coincidem.");return login_html(True)
                u=User(name=request.form["name"].strip(),username=request.form["username"].strip().lower(),password_hash=generate_password_hash(request.form["password"]),role="admin")
                d.add(u);d.commit();session.update(uid=u.id,name=u.name,username=u.username,role="admin");log(d,"CRIAR_ADMIN_INICIAL",u.username);d.commit();return redirect("/dashboard")
    except Exception: flash("Não foi possível acessar o banco de dados.")
    return login_html(True)
@app.get("/logout")
def logout(): session.clear();return redirect("/login")

@app.get("/dashboard")
@auth
def dashboard():
    with db() as d:
        total=d.query(Service).count();pending=d.query(Service).filter(Service.status=="Pendente").count();active=d.query(Service).filter(Service.status=="Em andamento").count();finished=d.query(Service).filter(Service.status=="Finalizado").count();urgent=d.query(Service).filter(Service.priority=="Urgente").count();users=d.query(User).count()
    return shell('''<h1>Dashboard</h1><p class="muted">Visão geral do Sistema Sakamoto</p><div class="cards"><div class="card"><div class="num">{{pending}}</div><div class="label">Aguardando</div></div><div class="card"><div class="num">{{active}}</div><div class="label">Em manutenção</div></div><div class="card"><div class="num">{{finished}}</div><div class="label">Finalizados</div></div><div class="card"><div class="num">{{urgent}}</div><div class="label">Urgentes</div></div></div><div class="grid"><div class="panel"><h3>📈 Atividade</h3><p class="muted">Serviços atualizados quando iniciados e finalizados.</p></div><div class="panel"><h3>👥 Equipe</h3><div class="num">{{users}}</div><div class="label">Usuários cadastrados</div></div></div>''',pending=pending,active=active,finished=finished,urgent=urgent,users=users)

@app.get("/usuarios")
@auth
@manager
def usuarios():
    with db() as d: users=d.query(User).order_by(User.name).all()
    return shell('''<h1>Usuários</h1><div class="panel"><form class="form" method="post" action="/usuarios/criar"><div class="field"><label>NOME</label><input name="name" required></div><div class="field"><label>LOGIN</label><input name="username" required></div><div class="field"><label>SENHA INICIAL</label><input name="password" type="password" minlength="8" required></div><div class="field"><label>CARGO</label><select name="role"><option value="funcionario">Funcionário</option><option value="chefe">Chefe</option>{% if session.role=='admin' %}<option value="admin">Administrador</option>{% endif %}</select></div><button class="btn green fullcol">➕ Criar usuário</button></form></div><br><div class="panel"><table class="table"><tr><th>Nome</th><th>Login</th><th>Cargo</th><th>Status</th></tr>{% for u in users %}<tr><td>{{u.name}}</td><td>{{u.username}}</td><td>{{roles[u.role]}}</td><td>{{'Ativo' if u.active else 'Inativo'}}</td></tr>{% endfor %}</table></div>''',users=users,roles=ROLES)
@app.post("/usuarios/criar")
@auth
@manager
def criar_usuario():
    role=request.form.get("role","funcionario")
    if session["role"]=="chefe" and role=="admin": abort(403)
    with db() as d:
        if d.query(User).filter(func.lower(User.username)==request.form["username"].strip().lower()).first(): flash("Esse login já existe.");return redirect("/usuarios")
        d.add(User(name=request.form["name"].strip(),username=request.form["username"].strip().lower(),password_hash=generate_password_hash(request.form["password"]),role=role));d.commit()
    flash("Usuário criado.");return redirect("/usuarios")

@app.route("/produtos",methods=["GET","POST"])
@auth
def produtos():
    with db() as d:
        if request.method=="POST":
            if session["role"] not in ("admin","chefe"): abort(403)
            p=Product(name=request.form["name"].strip(),code=request.form.get("code","").strip(),sector=request.form.get("sector","").strip(),description=request.form.get("description","").strip());d.add(p);d.commit();log(d,"CADASTRAR_PRODUTO",p.name);d.commit();flash("Produto cadastrado.");return redirect("/produtos")
        products=d.query(Product).order_by(Product.created_at.desc()).all()
    return shell('''<h1>Produtos</h1>{% if session.role in ['admin','chefe'] %}<div class="panel"><h3>➕ Cadastrar produto</h3><form class="form" method="post"><div class="field"><label>NOME DO PRODUTO</label><input name="name" required></div><div class="field"><label>CÓDIGO / PATRIMÔNIO</label><input name="code"></div><div class="field"><label>CLIENTE / SETOR</label><input name="sector"></div><div class="field fullcol"><label>DESCRIÇÃO</label><textarea name="description" rows="3"></textarea></div><button class="btn green fullcol">CADASTRAR PRODUTO</button></form></div><br>{% endif %}<div class="panel"><table class="table"><tr><th>Produto</th><th>Código</th><th>Setor</th><th>Cadastrado</th></tr>{% for p in products %}<tr><td>{{p.name}}</td><td>{{p.code}}</td><td>{{p.sector}}</td><td>{{p.created_at.strftime('%d/%m/%Y %H:%M')}}</td></tr>{% else %}<tr><td colspan="4">Nenhum produto cadastrado.</td></tr>{% endfor %}</table></div>''',products=products)

@app.get("/servicos")
@auth
def servicos():
    with db() as d:
        q=d.query(Service)
        if session["role"]=="funcionario": q=q.filter(Service.responsible_id==session["uid"])
        services=q.order_by(Service.created_at.desc()).all();users=d.query(User).filter(User.active==True).all()
    return shell('''<h1>Ordens de serviço</h1>{% if session.role in ['admin','chefe'] %}<a class="btn green" href="/servicos/novo">➕ Atribuir serviço</a><br><br>{% endif %}<div class="panel"><table class="table"><tr><th>OS</th><th>Produto</th><th>Prioridade</th><th>Status</th><th>Responsável</th><th>Ação</th></tr>{% for s in services %}<tr><td>OS-{{'%05d'%s.id}}</td><td>{{s.product}}</td><td>{{s.priority}}</td><td>{{s.status}}</td><td>{% for u in users if u.id==s.responsible_id %}{{u.name}}{% endfor %}</td><td><a class="btn" href="/servicos/{{s.id}}">Abrir</a></td></tr>{% else %}<tr><td colspan="6">Nenhum serviço atribuído.</td></tr>{% endfor %}</table></div>''',services=services,users=users)
@app.route("/servicos/novo",methods=["GET","POST"])
@auth
@manager
def novo_servico():
    with db() as d:
        users=d.query(User).filter(User.active==True).order_by(User.name).all()
        if request.method=="POST":
            s=Service(product=request.form["product"].strip(),client=request.form.get("client","").strip(),problem=request.form.get("problem","").strip(),priority=request.form.get("priority","Normal"),responsible_id=int(request.form["responsible_id"]),created_by=session["uid"]);d.add(s);d.commit();log(d,"ATRIBUIR_SERVICO",f"OS-{s.id} para usuário {s.responsible_id}");d.commit();flash("Serviço atribuído.");return redirect("/servicos")
    return shell('''<h1>➕ Atribuir serviço</h1><div class="panel"><form class="form" method="post"><div class="field"><label>PRODUTO</label><input name="product" required></div><div class="field"><label>CLIENTE / SETOR</label><input name="client"></div><div class="field fullcol"><label>PROBLEMA / SERVIÇO</label><textarea name="problem" rows="4"></textarea></div><div class="field"><label>RESPONSÁVEL</label><select name="responsible_id" required>{% for u in users %}<option value="{{u.id}}">{{u.name}} — {{roles[u.role]}}</option>{% endfor %}</select></div><div class="field"><label>PRIORIDADE</label><select name="priority"><option>Normal</option><option>Pouca urgência</option><option>Urgente</option></select></div><button class="btn green fullcol">ATRIBUIR SERVIÇO</button></form></div>''',users=users,roles=ROLES)
@app.route("/servicos/<int:sid>",methods=["GET","POST"])
@auth
def servico_detalhe(sid):
    with db() as d:
        s=d.get(Service,sid)
        if not s: abort(404)
        if session["role"]=="funcionario" and s.responsible_id!=session["uid"]: abort(403)
        if request.method=="POST":
            action=request.form.get("action")
            if action=="start" and s.started_at is None: s.started_at=datetime.utcnow();s.status="Em andamento";log(d,"INICIAR_SERVICO",f"OS-{s.id}")
            elif action=="finish": s.finished_at=datetime.utcnow();s.status="Finalizado";s.notes=request.form.get("notes","");log(d,"FINALIZAR_SERVICO",f"OS-{s.id}")
            d.commit();flash("Serviço atualizado.");return redirect(f"/servicos/{sid}")
    return shell('''<h1>OS-{{'%05d'%s.id}} — {{s.product}}</h1><div class="grid"><div class="panel"><p><b>Cliente/Setor:</b> {{s.client}}</p><p><b>Problema:</b> {{s.problem or 'Não informado'}}</p><p><b>Prioridade:</b> {{s.priority}}</p><p><b>Status:</b> {{s.status}}</p><p><b>Entrada:</b> {{s.created_at.strftime('%d/%m/%Y %H:%M')}}</p><p><b>Início:</b> {{s.started_at.strftime('%d/%m/%Y %H:%M') if s.started_at else 'Ainda não iniciado'}}</p><p><b>Finalização:</b> {{s.finished_at.strftime('%d/%m/%Y %H:%M') if s.finished_at else 'Ainda não finalizado'}}</p></div><div class="panel"><h3>Ações</h3>{% if not s.started_at %}<form method="post"><input type="hidden" name="action" value="start"><button class="btn green full">▶ Iniciar serviço</button></form>{% endif %}{% if s.status!='Finalizado' %}<form method="post"><div class="field"><label>OBSERVAÇÕES FINAIS</label><textarea name="notes" rows="5"></textarea></div><input type="hidden" name="action" value="finish"><button class="btn full">✓ Finalizar serviço</button></form>{% endif %}</div></div>''',s=s)

@app.get("/relatorios")
@auth
def relatorios():
    with db() as d:
        q=d.query(Service)
        if session["role"]=="funcionario": q=q.filter(Service.responsible_id==session["uid"])
        services=q.order_by(Service.created_at.desc()).all();users=d.query(User).all()
    return shell('''<h1>Relatórios</h1><p class="muted">Relatórios somente dos serviços que você pode visualizar.</p><div class="actions"><a class="btn green" href="/relatorios/csv">⬇ Baixar CSV</a><a class="btn" href="/relatorios/pdf">⬇ Baixar PDF</a><button class="btn" onclick="window.print()">🖨 Imprimir</button></div><br><div class="panel"><table class="table"><tr><th>OS</th><th>Produto</th><th>Responsável</th><th>Início</th><th>Finalização</th><th>Status</th></tr>{% for s in services %}<tr><td>OS-{{'%05d'%s.id}}</td><td>{{s.product}}</td><td>{% for u in users if u.id==s.responsible_id %}{{u.name}}{% endfor %}</td><td>{{s.started_at.strftime('%d/%m/%Y %H:%M') if s.started_at else '-'}}</td><td>{{s.finished_at.strftime('%d/%m/%Y %H:%M') if s.finished_at else '-'}}</td><td>{{s.status}}</td></tr>{% else %}<tr><td colspan="6">Nenhum serviço para relatório.</td></tr>{% endfor %}</table></div>''',services=services,users=users)

def scoped_services(d):
    q=d.query(Service)
    if session["role"]=="funcionario": q=q.filter(Service.responsible_id==session["uid"])
    return q
@app.get("/relatorios/csv")
@auth
def relatorio_csv():
    with db() as d:
        out=io.StringIO();w=csv.writer(out);w.writerow(["OS","Produto","Cliente/Setor","Prioridade","Status","Responsável","Início","Finalização"])
        for s in scoped_services(d).order_by(Service.created_at).all():
            u=d.get(User,s.responsible_id);w.writerow([f"OS-{s.id:05d}",s.product,s.client,s.priority,s.status,u.name if u else "",s.started_at.strftime("%d/%m/%Y %H:%M") if s.started_at else "",s.finished_at.strftime("%d/%m/%Y %H:%M") if s.finished_at else ""])
    return send_file(io.BytesIO(out.getvalue().encode("utf-8-sig")),as_attachment=True,download_name="relatorio_sakamoto.csv",mimetype="text/csv")
@app.get("/relatorios/pdf")
@auth
def relatorio_pdf():
    with db() as d:
        rows=scoped_services(d).order_by(Service.created_at).all();buf=io.BytesIO();c=canvas.Canvas(buf,pagesize=A4);w,h=A4;y=h-45
        c.setFont("Helvetica-Bold",16);c.drawString(40,y,"SAKAMOTO — RELATÓRIO DE SERVIÇOS");y-=22;c.setFont("Helvetica",9);c.drawString(40,y,"Gerado em "+datetime.now().strftime("%d/%m/%Y %H:%M"));y-=25
        for s in rows:
            u=d.get(User,s.responsible_id);c.drawString(40,y,f"OS-{s.id:05d} | {s.product[:30]} | {s.status} | {u.name if u else '-'}");y-=14
            c.drawString(55,y,f"Início: {s.started_at.strftime('%d/%m/%Y %H:%M') if s.started_at else '-'} | Final: {s.finished_at.strftime('%d/%m/%Y %H:%M') if s.finished_at else '-'}");y-=18
            if y<55:c.showPage();y=h-45;c.setFont("Helvetica",9)
        c.save()
    buf.seek(0);return send_file(buf,as_attachment=True,download_name="relatorio_sakamoto.pdf",mimetype="application/pdf")
@app.get("/historico")
@auth
def historico():
    with db() as d: rows=d.query(Audit).order_by(Audit.created_at.desc()).limit(200).all()
    return shell('''<h1>Histórico</h1><div class="panel"><table class="table"><tr><th>Data</th><th>Ação</th><th>Detalhes</th></tr>{% for x in rows %}<tr><td>{{x.created_at.strftime('%d/%m/%Y %H:%M')}}</td><td>{{x.action}}</td><td>{{x.details}}</td></tr>{% else %}<tr><td colspan="3">Sem registros.</td></tr>{% endfor %}</table></div>''',rows=rows)
@app.get("/configuracoes")
@auth
def configuracoes(): return shell("""<h1>Configurações</h1><div class='grid'><div class='panel'><h3>Minha conta</h3><p><b>Nome:</b> {{session.name}}</p><p><b>Login:</b> {{session.username}}</p><p><b>Cargo:</b> {{roles[session.role]}}</p></div><div class='panel'><h3>Permissões</h3><p>👑 Administrador — acesso total.</p><p>🧑‍💼 Chefe — gerencia equipe e atribui serviços.</p><p>👷 Funcionário — executa serviços atribuídos.</p></div></div>""",roles=ROLES)
@app.get("/status")
def status():
    try:
        init_db()
        with db() as d:return {"ok":True,"database":"connected","users":d.query(User).count(),"services":d.query(Service).count(),"products":d.query(Product).count()}
    except Exception as e:return {"ok":False,"database":"error","error":str(e)[:300]},503
@app.errorhandler(403)
def forbidden(e): return shell("<h1>Acesso negado</h1><div class='panel'>Você não tem permissão para esta área.</div>"),403
if __name__=="__main__": init_db();app.run(host="0.0.0.0",port=int(os.getenv("PORT",5000)))
