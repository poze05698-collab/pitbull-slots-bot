from telebot import types

from database import conn, cursor

from teclado import menu_principal

from utils import (
    data_atual,
    dinheiro,
    saldo_usuario,
    saldo_pendente,
    saque_pendente,
    buscar_pix,
    registrar_historico
)

from config import (
    VALOR_INDICACAO,
    VALOR_MINIMO_SAQUE
)

from antifraude import usuario_banido

from indicacoes import (
    gerar_link,
    indicacoes_usuario
)

from config import GRUPO_ID
from telebot.apihelper import ApiTelegramException

# ==========================================
# CADASTRAR USUÁRIO
# ==========================================

def cadastrar_usuario(message):

    user_id = message.from_user.id
    nome = message.from_user.first_name
    username = message.from_user.username

    cursor.execute(
        "SELECT id FROM usuarios WHERE id=?",
        (user_id,)
    )

    usuario = cursor.fetchone()

    if usuario is None:

        cursor.execute(
            """
            INSERT INTO usuarios
            (
                id,
                nome,
                username,
                saldo,
                saldo_pendente,
                saque_pendente,
                pix,
                banido,
                data_cadastro,
                ultimo_acesso
            )

            VALUES

            (?, ?, ?, 0, 0, 0, '', 0, ?, ?)

            """,

            (

                user_id,

                nome,

                username,

                data_atual(),

                data_atual()

            )

        )

        conn.commit()

        registrar_historico(

            user_id,

            "CADASTRO",

            "Usuário cadastrado"

        )

    else:

        cursor.execute(

            """
            UPDATE usuarios

            SET

            nome=?,

            username=?,

            ultimo_acesso=?

            WHERE id=?

            """,

            (

                nome,

                username,

                data_atual(),

                user_id

            )

        )

        conn.commit()

# ==========================================
# PERFIL
# ==========================================

def perfil_usuario(user_id):

    cursor.execute(
        """
        SELECT

        nome,

        username,

        pix,

        data_cadastro

        FROM usuarios

        WHERE id=?

        """,

        (user_id,)

    )

    return cursor.fetchone()

# ==========================================
# REGISTRAR
# ==========================================

def registrar(bot):

    @bot.message_handler(func=lambda m: m.text == "👤 Perfil")
    def perfil(message):

        if usuario_banido(message.from_user.id):

            bot.send_message(

                message.chat.id,

                "❌ Você está bloqueado."

            )

            return

        dados = perfil_usuario(

            message.from_user.id

        )

        texto = f"""
👤 <b>SEU PERFIL</b>

🆔 ID:

<code>{message.from_user.id}</code>

👤 Nome:

{dados[0]}

📱 Username:

@{dados[1] if dados[1] else 'Sem username'}

💰 Saldo:

{dinheiro(saldo_usuario(message.from_user.id))}

⏳ Saldo pendente:

{dinheiro(saldo_pendente(message.from_user.id))}

💸 Saque pendente:

{dinheiro(saque_pendente(message.from_user.id))}

💳 PIX:

{dados[2] if dados[2] else 'Não cadastrada'}

📅 Cadastro:

{dados[3]}
"""

        bot.send_message(

            message.chat.id,

            texto,

            parse_mode="HTML"

        )

# ==========================================
# SALDO
# ==========================================

    @bot.message_handler(func=lambda m: m.text == "💰 Saldo")
    def saldo(message):

        if usuario_banido(message.from_user.id):

            bot.send_message(
                message.chat.id,
                "❌ Você está bloqueado."
            )

            return

        disponivel = saldo_usuario(message.from_user.id)
        pendente = saldo_pendente(message.from_user.id)
        saque = saque_pendente(message.from_user.id)

        bot.send_message(

            message.chat.id,

            f"""
💰 <b>SEU SALDO</b>

━━━━━━━━━━━━━━

💵 Disponível:

{dinheiro(disponivel)}

━━━━━━━━━━━━━━

⏳ Pendente:

{dinheiro(pendente)}

━━━━━━━━━━━━━━

💸 Em saque:

{dinheiro(saque)}
""",

            parse_mode="HTML"

        )


# ==========================================
# HISTÓRICO
# ==========================================

    @bot.message_handler(func=lambda m: m.text == "📜 Histórico")
    def historico(message):

        cursor.execute(

            """
            SELECT

            tipo,

            descricao,

            valor,

            data

            FROM historico

            WHERE usuario_id=?

            ORDER BY id DESC

            LIMIT 15

            """,

            (message.from_user.id,)

        )

        registros = cursor.fetchall()

        if not registros:

            bot.send_message(

                message.chat.id,

                "📭 Você ainda não possui histórico."

            )

            return

        texto = "📜 <b>ÚLTIMAS MOVIMENTAÇÕES</b>\n\n"

        for tipo, descricao, valor, data in registros:

            texto += (
                f"📌 <b>{tipo}</b>\n"
                f"{descricao}\n"
                f"💰 {dinheiro(valor)}\n"
                f"📅 {data}\n\n"
            )

        bot.send_message(

            message.chat.id,

            texto,

            parse_mode="HTML"

        )


# ==========================================
# REGRAS
# ==========================================

    @bot.message_handler(func=lambda m: m.text == "📖 Regras")
    def regras(message):

        bot.send_message(

            message.chat.id,

            f"""
📖 <b>REGRAS</b>

• Convide amigos utilizando seu link.

• O amigo deve entrar no grupo.

• A indicação ficará pendente.

• O administrador analisará a indicação.

• Após aprovada, o saldo ficará disponível.

• Valor por indicação:
{dinheiro(VALOR_INDICACAO)}

• Saque mínimo:
{dinheiro(VALOR_MINIMO_SAQUE)}

Fraudes resultam em banimento.
""",

            parse_mode="HTML"

        )


# ==========================================
# INFORMAÇÕES
# ==========================================

    @bot.message_handler(func=lambda m: m.text == "ℹ️ Informações")
    def informacoes(message):

        bot.send_message(

            message.chat.id,

            """
ℹ️ <b>INFORMAÇÕES</b>

Este bot recompensa usuários que convidam novos membros para o grupo.

Caso tenha dúvidas, utilize o menu:

🎫 Suporte

Nossa equipe responderá o mais rápido possível.
""",

            parse_mode="HTML"

        )

# ==========================================
# MEU LINK
# ==========================================

    @bot.message_handler(func=lambda m: m.text == "🔗 Meu Link")
    def meu_link(message):

        if usuario_banido(message.from_user.id):

            bot.send_message(
                message.chat.id,
                "❌ Você está bloqueado."
            )

            return

        link = gerar_link(message.from_user.id)

if not link:

    bot.send_message(
        message.chat.id,
        "⏳ Seu link ainda não foi gerado."
    )

    return

        bot.send_message(
            message.chat.id,
            f"""
🔗 <b>SEU LINK DE CONVITE</b>

Compartilhe este link:

<code>{link}</code>
""",
            parse_mode="HTML"
        )


# ==========================================
# MINHAS INDICAÇÕES
# ==========================================

    @bot.message_handler(func=lambda m: m.text == "👥 Minhas Indicações")
    def minhas_indicacoes(message):

        lista = indicacoes_usuario(
            message.from_user.id
        )

        if not lista:

            bot.send_message(

                message.chat.id,

                """
👥 Você ainda não possui indicações.
"""

            )

            return

        texto = "👥 <b>SUAS INDICAÇÕES</b>\n\n"

        for indicado, valor, status, grupo, data in lista:

            grupo = "✅ Sim" if grupo else "❌ Não"

            texto += f"""
━━━━━━━━━━━━━━

👤 ID:

<code>{indicado}</code>

💰 Valor:

{dinheiro(valor)}

📌 Status:

{status}

👥 Grupo:

{grupo}

📅 Data:

{data}

"""

        bot.send_message(

            message.chat.id,

            texto,

            parse_mode="HTML"

        )


# ==========================================
# MENU
# ==========================================

    @bot.message_handler(commands=["menu"])
    def menu(message):

        bot.send_message(

            message.chat.id,

            """
🏠 Menu Principal
""",

            reply_markup=menu_principal()

        )
