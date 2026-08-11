from telebot import types

from config import (
    ADMIN_ID,
    STATUS_PENDENTE,
    GRUPO_ID
)

from database import cursor

from utils import (
    eh_admin,
    dinheiro
)

from indicacoes import (
    aprovar_indicacao,
    rejeitar_indicacao
)

from saques import (
    aprovar_saque,
    rejeitar_saque,
    listar_saques_pendentes
)

from antifraude import (
    banir_usuario,
    desbanir_usuario
)


# ==========================================
# VERIFICAR ADMIN
# ==========================================

def admin_autorizado(user_id):

    return eh_admin(user_id)


# ==========================================
# REGISTRAR
# ==========================================

def registrar(bot):

    # ==========================================
    # PAINEL ADMIN
    # ==========================================

    @bot.message_handler(commands=["admin"])
    def painel_admin(message):

        if not admin_autorizado(message.from_user.id):

            bot.reply_to(
                message,
                "❌ Você não possui permissão."
            )

            return

        teclado = types.ReplyKeyboardMarkup(
            resize_keyboard=True
        )

        teclado.row(
            "🎁 Indicações",
            "💸 Saques"
        )

        teclado.row(
            "👥 Usuários",
            "📊 Estatísticas"
        )

        teclado.row(
            "🚫 Banimentos",
            "⬅️ Menu"
        )

        bot.send_message(

            message.chat.id,

            """
🔐 <b>PAINEL ADMINISTRATIVO</b>

Escolha uma opção.
""",

            parse_mode="HTML",

            reply_markup=teclado

        )

    # ==========================================
    # INDICAÇÕES PENDENTES
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "🎁 Indicações")
    def listar_indicacoes(message):

        if not admin_autorizado(message.from_user.id):
            return

        cursor.execute(
            """
            SELECT
                i.id,
                u1.nome,
                u2.nome,
                i.valor,
                i.data,
                i.grupo_confirmado
            FROM indicacoes i
            JOIN usuarios u1
                ON u1.id = i.indicador_id
            JOIN usuarios u2
                ON u2.id = i.indicado_id
            WHERE i.status=?
            ORDER BY i.id
            """,
            (STATUS_PENDENTE,)
        )

        lista = cursor.fetchall()

        if not lista:

            bot.send_message(
                message.chat.id,
                "✅ Não existem indicações pendentes."
            )

            return

        for item in lista:

            teclado = types.InlineKeyboardMarkup()

            teclado.row(

                types.InlineKeyboardButton(
                    "✅ Aprovar",
                    callback_data=f"aprovar_indicacao:{item[0]}"
                ),

                types.InlineKeyboardButton(
                    "❌ Rejeitar",
                    callback_data=f"rejeitar_indicacao:{item[0]}"
                )

            )

            grupo = "✅ Sim" if item[5] else "❌ Não"

            bot.send_message(

                message.chat.id,

                f"""
🎁 <b>INDICAÇÃO #{item[0]}</b>

👤 Indicador:
{item[1]}

👤 Indicado:
{item[2]}

💰 Valor:
{dinheiro(item[3])}

👥 Entrou no grupo?
{grupo}

📅 Data:
{item[4]}
""",

                parse_mode="HTML",

                reply_markup=teclado

            )

        # ==========================================
    # APROVAR INDICAÇÃO
    # ==========================================

    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("aprovar_indicacao:")
    )
    def callback_aprovar_indicacao(call):

        if not admin_autorizado(call.from_user.id):
            bot.answer_callback_query(
                call.id,
                "Sem permissão.",
                show_alert=True
            )
            return

        indicacao_id = int(call.data.split(":")[1])

        cursor.execute(
            """
            SELECT indicado_id
            FROM indicacoes
            WHERE id=?
            """,
            (indicacao_id,)
        )

        resultado = cursor.fetchone()

        if resultado is None:
            bot.answer_callback_query(
                call.id,
                "Indicação não encontrada.",
                show_alert=True
            )
            return

        indicado_id = resultado[0]

        try:
            membro = bot.get_chat_member(GRUPO_ID, indicado_id)

            if membro.status in ("left", "kicked"):
                bot.answer_callback_query(
                    call.id,
                    "❌ O usuário ainda não entrou no grupo.",
                    show_alert=True
                )
                return

        except Exception:
            bot.answer_callback_query(
                call.id,
                "❌ Não foi possível verificar o grupo.",
                show_alert=True
            )
            return

        sucesso, retorno = aprovar_indicacao(
            indicacao_id,
            call.from_user.id
        )

        if not sucesso:
            bot.answer_callback_query(
                call.id,
                retorno,
                show_alert=True
            )
            return

        usuario_id = retorno

        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )

        bot.send_message(
            call.message.chat.id,
            "✅ Indicação aprovada com sucesso."
        )

        try:
            bot.send_message(
                usuario_id,
                """
🎉 Sua indicação foi aprovada!

O valor já está disponível em seu saldo.
"""
            )
        except Exception:
            pass

        bot.answer_callback_query(call.id)

    # ==========================================
    # REJEITAR INDICAÇÃO
    # ==========================================

    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("rejeitar_indicacao:")
    )
    def callback_rejeitar_indicacao(call):

        if not admin_autorizado(call.from_user.id):

            bot.answer_callback_query(
                call.id,
                "Sem permissão.",
                show_alert=True
            )

            return

        indicacao_id = int(call.data.split(":")[1])

        motivo = "Rejeitada pelo administrador"

        sucesso, retorno = rejeitar_indicacao(
            indicacao_id,
            call.from_user.id,
            motivo
        )

        if not sucesso:

            bot.answer_callback_query(
                call.id,
                retorno,
                show_alert=True
            )

            return

        usuario_id = retorno

        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )

        bot.send_message(
            call.message.chat.id,
            "❌ Indicação rejeitada."
        )

        try:

            bot.send_message(
                usuario_id,
                f"""
❌ Sua indicação foi rejeitada.

Motivo:

{motivo}
"""
            )

        except:
            pass

        bot.answer_callback_query(call.id)

    # ==========================================
    # SAQUES PENDENTES
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "💸 Saques")
    def listar_saques(message):

        if not admin_autorizado(message.from_user.id):
            return

        saques = listar_saques_pendentes()

        if not saques:

            bot.send_message(
                message.chat.id,
                "✅ Não existem saques pendentes."
            )

            return

        for saque in saques:

            teclado = types.InlineKeyboardMarkup()

            teclado.row(

                types.InlineKeyboardButton(
                    "✅ Aprovar",
                    callback_data=f"aprovar_saque:{saque[0]}"
                ),

                types.InlineKeyboardButton(
                    "❌ Rejeitar",
                    callback_data=f"rejeitar_saque:{saque[0]}"
                )

            )

            bot.send_message(

                message.chat.id,

                f"""
💸 <b>SAQUE #{saque[0]}</b>

👤 Usuário:

<code>{saque[1]}</code>

💰 Valor:

{dinheiro(saque[2])}

💳 PIX:

<code>{saque[3]}</code>

📅 Data:

{saque[4]}
""",

                parse_mode="HTML",

                reply_markup=teclado

            )

    # ==========================================
    # APROVAR SAQUE
    # ==========================================

    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("aprovar_saque:")
    )
    def callback_aprovar_saque(call):

        if not admin_autorizado(call.from_user.id):

            bot.answer_callback_query(
                call.id,
                "Sem permissão.",
                show_alert=True
            )

            return

        saque_id = int(call.data.split(":")[1])

        sucesso, retorno = aprovar_saque(
            saque_id,
            call.from_user.id
        )

        if not sucesso:

            bot.answer_callback_query(
                call.id,
                retorno,
                show_alert=True
            )

            return

        usuario_id = retorno

        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )

        bot.send_message(
            call.message.chat.id,
            "✅ Saque aprovado com sucesso."
        )

        try:

            bot.send_message(

                usuario_id,

                """
🎉 Seu saque foi aprovado!

Em breve o pagamento será realizado.
"""

            )

        except:
            pass

        bot.answer_callback_query(call.id)

    # ==========================================
    # REJEITAR SAQUE
    # ==========================================

    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("rejeitar_saque:")
    )
    def callback_rejeitar_saque(call):

        if not admin_autorizado(call.from_user.id):

            bot.answer_callback_query(
                call.id,
                "Sem permissão.",
                show_alert=True
            )

            return

        saque_id = int(call.data.split(":")[1])

        motivo = "Rejeitado pelo administrador"

        sucesso, retorno = rejeitar_saque(
            saque_id,
            call.from_user.id,
            motivo
        )

        if not sucesso:

            bot.answer_callback_query(
                call.id,
                retorno,
                show_alert=True
            )

            return

        usuario_id = retorno

        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )

        bot.send_message(
            call.message.chat.id,
            "❌ Saque rejeitado."
        )

        try:

            bot.send_message(

                usuario_id,

                f"""
❌ Seu saque foi rejeitado.

Motivo:

{motivo}
"""

            )

        except:
            pass

        bot.answer_callback_query(call.id)

    # ==========================================
    # USUÁRIOS
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "👥 Usuários")
    def listar_usuarios(message):

        if not admin_autorizado(message.from_user.id):
            return

        cursor.execute(
            """
            SELECT
                id,
                nome,
                username,
                saldo,
                banido,
                data_cadastro
            FROM usuarios
            ORDER BY id DESC
            LIMIT 30
            """
        )

        usuarios = cursor.fetchall()

        if not usuarios:

            bot.send_message(
                message.chat.id,
                "📭 Nenhum usuário cadastrado."
            )

            return

        cursor.execute(
            "SELECT COUNT(*) FROM usuarios"
        )

        total = cursor.fetchone()[0]

        bot.send_message(
            message.chat.id,
            f"""
👥 <b>GERENCIAMENTO DE USUÁRIOS</b>

📊 Total cadastrado: <b>{total}</b>

Mostrando os últimos 30 usuários.
""",
            parse_mode="HTML"
        )

        for usuario_id, nome, username, saldo, banido, data_cadastro in usuarios:

            status = "🚫 BANIDO" if banido else "🟢 ATIVO"

            markup = types.InlineKeyboardMarkup()

            if banido:

                markup.row(
                    types.InlineKeyboardButton(
                        "✅ Desbanir",
                        callback_data=f"usuario_unban:{usuario_id}"
                    )
                )

            else:

                markup.row(
                    types.InlineKeyboardButton(
                        "🚫 Banir",
                        callback_data=f"usuario_ban:{usuario_id}"
                    )
                )

            markup.row(
                types.InlineKeyboardButton(
                    "🔄 Atualizar",
                    callback_data=f"usuario_atualizar:{usuario_id}"
                )
            )

            bot.send_message(
                message.chat.id,
                f"""
👤 <b>USUÁRIO</b>

🆔 ID:
<code>{usuario_id}</code>

👤 Nome:
{nome or "Sem nome"}

📱 Username:
@{username if username else "Sem username"}

💰 Saldo:
{dinheiro(saldo or 0)}

📌 Status:
{status}

📅 Cadastro:
{data_cadastro}
""",
                parse_mode="HTML",
                reply_markup=markup
            )


    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("usuario_ban:")
    )
    def callback_ban_usuario(call):

        if not admin_autorizado(call.from_user.id):
            bot.answer_callback_query(
                call.id,
                "Sem permissão.",
                show_alert=True
            )
            return

        usuario_id = int(
            call.data.split(":")[1]
        )

        if usuario_id == ADMIN_ID:
            bot.answer_callback_query(
                call.id,
                "❌ Você não pode banir o administrador.",
                show_alert=True
            )
            return

        sucesso = banir_usuario(usuario_id)

        if sucesso:

            bot.answer_callback_query(
                call.id,
                "Usuário banido."
            )

            try:
                bot.send_message(
                    usuario_id,
                    "🚫 <b>Você foi bloqueado.</b>\n\nSeu acesso ao bot foi suspenso pelo administrador.",
                    parse_mode="HTML"
                )
            except Exception:
                pass

            atualizar_card_usuario(
                bot,
                call.message.chat.id,
                call.message.message_id,
                usuario_id
            )

        else:

            bot.answer_callback_query(
                call.id,
                "Não foi possível banir.",
                show_alert=True
            )


    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("usuario_unban:")
    )
    def callback_unban_usuario(call):

        if not admin_autorizado(call.from_user.id):
            bot.answer_callback_query(
                call.id,
                "Sem permissão.",
                show_alert=True
            )
            return

        usuario_id = int(
            call.data.split(":")[1]
        )

        sucesso = desbanir_usuario(usuario_id)

        if sucesso:

            bot.answer_callback_query(
                call.id,
                "Usuário desbanido."
            )

            try:
                bot.send_message(
                    usuario_id,
                    "✅ <b>Seu acesso ao bot foi liberado novamente.</b>",
                    parse_mode="HTML"
                )
            except Exception:
                pass

            atualizar_card_usuario(
                bot,
                call.message.chat.id,
                call.message.message_id,
                usuario_id
            )

        else:

            bot.answer_callback_query(
                call.id,
                "Não foi possível desbanir.",
                show_alert=True
            )


    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("usuario_atualizar:")
    )
    def callback_atualizar_usuario(call):

        if not admin_autorizado(call.from_user.id):
            bot.answer_callback_query(
                call.id,
                "Sem permissão.",
                show_alert=True
            )
            return

        usuario_id = int(
            call.data.split(":")[1]
        )

        atualizar_card_usuario(
            bot,
            call.message.chat.id,
            call.message.message_id,
            usuario_id
        )

        bot.answer_callback_query(
            call.id,
            "Dados atualizados."
        )


    def atualizar_card_usuario(
        bot,
        chat_id,
        message_id,
        usuario_id
    ):

        cursor.execute(
            """
            SELECT
                id,
                nome,
                username,
                saldo,
                banido,
                data_cadastro
            FROM usuarios
            WHERE id=?
            """,
            (usuario_id,)
        )

        usuario = cursor.fetchone()

        if not usuario:
            return

        uid, nome, username, saldo, banido, data_cadastro = usuario

        status = "🚫 BANIDO" if banido else "🟢 ATIVO"

        markup = types.InlineKeyboardMarkup()

        if banido:

            markup.row(
                types.InlineKeyboardButton(
                    "✅ Desbanir",
                    callback_data=f"usuario_unban:{uid}"
                )
            )

        else:

            markup.row(
                types.InlineKeyboardButton(
                    "🚫 Banir",
                    callback_data=f"usuario_ban:{uid}"
                )
            )

        markup.row(
            types.InlineKeyboardButton(
                "🔄 Atualizar",
                callback_data=f"usuario_atualizar:{uid}"
            )
        )

        try:

            bot.edit_message_text(
                f"""
👤 <b>USUÁRIO</b>

🆔 ID:
<code>{uid}</code>

👤 Nome:
{nome or "Sem nome"}

📱 Username:
@{username if username else "Sem username"}

💰 Saldo:
{dinheiro(saldo or 0)}

📌 Status:
{status}

📅 Cadastro:
{data_cadastro}
""",
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="HTML",
                reply_markup=markup
            )

        except Exception:
            pass

    # ==========================================
    # BANIMENTOS
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "🚫 Banimentos")
    def menu_banimentos(message):

        if not admin_autorizado(message.from_user.id):
            return

        bot.send_message(
            message.chat.id,
            """
🚫 <b>SISTEMA DE BANIMENTOS</b>

Envie um dos comandos abaixo:

<code>/ban ID_DO_USUARIO</code>

<code>/unban ID_DO_USUARIO</code>
""",
            parse_mode="HTML"
        )

    @bot.message_handler(commands=["ban"])
    def comando_ban(message):

        if not admin_autorizado(message.from_user.id):
            return

        try:
            usuario_id = int(message.text.split()[1])

        except:
            bot.reply_to(
                message,
                "Uso correto:\n/ban ID_DO_USUARIO"
            )
            return

        sucesso = banir_usuario(usuario_id)

        if sucesso:

            bot.send_message(
                message.chat.id,
                "✅ Usuário banido."
            )

            try:
                bot.send_message(
                    usuario_id,
                    "🚫 Você foi banido do bot."
                )
            except:
                pass

        else:

            bot.send_message(
                message.chat.id,
                "❌ Não foi possível banir."
            )

    @bot.message_handler(commands=["unban"])
    def comando_unban(message):

        if not admin_autorizado(message.from_user.id):
            return

        try:

            usuario_id = int(message.text.split()[1])

        except:

            bot.reply_to(
                message,
                "Uso correto:\n/unban ID_DO_USUARIO"
            )

            return

        sucesso = desbanir_usuario(usuario_id)

        if sucesso:

            bot.send_message(
                message.chat.id,
                "✅ Usuário desbanido."
            )

            try:

                bot.send_message(
                    usuario_id,
                    "✅ Seu acesso ao bot foi liberado novamente."
                )

            except:
                pass

        else:

            bot.send_message(
                message.chat.id,
                "❌ Não foi possível desbanir."
            )

    # ==========================================
    # ESTATÍSTICAS
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "📊 Estatísticas")
    def estatisticas(message):

        if not admin_autorizado(message.from_user.id):
            return

        cursor.execute("SELECT COUNT(*) FROM usuarios")
        usuarios = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM indicacoes")
        indicacoes = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM saques")
        saques = cursor.fetchone()[0]

        bot.send_message(

            message.chat.id,

            f"""
📊 <b>ESTATÍSTICAS</b>

👥 Usuários:
{usuarios}

🎁 Indicações:
{indicacoes}

💸 Saques:
{saques}
""",

            parse_mode="HTML"

        )
