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
# INICIAR BOT
# ==========================================

print("Bot iniciado com sucesso.")

bot.infinity_polling(
    skip_pending=True
)
