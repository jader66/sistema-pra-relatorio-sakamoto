from app import app, db, Product, Service, User, Audit, auth, manager, shell, ROLES, log
from flask import request, redirect, flash, abort, session
from sqlalchemy import text

# Regras da manutenção:
# 1) A OS só pode ser criada para um produto previamente cadastrado.
# 2) Se não houver produto cadastrado, a tela informa "Sem serviço".
# 3) A prioridade da manutenção pode ser alterada na ficha do produto.

@app.before_request
def ensure_product_priority_column():
    try:
        with db() as d:
            if str(d.bind.url).startswith('sqlite'):
                cols=d.execute(text('PRAGMA table_info(products)')).fetchall()
                names={r[1] for r in cols}
                if 'priority' not in names:
                    d.execute(text("ALTER TABLE products ADD COLUMN priority VARCHAR(30) DEFAULT 'Normal'"))
            else:
                d.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS priority VARCHAR(30) DEFAULT 'Normal'"))
            d.commit()
    except Exception:
        pass

@app.route('/servicos/novo', methods=['GET','POST'])
@auth
@manager
def novo_servico_produto():
    with db() as d:
        products=d.query(Product).order_by(Product.name).all()
        users=d.query(User).filter(User.active==True).order_by(User.name).all()
        if request.method=='POST':
            product_id=request.form.get('product_id')
            if not product_id:
                flash('Sem serviço: cadastre um produto antes de enviar uma manutenção.'); return redirect('/servicos/novo')
            try: p=d.get(Product, int(product_id))
            except Exception: p=None
            if not p:
                flash('O produto selecionado não existe. Cadastre o produto primeiro.'); return redirect('/servicos/novo')
            priority=request.form.get('priority','Normal')
            if priority not in ('Normal','Pouca urgência','Urgente'): priority='Normal'
            s=Service(product=p.name, client=request.form.get('client','').strip() or p.sector,
                      problem=request.form.get('problem','').strip(), priority=priority,
                      responsible_id=int(request.form['responsible_id']), created_by=session['uid'])
            d.add(s); d.commit(); log(d,'ATRIBUIR_SERVICO',f'OS-{s.id} | Produto {p.id} - {p.name} | {priority}'); d.commit()
            flash('Manutenção enviada para o funcionário.'); return redirect('/servicos')
    return shell('''<h1>➕ Enviar manutenção</h1>
<p class="muted">Selecione somente um produto que já esteja cadastrado.</p>
<div class="panel"><form class="form" method="post">
<div class="field fullcol"><label>PRODUTO CADASTRADO</label>
<select name="product_id" {% if not products %}disabled{% else %}required{% endif %}>
{% if products %}<option value="">Selecione um produto...</option>{% for p in products %}<option value="{{p.id}}">{{p.name}}{% if p.code %} — {{p.code}}{% endif %}{% if p.sector %} — {{p.sector}}{% endif %}</option>{% endfor %}
{% else %}<option value="">Sem serviço — nenhum produto cadastrado</option>{% endif %}</select></div>
{% if products %}<div class="field"><label>CLIENTE / SETOR</label><input name="client"></div>
<div class="field"><label>RESPONSÁVEL</label><select name="responsible_id" required>{% for u in users %}<option value="{{u.id}}">{{u.name}} — {{roles[u.role]}}</option>{% endfor %}</select></div>
<div class="field"><label>PRIORIDADE DA MANUTENÇÃO</label><select name="priority"><option>Normal</option><option>Pouca urgência</option><option>Urgente</option></select></div>
<div class="field fullcol"><label>PROBLEMA / SERVIÇO</label><textarea name="problem" rows="5" placeholder="Descreva o que precisa ser feito"></textarea></div>
<button class="btn green fullcol">🛠️ ENVIAR MANUTENÇÃO</button>
{% else %}<a class="btn green fullcol" href="/produtos">📦 Cadastrar produto primeiro</a>{% endif %}</form></div>''', products=products, users=users, roles=ROLES)

@app.route('/produtos/<int:pid>/prioridade', methods=['POST'])
@auth
@manager
def alterar_prioridade_produto(pid):
    priority=request.form.get('priority','Normal')
    if priority not in ('Normal','Pouca urgência','Urgente'):
        flash('Prioridade inválida.'); return redirect(f'/produtos/{pid}')
    with db() as d:
        p=d.get(Product,pid)
        if not p: abort(404)
        d.execute(text('UPDATE products SET priority=:priority WHERE id=:id'), {'priority':priority,'id':pid})
        # Atualiza a prioridade das OS pendentes/em andamento desse produto.
        d.query(Service).filter(Service.product==p.name, Service.status!='Finalizado').update({'priority':priority}, synchronize_session=False)
        log(d,'ALTERAR_PRIORIDADE',f'Produto {p.id} - {p.name}: {priority}'); d.commit()
    flash(f'Prioridade alterada para {priority}.'); return redirect(f'/produtos/{pid}')

@app.get('/produtos/<int:pid>')
@auth
def produto_detalhe(pid):
    with db() as d:
        p=d.get(Product,pid)
        if not p: abort(404)
        services=d.query(Service).filter(Service.product==p.name).order_by(Service.created_at.desc()).all()
        row=d.execute(text('SELECT priority FROM products WHERE id=:id'), {'id':pid}).first()
        priority=row[0] if row and row[0] else 'Normal'
    return shell('''<h1>📦 {{p.name}}</h1>
<div class="grid"><div class="panel">
<p><b>Patrimônio:</b> {{p.code or '-'}}</p><p><b>Setor:</b> {{p.sector or '-'}}</p><p><b>Descrição:</b> {{p.description or '-'}}</p>
<p><b>Status:</b> {% if services and services[0].status!='Finalizado' %}Em manutenção{% else %}Sem serviço / Disponível{% endif %}</p>
<h3>🚦 Prioridade</h3><form method="post" action="/produtos/{{p.id}}/prioridade" class="actions"><select name="priority"><option {% if priority=='Normal' %}selected{% endif %}>Normal</option><option {% if priority=='Pouca urgência' %}selected{% endif %}>Pouca urgência</option><option {% if priority=='Urgente' %}selected{% endif %}>Urgente</option></select><button class="btn green">Salvar prioridade</button></form>
<br><a class="btn green" href="/servicos/novo">🛠️ Enviar para manutenção</a>
</div><div class="panel"><h3>Histórico de manutenção</h3>{% for s in services %}<p><a class="btn" href="/servicos/{{s.id}}">OS-{{'%05d'%s.id}} — {{s.status}} — {{s.priority}}</a></p>{% else %}<p class="muted">Sem serviço registrado para este produto.</p>{% endfor %}</div></div>''',p=p,services=services,priority=priority)
