# Sakamoto — Manutenção

## Versão 1.0

**Status:** versão principal do sistema.

### Funcionalidades aplicadas no GitHub
- Login profissional.
- Criação da primeira conta Administrador pelo menu de login.
- Perfis Administrador, Chefe e Funcionário.
- Administrador e Chefe podem atribuir manutenções.
- Usuários e permissões.
- Dashboard e menu empresarial.
- Cadastro de equipamentos/produtos que entram para manutenção.
- Atribuição de manutenção somente para produto previamente cadastrado.
- Se não houver produto cadastrado, a tela de envio informa **Sem serviço** e oferece o cadastro do produto.
- Seleção do produto cadastrado ao criar uma manutenção.
- Prioridade por produto: **Normal**, **Pouca urgência** e **Urgente**.
- Alteração da prioridade diretamente na ficha do produto.
- Atualização da prioridade das ordens abertas/em andamento quando a prioridade do produto é alterada.
- Ficha do produto com status e histórico de manutenções.
- Ordens de serviço e acompanhamento.
- Relatórios e histórico de ações.
- PostgreSQL configurado para o ambiente Render.
- Deploy do Render configurado para iniciar pelo módulo `photo_app.py`.

### Regra principal da manutenção
**Cadastrar equipamento → abrir ficha → definir prioridade → enviar manutenção → selecionar funcionário → executar → finalizar → manter histórico.**

A versão 1.0 é o marco oficial para as próximas evoluções do Sistema Sakamoto.