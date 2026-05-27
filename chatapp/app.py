import asyncio
import chainlit as cl

@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="Strands Agent 테스트",
            message="Strands Agent를 테스트해줘",
        ),
        cl.Starter(
            label="Bedrock 모델 추천",
            message="AWS Bedrock 모델 추천해줘",
        ),
        cl.Starter(
            label="AgentCore 소개",
            message="Amazon Bedrock AgentCore가 뭐야?",
        ),
    ]


@cl.on_message
async def main(message: cl.Message):

    # 1. 툴 실행 단계 시각화
    async with cl.Step(name="Strands Agent Core", type="tool") as step:
        step.input = message.content
        await asyncio.sleep(1.5)
        tool_result = f"'{message.content}'에 대한 분석 완료"
        step.output = tool_result

    # 2. 최종 답변 스트리밍
    msg = cl.Message(content="")
    await msg.send()

    fake_response = f"""안녕하세요! **'{message.content}'** 질문을 받았습니다.

아래는 Strands Agent 예시 코드입니다:

```python
from strands import Agent
from strands_tools import calculator

agent = Agent(tools=[calculator])
result = agent("100 + 200은 얼마야?")
print(result)
```

`{tool_result}` 분석 완료 👍"""

    for token in fake_response.split(" "):
        await msg.stream_token(token + " ")
        await asyncio.sleep(0.05)

    await msg.update()
