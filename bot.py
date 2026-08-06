import telebot

from config import TOKEN

from teclado import menu_principal

from usuario import (
    registrar as registrar_usuario,
    cadastrar_usuario
)

from tickets import registrar as registrar_tickets

from saques import registrar as registrar_saques

from admin import registrar as registrar_admin

from database import conn, cursor

from config import GRUPO_ID
from indicacoes import registrar_indicacao, confirmar_entrada_grupo

# ==========================================
# BOT
# ==========================================

bot = telebot.TeleBot(

    TOKEN,

    parse_mode="HTML"

)


# ==========================================
# REGISTRAR MÓDULOS
# ==========================================

registrar_usuario(bot)

registrar_tickets(bot)

registrar_saques(bot)

registrar_admin(bot)


# ==========================================
# START
# ==========================================

@bot.message_handler(commands=["start"])
def start(message):

    cadastrar_usuario(message)

    bot.send_message(

        message.chat.id,

        """
🎉 <b>Bem-vindo!</b>

Seu cadastro foi realizado com sucesso.

Use o menu abaixo para navegar pelo bot.
""",

        reply_markup=menu_principal()

    )

# ==========================================
# NOVO MEMBRO NO GRUPO
# ==========================================

@bot.message_handler(content_types=["new_chat_members"])
def novo_membro(message):

    if message.chat.id != GRUPO_ID:
        return

    for membro in message.new_chat_members:

        if membro.is_bot:
            continue

        print(f"Novo membro: {membro.id} - {membro.first_name}")

        # Nas próximas etapas vamos identificar
        # qual convite foi usado e registrar
        # automaticamente a indicação.

# ==========================================
# INICIAR BOT
# ==========================================

print("Bot iniciado com sucesso.")

bot.infinity_polling(
    skip_pending=True
)
