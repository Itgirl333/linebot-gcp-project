from linebot.models import *
import wenxin_api
from wenxin_api.tasks.text_to_image import TextToImage
from wenxin_api.tasks.composition import Composition
from opencc import OpenCC
import requests
from bs4 import BeautifulSoup as bs
import random
import json

wenxin_api.ak = "your api key"
wenxin_api.sk = "your secret key"

def detect_json_array_to_new_message_array(fileName):
    with open(fileName, encoding = 'utf8') as f:
        jsonArray = json.load(f)
    returnArray = []
    for jsonObject in jsonArray:
        message_type = jsonObject.get('type')
        if message_type == 'text':
            returnArray.append(TextSendMessage.new_from_json_dict(jsonObject))
        elif message_type == 'imagemap':
            returnArray.append(ImagemapSendMessage.new_from_json_dict(jsonObject))
        elif message_type == 'template':
            returnArray.append(TemplateSendMessage.new_from_json_dict(jsonObject))
        elif message_type == 'image':
            returnArray.append(ImageSendMessage.new_from_json_dict(jsonObject))
        elif message_type == 'sticker':
            returnArray.append(StickerSendMessage.new_from_json_dict(jsonObject))  
        elif message_type == 'audio':
            returnArray.append(AudioSendMessage.new_from_json_dict(jsonObject))  
        elif message_type == 'location':
            returnArray.append(LocationSendMessage.new_from_json_dict(jsonObject))
        elif message_type == 'flex':
            returnArray.append(FlexSendMessage.new_from_json_dict(jsonObject))  
        elif message_type == 'video':
            returnArray.append(VideoSendMessage.new_from_json_dict(jsonObject))    
    return returnArray


# 爬取水果資訊
def get_fruit_info():
    headers = {'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36'}
    res = requests.get('https://www.superbuy.com.tw/collection_fast.php?main_cate=609', headers = headers)
    soup = bs(res.text, 'html.parser')
    location = soup.find(id = '649')
    fruits = location.find_all('div', 'product')
    total = []
    result = []
    for fruit in fruits:
        img = fruit.find_all('li')[0].find('img')['src']
        name = fruit.find_all('li')[2].text.strip()
        weight = fruit.find_all('li')[3].text.strip()
        price = fruit.find_all('li')[4].text.strip()
        total.append({'img': img, 'name': name, 'weight': weight, 'price': price})
    idxs = []
    while len(idxs) < 6:
        idx = random.randint(0, len(total)-1)
        if idx not in idxs:
            idxs.append(idx)
    for idx in idxs:
        result.append(total[idx])

    with open("line_message_json/fruits.json", encoding = 'utf8') as f:
        fruits = json.load(f)
    for i in range(6):
        fruits[0]['contents']['contents'][i]['hero']['url'] = result[i]['img']
        fruits[0]['contents']['contents'][i]['body']['contents'][0]['text'] = result[i]['name']
        fruits[0]['contents']['contents'][i]['body']['contents'][1]['text'] = result[i]['weight']
        fruits[0]['contents']['contents'][i]['body']['contents'][2]['text'] = result[i]['price']
    fruits_message = FlexSendMessage.new_from_json_dict(fruits[0])
    with open("line_message_json/fruits.json", 'w', newline = '', encoding = 'utf8') as f:
        json.dump(fruits, f, indent = 4, ensure_ascii = False)
    return fruits_message


# 文字生圖。目前支持风格有：油画、水彩画、卡通、粉笔画、儿童画、蜡笔画
def text_to_image(input_text, style = "油画"):
    input_text_s = OpenCC('tw2s').convert(input_text)
    input_dict = {
        "text": input_text_s,
        "style": style
    }
    rst = TextToImage.create(**input_dict)
    print(rst['imgUrls'])
    with open("line_message_json/img.json", encoding='utf8') as f:
        img = json.load(f)
    for idx, url in enumerate(rst['imgUrls']):
        img[0]['template']['columns'][idx]['imageUrl'] = url
        # img[0]['template']['columns'][idx]['action']['uri'] = url
    img_message = TemplateSendMessage.new_from_json_dict(img[0])
    return img_message


# 生成歌詞
def lyric_generate(input_text):
    input_text_s = OpenCC('tw2s').convert(input_text)
    url = "https://wenxin.baidu.com/wenxin/demo/genlyrics"
    payload = {
        'keyWord': '["' + input_text_s + '"]',
        'name': '歌词'
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Cookie': 'BAIDUID=9B0A87B3977A05C8B4A2D700254754D4:FG=1'
    }

    res = requests.post(url, headers=headers, data=payload)
    result = res.json()['content']['result']
    verse = ""
    chorus = ""
    if '主歌' in result:
        verse = result.split('主歌\n')[-1]
        if '副歌' in verse:
            chorus = OpenCC('s2tw').convert(verse.split('副歌\n')[-1])
            verse = OpenCC('s2tw').convert(verse.split('副歌\n')[0])

    with open("line_message_json/lyric.json", encoding='utf8') as f:
        lyric = json.load(f)

    lyric[0]['contents']['body']['contents'][0]['text'] = input_text
    lyric[0]['contents']['body']['contents'][1]['contents'][0]['contents'][1]['text'] = verse
    lyric[0]['contents']['body']['contents'][1]['contents'][1]['contents'][1]['text'] = chorus
    lyric_message = FlexSendMessage.new_from_json_dict(lyric[0])
    return lyric_message


# Line 模擬付款網址
def get_check(amount):
    url = "https://sandbox-api-pay.line.me/v2/payments/request"
    header = {"Content-Type":"application/json","X-LINE-ChannelId":"1657565756","X-LINE-ChannelSecret":"00ca3d68e490d4c527cd61adfeac3f4c"}
    payload = {"amount": amount,
        "currency": "TWD", 
        "productName": "花媽優選",
        "productImageUrl": "https://images.theconversation.com/files/417973/original/file-20210826-2243-15s35b8.jpg?ixlib=rb-1.1.0&q=45&auto=format&w=1200&h=1200.0&fit=crop",
        "confirmUrl": "http://127.0.0.1:3000",
        "orderId": "Order202210200011"
    }
    res = requests.post(url, data = json.dumps(payload), headers = header, verify = False)
    jd = res.json()
    return jd['info']['paymentUrl']['web']