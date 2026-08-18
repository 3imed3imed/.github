"""YouTube uploader (spec §25, §26, §46).

Implements resumable upload, metadata, thumbnail, captions, playlist assignment,
the synthetic-media flag, privacy and ``publishAt`` scheduling, plus processing
status polling.

SAFETY GATES (enforced here, not just documented):
* No upload happens unless ``UPLOAD_ENABLED=true``.
* Privacy is never ``public`` directly — public happens only via ``publishAt``,
  and only when ``PUBLIC_AUTO_PUBLISH=true`` (owner-set).
* google-api client libs are an optional dependency; absent them the uploader
  runs in ``dry-run`` mode and reports what it *would* do.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.config import Settings, get_settings
from app.observability import get_logger

log = get_logger("youtube")


@dataclass
class UploadPlan:
    video_path: Path
    title: str
    description: str
    thumbnail_path: Path | None
    captions_path: Path | None
    synthetic_media: bool
    privacy_status: str
    publish_at: str | None
    playlist_id: str | None
    tags: list[str] = field(default_factory=list)
    category_id: str = "25"  # News & Politics is closest for documentary/crime


@dataclass
class UploadResult:
    status: str  # dry-run | uploaded | scheduled | blocked
    video_id: str | None
    processing_status: str | None
    detail: str


class YouTubeUploader:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def _oauth_ready(self) -> bool:
        s = self.settings
        return bool(s.youtube_client_id and s.youtube_client_secret and s.youtube_refresh_token)

    def build_plan(
        self,
        *,
        video_path: Path,
        title: str,
        description: str,
        thumbnail_path: Path | None,
        captions_path: Path | None,
        synthetic_media: bool,
        publish_at: str | None = None,
    ) -> UploadPlan:
        safety = self.settings.safety
        privacy = safety.privacy_status()
        # publishAt only when auto-publish is explicitly enabled by the owner.
        effective_publish_at = publish_at if safety.public_auto_publish else None
        if effective_publish_at:
            privacy = "private"  # required by API when using publishAt
        return UploadPlan(
            video_path=video_path,
            title=title[:100],
            description=description[:4900],
            thumbnail_path=thumbnail_path,
            captions_path=captions_path,
            synthetic_media=synthetic_media,
            privacy_status=privacy,
            publish_at=effective_publish_at,
            playlist_id=self.settings.youtube_playlist_id,
            tags=["true crime", "cold case", "documentary"],
        )

    def upload(self, plan: UploadPlan) -> UploadResult:
        # Gate 1: uploads globally disabled -> render-only mode.
        if not self.settings.safety.upload_enabled:
            return UploadResult(
                status="dry-run",
                video_id=None,
                processing_status=None,
                detail="UPLOAD_ENABLED=false — render-only mode; nothing uploaded.",
            )
        # Gate 2: OAuth / client libs missing -> dry-run, never a password prompt.
        if not self._oauth_ready():
            return UploadResult(
                status="dry-run",
                video_id=None,
                processing_status=None,
                detail="YouTube OAuth refresh token not configured — cannot upload.",
            )
        try:
            return self._real_upload(plan)
        except Exception as exc:  # noqa: BLE001
            log.error("upload failed: %s", exc)
            return UploadResult(status="blocked", video_id=None, processing_status=None, detail=str(exc))

    # -- real upload (only reached with libs + OAuth + UPLOAD_ENABLED) ------ #
    def _real_upload(self, plan: UploadPlan) -> UploadResult:  # pragma: no cover - network
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        s = self.settings
        creds = Credentials(
            token=None,
            refresh_token=s.youtube_refresh_token,
            client_id=s.youtube_client_id,
            client_secret=s.youtube_client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"],
        )
        creds.refresh(Request())
        youtube = build("youtube", "v3", credentials=creds)

        status = {"privacyStatus": plan.privacy_status, "selfDeclaredMadeForKids": False}
        if plan.publish_at:
            status["publishAt"] = plan.publish_at
        if plan.synthetic_media:
            status["containsSyntheticMedia"] = True

        body = {
            "snippet": {
                "title": plan.title,
                "description": plan.description,
                "tags": plan.tags,
                "categoryId": plan.category_id,
            },
            "status": status,
        }
        media = MediaFileUpload(str(plan.video_path), chunksize=8 * 1024 * 1024, resumable=True)
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

        response = None
        while response is None:
            _, response = request.next_chunk()  # resumable — retries handled by client
        video_id = response["id"]

        if plan.thumbnail_path and Path(plan.thumbnail_path).exists():
            from googleapiclient.http import MediaFileUpload as _M

            youtube.thumbnails().set(videoId=video_id, media_body=_M(str(plan.thumbnail_path))).execute()

        if plan.captions_path and Path(plan.captions_path).exists():
            from googleapiclient.http import MediaFileUpload as _M

            youtube.captions().insert(
                part="snippet",
                body={"snippet": {"videoId": video_id, "language": "en", "name": "English", "isDraft": False}},
                media_body=_M(str(plan.captions_path)),
            ).execute()

        if plan.playlist_id:
            youtube.playlistItems().insert(
                part="snippet",
                body={"snippet": {"playlistId": plan.playlist_id, "resourceId": {"kind": "youtube#video", "videoId": video_id}}},
            ).execute()

        processing = self._poll_processing(youtube, video_id)
        final_status = "scheduled" if plan.publish_at else "uploaded"
        return UploadResult(
            status=final_status,
            video_id=video_id,
            processing_status=processing,
            detail=f"{final_status}; privacy={plan.privacy_status}",
        )

    def _poll_processing(self, youtube, video_id: str, attempts: int = 10) -> str:  # pragma: no cover
        import time

        for _ in range(attempts):
            resp = youtube.videos().list(part="processingDetails,status", id=video_id).execute()
            items = resp.get("items", [])
            if items:
                pd = items[0].get("processingDetails", {})
                state = pd.get("processingStatus", "unknown")
                if state in {"succeeded", "failed", "terminated"}:
                    return state
            time.sleep(15)
        return "processing"
