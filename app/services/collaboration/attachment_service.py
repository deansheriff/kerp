"""
Attachment service for collaboration file uploads.
"""

import hashlib
import logging
import uuid
from datetime import datetime
from pathlib import PurePosixPath

from fastapi import UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.collaboration.attachment import MessageAttachment
from app.models.collaboration.message import Message
from app.models.collaboration.participant import ConversationParticipant

logger = logging.getLogger(__name__)


class CollabAttachmentService:
    """Handle file uploads and downloads for chat messages."""

    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
    MAX_FILES_PER_MESSAGE = 5
    ALLOWED_EXTENSIONS = {
        ".pdf", ".doc", ".docx", ".xls", ".xlsx",
        ".jpg", ".jpeg", ".png", ".gif", ".webp",
        ".zip", ".csv", ".txt", ".pptx", ".ppt",
    }

    @staticmethod
    async def save_attachments(
        db: Session,
        org_id: uuid.UUID,
        conversation_id: uuid.UUID,
        message_id: uuid.UUID,
        files: list[UploadFile],
    ) -> list[MessageAttachment]:
        """Validate and upload files to S3, create attachment records."""
        if len(files) > CollabAttachmentService.MAX_FILES_PER_MESSAGE:
            raise ValueError(
                f"Maximum {CollabAttachmentService.MAX_FILES_PER_MESSAGE} files per message."
            )

        attachments = []
        for file in files:
            if not file.filename:
                continue

            # Extension check
            suffix = PurePosixPath(file.filename).suffix.lower()
            if suffix not in CollabAttachmentService.ALLOWED_EXTENSIONS:
                logger.warning("Rejected file extension: %s", suffix)
                continue

            # Read content
            content = await file.read()
            if len(content) > CollabAttachmentService.MAX_FILE_SIZE:
                raise ValueError(
                    f"File '{file.filename}' exceeds "
                    f"{CollabAttachmentService.MAX_FILE_SIZE // (1024*1024)} MB limit."
                )

            # Compute checksum
            checksum = hashlib.sha256(content).hexdigest()

            # Generate S3 key
            file_id = uuid.uuid4()
            safe_name = file.filename.replace(" ", "_")
            s3_key = f"collab/{org_id}/{conversation_id}/{file_id}_{safe_name}"

            # Upload to S3
            try:
                from app.services.storage import get_storage

                storage = get_storage()
                storage.upload(
                    key=s3_key,
                    data=content,
                    content_type=file.content_type or "application/octet-stream",
                )
            except Exception:
                logger.exception("Failed to upload file: %s", file.filename)
                raise ValueError(f"Failed to upload '{file.filename}'.")

            attachment = MessageAttachment(
                message_id=message_id,
                organization_id=org_id,
                file_name=file.filename,
                file_key=s3_key,
                content_type=file.content_type or "application/octet-stream",
                file_size=len(content),
                checksum=checksum,
            )
            db.add(attachment)
            attachments.append(attachment)

        db.flush()
        return attachments

    @staticmethod
    def get_attachment(
        db: Session,
        org_id: uuid.UUID,
        attachment_id: uuid.UUID,
        person_id: uuid.UUID,
    ):
        """Get attachment with membership verification, return streaming response."""
        att = db.scalar(
            select(MessageAttachment).where(
                MessageAttachment.attachment_id == attachment_id,
                MessageAttachment.organization_id == org_id,
            )
        )
        if not att:
            from fastapi.responses import JSONResponse

            return JSONResponse({"error": "Attachment not found"}, status_code=404)

        # Verify the person is a participant in the message's conversation
        msg = db.get(Message, att.message_id)
        if not msg:
            from fastapi.responses import JSONResponse

            return JSONResponse({"error": "Message not found"}, status_code=404)

        participant = db.scalar(
            select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == msg.conversation_id,
                ConversationParticipant.person_id == person_id,
                ConversationParticipant.left_at.is_(None),
            )
        )
        if not participant:
            from fastapi.responses import JSONResponse

            return JSONResponse({"error": "Access denied"}, status_code=403)

        # Stream from S3
        try:
            from app.services.storage import get_storage
            import io

            storage = get_storage()
            data = storage.download(att.file_key)
            return StreamingResponse(
                io.BytesIO(data),
                media_type=att.content_type,
                headers={
                    "Content-Disposition": f'attachment; filename="{att.file_name}"',
                    "Content-Length": str(att.file_size),
                },
            )
        except Exception:
            logger.exception("Failed to download: %s", att.file_key)
            from fastapi.responses import JSONResponse

            return JSONResponse({"error": "Download failed"}, status_code=500)
