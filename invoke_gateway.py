import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from urllib.parse import urlparse
import requests
import json

session = boto3.Session()
credentials = session.get_credentials().get_frozen_credentials()
gateway_url = "https://gateway-quick-start-c7e33c-r32ay06enf.gateway.bedrock-agentcore.ap-northeast-2.amazonaws.com/mcp"
host = urlparse(gateway_url).netloc


def call_mcp(method, params=None, request_id="1"):
    payload_json = json.dumps({
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": params or {},
    })

    request = AWSRequest(
        method="POST",
        url=gateway_url,
        data=payload_json,  # MCP 요청 바디
        headers={"Content-Type": "application/json", "Host": host},
    )
    SigV4Auth(credentials, "bedrock-agentcore", "ap-northeast-2").add_auth(request)

    response = requests.post(gateway_url, headers=dict(request.headers), data=payload_json)
    return response


# Gateway에 연결된 툴 목록 조회
tools_response = call_mcp("tools/list", request_id="0")
print(tools_response)
tools = tools_response.json().get("result", {}).get("tools", [])
for tool in tools:
    print(f"- {tool['name']}: {tool.get('description')}")

# 툴 호출
response = call_mcp("tools/call", {
    "name": "target-quick-start-opy6um___send_notification",
    "arguments": {
        "message": "주문 #A1029 배송이 3일 지연되었습니다.",
        "subject": "배송 지연 알림"
    }
})

print(response)
print(response.text)