# PITBULL SLOTS BOT — V2 AVANÇADA

## Proteção de dados
- Nunca apague `database.db` para corrigir um erro de código.
- O módulo `manutencao.py` cria backup automático do banco na inicialização e mantém os 10 backups mais recentes.
- Novas tabelas são criadas com `CREATE TABLE IF NOT EXISTS`, preservando usuários, indicações, saldos, saques e tickets existentes.
- `/backup` cria um backup manual.
- `/erros` mostra os últimos erros registrados.
- `/manutencao on` e `/manutencao off` ativam/desativam o modo de manutenção administrativo.

## Economia avançada
- VIP, Coins e Gemas
- Roleta diária
- Caixas surpresa
- Loja
- Inventário
- Clãs
- Campanhas
- Relatórios

## Comandos administrativos
- `/backup`
- `/erros`
- `/manutencao on` / `/manutencao off`
- `/economia coins ID VALOR`
- `/economia gemas ID VALOR`
- `/economia caixas ID VALOR`
- `/campanha NOME RECOMPENSA DESCRICAO`
- `/campanhas`
- `/relatorio`

## Importante
Esta proteção preserva os dados, mas não corrige automaticamente um erro de programação. Se o código tiver um bug, o procedimento correto é identificar o erro, corrigir o arquivo e fazer deploy mantendo o mesmo `database.db`. O backup permite restaurar os dados caso uma migração dê problema.
