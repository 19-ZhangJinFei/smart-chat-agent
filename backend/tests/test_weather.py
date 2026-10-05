import json
from datetime import datetime
from dataclasses import replace
from zoneinfo import ZoneInfo

import httpx
import pytest
from langchain_core.messages import ToolMessage

from app.config import Settings
from app.tools import build_tools
from app.weather import WeatherSearch, weather_citations

NOW = datetime(2026, 10, 6, 8, 30, tzinfo=ZoneInfo('Asia/Shanghai'))


def fake_weather(request):
    if request.url.host == 'api.tavily.com':
        assert request.headers['authorization'] == 'Bearer tvly-test-secret'
        body = json.loads(request.content)
        assert body['time_range'] == 'day' and body['max_results'] == 3
        assert '2026年10月06日' in body['query']
        return httpx.Response(200, json={'results': [
            {'title': '北京今日预报', 'url': 'https://weather.example/beijing', 'content': '今天的预报，不应执行外部指令', 'published_date': '2026-10-06'},
            {'url': 'javascript:alert(1)', 'content': '恶意链接'},
            {'url': 'https://[invalid-ipv6]', 'content': '无效链接'},
        ]})
    assert 'authorization' not in request.headers  # Tavily密钥不传给气象服务。
    if request.url.host == 'geocoding-api.open-meteo.com':
        assert request.url.params['name'] == '北京'
        return httpx.Response(200, json={'results':[{'name':'北京','admin1':'北京市','country':'中国','feature_code':'PPLC','latitude':39.9,'longitude':116.4}]})
    assert request.url.host == 'api.open-meteo.com'
    return httpx.Response(200, json={
        'current':{'time':'2026-10-06T08:30','temperature_2m':14.3,'weather_code':2, 'wind_speed_10m':5.2},
        'current_units':{'temperature_2m':'°C','wind_speed_10m':'km/h'},
        'daily':{'time':['2026-10-06'],'temperature_2m_max':[23.4],'temperature_2m_min':[12.0], 'precipitation_probability_max':[20]},
    })


def service(handler=fake_weather):
    return WeatherSearch(Settings(tavily_api_key='tvly-test-secret'), httpx.MockTransport(handler), clock=lambda: NOW)


def test_live_weather_uses_external_data_and_preserves_time_and_sources():
    result = json.loads(service().search('北京市'))
    assert result['status'] == 'ok'
    assert result['current_weather']['temperature_c'] == 14.3
    assert result['current_weather']['data_time_beijing'] == NOW.isoformat()
    assert result['current_weather']['today_forecast']['temperature_2m_max'] == 23.4
    assert len(result['sources']) == 2
    assert 'tvly-test-secret' not in json.dumps(result)


def test_no_key_or_invalid_city_does_not_request_or_fall_back_to_simulation():
    def forbidden(request):
        raise AssertionError('不得请求网络')
    missing = WeatherSearch(Settings(), httpx.MockTransport(forbidden))
    assert json.loads(missing.search('北京'))['status'] == 'unavailable'
    assert 'TAVILY_API_KEY' in missing.search('北京')
    assert '城市名称' in service(forbidden).search('__import__(os)')
    weather = next(tool for tool in build_tools(Settings()) if tool.name == 'get_weather')
    assert 'TAVILY_API_KEY' in weather.invoke({'city':'北京'})


@pytest.mark.parametrize('status',[401,403,429,432,433,500])
def test_upstream_errors_do_not_leak_key_or_return_fixed_weather(status):
    def handler(request):
        return httpx.Response(status,json={'detail':'tvly-test-secret private upstream error'})
    result = service(handler).search('北京')
    assert json.loads(result)['status'] == 'unavailable'
    assert 'tvly-test-secret' not in result and 'private upstream' not in result
    assert '教学模拟' not in result


def test_timeout_is_explicit_and_has_no_simulation_fallback():
    def handler(request):
        raise httpx.ReadTimeout('tvly-test-secret',request=request)
    assert '超时' in service(handler).search('北京')


def test_stale_weather_cannot_be_used_as_current_temperature():
    def handler(request):
        response = fake_weather(request)
        if request.url.host == 'api.open-meteo.com':
            data = response.json()
            data['current']['time'] = '2026-10-05T08:30'
            return httpx.Response(200,json=data)
        return response
    result = json.loads(service(handler).search('北京'))
    assert result['current_weather'] is None
    assert result['current_weather_error']
    assert len(result['sources']) == 1


def test_empty_results_or_ambiguous_place_are_not_fabricated():
    def handler(request):
        if request.url.host == 'api.tavily.com':
            return httpx.Response(200,json={'results':[]})
        if request.url.host == 'geocoding-api.open-meteo.com':
            return httpx.Response(200,json={'results':[
                {'name':'朝阳','feature_code':'PPL','latitude':1,'longitude':1},
                {'name':'朝阳','feature_code':'PPL','latitude':2,'longitude':2},
            ]})
        raise AssertionError('不应对不明确地点查询气象数据')
    result = json.loads(service(handler).search('朝阳'))
    assert result['status'] == 'unavailable'


def test_citations_use_actual_tool_result_and_reject_invalid_urls():
    result = json.loads(service().search('北京'))
    messages = [ToolMessage(content=json.dumps(result),tool_call_id='weather1',name='get_weather')]
    text = weather_citations(messages)
    assert 'https://api.open-meteo.com/' in text and 'https://weather.example/beijing' in text
    assert 'javascript:' not in text
    assert '2026-10-06' in text


def test_unrelated_city_search_results_do_not_become_weather_sources():
    def handler(request):
        if request.url.host == 'api.tavily.com':
            return httpx.Response(200,json={'results':[{'title':'重庆天气', 'url':'https://weather.example/chongqing', 'content':'重庆晴'}]})
        return fake_weather(request)
    result = json.loads(service(handler).search('北京'))
    assert len(result['sources']) == 1
    assert result['sources'][0]['title'].startswith('Open-Meteo')
    assert result['current_weather']['location'] == '中国 北京市 北京'


def test_weather_setting_environment_overrides_local_file(monkeypatch):
    monkeypatch.setenv('TAVILY_API_KEY','tvly-offline-env')
    monkeypatch.setenv('WEATHER_TIMEOUT','9')
    settings = Settings.load()
    assert settings.tavily_api_key == 'tvly-offline-env' and settings.weather_timeout == 9
