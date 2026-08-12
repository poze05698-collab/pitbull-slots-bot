import telebot

from config import TOKEN

# LINK OFICIAL DO GRUPO USADO PELO BOTAO ENTRAR NO GRUPO
GRUPO_LINK_BOTAO = "https://t.me/PITBULLPRIME1"

from telebot import types

from teclado import menu_principal

from usuario import (
    registrar as registrar_usuario,
    cadastrar_usuario
)

from tickets import registrar as registrar_tickets
from gamificacao import registrar as registrar_gamificacao, registrar_atividade
from avancado import registrar as registrar_avancado
from manutencao import registrar as registrar_manutencao, registrar_erro, preparar as preparar_manutencao

from saques import registrar as registrar_saques

from admin import registrar as registrar_admin

from database import conn, cursor

from config import GRUPO_ID
from indicacoes import (
    registrar_indicacao,
    confirmar_entrada_grupo,
    buscar_dono_convite,
    buscar_por_indicado
)
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

preparar_manutencao()
preparar_premium()
registrar_manutencao(bot)

registrar_usuario(bot)

registrar_tickets(bot)
registrar_gamificacao(bot)
registrar_avancado(bot)
registrar_premium(bot)
registrar_painel_extra(bot)

registrar_saques(bot)

registrar_admin(bot)


# ==========================================
# START
# ==========================================

@bot.message_handler(commands=["start"])
def start(message):

    try:
        cadastrar_usuario(message)
        registrar_atividade(message.from_user.id)
    except Exception as erro:
        print("========== ERRO NO CADASTRO DO /START ==========")
        print(f"USUARIO_ID: {message.from_user.id}")
        print(f"ERRO: {erro}")
        registrar_erro("start", erro, message.from_user.id)
        # Mesmo que uma atualização de cadastro falhe, o /start continua.

    indicador_id = None

    partes = message.text.split(maxsplit=1)
    if len(partes) > 1:
        parametro = partes[1].strip()
        if parametro.startswith("ref_"):
            try:
                indicador_id = int(parametro.replace("ref_", "", 1))
            except ValueError:
                indicador_id = None

    if indicador_id:
        try:
            sucesso, retorno = registrar_indicacao(
                indicador_id,
                message.from_user.id
            )
            print("========== INDICAÇÃO NO /START ==========")
            print(f"INDICADOR_ID: {indicador_id}")
            print(f"INDICADO_ID: {message.from_user.id}")
            print(f"SUCESSO: {sucesso}")
            print(f"RETORNO: {retorno}")
        except Exception as erro:
            print("========== ERRO AO REGISTRAR INDICAÇÃO ==========")
            print(f"ERRO: {erro}")

    try:
        indicacao = buscar_por_indicado(message.from_user.id)

        mostrar_etapa_grupo = True
        mensagem_status = None

        if indicacao:
            status_indicacao = indicacao[4]
            grupo_confirmado = indicacao[5]

            if status_indicacao == "APROVADO":
                mostrar_etapa_grupo = False
            elif grupo_confirmado == 1:
                mostrar_etapa_grupo = False
                mensagem_status = """
⏳ <b>INDICAÇÃO EM ANÁLISE</b>

✅ Sua entrada no grupo já foi confirmada.

Agora basta aguardar o administrador analisar sua indicação.
"""

        if mostrar_etapa_grupo:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("👥 Entrar no Grupo", url=GRUPO_LINK_BOTAO))
            markup.add(types.InlineKeyboardButton("✅ Já entrei no grupo", callback_data="confirmar_grupo"))

            texto_start = """
🎉 <b>Bem-vindo!</b>

Seu cadastro foi realizado com sucesso.

Para validar sua indicação:

1️⃣ Entre no grupo.
2️⃣ Volte ao bot.
3️⃣ Clique em <b>✅ Já entrei no grupo</b>.
4️⃣ Aguarde a aprovação do administrador.

Após a aprovação, o saldo será liberado.
"""

            bot.send_message(
                message.chat.id,
                texto_start,
                reply_markup=markup,
                parse_mode="HTML"
            )

        elif mensagem_status:
            bot.send_message(message.chat.id, mensagem_status, parse_mode="HTML")

        else:
            bot.send_message(
                message.chat.id,
                "🎉 <b>Bem-vindo de volta!</b>\n\nSua indicação já foi processada.\n\nVocê não precisa entrar no grupo novamente.",
                parse_mode="HTML"
            )

        bot.send_message(
            message.chat.id,
            "🏠 Menu Principal",
            reply_markup=menu_principal()
        )

    except Exception as erro:
        print("========== ERRO NO /START ==========")
        print(f"USUARIO_ID: {message.from_user.id}")
        print(f"ERRO: {erro}")
        try:
            bot.send_message(
                message.chat.id,
                "🎉 <b>Bem-vindo!</b>\n\nOcorreu uma falha temporária ao carregar seu menu. Tente tocar em /start novamente.",
                parse_mode="HTML",
                reply_markup=menu_principal()
            )
        except Exception as erro2:
            print(f"ERRO AO ENVIAR FALLBACK DO /START: {erro2}")

# ==========================================
# CONFIRMAR ENTRADA NO GRUPO
# ==========================================

@bot.callback_query_handler(func=lambda call: call.data == "confirmar_grupo")
def confirmar_grupo(call):

    usuario_id = call.from_user.id

    try:

        membro = bot.get_chat_member(
            chat_id=GRUPO_ID,
            user_id=usuario_id
        )

        print("========== VERIFICAÇÃO DO GRUPO ==========")
        print(f"GRUPO_ID: {GRUPO_ID}")
        print(f"USUARIO_ID: {usuario_id}")
        print(f"STATUS: {membro.status}")

    except Exception as erro:

        print("========== ERRO AO VERIFICAR GRUPO ==========")
        print(f"GRUPO_ID: {GRUPO_ID}")
        print(f"USUARIO_ID: {usuario_id}")
        print(f"ERRO: {erro}")

        bot.answer_callback_query(
            call.id,
            "❌ Não foi possível verificar o grupo.",
            show_alert=True
        )
        return

    if membro.status in ("left", "kicked"):

        bot.answer_callback_query(
            call.id,
            f"❌ O Telegram informou que você está como: {membro.status}.",
            show_alert=True
        )
        return

    indicacao = buscar_por_indicado(
        usuario_id
    )

    # Se já confirmou anteriormente, não cria outra mensagem.
    if indicacao and indicacao[5] == 1:

        bot.answer_callback_query(
            call.id,
            "✅ Sua entrada já foi confirmada. Aguarde a análise.",
            show_alert=True
        )

        return

    confirmar_entrada_grupo(
        usuario_id
    )

    # Remove os botões antigos para impedir nova confirmação.
    try:
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )
    except Exception:
        pass

    bot.answer_callback_query(
        call.id,
        "✅ Grupo confirmado!"
    )

    bot.send_message(
        call.message.chat.id,
        """
🎉 <b>SUA ENTRADA FOI CONFIRMADA!</b>

✅ O sistema confirmou que você está no grupo.

⏳ Agora basta aguardar o administrador analisar sua indicação.

Você não precisará entrar no grupo novamente.
""",
        parse_mode="HTML"
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

        confirmar_entrada_grupo(membro.id)


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

# Diagnóstico seguro da tabela de indicações (não exibe dados pessoais).
try:
    cursor.execute("SELECT status, COUNT(*) FROM indicacoes GROUP BY status")
    print("========== STATUS DAS INDICAÇÕES ==========")
    for _status, _qtd in cursor.fetchall():
        print(f"STATUS: {_status} | QUANTIDADE: {_qtd}")
except Exception as _erro:
    print(f"ERRO AO CONSULTAR STATUS DAS INDICAÇÕES: {_erro}")

import time as _time

while True:
    try:
        bot.infinity_polling(skip_pending=True)
    except Exception as _erro:
        registrar_erro("polling", _erro)
        print("Polling interrompido. Reiniciando em 5 segundos...")
        _time.sleep(5)
