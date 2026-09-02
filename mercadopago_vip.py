"""Integração Pix do Mercado Pago para venda de VIP.

Usa a API oficial do Mercado Pago no backend. O Access Token nunca é enviado
para o Telegram. Para evitar depender de um servidor web público na Discloud,
o bot consulta pagamentos pendentes em intervalos curtos e usa idempotência.
"""
import re
import threading
import time
import uuid
from datetime import datetime, timedelta

import requests

from config import MERCADOPAGO_ACCESS_TOKEN, MERCADOPAGO_VIP_ATIVO, MERCADOPAGO_POLL_INTERVAL
from database import conn, cursor
from utils import data_atual, registrar_historico, registrar_movimentacao, criar_notificacao

BASE_URL = "https://api.mercadopago.com"
_lock_aprovacao = threading.Lock()


def preparar_pagamentos_mp():
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vip_pagamentos_mp (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            pagamento_id TEXT UNIQUE,
            referencia TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL,
            valor REAL NOT NULL,
            dias INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            codigo TEXT,
            criado_em TEXT NOT NULL,
            atualizado_em TEXT NOT NULL
        )
    """)
    for coluna, tipo in (("chat_id", "INTEGER"), ("message_id", "INTEGER")):
        try:
            cursor.execute(f"ALTER TABLE vip_pagamentos_mp ADD COLUMN {coluna} {tipo}")
        except Exception:
            pass
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_vip_mp_status ON vip_pagamentos_mp(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_vip_mp_usuario ON vip_pagamentos_mp(usuario_id, status)")
    conn.commit()


def _headers(idempotency=None):
    h = {
        "Authorization": f"Bearer {MERCADOPAGO_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if idempotency:
        h["X-Idempotency-Key"] = idempotency
    return h


def configurado():
    return bool(MERCADOPAGO_VIP_ATIVO and MERCADOPAGO_ACCESS_TOKEN and MERCADOPAGO_ACCESS_TOKEN.strip())


def criar_pix(usuario_id, email, valor, dias, descricao):
    """Cria um pagamento Pix e retorna (ok, dados/erro)."""
    preparar_pagamentos_mp()
    if not configurado():
        return False, "O pagamento online ainda não foi configurado pelo administrador."

    email = (email or "").strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return False, "Informe um e-mail válido."

    try:
        valor = round(float(valor), 2)
        dias = int(dias)
        referencia = f"vip-{usuario_id}-{uuid.uuid4().hex[:20]}"
        idem = str(uuid.uuid4())
        payload = {
            "transaction_amount": valor,
            "description": descricao[:200],
            "payment_method_id": "pix",
            "external_reference": referencia,
            "payer": {"email": email},
        }
        resposta = requests.post(
            f"{BASE_URL}/v1/payments",
            headers=_headers(idem),
            json=payload,
            timeout=(5, 15),
        )
        dados = resposta.json() if resposta.content else {}
        if resposta.status_code not in (200, 201):
            print(f"MERCADO PAGO ERRO {resposta.status_code}: {dados}")
            return False, "Não foi possível gerar o Pix agora. Tente novamente."

        pagamento_id = str(dados.get("id", ""))
        tx = dados.get("point_of_interaction", {}).get("transaction_data", {})
        qr = tx.get("qr_code") or ""
        qr_base64 = tx.get("qr_code_base64") or ""
        ticket_url = tx.get("ticket_url") or ""
        if not pagamento_id or not qr:
            print(f"MERCADO PAGO RESPOSTA SEM PIX: {dados}")
            return False, "O Mercado Pago não retornou os dados do Pix."

        agora = data_atual()
        cursor.execute("""
            INSERT INTO vip_pagamentos_mp
            (usuario_id,pagamento_id,referencia,email,valor,dias,status,codigo,criado_em,atualizado_em)
            VALUES(?,?,?,?,?,?,'pending',NULL,?,?)
        """, (usuario_id, pagamento_id, referencia, email, valor, dias, agora, agora))
        conn.commit()

        return True, {
            "id": pagamento_id,
            "referencia": referencia,
            "qr_code": qr,
            "qr_code_base64": qr_base64,
            "ticket_url": ticket_url,
            "status": dados.get("status", "pending"),
            "valor": valor,
            "dias": dias,
        }
    except requests.RequestException as erro:
        print(f"MERCADO PAGO REDE: {erro}")
        return False, "O Mercado Pago está temporariamente indisponível. Tente novamente."
    except Exception as erro:
        conn.rollback()
        print(f"ERRO AO CRIAR PIX VIP: {erro}")
        return False, "Não foi possível criar o pagamento agora."


def consultar_pagamento(pagamento_id):
    if not configurado():
        return None
    try:
        r = requests.get(f"{BASE_URL}/v1/payments/{pagamento_id}", headers=_headers(), timeout=(5, 10))
        if r.status_code != 200:
            return None
        return r.json()
    except Exception as erro:
        print(f"ERRO CONSULTANDO PAGAMENTO {pagamento_id}: {erro}")
        return None


def registrar_mensagem_pix(pagamento_id, chat_id, message_id):
    """Guarda a mensagem que contém o Pix para removê-la após a aprovação."""
    try:
        preparar_pagamentos_mp()
        cursor.execute(
            "UPDATE vip_pagamentos_mp SET chat_id=?, message_id=?, atualizado_em=? WHERE pagamento_id=?",
            (int(chat_id), int(message_id), data_atual(), str(pagamento_id)),
        )
        conn.commit()
    except Exception as erro:
        print(f"ERRO SALVANDO MENSAGEM PIX {pagamento_id}: {erro}")


def _remover_mensagem_pix(bot, pagamento_id):
    """Apaga a mensagem do Pix depois que o pagamento foi confirmado."""
    try:
        preparar_pagamentos_mp()
        cursor.execute(
            "SELECT chat_id, message_id FROM vip_pagamentos_mp WHERE pagamento_id=?",
            (str(pagamento_id),),
        )
        dados_msg = cursor.fetchone()
        if not dados_msg or not dados_msg[0] or not dados_msg[1]:
            return
        try:
            bot.delete_message(int(dados_msg[0]), int(dados_msg[1]))
        except Exception as erro:
            print(f"AVISO AO REMOVER MENSAGEM PIX {pagamento_id}: {erro}")
        cursor.execute(
            "UPDATE vip_pagamentos_mp SET chat_id=NULL, message_id=NULL, atualizado_em=? WHERE pagamento_id=?",
            (data_atual(), str(pagamento_id)),
        )
        conn.commit()
    except Exception as erro:
        print(f"ERRO REMOVENDO MENSAGEM PIX {pagamento_id}: {erro}")


def marcar_aprovado(bot, row, dados):
    """Libera exatamente uma vez um pagamento aprovado."""
    from vip import ativar_vip_por_pagamento_mp

    with _lock_aprovacao:
        preparar_pagamentos_mp()
        pagamento_id = str(row[2])
        cursor.execute("SELECT status,codigo FROM vip_pagamentos_mp WHERE pagamento_id=?", (pagamento_id,))
        atual = cursor.fetchone()
        if not atual or atual[0] == "approved":
            return
        if atual[0] not in ("pending", "in_process"):
            return

        codigo_existente = atual[1]
        if codigo_existente:
            codigo = codigo_existente
            expiracao = None
        else:
            ok, codigo, expiracao = ativar_vip_por_pagamento_mp(
                bot=bot,
                usuario_id=int(row[1]),
                pagamento_id=pagamento_id,
                valor=float(row[5]),
                dias=int(row[6]),
            )
            if not ok:
                return

            agora = data_atual()
            cursor.execute("""
                UPDATE vip_pagamentos_mp
                SET codigo=?, atualizado_em=?
                WHERE pagamento_id=? AND status IN ('pending','in_process')
                """, (codigo, agora, pagamento_id))
            conn.commit()

        agora = data_atual()
        cursor.execute("""
            UPDATE vip_pagamentos_mp
            SET status='approved', atualizado_em=?
            WHERE pagamento_id=? AND status IN ('pending','in_process')
        """, (agora, pagamento_id))
        conn.commit()

        try:
            bot.send_message(
                int(row[1]),
                "🎉 <b>PAGAMENTO CONFIRMADO!</b>\n\n"
                "💎 Seu VIP foi liberado.\n"
                f"🎟️ Código para resgatar: <code>{codigo}</code>\n\n"
                "Toque em <b>🎟️ Código Promocional</b> e envie esse código para ativar seu VIP.",
                parse_mode="HTML",
            )
        except Exception as erro:
            print(f"ERRO ENVIANDO CODIGO VIP {row[1]}: {erro}")

        _remover_mensagem_pix(bot, pagamento_id)


def _processar_pendentes(bot):
    preparar_pagamentos_mp()
    cursor.execute("""
        SELECT id,usuario_id,pagamento_id,referencia,email,valor,dias,status,codigo,criado_em
        FROM vip_pagamentos_mp
        WHERE status IN ('pending','in_process')
        ORDER BY id ASC LIMIT 50
    """)
    rows = cursor.fetchall()
    for row in rows:
        dados = consultar_pagamento(row[2])
        if not dados:
            continue
        status = str(dados.get("status") or "pending")
        if status == "approved":
            marcar_aprovado(bot, row, dados)
        elif status in ("cancelled", "rejected", "refunded", "charged_back"):
            cursor.execute("UPDATE vip_pagamentos_mp SET status=?, atualizado_em=? WHERE pagamento_id=? AND status NOT IN ('approved')", (status, data_atual(), row[2]))
            conn.commit()
        elif status != row[7]:
            cursor.execute("UPDATE vip_pagamentos_mp SET status=?, atualizado_em=? WHERE pagamento_id=?", (status, data_atual(), row[2]))
            conn.commit()


def iniciar_monitoramento(bot):
    """Inicia uma única thread daemon para acompanhar pagamentos."""
    preparar_pagamentos_mp()
    if not configurado():
        print("ℹ️ Mercado Pago VIP: Access Token ainda não configurado.")
        return
    if getattr(iniciar_monitoramento, "_iniciado", False):
        return
    iniciar_monitoramento._iniciado = True

    def loop():
        while True:
            try:
                _processar_pendentes(bot)
            except Exception as erro:
                print(f"ERRO NO MONITORAMENTO MERCADO PAGO: {erro}")
            time.sleep(max(15, int(MERCADOPAGO_POLL_INTERVAL)))

    threading.Thread(target=loop, name="mercadopago-vip", daemon=True).start()
    print("✅ Monitoramento de pagamentos Mercado Pago iniciado.")
