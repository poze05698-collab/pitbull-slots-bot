from telebot import types


# =====================================================
# MENU PRINCIPAL
# =====================================================

def menu_principal():

    teclado = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        is_persistent=True,
        row_width=2,
        input_field_placeholder="✨ Escolha uma opção..."
    )

    teclado.row(
        "👤 Perfil",
        "💰 Saldo"
    )

    teclado.row(
        "🔗 Meu Link",
        "👥 Minhas Indicações"
    )

    teclado.row(
        "💳 PIX",
        "💸 Solicitar Saque"
    )

    teclado.row(
        "🎫 Suporte",
        "📜 Histórico"
    )

    teclado.row(
        "🔔 Notificações",
        "🏆 Ranking"
    )

    teclado.row(
        "🏅 Meu Nível",
        "🎯 Missões"
    )

    teclado.row(
        "👥 Equipe",
        "🏅 Conquistas"
    )

    teclado.row(
        "🔥 Sequência",
        "🛡️ Confiança"
    )

    teclado.row(
        "🎁 Evento",
        "💎 VIP"
    )

    teclado.row(
        "🎟️ Código Promocional"
    )

    teclado.row(
        "🪙 Moedas",
        "🎰 Roleta"
    )

    teclado.row(
        "🎁 Caixa Surpresa",
        "🏪 Loja"
    )

    teclado.row(
        "🎫 Raspadinha",
        "🤝 Parceiros"
    )

    teclado.row(
        "⚔️ Clã"
    )

    teclado.row(
        "📖 Regras",
        "ℹ️ Informações"
    )

    return teclado


# =====================================================
# MENU ADMIN
# =====================================================

def menu_admin():

    teclado = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        is_persistent=True,
        row_width=2,
        input_field_placeholder="🔐 Painel administrativo..."
    )

    teclado.row(
        "🎁 Indicações",
        "💸 Saques"
    )

    teclado.row(
        "👥 Usuários",
        "🚫 Banimentos"
    )

    teclado.row(
        "📊 Estatísticas",
        "⚙️ Configurações"
    )

    teclado.row(
        "🧠 Gamificação",
        "⚙️ Configurações Avançadas"
    )

    teclado.row(
        "🛠️ Manutenção",
        "🤝 Parceiros"
    )

    teclado.row(
        "🎟️ Códigos"
    )

    teclado.row(
        "⬅️ Menu"
    )

    return teclado


# =====================================================
# CONFIRMAR
# =====================================================

def teclado_confirmacao(callback_sim, callback_nao):

    teclado = types.InlineKeyboardMarkup()

    teclado.row(

        types.InlineKeyboardButton(
            "✅ Confirmar",
            callback_data=callback_sim
        ),

        types.InlineKeyboardButton(
            "❌ Cancelar",
            callback_data=callback_nao
        )

    )

    return teclado


# =====================================================
# APROVAR / REJEITAR
# =====================================================

def teclado_aprovacao(aprovar, rejeitar):

    teclado = types.InlineKeyboardMarkup()

    teclado.row(

        types.InlineKeyboardButton(
            "✅ Aprovar",
            callback_data=aprovar
        ),

        types.InlineKeyboardButton(
            "❌ Rejeitar",
            callback_data=rejeitar
        )

    )

    return teclado


# =====================================================
# VOLTAR
# =====================================================

def teclado_voltar(callback):

    teclado = types.InlineKeyboardMarkup()

    teclado.add(

        types.InlineKeyboardButton(
            "⬅️ Voltar",
            callback_data=callback
        )

    )

    return teclado
