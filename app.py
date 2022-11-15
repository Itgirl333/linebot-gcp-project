from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *
from linebot.models.template import ButtonsTemplate, CarouselTemplate, ConfirmTemplate, ImageCarouselTemplate
from others.func import *
import json
import urllib.request
import os

import tensorflow.keras
from PIL import Image, ImageOps
import numpy as np

# 建立日誌紀錄設定檔，https://googleapis.dev/python/logging/latest/stdlib-usage.html
import logging
import google.cloud.logging
from google.cloud.logging.handlers import CloudLoggingHandler
from google.cloud import storage
from google.cloud import firestore

# 啟用log的客戶端
client = google.cloud.logging.Client()
# 建立line event log，用來記錄line event
bot_event_handler = CloudLoggingHandler(client, name = "cxcxc_bot_event")
bot_event_logger = logging.getLogger('cxcxc_bot_event')
bot_event_logger.setLevel(logging.INFO)
bot_event_logger.addHandler(bot_event_handler)

app = Flask(__name__)

line_bot_api = LineBotApi('your channel access token')
handler = WebhookHandler('your channel secret')



@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    print(body)
    # 消息交由 bot_event_logger 傳回 GCP
    bot_event_logger.info(body)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)
    return 'OK'


# 设定图文选单
with open("line_message_json/menu.json", encoding = 'utf8') as f:
    menuJson = json.load(f)
lineRichMenuId = line_bot_api.create_rich_menu(rich_menu = RichMenu.new_from_json_dict(menuJson))
with open("line_message_json/menu.png", 'rb') as uploadImageFile:
    line_bot_api.set_rich_menu_image(lineRichMenuId, 'image/jpeg', uploadImageFile)

@handler.add(FollowEvent)
def handle_follow_event(event):
    # 绑定图文选单，並傳送欢迎訊息
    line_user_profile= line_bot_api.get_profile(event.source.user_id)
    line_bot_api.link_rich_menu_to_user(line_user_profile.user_id, lineRichMenuId)
    welcome_message = detect_json_array_to_new_message_array("line_message_json/welcome.json")
    line_bot_api.reply_message(event.reply_token, welcome_message)

    # 下載用戶大頭照到本地，並上傳到 cloud storage
    file_name = line_user_profile.user_id + '.jpg'
    urllib.request.urlretrieve(line_user_profile.picture_url, file_name)
    storage_client = storage.Client()
    bucket_name = "linebot-tibame01-storage"
    destination_blob_name = f"{line_user_profile.user_id}/user_pic.png"
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(file_name)
    os.remove(file_name)

    # 將用戶個資上傳到 firestore
    user_dict={
        "user_id": line_user_profile.user_id,
        "picture_url": f"https://storage.googleapis.com/{bucket_name}/destination_blob_name",
        "display_name": line_user_profile.display_name,
        "status_message": line_user_profile.status_message,
        "system_language": line_user_profile.language
    }
    db = firestore.Client()
    doc_ref = db.collection(u'line-user').document(user_dict.get("user_id"))
    doc_ref.set(user_dict)


@handler.add(MessageEvent, message = TextMessage)
def handle_text_message(event):
    line_user_profile= line_bot_api.get_profile(event.source.user_id)
    if event.message.text.find('@') == 0:
        input_text = event.message.text[1:]
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text = f'正在生成「{input_text}」的圖片，請稍等 30 秒'))
        img_message = text_to_image(input_text)
        line_bot_api.push_message(line_user_profile.user_id, img_message)
    elif event.message.text.find('#') == 0:
        input_text = event.message.text[1:]
        lyric_message = lyric_generate(input_text)
        line_bot_api.reply_message(event.reply_token, [TextSendMessage(text = f'正在生成屬於你的「{input_text}」獨一無二的歌詞'), lyric_message])
    else:
        pass


@handler.add(MessageEvent, message = LocationMessage)
def handle_location_message(event):
    with open("line_message_json/confirm.json", encoding = 'utf8') as f:
        confirm = json.load(f)
    confirm[0]['template']['text'] = f"您位於「{event.message.address}」，離您最近的里為「全安里」，日後商品會寄送該里的位置，請確認"
    confirm_message = TemplateSendMessage.new_from_json_dict(confirm[0])
    line_bot_api.reply_message(event.reply_token, confirm_message)


@handler.add(MessageEvent, message = ImageMessage)
def handle_image_message(event):
    image_blob = line_bot_api.get_message_content(event.message.id)
    temp_file_path = event.message.id + '.png'
    with open(temp_file_path, 'wb') as fd:
        for chunk in image_blob.iter_content():
            fd.write(chunk)
    
    # 將用戶發送的圖片上傳到 cloud storage
    storage_client = storage.Client()
    bucket_name = 'linebot-tibame01-storage'
    destination_blob_name = f'{event.source.user_id}/image/{event.message.id}.png'
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(temp_file_path)

    # 圖片辨識
    model = tensorflow.keras.models.load_model('converted_savedmodel/model.savedmodel')
    data = np.ndarray(shape=(1, 224, 224, 3), dtype=np.float32)
    image = Image.open(temp_file_path)
    size = (224, 224)
    image = ImageOps.fit(image, size, Image.ANTIALIAS)
    image_array = np.asarray(image)
    normalized_image_array = (image_array.astype(np.float32) / 127.0) - 1
    data[0] = normalized_image_array
    # run the inference
    prediction = model.predict(data)
    index = np.argmax(prediction[0])
    if index == 0:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text = '已識別到您的澆水行為，您已完成今日打卡，恭喜獲得 5 點！明天繼續澆水可再獲得 5 點喔'))
    else:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text = '不好意思，無法識別您的澆水行為，請重新上傳一張澆水的圖片'))
    os.remove(temp_file_path)


@handler.add(PostbackEvent)
def handle_post_message(event):
    if event.postback.data.find('location_confirmed') == 0:    # 圖文選單1: 團購商品 
        text_message = TextSendMessage(text = '已確認您的位置。快來逛逛最新的社區團購商品吧！')
        fruit_message = get_fruit_info()
        line_bot_api.reply_message(event.reply_token, [text_message, fruit_message])
    elif event.postback.data.find('tree_adopt') == 0:          # 圖文選單2: 果樹認養
        adopt_message = detect_json_array_to_new_message_array("line_message_json/adopt.json")
        line_bot_api.reply_message(event.reply_token, adopt_message)      
    elif event.postback.data.find('get_coupon') == 0:          # 圖文選單3: 行銷活動
        campaign_message = detect_json_array_to_new_message_array("line_message_json/campaign.json")
        line_bot_api.reply_message(event.reply_token, campaign_message)
    elif event.postback.data.find('my_shopping_cart') == 0:    # 圖文選單4: 我的購物車
        cart_message = detect_json_array_to_new_message_array("line_message_json/cart.json")
        line_bot_api.reply_message(event.reply_token, cart_message)
    elif event.postback.data.find('my_order') == 0:            # 圖文選單5: 我的訂單
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text = '您還沒有購買任何商品'))
    elif event.postback.data.find('profile_settings') == 0:    # 圖文選單6: 個人資訊設定
        setting_message = detect_json_array_to_new_message_array("line_message_json/setting.json")        
        line_bot_api.reply_message(event.reply_token, setting_message)
    elif event.postback.data.find('location_not_confirmed') == 0:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text = '您也可以在個人設定中自行設定喔'))
    elif event.postback.data.find('add_to_cart') == 0:         # 加入購物車
        with open("line_message_json/fruits.json", encoding = 'utf8') as f:
            fruits = json.load(f)
        idx = int(event.postback.data[-1]) - 1
        product_name = fruits[0]['contents']['contents'][idx]['body']['contents'][0]['text']
        product_price = fruits[0]['contents']['contents'][idx]['body']['contents'][2]['text']
        print(idx, product_name, product_price)
        product_info = {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "text",
                    "text": product_name,
                    "size": "sm",
                    "color": "#555555",
                    "flex": 0
                },
                {
                    "type": "text",
                    "text": product_price,
                    "size": "sm",
                    "color": "#111111",
                    "align": "end"
                }
            ]
        }        
        with open("line_message_json/cart.json", encoding = 'utf8') as f:
            cart = json.load(f)
        cart[0]['contents']['body']['contents'][5]['contents'].insert(0, product_info)
        total_price = int(cart[0]['contents']['body']['contents'][5]['contents'][-3]['contents'][1]['text'][2:])
        total_price += int(product_price[2:])
        cart[0]['contents']['body']['contents'][5]['contents'][-3]['contents'][1]['text'] = f'$ {total_price}'   # 要改！！！
        with open("line_message_json/cart.json", 'w', newline = '', encoding = 'utf8') as f:
            json.dump(cart, f, indent = 4, ensure_ascii = False)     
        cart_message = FlexSendMessage.new_from_json_dict(cart[0])
        line_bot_api.reply_message(event.reply_token, cart_message)
    elif event.postback.data.find('clear_cart') == 0:         # 清空購物車
        with open("line_message_json/cart.json", encoding = 'utf8') as f:
            cart = json.load(f)
        del cart[0]['contents']['body']['contents'][5]['contents'][:-4]
        cart[0]['contents']['body']['contents'][5]['contents'][-3]['contents'][1]['text'] = '$ 0'
        with open("line_message_json/cart.json", 'w', newline = '', encoding = 'utf8') as f:
            json.dump(cart, f, indent = 4, ensure_ascii = False)     
        cart_message = FlexSendMessage.new_from_json_dict(cart[0])
        line_bot_api.reply_message(event.reply_token, cart_message)
    elif event.postback.data.find('pay_rightnow') == 0:        # 直接下單
        with open("line_message_json/cart.json", encoding = 'utf8') as f:
            cart = json.load(f)
        total_price = int(cart[0]['contents']['body']['contents'][5]['contents'][-3]['contents'][1]['text'][2:])
        pay_url = get_check(total_price)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text = f'付款連結如下：{pay_url}'))   
    elif event.postback.data.find('add_to_adopt') == 0:        # 加入認養
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text = '您所在區域為全安里，已為您登記全安里的集體認養，屆時會根據參與人數平攤整體的認養費用，會再透過此窗口通知付款及細節'))
    elif event.postback.data.find('save_coupon') == 0:         # 儲存優惠券
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text = '已儲存優惠券'))
    elif event.postback.data.find('participate_campaign_1') == 0:         # 參加行銷活動 1
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text = '您已進入文字生圖比賽，請輸入描述語，範例：@鄉村果園，農夫採摘水果，16世紀歐洲，文藝復興'))
    elif event.postback.data.find('participate_campaign_2') == 0:         # 參加行銷活動 2
        guide_message = detect_json_array_to_new_message_array("line_message_json/guide.json")
        line_bot_api.reply_message(event.reply_token, guide_message)
    elif event.postback.data.find('participate_campaign_3') == 0:         # 參加行銷活動 3
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text = '您已進入生成歌詞比賽，請輸入描述語，範例：#鄉村生活'))
    elif event.postback.data.find('commit') == 0:         # 提交作品參加比賽
        coupon_message = detect_json_array_to_new_message_array("line_message_json/coupon.json")
        line_bot_api.reply_message(event.reply_token, coupon_message)       
    else:
        pass


if __name__ == "__main__":
    app.run(host = "0.0.0.0", port = int(os.environ.get("PORT", 8080)))