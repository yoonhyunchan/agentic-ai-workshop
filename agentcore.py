import json
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from datetime import date as _date

# ── 메모리 저장소 ──
WORKOUTS = []                 # [{"date","type","minutes"}, ...]
WEEKLY_GOAL = {"minutes": 150}   # 주간 목표 (WHO 권장 기본값)

@tool
def get_today() -> str:
  """오늘 날짜와 이번 주 시작일(월요일)을 반환한다.

  사용자가 '오늘', '어제', '이번 주' 같은 상대적 표현을 쓰면
  먼저 이 툴로 기준 날짜를 확인한 뒤 다른 툴에 넘긴다.
  """
  today = _date.today()
  monday = today.fromordinal(today.toordinal() - today.weekday())  # 이번 주 월요일
  return f"오늘은 {today.isoformat()} ({'월화수목금토일'[today.weekday()]}요일), 이번 주 시작(월)은 {monday.isoformat()}"

@tool
def log_workout(date: str, workout_type: str, minutes: int) -> str:
  """운동 기록을 추가한다.

  '오늘 30분 달렸어', '어제 요가 1시간' 처럼 운동한 내역을 기록할 때 사용한다.

  Args:
      date: 운동 날짜 'YYYY-MM-DD'
      workout_type: 운동 종류 (예: "달리기", "요가", "헬스")
      minutes: 운동 시간(분), 정수
  """
  WORKOUTS.append({"date": date, "type": workout_type, "minutes": minutes})
  return f"💪 기록 완료: {date} {workout_type} {minutes}분"

@tool
def weekly_summary(start_date: str) -> str:
  """특정 주(7일)의 운동 기록과 총 운동 시간을 요약한다.

  '이번 주 얼마나 운동했어?' 처럼 한 주 운동량을 모아 볼 때 사용한다.

  Args:
      start_date: 그 주의 시작 날짜 'YYYY-MM-DD' (이 날부터 7일간 집계)
  """
  from datetime import date as d
  y, m, day = map(int, start_date.split("-"))
  base = d(y, m, day)
  items = [w for w in WORKOUTS
           if 0 <= (d(*map(int, w["date"].split("-"))) - base).days < 7]
  total = sum(w["minutes"] for w in items)
  detail = ", ".join(f"{w['type']} {w['minutes']}분" for w in items) or "기록 없음"
  return f"{start_date}부터 7일: 총 {total}분 ({detail})"

@tool
def set_goal(minutes: int) -> str:
  """주간 운동 목표 시간(분)을 설정한다.

  '주 200분 목표로 잡아줘' 처럼 목표를 정할 때 사용한다.

  Args:
      minutes: 주간 목표 운동 시간(분)
  """
  WEEKLY_GOAL["minutes"] = minutes
  return f"🎯 주간 목표를 {minutes}분으로 설정했어요."

@tool
def check_goal(start_date: str) -> str:
  """그 주의 운동량이 주간 목표를 채웠는지 확인한다.

  '목표 채웠어?', '얼마나 남았어?' 처럼 목표 대비 진행률을 볼 때 사용한다.

  Args:
      start_date: 그 주의 시작 날짜 'YYYY-MM-DD'
  """
  from datetime import date as d
  y, m, day = map(int, start_date.split("-"))
  base = d(y, m, day)
  total = sum(w["minutes"] for w in WORKOUTS
              if 0 <= (d(*map(int, w["date"].split("-"))) - base).days < 7)
  goal = WEEKLY_GOAL["minutes"]
  remain = goal - total
  if remain <= 0:
      return f"🎉 목표 달성! {total}/{goal}분 ({-remain}분 초과 달성)"
  return f"{total}/{goal}분, 목표까지 {remain}분 남았어요. 화이팅!"

SYSTEM_PROMPT = """너는 친근한 운동 코치 비서야.

처음 대화를 시작하면 할 수 있는 일을 간단히 소개해:
- 운동 기록, 주간 운동 요약, 목표 설정, 목표 달성 여부 점검

매 대화 끝에 이번 주 목표 점검을 자연스럽게 한 번 언급해줘.
- 운동 기록 → log_workout, 주간 요약 → weekly_summary, 목표 설정 → set_goal, 목표 점검 → check_goal.
- '목표 채웠어?' 같은 질문은 그 주 운동량을 모아 목표와 비교해서 답해.
- 한국어로 짧고 응원하는 톤으로 답해."""

model = BedrockModel(
  model_id="us.amazon.nova-2-lite-v1:0",
  region_name="us-east-1"
)

agent = Agent(
  model=model,
  system_prompt=SYSTEM_PROMPT,
  tools=[get_today, log_workout, weekly_summary, set_goal, check_goal],
  callback_handler=None
)

# ============================================================
# AgentCore App
# ============================================================

app = BedrockAgentCoreApp()

@app.entrypoint
def invoke(payload):
    """Process user input and return a response"""
    user_message = payload.get("prompt", "No prompt found in input, please provide a json payload with 'prompt' key")
    result = agent(user_message)
    return str(result)

if __name__ == "__main__":
  app.run()