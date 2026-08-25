from app import app,db,auth,manager,ROLES,Product,Service,User,shell,send_file,io,datetime,session,request,redirect,abort,flash,engine
from sqlalchemy import String,Integer,DateTime,ForeignKey,LargeBinary
from sqlalchemy.orm import Mapped,mapped_column
Base=Product.registry
class Photo(Base):
 __tablename__='photos';id:Mapped[int]=mapped_column(primary_key=True);owner_type:Mapped[str]=mapped_column(String(20));owner_id:Mapped[int]=mapped_column(Integer,index=True);filename:Mapped[str]=mapped_column(String(255));mimetype:Mapped[str]=mapped_column(String(100));data:Mapped[bytes]=mapped_column(LargeBinary);created_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True);created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
Base.metadata.create_all(engine)
def save(d,t,oid,files):
 n=0
 for f in files:
  if not f or not f.filename or f.mimetype not in {'image/jpeg','image/png','image/webp','image/gif'}:continue
  b=f.read()
  if b and len(b)<=8*1024*1024:d.add(Photo(owner_type=t,owner_id=oid,filename=f.filename[:255],mimetype=f.mimetype,data=b,created_by=session.get('uid')));n+=1
 return n
def remove(name):
 for r in list(app.url_map.iter_rules()):
  if r.endpoint==name:app.url_map._rules.remove(r);app.url_map._rules_by_endpoint.pop(name,None)
 app.view_functions.pop(name,None)
for x in ('produtos','novo_servico','servico_detalhe'):remove(x)
@app.route('/produtos',methods=['GET','POST'],endpoint='produtos')
@auth
def produtos():
 with db() as d:
  if request.method=='POST':
   if session['role'] not in ('admin','chefe'):abort(403)
   p=Product(name=request.form['name'].strip(),code=request.form.get('code',''),sector=request.form.get('sector',''),description=request.form.get('description',''));d.add(p);d.commit();n=save(d,'product',p.id,request.files.getlist('photos'));d.commit();flash(f'Produto cadastrado. {n} foto(s).');return redirect('/produtos')
  ps=d.query(Product).order_by(Product.created_at.desc()).all();counts={p.id:d.query(Photo).filter_by(owner_type='product',owner_id=p.id).count() for p in ps}
 return shell('''<h1>📦 Produtos</h1>{% if session.role in ['admin','chefe'] %}<div class="panel"><form class="form" method="post" enctype="multipart/form-data"><div class="field"><label>NOME</label><input name="name" required></div><div class="field"><label>CÓDIGO / PATRIMÔNIO</label><input name="code"></div><div class="field"><label>SETOR</label><input name="sector"></div><div class="field fullcol"><label>DESCRIÇÃO</label><textarea name="description"></textarea></div><div class="field fullcol"><label>📷 FOTOS DO PRODUTO</label><input type="file" name="photos" accept="image/*" multiple></div><button class="btn green fullcol">CADASTRAR PRODUTO</button></form></div><br>{% endif %}<div class="panel"><table class="table"><tr><th>Produto</th><th>Código</th><th>Setor</th><th>Fotos</th></tr>{% for p in ps %}<tr><td>{{p.name}}</td><td>{{p.code}}</td><td>{{p.sector}}</td><td>📷 {{counts[p.id]}}</td></tr>{% else %}<tr><td colspan="4">Nenhum produto.</td></tr>{% endfor %}</table></div>''',ps=ps,counts=counts)
@app.route('/servicos/novo',methods=['GET','POST'],endpoint='novo_servico')
@auth
@manager
def novo_servico():
 with db() as d:
  users=d.query(User).filter(User.active==True).order_by(User.name).all()
  if request.method=='POST':
   s=Service(product=request.form['product'].strip(),client=request.form.get('client',''),problem=request.form.get('problem',''),priority=request.form.get('priority','Normal'),responsible_id=int(request.form['responsible_id']),created_by=session['uid']);d.add(s);d.commit();n=save(d,'service',s.id,request.files.getlist('photos'));d.commit();flash(f'Trabalho enviado. {n} foto(s).');return redirect('/servicos')
 return shell('''<h1>🛠️ Enviar trabalho</h1><div class="panel"><form class="form" method="post" enctype="multipart/form-data"><div class="field"><label>PRODUTO</label><input name="product" required></div><div class="field"><label>CLIENTE / SETOR</label><input name="client"></div><div class="field fullcol"><label>PROBLEMA</label><textarea name="problem" rows="4"></textarea></div><div class="field"><label>RESPONSÁVEL</label><select name="responsible_id">{% for u in users %}<option value="{{u.id}}">{{u.name}} — {{roles[u.role]}}</option>{% endfor %}</select></div><div class="field"><label>PRIORIDADE</label><select name="priority"><option>Normal</option><option>Pouca urgência</option><option>Urgente</option></select></div><div class="field fullcol"><label>📷 FOTOS DO PRODUTO / PROBLEMA</label><input type="file" name="photos" accept="image/*" multiple></div><button class="btn green fullcol">ENVIAR TRABALHO</button></form></div>''',users=users,roles=ROLES)
@app.route('/servicos/<int:sid>',methods=['GET','POST'],endpoint='servico_detalhe')
@auth
def servico_detalhe(sid):
 with db() as d:
  s=d.get(Service,sid)
  if not s:abort(404)
  if session['role']=='funcionario' and s.responsible_id!=session['uid']:abort(403)
  if request.method=='POST':
   a=request.form.get('action')
   if a=='start' and not s.started_at:s.started_at=datetime.utcnow();s.status='Em andamento'
   elif a=='finish':s.finished_at=datetime.utcnow();s.status='Finalizado';s.notes=request.form.get('notes','')
   elif a=='photos':save(d,'service',sid,request.files.getlist('photos'))
   d.commit();return redirect(f'/servicos/{sid}')
  imgs=d.query(Photo).filter_by(owner_type='service',owner_id=sid).order_by(Photo.created_at).all()
 return shell('''<h1>OS-{{'%05d'%s.id}} — {{s.product}}</h1><div class="grid"><div class="panel"><p><b>Problema:</b> {{s.problem}}</p><p><b>Prioridade:</b> {{s.priority}}</p><p><b>Status:</b> {{s.status}}</p><p><b>Entrada:</b> {{s.created_at.strftime('%d/%m/%Y %H:%M')}}</p><p><b>Início:</b> {{s.started_at.strftime('%d/%m/%Y %H:%M') if s.started_at else '-'}}</p><p><b>Final:</b> {{s.finished_at.strftime('%d/%m/%Y %H:%M') if s.finished_at else '-'}}</p></div><div class="panel">{% if not s.started_at %}<form method="post"><input type="hidden" name="action" value="start"><button class="btn green full">▶ Iniciar</button></form>{% endif %}{% if s.status!='Finalizado' %}<form method="post"><input type="hidden" name="action" value="finish"><textarea name="notes" placeholder="Observações"></textarea><button class="btn full">✓ Finalizar</button></form>{% endif %}<hr><form method="post" enctype="multipart/form-data"><input type="hidden" name="action" value="photos"><input type="file" name="photos" accept="image/*" multiple required><button class="btn green">📷 Enviar fotos</button></form></div></div><br><div class="panel"><h3>📷 Fotos ({{imgs|length}})</h3><div class="photo-grid">{% for x in imgs %}<a href="/foto/{{x.id}}" target="_blank"><img src="/foto/{{x.id}}"></a>{% else %}<p class="muted">Nenhuma foto.</p>{% endfor %}</div></div>''',s=s,imgs=imgs)
@app.get('/foto/<int:pid>')
@auth
def foto(pid):
 with db() as d:
  x=d.get(Photo,pid)
  if not x:abort(404)
  if x.owner_type=='service':
   s=d.get(Service,x.owner_id)
   if session['role']=='funcionario' and (not s or s.responsible_id!=session['uid']):abort(403)
  elif x.owner_type=='product' and session['role']=='funcionario':abort(403)
  return send_file(io.BytesIO(x.data),mimetype=x.mimetype,download_name=x.filename)
