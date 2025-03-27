import streamlit as st
import os
from openai import OpenAI
from dotenv import load_dotenv
from weather_tool import WeatherTool
import json
import time
import requests

# 환경 변수 로드
load_dotenv()

# OpenAI 클라이언트 설정
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 카카오 API 키 설정
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")
KAKAO_JAVASCRIPT_KEY = os.getenv("KAKAO_JAVASCRIPT_API_KEY")

# 날씨 도구 정의
weather_tool = WeatherTool()

# 도구 정의
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "주어진 위치의 현재 날씨 정보를 가져옵니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "도시 이름 또는 서울 구 이름 (예: '서울', '부산', '인천', '대구', '광주', '대전', '울산', '세종', '경기', '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주', '구로구', '은평구', '양천구')"
                    }
                },
                "required": ["location"]
            }
        }
    }
]

def run_conversation(user_input):
    """
    사용자 입력을 받아 에이전트와 대화를 진행합니다.
    
    Args:
        user_input (str): 사용자 입력 메시지
        
    Returns:
        str: 에이전트의 응답
    """
    try:
        # 에이전트 생성 및 대화 시작
        assistant = client.beta.assistants.create(
            name="날씨 도우미",
            instructions="""
            당신은 날씨 정보를 제공하는 도우미입니다. 
            사용자가 특정 도시나 서울의 구의 날씨에 대해 물어보면 get_weather 함수를 사용하여 정보를 제공하세요.
            날씨 정보에 오류가 있는 경우, 사용자에게 친절하게 설명하고 해결 방법을 안내해주세요.
            
            날씨 정보를 제공할 때는 다음 정보를 포함하세요:
            1. 현재 하늘 상태 (맑음, 구름많음, 흐림 등)
            2. 현재 기온
            3. 강수 형태 및 확률
            4. 습도
            5. 풍속
            
            시간별 예보 정보도 있다면 간략하게 요약해서 알려주세요.
            
            지원하는 지역:
            - 광역시/도: 서울, 부산, 인천, 대구, 광주, 대전, 울산, 세종, 경기, 강원, 충북, 충남, 전북, 전남, 경북, 경남, 제주
            - 서울 구 단위: 구로구, 은평구, 양천구
            
            항상 친절하고 도움이 되는 방식으로 응답하세요.
            한국어로 응답하세요.
            """,
            model="gpt-4o",
            tools=tools
        )
        
        thread = client.beta.threads.create()
        
        # 사용자 메시지 추가
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_input
        )
        
        # 실행 생성
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=assistant.id
        )
        
        # 실행 상태 확인
        while True:
            run = client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )
            
            if run.status == "requires_action":
                tool_calls = run.required_action.submit_tool_outputs.tool_calls
                tool_outputs = []
                
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    if function_name == "get_weather":
                        output = weather_tool.get_weather(function_args["location"])
                        tool_outputs.append({
                            "tool_call_id": tool_call.id,
                            "output": json.dumps(output, ensure_ascii=False)
                        })
                
                # 도구 출력 제출
                client.beta.threads.runs.submit_tool_outputs(
                    thread_id=thread.id,
                    run_id=run.id,
                    tool_outputs=tool_outputs
                )
            
            elif run.status == "completed":
                # 응답 가져오기
                messages = client.beta.threads.messages.list(
                    thread_id=thread.id
                )
                
                # 가장 최근 응답 반환
                for message in messages.data:
                    if message.role == "assistant":
                        return message.content[0].text.value
            
            elif run.status in ["failed", "cancelled", "expired"]:
                return f"대화 처리 중 오류가 발생했습니다: {run.status}"
            
            # 잠시 대기
            time.sleep(1)
    
    except Exception as e:
        return f"에이전트 실행 중 오류가 발생했습니다: {str(e)}"

# Streamlit 앱 설정
st.set_page_config(
    page_title="날씨 AI 도우미",
    page_icon="🌤️",
    layout="wide"
)

# 앱 제목
st.title("🌤️ 날씨 AI 도우미")

# 소개 텍스트
st.markdown("""
이 앱은 OpenAI의 GPT-4o와 기상청 API를 사용하여 날씨 정보를 제공합니다.
원하는 지역의 날씨에 대해 질문해보세요!
""")

# 카카오 API 키 확인
if not KAKAO_REST_API_KEY or not KAKAO_JAVASCRIPT_KEY:
    st.error("카카오 API 키가 설정되지 않았습니다. .env 파일에 KAKAO_REST_API_KEY와 KAKAO_JAVASCRIPT_KEY를 설정해주세요.")
else:
    # 카카오맵 HTML
    st.markdown(f"""
    <div id="map" style="width:100%;height:400px;"></div>
    <script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={KAKAO_JAVASCRIPT_KEY}&libraries=services"></script>
    <script>
    window.onload = function() {{
        var container = document.getElementById('map');
        if (!container) {{
            console.error('맵 컨테이너를 찾을 수 없습니다.');
            return;
        }}
        
        var options = {{
            center: new kakao.maps.LatLng(37.5665, 126.9780),
            level: 3
        }};
        
        try {{
            var map = new kakao.maps.Map(container, options);
            var geocoder = new kakao.maps.services.Geocoder();
            
            // 초기 마커 생성
            var marker = new kakao.maps.Marker({{
                map: map,
                position: new kakao.maps.LatLng(37.5665, 126.9780)
            }});
            
            console.log('카카오맵 초기화 완료');
        }} catch (error) {{
            console.error('카카오맵 초기화 실패:', error);
        }}
    }};
    </script>
    """, unsafe_allow_html=True)

# 지역 검색
search_query = st.text_input("지역을 검색하세요:", key="location_search")
if search_query:
    # 카카오 API를 사용하여 지역 검색
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    url = f"https://dapi.kakao.com/v2/local/search/address.json?query={search_query}"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        if data["documents"]:
            location = data["documents"][0]
            st.write(f"검색된 위치: {location['address_name']}")
            st.write(f"위도: {location['y']}")
            st.write(f"경도: {location['x']}")
            
            # 지도 중심 이동을 위한 JavaScript
            st.markdown(f"""
            <script>
            var lat = {location['y']};
            var lng = {location['x']};
            var moveLatLng = new kakao.maps.LatLng(lat, lng);
            map.setCenter(moveLatLng);
            var marker = new kakao.maps.Marker({{
                map: map,
                position: moveLatLng
            }});
            </script>
            """, unsafe_allow_html=True)
        else:
            st.warning("검색 결과가 없습니다.")

# 사이드바에 지원 지역 표시
st.sidebar.title("지원하는 지역")
st.sidebar.markdown("**광역시/도**")
st.sidebar.markdown("서울, 부산, 인천, 대구, 광주, 대전, 울산, 세종, 경기, 강원, 충북, 충남, 전북, 전남, 경북, 경남, 제주")
st.sidebar.markdown("**서울 구 단위**")
st.sidebar.markdown("구로구, 은평구, 양천구")

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# 이전 메시지 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 사용자 입력 처리
if prompt := st.chat_input("질문을 입력하세요 (예: '서울의 날씨는 어때요?')"):
    # 사용자 메시지 표시
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # 사용자 메시지 저장
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # 응답 생성 중 표시
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("🤔 생각 중...")
        
        # 응답 생성
        response = run_conversation(prompt)
        
        # 응답 표시
        message_placeholder.markdown(response)
    
    # 응답 저장
    st.session_state.messages.append({"role": "assistant", "content": response})

# 앱 실행 방법 안내
st.markdown("---")
st.markdown("""
### 앱 실행 방법
1. 터미널에서 다음 명령어를 실행하세요:
```
streamlit run app.py
```
2. 웹 브라우저가 자동으로 열리고 앱이 실행됩니다.
""")

# 주의사항
st.sidebar.markdown("---")
st.sidebar.markdown("### 주의사항")
st.sidebar.markdown("""
- 기상청 API 키가 필요합니다.
- `.env` 파일에 API 키를 설정해야 합니다.
- 일일 API 호출 한도가 있을 수 있습니다.
""")

# 푸터
st.sidebar.markdown("---")
st.sidebar.markdown("© 2023 날씨 AI 도우미") 