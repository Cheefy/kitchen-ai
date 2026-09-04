from fastapi import APIRouter

from app import schemas
from app.services.notifications import notify

router = APIRouter()


@router.post("/notifications/test")
async def send_test_notification(body: schemas.NotificationTestRequest):
    result = await notify(body.message, title="Kitchen AI (test)")
    return {"sent": result is not None, "pushover_response": result}
