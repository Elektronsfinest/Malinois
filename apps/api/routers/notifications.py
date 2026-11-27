from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from database import get_db
from models import User
from routers.auth import get_current_user
from schemas import NotificationItemResponse
from services import notifications as notif_service

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationItemResponse])
def list_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[NotificationItemResponse]:
    return notif_service.list_active_notifications(db, current_user)


@router.post("/{case_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
def dismiss_notification(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    notif_service.dismiss_notification(db, current_user, case_id)
