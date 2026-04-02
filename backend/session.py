from dataclasses import dataclass

from backend.api_client import CratesApiClient


@dataclass(frozen=True)
class UserSession:
    user_id: int
    email: str
    role: str
    client: CratesApiClient
