import os
import json
import uuid
import boto3
import chainlit as cl
import chainlit.data as cl_data
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from chainlit.input_widget import TextInput


def _parse_json_col(value):
    """SQLite 는 JSON 컬럼을 TEXT 로 반환하므로 dict 로 변환한다."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return {}
    return value if isinstance(value, dict) else {}


class SQLiteSafeDataLayer(SQLAlchemyDataLayer):
    """SQLite TEXT JSON 컬럼을 안전하게 파싱하는 패치 레이어."""

    async def get_all_user_threads(self, user_id=None, thread_id=None):
        threads = await super().get_all_user_threads(
            user_id=user_id, thread_id=thread_id
        )
        if not threads:
            return threads
        for thread in threads:
            thread["metadata"] = _parse_json_col(thread.get("metadata"))
            for step in thread.get("steps", []):
                step["metadata"] = _parse_json_col(step.get("metadata"))
                if isinstance(step.get("generation"), str):
                    step["generation"] = _parse_json_col(step["generation"]) or None
        return threads


# -------------------------------------------------------
# 인증 (과거 대화 기록을 유저별로 묶기 위해 필수)
# -------------------------------------------------------
@cl.password_auth_callback
def auth_callback(username: str, password: str):
    # 워크샵용 간단 인증. 실제 배포 시 교체하세요.
    if (username, password) == ("admin", "admin"):
        return cl.User(identifier="admin", metadata={"role": "admin"})
    return None


# -------------------------------------------------------
# 데이터 레이어 (대화/메시지를 DB에 영속화 → 사이드바 기록)
#   DATABASE_URL 예시
#     SQLite : sqlite+aiosqlite:///./chainlit.db
#     Postgres: postgresql+asyncpg://user:pass@localhost:5432/chainlit
# -------------------------------------------------------
@cl.data_layer
def get_data_layer():
    return SQLiteSafeDataLayer(conninfo=os.environ["DATABASE_URL"])


# -------------------------------------------------------
# 시작 화면 스타터 메시지
# -------------------------------------------------------
@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="오늘 운동 기록",
            message="오늘 헬스 1시간 했어",
        ),
        cl.Starter(
            label="이번 주 요약",
            message="이번 주 운동 요약해줘",
        ),
        cl.Starter(
            label="목표 설정",
            message="주간 목표를 180분으로 잡아줘",
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

    # [변경①] 세션 ID = 스레드 ID (resume 시 동일 AgentCore 세션으로 이어가기 위함)
    cl.user_session.set("session_id", cl.context.session.thread_id)
    cl.user_session.set("agent_runtime_arn", None)


# -------------------------------------------------------
# 설정 업데이트 시 ARN 저장
# -------------------------------------------------------
@cl.on_settings_update
async def settings_update(settings):
    arn = settings.get("agent_runtime_arn", "").strip()
    cl.user_session.set("agent_runtime_arn", arn)

    if arn:
        # [변경②] ARN 을 스레드 metadata 에 영속화 (resume 시 복원용)
        thread_id = cl.context.session.thread_id
        await cl_data.get_data_layer().update_thread(
            thread_id, metadata={"agent_runtime_arn": arn}
        )
        await cl.Message(content="✅ AgentCore ARN이 설정되었습니다. 이제 질문해보세요!").send()
    else:
        await cl.Message(content="⚠️ ARN이 비어있습니다. 다시 입력해주세요.").send()


# -------------------------------------------------------
# [변경③] 과거 대화 이어가기 (resume 시 세션 상태 복원)
# -------------------------------------------------------
@cl.on_chat_resume
async def on_chat_resume(thread):
    # 세션 ID 복원: 스레드 ID 그대로 → 같은 AgentCore 세션으로 이어감
    cl.user_session.set("session_id", thread["id"])

    # ARN 복원: 설정할 때 저장해둔 thread metadata 에서 꺼냄
    metadata = thread.get("metadata") or {}
    cl.user_session.set("agent_runtime_arn", metadata.get("agent_runtime_arn"))

    # 설정 UI 다시 표시 (저장해둔 ARN 으로 채움)
    await cl.ChatSettings([
        TextInput(
            id="agent_runtime_arn",
            label="AgentCore Runtime ARN",
            initial=metadata.get("agent_runtime_arn", ""),
            description="배포한 AgentCore Runtime의 ARN을 입력하세요.",
        )
    ]).send()


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

            # ARN 에서 리전 추출: arn:aws:bedrock-agentcore:<region>:<acct>:...
            region = agent_runtime_arn.split(":")[3]
            client = boto3.client("bedrock-agentcore", region_name=region)
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

        await cl.Message(content=full_response).send()

    except Exception as e:
        await cl.Message(content=f"❌ 오류가 발생했습니다: {str(e)}").send()
