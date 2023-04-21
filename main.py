from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, ImageMessage, TextSendMessage, ImageSendMessage
from flask import Flask, request, abort
from pathlib import Path
from clip_interrogator import Config, Interrogator
from PIL import Image
import openai
from flask_ngrok import run_with_ngrok # これが重要 googlecolabo用
import os
app = Flask(__name__)
app.debug = False
run_with_ngrok(app) # これが重要 googlecolabo用


# アクセストークンの読み込み
channel_access_token = "YOUR_CHANNEL_ACCESS_TOKEN"
channel_secret = "YOUR_CHANNEL_SECRET"

# LINE Messaging API のインスタンスを生成
line_bot_api = LineBotApi(channel_access_token)
# LINE Messaging API からのWebhookの署名検証に使うインスタンスを生成
handler = WebhookHandler(channel_secret)


# CLIP-interrogatorのインスタンスを生成
ci = Interrogator(Config(clip_model_name="ViT-L-14/openai"))

# OpenaiのAPIキー
openai.api_key = "API_KEY"

# http://127.0.0.1:5000をルートとして、("")の中でアクセスポイント指定

@app.route("/", methods=['POST'])
def callback():
  signature = request.headers['X-Line-Signature']
  body = request.get_data(as_text=True)
  if body:
    print("あるよ")
  # app.logger.info("Request body: " + body)
  print(body)

  try:
    print("tryに入った")
    handler.handle(body, signature)
  except InvalidSignatureError:
    abort(400)

  return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    print("入った")
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=event.message.text),
    )


@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
  print("HandleImageに入りました")
  message_id = event.message.id
  # message_idから画像のバイナリデータを取得
  message_content = line_bot_api.get_message_content(message_id)
  print(message_content)

  with open(Path(f"image/{message_id}.jpg").absolute(), "wb") as f:
    # バイナリを1024バイトずつ書き込む
    for chunk in message_content.iter_content():
      f.write(chunk)
  print("画像書き込み完了")
  line_bot_api.push_message(event.source.user_id, TextSendMessage(text="インスタ中"))

  image = Image.open(f"image/{message_id}.jpg")
  # CLIP-interrogatorを使って画像を表現するテキストを取得
  text = ci.interrogate(image)
  print("clip-interogater完了")
  print(text)
  # ChatGPTのインスタンスを作成し、タイトルとあらすじを作るようにお願いする
  movietitlemaker = ChatGPT(system_setting="今から複数の単語を入力します。あなたは、その単語から連想されるInstagramで人気のハッシュタグを返してください")
  # ChatGPTのインスタンスにCLIP-interrogatorが出力したテキストを入力
  movietitlemaker.input_message(text)
  # ChatGPTの返答（タイトルとあらすじ）を取得
  movie = movietitlemaker.input_list[-1]["content"]
  # タイトルとあらすじをメッセージでユーザに送信
  line_bot_api.push_message(event.source.user_id, TextSendMessage(text=movie))

class ChatGPT:

  def __init__(self, system_setting):
    # システム設定として与えられたメッセージを用意する
    self.system = {"role": "system", "content": system_setting}

    # これまでに入力されたメッセージのリスト
    self.input_list = [self.system]

    # OpenAI API で返されたログのリスト
    self.logs = []

  def input_message(self, input_text):
    # ユーザーが入力したテキストをリストに追加する
    self.input_list.append({"role": "user", "content": input_text})

    # OpenAI API による応答を取得する
    result = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=self.input_list)

    # OpenAI API から返されたログをリストに追加する
    self.logs.append(result)

    # 応答をリストに追加する
    self.input_list.append({
      "role": "assistant",
      "content": result.choices[0].message.content
    })

if __name__ == '__main__':
  app.run()
