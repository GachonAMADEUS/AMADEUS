from datetime import datetime

from pydantic import BaseModel
from pydantic import ConfigDict


class UploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_filename: str
    status: str
    progress: int
    stage: str
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ResultResponse(BaseModel):
    upload_id: int
    status: str
    progress: int
    stage: str
    message: str
    model_stl_url: str | None = None
    project_3mf_url: str | None = None
    report_json_url: str | None = None
    report_txt_url: str | None = None
    stdout_url: str | None = None
    stderr_url: str | None = None
    error_message: str | None = None
