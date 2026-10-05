"""Tavily联网天气检索：不使用固定城市样例，不把搜索摘要当作观测API。"""
import json
import math
import logging
import re
from datetime import datetime, timedelta
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx

logger = logging.getLogger('smartchat.weather')

WEATHER_CODES = {0:'晴',1:'晴间少云',2:'多云',3:'阴',45:'雾',48:'霜雾',
    51:'小毛毛雨',53:'毛毛雨',55:'强毛毛雨',56:'冻毛毛雨',57:'强冻毛毛雨',
    61:'小雨',63:'中雨',65:'大雨',66:'冻雨',67:'强冻雨',71:'小雪',73:'中雪',75:'大雪',
    77:'雪粒',80:'阵雨',81:'中等阵雨',82:'强阵雨',85:'阵雪',86:'强阵雪',
    95:'雷暴',96:'雷暴伴冰雹',99:'强雷暴伴冰雹'}
REGIONS = ('北京市','天津市','上海市','重庆市','内蒙古','黑龙江','新疆','西藏',
    '北京','天津','上海','重庆','山西','河北','河南','山东','江苏','浙江','安徽','福建',
    '江西','湖北','湖南','广东','广西','海南','四川','贵州','云南','陕西','甘肃','青海',
    '宁夏','辽宁','吉林','台湾','香港','澳门')


class WeatherSearch:
    def __init__(self, settings, transport=None, clock=None):
        self.settings, self.transport = settings, transport
        self.clock = clock or (lambda: datetime.now(ZoneInfo('Asia/Shanghai')))

    def search(self, city):
        city = city.strip()
        def failed(message):
            return json.dumps({'status': 'unavailable', 'city': city, 'message': message}, ensure_ascii=False)
        if not re.fullmatch(r'[\u3400-\u9fffA-Za-z· .-]{1,60}', city):
            return failed('请提供明确的城市名称，例如北京、山西太原或London')
        key = self.settings.tavily_api_key
        if not key:
            return failed('天气联网查询尚未配置，请在本机backend/.env填写TAVILY_API_KEY；无法确认当前天气')
        now = self.clock().astimezone(ZoneInfo('Asia/Shanghai'))
        query = f'{city} {now:%Y年%m月%d日} 今日天气 最新天气预报 当前温度 降雨'
        try:
            with httpx.Client(timeout=self.settings.weather_timeout, transport=self.transport,
                              follow_redirects=False, trust_env=False) as client:
                response = client.post('https://api.tavily.com/search',
                    headers={'Authorization': f'Bearer {key}'}, json={
                        'query': query, 'topic': 'general', 'search_depth': 'basic',
                        'max_results': 3, 'time_range': 'day', 'include_answer': False,
                        'include_raw_content': False, 'include_published_date': True,
                        'auto_parameters': False,
                        'include_domains': ['weather.com.cn','nmc.cn','cma.cn','info.gov.hk',
                            'weather.gov','metoffice.gov.uk','bom.gov.au','weather.gc.ca',
                            'meteofrance.com','weather.com','accuweather.com','timeanddate.com'],
                    })
                if response.status_code in (401, 403):
                    return failed('天气搜索密钥无效或权限不足，请检查本地TAVILY_API_KEY')
                if response.status_code in (429, 432, 433):
                    return failed('天气搜索服务限流或额度不足，请稍后再试或检查Tavily账户')
                response.raise_for_status()
                payload = response.json()
                try:
                    current_weather, weather_source = self.current_weather(city, client, now)
                    weather_error = None
                except ValueError as exc:
                    current_weather, weather_source = None, None
                    known_errors = ('无法确定城市位置', '城市名存在歧义，请补充省份或国家', '气象数据时间过期')
                    weather_error = str(exc) if str(exc) in known_errors else '当前气象数据暂不可用，无法确认当前温度'
                except (httpx.HTTPError, TypeError, KeyError, AttributeError):
                    current_weather, weather_source = None, None
                    weather_error = '当前气象数据暂不可用，不能从不明日期的摘要推断当前温度'
            sources = []
            if weather_source:
                sources.append(weather_source)
            rows = payload.get('results')
            lookup_city = city.removesuffix('市')
            region = next((name for name in REGIONS if lookup_city.startswith(name) and len(lookup_city) > len(name)), '')
            if region:
                lookup_city = lookup_city[len(region):].removeprefix('省').removeprefix('市').strip()
            for row in (rows[:3] if isinstance(rows, list) else []):
                if not isinstance(row, dict):
                    continue
                url, content = row.get('url'), row.get('content')
                if not isinstance(url, str) or not isinstance(content, str) or not content.strip():
                    continue
                # 搜索引擎可能返回异地页面，只保留提及所查城市的摘要。
                if lookup_city.casefold() not in (str(row.get('title', '')) + ' ' + content).casefold():
                    continue
                try:
                    parsed = urlsplit(url)
                except ValueError:
                    continue
                if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username:
                    continue
                sources.append({'title': str(row.get('title') or '天气来源')[:160],
                    'url': url[:2000], 'snippet': content[:1200],
                    'published_date': str(row.get('published_date') or '来源未提供更新时间')[:80]})
            if not sources:
                return failed('联网搜索没有返回可用天气来源，无法确认当前天气；请补充省份或稍后再试')
            result = {'status': 'ok', 'city': city, 'queried_at': now.isoformat(),
                      'date_requested': now.strftime('%Y-%m-%d'), 'sources': sources,
                      'current_weather': current_weather, 'current_weather_error': weather_error,
                      'notice': '气温和当前天气优先使用current_weather气象模型数据，使用“数据时间”，禁止称为“观测时间”或实测。网页摘要仅作为补充，核对城市与适用日期；不明或过期时明确无法确认。查询时间不是数据时间。'}
            return json.dumps(result, ensure_ascii=False).replace(key, '[已隐藏]')
        except httpx.TimeoutException:
            return failed('天气联网搜索超时，无法确认当前天气，请稍后再试')
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            logger.warning('天气联网查询失败，未返回上游详情')
            return failed('天气联网搜索暂时不可用，无法确认当前天气，请稍后再试')

    def current_weather(self, city, client, now):
        city = city.removesuffix('市')
        region = next((name for name in REGIONS if city.startswith(name) and len(city) > len(name)), '')
        name = city[len(region):].removeprefix('省').removeprefix('市').strip() if region else city
        name = name.removesuffix('市')
        response = client.get('https://geocoding-api.open-meteo.com/v1/search',
            params={'name': name, 'count': 5, 'language': 'zh', 'format': 'json'})
        response.raise_for_status()
        candidates = response.json().get('results', [])
        matches = [row for row in candidates if isinstance(row, dict)
                   and str(row.get('name', '')).removesuffix('市').casefold() == name.casefold()
                   and (not region or region.removesuffix('市') in str(row.get('admin1', '')))]
        if not matches:
            raise ValueError('无法确定城市位置')
        place = matches[0]
        if len(matches) > 1 and place.get('feature_code') not in ('PPLC','PPLA'):
            raise ValueError('城市名存在歧义，请补充省份或国家')
        latitude, longitude = float(place['latitude']), float(place['longitude'])
        if not math.isfinite(latitude) or not math.isfinite(longitude) or not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError('位置坐标无效')
        response = client.get('https://api.open-meteo.com/v1/forecast', params={
            'latitude': latitude, 'longitude': longitude, 'timezone': 'Asia/Shanghai', 'forecast_days': 1,
            'current': 'temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m',
            'daily': 'temperature_2m_max,temperature_2m_min,precipitation_probability_max',
        })
        response.raise_for_status()
        data = response.json()
        current = data['current']
        stamp = datetime.fromisoformat(current['time'])
        stamp = stamp.astimezone(ZoneInfo('Asia/Shanghai')) if stamp.tzinfo else stamp.replace(tzinfo=ZoneInfo('Asia/Shanghai'))
        if abs(now - stamp) > timedelta(hours=2):
            raise ValueError('气象数据时间过期')
        temperature = current['temperature_2m']
        if type(temperature) not in (int, float) or not math.isfinite(temperature):
            raise ValueError('气象温度无效')
        units = data.get('current_units', {})
        if units.get('temperature_2m') != '°C' or units.get('wind_speed_10m') != 'km/h':
            raise ValueError('气象数据单位异常')
        daily = data.get('daily', {})
        today = None
        if (daily.get('time') or [None])[0] == now.strftime('%Y-%m-%d'):
            today = {key: daily[key][0] for key in ('temperature_2m_max','temperature_2m_min','precipitation_probability_max') if daily.get(key)}
        value = {'provider': 'Open-Meteo', 'location': ' '.join(str(place.get(k) or '') for k in ('country','admin1','name')).strip(),
                 'latitude':latitude, 'longitude':longitude, 'data_time_beijing':stamp.isoformat(),
                 'temperature_c':temperature, 'weather':WEATHER_CODES.get(current.get('weather_code'), '未知天气代码'),
                 'apparent_temperature_c':current.get('apparent_temperature'),
                 'relative_humidity_percent':current.get('relative_humidity_2m'),
                 'precipitation_mm':current.get('precipitation'), 'wind_kmh':current.get('wind_speed_10m'),
                 'today_forecast':today, 'notice':'联网获取的气象模型当前数据及预报，不是本地模拟样例，也不宣称为现场气象站实测'}
        source = {'title': 'Open-Meteo 当前天气与今日预报', 'url':str(response.url),
                  'snippet':f"气象数据时间（北京时间）：{stamp.isoformat()}；地点：{value['location']}",
                  'published_date':stamp.isoformat()}
        return value, source


def weather_citations(messages):
    """仅从本轮实际天气工具结果附加来源，不依赖模型自行写对URL。"""
    lines, seen = [], set()
    for message in messages:
        if message.type != 'tool' or getattr(message, 'name', '') != 'get_weather':
            continue
        try:
            result = json.loads(message.content)
            if result.get('status') != 'ok':
                continue
            sources = result.get('sources', [])
            heading_added = False
            for source in sources:
                url = source.get('url', '')
                parsed = urlsplit(url)
                if url in seen or parsed.scheme not in ('http', 'https') or not parsed.hostname:
                    continue
                if not heading_added:
                    lines.append(f"天气查询来源（{result.get('city', '')}；联网查询时间：{result.get('queried_at', '')}）")
                    heading_added = True
                lines.append(f"{source.get('title', '天气来源')}：{url}")
                seen.add(url)
        except (ValueError, TypeError, AttributeError):
            continue
    return '\n'.join(lines)
