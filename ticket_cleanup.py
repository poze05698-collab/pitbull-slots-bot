"""Utilitários de limpeza de mensagens de tickets."""
import threading

_lock = threading.RLock()
_messages = {}

def registrar_mensagem(ticket_id, message_id):
    with _lock:
        _messages.setdefault(int(ticket_id), set()).add(int(message_id))

def obter_mensagens(ticket_id):
    with _lock:
        return list(_messages.get(int(ticket_id), set()))

def limpar_ticket(bot, chat_id, ticket_id):
    ids = obter_mensagens(ticket_id)
    apagadas = 0
    for mid in ids:
        try:
            bot.delete_message(chat_id, mid)
            apagadas += 1
        except Exception:
            pass
    with _lock:
        _messages.pop(int(ticket_id), None)
    return apagadas
