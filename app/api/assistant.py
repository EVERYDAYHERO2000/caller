"""The assistant (the round button at the bottom right): chats with an AI that works with contacts, «Дела» and calls."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import assistant, db
from ..calls import AgentNotReady, LineBusy

router = APIRouter(tags=["assistant"])


class AskIn(BaseModel):
    text: str = Field(..., description="Сообщение владельца: «что мне просили напомнить?», «позвони маме»…")


class ConfirmIn(BaseModel):
    prompt: str | None = Field(None, description="Поручение агенту (можно поправить перед звонком)")
    agent_id: int | None = None
    script_id: int | None = None


def _wrap(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except assistant.AssistantError as e:
        raise HTTPException(422, str(e))


@router.get("/assistant/chats")
def list_chats():
    """Чаты ассистента, последние сверху."""
    return assistant.chats()


@router.post("/assistant/chats", status_code=201)
def create_chat():
    """Новый пустой чат."""
    return assistant.new_chat()


@router.delete("/assistant/chats/{chat_id}")
def delete_chat(chat_id: int):
    """Удалить чат с его сообщениями (дела и звонки остаются)."""
    db.execute("DELETE FROM assistant_messages WHERE chat_id=?", (chat_id,))
    return {"deleted": db.delete("assistant_chats", chat_id)}


@router.get("/assistant/chats/{chat_id}/messages")
def chat_messages(chat_id: int):
    """Сообщения чата: user, assistant (текст) и action (карточки звонка и «выполнено»)."""
    return assistant.messages(chat_id)


@router.post("/assistant/chats/{chat_id}/messages")
async def ask(chat_id: int, body: AskIn):
    """Написать ассистенту. Возвращает новые сообщения: ваше, карточки и ответ."""
    try:
        return await assistant.ask(chat_id, body.text)
    except assistant.AssistantError as e:
        raise HTTPException(422, str(e))


@router.post("/assistant/actions/{msg_id}/confirm")
async def confirm(msg_id: int, body: ConfirmIn):
    """«Позвонить» в карточке звонка — только здесь номер набирается."""
    try:
        return await assistant.confirm_call(msg_id, body.prompt, body.agent_id, body.script_id)
    except assistant.AssistantError as e:
        raise HTTPException(422, str(e))
    except LineBusy as e:
        raise HTTPException(409, str(e))
    except AgentNotReady as e:
        raise HTTPException(503, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.post("/assistant/actions/{msg_id}/cancel")
def cancel(msg_id: int):
    """«Отмена» в карточке звонка."""
    return _wrap(assistant.cancel_call, msg_id)


@router.post("/assistant/actions/{msg_id}/undo")
def undo(msg_id: int):
    """«Отменить» в карточке «выполнено»: дело снова в работе."""
    return _wrap(assistant.undo_done, msg_id)
