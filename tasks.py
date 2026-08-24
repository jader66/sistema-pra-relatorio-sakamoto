import app as core
from app import app, Session, User, Order, Audit, auth, is_manager, log, priority
from flask import request, redirect, url_for, render_template_string, flash, abort, session
from datetime import datetime

# Módulo de serviços: Administrador e Chefe podem atribuir serviços a qualquer usuário.
# Funcionário pode apenas executar serviços atribuídos a ele.

# Adiciona os atalhos ao menu empresarial já criado pelo settings.py.
core.LAYOUT = core.LAYOUT.replace(
    '<a href="/ordens">🧰 Ordens de serviço</a>',
    '<a href="/ordens">🧰 Ordens de serviço</a><a href="/servicos">📋 Serviços</a>'
).replace(
    '<a href="/ordem/nova">➕ Nova ordem</a>',
    '<a href="/ordem/nova">➕ Nova ordem</a><a href="/servicos/novo">➕ Atribuir serviço</a>'
)

SERVICE_CSS = '''<style>
.service-form{max-width:900px}.service-form input,.service-form select,.service-form textarea{width:100%;padding:13px;margin:6px 0 15px;border:1px solid #d6dfd3;border-radius:9px}.service-card{background:#fff;border:1px solid #e2e9df;border-radius:15px;padding:18px;margin:12px 0}.service-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:15px}.notice{background:#eef8e9;padding:13px;border-radius:10px;margin-bottom:15px}.danger{background:#ffe4e4;color:#9b0000}.small{font-size:12px;color:#718070}
</style>'''

SERVICE_TEMPLATE = '''<h1>📋 Serviços atribuídos</h1><p class="muted">Serviços criados pelo Administrador ou Chefe e atribuídos à equipe.</p><p><a class="btn primary" href="/servicos/novo">➕ Atribuir novo serviço</a></p>
<div class="service-grid">{% for o in orders %}<div class="service-card"><div><b>{{o.number}}</b> <span class="tag {% if priority(o)=='urgente' %}urgent{% elif priority(o)=='pouca urgencia' %}warning{% endif %}">{{priority(o)}}</span></div><h3>{{o.product}}</h3><p>{{o.problem or 'Sem descrição do problema.'}}</p><p class="small">Entrada: {{o.created_at.strftime('%d/%m/%Y %H:%M')}}<br>Status: {{o.status}}<br>Responsável: {{names.get(o.responsible_id,'Não atribuído')}}</p><a class="btn" href="/ordem/{{o.id}}">Abrir serviço</a></div>{% else %}<div class="service-card"><b>Nenhum serviço encontrado.</b></div>{% endfor %}</div>'''

NEW_SERVICE = '''<h1>➕ Atribuir serviço</h1><div class="notice"><b>Permissão:</b> Administrador e Chefe podem atribuir serviços para qualquer usuário ativo.</div><form class="form service-form" method="post" enctype="multipart/form-data"><label>Produto / equipamento<input name="product" required placeholder="Ex.: Computador Dell"></label><label>Cliente / setor<input name="client_sector" placeholder="Ex.: Financeiro"></label><label>Problema ou serviço solicitado<textarea name="problem" rows="5" placeholder="Descreva o que precisa ser feito" required></textarea></label><label>Responsável pelo serviço<select name="responsible_id" required><option value="">Selecione o usuário</option>{% for u in users %}<option value="{{u.id}}">{{u.name}} — {{roles[u.role]}}</option>{% endfor %}</select></label><label>Prioridade<select name="priority"><option value="normal">🟢 Normal</option><option value="pouca urgencia">🟡 Pouca urgência</option><option value="urgente">🔴 Urgente</option></select></label><label>Foto do produto<input type="file" name="photo" accept="image/*"></label><button class="btn primary" type="submit">Atribuir serviço</button></form>'''

@app.before_request
def block_employee_service_creation():
    # Funcionários não podem criar/atribuir serviços para terceiros.
    if request.path in ('/ordem/nova','/servicos/novo') and request.method in ('GET','POST') and session.get('role') == 'funcionario':
        return redirect(url_for('my_services'))

@app.route('/servicos')
@auth
def services():
    with Session() as db:
        q=db.query(Order)
        if session.get('role')=='funcionario':
            q=q.filter(Order.responsible_id==session['uid'])
        orders=q.order_by(Order.created_at.desc()).all()
        names={u.id:u.name for u in db.query(User).all()}
        body=SERVICE_TEMPLATE.replace('</h1>','</h1>')
        html=render_template_string(body,orders=orders,names=names,priority=priority)
    return core.page(SERVICE_CSS+html)

@app.route('/meus-servicos')
@auth
def my_services():
    return redirect(url_for('services'))

@app.route('/servicos/novo', methods=['GET','POST'])
@auth
def new_service():
    if not is_manager(): abort(403)
    with Session() as db:
        users=db.query(User).filter_by(active=True).order_by(User.name).all()
        if request.method=='POST':
            responsible=request.form.get('responsible_id')
            alvo=db.get(User,int(responsible)) if responsible else None
            if not alvo or not alvo.active:
                flash('Selecione um usuário ativo para receber o serviço.')
            else:
                f=request.files.get('photo'); data=f.read() if f and f.filename else None; name=f.filename if f and f.filename else None
                num='OS-'+datetime.now().strftime('%Y%m%d%H%M%S')+'-'+__import__('secrets').token_hex(2).upper()
                o=Order(number=num,product=request.form['product'].strip(),client_sector=request.form.get('client_sector','').strip(),problem=request.form.get('problem','').strip(),priority=request.form.get('priority','normal'),responsible_id=alvo.id,created_by=session['uid'],photo=data,photo_name=name)
                db.add(o); db.flush(); log(db,'ATRIBUIR_SERVICO',f'{num}: {session.get("name")} -> {alvo.name}'); db.commit()
                flash(f'Serviço {num} atribuído para {alvo.name}.')
                return redirect(url_for('services'))
        html=render_template_string(NEW_SERVICE,users=users,roles=core.ROLES)
    return core.page(SERVICE_CSS+html)
