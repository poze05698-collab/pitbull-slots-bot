# PIT BONUS BOT — V2 AVANÇADA

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


## 💳 VIP com Mercado Pago (Pix automático)

A versão atual permite vender o VIP por Pix usando a API oficial do Mercado Pago. O bot cria a cobrança, mostra o Pix Copia e Cola e acompanha o pagamento automaticamente. Quando o Mercado Pago confirma `approved`, o sistema gera um código VIP de uso único; o usuário ainda precisa resgatar o código no botão `🎟️ Código Promocional`. A IA não decide se um pagamento foi aprovado.

### Configuração

1. No Mercado Pago, abra **Suas integrações** e crie/abra uma aplicação.
2. Entre em **Credenciais de produção** e copie o **Access Token**.
3. No `config.py`, preencha `MERCADOPAGO_ACCESS_TOKEN`.
4. Nunca publique esse token no GitHub e nunca envie o token pelo Telegram.
5. Faça primeiro um teste com as credenciais/ambiente de teste antes de receber pagamentos reais.

O código usa `X-Idempotency-Key` nas criações de pagamento e consulta os pagamentos pendentes automaticamente.
