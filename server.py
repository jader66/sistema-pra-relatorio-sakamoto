"""Servidor com configuração inicial obrigatória do Administrador."""
from flask import request, redirect, url_for, render_template_string
from werkzeug.security import generate_password_hash
from app import app, Session, User

SETUP_HTML = '''<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Configuração inicial | Sakamoto</title><style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#071007;color:#fff;font-family:Arial}.box{width:min(440px,92vw);padding:32px;border-radius:20px;background:#102010;border:1px solid #4b8735;box-shadow:0 0 50px #0008}.logo{font-size:28px;font-weight:900;color:#ffd500;text-align:center}.sub{text-align:center;color:#6dff22;font-size:11px;letter-spacing:2px;margin:7px 0 25px}.field{margin:13px 0}.field label{display:block;font-size:12px;color:#b9c8b3;margin-bottom:5px}.field input{width:100%;padding:13px;border-radius:10px;border:1px solid #365535;background:#081208;color:white}.btn{width:100%;padding:14px;border:0;border-radius:10px;background:linear-gradient(90deg,#ffd500,#70ef16);font-weight:900;cursor:pointer}.info{font-size:12px;color:#aebba8;line-height:1.5;margin-bottom:20px}</style></head><body><div class="box"><div class="logo">SAKAMOTO</div><div class="sub">CONFIGURAÇÃO INICIAL</div><p class="info">Crie agora a conta do Administrador. Não existe usuário ou senha pré-cadastrados. O Administrador será responsável por criar os demais usuários e definir seus cargos.</p><form method="post"><div class="field"><label>NOME DO ADMINISTRADOR</label><input name="name" required autocomplete="name"></div><div class="field"><label>USUÁRIO</label><input name="username" required autocomplete="username"></div><div class="field"><label>SENHA</label><input type="password" name="password" required minlength="8" autocomplete="new-password"></div><div class="field"><label>CONFIRMAR SENHA</label><input type="password" name="confirm" required minlength="8" autocomplete="new-password"></div><button class="btn">CRIAR CONTA ADMINISTRADOR</button></form></div></body></html>'''

@app.before_request
def require_initial_admin():
    if request.endpoint == 'setup_admin' or request.path.startswith('/static'):
        return None
    with Session() as db:
        exists = db.query(User).count() > 0
    if not exists:
        return redirect(url_for('setup_admin'))

@app.route('/setup-admin', methods=['GET','POST'])
def setup_admin():
    with Session() as db:
        if db.query(User).count() > 0:
            return redirect(url_for('login'))
        if request.method == 'POST':
            name=request.form.get('name','').strip()
            username=request.form.get('username','').strip().lower()
            password=request.form.get('password','')
            confirm=request.form.get('confirm','')
            if not name or not username or len(password) < 8 or password != confirm:
                return render_template_string(SETUP_HTML + '<script>alert("Preencha corretamente os campos e confirme a senha.")</script>')
            user=User(name=name,username=username,password_hash=generate_password_hash(password),role='admin',active=True,failed=0,locked_until=None)
            db.add(user);db.commit()
            return redirect(url_for('login'))
    return render_template_string(SETUP_HTML)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
