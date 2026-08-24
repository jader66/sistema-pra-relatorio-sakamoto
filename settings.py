import app as core
from app import app, Session, User, ROLES, auth, manager, log, is_manager
from flask import request, redirect, url_for, render_template_string, flash, abort, session
from werkzeug.security import generate_password_hash, check_password_hash

ROLE_INFO = {
    'admin': 'Administrador: acesso total ao sistema, usuários, ordens, relatórios, histórico e configurações.',
    'chefe': 'Chefe: acompanha funcionários, produtos, serviços, relatórios e operação. Não pode administrar o Administrador.',
    'funcionario': 'Funcionário: trabalha somente nas ordens atribuídas a ele e consulta seus próprios relatórios.'
}

core.LAYOUT = core.LAYOUT.replace(
    '<a href="/logout">↪ Sair</a>',
    '<a href="/configuracoes">⚙️ Configurações</a><a href="/criar-usuario">➕ Criar usuário</a><a href="/logout">↪ Sair</a>'
)

SETTINGS_LAYOUT = '''<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sakamoto | Configurações</title><style>*{box-sizing:border-box}body{margin:0;font-family:Inter,Arial;background:#f4f7f2;color:#172218}.side{position:fixed;inset:0 auto 0 0;width:245px;background:#071007;color:#fff;padding:22px 14px}.brand{font-weight:900;font-size:22px;color:#ffd500;padding:8px 12px 26px}.brand small{display:block;color:#65ff20;font-size:10px;letter-spacing:2px;margin-top:4px}.nav a{display:block;color:#cbd7c8;text-decoration:none;padding:12px;border-radius:9px;margin:3px 0}.nav a:hover{background:#173018;color:#fff}.main{margin-left:245px;min-height:100vh}.top{height:70px;background:#fff;border-bottom:1px solid #e2e9df;padding:0 28px;display:flex;justify-content:space-between;align-items:center}.content{padding:28px;max-width:1500px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:18px}.panel,.form{background:#fff;border:1px solid #e2e9df;border-radius:15px;padding:20px;box-shadow:0 5px 20px #00000008}.form input,.form select{width:100%;padding:12px;margin:5px 0 14px;border:1px solid #d6dfd3;border-radius:9px}.btn{border:0;border-radius:9px;padding:10px 14px;background:#132313;color:#fff;cursor:pointer}.primary{background:linear-gradient(90deg,#ffd500,#70ef16);color:#071000;font-weight:900}.muted{color:#718070;font-size:13px}.role{padding:15px;margin:10px 0;border:1px solid #e1e8dd;border-radius:12px;background:#fafcf9}.ok{background:#e9f8e3;padding:10px;border-radius:9px;margin-bottom:15px}table{width:100%;border-collapse:collapse}th,td{padding:11px;border-bottom:1px solid #edf1eb;text-align:left;font-size:13px}th{background:#f5f8f3}.back{display:inline-block;margin-bottom:15px;color:#355b32}@media(max-width:900px){.side{position:relative;width:100%;height:auto}.main{margin-left:0}}@media(max-width:600px){.content{padding:15px}}</style></head><body><aside class="side"><div class="brand">SAKAMOTO<small>VARIEDADES E TECNOLOGIA</small></div><nav class="nav"><a href="/dashboard">📊 Dashboard</a><a href="/ordens">🧰 Ordens de serviço</a><a href="/ordem/nova">➕ Nova ordem</a><a href="/relatorios">📄 Relatórios</a>{% if myrole in ['Administrador','Chefe'] %}<a href="/usuarios">👥 Funcionários</a><a href="/criar-usuario">➕ Criar usuário</a><a href="/historico">🕘 Histórico</a>{% endif %}<a href="/configuracoes">⚙️ Configurações</a><a href="/logout">↪ Sair</a></nav></aside><main class="main"><header class="top"><b>{{myrole}}</b><span>{{me}} · <a href="/configuracoes">Configurações</a> · <a href="/logout">Sair</a></span></header><section class="content">{% for m in get_flashed_messages() %}<div class="ok">{{m}}</div>{% endfor %}{{body|safe}}</section></main></body></html>'''

def cfg_page(body):
    return render_template_string(SETTINGS_LAYOUT, body=body, myrole=ROLES.get(session.get('role'),''), me=session.get('name'))

@app.route('/configuracoes', methods=['GET','POST'])
@auth
def configuracoes():
    with Session() as db:
        u = db.get(User, session['uid'])
        if not u:
            session.clear(); return redirect(url_for('login'))
        if request.method == 'POST':
            atual = request.form.get('current_password','')
            nova = request.form.get('new_password','')
            confirma = request.form.get('confirm_password','')
            if not check_password_hash(u.password_hash, atual): flash('A senha atual está incorreta.')
            elif len(nova) < 8: flash('A nova senha precisa ter pelo menos 8 caracteres.')
            elif nova != confirma: flash('A confirmação da nova senha não confere.')
            else:
                u.password_hash = generate_password_hash(nova); log(db, 'ALTERAR_SENHA', 'usuário alterou a própria senha'); db.commit(); flash('Senha alterada com sucesso.')
        usuarios = db.query(User).order_by(User.name).all() if is_manager() else []
        body = render_template_string(TEMPLATE, usuario=u, usuarios=usuarios, roles=ROLES, role_info=ROLE_INFO, manager=is_manager(), myrole=ROLES.get(session.get('role'),''))
    return cfg_page(body)

@app.route('/criar-usuario', methods=['GET','POST'])
@auth
@manager
def criar_usuario():
    with Session() as db:
        if request.method == 'POST':
            nome = request.form.get('name','').strip()
            username = request.form.get('username','').strip().lower()
            senha = request.form.get('password','')
            confirma = request.form.get('confirm_password','')
            role = request.form.get('role','funcionario')
            if not nome or not username or len(senha) < 8:
                flash('Preencha nome, login e uma senha com pelo menos 8 caracteres.')
            elif senha != confirma:
                flash('A confirmação da senha não confere.')
            elif role not in ROLES:
                flash('Perfil inválido.')
            elif session.get('role') == 'chefe' and role == 'admin':
                abort(403)
            elif db.query(User).filter(User.username == username).first():
                flash('Este login já está cadastrado. Escolha outro.')
            else:
                novo = User(name=nome, username=username, password_hash=generate_password_hash(senha), role=role, active=True)
                db.add(novo); db.flush(); log(db, 'CRIAR_USUARIO', f'{username} | perfil={role}'); db.commit()
                flash(f'Usuário {username} criado com sucesso.')
                return redirect(url_for('criar_usuario'))
        body = render_template_string(CREATE_USER_TEMPLATE, roles=ROLES, myrole=ROLES.get(session.get('role'),''))
    return cfg_page(body)

@app.route('/configuracoes/usuario/<int:uid>/perfil', methods=['POST'])
@auth
@manager
def configurar_perfil(uid):
    role = request.form.get('role','funcionario')
    if role not in ROLES: abort(400)
    with Session() as db:
        alvo = db.get(User, uid)
        if not alvo: abort(404)
        if alvo.id == session['uid'] and session.get('role') == 'admin' and role != 'admin':
            flash('O Administrador não pode retirar o próprio perfil administrativo por esta tela.')
            return redirect(url_for('configuracoes'))
        if session.get('role') == 'chefe' and (alvo.role == 'admin' or role == 'admin'): abort(403)
        anterior = alvo.role; alvo.role = role; log(db, 'ALTERAR_PERFIL', f'{alvo.username}: {anterior} -> {role}'); db.commit(); flash('Perfil atualizado.')
    return redirect(url_for('configuracoes'))

@app.route('/configuracoes/usuario/<int:uid>/status', methods=['POST'])
@auth
@manager
def configurar_status(uid):
    with Session() as db:
        alvo = db.get(User, uid)
        if not alvo or alvo.id == session['uid']: abort(400)
        if session.get('role') == 'chefe' and alvo.role == 'admin': abort(403)
        alvo.active = not alvo.active; log(db, 'ALTERAR_STATUS_USUARIO', f'{alvo.username}: {"ativo" if alvo.active else "desativado"}'); db.commit(); flash('Status do usuário atualizado.')
    return redirect(url_for('configuracoes'))

TEMPLATE = '''<h1>⚙️ Configurações</h1><div class="grid"><div class="form"><h2>🔐 Minha conta</h2><p class="muted">Sua senha nunca é exibida. Ela fica armazenada de forma protegida.</p><p><b>Nome:</b> {{usuario.name}}<br><b>Login:</b> {{usuario.username}}<br><b>Perfil:</b> {{roles[usuario.role]}}</p><form method="post"><label>Senha atual<input type="password" name="current_password" required></label><label>Nova senha<input type="password" name="new_password" minlength="8" required></label><label>Confirmar nova senha<input type="password" name="confirm_password" minlength="8" required></label><button class="btn primary">Alterar senha</button></form></div><div class="panel"><h2>👤 Perfis</h2>{% for role,info in role_info.items() %}<div class="role"><b>{{roles[role]}}</b><p class="muted">{{info}}</p></div>{% endfor %}</div></div>{% if manager %}<div class="panel" style="margin-top:18px"><h2>👥 Usuários cadastrados</h2><p><a class="btn primary" href="/criar-usuario">➕ Criar novo usuário</a></p><table><tr><th>Nome</th><th>Login</th><th>Perfil</th><th>Status</th></tr>{% for x in usuarios %}<tr><td>{{x.name}}</td><td>{{x.username}}</td><td>{{roles[x.role]}}</td><td>{{'Ativo' if x.active else 'Desativado'}}</td></tr>{% endfor %}</table></div>{% endif %}'''

CREATE_USER_TEMPLATE = '''<a class="back" href="/configuracoes">← Voltar para configurações</a><div class="form"><h1>➕ Criar novo usuário</h1><p class="muted">Cadastre uma conta para acessar o Sistema Sakamoto. A senha não será exibida depois do cadastro.</p><form method="post"><label>Nome completo<input name="name" autocomplete="name" placeholder="Ex.: João da Silva" required></label><label>Login de acesso<input name="username" autocomplete="username" placeholder="Ex.: joao.silva" required></label><label>Senha inicial<input type="password" name="password" minlength="8" autocomplete="new-password" required></label><label>Confirmar senha<input type="password" name="confirm_password" minlength="8" autocomplete="new-password" required></label><label>O que este usuário representa<select name="role" required>{% for role,nome in roles.items() %}{% if not (myrole=='Chefe' and role=='admin') %}<option value="{{role}}">{{nome}}</option>{% endif %}{% endfor %}</select></label><button class="btn primary" type="submit">Criar usuário e salvar</button></form></div>'''
