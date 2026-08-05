from telebot.types import ReplyKeyboardMarkup, KeyboardButton

# ==========================================
# MENU PRINCIPAL
# ==========================================

def menu_principal():

    menu = ReplyKeyboardMarkup(
        resize_keyboard=True,
        row_width=2
    )

    menu.add(
        KeyboardButton("👤 Perfil"),
        KeyboardButton("💰 Saldo")
    )

    menu.add(
        KeyboardButton("👥 Indicados"),
        KeyboardButton("🔗 Meu Link")
    )

    menu.add(
        KeyboardButton("💳 PIX"),
        KeyboardButton("💸 Solicitar Saque")
    )

    menu.add(
        KeyboardButton("📜 Histórico"),
        KeyboardButton("🎫 Suporte")
    )

    menu.add(
        KeyboardButton("📖 Regras"),
        KeyboardButton("ℹ️ Informações")
    )

    return menu


# ==========================================
# MENU ADMIN
# ==========================================

def menu_admin():

    menu = ReplyKeyboardMarkup(
        resize_keyboard=True,
        row_width=2
    )

    menu.add(
        KeyboardButton("📊 Estatísticas"),
        KeyboardButton("👥 Usuários")
    )

    menu.add(
        KeyboardButton("⏳ Indicações"),
        KeyboardButton("💸 Saques")
    )

    menu.add(
        KeyboardButton("🎫 Tickets"),
        KeyboardButton("🚫 Banidos")
    )

    menu.add(
        KeyboardButton("🏠 Menu Principal")
    )

    return menu
