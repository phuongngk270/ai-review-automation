"""Write AI Review outcomes to the master Google Sheet.

Column mapping (per SKILL.md Stage 8):
- M: outcome (PASS|FAIL|UNKNOWN|NOT_APPLICABLE)
- N: match formula — never write
- O: tester (combo profile name)
- P: date run (YYYY-MM-DD)
- Q: notes (optional)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
TOKEN_PATH = Path.home() / ".cache" / "anduin-automation" / "sheets-token.json"
CLIENT_SECRETS_PATH = Path.home() / ".cache" / "anduin-automation" / "oauth-client.json"


def connect():
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())
    return build("sheets", "v4", credentials=creds)


@dataclass(frozen=True)
class OutcomeRow:
    row: int
    tester: str
    outcome: str
    date: str
    notes: str = ""


def write_outcomes(service, *, sheet_id: str, tab_name: str, rows: list[OutcomeRow]) -> None:
    data = []
    for r in rows:
        data.append({"range": f"{tab_name}!M{r.row}", "values": [[r.outcome]]})
        data.append({"range": f"{tab_name}!O{r.row}", "values": [[r.tester]]})
        data.append({"range": f"{tab_name}!P{r.row}", "values": [[r.date]]})
        data.append({"range": f"{tab_name}!Q{r.row}", "values": [[r.notes]]})
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=sheet_id,
        body={"valueInputOption": "USER_ENTERED", "data": data},
    ).execute()
