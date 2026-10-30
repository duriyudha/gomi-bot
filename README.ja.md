# gomi-bot（ごみの日 LINE bot）

仙台市 青葉区八幡2丁目 の「ごみの日」を教えてくれる LINE bot です。

- 「今日」「明日」「今週」と送ると、出せるごみを返事します。
- ごみの日の前の夜 20時 に「明日は〇〇の日です」と自動でお知らせします。

---

## 1. ファイルの説明

| ファイル | やること |
|---|---|
| `schedule.yml` | ごみの日のルールを書いたファイル。曜日や「第2・第4水曜日」、休みの日（年末年始）をここに書きます。 |
| `app/schedule.py` | `schedule.yml` を読んで、「この日はどのごみの日？」を計算します。LINE や FastAPI は使っていないので、これだけでテストできます。 |
| `app/messages.py` | bot が送る日本語の文を作ります（「明日は家庭ごみの日です」など）。 |
| `app/store.py` | SQLite に保存します。保存するのは「友だちの LINE ユーザーID」と「今月 push を何通送ったか」の2つです。 |
| `app/reminder.py` | 夜20時のお知らせを送る処理です。今月の送信数が 190通 になったら止めます。 |
| `app/config.py` | 環境変数から秘密の値（チャネルシークレットなど）を読みます。 |
| `app/main.py` | FastAPI のアプリ本体です。LINE から届く `/callback` を受けて、返事をします。毎晩20時の仕事（APScheduler）もここで動かします。 |
| `tests/` | pytest のテストです。 |
| `Dockerfile` | Docker イメージの作り方です。 |
| `docker-compose.yml` | サーバーで動かすための設定です。 |
| `.env.example` | 秘密の値を入れる `.env` ファイルの見本です。 |

---

## 2. 「明日」と送ってから、返事が来るまで

1. ユーザーが LINE で「明日」と送ります。
2. LINE のサーバーが、私のサーバー `https://gomi.duriyudha.com/callback` に POST で知らせます。
3. Cloudflare Tunnel を通って、Docker の中の FastAPI に届きます。
4. `main.py` の `callback()` が、`X-Line-Signature`（署名）をチェックします。
   本当に LINE から来たものか確かめるためです。だめなら 400 を返して終わりです。
5. 届いたデータを「メッセージのイベント」に変えます。
6. `messages.py` の `reply_for()` が、送られた文が「明日」だと分かります。
7. `schedule.py` の `items_on()` が、明日の日付で「どのルールに合うか」を調べます。
   - 休みの日（年末年始など）なら、何もなし。
   - 毎週のルール（例：火・金は家庭ごみ）に合うか。
   - 第◯曜日のルール（例：第2・第4水曜日は紙類）に合うか。
8. 「明日 11/3(火) は家庭ごみの日です。朝8:30までに出してください。」という文を作ります。
9. reply token を使って、LINE に返事を送ります（reply は無料で、送信数に入りません）。
10. LINE に 200 OK を返して終わりです。

日付はすべて日本時間（Asia/Tokyo）で計算します。

### 夜20時のお知らせの流れ

1. APScheduler が毎日 20:00 に `send_reminders()` を呼びます。
2. 明日のごみを調べます。何もなければ、送らずに終わります。
3. 登録しているユーザー1人ずつに push メッセージを送ります。
4. 1通送るたびに、今月の送信数を SQLite に +1 します。
5. 送信数が 190通 になったら、そこで止めます（LINE の無料プランは月 200通 まで）。

### 登録と解除

- bot を友だち追加すると（follow イベント）、ユーザーIDを保存します。
- ブロックすると（unfollow イベント）、ユーザーIDを消します。

---

## 3. なぜこれを使ったか

**FastAPI**
- やることは「POST を1つ受けるだけ」なので、小さくてかんたんなものがよかったからです。
- 速く、コードが短く書けます。テスト用のクライアントもついています。

**APScheduler**
- アプリの中で「毎日20時」の仕事を動かせます。
- Redis や別のワーカー、cron の設定がいりません。コンテナ1つで全部動きます。
- 注意：アプリを2つ動かすと、お知らせが2回送られます。なので、コンテナも uvicorn のワーカーも1つだけにしています。

**YAML ファイル（schedule.yml）**
- ごみの日はコードに書かず、ファイルに分けました。
- ルールが変わったときや、年末年始の日を足すときに、コードをさわらずに直せます。
- 人が読んでも分かりやすい形です。
- 別の地区でも、このファイルを変えるだけで使えます。

---

## 4. Docker で動かす（Ubuntu サーバー）

前もって必要なもの：Docker、Docker Compose、Cloudflare Tunnel（`deployment_default` ネットワークで動いている cloudflared）。

```bash
git clone https://github.com/duriyudha/gomi-bot.git
```

```bash
cd gomi-bot
```

```bash
cp .env.example .env
```

`.env` を開いて、LINE Developers の画面にある「チャネルシークレット」と「チャネルアクセストークン」を入れます。

```bash
docker compose up -d --build
```

```bash
docker compose logs -f
```

### Cloudflare Tunnel の設定

ポートは外に出していません。cloudflared と同じ `deployment_default` ネットワークにいるので、名前で届きます。
Tunnel の設定で、`gomi.duriyudha.com` の行き先を次にします。

```
http://gomi-bot:8000
```

### LINE Developers の設定

- Webhook URL：`https://gomi.duriyudha.com/callback`
- 「Webhook の利用」をオンにします。
- 「応答メッセージ」（自動の返事）はオフにします。

### データについて

- SQLite のファイルは `gomi-data` という Docker ボリュームの `/data/gomi.db` にあります。コンテナを作り直しても消えません。
- `schedule.yml` はコンテナの外から読みこんでいます。直したら `docker compose restart` だけで反映されます。

---

## 5. テスト

```bash
pip install -r requirements-dev.txt
```

```bash
pytest
```

テストしていること：

- 毎週のルール（火・金、木、土）
- 第2・第4水曜日（水曜日が5回ある月もふくむ）
- 休みの日（年末年始）
- 月や年をまたぐ「明日」（例：11/30 → 12/1）
- 190通で止まる仕組み
- 署名が正しくないと 400 になること
