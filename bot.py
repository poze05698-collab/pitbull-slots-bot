import telebot

from config import TOKEN, GRUPO_LINK

from telebot import types

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

    indicador_id = None

    if len(message.text.split()) > 1:

        parametro = message.text.split()[1]

        if parametro.startswith("ref_"):

            try:
                indicador_id = int(
                    parametro.replace("ref_", "")
                )

            except:
                indicador_id = None

    if indicador_id:

        registrar_indicacao(
            indicador_id,
            message.from_user.id
        )

    markup = types.InlineKeyboardMarkup()

    markup.add(
        types.InlineKeyboardButton(
            "👥 Entrar no Grupo",
            url=GRUPO_LINK
        )
    )

    bot.send_message(
        message.chat.id,
        """
🎉 <b>Bem-vindo!</b>

Seu cadastro foi realizado com sucesso.

Para validar sua indicação:

1️⃣ Entre no grupo.

2️⃣ Depois volte ao bot.

3️⃣ O administrador analisará sua indicação.

Após a aprovação, o saldo será liberado.
""",
        reply_markup=markup,
        parse_mode="HTML"
    )

    bot.send_message(
        message.chat.id,
        "🏠 Menu Principal",
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

resultado = confirmar_entrada_grupo(membro.id)

print(f"CONFIRMOU O GRUPO? {resultado}")


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
