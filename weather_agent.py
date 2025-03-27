import os
from openai import OpenAI
from dotenv import load_dotenv
from weather_tool import WeatherTool
import json

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
            import time
            time.sleep(1)
    
    except Exception as e:
        return f"에이전트 실행 중 오류가 발생했습니다: {str(e)}"

if __name__ == "__main__":
    print("날씨 도우미에게 물어보세요! (종료하려면 'exit' 입력)")
    print("참고: 기상청 API 키를 .env 파일에 설정해야 합니다.")
    print("사용 가능한 지역:")
    print("- 광역시/도: 서울, 부산, 인천, 대구, 광주, 대전, 울산, 세종, 경기, 강원, 충북, 충남, 전북, 전남, 경북, 경남, 제주")
    print("- 서울 구 단위: 구로구, 은평구, 양천구")
    
    while True:
        user_input = input("\n질문: ")
        
        if user_input.lower() == "exit":
            print("대화를 종료합니다.")
            break
        
        response = run_conversation(user_input)
        print(f"\n도우미: {response}") 