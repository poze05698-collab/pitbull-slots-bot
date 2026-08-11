from telebot import types

from config import (
    ADMIN_ID,
    STATUS_PENDENTE
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
    rejeitar_saque
)


# Guarda temporariamente a indicação que o administrador está rejeitando.
# Exemplo: {ADMIN_ID: INDICACAO_ID}
rejeicoes_aguardando_motivo = {}


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
                i.indicador_id,
                i.indicado_id,
                i.valor,
                i.data,
                i.grupo_confirmado,
                u1.nome,
                u2.nome
            FROM indicacoes i
            LEFT JOIN usuarios u1
                ON u1.id = i.indicador_id
            LEFT JOIN usuarios u2
                ON u2.id = i.indicado_id
            WHERE UPPER(TRIM(COALESCE(i.status, ''))) = 'PENDENTE'
            ORDER BY i.id
            """
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

            grupo = "Sim" if item[5] else "Não"

            indicador_nome = item[6] or "Usuário"
            indicado_nome = item[7] or "Usuário"

            bot.send_message(

                message.chat.id,

                f"""
🎁 INDICAÇÃO #{item[0]}

👤 Indicador:
{indicador_nome}

🆔 ID do indicador:
<code>{item[1]}</code>

👤 Indicado:
{indicado_nome}

🆔 ID do indicado:
<code>{item[2]}</code>

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

        # Busca quem indicou e quem foi indicado.
        cursor.execute(
            """
            SELECT indicador_id, indicado_id
            FROM indicacoes
            WHERE id=?
            """,
            (indicacao_id,)
        )

        dados = cursor.fetchone()

        if not dados:
            bot.answer_callback_query(
                call.id,
                "Indicação não encontrada.",
                show_alert=True
            )
            return

        indicador_id, indicado_id = dados

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

        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )

        bot.send_message(
            call.message.chat.id,
            "✅ Indicação aprovada com sucesso."
        )

        # Avisa quem indicou.
        try:
            bot.send_message(
                indicador_id,
                """
🎉 Sua indicação foi aprovada!

💰 O valor já está disponível em seu saldo.
"""
            )
        except Exception:
            pass

        # Avisa também quem entrou no grupo.
        try:
            bot.send_message(
                indicado_id,
                """
🎉 Sua entrada foi aprovada!

✅ Sua indicação foi aprovada pelo administrador.
💰 A recompensa já foi liberada para quem fez a indicação.

Obrigado por participar!
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

        # Confirma que a indicação existe antes de pedir o motivo.
        cursor.execute(
            """
            SELECT indicador_id, indicado_id
            FROM indicacoes
            WHERE id=?
            """,
            (indicacao_id,)
        )

        dados = cursor.fetchone()

        if not dados:
            bot.answer_callback_query(
                call.id,
                "Indicação não encontrada.",
                show_alert=True
            )
            return

        rejeicoes_aguardando_motivo[call.from_user.id] = {
            "indicacao_id": indicacao_id,
            "mensagem_id": call.message.message_id
        }

        bot.answer_callback_query(call.id)

        bot.send_message(
            call.from_user.id,
            f"""
❌ <b>REJEITAR INDICAÇÃO #{indicacao_id}</b>

Digite agora o <b>motivo da reprovação</b>.

Exemplo:
<code>Indicação não validada de acordo com as regras do grupo.</code>

O motivo será enviado ao usuário.
""",
            parse_mode="HTML",
            reply_markup=types.ForceReply(
                selective=True,
                input_field_placeholder="Digite o motivo da reprovação..."
            )
        )

    # ==========================================
    # RECEBER MOTIVO DA REPROVAÇÃO
    # ==========================================

    @bot.message_handler(
        func=lambda m: (
            m.from_user.id in rejeicoes_aguardando_motivo
            and m.reply_to_message is not None
        )
    )
    def receber_motivo_rejeicao(message):

        if not admin_autorizado(message.from_user.id):
            return

        dados_pendentes = rejeicoes_aguardando_motivo.get(
            message.from_user.id
        )

        if not dados_pendentes:
            return

        motivo = (message.text or "").strip()

        if not motivo:
            bot.reply_to(
                message,
                "❌ Digite um motivo válido para a reprovação."
            )
            return

        indicacao_id = dados_pendentes["indicacao_id"]
        mensagem_id = dados_pendentes["mensagem_id"]

        # Busca os dois usuários antes de processar a indicação.
        cursor.execute(
            """
            SELECT indicador_id, indicado_id
            FROM indicacoes
            WHERE id=?
            """,
            (indicacao_id,)
        )

        dados = cursor.fetchone()

        if not dados:
            rejeicoes_aguardando_motivo.pop(
                message.from_user.id,
                None
            )

            bot.reply_to(
                message,
                "❌ Indicação não encontrada."
            )
            return

        indicador_id, indicado_id = dados

        sucesso, retorno = rejeitar_indicacao(
            indicacao_id,
            message.from_user.id,
            motivo
        )

        if not sucesso:
            rejeicoes_aguardando_motivo.pop(
                message.from_user.id,
                None
            )

            bot.reply_to(
                message,
                f"❌ {retorno}"
            )
            return

        rejeicoes_aguardando_motivo.pop(
            message.from_user.id,
            None
        )

        # Remove os botões da indicação no painel.
        try:
            bot.edit_message_reply_markup(
                chat_id=message.chat.id,
                message_id=mensagem_id,
                reply_markup=None
            )
        except Exception:
            pass

        bot.send_message(
            message.chat.id,
            "❌ Indicação rejeitada com sucesso."
        )

        # Avisa quem indicou.
        try:
            bot.send_message(
                indicador_id,
                f"""
❌ Sua indicação foi rejeitada.

📝 Motivo:
{motivo}
"""
            )
        except Exception:
            pass

        # Avisa também quem foi indicado.
        try:
            bot.send_message(
                indicado_id,
                f"""
❌ Sua indicação foi reprovada.

📝 Motivo informado pelo administrador:
{motivo}
"""
            )
        except Exception:
            pass


    # ==========================================
    # SAQUES PENDENTES
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "💸 Saques")
    def listar_saques(message):

        if not admin_autorizado(message.from_user.id):
            return

        cursor.execute(
            """
            SELECT
                s.id,
                u.nome,
                s.usuario_id,
                s.valor,
                s.pix,
                s.data
            FROM saques s
            JOIN usuarios u
                ON u.id = s.usuario_id
            WHERE s.status=?
            ORDER BY s.id
            """,
            (STATUS_PENDENTE,)
        )

        saques = cursor.fetchall()

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
{saque[1]}

🆔 ID:
<code>{saque[2]}</code>

💰 Valor:
{dinheiro(saque[3])}

💳 PIX:
<code>{saque[4]}</code>

📅 Data:
{saque[5]}
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
    # ESTATÍSTICAS
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "📊 Estatísticas")
    def estatisticas(message):

        if not admin_autorizado(message.from_user.id):
            return

        cursor.execute("SELECT COUNT(*) FROM usuarios")
        usuarios = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM indicacoes"
        )
        indicacoes = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM saques"
        )
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
