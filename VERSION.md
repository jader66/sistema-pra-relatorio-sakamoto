# Sakamoto — Manutenção

## Versão 1.0

**Status:** sistema consolidado para o fluxo de manutenção.

### Funcionalidades
- Login sem usuário/senha expostos na tela.
- Criação da primeira conta Administrador.
- Bloqueio temporário após várias tentativas de login.
- Administrador define cargos; Chefe e Administrador podem atribuir manutenções.
- Funcionário vê somente os trabalhos atribuídos a ele.
- Configurações para alteração da própria senha.
- Administrador pode editar cargo, status e senha dos usuários.
- Dashboard de equipamentos, pendências, manutenção, finalizados e urgentes.
- Cadastro de equipamentos que entram para manutenção.
- Fotos persistentes de produtos e ordens de serviço armazenadas no banco.
- Atribuição de manutenção somente para produto previamente cadastrado.
- Se não houver produto, aparece **Sem serviço** e o botão para cadastrar primeiro.
- Seleção do equipamento cadastrado ao criar uma manutenção.
- Prioridade **Normal**, **Pouca urgência** e **Urgente**.
- A prioridade pode ser alterada na ficha do equipamento.
- A prioridade das ordens abertas acompanha a prioridade alterada do equipamento.
- Prioridade automática aumenta conforme a ordem fica parada.
- Ficha do equipamento com status, fotos e histórico.
- Ordem de serviço com início, finalização, observações e fotos durante o conserto.
- Histórico de ações.
- Relatórios individuais para funcionário e visão completa para Chefe/Administrador.
- Filtros por período, funcionário, status e prioridade.
- Download em PDF, Excel e CSV e impressão.
- PostgreSQL persistente configurado para o Render.
- Migração de ordens antigas para o vínculo por produto.
- Render inicia o aplicativo principal `app:app`.

### Fluxo oficial
**Cadastrar equipamento → adicionar fotos → definir prioridade → abrir ficha → enviar manutenção → selecionar funcionário → iniciar → adicionar fotos → finalizar → relatório/histórico.**
