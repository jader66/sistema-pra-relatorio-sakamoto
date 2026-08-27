"""Módulo de apoio ao modelo de gestão da qualidade baseado na ISO 9001."""
from datetime import datetime
from flask import Blueprint, request, redirect, session, render_template_string, flash
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

iso_bp = Blueprint("iso9001", __name__)


class QualityRecordMixin:
    """Campos comuns para rastreabilidade e tratamento de ocorrências."""


class QualityRecord:
    pass


def register_iso9001(app):
    """Registra o painel de qualidade sem alterar as rotas existentes."""
    from app import Base, engine, SessionLocal, Service, Product, Audit, auth, manager, log

    class QualityIssue(Base):
        __tablename__ = "quality_issues"
        id: Mapped[int] = mapped_column(primary_key=True)
        service_id: Mapped[int | None] = mapped_column(ForeignKey("services.id"), nullable=True)
        title: Mapped[str] = mapped_column(String(180))
        description: Mapped[str] = mapped_column(Text, default="")
        cause: Mapped[str] = mapped_column(Text, default="")
        corrective_action: Mapped[str] = mapped_column(Text, default="")
        status: Mapped[str] = mapped_column(String(30), default="Aberta")
        responsible_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
        due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
        closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
        created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    Base.metadata.create_all(engine)

    @app.get("/qualidade")
    @auth
    @manager
    def qualidade():
        with SessionLocal() as db:
            issues = db.query(QualityIssue).order_by(QualityIssue.created_at.desc()).all()
            services = db.query(Service).order_by(Service.created_at.desc()).limit(50).all()
            products = db.query(Product).order_by(Product.name).all()
            abertas = sum(i.status == "Aberta" for i in issues)
            andamento = sum(i.status == "Em andamento" for i in issues)
            encerradas = sum(i.status == "Encerrada" for i in issues)
        return render_template_string(PAGE, issues=issues, services=services, products=products,
                                      abertas=abertas, andamento=andamento, encerradas=encerradas)

    @app.post("/qualidade/nova")
    @auth
    @manager
    def nova_ocorrencia():
        title = request.form.get("title", "").strip()
        if not title:
            flash("Informe o título da ocorrência.")
            return redirect("/qualidade")
        due = request.form.get("due_date") or None
        due_date = datetime.fromisoformat(due) if due else None
        with SessionLocal() as db:
            issue = QualityIssue(
                service_id=request.form.get("service_id") or None,
                title=title,
                description=request.form.get("description", "").strip(),
                cause=request.form.get("cause", "").strip(),
                corrective_action=request.form.get("corrective_action", "").strip(),
                due_date=due_date,
                responsible_id=request.form.get("responsible_id") or None,
            )
            db.add(issue)
            log(db, "CRIAR_NAO_CONFORMIDADE", title)
            db.commit()
        return redirect("/qualidade")

    @app.post("/qualidade/<int:issue_id>/encerrar")
    @auth
    @manager
    def encerrar_ocorrencia(issue_id):
        with SessionLocal() as db:
            issue = db.get(QualityIssue, issue_id)
            if not issue:
                return redirect("/qualidade")
            issue.status = "Encerrada"
            issue.closed_at = datetime.utcnow()
            log(db, "ENCERRAR_NAO_CONFORMIDADE", f"#{issue.id} {issue.title}")
            db.commit()
        return redirect("/qualidade")

    if not any(rule.rule == "/qualidade" for rule in app.url_map.iter_rules()):
        app.register_blueprint(iso_bp)


PAGE = """
<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Qualidade | ISO 9001</title>
<style>body{font-family:Arial;background:#f4f7f2;color:#172218;margin:0;padding:28px}.wrap{max-width:1200px;margin:auto}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:15px}.card,.panel{background:white;border:1px solid #dfe8dc;border-radius:14px;padding:18px;margin:15px 0}.num{font-size:30px;font-weight:900}.muted{color:#6d7c6a}input,textarea,select{width:100%;padding:10px;margin:5px 0 12px;box-sizing:border-box;border:1px solid #cbd7c7;border-radius:8px}.btn{padding:10px 14px;border:0;border-radius:8px;background:#173817;color:white;cursor:pointer}table{width:100%;border-collapse:collapse}th,td{padding:10px;border-bottom:1px solid #e5ebe3;text-align:left;vertical-align:top}@media(max-width:700px){.cards{grid-template-columns:1fr}}</style></head>
<body><div class="wrap"><a href="/dashboard">← Dashboard</a><h1>Gestão da Qualidade — ISO 9001</h1>
<p class="muted">Painel de rastreabilidade, não conformidades e ações corretivas.</p>
<div class="cards"><div class="card"><div class="num">{{abertas}}</div>Não conformidades abertas</div><div class="card"><div class="num">{{andamento}}</div>Em andamento</div><div class="card"><div class="num">{{encerradas}}</div>Encerradas</div></div>
<div class="panel"><h2>Registrar ocorrência</h2><form method="post" action="/qualidade/nova"><label>Título<input name="title" required placeholder="Ex.: equipamento retornou com falha"></label><label>Ordem de serviço<select name="service_id"><option value="">Sem OS vinculada</option>{% for s in services %}<option value="{{s.id}}">OS-{{'%05d'%s.id}} — {{s.client or 'Sem cliente'}}</option>{% endfor %}</select></label><label>Descrição<textarea name="description" rows="3"></textarea></label><label>Causa identificada<textarea name="cause" rows="3"></textarea></label><label>Ação corretiva<textarea name="corrective_action" rows="3"></textarea></label><label>Prazo<input type="datetime-local" name="due_date"></label><button class="btn">Registrar</button></form></div>
<div class="panel"><h2>Rastreabilidade das ocorrências</h2><table><tr><th>ID</th><th>Ocorrência</th><th>OS</th><th>Causa</th><th>Ação corretiva</th><th>Status</th><th>Data</th><th></th></tr>{% for i in issues %}<tr><td>#{{i.id}}</td><td>{{i.title}}<br><span class="muted">{{i.description}}</span></td><td>{{('OS-%05d'%i.service_id) if i.service_id else '-'}}</td><td>{{i.cause or '-'}}</td><td>{{i.corrective_action or '-'}}</td><td>{{i.status}}</td><td>{{i.created_at.strftime('%d/%m/%Y %H:%M')}}</td><td>{% if i.status != 'Encerrada' %}<form method="post" action="/qualidade/{{i.id}}/encerrar"><button class="btn">Encerrar</button></form>{% endif %}</td></tr>{% else %}<tr><td colspan="8">Nenhuma ocorrência registrada.</td></tr>{% endfor %}</table></div>
</div></body></html>
"""
