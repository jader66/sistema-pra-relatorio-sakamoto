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
    last_login:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)

class Order(Base):
    __tablename__='orders'
    id:Mapped[int]=mapped_column(primary_key=True)
    number:Mapped[str]=mapped_column(String(40),unique=True,index=True)
    product:Mapped[str]=mapped_column(String(160))
    client_sector:Mapped[str]=mapped_column(String(160),default='')
    problem:Mapped[str]=mapped_column(Text,default='')
    priority:Mapped[str]=mapped_column(String(30),default='normal')
    status:Mapped[str]=mapped_column(String(30),default='aguardando')
    responsible_id:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.now)
    started_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    finished_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    parts:Mapped[str]=mapped_column(Text,default='')
    notes:Mapped[str]=mapped_column(Text,default='')
    photo:Mapped[bytes|None]=mapped_column(LargeBinary,nullable=True)
    photo_name:Mapped[str|None]=mapped_column(String(255),nullable=True)

class Audit(Base):
    __tablename__='audit'
    id:Mapped[int]=mapped_column(primary_key=True)
    user_id:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    action:Mapped[str]=mapped_column(String(100))
    details:Mapped[str]=mapped_column(Text,default='')
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.now)

Base.metadata.create_all(engine)

app=Flask(__name__)
app.secret_key=os.getenv('SECRET_KEY',secrets.token_hex(32))
app.config['MAX_CONTENT_LENGTH']=12*1024*1024
ROLES={'admin':'Administrador','chefe':'Chefe','funcionario':'Funcionário'}

def log(db,action,details=''): db.add(Audit(user_id=session.get('uid'),action=action,details=details))
def is_manager(): return session.get('role') in ('admin','chefe')
def auth(f):
    @wraps(f)
    def w(*a,**k):
        if not session.get('uid'): return redirect(url_for('login'))
        return f(*a,**k)
    return w
def manager(f):
    @wraps(f)
    def w(*a,**k):
        if not is_manager(): abort(403)
        return f(*a,**k)
    return w
def priority(o):
    if o.status=='finalizado': return o.priority
    age=(datetime.now()-o.created_at).days
    base={'normal':1,'pouca urgencia':2,'urgente':3}.get(o.priority,1)
    return ['normal','pouca urgencia','urgente'][min(3,base+(age>=3)+(age>=7))-1]
def visible(q):
    if session.get('role')=='funcionario': return q.filter(or_(Order.responsible_id==session['uid'],Order.created_by==session['uid']))
    return q

def seed():
    with Session() as db:
        if not db.query(User).count():
            db.add_all([User(name='Administrador',username='admin',password_hash=generate_password_hash('123456'),role='admin'),User(name='Chefe',username='chefe',password_hash=generate_password_hash('123456'),role='chefe'),User(name='Funcionário 1',username='funcionario1',password_hash=generate_password_hash('123456'),role='funcionario')]); db.commit()
seed()

@app.context_processor
def ctx(): return {'roles':ROLES,'app_name':APP,'me':session.get('name'),'myrole':ROLES.get(session.get('role'),'')}

CSS='''<style>*{box-sizing:border-box}body{margin:0;font-family:Inter,Arial;background:#f4f7f2;color:#172218}.side{position:fixed;inset:0 auto 0 0;width:245px;background:#071007;color:#fff;padding:22px 14px}.brand{font-weight:900;font-size:22px;color:#ffd500;padding:8px 12px 26px}.brand small{display:block;color:#65ff20;font-size:10px;letter-spacing:2px;margin-top:4px}.nav a{display:block;color:#cbd7c8;text-decoration:none;padding:12px;border-radius:9px;margin:3px 0}.nav a:hover{background:#173018;color:#fff}.main{margin-left:245px;min-height:100vh}.top{height:70px;background:#fff;border-bottom:1px solid #e2e9df;padding:0 28px;display:flex;justify-content:space-between;align-items:center}.content{padding:28px;max-width:1500px}.cards{display:grid;grid-template-columns:repeat(5,1fr);gap:14px}.card,.panel,.form{background:#fff;border:1px solid #e2e9df;border-radius:15px;padding:20px;box-shadow:0 5px 20px #00000008}.num{font-size:30px;font-weight:900;margin-top:8px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:16px;margin-top:18px}.btn{display:inline-block;border:0;border-radius:9px;padding:10px 14px;background:#132313;color:#fff;text-decoration:none;cursor:pointer}.primary{background:linear-gradient(90deg,#ffd500,#70ef16);color:#071000;font-weight:900}.danger{background:#b4232d}.muted{color:#718070;font-size:13px}.tag{padding:5px 9px;border-radius:99px;background:#edf2ea;font-size:11px}.urgent{background:#ffe1e1;color:#9b0000}.warning{background:#fff0c7;color:#795500}table{width:100%;border-collapse:collapse}th,td{padding:11px;border-bottom:1px solid #edf1eb;text-align:left;font-size:13px}th{background:#f5f8f3}.form{max-width:850px}.form input,.form select,.form textarea{width:100%;padding:12px;margin:5px 0 14px;border:1px solid #d6dfd3;border-radius:9px}.actions{display:flex;gap:8px;flex-wrap:wrap}.photo{max-width:300px;border-radius:12px}.bar{height:8px;background:#e7eee5;border-radius:9px}.bar i{display:block;height:100%;background:#5ae31c;border-radius:9px}@media(max-width:900px){.side{position:relative;width:100%;height:auto}.main{margin-left:0}.cards{grid-template-columns:repeat(2,1fr)}}@media(max-width:600px){.cards{grid-template-columns:1fr}.content{padding:15px}.top{padding:0 15px}}</style>'''
LAYOUT='''<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{app_name}}</title>'''+CSS+'''</head><body><aside class="side"><div class="brand">SAKAMOTO<small>VARIEDADES E TECNOLOGIA</small></div><nav class="nav"><a href="/dashboard">📊 Dashboard</a><a href="/ordens">🧰 Ordens de serviço</a><a href="/ordem/nova">➕ Nova ordem</a><a href="/relatorios">📄 Relatórios</a>{% if myrole in ['Administrador','Chefe'] %}<a href="/usuarios">👥 Funcionários</a><a href="/historico">🕘 Histórico</a>{% endif %}<a href="/logout">↪ Sair</a></nav></aside><main class="main"><header class="top"><b>{{myrole}}</b><span>{{me}} · <a href="/logout">Sair</a></span></header><section class="content">{% for m in get_flashed_messages() %}<div class="panel" style="margin-bottom:15px">{{m}}</div>{% endfor %}{{body|safe}}</section></main></body></html>'''
def page(body): return render_template_string(LAYOUT,body=body)

LOGIN='''<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Acesso | Sakamoto</title><style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:radial-gradient(circle at 50% 15%,#173d0c,#061006 55%,#020402);font-family:Arial;color:#fff}.box{width:min(430px,92vw);padding:34px;border:1px solid #3e7131;border-radius:24px;background:#061006e8;box-shadow:0 0 60px #55ff0026;text-align:center}.logo{width:190px;height:190px}.title{font-size:26px;font-weight:900;color:#ffd900}.sub{font-size:11px;letter-spacing:3px;color:#61ff18;margin:6px 0 25px}.field{text-align:left;margin:12px 0}.field label{font-size:11px;color:#b9c8b3}.field input{width:100%;padding:14px;margin-top:6px;border:1px solid #29442a;border-radius:12px;background:#0b180b;color:#fff}.pass{position:relative}.eye{position:absolute;right:8px;top:13px;background:none;border:0;color:#8cff55;cursor:pointer}.submit{width:100%;padding:14px;border:0;border-radius:12px;background:linear-gradient(90deg,#ffd500,#75ff16);font-weight:900;cursor:pointer}.link{display:block;color:#8cff55;text-decoration:none;font-size:12px;margin-top:15px}.flash{background:#481b1b;color:#ffc0c0;padding:10px;border-radius:10px;font-size:13px}</style></head><body><div class="box"><img class="logo" src="/static/logo.svg"><div class="title">SAKAMOTO</div><div class="sub">VARIEDADES E TECNOLOGIA</div>{% for m in get_flashed_messages() %}<p class="flash">{{m}}</p>{% endfor %}<form method="post"><div class="field"><label>USUÁRIO</label><input name="username" autocomplete="username" required></div><div class="field"><label>SENHA</label><div class="pass"><input id="password" type="password" name="password" autocomplete="current-password" required><button class="eye" type="button" onclick="togglePass()">👁</button></div></div><div style="text-align:left;font-size:12px;color:#aebca8;margin:10px 0"><input type="checkbox" name="remember" value="1"> Lembrar acesso</div><button class="submit">ENTRAR NO SISTEMA</button></form><a class="link" href="/recuperar">Esqueci minha senha</a></div><script>function togglePass(){let p=document.getElementById('password');p.type=p.type==='password'?'text':'password'}</script></body></html>'''

@app.route('/')
def index(): return redirect(url_for('dashboard')) if session.get('uid') else redirect(url_for('login'))
@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        with Session() as db:
            u=db.query(User).filter(func.lower(User.username)==request.form.get('username','').strip().lower()).first()
            if not u or not u.active: flash('Usuário ou senha inválidos.'); return render_template_string(LOGIN)
            if u.locked_until and u.locked_until>datetime.now(): flash('Conta temporariamente bloqueada.'); return render_template_string(LOGIN)
            if not check_password_hash(u.password_hash,request.form.get('password','')):
                u.failed+=1
                if u.failed>=5: u.failed=0;u.locked_until=datetime.now()+timedelta(minutes=15);log(db,'BLOQUEIO_LOGIN',u.username)
                db.commit();flash('Usuário ou senha inválidos.');return render_template_string(LOGIN)
            u.failed=0;u.locked_until=None;u.last_login=datetime.now();session.permanent=request.form.get('remember')=='1';session.update(uid=u.id,name=u.name,username=u.username,role=u.role);log(db,'LOGIN',u.username);db.commit()
        return redirect(url_for('dashboard'))
    return render_template_string(LOGIN)
@app.route('/logout')
def logout():
    if session.get('uid'):
        with Session() as db: log(db,'LOGOUT',session.get('username'));db.commit()
    session.clear();return redirect(url_for('login'))
@app.route('/recuperar',methods=['GET','POST'])
def recover():
    if request.method=='POST':
        with Session() as db: log(db,'SOLICITACAO_SENHA',request.form.get('username',''));db.commit()
        flash('Solicitação registrada. O administrador poderá redefinir sua senha no painel.');return redirect(url_for('login'))
    return page('<div class="form"><h1>Recuperação de senha</h1><p class="muted">Informe seu usuário. A solicitação será registrada para o administrador.</p><form method="post"><input name="username" placeholder="Usuário" required><button class="btn primary">Solicitar</button></form></div>')

@app.route('/dashboard')
@auth
def dashboard():
    with Session() as db:
        q=visible(db.query(Order)); total=q.count(); waiting=q.filter(Order.status=='aguardando').count(); repairing=q.filter(Order.status=='consertando').count(); finished=q.filter(Order.status=='finalizado').count(); orders=q.order_by(Order.created_at.desc()).limit(10).all(); urgent=sum(priority(o)=='urgente' for o in orders if o.status!='finalizado'); late=sum((datetime.now()-o.created_at).days>=7 for o in orders if o.status!='finalizado'); users=db.query(User).filter_by(active=True).all(); rank=[]
        for u in users: rank.append((u,visible(db.query(Order)).filter(Order.responsible_id==u.id,Order.status=='finalizado').count()))
        rank.sort(key=lambda x:x[1],reverse=True)
        body=render_template_string(DASH, total=total,waiting=waiting,repairing=repairing,finished=finished,urgent=urgent,late=late,orders=orders,rank=rank[:5],priority=priority)
    return page(body)

@app.route('/ordens')
@auth
def orders():
    with Session() as db: body=render_template_string(ORDERS,orders=visible(db.query(Order)).order_by(Order.created_at.desc()).all(),priority=priority)
    return page(body)
@app.route('/ordem/nova',methods=['GET','POST'])
@auth
def new_order():
    with Session() as db:
        if request.method=='POST':
            f=request.files.get('photo'); data=f.read() if f and f.filename else None; name=f.filename if f and f.filename else None; num='OS-'+datetime.now().strftime('%Y%m%d%H%M%S')+'-'+secrets.token_hex(2).upper();o=Order(number=num,product=request.form['product'],client_sector=request.form.get('client_sector',''),problem=request.form.get('problem',''),priority=request.form.get('priority','normal'),responsible_id=int(request.form['responsible_id']) if request.form.get('responsible_id') else None,created_by=session['uid'],photo=data,photo_name=name);db.add(o);log(db,'CRIAR_OS',num);db.commit();flash('Ordem criada com sucesso.');return redirect(url_for('orders'))
        us=db.query(User).filter_by(active=True).order_by(User.name).all();body=render_template_string(FORM,users=us)
    return page(body)
@app.route('/ordem/<int:oid>')
@auth
def detail(oid):
    with Session() as db:
        o=db.get(Order,oid)
        if not o:abort(404)
        if session['role']=='funcionario' and o.responsible_id not in (session['uid'],None) and o.created_by!=session['uid']:abort(403)
        body=render_template_string(DETAIL,o=o,priority=priority)
    return page(body)
@app.route('/ordem/<int:oid>/iniciar',methods=['POST'])
@auth
def start(oid):
    with Session() as db:
        o=db.get(Order,oid)
        if not o:abort(404)
        if session['role']=='funcionario' and o.responsible_id not in (None,session['uid']):abort(403)
        o.responsible_id=o.responsible_id or session['uid'];o.status='consertando';o.started_at=o.started_at or datetime.now();log(db,'INICIAR_OS',o.number);db.commit()
    return redirect(url_for('detail',oid=oid))
@app.route('/ordem/<int:oid>/finalizar',methods=['POST'])
@auth
def finish(oid):
    with Session() as db:
        o=db.get(Order,oid)
        if not o:abort(404)
        if session['role']=='funcionario' and o.responsible_id!=session['uid']:abort(403)
        o.status='finalizado';o.finished_at=datetime.now();o.parts=request.form.get('parts','');o.notes=request.form.get('notes','');log(db,'FINALIZAR_OS',o.number);db.commit()
    return redirect(url_for('detail',oid=oid))
@app.route('/foto/<int:oid>')
def photo(oid):
    with Session() as db:
        o=db.get(Order,oid)
        if not o or not o.photo:abort(404)
        return send_file(io.BytesIO(o.photo),download_name=o.photo_name or 'produto.jpg',mimetype='image/jpeg')

@app.route('/usuarios',methods=['GET','POST'])
@auth
@manager
def users():
    with Session() as db:
        if request.method=='POST':
            role=request.form.get('role','funcionario')
            if session['role']=='chefe' and role=='admin':abort(403)
            u=User(name=request.form['name'],username=request.form['username'].strip().lower(),password_hash=generate_password_hash(request.form['password']),role=role)
            try: db.add(u);log(db,'CRIAR_USUARIO',u.username);db.commit();flash('Usuário criado e salvo.')
            except Exception: db.rollback();flash('Não foi possível criar. O login pode já existir.')
        rows=db.query(User).order_by(User.name).all();body=render_template_string(USERS,users=rows)
    return page(body)
@app.route('/usuarios/<int:uid>/toggle',methods=['POST'])
@auth
@manager
def toggle(uid):
    with Session() as db:
        u=db.get(User,uid)
        if not u or u.id==session['uid']:abort(400)
        if session['role']=='chefe' and u.role=='admin':abort(403)
        u.active=not u.active;log(db,'ALTERAR_USUARIO',u.username);db.commit()
    return redirect(url_for('users'))
@app.route('/historico')
@auth
@manager
def history():
    with Session() as db:
        logs=db.query(Audit).order_by(Audit.created_at.desc()).limit(500).all();names={u.id:u.name for u in db.query(User).all()};body=render_template_string(HISTORY,logs=logs,names=names)
    return page(body)

@app.route('/relatorios')
@auth
def reports():
    with Session() as db: us=db.query(User).filter_by(active=True).order_by(User.name).all();body=render_template_string(REPORT_FILTER,users=us)
    return page(body)
def report_rows(db):
    q=visible(db.query(Order));ini=request.args.get('inicio');fim=request.args.get('fim');uid=request.args.get('usuario');status=request.args.get('status');pri=request.args.get('prioridade')
    if ini:q=q.filter(Order.created_at>=datetime.fromisoformat(ini))
    if fim:q=q.filter(Order.created_at<datetime.fromisoformat(fim)+timedelta(days=1))
    if uid and session['role']!='funcionario':q=q.filter(Order.responsible_id==int(uid))
    if status:q=q.filter(Order.status==status)
    if pri:q=q.filter(Order.priority==pri)
    return q.order_by(Order.created_at.desc()).all()
@app.route('/relatorio/visualizar')
@auth
def report_view():
    with Session() as db: body=render_template_string(REPORT,rows=report_rows(db),priority=priority)
    return page(body)
@app.route('/relatorio/csv')
@auth
def csv_report():
    with Session() as db: rows=report_rows(db); names={u.id:u.name for u in db.query(User).all()}
    out=io.StringIO();w=csv.writer(out,delimiter=';');w.writerow(['OS','Produto','Cliente/Setor','Prioridade','Status','Entrada','Início','Finalização','Responsável','Peças','Observações'])
    for o in rows:w.writerow([o.number,o.product,o.client_sector,priority(o),o.status,o.created_at,o.started_at or '',o.finished_at or '',names.get(o.responsible_id,''),o.parts,o.notes])
    return send_file(io.BytesIO(out.getvalue().encode('utf-8-sig')),as_attachment=True,download_name='relatorio_sakamoto.csv',mimetype='text/csv')
@app.route('/relatorio/xlsx')
@auth
def xlsx_report():
    from openpyxl import Workbook
    with Session() as db: rows=report_rows(db);names={u.id:u.name for u in db.query(User).all()}
    wb=Workbook();ws=wb.active;ws.title='Relatório';ws.append(['OS','Produto','Cliente/Setor','Prioridade','Status','Entrada','Início','Finalização','Responsável','Peças','Observações'])
    for o in rows:ws.append([o.number,o.product,o.client_sector,priority(o),o.status,o.created_at,o.started_at or '',o.finished_at or '',names.get(o.responsible_id,''),o.parts,o.notes])
    buf=io.BytesIO();wb.save(buf);buf.seek(0);return send_file(buf,as_attachment=True,download_name='relatorio_sakamoto.xlsx',mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
@app.route('/relatorio/pdf')
@auth
def pdf_report():
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4,landscape
    with Session() as db: rows=report_rows(db);names={u.id:u.name for u in db.query(User).all()}
    buf=io.BytesIO();c=canvas.Canvas(buf,pagesize=landscape(A4));w,h=landscape(A4);y=h-35;c.setFont('Helvetica-Bold',16);c.drawString(30,y,'SAKAMOTO — RELATÓRIO DE MANUTENÇÃO');y-=28;c.setFont('Helvetica',8)
    for o in rows:
        line=f'{o.number} | {o.product[:32]} | {priority(o)} | {o.status} | {o.created_at:%d/%m/%Y %H:%M} | {o.finished_at:%d/%m/%Y %H:%M}' if o.finished_at else f'{o.number} | {o.product[:32]} | {priority(o)} | {o.status} | {o.created_at:%d/%m/%Y %H:%M}'
        c.drawString(30,y,line[:155]);y-=14
        if y<35:c.showPage();y=h-35;c.setFont('Helvetica',8)
    c.save();buf.seek(0);return send_file(buf,as_attachment=True,download_name='relatorio_sakamoto.pdf',mimetype='application/pdf')

@app.errorhandler(403)
def e403(e):return page('<div class="form"><h1>Acesso negado</h1><p>Seu perfil não possui permissão para esta área.</p></div>'),403

DASH='''<h1>Dashboard</h1><p class="muted">Visão geral da operação de manutenção.</p><div class="cards"><div class="card">Produtos pendentes<div class="num">{{total}}</div></div><div class="card">Aguardando<div class="num">{{waiting}}</div></div><div class="card">Em manutenção<div class="num">{{repairing}}</div></div><div class="card">Finalizados<div class="num">{{finished}}</div></div><div class="card">Urgentes<div class="num">{{urgent}}</div></div></div><div class="grid"><div class="panel"><h3>Ranking de produtividade</h3>{% for u,c in rank %}<p><b>{{u.name}}</b> <span class="muted">{{c}} serviços</span></p><div class="bar"><i style="width:{{min(c*10,100)}}%"></i></div>{% else %}<p class="muted">Ainda sem serviços finalizados.</p>{% endfor %}</div><div class="panel"><h3>Ordens recentes</h3><a class="btn primary" href="/ordem/nova">+ Nova ordem</a><a class="btn" href="/ordens">Ver todas</a><ul>{% for o in orders %}<li><a href="/ordem/{{o.id}}">{{o.number}} — {{o.product}}</a> · {{o.status}} · {{priority(o)}}</li>{% endfor %}</ul></div></div>'''
ORDERS='''<h1>Ordens de serviço</h1><p><a class="btn primary" href="/ordem/nova">+ Nova ordem</a></p><div class="panel"><table><tr><th>OS</th><th>Produto</th><th>Prioridade</th><th>Status</th><th>Entrada</th><th></th></tr>{% for o in orders %}<tr><td>{{o.number}}</td><td>{{o.product}}</td><td><span class="tag {% if priority(o)=='urgente' %}urgent{% elif priority(o)=='pouca urgencia' %}warning{% endif %}">{{priority(o)}}</span></td><td>{{o.status}}</td><td>{{o.created_at.strftime('%d/%m/%Y %H:%M')}}</td><td><a class="btn" href="/ordem/{{o.id}}">Abrir</a></td></tr>{% endfor %}</table></div>'''
FORM='''<h1>Nova ordem de serviço</h1><form class="form" method="post" enctype="multipart/form-data"><label>Produto<input name="product" required></label><label>Cliente / setor<input name="client_sector"></label><label>Problema informado<textarea name="problem" rows="5"></textarea></label><label>Prioridade<select name="priority"><option value="normal">Normal</option><option value="pouca urgencia">Pouca urgência</option><option value="urgente">Urgente</option></select></label><label>Funcionário responsável<select name="responsible_id"><option value="">A definir</option>{% for u in users %}<option value="{{u.id}}">{{u.name}} — {{roles[u.role]}}</option>{% endfor %}</select></label><label>Foto do produto<input type="file" name="photo" accept="image/*"></label><button class="btn primary">Cadastrar ordem</button></form>'''
DETAIL='''<h1>{{o.number}} <span class="tag">{{o.status}}</span></h1><div class="grid"><div class="panel"><h2>{{o.product}}</h2><p><b>Prioridade:</b> {{priority(o)}}</p><p><b>Cliente/setor:</b> {{o.client_sector or '—'}}</p><p><b>Problema:</b><br>{{o.problem or '—'}}</p>{% if o.photo %}<img class="photo" src="/foto/{{o.id}}">{% endif %}<p class="muted">Entrada: {{o.created_at.strftime('%d/%m/%Y %H:%M')}}<br>Início: {{o.started_at.strftime('%d/%m/%Y %H:%M') if o.started_at else '—'}}<br>Finalização: {{o.finished_at.strftime('%d/%m/%Y %H:%M') if o.finished_at else '—'}}</p>{% if o.status!='finalizado' %}<form method="post" action="/ordem/{{o.id}}/iniciar"><button class="btn primary">Iniciar conserto</button></form>{% if o.status=='consertando' %}<form method="post" action="/ordem/{{o.id}}/finalizar"><label>Peças utilizadas<textarea name="parts"></textarea></label><label>Observações<textarea name="notes"></textarea></label><button class="btn primary">Finalizar ordem</button></form>{% endif %}{% endif %}</div></div>'''
USERS='''<h1>Usuários e permissões</h1><form class="form" method="post"><h3>Criar usuário</h3><input name="name" placeholder="Nome completo" required><input name="username" placeholder="Login" required><input type="password" name="password" placeholder="Senha" minlength="6" required><select name="role"><option value="funcionario">Funcionário</option><option value="chefe">Chefe</option>{% if session['role']=='admin' %}<option value="admin">Administrador</option>{% endif %}</select><button class="btn primary">Criar usuário</button></form><div class="panel" style="margin-top:18px"><table><tr><th>Nome</th><th>Login</th><th>Perfil</th><th>Status</th><th></th></tr>{% for u in users %}<tr><td>{{u.name}}</td><td>{{u.username}}</td><td>{{roles[u.role]}}</td><td>{{'Ativo' if u.active else 'Desativado'}}</td><td>{% if u.id!=session['uid'] %}<form method="post" action="/usuarios/{{u.id}}/toggle"><button class="btn">{{'Desativar' if u.active else 'Ativar'}}</button></form>{% endif %}</td></tr>{% endfor %}</table></div>'''
HISTORY='''<h1>Histórico de ações</h1><div class="panel"><table><tr><th>Data/hora</th><th>Usuário</th><th>Ação</th><th>Detalhes</th></tr>{% for x in logs %}<tr><td>{{x.created_at.strftime('%d/%m/%Y %H:%M:%S')}}</td><td>{{names.get(x.user_id,'Sistema')}}</td><td>{{x.action}}</td><td>{{x.details}}</td></tr>{% endfor %}</table></div>'''
REPORT_FILTER='''<h1>Relatórios</h1><form class="form" method="get" action="/relatorio/visualizar"><label>Data inicial<input type="date" name="inicio"></label><label>Data final<input type="date" name="fim"></label><label>Funcionário<select name="usuario"><option value="">Todos</option>{% for u in users %}<option value="{{u.id}}">{{u.name}}</option>{% endfor %}</select></label><label>Status<select name="status"><option value="">Todos</option><option>aguardando</option><option>consertando</option><option>finalizado</option></select></label><label>Prioridade<select name="prioridade"><option value="">Todas</option><option value="normal">Normal</option><option value="pouca urgencia">Pouca urgência</option><option value="urgente">Urgente</option></select></label><button class="btn primary">Gerar relatório</button></form>'''
REPORT='''<h1>Relatório de manutenção</h1><div class="actions"><a class="btn" href="/relatorio/csv?{{request.query_string.decode()}}">CSV</a><a class="btn" href="/relatorio/xlsx?{{request.query_string.decode()}}">Excel</a><a class="btn" href="/relatorio/pdf?{{request.query_string.decode()}}">PDF</a><button class="btn" onclick="window.print()">Imprimir</button></div><div class="panel" style="margin-top:15px"><table><tr><th>OS</th><th>Produto</th><th>Prioridade</th><th>Status</th><th>Entrada</th><th>Início</th><th>Finalização</th></tr>{% for o in rows %}<tr><td>{{o.number}}</td><td>{{o.product}}</td><td>{{priority(o)}}</td><td>{{o.status}}</td><td>{{o.created_at.strftime('%d/%m/%Y %H:%M')}}</td><td>{{o.started_at.strftime('%d/%m/%Y %H:%M') if o.started_at else '—'}}</td><td>{{o.finished_at.strftime('%d/%m/%Y %H:%M') if o.finished_at else '—'}}</td></tr>{% endfor %}</table></div>'''

app.jinja_env.globals['min']=min
if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.getenv('PORT',5000)),debug=False)
