from app import app, db, Product, Service, User, Audit, auth, manager, shell, ROLES, log
from flask import request, redirect, flash, abort

# Regras da manutenção: toda OS deve apontar para um produto previamente cadastrado.
# As rotas existentes de produtos/serviços são mantidas; esta camada valida o vínculo.

@app.route('/servicos/novo', methods=['GET','POST'])
@auth
@manager
def novo_servico_produto():
    with db() as d:
        products=d.query(Product).order_by(Product.name).all()
        users=d.query(User).filter(User.active==True).order_by(User.name).all()
        if request.method=='POST':
            product_id=request.form.get('product_id')
            p=d.get(Product, int(product_id)) if product_id else None
            if not p:
                flash('Selecione um produto já cadastrado.'); return redirect('/servicos/novo')
            s=Service(product=p.name, client=request.form.get('client','').strip() or p.sector,
                      problem=request.form.get('problem','').strip(), priority=request.form.get('priority','Normal'),
                      responsible_id=int(request.form['responsible_id']), created_by=request.form.get('created_by', '') or 0)
            # created_by deve ser o usuário conectado; evita aceitar valor arbitrário do formulário.
            s.created_by=__import__('flask').session['uid']
            d.add(s); d.commit(); log(d,'ATRIBUIR_SERVICO',f'OS-{s.id} | Produto {p.id} - {p.name}'); d.commit()
            flash('Manutenção enviada para o funcionário.'); return redirect('/servicos')
    return shell('''<h1>➕ Enviar manutenção</h1><p class="muted">Só é possível enviar manutenção para um produto já cadastrado.</p>
<div class="panel"><form class="form" method="post">
<div class="field fullcol"><label>PRODUTO CADASTRADO</label><select name="product_id" required><option value="">Selecione um produto...</option>{% for p in products %}<option value="{{p.id}}">{{p.name}}{% if p.code %} — {{p.code}}{% endif %}{% if p.sector %} — {{p.sector}}{% endif %}</option>{% endfor %}</select></div>
<div class="field"><label>CLIENTE / SETOR</label><input name="client"></div>
<div class="field"><label>RESPONSÁVEL</label><select name="responsible_id" required>{% for u in users %}<option value="{{u.id}}">{{u.name}} — {{roles[u.role]}}</option>{% endfor %}</select></div>
<div class="field"><label>PRIORIDADE</label><select name="priority"><option>Normal</option><option>Pouca urgência</option><option>Urgente</option></select></div>
<div class="field fullcol"><label>PROBLEMA / SERVIÇO</label><textarea name="problem" rows="5" placeholder="Descreva o que precisa ser feito"></textarea></div>
<button class="btn green fullcol">🛠️ ENVIAR MANUTENÇÃO</button></form></div>''', products=products, users=users, roles=ROLES)

@app.get('/produtos/<int:pid>')
@auth
def produto_detalhe(pid):
    with db() as d:
        p=d.get(Product,pid)
        if not p: abort(404)
        services=d.query(Service).filter(Service.product==p.name).order_by(Service.created_at.desc()).all()
        users=d.query(User).all()
    return shell('''<h1>📦 {{p.name}}</h1><div class="grid"><div class="panel"><p><b>Patrimônio:</b> {{p.code or '-'}}</p><p><b>Setor:</b> {{p.sector or '-'}}</p><p><b>Descrição:</b> {{p.description or '-'}}</p><p><b>Status:</b> {% if services and services[0].status!='Finalizado' %}Em manutenção{% else %}Disponível{% endif %}</p><a class="btn green" href="/servicos/novo">🛠️ Enviar para manutenção</a></div><div class="panel"><h3>Histórico de manutenção</h3>{% for s in services %}<p><a class="btn" href="/servicos/{{s.id}}">OS-{{'%05d'%s.id}} — {{s.status}}</a></p>{% else %}<p class="muted">Nenhuma manutenção registrada.</p>{% endfor %}</div></div>''',p=p,services=services,users=users)
