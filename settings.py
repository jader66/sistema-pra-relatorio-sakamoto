from app import app, Session, User, Audit, ROLES, ROLE_INFO, auth, manager, managers_only, log, page
from flask import request, redirect, url_for, render_template_string, flash, abort, session
from werkzeug.security import generate_password_hash, check_password_hash

# Camada de configuração adicionada sem expor credenciais na tela de login.

SETTINGS_LAYOUT='''<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sakamoto | Configurações</title><style>*{box-sizing:border-box}body{margin:0;font-family:Inter,Arial;background:#f4f7f2;color:#172218}.side{position:fixed;inset:0 auto 0 0;width:245px;background:#071007;color:#fff;padding:22px 14px}.brand{font-weight:900;font-size:22px;color:#ffd500;padding:8px 12px 26px}.brand small{display:block;color:#65ff20;font-size:10px;letter-spacing:2px;margin-top:4px}.nav a{display:block;color:#cbd7c8;text-decoration:none;padding:12px;border-radius:9px;margin:3px 0;text-decoration:none}.nav a:hover{background:#173018;color:#fff}.main{margin-left:245px;min-height:100vh}.top{height:70px;background:#fff;border-bottom:1px solid #e2e9df;padding:0 28px;display:flex;justify-content:space-between;align-items:center}.content{padding:28px;max-width:1500px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:18px}.panel,.form{background:#fff;border:1px solid #e2e9df;border-radius:15px;padding:20px;box-shadow:0 5px 20px #00000008}.form input,.form select{width:100%;padding:12px;margin:5px 0 14px;border:1px solid #d6dfd3;border-radius:9px}.btn{border:0;border-radius:9px;padding:10px 14px;background:#132313;color:#fff;cursor:pointer}.primary{background:linear-gradient(90deg,#ffd500,#70ef16);color:#071000;font-weight:900}.muted{color:#718070;font-size:13px}.role{padding:15px;margin:10px 0;border:1px solid #e1e8dd;border-radius:12px;background:#fafcf9}.ok{background:#e9f8e3;padding:10px;border-radius:9px;margin-bottom:15px}table{width:100%;border-collapse:collapse}th,td{padding:11px;border-bottom:1px solid #edf1eb;text-align:left;font-size:13px}th{background:#f5f8f3}@media(max-width:900px){.side{position:relative;width:100%;height:auto}.main{margin-left:0}}@media(max-width:600px){.content{padding:15px}}</style></head><body><aside class="side"><div class="brand">SAKAMOTO<small>VARIEDADES E TECNOLOGIA</small></div><nav class="nav"><a href="/dashboard">📊 Dashboard</a><a href="/ordens">🧰 Ordens de serviço</a><a href="/ordem/nova">➕ Nova ordem</a><a href="/relatorios">📄 Relatórios</a>{% if myrole in ['Administrador','Chefe'] %}<a href="/usuarios">👥 Funcionários</a><a href="/historico">🕘 Histórico</a>{% endif %}<a href="/configuracoes">⚙️ Configurações</a><a href="/logout">↪ Sair</a></nav></aside><main class="main"><header class="top"><b>{{myrole}}</b><span>{{me}} · <a href="/configuracoes">Configurações</a> · <a href="/logout">Sair</a></span></header><section class="content">{% for m in get_flashed_messages() %}<div class="ok">{{m}}</div>{% endfor %}{{body|safe}}</section></main></body></html>'''

def cfg_page(body):
    return render_template_string(SETTINGS_LAYOUT,body=body,myrole=ROLES.get(session.get('role'),''),me=session.get('name'))

@app.route('/configuracoes',methods=['GET','POST'])
@auth
def configuracoes():
    with Session() as db:
        u=db.get(User,session['uid'])
        if request.method=='POST':
            atual=request.form.get('current_password','')
            nova=request.form.get('new_password','')
            confirma=request.form.get('confirm_password','')
            if not check_password_hash(u.password_hash,atual): flash('A senha atual está incorreta.')
            elif len(nova)<6: flash('A nova senha precisa ter pelo menos 6 caracteres.')
            elif nova!=confirma: flash('A confirmação da nova senha não confere.')
            else:
                u.password_hash=generate_password_hash(nova)
                log(db,'ALTERAR_SENHA','usuário alterou a própria senha')
                db.commit();flash('Senha alterada com sucesso.')
        usuarios=db.query(User).order_by(User.name).all() if manager() else []
        body=render_template_string(TEMPLATE,usuario=u,usuarios=usuarios,roles=ROLES,role_info=ROLE_INFO,manager=manager())
    return cfg_page(body)

@app.route('/configuracoes/usuario/<int:uid>/perfil',methods=['POST'])
@auth
@managers_only
def configurar_perfil(uid):
    role=request.form.get('role','funcionario')
    if role not in ROLES: abort(400)
    with Session() as db:
        alvo=db.get(User,uid)
        if not alvo: abort(404)
        if alvo.id==session['uid'] and session.get('role')=='admin' and role!='admin':
            flash('O Administrador não pode retirar o próprio perfil administrativo por esta tela.')
            return redirect(url_for('configuracoes'))
        if session.get('role')=='chefe' and (alvo.role=='admin' or role=='admin'): abort(403)
        anterior=alvo.role;alvo.role=role;log(db,'ALTERAR_PERFIL',f'{alvo.username}: {anterior} -> {role}');db.commit();flash('Perfil atualizado.')
    return redirect(url_for('configuracoes'))

@app.route('/configuracoes/usuario/<int:uid>/status',methods=['POST'])
@auth
@managers_only
def configurar_status(uid):
    with Session() as db:
        alvo=db.get(User,uid)
        if not alvo or alvo.id==session['uid']: abort(400)
        if session.get('role')=='chefe' and alvo.role=='admin': abort(403)
        alvo.active=not alvo.active;log(db,'ALTERAR_STATUS_USUARIO',f'{alvo.username}: {"ativo" if alvo.active else "desativado"}');db.commit();flash('Status do usuário atualizado.')
    return redirect(url_for('configuracoes'))

TEMPLATE='''<h1>Configurações</h1><div class="grid"><div class="form"><h2>Minha conta</h2><p class="muted">Altere sua senha a qualquer momento. A senha é armazenada com hash e nunca é mostrada na tela.</p><p><b>Nome:</b> {{usuario.name}}<br><b>Login:</b> {{usuario.username}}<br><b>Perfil:</b> {{roles[usuario.role]}}</p><form method="post"><label>Senha atual<input type="password" name="current_password" autocomplete="current-password" required></label><label>Nova senha<input type="password" name="new_password" minlength="6" autocomplete="new-password" required></label><label>Confirmar nova senha<input type="password" name="confirm_password" minlength="6" autocomplete="new-password" required></label><button class="btn primary">Alterar senha</button></form></div><div class="panel"><h2>O que cada usuário representa</h2>{% for role,info in role_info.items() %}<div class="role"><b>{{roles[role]}}</b><p class="muted">{{info}}</p></div>{% endfor %}</div></div>{% if manager %}<div class="panel" style="margin-top:18px"><h2>Configurar usuários</h2><p class="muted">Aqui o Administrador/Chefe define se cada conta representa um Administrador, Chefe ou Funcionário. Senhas não ficam visíveis.</p><table><tr><th>Nome</th><th>Login</th><th>Perfil</th><th>Status</th><th>Ação</th></tr>{% for x in usuarios %}<tr><td>{{x.name}}</td><td>{{x.username}}</td><td><form method="post" action="/configuracoes/usuario/{{x.id}}/perfil"><select name="role" onchange="this.form.submit()">{% for r,n in roles.items() %}{% if not (myrole=='Chefe' and r=='admin') %}<option value="{{r}}" {% if x.role==r %}selected{% endif %}>{{n}}</option>{% endif %}{% endfor %}</select></form></td><td>{{'Ativo' if x.active else 'Desativado'}}</td><td>{% if x.id!=session['uid'] %}<form method="post" action="/configuracoes/usuario/{{x.id}}/status"><button class="btn">{{'Desativar' if x.active else 'Ativar'}}</button></form>{% endif %}</td></tr>{% endfor %}</table></div>{% endif %}'''

# /usuarios continua existindo no app principal; a nova aba Configurações concentra senha e perfil.
if __name__=='__main__':
    app.run(host='0.0.0.0',port=int(os.getenv('PORT',5000)),debug=False)
