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

    print("========== NOVO MEMBRO ==========")
    print(message.json)

    for membro in message.new_chat_members:

        if membro.is_bot:
            continue

        print(f"ID: {membro.id}")
        print(f"NOME: {membro.first_name}")

# ==========================================
# CRIAR LINK DE CONVITE
# ==========================================

@bot.message_handler(commands=["criarlink"])
def criar_link_teste(message):

    try:

        chat = bot.get_chat(GRUPO_ID)

        convite = bot.create_chat_invite_link(
            chat_id=GRUPO_ID
        )

        bot.send_message(
            message.chat.id,
            f"""
Grupo:
{chat.title}

Link:

{convite.invite_link}
"""
        )

    except Exception as erro:

        bot.send_message(
            message.chat.id,
            str(erro)
        )

# ==========================================
# INICIAR BOT
# ==========================================

print("Bot iniciado com sucesso.")

bot.infinity_polling(
    skip_pending=True
)
