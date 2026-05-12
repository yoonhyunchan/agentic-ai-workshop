from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from datetime import datetime

# ============================================================
# Tools
# ============================================================

@tool
def get_schedule(date: str) -> str:
  """특정 날짜의 일정을 조회합니다. date는 'YYYY-MM-DD' 형식입니다."""
  schedules = {
      "2026-05-05": "10:00 팀 미팅, 14:00 고객사 미팅, 16:00 코드 리뷰",
      "2026-05-06": "09:00 스프린트 플래닝, 15:00 1:1 미팅",
      "2026-05-07": "종일 워크샵"
  }
  return schedules.get(date, f"{date}에 등록된 일정이 없습니다.")

@tool
def get_current_time() -> str:
  """현재 날짜와 시간을 반환합니다."""
  return datetime.now().strftime("%Y-%m-%d %H:%M")

@tool
def calculator(expression: str) -> str:
  """수학 계산을 수행합니다. expression은 계산할 수식입니다."""
  try:
      return str(eval(expression))
  except Exception as e:
      return f"계산 오류: {e}"

# ============================================================
# Agent
# ============================================================

model = BedrockModel(
  model_id="us.amazon.nova-2-lite-v1:0",
  region_name="us-east-1"
)

agent = Agent(
  model=model,
  tools=[get_schedule, get_current_time, calculator],
  system_prompt="""너는 업무 비서 Agent야. 다음 도구를 활용해서 사용자를 도와줘:
- 일정 조회
- 현재 시간 확인
- 계산
한국어로 답변해."""
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
