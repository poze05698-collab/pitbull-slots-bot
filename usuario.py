from telebot import types

from database import cursor, conn
from teclado import menu_principal
from utils import (
    data_atual,
    dinheiro,
    registrar_historico,
    saldo_usuario,
    saldo_pendente
)


def cadastrar_usuario(message):

    user_id = message.from_user.id
    nome = message.from_user.first_name
    username = message.from_user.username

    cursor.execute(
        "SELECT id FROM usuarios WHERE id=?",
        (user_id,)
    )

    if cursor.fetchone() is None:

        cursor.execute(
            """
            INSERT INTO usuarios
            (
                id,
                nome,
                username,
                saldo,
                saldo_pendente,
                pix,
                banido,
                data_cadastro,
                ultimo_acesso
            )

            VALUES
            (?, ?, ?, 0, 0, '', 0, ?, ?)
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


def registrar(bot):

    @bot.message_handler(func=lambda m: m.text == "👤 Perfil")
    def perfil(message):

        cadastrar_usuario(message)

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
            (message.from_user.id,)
        )

        usuario = cursor.fetchone()

        texto = f"""
👤 <b>PERFIL</b>

🆔 ID: <code>{message.from_user.id}</code>

👤 Nome:
{usuario[0]}

📱 Username:
@{usuario[1] if usuario[1] else "Sem username"}

💰 Saldo:
{dinheiro(saldo_usuario(message.from_user.id))}

⏳ Saldo pendente:
{dinheiro(saldo_pendente(message.from_user.id))}

💳 PIX:

{usuario[2] if usuario[2] else "Não cadastrada"}

📅 Cadastro:

{usuario[3]}
"""

        bot.send_message(
            message.chat.id,
            texto,
            parse_mode="HTML"
        )


    @bot.message_handler(func=lambda m: m.text == "💰 Saldo")
    def saldo(message):

        bot.send_message(

            message.chat.id,

            f"""

💰 <b>SEU SALDO</b>

Disponível:

{dinheiro(saldo_usuario(message.from_user.id))}

Pendente:

{dinheiro(saldo_pendente(message.from_user.id))}

            """,

            parse_mode="HTML"

        )
