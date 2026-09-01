# =====================================================
# TOKEN DO BOT
# =====================================================

import os

TOKEN = "8771309444:AAEOZJdlGIWwezJsSVWENvzbplWrowt9IcY"
# Se futuramente quiser proteger o token, troque para os.getenv("BOT_TOKEN", "")


# =====================================================
# ADMINISTRADOR
# =====================================================

ADMIN_ID = 6172813641


# =====================================================
# BOT
# =====================================================

BOT_USERNAME = "PITBULL_SLOTS_BOT"


# =====================================================
# GRUPO
# =====================================================

GRUPO_ID = -1003355182545

GRUPO_LINK = "https://t.me/PITBULLPRIME1"


# =====================================================
# VALORES
# =====================================================

VALOR_INDICACAO = 1.00

VALOR_MINIMO_SAQUE = 20.00


# =====================================================
# STATUS
# =====================================================

STATUS_PENDENTE = "PENDENTE"

STATUS_APROVADO = "APROVADO"

STATUS_REJEITADO = "REJEITADO"

STATUS_ABERTO = "ABERTO"

STATUS_FECHADO = "FECHADO"

STATUS_RESPONDIDO = "RESPONDIDO"


# =====================================================
# CONFIGURAÇÕES
# =====================================================

ANTI_FRAUDE = True

GRUPO_OBRIGATORIO = True

PIX_OBRIGATORIO = True


# =====================================================
# SUPORTE
# =====================================================

SUPORTE = "@PitbullSlots011"

# =====================================================
# IA DO SUPORTE — GEMINI FREE TIER
# =====================================================
# Coloque aqui a chave criada gratuitamente no Google AI Studio.
# Se ficar vazia, o bot continua funcionando e usa respostas locais
# de fallback, sem bloquear o suporte.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Modelo rápido para atendimento. O uso gratuito depende da cota
# gratuita vigente da API; não é ilimitado.
GEMINI_MODEL = "gemini-3.5-flash-lite"

IA_SUPORTE_ATIVA = True
IA_MAX_MENSAGEM = 2000
IA_TIMEOUT = 12
IA_COOLDOWN_SEGUNDOS = 8

# =====================================================
# MERCADO PAGO — VIP ONLINE
# =====================================================
# Gere o Access Token em Mercado Pago > Suas integrações > Credenciais de produção.
# NUNCA publique este token no GitHub ou envie pelo Telegram.
MERCADOPAGO_ACCESS_TOKEN = os.getenv("MERCADOPAGO_ACCESS_TOKEN", "")
MERCADOPAGO_VIP_ATIVO = True
MERCADOPAGO_POLL_INTERVAL = 30
