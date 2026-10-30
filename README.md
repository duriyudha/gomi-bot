# gomi-bot
仙台市青葉区八幡のごみ収集日を教えるLINE bot (FastAPI)

LINE bot that tells which garbage goes out in Sendai, Aoba-ku Hachiman 2-chome.
Replies to 「今日」「明日」「今週」 and sends a reminder at 20:00 JST the night before a collection day.

- Docs (Japanese): [README.ja.md](README.ja.md)
- Schedule: [schedule.yml](schedule.yml)

```bash
cp .env.example .env   # fill in LINE secrets
docker compose up -d --build
```
