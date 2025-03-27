import os
import requests
import datetime
import json
from dotenv import load_dotenv
import urllib.parse

load_dotenv()

class WeatherTool:
    def __init__(self):
        self.api_key = os.getenv("WEATHER_API_KEY")
        self.base_url = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
    
    def get_weather(self, location):
        """
        주어진 위치의 날씨 정보를 가져옵니다.
        
        Args:
            location (str): 날씨 정보를 가져올 도시 이름
            
        Returns:
            dict: 날씨 정보를 담은 딕셔너리
        """
        # API 키 확인
        if not self.api_key:
            return {"error": "기상청 API 키가 설정되지 않았습니다. .env 파일에 유효한 API 키를 설정해주세요."}
        
        # 위치 코드 매핑 (간단한 예시)
        location_codes = {
            # 광역시/도
            "서울": {"nx": 60, "ny": 127},
            "인천": {"nx": 55, "ny": 124},
            "부산": {"nx": 98, "ny": 76},
            "대구": {"nx": 89, "ny": 90},
            "광주": {"nx": 58, "ny": 74},
            "대전": {"nx": 67, "ny": 100},
            "울산": {"nx": 102, "ny": 84},
            "세종": {"nx": 66, "ny": 103},
            "경기": {"nx": 60, "ny": 120},
            "강원": {"nx": 73, "ny": 134},
            "충북": {"nx": 69, "ny": 107},
            "충남": {"nx": 68, "ny": 100},
            "전북": {"nx": 63, "ny": 89},
            "전남": {"nx": 51, "ny": 67},
            "경북": {"nx": 89, "ny": 91},
            "경남": {"nx": 91, "ny": 77},
            "제주": {"nx": 52, "ny": 38},
            
            # 서울 구 단위
            "구로구": {"nx": 58, "ny": 125},
            "은평구": {"nx": 59, "ny": 127},
            "양천구": {"nx": 58, "ny": 126}
        }
        
        # 위치 코드 확인
        if location not in location_codes:
            return {"error": f"'{location}'에 대한 위치 코드가 없습니다. 다음 중 하나를 입력해주세요: {', '.join(location_codes.keys())}"}
        
        # 현재 날짜와 시간 정보
        now = datetime.datetime.now()
        base_date = now.strftime("%Y%m%d")  # 오늘 날짜
        
        # 기상청 API는 02:00, 05:00, 08:00, 11:00, 14:00, 17:00, 20:00, 23:00에 발표
        # 가장 최근 발표 시간을 사용
        forecast_hours = [2, 5, 8, 11, 14, 17, 20, 23]
        current_hour = now.hour
        
        # 가장 최근 발표 시간 찾기
        base_time = None
        for hour in sorted(forecast_hours, reverse=True):
            if current_hour >= hour:
                base_time = f"{hour:02d}00"
                break
        
        # 만약 오늘의 첫 발표 시간(02:00) 이전이라면 어제의 마지막 발표 시간(23:00) 사용
        if base_time is None:
            yesterday = now - datetime.timedelta(days=1)
            base_date = yesterday.strftime("%Y%m%d")
            base_time = "2300"
        
        # 파라미터 설정
        params = {
            'serviceKey': self.api_key,
            'pageNo': '1',
            'numOfRows': '1000',
            'dataType': 'JSON',
            'base_date': base_date,
            'base_time': base_time,
            'nx': location_codes[location]["nx"],
            'ny': location_codes[location]["ny"]
        }
        
        try:
            response = requests.get(self.base_url, params=params)
            
            # API 응답 상태 코드 확인
            if response.status_code != 200:
                return {"error": f"날씨 정보를 가져오는 중 오류가 발생했습니다. 상태 코드: {response.status_code}"}
            
            # XML 응답 확인
            if "<OpenAPI_ServiceResponse>" in response.text:
                error_msg = "API 키가 유효하지 않거나 등록되지 않았습니다. 공공데이터포털에서 발급받은 올바른 API 키를 사용해주세요."
                if "SERVICE_KEY_IS_NOT_REGISTERED_ERROR" in response.text:
                    error_msg = "등록되지 않은 API 키입니다. 공공데이터포털에서 발급받은 올바른 API 키를 사용해주세요."
                elif "SERVICE_KEY_IS_NOT_REGISTERED" in response.text:
                    error_msg = "등록되지 않은 API 키입니다. 공공데이터포털에서 발급받은 올바른 API 키를 사용해주세요."
                elif "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR" in response.text:
                    error_msg = "일일 요청 한도를 초과했습니다. 내일 다시 시도해주세요."
                elif "DEADLINE_HAS_EXPIRED" in response.text:
                    error_msg = "API 사용 기간이 만료되었습니다. 공공데이터포털에서 API 사용 신청을 갱신해주세요."
                elif "INVALID_PARAMETER" in response.text:
                    error_msg = "잘못된 파라미터가 전달되었습니다. base_date와 base_time을 확인해주세요."
                return {"error": error_msg}
            
            # 응답 데이터 파싱
            try:
                data = response.json()
            except json.JSONDecodeError:
                return {"error": "API 응답을 JSON으로 파싱할 수 없습니다."}
            
            # 응답 결과 코드 확인
            if 'response' not in data or 'header' not in data['response']:
                return {"error": "API 응답 형식이 올바르지 않습니다."}
                
            result_code = data['response']['header']['resultCode']
            if result_code != '00':
                return {"error": f"API 호출 오류: {data['response']['header']['resultMsg']}"}
            
            # 데이터 항목 확인
            if 'body' not in data['response'] or 'items' not in data['response']['body'] or 'item' not in data['response']['body']['items']:
                return {"error": "API 응답에 날씨 데이터가 없습니다."}
                
            items = data['response']['body']['items']['item']
            if not items:
                return {"error": "날씨 데이터가 없습니다."}
            
            # 필요한 날씨 정보 추출
            weather_info = {
                "location": location,
                "date": base_date,
                "time": base_time,
                "forecasts": []
            }
            
            # 날씨 코드 매핑
            weather_codes = {
                "POP": "강수확률",
                "PTY": "강수형태",
                "REH": "습도",
                "SKY": "하늘상태",
                "TMP": "기온",
                "TMN": "최저기온",
                "TMX": "최고기온",
                "UUU": "동서바람성분",
                "VVV": "남북바람성분",
                "WAV": "파고",
                "VEC": "풍향",
                "WSD": "풍속"
            }
            
            # 강수형태 코드 매핑
            pty_codes = {
                "0": "없음",
                "1": "비",
                "2": "비/눈",
                "3": "눈",
                "4": "소나기"
            }
            
            # 하늘상태 코드 매핑
            sky_codes = {
                "1": "맑음",
                "3": "구름많음",
                "4": "흐림"
            }
            
            # 현재 시간에 가장 가까운 예보 데이터 찾기
            current_forecast = {}
            for item in items:
                category = item['category']
                fcst_date = item['fcstDate']
                fcst_time = item['fcstTime']
                
                # 현재 시간 이후의 예보만 사용
                current_time = now.strftime("%H%M")
                if (fcst_date > base_date) or (fcst_date == base_date and fcst_time >= current_time):
                    if category in weather_codes:
                        if category == "PTY":
                            value = pty_codes.get(item['fcstValue'], item['fcstValue'])
                        elif category == "SKY":
                            value = sky_codes.get(item['fcstValue'], item['fcstValue'])
                        else:
                            value = item['fcstValue']
                        
                        # 시간별 예보 저장
                        forecast_key = f"{fcst_date}_{fcst_time}"
                        if forecast_key not in current_forecast:
                            current_forecast[forecast_key] = {
                                "date": fcst_date,
                                "time": fcst_time,
                                "data": {}
                            }
                        
                        current_forecast[forecast_key]["data"][weather_codes[category]] = value
            
            # 시간별로 정렬하여 예보 추가
            sorted_forecasts = sorted(current_forecast.values(), key=lambda x: (x["date"], x["time"]))
            
            # 최대 24시간의 예보만 포함
            for forecast in sorted_forecasts[:24]:
                formatted_time = f"{forecast['time'][:2]}:{forecast['time'][2:]}"
                formatted_date = f"{forecast['date'][4:6]}/{forecast['date'][6:]}"
                
                weather_info["forecasts"].append({
                    "date": formatted_date,
                    "time": formatted_time,
                    "data": forecast["data"]
                })
            
            # 현재 날씨 정보 추출 (가장 빠른 시간의 예보)
            if weather_info["forecasts"]:
                current_data = weather_info["forecasts"][0]["data"]
                weather_info["current"] = {
                    "temperature": current_data.get("기온", "정보 없음"),
                    "sky": current_data.get("하늘상태", "정보 없음"),
                    "precipitation_type": current_data.get("강수형태", "정보 없음"),
                    "precipitation_probability": current_data.get("강수확률", "정보 없음"),
                    "humidity": current_data.get("습도", "정보 없음"),
                    "wind_speed": current_data.get("풍속", "정보 없음")
                }
            
            return weather_info
        
        except requests.exceptions.RequestException as e:
            return {"error": f"날씨 정보를 가져오는 중 오류가 발생했습니다: {str(e)}"}
        except (KeyError, IndexError, ValueError) as e:
            return {"error": f"날씨 데이터 처리 중 오류가 발생했습니다: {str(e)}"} 