import time
from typing import Dict, List

from pydantic import BaseModel


class BlocksModel(BaseModel):
    pass


class Divider(BlocksModel):
    @property
    def payload(self) -> Dict:
        return {
            "type": "divider",
        }


class PlainText(BlocksModel):
    text: str
    emoji: bool = True

    @property
    def element(self) -> Dict:
        return {
            "type": "plain_text",
            "text": self.text,
            "emoji": self.emoji
        }

    @property
    def payload(self) -> Dict:
        return {
            "type": "context",
            "elements": [self.element],
        }


class PlainTexts(BlocksModel):
    send_alarmblocks: List[PlainText] = []

    @property
    def payload(self) -> Dict:
        return {
            "type": "context",
            "elements": [b.element for b in self.blocks]
        }


class MrkDwn(BlocksModel):
    text: str

    @property
    def payload(self) -> Dict:
        return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": self.text
            }
        }


class Button(BlocksModel):
    text: str
    emoji: bool = True
    value: str = ""
    url: str = ""
    action_id: str = ""

    @property
    def element(self) -> Dict:
        random_id: str = str(time.time()).replace('.', '')
        return {
            "type": "button",
            "text": {
                "type": "plain_text",
                "text": self.text,
                "emoji": self.emoji
            },
            "value": self.value if self.value else random_id,
            "url": self.url,
            "action_id": self.action_id if self.action_id else random_id,
        }

    @property
    def payload(self) -> Dict:
        return {
            "type": "actions",
            "elements": [self.element],
        }

class Buttons(BlocksModel):
    blocks: List[Button] = []

    @property
    def payload(self) -> Dict:
        return {
            "type": "actions",
            "elements": [b.element for b in self.blocks]
        }

