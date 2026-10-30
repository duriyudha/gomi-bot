"""FastAPI app: LINE webhook (/callback) and the nightly reminder job."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    PushMessageRequest,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import (
    FollowEvent,
    MessageEvent,
    TextMessageContent,
    UnfollowEvent,
)

from app.config import Settings
from app.messages import reply_for
from app.reminder import send_reminders
from app.schedule import JST, Schedule, load_schedule, today_jst
from app.store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("gomi-bot")

WELCOME_TEXT = (
    "友だち追加ありがとうございます。\n"
    "収集日の前の日の20時にお知らせします。\n"
    "「今日」「明日」「今週」と送ると、ごみの日を答えます。"
)


class Bot:
    """Holds everything the webhook and the reminder job need."""

    def __init__(self, settings: Settings):
        self.parser = WebhookParser(settings.channel_secret)
        self.api = MessagingApi(ApiClient(Configuration(access_token=settings.channel_access_token)))
        self.schedule: Schedule = load_schedule(settings.schedule_path)
        self.store = Store(settings.db_path)

    def reply(self, reply_token: str, text: str) -> None:
        self.api.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=text)]))

    def push(self, user_id: str, text: str) -> None:
        self.api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=text)]))

    def handle_event(self, event) -> None:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
            self.reply(event.reply_token, reply_for(self.schedule, event.message.text, today_jst()))
        elif isinstance(event, FollowEvent):
            self.store.add_subscriber(event.source.user_id)
            log.info("Subscribed: %s", event.source.user_id)
            self.reply(event.reply_token, WELCOME_TEXT)
        elif isinstance(event, UnfollowEvent):
            self.store.remove_subscriber(event.source.user_id)
            log.info("Unsubscribed: %s", event.source.user_id)

    def handle_events(self, events: list) -> None:
        for event in events:
            try:
                self.handle_event(event)
            except Exception:
                # Log and keep going, so one bad event does not stop the others.
                log.exception("Failed to handle event: %s", type(event).__name__)

    def run_reminder(self) -> None:
        send_reminders(self.schedule, self.store, self.push)


@asynccontextmanager
async def lifespan(app: FastAPI):
    bot = Bot(Settings.from_env())
    scheduler = BackgroundScheduler(timezone=JST)
    # Every day at 20:00 JST. If the app was down at 20:00, still run if it comes back within 30 min.
    scheduler.add_job(bot.run_reminder, "cron", hour=20, minute=0, misfire_grace_time=1800, coalesce=True)
    scheduler.start()
    app.state.bot = bot
    log.info("Started. %d subscribers.", len(bot.store.subscribers()))
    yield
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)


@app.post("/callback")
async def callback(request: Request) -> str:
    signature = request.headers.get("X-Line-Signature", "")
    body = (await request.body()).decode("utf-8")
    bot: Bot = request.app.state.bot
    try:
        events = bot.parser.parse(body, signature)  # checks the signature
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    # LINE API calls are blocking, so run them outside the event loop.
    await run_in_threadpool(bot.handle_events, events)
    return "OK"


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
