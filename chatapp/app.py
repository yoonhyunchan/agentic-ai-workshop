import json
import uuid
import boto3
import chainlit as cl
from chainlit.input_widget import TextInput

# -------------------------------------------------------
# 시작 화면 스타터 메시지
# -------------------------------------------------------
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


# -------------------------------------------------------
# 채팅 시작 시 설정 UI 표시
# -------------------------------------------------------
@cl.on_chat_start
async def start():
    await cl.ChatSettings([
        TextInput(
            id="agent_runtime_arn",
            label="AgentCore Runtime ARN",
            placeholder="arn:aws:bedrock-agentcore:ap-northeast-2:123456789012:agent-runtime/xxxxx",
            description="배포한 AgentCore Runtime의 ARN을 입력하세요.",
        )
    ]).send()

    # 세션 ID 초기화 (대화 컨텍스트 유지)
    cl.user_session.set("session_id", str(uuid.uuid4()))
    cl.user_session.set("agent_runtime_arn", None)


# -------------------------------------------------------
# 설정 업데이트 시 ARN 저장
# -------------------------------------------------------
@cl.on_settings_update
async def settings_update(settings):
    arn = settings.get("agent_runtime_arn", "").strip()
    cl.user_session.set("agent_runtime_arn", arn)

    if arn:
        await cl.Message(content=f"✅ AgentCore ARN이 설정되었습니다. 이제 질문해보세요!").send()
    else:
        await cl.Message(content="⚠️ ARN이 비어있습니다. 다시 입력해주세요.").send()


# -------------------------------------------------------
# 메시지 수신 및 AgentCore 호출
# -------------------------------------------------------
@cl.on_message
async def main(message: cl.Message):
    agent_runtime_arn = cl.user_session.get("agent_runtime_arn")
    session_id = cl.user_session.get("session_id")

    # ARN 미입력 시 안내
    if not agent_runtime_arn:
        await cl.Message(
            content="⚠️ 먼저 **⚙️ 설정**에서 AgentCore Runtime ARN을 입력해주세요."
        ).send()
        return

    # AgentCore 호출
    try:
        async with cl.Step(name="AgentCore Runtime", type="tool") as step:
            step.input = message.content

            client = boto3.client("bedrock-agentcore", region_name="ap-northeast-2")
            payload = json.dumps({"prompt": message.content}).encode()

            response = client.invoke_agent_runtime(
                agentRuntimeArn=agent_runtime_arn,
                runtimeSessionId=session_id,
                payload=payload,
            )

            # 응답 파싱
            full_response = ""
            content_type = response.get("contentType", "")

            if "text/event-stream" in content_type:
                for line in response["response"].iter_lines(chunk_size=10):
                    if line:
                        decoded = line.decode("utf-8")
                        if decoded.startswith("data: "):
                            full_response += decoded[6:]
            elif "application/json" in content_type:
                chunks = []
                for chunk in response.get("response", []):
                    chunks.append(chunk.decode("utf-8"))
                full_response = json.loads("".join(chunks))
                if isinstance(full_response, dict):
                    full_response = full_response.get("output", str(full_response))
            else:
                full_response = str(response)

            step.output = "AgentCore 응답 완료"

        # 스트리밍으로 답변 출력
        msg = cl.Message(content="")
        await msg.send()
        for token in full_response.split(" "):
            await msg.stream_token(token + " ")
        await msg.update()

    except Exception as e:
        await cl.Message(content=f"❌ 오류가 발생했습니다: {str(e)}").send()
