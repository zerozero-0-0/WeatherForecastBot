import openmeteo_requests

import requests_cache
import pandas as pd
from retry_requests import retry
import discord
import os
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv

# .envファイルを読み込む
load_dotenv()

# トークンの取得
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
# チャンネルのID
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))

#メッセージを送る時間を指定
HOUR = 6
MINUTE = 0
SECOND = 0

# Setup the Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)

# Make sure all required weather variables are listed here
# The order of variables in hourly or daily is important to assign them correctly below
url = "https://api.open-meteo.com/v1/forecast"

first_locate = os.getenv('FIRST_LOCATE')
second_locate = os.getenv('SECOND_LOCATE')

first_locate_lat = os.getenv('FIRST_LOCATE_LATITUDE') 
first_locate_lon = os.getenv('FIRST_LOCATE_LONGITUDE')

second_locate_lat = os.getenv('SECOND_LOCATE_LATITUDE') 
second_locate_lon = os.getenv('SECOND_LOCATE_LONGITUDE')


params = {
	"latitude": [first_locate_lat, second_locate_lat],
	"longitude": [first_locate_lon, second_locate_lon],
	"hourly": "precipitation_probability",
	"daily": ["temperature_2m_max", "temperature_2m_min"],
	"timezone": "GMT",
	"forecast_days": 1
}

#Intents の設定
intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

async def fetch_api_data():
    try:
        responses = openmeteo.weather_api(url, params=params)
        return responses
    except Exception as e:
        print(f"APIを取得できませんでした:{e}")
        return None

async def send_message(channel):
    responses = await fetch_api_data()
    if not responses:
        return
    
    message = ""

    for i in range(len(responses)):
        # Process first location. Add a for-loop for multiple locations or weather models
        response = responses[i]

        #Process hourly data. The order of variables needs to be the same as requested.
        hourly = response.Hourly()
        hourly_precipitation_probability = hourly.Variables(0).ValuesAsNumpy()

        hourly_data = {"date": pd.date_range(
	        start = pd.to_datetime(hourly.Time(), unit = "s", utc = True),
	        end = pd.to_datetime(hourly.TimeEnd(), unit = "s", utc = True),
	        freq = pd.Timedelta(seconds = hourly.Interval()),
	        inclusive = "left"
        )}
        hourly_data["precipitation_probability"] = hourly_precipitation_probability

        hourly_dataframe = pd.DataFrame(data = hourly_data)
        
        # Process daily data. The order of variables needs to be the same as requested.
        daily = response.Daily()
        daily_temperature_2m_max = daily.Variables(0).ValuesAsNumpy()
        daily_temperature_2m_min = daily.Variables(1).ValuesAsNumpy()

        daily_data = {"date": pd.date_range(
	        start = pd.to_datetime(daily.Time(), unit = "s", utc = True),
    	    end = pd.to_datetime(daily.TimeEnd(), unit = "s", utc = True),
	        freq = pd.Timedelta(seconds = daily.Interval()),
	        inclusive = "left"
        )}
        daily_data["temperature_2m_max"] = daily_temperature_2m_max
        daily_data["temperature_2m_min"] = daily_temperature_2m_min

        daily_dataframe = pd.DataFrame(data = daily_data)
    
        # 雨が降りそうな時間を配列に持つ
        rain = []
        for j in range(0, 24):
            if hourly_dataframe["precipitation_probability"][j] > 40.0:
                rain.append(f"{j}:00")
    
    
        # メッセージを作成
        if i == 0:
            message += f"{first_locate}\n"
        elif i == 1:
            message += f"{second_locate}\n"
    
        # 最高気温と最低気温を小数点第一位まで丸める
        max_temp = round(float(daily_dataframe['temperature_2m_max'][0]), 1)
        min_temp = round(float(daily_dataframe['temperature_2m_min'][0]), 1)
    
        message += f"最高気温 : {max_temp}度\n"
        message += f"最低気温 : {min_temp}度\n"
    
        if len(rain) > 0:
            message += "雨が降りそうな時間帯 : "
            for k in range(len(rain)):
                message += f"{rain[k]} "
            message += "\n"
    
        if i == 0:
            message += "\n"
    
    await channel.send(message)
        
@client.event
async def on_ready():
    print('ログインに成功しました')
    channel = client.get_channel(CHANNEL_ID)
    await channel.send("Botが起動しました")
    while not client.is_closed():
        now = datetime.now()
        target_time = now.replace(hour = HOUR, minute = MINUTE, second = SECOND)

        if now > target_time:
            target_time += timedelta(days = 1)
            
        wait_time = (target_time - now).total_seconds()
        
        await channel.send(f"次回の送信は{target_time}です")
        
        await asyncio.sleep(wait_time)
        
        
        try:
            await send_message(channel)
            print(f"今回は{now}に送信しました\n")
            print(f"次回の送信は{target_time}です\n")
        except Exception as e:
            print(f"メッセージの送信に失敗しました:{e}")
        
        await asyncio.sleep(24 * 60 * 60)
    
client.run(TOKEN)

